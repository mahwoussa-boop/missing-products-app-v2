"""
sovereign_matcher.py — محرك المطابقة السيادي لمتجر مهووس
═══════════════════════════════════════════════════════════════
v9.0 — دعم التجميع الذكي وتصحيح نسب المطابقة 
"""

import re
import json
import asyncio
import pandas as pd
import streamlit as st
import google.generativeai as genai
from rapidfuzz import fuzz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from typing import Dict, Any
import threading
from streamlit.runtime.scriptrunner import add_script_run_ctx

from config import GEMINI_API_KEY, SYNONYMS

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

class SovereignMatcher:
    def __init__(self, mahwous_df: pd.DataFrame):
        self.mahwous_df = mahwous_df
        
        if self.mahwous_df.empty:
            self.mah_processed = pd.DataFrame(columns=['product_name', 'clean_name', 'category', 'brand', 'size'])
            self.vectorizer = TfidfVectorizer(ngram_range=(1, 3), analyzer='char_wb')
            self.tfidf_matrix = self.vectorizer.fit_transform(["منتج_بديل_فارغ"])
            return

        self.mah_processed = self._preprocess_df(mahwous_df)
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 3), analyzer='char_wb')
        
        try:
            self.tfidf_matrix = self.vectorizer.fit_transform(self.mah_processed['clean_name'])
        except ValueError:
            self.mah_processed['clean_name'] = 'منتج_بدون_اسم_معروف'
            self.tfidf_matrix = self.vectorizer.fit_transform(self.mah_processed['clean_name'])

    def _preprocess_df(self, df: pd.DataFrame) -> pd.DataFrame:
        processed = df.copy()
        if 'product_name' not in processed.columns:
            processed['product_name'] = 'منتج_بدون_اسم'
            
        processed['clean_name'] = processed['product_name'].astype(str).apply(self.normalize_text)
        processed['clean_name'] = processed['clean_name'].replace(r'^\s*$', 'منتج_بدون_اسم', regex=True).fillna('منتج_بدون_اسم')
        
        if processed['clean_name'].str.strip().eq('').all():
            processed['clean_name'] = 'منتج_بدون_اسم'
            
        processed['category'] = processed['clean_name'].apply(self.detect_category)
        processed['brand'] = processed['product_name'].astype(str).apply(self.extract_brand)
        processed['size'] = processed['product_name'].astype(str).apply(self.extract_size)
        return processed

    @staticmethod
    def normalize_text(text: str) -> str:
        if not text or pd.isna(text): return "منتج_بدون_اسم"
        text = str(text).lower().strip()
        for word, syn in SYNONYMS.items(): text = text.replace(word, syn)
        text = re.sub("[إأآا]", "ا", text)
        text = re.sub("ة", "ه", text)
        text = re.sub("ى", "ي", text)
        text = re.sub(r"[\u064B-\u0652]", "", text)
        text = re.sub(r"[^\w\s]", " ", text)
        cleaned = " ".join(text.split())
        return cleaned if cleaned else "منتج_بدون_اسم"

    @staticmethod
    def detect_category(text: str) -> str:
        if any(k in text for k in ['عطر', 'perfume', 'edp', 'edt', 'parfum', 'كولونيا']): return 'perfume'
        if any(k in text for k in ['روج', 'شفاه', 'مكياج', 'makeup', 'خدود', 'بلشر', 'هايلايتر', 'ماسكارا', 'بودره', 'ايلاينر']): return 'makeup'
        if any(k in text for k in ['لوشن', 'مرطب', 'جسم', 'body', 'lotion', 'كريم', 'شاور']): return 'skincare'
        return 'other'

    @staticmethod
    def extract_brand(name: str) -> str:
        name_lower = name.lower()
        for syn, brand in SYNONYMS.items():
            if syn in name_lower: return brand
        return "unknown"

    @staticmethod
    def extract_size(name: str) -> str:
        match = re.search(r'(\d+)\s*(ml|مل|لتر|l)', name.lower())
        return match.group(0) if match else "unknown"

    def find_best_match(self, comp_name: str) -> Dict[str, Any]:
        if self.mahwous_df.empty:
            return {"status": "مفقود أكيد", "confidence_level": "green", "match_name": "", "match_image": "", "match_price": 0, "match_score": 0}

        clean_comp = self.normalize_text(comp_name)
        cat_comp = self.detect_category(clean_comp)
        brand_comp = self.extract_brand(comp_name)
        size_comp = self.extract_size(comp_name)

        potential_indices = self.mah_processed[self.mah_processed['category'] == cat_comp].index
        if len(potential_indices) == 0: potential_indices = self.mah_processed.index
        if not clean_comp.strip(): clean_comp = 'منتج_بدون_اسم'

        try:
            comp_vec = self.vectorizer.transform([clean_comp])
            cosine_sims = cosine_similarity(comp_vec, self.tfidf_matrix).flatten()
        except ValueError:
            cosine_sims = [0] * len(self.mah_processed)
        
        best_idx = -1
        best_score = 0
        
        for idx in potential_indices:
            f_score = fuzz.token_set_ratio(clean_comp, self.mah_processed.at[idx, 'clean_name'])
            combined_score = (cosine_sims[idx] * 40) + (f_score * 0.6)
            
            if brand_comp != "unknown" and brand_comp == self.mah_processed.at[idx, 'brand']: combined_score += 10
            if size_comp != "unknown" and size_comp == self.mah_processed.at[idx, 'size']: combined_score += 5

            if combined_score > best_score:
                best_score = combined_score
                best_idx = idx

        # ─── تحديد الأقسام بدقة بناءً على طلبك ───
        # من 0 إلى 45 -> مفقود أكيد (القسم الأخضر)
        # من 46 إلى 85 -> يحتاج مراجعة (القسم الأصفر)
        # من 86 إلى 100 -> متطابق متوفر لدينا (القسم الأحمر)
        
        status = "مفقود أكيد"
        confidence = "green"
        match_info = {}

        if best_idx != -1:
            match_row = self.mahwous_df.iloc[best_idx]
            match_info = {
                "match_name": match_row.get('product_name', ''),
                "match_image": match_row.get('image_url', ''),
                "match_price": match_row.get('price', 0),
                "match_score": round(best_score, 1)
            }
            
            if best_score > 85:
                status = "متطابق (متوفر)"
                confidence = "red"
            elif best_score > 45:
                status = "مشتبه به (مراجعة)"
                confidence = "yellow"

        return {
            "status": status,
            "confidence_level": confidence,
            **match_info
        }

async def ai_verify_match(comp_name: str, match_name: str) -> Dict:
    if not GEMINI_API_KEY: return {"is_match": False, "reason": "No API Key"}
    prompt = f"""قارن بين هذين المنتجين بدقة: المنتج 1: {comp_name} | المنتج 2: {match_name}
    أجب بصيغة JSON: {{"is_match": true/false, "reason": "شرح موجز بالعربية"}}"""
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = await asyncio.to_thread(model.generate_content, prompt)
        return json.loads(re.sub(r'```json\s*|\s*```', '', response.text).strip())
    except: return {"is_match": False, "reason": "AI Error"}

def _run_analysis_thread(mahwous_df, competitor_data, matcher):
    raw_results = []
    
    # 1. جمع كل البيانات أولاً
    for comp_file, df in competitor_data.items():
        if df.empty: continue
        for _, row in df.iterrows():
            if not st.session_state.analysis_running: break
            prod_name = str(row.get('product_name', 'منتج_غير_معروف')).strip()
            if not prod_name: continue
            
            match_res = matcher.find_best_match(prod_name)
            raw_results.append({
                "product_name": prod_name,
                "price": row.get('price', 0),
                "image_url": row.get('image_url', ''),
                "competitor_name": comp_file.replace('.csv', ''),
                **match_res
            })
            st.session_state.processed_count += 1
            if st.session_state.processed_count % 10 == 0:
                st.session_state.analysis_results = raw_results
                
    if not st.session_state.analysis_running: return

    # 2. التجميع الذكي للمنافسين (Smart Grouping)
    if raw_results:
        df_res = pd.DataFrame(raw_results)
        grouped = df_res.groupby('product_name', as_index=False).agg({
            'price': lambda x: f"{min(x)} - {max(x)}" if min(x) != max(x) else str(min(x)),
            'competitor_name': lambda x: " ، ".join(set(x)),
            'image_url': 'first',
            'match_name': 'first',
            'match_image': 'first',
            'match_price': 'first',
            'match_score': 'max',
            'confidence_level': 'first',
            'status': 'first'
        })
        st.session_state.analysis_results = grouped.to_dict('records')
    else:
        st.session_state.analysis_results = []
        
    st.session_state.analysis_running = False
    st.session_state.needs_rerun = True

def start_sovereign_analysis(mahwous_df, competitor_data):
    try: matcher = SovereignMatcher(mahwous_df)
    except Exception as e:
        st.error(f"حدث خطأ غير متوقع أثناء تهيئة المحرك: {e}")
        st.session_state.analysis_running = False
        return

    st.session_state.total_count = sum(len(df) for df in competitor_data.values())
    st.session_state.processed_count = 0
    st.session_state.analysis_results = []
    st.session_state.analysis_running = True

    thread = threading.Thread(target=_run_analysis_thread, args=(mahwous_df, competitor_data, matcher))
    add_script_run_ctx(thread)
    thread.start()

"""
sovereign_matcher.py — محرك المطابقة السيادي (النسخة الصارمة V11.0)
═══════════════════════════════════════════════════════════════
- استبعاد العينات (أقل من 15 ريال أو 10 مل).
- قانون التستر الصارم (التستر لا يقارن إلا بتستر).
- عقوبات (Penalties) قاسية لاختلاف الماركة بوضوح.
- إعادة توزيع نسب الأقسام لتقليل أخطاء "تتطلب مراجعة".
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
        # 1. فلترة متجرنا أولاً (استبعاد العينات الصغيرة والرخيصة)
        self.mahwous_df = self._filter_samples(mahwous_df)
        
        if self.mahwous_df.empty:
            self.mah_processed = pd.DataFrame(columns=['product_name', 'clean_name', 'category', 'brand', 'size', 'is_tester'])
            self.vectorizer = TfidfVectorizer(ngram_range=(1, 3), analyzer='char_wb')
            self.tfidf_matrix = self.vectorizer.fit_transform(["فارغ"])
            return

        self.mah_processed = self._preprocess_df(self.mahwous_df)
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 3), analyzer='char_wb')
        
        try:
            self.tfidf_matrix = self.vectorizer.fit_transform(self.mah_processed['clean_name'])
        except ValueError:
            self.mah_processed['clean_name'] = 'منتج_مجهول'
            self.tfidf_matrix = self.vectorizer.fit_transform(self.mah_processed['clean_name'])

    def _filter_samples(self, df: pd.DataFrame) -> pd.DataFrame:
        """إزالة المنتجات التي يقل سعرها عن 15 ريال أو حجمها أقل من 10 مل."""
        if df.empty: return df
        # تنظيف السعر والحجم للفلترة
        df = df.copy()
        def get_vol(name):
            m = re.search(r'(\d+)\s*(ml|مل)', str(name).lower())
            return int(m.group(1)) if m else 50 # افتراض 50 إذا لم يوجد
        
        # تطبيق الفلترة الصارمة
        mask = (df['price'] >= 15) & (df['product_name'].apply(get_vol) >= 10)
        return df[mask].reset_index(drop=True)

    def _preprocess_df(self, df: pd.DataFrame) -> pd.DataFrame:
        processed = df.copy()
        processed['clean_name'] = processed['product_name'].astype(str).apply(self.normalize_text)
        processed['is_tester'] = processed['product_name'].astype(str).apply(self.check_if_tester)
        processed['brand'] = processed['product_name'].astype(str).apply(self.extract_brand)
        processed['size'] = processed['product_name'].astype(str).apply(self.extract_size)
        processed['category'] = processed['clean_name'].apply(self.detect_category)
        return processed

    @staticmethod
    def check_if_tester(text: str) -> bool:
        """تمييز التستر بصرامة."""
        kws = ['تستر', 'tester', 'بدون كرتون', 'بدون غطاء', 'تستير', 'علبة عادية']
        return any(kw in str(text).lower() for kw in kws)

    @staticmethod
    def normalize_text(text: str) -> str:
        if not text or pd.isna(text): return "منتج_فارغ"
        text = str(text).lower().strip()
        # إزالة كلمات الحشو التي ترفع النسبة كذباً
        fillers = ['عطر', 'perfume', 'بخاخ', 'spray', 'للجنسين', 'unisex', 'للرجال', 'men', 'للنساء', 'women']
        for f in fillers: text = text.replace(f, '')
        
        for word, syn in SYNONYMS.items(): text = text.replace(word, syn)
        text = re.sub("[إأآا]", "ا", text); text = re.sub("ة", "ه", text); text = re.sub("ى", "ي", text)
        text = re.sub(r"[^\w\s]", " ", text)
        return " ".join(text.split())

    @staticmethod
    def detect_category(text: str) -> str:
        if any(k in text for k in ['روج', 'شفاه', 'مكياج', 'خدود', 'بلشر']): return 'makeup'
        if any(k in text for k in ['جهاز', 'الة', 'فواحة', 'ترطيب']): return 'device'
        return 'perfume'

    @staticmethod
    def extract_brand(name: str) -> str:
        name_lower = str(name).lower()
        for syn, brand in SYNONYMS.items():
            if syn in name_lower: return brand
        # استخراج أول كلمة كماركة محتملة إذا لم يوجد في المترادفات
        words = name_lower.split()
        return words[0] if words else "unknown"

    @staticmethod
    def extract_size(name: str) -> str:
        match = re.search(r'(\d+)\s*(ml|مل)', str(name).lower())
        return match.group(1) if match else "unknown"

    def find_best_match(self, comp_name: str) -> Dict[str, Any]:
        if self.mahwous_df.empty:
            return {"status": "مفقود أكيد", "confidence_level": "green", "match_name": "", "match_image": "", "match_price": 0, "match_score": 0}

        # فلترة المنافس (إذا كان عينة رخيصة أو صغيرة، لا نفحصه أصلاً ونعتبره مفقوداً أو نتجاهله)
        # سيتم التعامل مع هذا في db_manager لتسريع العملية

        clean_comp = self.normalize_text(comp_name)
        is_tester_comp = self.check_if_tester(comp_name)
        brand_comp = self.extract_brand(comp_name)
        size_comp = self.extract_size(comp_name)
        cat_comp = self.detect_category(clean_comp)

        potential_indices = self.mah_processed[self.mah_processed['category'] == cat_comp].index
        if len(potential_indices) == 0: potential_indices = self.mah_processed.index

        try:
            comp_vec = self.vectorizer.transform([clean_comp])
            cosine_sims = cosine_similarity(comp_vec, self.tfidf_matrix).flatten()
        except:
            cosine_sims = [0] * len(self.mah_processed)
        
        best_idx = -1
        best_score = 0
        
        for idx in potential_indices:
            f_score = fuzz.token_set_ratio(clean_comp, self.mah_processed.at[idx, 'clean_name'])
            combined_score = (cosine_sims[idx] * 45) + (f_score * 0.55)
            
            # --- القوانين السيادية العقابية ---
            
            # 1. التستر ضد العادي (عقوبة قاسية جداً)
            if is_tester_comp != self.mah_processed.at[idx, 'is_tester']:
                combined_score *= 0.25 # خفض النسبة لـ 25% من قيمتها
            
            # 2. اختلاف الماركة (إذا كانت الماركة معروفة ومختلفة)
            mah_brand = self.mah_processed.at[idx, 'brand']
            if brand_comp != "unknown" and mah_brand != "unknown" and brand_comp != mah_brand:
                combined_score *= 0.40 
            
            # 3. اختلاف الحجم (عقوبة متوسطة)
            mah_size = self.mah_processed.at[idx, 'size']
            if size_comp != "unknown" and mah_size != "unknown" and size_comp != mah_size:
                combined_score *= 0.70

            if combined_score > best_score:
                best_score = combined_score
                best_idx = idx

        # --- إعادة ضبط العتبات بناءً على الطلب ---
        final_score = min(round(best_score, 1), 100.0)
        status = "مفقود أكيد"
        confidence = "green"
        match_info = {}

        if best_idx != -1:
            match_row = self.mahwous_df.iloc[best_idx]
            match_info = {
                "match_name": match_row['product_name'],
                "match_image": match_row.get('image_url', ''),
                "match_price": match_row.get('price', 0),
                "match_score": final_score
            }
            
            if final_score >= 90: # متطابق أكيد
                status = "متطابق (متوفر)"
                confidence = "red"
            elif final_score >= 68: # تتطلب مراجعة (تم رفع الحد لتقليل العدد)
                status = "مشتبه به (مراجعة)"
                confidence = "yellow"

        return {"status": status, "confidence_level": confidence, **match_info}

def _run_analysis_thread(mahwous_df, competitor_data, matcher):
    raw_results = []
    for comp_file, df in competitor_data.items():
        # فلترة ملف المنافس قبل الفحص (أقل من 15 ريال أو 10 مل)
        def get_vol(name):
            m = re.search(r'(\d+)\s*(ml|مل)', str(name).lower())
            return int(m.group(1)) if m else 50
        df = df[(df['price'] >= 15) & (df['product_name'].apply(get_vol) >= 10)]
        
        for _, row in df.iterrows():
            if not st.session_state.analysis_running: break
            prod_name = str(row.get('product_name', '')).strip()
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
            if st.session_state.processed_count % 20 == 0:
                st.session_state.analysis_results = raw_results
                
    if raw_results:
        df_res = pd.DataFrame(raw_results)
        grouped = df_res.groupby('product_name', as_index=False).agg({
            'price': lambda x: f"{min(x)} - {max(x)}" if min(x) != max(x) else str(min(x)),
            'competitor_name': lambda x: " ، ".join(set(x)),
            'image_url': 'first', 'match_name': 'first', 'match_image': 'first',
            'match_price': 'first', 'match_score': 'max', 'confidence_level': 'first', 'status': 'first'
        })
        st.session_state.analysis_results = grouped.to_dict('records')
    
    st.session_state.analysis_running = False
    st.session_state.needs_rerun = True

def start_sovereign_analysis(mahwous_df, competitor_data):
    try: matcher = SovereignMatcher(mahwous_df)
    except Exception as e:
        st.error(f"خطأ في تهيئة المحرك: {e}"); st.session_state.analysis_running = False; return
    
    # حساب الإجمالي بعد الفلترة التقريبية
    st.session_state.total_count = sum(len(df) for df in competitor_data.values())
    st.session_state.processed_count = 0
    st.session_state.analysis_results = []
    st.session_state.analysis_running = True
    thread = threading.Thread(target=_run_analysis_thread, args=(mahwous_df, competitor_data, matcher))
    add_script_run_ctx(thread)
    thread.start()

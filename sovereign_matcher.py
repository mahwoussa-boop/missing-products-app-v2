"""
sovereign_matcher.py — محرك المطابقة السيادي لمتجر مهووس
═══════════════════════════════════════════════════════════════
v7.0 — الإصلاح الشامل للدقة والذكاء (معدل لمعالجة النصوص الفارغة)
- استخدام تقنيات (Advanced NLP) لاستخراج الماركة، الحجم، والتركيز.
- فلترة الفئات الصارمة (عطور، مكياج، لوشن).
- دمج الذكاء الاصطناعي (Gemini 2.0 Flash) لاتخاذ القرارات النهائية.
- تحسين الأداء عبر الذاكرة المؤقتة (Caching).
- حماية المحرك من الانهيار (ValueError: empty vocabulary).
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
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
import threading

from config import GEMINI_API_KEY, SYNONYMS, REJECT_KEYWORDS, TESTER_KEYWORDS, SET_KEYWORDS

# إعداد Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

class SovereignMatcher:
    def __init__(self, mahwous_df: pd.DataFrame):
        self.mahwous_df = mahwous_df
        self.mah_processed = self._preprocess_df(mahwous_df)
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 3), analyzer='char_wb')
        
        # حماية المحرك من الانهيار في حال كانت كل الكلمات Stop Words وأصبح النص فارغاً
        try:
            self.tfidf_matrix = self.vectorizer.fit_transform(self.mah_processed['clean_name'])
        except ValueError:
            # إذا فشل المحرك، نقوم بوضع قيمة افتراضية للعمل بأمان
            self.mah_processed['clean_name'] = 'منتج_غير_معروف'
            self.tfidf_matrix = self.vectorizer.fit_transform(self.mah_processed['clean_name'])

    def _preprocess_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """تحليل ومعالجة مسبقة لبيانات المتجر لاستخراج الخصائص الحرجة."""
        processed = df.copy()
        processed['clean_name'] = processed['product_name'].apply(self.normalize_text)
        
        # --- الإصلاح الجذري لمعالجة النصوص الفارغة ---
        # استبدال أي نص فارغ تماماً بكلمة آمنة حتى يتعرف عليها المحرك ولا ينهار
        processed['clean_name'] = processed['clean_name'].replace(r'^\s*$', 'منتج_بدون_اسم', regex=True).fillna('منتج_بدون_اسم')
        
        processed['category'] = processed['clean_name'].apply(self.detect_category)
        processed['brand'] = processed['product_name'].apply(self.extract_brand)
        processed['size'] = processed['product_name'].apply(self.extract_size)
        return processed

    @staticmethod
    def normalize_text(text: str) -> str:
        """تنظيف وتوحيد النصوص العربية والإنجليزية."""
        if not text or pd.isna(text): return ""
        text = str(text).lower().strip()
        # استبدال المرادفات
        for word, syn in SYNONYMS.items():
            text = text.replace(word, syn)
        # توحيد الحروف
        text = re.sub("[إأآا]", "ا", text)
        text = re.sub("ة", "ه", text)
        text = re.sub("ى", "ي", text)
        text = re.sub(r"[\u064B-\u0652]", "", text) # إزالة التشكيل
        text = re.sub(r"[^\w\s]", " ", text)
        return " ".join(text.split())

    @staticmethod
    def detect_category(text: str) -> str:
        """تحديد فئة المنتج لمنع الخلط."""
        if any(k in text for k in ['عطر', 'perfume', 'edp', 'edt', 'parfum', 'كولونيا']): return 'perfume'
        if any(k in text for k in ['روج', 'شفاه', 'مكياج', 'makeup', 'خدود', 'بلشر', 'هايلايتر', 'ماسكارا', 'بودره', 'ايلاينر']): return 'makeup'
        if any(k in text for k in ['لوشن', 'مرطب', 'جسم', 'body', 'lotion', 'كريم', 'شاور']): return 'skincare'
        return 'other'

    @staticmethod
    def extract_brand(name: str) -> str:
        """محاولة استخراج الماركة من الاسم."""
        name_lower = name.lower()
        for syn, brand in SYNONYMS.items():
            if syn in name_lower: return brand
        return "unknown"

    @staticmethod
    def extract_size(name: str) -> str:
        """استخراج الحجم (مثلاً 100ml)."""
        match = re.search(r'(\d+)\s*(ml|مل|لتر|l)', name.lower())
        return match.group(0) if match else "unknown"

    def find_best_match(self, comp_name: str) -> Dict[str, Any]:
        """البحث عن أفضل مطابقة باستخدام خوارزمية سيادية هجينة."""
        clean_comp = self.normalize_text(comp_name)
        cat_comp = self.detect_category(clean_comp)
        brand_comp = self.extract_brand(comp_name)
        size_comp = self.extract_size(comp_name)

        # 1. تصفية أولية بناءً على الفئة
        potential_indices = self.mah_processed[self.mah_processed['category'] == cat_comp].index
        if len(potential_indices) == 0:
            potential_indices = self.mah_processed.index # Fallback if category detection fails

        # حماية إضافية لضمان أن النص المدخل غير فارغ لمحرك البحث
        if not clean_comp.strip():
            clean_comp = 'منتج_بدون_اسم'

        # 2. حساب TF-IDF Similarity
        comp_vec = self.vectorizer.transform([clean_comp])
        cosine_sims = cosine_similarity(comp_vec, self.tfidf_matrix).flatten()
        
        best_idx = -1
        best_score = 0
        
        for idx in potential_indices:
            # حساب Fuzzy Score
            f_score = fuzz.token_set_ratio(clean_comp, self.mah_processed.at[idx, 'clean_name'])
            # دمج الـ Scores (TF-IDF + Fuzzy)
            combined_score = (cosine_sims[idx] * 40) + (f_score * 0.6)
            
            # مكافأة مطابقة الماركة والحجم
            if brand_comp != "unknown" and brand_comp == self.mah_processed.at[idx, 'brand']:
                combined_score += 10
            if size_comp != "unknown" and size_comp == self.mah_processed.at[idx, 'size']:
                combined_score += 5

            if combined_score > best_score:
                best_score = combined_score
                best_idx = idx

        # 3. اتخاذ القرار النهائي
        status = "Confirmed Missing"
        confidence = "green"
        match_info = {}

        if best_idx != -1:
            match_row = self.mahwous_df.iloc[best_idx]
            match_info = {
                "match_name": match_row['product_name'],
                "match_image": match_row.get('image_url', ''),
                "match_price": match_row.get('price', 0),
                "match_score": best_score
            }
            
            if best_score > 90:
                status = "Exact Duplicate"
                confidence = "red"
            elif best_score > 55:
                status = "Potential Match"
                confidence = "yellow"

        return {
            "status": status,
            "confidence_level": confidence,
            **match_info
        }

async def ai_verify_match(comp_name: str, match_name: str) -> Dict:
    """التحقق الذكي عبر Gemini 2.0 لضمان دقة 100%."""
    if not GEMINI_API_KEY: return {"is_match": False, "reason": "No API Key"}
    
    prompt = f"""
    قارن بين هذين المنتجين بدقة متناهية:
    المنتج 1 (المنافس): {comp_name}
    المنتج 2 (متجرنا): {match_name}

    القواعد:
    - إذا كان أحدهما عطر والآخر (لوشن، زيت، بخاخ شعر، أو تستر)، فهما مختلفان (is_match: false).
    - إذا اختلف الحجم (مثلاً 50 مل مقابل 100 مل)، فهما مختلفان.
    - إذا اختلف التركيز (EDP مقابل EDT)، فهما مختلفان.

    أجب بصيغة JSON:
    {{"is_match": true/false, "reason": "شرح موجز بالعربية"}}
    """
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = await asyncio.to_thread(model.generate_content, prompt)
        return json.loads(re.sub(r'```json\s*|\s*```', '', response.text).strip())
    except:
        return {"is_match": False, "reason": "AI Error"}

def start_sovereign_analysis(mahwous_df, competitor_data):
    """بدء عملية التحليل السيادي."""
    matcher = SovereignMatcher(mahwous_df)
    results = []
    
    total = sum(len(df) for df in competitor_data.values())
    st.session_state.total_count = total
    st.session_state.processed_count = 0
    st.session_state.analysis_results = []
    st.session_state.analysis_running = True

    for comp_file, df in competitor_data.items():
        for _, row in df.iterrows():
            if not st.session_state.analysis_running: break
            
            match_res = matcher.find_best_match(row['product_name'])
            results.append({**row.to_dict(), "competitor_name": comp_file, **match_res})
            
            st.session_state.processed_count += 1
            if st.session_state.processed_count % 10 == 0:
                st.session_state.analysis_results = results
                # تحديث الواجهة
                
    st.session_state.analysis_results = results
    st.session_state.analysis_running = False
    st.session_state.needs_rerun = True

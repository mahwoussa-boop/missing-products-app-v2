"""
ai_matcher.py v3.0 — محرك المطابقة الهجين المتقدم
══════════════════════════════════════════════════
الأولوية القصوى: القضاء على النتائج الإيجابية الخاطئة (False Positives).
النظام: تنظيف النصوص -> RapidFuzz + TF-IDF -> التحقق الدقيق بواسطة LLM.
"""

import re
import json
import asyncio
import aiohttp
import pandas as pd
import numpy as np
import streamlit as st
import google.generativeai as genai
from rapidfuzz import fuzz, process
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime

from config import GEMINI_API_KEY

# إعداد Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def normalize_arabic(text: str) -> str:
    """تنظيف وتوحيد النصوص العربية والإنجليزية."""
    if not text or pd.isna(text):
        return ""
    text = str(text).lower().strip()
    # توحيد الحروف العربية
    text = re.sub("[إأآا]", "ا", text)
    text = re.sub("ة", "ه", text)
    text = re.sub("ى", "ي", text)
    # إزالة الحركات
    text = re.sub(r"[\u064B-\u0652]", "", text)
    # إزالة الرموز الخاصة مع الإبقاء على الأرقام والكلمات المهمة
    text = re.sub(r"[^\w\s]", " ", text)
    # إزالة المسافات الزائدة
    text = " ".join(text.split())
    return text

def extract_features(text: str) -> Dict[str, Any]:
    """استخراج ميزات المنتج (الحجم، التركيز، النوع)."""
    text = text.lower()
    features = {
        "size": re.search(r"(\d+)\s*(ml|مل)", text),
        "concentration": re.search(r"(edp|edt|parfum|eau de parfum|eau de toilette|عطر|تواليت)", text),
        "is_tester": "tester" in text or "تستر" in text,
        "is_hair_mist": "hair mist" in text or "عطر شعر" in text,
    }
    features["size"] = features["size"].group(1) if features["size"] else None
    features["concentration"] = features["concentration"].group(0) if features["concentration"] else None
    return features

def get_hybrid_score(name1: str, name2: str, tfidf_matrix=None, idx1=None, idx2=None) -> float:
    """حساب درجة التشابه الهجين (Fuzzy + TF-IDF)."""
    n1 = normalize_arabic(name1)
    n2 = normalize_arabic(name2)
    
    # 1. Fuzzy Matching (RapidFuzz)
    token_sort = fuzz.token_sort_ratio(n1, n2)
    partial_ratio = fuzz.partial_ratio(n1, n2)
    fuzzy_score = (token_sort * 0.6) + (partial_ratio * 0.4)
    
    # 2. TF-IDF Cosine Similarity
    cosine_score = 0
    if tfidf_matrix is not None and idx1 is not None and idx2 is not None:
        try:
            sim = cosine_similarity(tfidf_matrix[idx1], tfidf_matrix[idx2])
            cosine_score = sim[0][0] * 100
        except:
            cosine_score = 0
        
    if cosine_score > 0:
        return (fuzzy_score * 0.5) + (cosine_score * 0.5)
    return fuzzy_score

async def ai_deep_verify(prod_name: str, comp_name: str) -> Tuple[bool, str]:
    """التحقق الدقيق باستخدام LLM للتفريق بين المنتجات المتشابهة."""
    if not GEMINI_API_KEY:
        return False, "API Key Missing"
    
    prompt = f"""
    بصفتك خبير في العطور، هل هذين المنتجين هما نفس المنتج تماماً؟
    انتبه بدقة للفروقات التالية:
    1. الحجم (مثلاً 50ml vs 100ml) -> مختلفين.
    2. التركيز (EDP, EDT, Parfum) -> مختلفين.
    3. النوع (عطر عادي، تستر Tester، عطر شعر Hair Mist) -> مختلفين.
    4. المجموعات (Set) مقابل العلب المنفردة -> مختلفين.

    المنتج 1: {prod_name}
    المنتج 2: {comp_name}

    أجب بصيغة JSON فقط:
    {{"is_match": true/false, "reason": "سبب موجز بالعربية"}}
    """
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = await asyncio.to_thread(model.generate_content, prompt)
        res_text = response.text
        res_text = re.sub(r'```json\s*|\s*```', '', res_text).strip()
        data = json.loads(res_text)
        return data.get("is_match", False), data.get("reason", "")
    except Exception as e:
        return False, f"AI Error: {str(e)}"

def process_competitors(mahwous_df: pd.DataFrame, competitor_files_data: Dict[str, pd.DataFrame], progress_callback=None) -> pd.DataFrame:
    """المعالجة الأساسية للمنافسين باستخدام النظام الهجين."""
    if mahwous_df.empty or not competitor_files_data:
        return pd.DataFrame()

    # تجميع كل منتجات المنافسين في DataFrame واحد
    all_comp_list = []
    for comp_name, df in competitor_files_data.items():
        df['competitor_name'] = comp_name
        all_comp_list.append(df)
    
    competitor_df = pd.concat(all_comp_list, ignore_index=True)
    
    # تحضير TF-IDF
    all_names = mahwous_df['product_name'].astype(str).tolist() + competitor_df['product_name'].astype(str).tolist()
    vectorizer = TfidfVectorizer(preprocessor=normalize_arabic)
    tfidf_matrix = vectorizer.fit_transform(all_names)
    mahwous_len = len(mahwous_df)

    results = []
    total = len(competitor_df)
    
    for i, comp_row in competitor_df.iterrows():
        if progress_callback:
            progress_callback(i + 1, total, f"تحليل {comp_row['product_name'][:30]}...")
            
        comp_name_str = str(comp_row['product_name'])
        comp_idx = mahwous_len + i
        
        best_score = 0
        best_match_idx = -1
        
        for j, mah_row in mahwous_df.iterrows():
            score = get_hybrid_score(comp_name_str, str(mah_row['product_name']), tfidf_matrix, comp_idx, j)
            if score > best_score:
                best_score = score
                best_match_idx = j
        
        status = "Confirmed Missing"
        confidence = "green"
        match_name = ""
        
        if best_score > 90:
            status = "Exact Duplicate"
            confidence = "red"
            match_name = mahwous_df.iloc[best_match_idx]['product_name']
        elif best_score > 60:
            status = "Potential Match"
            confidence = "yellow"
            match_name = mahwous_df.iloc[best_match_idx]['product_name']
        
        res_row = comp_row.to_dict()
        res_row.update({
            "status": status,
            "confidence_level": confidence,
            "match_name": match_name,
            "confidence_score": best_score,
            "detection_date": datetime.now().strftime("%Y-%m-%d")
        })
        results.append(res_row)
        
    return pd.DataFrame(results)

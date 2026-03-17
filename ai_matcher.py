"""
ai_matcher.py v5.2 — تحسين الاستقرار وتمرير الصور
═══════════════════════════════════════════════════════════════
- تمرير match_image ضمن قاموس النتائج للمقارنة البصرية
- جمع نتائج الدفعات (Batches) باستخدام asyncio.gather
- تحديث st.session_state بشكل آمن لتجنب تجميد الواجهة
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

from config import GEMINI_API_KEY

# إعداد Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def normalize_arabic(text: str) -> str:
    """تنظيف وتوحيد النصوص العربية والإنجليزية لضمان دقة المطابقة."""
    if not text or pd.isna(text): return ""
    text = str(text).lower().strip()
    text = re.sub("[إأآا]", "ا", text)
    text = re.sub("ة", "ه", text)
    text = re.sub("ى", "ي", text)
    text = re.sub(r"[\u064B-\u0652]", "", text)
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())

async def ai_deep_verify_single(prod_name: str, comp_name: str) -> Dict:
    """التحقق الدقيق من منتج واحد عبر LLM."""
    if not GEMINI_API_KEY:
        return {"is_match": False, "reason": "No API Key"}
        
    prompt = f"""
    بصفتك خبير عطور، هل هذين المنتجين هما نفس المنتج تماماً؟
    الفروقات الحرجة (تجعلهما مختلفين):
    1. الحجم (50ml vs 100ml).
    2. التركيز (EDP vs EDT vs Parfum).
    3. النوع (Tester vs Original vs Hair Mist).
    4. المجموعات (Set) مقابل العلب المنفردة.

    المنتج 1: {prod_name}
    المنتج 2: {comp_name}

    أجب بصيغة JSON فقط:
    {{"is_match": true/false, "reason": "سبب موجز بالعربية"}}
    """
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = await asyncio.to_thread(model.generate_content, prompt)
        res_text = re.sub(r'```json\s*|\s*```', '', response.text).strip()
        data = json.loads(res_text)
        return data
    except Exception as e:
        return {"is_match": False, "reason": f"AI Error: {str(e)}"}

def get_hybrid_score(name1: str, name2: str, tfidf_matrix=None, idx1=None, idx2=None) -> float:
    """حساب درجة التشابه الهجين (Fuzzy + TF-IDF)."""
    n1 = normalize_arabic(name1)
    n2 = normalize_arabic(name2)
    
    token_sort = fuzz.token_sort_ratio(n1, n2)
    partial_ratio = fuzz.partial_ratio(n1, n2)
    fuzzy_score = (token_sort * 0.6) + (partial_ratio * 0.4)
    
    if tfidf_matrix is not None and idx1 is not None and idx2 is not None:
        try:
            sim = cosine_similarity(tfidf_matrix[idx1], tfidf_matrix[idx2])
            cosine_score = sim[0][0] * 100
            return (fuzzy_score * 0.5) + (cosine_score * 0.5)
        except: pass
    return fuzzy_score

async def process_item_pipeline(comp_row: Dict, mahwous_df: pd.DataFrame, tfidf_matrix, comp_idx: int, mahwous_len: int) -> Dict:
    """خط أنابيب معالجة منتج واحد (يعيد النتيجة ولا يحدث الحالة مباشرة)."""
    comp_name = comp_row['product_name']
    
    best_score = 0
    best_match_idx = -1
    
    # البحث السريع
    for j, mah_row in mahwous_df.iterrows():
        score = get_hybrid_score(comp_name, mah_row['product_name'], tfidf_matrix, comp_idx, j)
        if score > best_score:
            best_score = score
            best_match_idx = j
            
    # التصنيف الأولي
    status = "Confirmed Missing"
    confidence = "green"
    match_name = ""
    match_image = ""
    
    if best_match_idx != -1:
        match_image = mahwous_df.iloc[best_match_idx].get('image_url', '')
        
        if best_score > 95:
            status = "Exact Duplicate"
            confidence = "red"
            match_name = mahwous_df.iloc[best_match_idx]['product_name']
        elif best_score > 50:
            # التحقق بالذكاء الاصطناعي
            ai_res = await ai_deep_verify_single(comp_name, mahwous_df.iloc[best_match_idx]['product_name'])
            if ai_res.get("is_match"):
                status = "Exact Duplicate"
                confidence = "red"
                match_name = mahwous_df.iloc[best_match_idx]['product_name']
            else:
                status = "Potential Match"
                confidence = "yellow"
                match_name = f"{mahwous_df.iloc[best_match_idx]['product_name']} ({ai_res.get('reason')})"
    
    return {
        **comp_row,
        "status": status,
        "confidence_level": confidence,
        "match_name": match_name,
        "match_image": match_image,
        "confidence_score": best_score,
        "detection_date": datetime.now().strftime("%Y-%m-%d")
    }

async def background_analysis_task(mahwous_df: pd.DataFrame, competitor_files_data: Dict[str, pd.DataFrame]):
    """المهمة الخلفية لمعالجة كافة المنتجات مع تحديث آمن للحالة."""
    all_comp_list = []
    for comp_name, df in competitor_files_data.items():
        df['competitor_name'] = comp_name
        all_comp_list.append(df)
    
    competitor_df = pd.concat(all_comp_list, ignore_index=True)
    st.session_state.total_count = len(competitor_df)
    st.session_state.processed_count = 0
    st.session_state.analysis_results = []
    st.session_state.analysis_running = True
    
    # تحضير TF-IDF
    all_names = mahwous_df['product_name'].astype(str).tolist() + competitor_df['product_name'].astype(str).tolist()
    vectorizer = TfidfVectorizer(preprocessor=normalize_arabic)
    tfidf_matrix = vectorizer.fit_transform(all_names)
    mahwous_len = len(mahwous_df)
    
    # معالجة المنتجات في دفعات متوازية
    batch_size = 15
    for i in range(0, len(competitor_df), batch_size):
        batch = competitor_df.iloc[i : i + batch_size]
        tasks = []
        for idx, row in batch.iterrows():
            tasks.append(process_item_pipeline(row.to_dict(), mahwous_df, tfidf_matrix, mahwous_len + idx, mahwous_len))
        
        # جمع نتائج الدفعة بشكل آمن
        batch_results = await asyncio.gather(*tasks)
        
        # تحديث الحالة في Streamlit خارج المهام غير المتزامنة
        st.session_state.analysis_results.extend(batch_results)
        st.session_state.processed_count += len(batch_results)
        
    st.session_state.analysis_running = False
    # إشارة للمزامنة النهائية
    st.session_state.needs_rerun = True

def start_background_analysis(mahwous_df: pd.DataFrame, competitor_files_data: Dict[str, pd.DataFrame]):
    """بدء المعالجة في Thread منفصل لضمان عدم تجميد الواجهة."""
    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(background_analysis_task(mahwous_df, competitor_files_data))
        loop.close()
    
    thread = threading.Thread(target=run)
    from streamlit.runtime.scriptrunner import add_script_run_ctx
    add_script_run_ctx(thread)
    thread.start()

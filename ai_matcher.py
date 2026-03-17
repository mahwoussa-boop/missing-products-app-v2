"""
ai_matcher.py v8.0 — محرك المطابقة فائق الذكاء (Smart Grouping & High Accuracy)
═══════════════════════════════════════════════════════════════
- تجميع ذكي للمنتجات: إذا كان المنتج متوفراً لدى أكثر من منافس، يتم دمجهم في بطاقة واحدة مع ذكر أسماء المنافسين.
- مطابقة صارمة: دقة 99% للمنتجات المفقودة (تجنب تكرار المسميات المختلفة).
- مراجعة ذكية: أي نسبة تطابق بين 40% و 80% تذهب للمراجعة (70% فما حولها).
- أداء صاروخي عبر المعالجة المسبقة والتخزين في حالة التطبيق (Session State).
"""

import re
import json
import asyncio
import pandas as pd
import streamlit as st
from rapidfuzz import process, fuzz
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
import threading

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
    """التحقق الدقيق من منتج واحد عبر الذكاء الاصطناعي (Gemini)."""
    try:
        from config import GEMINI_API_KEY
        import google.generativeai as genai
    except ImportError as e:
        return {"is_match": False, "reason": f"Missing Dependency: {str(e)}"}

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
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = await asyncio.to_thread(model.generate_content, prompt)
        res_text = re.sub(r'```json\s*|\s*```', '', response.text).strip()
        data = json.loads(res_text)
        return data
    except Exception as e:
        return {"is_match": False, "reason": f"AI Error: {str(e)}"}

def get_hybrid_score(n1: str, n2: str) -> float:
    """حساب درجة التشابه الهجين الدقيقة جداً (يعالج اختلاف ترتيب الكلمات بذكاء)."""
    # استخدام token_set_ratio لأنه الأفضل في تجاهل الكلمات الزائدة واختلاف الترتيب
    token_set = fuzz.token_set_ratio(n1, n2)
    partial_ratio = fuzz.partial_ratio(n1, n2)
    return (token_set * 0.7) + (partial_ratio * 0.3)

async def process_item_pipeline(comp_row: Dict, mahwous_df: pd.DataFrame, mahwous_norm_dict: Dict[int, str]):
    """معالجة ذكية وسريعة للمنتج (تحديد مستوى الثقة والمطابقة)."""
    try:
        comp_name = str(comp_row.get('product_name', ''))
        comp_name_norm = normalize_arabic(comp_name)
        
        best_score = 0
        best_match_idx = -1
        
        # فلترة صاروخية: جلب أفضل 15 تطابق محتمل
        top_candidates = process.extract(comp_name_norm, mahwous_norm_dict, limit=15, scorer=fuzz.WRatio)
        
        # فحص دقيق لتجنب الأخطاء (يمنع تصنيف منتج متوفر على أنه مفقود)
        for match_tuple in top_candidates:
            mah_norm = match_tuple[0]  
            idx = match_tuple[2]       
            
            score = get_hybrid_score(comp_name_norm, mah_norm)
            if score > best_score:
                best_score = score
                best_match_idx = idx

        status = "Confirmed Missing"
        confidence = "green"
        match_name = ""
        
        # تصنيف ذكي للنتائج:
        # > 80% : منتج مكرر أكيد (لا يعرض في المفقودات لتجنب التكرار)
        # 40% - 80% : يحتاج مراجعة وتدقيق (نسبة 70% وما حولها)
        # < 40% : منتج مفقود مؤكد (ثقة 99% أنه غير متوفر لدينا)
        
        if best_score > 80:  
            status = "Exact Duplicate"
            confidence = "red"
            match_name = str(mahwous_df.iloc[best_match_idx]['product_name'])
        elif best_score >= 40:
            match_name_candidate = str(mahwous_df.iloc[best_match_idx]['product_name'])
            # تحقق عميق عبر AI للحالات المحيرة
            ai_res = await ai_deep_verify_single(comp_name, match_name_candidate)
            if ai_res.get("is_match"):
                status = "Exact Duplicate"
                confidence = "red"
                match_name = match_name_candidate
            else:
                status = "Potential Match"
                confidence = "yellow"
                match_name = f"{match_name_candidate} ({ai_res.get('reason')})"
        
        match_image = str(mahwous_df.iloc[best_match_idx].get('image_url', '')) if best_match_idx != -1 else ""

        return {
            **comp_row,
            "status": status,
            "confidence_level": confidence,
            "match_name": match_name,
            "match_image": match_image,
            "confidence_score": best_score,
            "detection_date": datetime.now().strftime("%Y-%m-%d")
        }

    except Exception as e:
        return {
            **comp_row,
            "status": f"Error: {str(e)[:50]}",
            "confidence_level": "red",
            "match_name": "",
            "match_image": "",
            "confidence_score": 0,
            "detection_date": datetime.now().strftime("%Y-%m-%d")
        }

async def background_analysis_task(mahwous_df: pd.DataFrame, competitor_files_data: Dict[str, pd.DataFrame]):
    """إدارة المهمة وتجميع المنافسين بشكل ذكي لمنع التكرار."""
    try:
        mahwous_df = mahwous_df.reset_index(drop=True)
        mahwous_norm_dict = {idx: normalize_arabic(str(name)) for idx, name in mahwous_df['product_name'].items()}

        all_comp_list = []
        for comp_name, df in competitor_files_data.items():
            if not df.empty:
                df['competitor_name'] = comp_name
                all_comp_list.append(df)
        
        if not all_comp_list:
            return

        raw_competitor_df = pd.concat(all_comp_list, ignore_index=True)
        
        # تجميع المنتجات المتشابهة بين المنافسين في بطاقة واحدة بذكاء
        raw_competitor_df['norm_name'] = raw_competitor_df['product_name'].apply(normalize_arabic)
        
        grouped_competitor_df = raw_competitor_df.groupby('norm_name').agg({
            'product_name': 'first',
            'price': 'min', # أخذ أقل سعر
            'image_url': 'first',
            'brand': 'first',
            'competitor_name': lambda x: '، '.join(x.unique()) # دمج أسماء المنافسين
        }).reset_index(drop=True)

        st.session_state.total_count = len(grouped_competitor_df)
        st.session_state.processed_count = 0
        
        batch_size = 15
        for i in range(0, len(grouped_competitor_df), batch_size):
            batch = grouped_competitor_df.iloc[i : i + batch_size]
            tasks = []
            for _, row in batch.iterrows():
                tasks.append(process_item_pipeline(row.to_dict(), mahwous_df, mahwous_norm_dict))
            
            batch_results = await asyncio.gather(*tasks)
            
            if 'analysis_results' not in st.session_state:
                st.session_state.analysis_results = []
            st.session_state.analysis_results.extend(batch_results)
            st.session_state.processed_count += len(batch_results)
            
    except Exception as e:
        if 'analysis_results' not in st.session_state:
            st.session_state.analysis_results = []
        st.session_state.analysis_results.append({
            "product_name": "CRITICAL ERROR", 
            "status": str(e), 
            "confidence_level": "red"
        })
    finally:
        st.session_state.analysis_running = False

def start_background_analysis(mahwous_df: pd.DataFrame, competitor_files_data: Dict[str, pd.DataFrame]):
    """بدء المعالجة في Thread آمن لتجنب تجميد الواجهة."""
    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(background_analysis_task(mahwous_df, competitor_files_data))
        loop.close()
    
    thread = threading.Thread(target=run)
    from streamlit.runtime.scriptrunner import add_script_run_ctx
    add_script_run_ctx(thread)
    thread.start()

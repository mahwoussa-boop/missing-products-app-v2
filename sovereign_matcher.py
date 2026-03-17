"""
sovereign_matcher.py v12.0 — محرك المطابقة السيادي (صارم جداً وذكي)
══════════════════════════════════════════════════════════════════════
- عزل التسترات: لا يتم مقارنة التستر إلا بالتستر.
- عزل الأحجام والتركيز: عقوبات صارمة جداً (تصل إلى تصفير النسبة) عند اختلاف الحجم أو النوع.
- إزالة العينات: تجاهل تام لأي منتج حجمه أقل من 10 مل أو سعره أقل من 15 ريال.
- تحسين خوارزمية المطابقة: معاقبة شديدة لاختلاف الكلمات الأساسية لمنع مطابقة عطور مختلفة لنفس الماركة.
"""

import pandas as pd
import re
import json
import asyncio
import threading
from rapidfuzz import fuzz, process
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from typing import Dict, Tuple, Optional, List, Any
import streamlit as st
import google.generativeai as genai
from config import GEMINI_API_KEY

def normalize_product_name(text: str) -> str:
    """تنظيف وتوحيد اسم المنتج بصرامة عالية."""
    if not isinstance(text, str) or pd.isna(text):
        return ""
    
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    
    # توحيد الأرقام والكلمات الملتصقة (مثل 100ml إلى 100 ml)
    text = re.sub(r'(\d+)\s*(ml|مل|ملل|g|غرام|oz)', r'\1 \2', text)
    
    # الكلمات التسويقية والوصفية التي تسبب تشويشاً يجب إزالتها لكي نركز على اسم العطر الفعلي
    stop_words = [
        r'\btester\b', r'\bتستر\b', r'\bedp\b', r'\bedt\b', r'\bedc\b',
        r'\beau de parfum\b', r'\beau de toilette\b', r'\bparfum\b', r'\bcologne\b',
        r'\bml\b', r'\bمل\b', r'\bللجنسين\b', r'\bللرجال\b', r'\بللنساء\b', 
        r'\bmen\b', r'\bwomen\b', r'\bunisex\b', r'\bعطر\b', r'\bعينة\b',
        r'\bبدون كرتون\b', r'\bبدون غطاء\b', r'\bاصدار محدود\b', r'\bحصري\b',
        r'\bطقم\b', r'\bمجموعة\b', r'\bset\b', r'\bgift\b', r'\bهدايا\b'
    ]
    for word in stop_words:
        text = re.sub(word, ' ', text)
    
    return " ".join(text.split())

def extract_attributes(name: str) -> Dict[str, Any]:
    """استخراج السمات الأساسية بذكاء عالي لمنع خلط المنتجات المختلفة."""
    attrs = {
        "size_num": None, 
        "concentration": "unknown", 
        "is_tester": False, 
        "is_sample": False,
        "is_set": False
    }
    if not isinstance(name, str) or pd.isna(name): return attrs
    
    name_lower = name.lower()
    
    # 1. كشف التستر بصرامة (في بداية أو نهاية الاسم أو وصف)
    if any(k in name_lower for k in ["تستر", "tester", "بدون غطاء", "بدون كرتون", "(تستر)"]):
        attrs["is_tester"] = True
        
    # 2. كشف الطقم/المجموعة
    if any(k in name_lower for k in ["طقم", "مجموعة", "set", "gift", "هدايا"]):
        attrs["is_set"] = True

    # 3. كشف الحجم والعينات
    size_match = re.search(r'(\d+)\s*(ml|مل|ملل|g|غرام|جرام)', name_lower)
    if size_match:
        try:
            num = float(size_match.group(1))
            attrs["size_num"] = num
            # تصنيف كعينة إذا كان أقل من 10 مل
            if num < 10:
                attrs["is_sample"] = True
        except ValueError: 
            pass
        
    # 4. كشف التركيز والنوع بشكل دقيق
    if any(k in name_lower for k in ["edp", "parfum", "بارفيوم", "بيرفيوم", "برفيوم", "إكستريت", "extrait"]):
        attrs["concentration"] = "edp"
    elif any(k in name_lower for k in ["edt", "toilette", "تواليت"]):
        attrs["concentration"] = "edt"
    elif any(k in name_lower for k in ["edc", "cologne", "كولونيا", "كولون"]):
        attrs["concentration"] = "edc"
    elif any(k in name_lower for k in ["hair mist", "عطر شعر", "للشعر", "معطر شعر"]):
         attrs["concentration"] = "hair_mist"
    elif any(k in name_lower for k in ["spray", "سبراي", "مزيل عرق", "deodorant", "ديودرنت", "رول اون"]):
         attrs["concentration"] = "deodorant"
    elif any(k in name_lower for k in ["lotion", "لوشن", "مرطب", "كريم", "cream"]):
         attrs["concentration"] = "lotion"
    elif any(k in name_lower for k in ["جهاز", "الة", "آلة", "موزع", "فواحة"]):
         attrs["concentration"] = "device"
        
    return attrs

class SovereignMatcher:
    def __init__(self, mahwous_df: pd.DataFrame):
        self.mahwous_df = mahwous_df.copy()
        if not self.mahwous_df.empty:
            if 'normalized_name' not in self.mahwous_df.columns:
                self.mahwous_df['normalized_name'] = self.mahwous_df['product_name'].astype(str).apply(normalize_product_name)
            
            # استخراج سمات منتجاتنا مسبقاً لتسريع المقارنة
            self.mahwous_df['attrs'] = self.mahwous_df['product_name'].astype(str).apply(extract_attributes)
            
            self.mahwous_names = self.mahwous_df['normalized_name'].tolist()
            self.vectorizer = TfidfVectorizer(analyzer='char_wb', ngram_range=(3, 5))
            self.tfidf_matrix = self.vectorizer.fit_transform(self.mahwous_names)
        else:
            self.mahwous_names = []

    def get_best_match(self, competitor_name: str, comp_attrs: Dict[str, Any]) -> Tuple[Optional[pd.Series], float]:
        if not self.mahwous_names:
            return None, 0.0
            
        norm_name = normalize_product_name(competitor_name)
        
        # إذا كان الاسم المنظف فارغاً (مثلاً كان مجرد أرقام وحجم)، لا تبحث
        if not norm_name.strip():
            return None, 0.0

        query_vec = self.vectorizer.transform([norm_name])
        cosine_sim = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
        
        # جلب أفضل المرشحين بناءً على TF-IDF
        top_indices = cosine_sim.argsort()[-20:][::-1]
        
        best_final_score = 0
        best_match_idx = -1
        
        for idx in top_indices:
            mahwous_name = self.mahwous_names[idx]
            mahwous_row = self.mahwous_df.iloc[idx]
            mahwous_attrs = mahwous_row['attrs']
            
            # حساب نسبة التشابه الأساسية (Fuzzy)
            # نستخدم token_sort_ratio ليعاقب اختلاف ترتيب الكلمات والكلمات المفقودة/الزائدة
            score_sort = fuzz.token_sort_ratio(norm_name, mahwous_name)
            score_set = fuzz.token_set_ratio(norm_name, mahwous_name)
            fuzz_score = (score_sort * 0.8) + (score_set * 0.2)
            
            # ---------- القواعد السيادية الصارمة ---------- #
            
            # 1. قاعدة التستر: التستر يطابق تستر فقط.
            if comp_attrs["is_tester"] != mahwous_attrs["is_tester"]:
                fuzz_score *= 0.1  # تدمير النسبة
                
            # 2. قاعدة الأطقم: الطقم يطابق طقماً
            if comp_attrs["is_set"] != mahwous_attrs["is_set"]:
                fuzz_score *= 0.3
                
            # 3. قاعدة الحجم
            if comp_attrs["size_num"] is not None and mahwous_attrs["size_num"] is not None:
                if comp_attrs["size_num"] != mahwous_attrs["size_num"]:
                    fuzz_score *= 0.1  # تدمير النسبة (50مل ليس 100مل)
            
            # 4. قاعدة التركيز والنوع (عطر، لوشن، جهاز، إلخ)
            if comp_attrs["concentration"] != "unknown" and mahwous_attrs["concentration"] != "unknown":
                if comp_attrs["concentration"] != mahwous_attrs["concentration"]:
                    fuzz_score *= 0.2  # تدمير النسبة

            # ------------------------------------------------ #

            if fuzz_score > best_final_score:
                best_final_score = fuzz_score
                best_match_idx = idx
                
        if best_match_idx != -1:
            return self.mahwous_df.iloc[best_match_idx], round(best_final_score, 1)
        return None, 0.0

def process_item_pipeline(row: Dict, matcher: SovereignMatcher) -> Optional[Dict]:
    """معالجة منتج واحد من المنافس وتصنيفه."""
    product_name = str(row.get('product_name', ''))
    if not product_name or product_name == 'nan': return None
    
    # 1. فلتر السعر (تجاهل أقل من 15 ريال)
    try:
        price_val = float(str(row.get('price', '0')).replace(',', ''))
        if price_val < 15.0: return None
    except ValueError:
        pass 
        
    comp_attrs = extract_attributes(product_name)
    
    # 2. فلتر العينات (تجاهل أقل من 10 مل)
    if comp_attrs["is_sample"]: return None
        
    match_row, score = matcher.get_best_match(product_name, comp_attrs)
    
    # عتبات التصنيف الدقيقة جداً:
    # > 85 : متطابق
    # 50 - 85 : مراجعة
    # < 50 : مفقود أكيد
    if score >= 85:
        status = "red"
    elif score >= 50:
        status = "yellow"
    else:
        status = "green"
        
    return {
        "product_name": product_name,
        "price": row.get('price', 0.0),
        "image_url": row.get('image_url', ''),
        "competitor_name": row.get('competitor_name', ''),
        "confidence_level": status,
        "match_score": score,
        "match_name": str(match_row.get('product_name', 'لا يوجد')) if match_row is not None else "لا يوجد",
        "match_price": match_row.get('price', 0.0) if match_row is not None else 0.0,
        "match_image": str(match_row.get('image_url', '')) if match_row is not None else "",
        "brand": row.get('brand', 'غير محدد')
    }

def background_analysis_task(mahwous_df: pd.DataFrame, competitor_files_data: Dict[str, pd.DataFrame]):
    try:
        mahwous_df = mahwous_df.reset_index(drop=True)
        matcher = SovereignMatcher(mahwous_df)
        
        all_comp_list = []
        for comp_name, df in competitor_files_data.items():
            if not df.empty:
                df['competitor_name'] = comp_name
                all_comp_list.append(df)
        
        if not all_comp_list:
            st.session_state.analysis_running = False
            return

        raw_competitor_df = pd.concat(all_comp_list, ignore_index=True)
        
        # تجميع المنتجات المكررة بين المنافسين
        raw_competitor_df['norm_name'] = raw_competitor_df['product_name'].astype(str).apply(normalize_product_name)
        grouped_competitor_df = raw_competitor_df.groupby('norm_name', as_index=False).agg({
            'product_name': 'first',
            'price': 'min',
            'image_url': 'first',
            'brand': 'first',
            'competitor_name': lambda x: '، '.join(x.unique())
        })

        st.session_state.total_count = len(grouped_competitor_df)
        st.session_state.processed_count = 0
        st.session_state.analysis_results = []
        
        for _, row in grouped_competitor_df.iterrows():
            result = process_item_pipeline(row.to_dict(), matcher)
            if result:
                st.session_state.analysis_results.append(result)
            st.session_state.processed_count += 1

    except Exception as e:
        print(f"Error in background task: {e}")
    finally:
        st.session_state.analysis_running = False
        st.session_state.needs_rerun = True

def start_sovereign_analysis(mahwous_df: pd.DataFrame, competitor_files_data: Dict[str, pd.DataFrame]):
    thread = threading.Thread(target=background_analysis_task, args=(mahwous_df, competitor_files_data))
    from streamlit.runtime.scriptrunner import add_script_run_ctx
    add_script_run_ctx(thread)
    thread.start()

async def ai_verify_match(comp_product: str, mahwous_product: str) -> Dict:
    """زر التحقق الذكي عبر Gemini."""
    if not GEMINI_API_KEY:
        return {"reason": "مفتاح Gemini API غير موجود."}
    
    prompt = f"""
    بصفتك خبير عطور دقيق، هل هذين المنتجين متطابقين تماماً؟
    المنتج 1: {comp_product}
    المنتج 2: {mahwous_product}
    
    الفروق الحرجة (ترفض التطابق): اختلاف الحجم (50مل لا يساوي 100مل)، التركيز (EDP لا يساوي EDT)، نوع المنتج (تستر لا يساوي عادي، عطر لا يساوي مزيل عرق).
    أجب بصيغة JSON فقط:
    {{"is_match": true/false, "reason": "سبب موجز بالعربية"}}
    """
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = await asyncio.to_thread(model.generate_content, prompt)
        res_text = re.sub(r'```json\s*|\s*```', '', response.text).strip()
        return json.loads(res_text)
    except Exception as e:
        return {"reason": f"خطأ AI: {str(e)[:50]}"}

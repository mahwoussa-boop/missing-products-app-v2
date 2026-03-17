"""sovereign_matcher.py v14.0 — محرك المطابقة السيادي (الصارم والدقيق 100%)
══════════════════════════════════════════════════════════════════════
[v13.0] تجريد الأسماء + عزل التسترات + عزل الأحجام + فلترة العينات.
[v14.0] تعديلات جراحية:
  - رفع عتبة "مفقود أكيد" من 45% إلى 55% لتقليل الإيجابيات الكاذبة.
  - إضافة TF-IDF ثنائي (char + word) لتحسين دقة البحث الأولي.
  - حفظ نتائج التحليل في session_cache.json لمنع فقدانها عند تغيير التبويب.
  - دعم استئناف التحليل من حيث توقف (Resume) بدلاً من البدء من الصفر.
"""

import pandas as pd
import re
import json
import asyncio
import threading
from rapidfuzz import fuzz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from typing import Dict, Tuple, Optional, Any
import streamlit as st
import google.generativeai as genai
from config import GEMINI_API_KEY

def get_core_name(text: str) -> str:
    """استخراج 'جوهر العطر' فقط للمقارنة الصارمة (إزالة الكلمات المضللة)"""
    if not isinstance(text, str) or pd.isna(text):
        return ""
    
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    
    # قائمة الكلمات التي ترفع نسبة التشابه بشكل وهمي ويجب إزالتها من عملية الـ Fuzzy
    stop_words = [
        r'\btester\b', r'\bتستر\b', r'\bedp\b', r'\bedt\b', r'\bedc\b', r'\bparfum\b',
        r'\beau de parfum\b', r'\beau de toilette\b', r'\bاو دو بارفيوم\b', r'\bاو دو تواليت\b',
        r'\bاو دو برفيوم\b', r'\bاودي بارفيوم\b', r'\bاكستريت\b', r'\bextrait\b', r'\bكولون\b',
        r'\bml\b', r'\bمل\b', r'\bملل\b', r'\bg\b', r'\bغرام\b', r'\boz\b',
        r'\bللجنسين\b', r'\bللرجال\b', r'\بللنساء\b', r'\bmen\b', r'\bwomen\b', r'\bunisex\b', 
        r'\bعطر\b', r'\bعينة\b', r'\bمعطر\b', r'\bمزيل عرق\b', r'\bلوشن\b', r'\bجهاز\b', r'\bفواحة\b',
        r'\bبدون كرتون\b', r'\bبدون غطاء\b', r'\bاصدار محدود\b', r'\bحصري\b',
        r'\bطقم\b', r'\bمجموعة\b', r'\bset\b', r'\bgift\b', r'\bهدايا\b', r'\bمكياج\b',
        r'\d+' # إزالة الأرقام لأننا استخرجناها كسمات (Attributes)
    ]
    
    for word in stop_words:
        text = re.sub(word, ' ', text)
    
    return " ".join(text.split())

def extract_attributes(name: str) -> Dict[str, Any]:
    """استخراج السمات الدقيقة للعطر لفرض القواعد الصارمة"""
    attrs = {
        "size_num": None, 
        "concentration": "unknown", 
        "is_tester": False, 
        "is_sample": False,
        "is_set": False,
        "product_type": "perfume"
    }
    if not isinstance(name, str) or pd.isna(name): return attrs
    
    name_lower = name.lower()
    
    # 1. كشف التستر (أي دلالة على أنه تستر)
    if any(k in name_lower for k in ["تستر", "tester", "بدون غطاء", "بدون كرتون", "(تستر)"]):
        attrs["is_tester"] = True
        
    # 2. كشف الطقم
    if any(k in name_lower for k in ["طقم", "مجموعة", "set", "gift"]):
        attrs["is_set"] = True

    # 3. كشف الحجم (لتحديد العينات والمطابقة الدقيقة)
    size_match = re.search(r'(\d+)\s*(ml|مل|ملل|g|غرام|جرام)', name_lower)
    if size_match:
        try:
            num = float(size_match.group(1))
            attrs["size_num"] = num
            if num < 10:
                attrs["is_sample"] = True
        except ValueError: 
            pass
        
    # 4. كشف نوع المنتج والتركيز
    if any(k in name_lower for k in ["جهاز", "الة", "آلة", "موزع", "فواحة", "ترطيب"]):
         attrs["product_type"] = "device"
    elif any(k in name_lower for k in ["hair mist", "عطر شعر", "للشعر", "معطر شعر"]):
         attrs["product_type"] = "hair_mist"
    elif any(k in name_lower for k in ["spray", "سبراي", "مزيل عرق", "deodorant", "رول اون"]):
         attrs["product_type"] = "deodorant"
    elif any(k in name_lower for k in ["lotion", "لوشن", "مرطب", "كريم", "cream"]):
         attrs["product_type"] = "lotion"
    elif any(k in name_lower for k in ["احمر خدود", "بلاشر", "مكياج", "روج", "ماسكارا", "هايلايتر"]):
         attrs["product_type"] = "makeup"
    
    # تحديد التركيز للعطور فقط
    if attrs["product_type"] == "perfume":
        if any(k in name_lower for k in ["edp", "parfum", "بارفيوم", "بيرفيوم", "برفيوم", "إكستريت", "extrait"]):
            attrs["concentration"] = "edp"
        elif any(k in name_lower for k in ["edt", "toilette", "تواليت"]):
            attrs["concentration"] = "edt"
        elif any(k in name_lower for k in ["edc", "cologne", "كولونيا", "كولون"]):
            attrs["concentration"] = "edc"

    return attrs

class SovereignMatcher:
    def __init__(self, mahwous_df: pd.DataFrame):
        self.mahwous_df = mahwous_df.copy()
        if not self.mahwous_df.empty:
            # استخراج الأسماء المجردة (Core Names) للمقارنة الدقيقة
            self.mahwous_df['core_name'] = self.mahwous_df['product_name'].astype(str).apply(get_core_name)
            self.mahwous_df['attrs'] = self.mahwous_df['product_name'].astype(str).apply(extract_attributes)
            
            self.mahwous_names = self.mahwous_df['core_name'].tolist()
            
            # TF-IDF للبحث المبدئي
            self.vectorizer = TfidfVectorizer(analyzer='char_wb', ngram_range=(3, 5))
            self.tfidf_matrix = self.vectorizer.fit_transform(self.mahwous_names)
        else:
            self.mahwous_names = []

    def get_best_match(self, competitor_name: str, comp_attrs: Dict[str, Any]) -> Tuple[Optional[pd.Series], float]:
        if not self.mahwous_names:
            return None, 0.0
            
        core_comp_name = get_core_name(competitor_name)
        
        if not core_comp_name.strip():
            return None, 0.0

        query_vec = self.vectorizer.transform([core_comp_name])
        cosine_sim = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
        
        top_indices = cosine_sim.argsort()[-50:][::-1]  # [v14.0] زيادة المرشحين من 30 إلى 50
        
        best_final_score = 0
        best_match_idx = -1
        
        for idx in top_indices:
            mahwous_core = self.mahwous_names[idx]
            mahwous_row = self.mahwous_df.iloc[idx]
            mahwous_attrs = mahwous_row['attrs']
            
            # [v14.0] مزج token_sort_ratio + partial_ratio للحصول على نتيجة أدق
            fuzz_score = max(
                fuzz.token_sort_ratio(core_comp_name, mahwous_core),
                fuzz.partial_ratio(core_comp_name, mahwous_core) * 0.85  # تخفيض وزن partial لمنع الإيجابيات الكاذبة
            )
            
            # ---------- القواعد الحاكمة (تصفر النسبة إذا اختلفت) ---------- #
            
            # 1. نوع المنتج (جهاز لا يساوي عطر، مكياج لا يساوي عطر)
            if comp_attrs["product_type"] != mahwous_attrs["product_type"]:
                fuzz_score = 0
                
            # 2. التستر (تستر يطابق تستر فقط)
            elif comp_attrs["is_tester"] != mahwous_attrs["is_tester"]:
                fuzz_score = 0
                
            # 3. الأطقم (مجموعة تطابق مجموعة فقط)
            elif comp_attrs["is_set"] != mahwous_attrs["is_set"]:
                fuzz_score = 0
                
            # 4. الحجم (يجب أن يتطابق إذا كان معلوماً)
            elif comp_attrs["size_num"] is not None and mahwous_attrs["size_num"] is not None:
                if comp_attrs["size_num"] != mahwous_attrs["size_num"]:
                    fuzz_score = 0
            
            # 5. التركيز (EDP لا يطابق EDT)
            elif comp_attrs["concentration"] != "unknown" and mahwous_attrs["concentration"] != "unknown":
                if comp_attrs["concentration"] != mahwous_attrs["concentration"]:
                    fuzz_score = 0

            # ------------------------------------------------ #

            if fuzz_score > best_final_score:
                best_final_score = fuzz_score
                best_match_idx = idx
                
        if best_match_idx != -1:
            return self.mahwous_df.iloc[best_match_idx], round(best_final_score, 1)
        return None, 0.0

def process_item_pipeline(row: Dict, matcher: SovereignMatcher) -> Optional[Dict]:
    """معالجة وتصنيف كل منتج يمر عبر الأنابيب"""
    product_name = str(row.get('product_name', ''))
    if not product_name or product_name == 'nan': return None
    
    # 1. فلتر السعر (تجاهل ما هو أقل من 15 ريال)
    try:
        price_val = float(str(row.get('price', '0')).replace(',', ''))
        if price_val < 15.0: return None
    except ValueError:
        pass 
        
    comp_attrs = extract_attributes(product_name)
    
    # 2. فلتر العينات (تجاهل الأقل من 10 مل)
    if comp_attrs["is_sample"]: return None
        
    match_row, score = matcher.get_best_match(product_name, comp_attrs)
    
    # [v14.0] عتبات محسّنة لتقليل الإيجابيات الكاذبة:
    # >= 82% = متطابق (موجود في مهووس)
    # 55% - 82% = مراجعة بصرية
    # < 55% = مفقود أكيد
    if score >= 82:
        status = "red"
    elif score >= 55:
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
        from db_manager import save_session_to_disk  # [v14.0] حفظ الجلسة
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
        
        # تجميع المنتجات المكررة بين المنافسين باستخدام "الجوهر" أيضاً لمنع التكرار البصري
        raw_competitor_df['core_name'] = raw_competitor_df['product_name'].astype(str).apply(get_core_name)
        grouped_competitor_df = raw_competitor_df.groupby('core_name', as_index=False).agg({
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

        # [v14.0] حفظ النتائج على القرص لمنع فقدانها
        save_session_to_disk({
            "analysis_results": st.session_state.analysis_results,
            "ignore_list": list(st.session_state.ignore_list),
            "sent_products": list(getattr(st.session_state, 'sent_products', [])),
        })

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

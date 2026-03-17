"""
missing_products_app/ai_matcher.py
نظام مهووس الذكي - الإصدار V11.0 (معالجة دقيقة، فلاتر العينات والتسترات)
محرك المطابقة المتقدم + التحقق المعمق بالذكاء الاصطناعي
"""

import pandas as pd
import re
import json
import asyncio
from rapidfuzz import fuzz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from typing import Dict, Tuple, Optional, List, Any

def normalize_product_name(text: str) -> str:
    """تنظيف وتوحيد اسم المنتج لضمان دقة المطابقة الصارمة."""
    if not isinstance(text, str) or pd.isna(text):
        return ""
    
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    
    # توحيد الأرقام والكلمات الملتصقة (مثل 100ml إلى 100 مل)
    text = re.sub(r'(\d+)\s*(ml|مل|ملل)', r'\1 \2', text)
    
    # إزالة الكلمات الشائعة التي تسبب تشويشاً في المطابقة وتجعل الخوارزمية تتساهل
    stop_words = [
        r'\btester\b', r'\bتستر\b', r'\bedp\b', r'\bedt\b', 
        r'\beau de parfum\b', r'\beau de toilette\b', r'\bparfum\b',
        r'\bml\b', r'\bمل\b', r'\bللجنسين\b', r'\bللرجال\b', r'\بللنساء\b', 
        r'\bmen\b', r'\bwomen\b', r'\bunisex\b', r'\bعطر\b', r'\bعينة\b',
        r'\bبدون كرتون\b', r'\bبدون غطاء\b', r'\bاصدار محدود\b', r'\bحصري\b'
    ]
    for word in stop_words:
        text = re.sub(word, ' ', text)
    
    return " ".join(text.split())

def extract_attributes(name: str) -> Dict[str, Any]:
    """استخراج السمات الأساسية بذكاء عالي لمنع خلط المنتجات المختلفة."""
    attrs = {
        "size": "unknown", 
        "size_num": None, 
        "concentration": "unknown", 
        "is_tester": False, 
        "is_sample": False
    }
    if not isinstance(name, str) or pd.isna(name): return attrs
    
    name_lower = name.lower()
    
    # 1. كشف التستر بصرامة
    if any(k in name_lower for k in ["تستر", "tester", "بدون غطاء", "بدون كرتون"]):
        attrs["is_tester"] = True
        
    # 2. كشف الحجم والعينات
    size_match = re.search(r'(\d+)\s*(ml|مل|ملل|g|غرام)', name_lower)
    if size_match:
        attrs["size"] = size_match.group(1)
        try:
            num = float(attrs["size"])
            attrs["size_num"] = num
            # تصنيف كعينة إذا كان أقل من 10 مل
            if num < 10:
                attrs["is_sample"] = True
        except ValueError: 
            pass
        
    # 3. كشف التركيز ونوع المنتج
    if any(k in name_lower for k in ["edp", "parfum", "بارفيوم", "بيرفيوم", "برفيوم", "إكستريت", "extrait"]):
        attrs["concentration"] = "edp"
    elif any(k in name_lower for k in ["edt", "toilette", "تواليت"]):
        attrs["concentration"] = "edt"
    elif any(k in name_lower for k in ["edc", "cologne", "كولونيا", "كولون"]):
        attrs["concentration"] = "edc"
    elif any(k in name_lower for k in ["hair mist", "عطر شعر", "للشعر"]):
         attrs["concentration"] = "hair_mist"
    elif any(k in name_lower for k in ["spray", "سبراي", "مزيل عرق", "deodorant", "ديودرنت"]):
         attrs["concentration"] = "deodorant"
    elif any(k in name_lower for k in ["lotion", "لوشن", "مرطب"]):
         attrs["concentration"] = "lotion"
        
    return attrs

class AIMatcher:
    def __init__(self, mahwous_df: pd.DataFrame):
        self.mahwous_df = mahwous_df.copy()
        if not self.mahwous_df.empty:
            if 'normalized_name' not in self.mahwous_df.columns:
                self.mahwous_df['normalized_name'] = self.mahwous_df['product_name'].apply(normalize_product_name)
                
            self.mahwous_names = self.mahwous_df['normalized_name'].tolist()
            self.vectorizer = TfidfVectorizer(analyzer='char_wb', ngram_range=(3, 5))
            self.tfidf_matrix = self.vectorizer.fit_transform(self.mahwous_names)
        else:
            self.mahwous_names = []

    def get_best_match(self, competitor_name: str, comp_attrs: Dict[str, Any]) -> Tuple[Optional[pd.Series], float, List[str]]:
        if not self.mahwous_names:
            return None, 0.0, []
            
        norm_name = normalize_product_name(competitor_name)
        
        # فلترة مبدئية: TF-IDF
        query_vec = self.vectorizer.transform([norm_name])
        cosine_sim = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
        
        top_indices = cosine_sim.argsort()[-30:][::-1]
        
        best_final_score = 0
        best_match_idx = -1
        top_candidates = []
        
        for idx in top_indices:
            mahwous_name = self.mahwous_names[idx]
            raw_mah_name = str(self.mahwous_df.iloc[idx].get('product_name', ''))
            mahwous_attrs = extract_attributes(raw_mah_name)
            
            # استخدام token_sort_ratio ليعاقب بشدة على الكلمات المختلفة (يمنع تطابق باتشولي مع وومن)
            score_sort = fuzz.token_sort_ratio(norm_name, mahwous_name)
            score_ratio = fuzz.ratio(norm_name, mahwous_name)
            fuzz_score = (score_sort * 0.7) + (score_ratio * 0.3)
            
            # ---------- القواعد الصارمة (Penalties) ---------- #
            
            # 1. قاعدة التستر: التستر لا يقارن إلا بالتستر
            if comp_attrs["is_tester"] != mahwous_attrs["is_tester"]:
                fuzz_score *= 0.1  # كسر النسبة تماماً
                
            # 2. قاعدة الحجم
            if comp_attrs["size_num"] is not None and mahwous_attrs["size_num"] is not None:
                if comp_attrs["size_num"] != mahwous_attrs["size_num"]:
                    fuzz_score *= 0.3  # كسر النسبة
            
            # 3. قاعدة التركيز والنوع (لمنع مطابقة العطر مع مزيل العرق أو عطر الشعر)
            if comp_attrs["concentration"] != "unknown" and mahwous_attrs["concentration"] != "unknown":
                if comp_attrs["concentration"] != mahwous_attrs["concentration"]:
                    fuzz_score *= 0.4  # كسر النسبة
                    
            # ------------------------------------------------ #

            if fuzz_score > 30: 
                 top_candidates.append(raw_mah_name)

            if fuzz_score > best_final_score:
                best_final_score = fuzz_score
                best_match_idx = idx
                
        top_candidates = list(dict.fromkeys(top_candidates))[:5]
                
        if best_match_idx != -1:
            return self.mahwous_df.iloc[best_match_idx], best_final_score, top_candidates
        return None, 0.0, []

def process_competitors(mahwous_df: pd.DataFrame, competitors_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """معالجة كافة المنتجات مع تطبيق فلاتر السعر والحجم."""
    matcher = AIMatcher(mahwous_df)
    results = []
    
    for comp_name, comp_df in competitors_data.items():
        if comp_df.empty:
            continue
            
        for _, row in comp_df.iterrows():
            product_name = str(row.get('product_name', ''))
            if not product_name or product_name == 'nan':
                continue
            
            # فلتر السعر: تخطي المنتجات التي يقل سعرها عن 15 ريال
            try:
                price_val = float(row.get('price', 0.0))
                if price_val < 15.0:
                    continue
            except ValueError:
                pass # في حال كان السعر غير متوفر كأرقام، نكمل المعالجة
                
            comp_attrs = extract_attributes(product_name)
            
            # فلتر العينات: تخطي المنتجات التي يقل حجمها عن 10 مل
            if comp_attrs["is_sample"]:
                continue
                
            match_row, score, candidates = matcher.get_best_match(product_name, comp_attrs)
            
            # تحديث عتبات الدقة نظراً لأن الخوارزمية أصبحت أكثر صرامة وتعاقب بشدة
            if score >= 75:
                status = "متوفر (مكرر)"
            elif score >= 45:
                status = "يحتاج مراجعة"
            else:
                status = "منتج مفقود مؤكد"
                
            results.append({
                "product_name": product_name,
                "price": row.get('price', 0.0),
                "image_url": row.get('image_url', ''),
                "competitor_name": comp_name,
                "confidence_score": score,
                "status": status,
                "matched_product": match_row.get('product_name', 'لا يوجد') if match_row is not None else "لا يوجد",
                "matched_image": match_row.get('image_url', '') if match_row is not None else "",
                "brand": row.get('brand', 'غير محدد'),
                "top_candidates": candidates
            })
            
    return pd.DataFrame(results)

async def ai_deep_verify_candidates(comp_product: str, candidates: List[str]) -> Dict:
    """زر التحقق الذكي: يسأل Gemini لمقارنة المنتج المفقود بأقرب 5 منتجات."""
    try:
        from config import GEMINI_API_KEY
        import google.generativeai as genai
    except ImportError as e:
        return {"found": False, "reason": f"نقص في المكتبات: {str(e)}"}

    if not GEMINI_API_KEY:
        return {"found": False, "reason": "مفتاح API الخاص بـ Gemini غير متوفر"}
        
    prompt = f"""
    أنت خبير بيانات وعطور دقيق جداً.
    المنتج المراد التأكد منه (من المنافس): "{comp_product}"
    
    قائمة بأقرب المنتجات المتوفرة في متجرنا:
    {json.dumps(candidates, ensure_ascii=False)}
    
    هل المنتج المراد البحث عنه موجود "بالضبط" ضمن هذه القائمة؟
    تحذير: يجب أن تفرق بدقة بين الأحجام (مثال: 50مل لا يساوي 100مل) والتركيز (EDP لا يساوي EDT) والأنواع (تستر لا يساوي عادي).
    
    أجب بصيغة JSON فقط:
    {{"found": true/false, "matched_name": "اسم المنتج المطابق إن وجد، أو اتركه فارغاً", "reason": "سبب قرارك باختصار شديد بالعربية"}}
    """
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = await asyncio.to_thread(model.generate_content, prompt)
        res_text = re.sub(r'```json\s*|\s*```', '', response.text).strip()
        data = json.loads(res_text)
        return data
    except Exception as e:
        return {"found": False, "reason": f"خطأ في الاتصال بالذكاء الاصطناعي: {str(e)[:50]}"}

def get_brand_statistics(results_df: pd.DataFrame) -> pd.DataFrame:
    """إحصائيات الماركات للمنتجات المفقودة لتوجيه المشتريات."""
    if results_df.empty: return pd.DataFrame()
    missing_only = results_df[results_df['status'] == "منتج مفقود مؤكد"]
    if missing_only.empty: return pd.DataFrame()
    
    brand_stats = missing_only.groupby('brand').size().reset_index(name='count')
    return brand_stats.sort_values(by='count', ascending=False).head(10)

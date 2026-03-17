"""
missing_products_app/ai_matcher.py
نظام مهووس الذكي - الإصدار V9.0 (المعدل والمصحح)
محرك المطابقة المتقدم (RapidFuzz + TF-IDF)
"""

import pandas as pd
import re
from rapidfuzz import fuzz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from typing import Dict, Tuple, Optional

def normalize_product_name(text: str) -> str:
    """
    تنظيف وتوحيد اسم المنتج لضمان دقة المطابقة.
    """
    if not isinstance(text, str) or pd.isna(text):
        return ""
    
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    
    stop_words = [
        r'\btester\b', r'\bتستر\b', r'\bedp\b', r'\bedt\b', 
        r'\beau de parfum\b', r'\beau de toilette\b', r'\bparfum\b',
        r'\bml\b', r'\bمل\b', r'\b100ml\b', r'\b50ml\b', r'\b200ml\b',
        r'\bللجنسين\b', r'\bللرجال\b', r'\بللنساء\b', r'\bmen\b', r'\bwomen\b', r'\bunisex\b'
    ]
    for word in stop_words:
        text = re.sub(word, ' ', text)
    
    return " ".join(text.split())

def extract_attributes(name: str) -> Dict[str, str]:
    """
    استخراج السمات الأساسية (الحجم، التركيز) للتمييز بين المنتجات المتشابهة.
    """
    attributes = {"size": "unknown", "concentration": "unknown"}
    if not isinstance(name, str): return attributes
    
    name_lower = name.lower()
    
    # البحث عن الحجم
    size_match = re.search(r'(\d+)\s*(ml|مل)', name_lower)
    if size_match:
        attributes["size"] = size_match.group(1)
        
    # البحث عن التركيز
    if any(k in name_lower for k in ["edp", "parfum", "بارفيوم"]):
        attributes["concentration"] = "edp"
    elif any(k in name_lower for k in ["edt", "toilette", "تواليت"]):
        attributes["concentration"] = "edt"
        
    return attributes

class AIMatcher:
    def __init__(self, mahwous_df: pd.DataFrame):
        self.mahwous_df = mahwous_df
        if not self.mahwous_df.empty:
            if 'normalized_name' not in self.mahwous_df.columns:
                self.mahwous_df['normalized_name'] = self.mahwous_df['product_name'].apply(normalize_product_name)
                
            # --- الإصلاح الجذري لمعالجة النصوص الفارغة ---
            # حقن قيمة افتراضية للنصوص التي أصبحت فارغة بعد التنظيف
            self.mahwous_df['normalized_name'] = self.mahwous_df['normalized_name'].replace(r'^\s*$', 'منتج_بدون_اسم', regex=True).fillna('منتج_بدون_اسم')
            
            self.mahwous_names = self.mahwous_df['normalized_name'].tolist()
            self.vectorizer = TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 4))
            
            # حماية المحرك بـ Try/Except
            try:
                self.tfidf_matrix = self.vectorizer.fit_transform(self.mahwous_names)
            except ValueError:
                # خطة طوارئ في حال فشل استخراج الميزات
                self.mahwous_names = ['منتج_غير_معروف'] * len(self.mahwous_names)
                self.tfidf_matrix = self.vectorizer.fit_transform(self.mahwous_names)
        else:
            self.mahwous_names = []

    def get_best_match(self, competitor_name: str) -> Tuple[Optional[pd.Series], float]:
        """
        البحث عن أفضل تطابق باستخدام تقنيات هجينة (TF-IDF + RapidFuzz).
        """
        if not self.mahwous_names:
            return None, 0.0
            
        norm_name = normalize_product_name(competitor_name)
        comp_attrs = extract_attributes(competitor_name)
        
        # المرحلة الأولى: تصفية سريعة باستخدام TF-IDF Cosine Similarity
        query_vec = self.vectorizer.transform([norm_name])
        cosine_sim = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
        
        top_indices = cosine_sim.argsort()[-20:][::-1]
        best_final_score = 0
        best_match_idx = -1
        
        # المرحلة الثانية: مطابقة دقيقة باستخدام RapidFuzz
        for idx in top_indices:
            mahwous_name = self.mahwous_names[idx]
            fuzz_score = fuzz.token_set_ratio(norm_name, mahwous_name)
            
            mahwous_row = self.mahwous_df.iloc[idx]
            # إصلاح: استخدام مفتاح product_name الصحيح
            mahwous_attrs = extract_attributes(str(mahwous_row.get('product_name', '')))
            
            if comp_attrs["size"] != "unknown" and mahwous_attrs["size"] != "unknown":
                if comp_attrs["size"] != mahwous_attrs["size"]:
                    fuzz_score *= 0.6
            
            if comp_attrs["concentration"] != "unknown" and mahwous_attrs["concentration"] != "unknown":
                if comp_attrs["concentration"] != mahwous_attrs["concentration"]:
                    fuzz_score *= 0.8

            if fuzz_score > best_final_score:
                best_final_score = fuzz_score
                best_match_idx = idx
                
        if best_match_idx != -1:
            return self.mahwous_df.iloc[best_match_idx], best_final_score
        return None, 0.0

def process_competitors(mahwous_df: pd.DataFrame, competitors_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    معالجة بيانات المنافسين وتصنيفها بناءً على عتبات الدقة الجديدة V9.0.
    """
    matcher = AIMatcher(mahwous_df)
    results = []
    
    for comp_name, comp_df in competitors_data.items():
        if comp_df.empty:
            continue
            
        for _, row in comp_df.iterrows():
            # إصلاح: استخدام product_name بدلاً من name
            product_name = str(row.get('product_name', ''))
            if not product_name or product_name == 'nan':
                continue
                
            match_row, score = matcher.get_best_match(product_name)
            
            if score >= 80:
                status = "متوفر (مكرر)"
            elif score >= 40:
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
                # إصلاح: استخدام المفاتيح الإنجليزية الصحيحة
                "matched_product": match_row.get('product_name', 'لا يوجد') if match_row is not None else "لا يوجد",
                "matched_image": match_row.get('image_url', '') if match_row is not None else "",
                "brand": row.get('brand', 'غير محدد')
            })
            
    return pd.DataFrame(results)

def get_brand_statistics(results_df: pd.DataFrame) -> pd.DataFrame:
    """
    حساب إحصائيات الماركات المفقودة لتحديد الفرص البيعية.
    """
    if results_df.empty:
        return pd.DataFrame()
        
    missing_only = results_df[results_df['status'] == "منتج مفقود مؤكد"]
    
    if missing_only.empty:
        return pd.DataFrame()
        
    brand_stats = missing_only.groupby('brand').size().reset_index(name='count')
    brand_stats = brand_stats.sort_values(by='count', ascending=False).head(10)
    
    return brand_stats

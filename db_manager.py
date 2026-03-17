"""
db_manager.py v5.3 — مدير تحميل البيانات (Smarter Detection)
═══════════════════════════════════════════════════
- كشف ذكي للأعمدة يتوافق مع ملفات Salla المجمعة (Scraped Data)
- معالجة آمنة للبيانات الناقصة لتجنب الانهيارات الصامتة
"""

import pandas as pd
import streamlit as st
from typing import Dict, Optional

def load_mahwous_store_data(uploaded_file) -> pd.DataFrame:
    """تحميل بيانات متجر مهووس (متوافق مع CSV)."""
    if uploaded_file is None: return pd.DataFrame()
    try:
        df = pd.read_csv(uploaded_file, header=1, encoding="utf-8-sig")
        if "أسم المنتج" not in df.columns:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, header=0, encoding="utf-8-sig")
        
        rename_map = {
            "أسم المنتج": "product_name", "اسم المنتج": "product_name",
            "سعر المنتج": "price", "صورة المنتج": "image_url",
            "الماركة": "brand", "الوصف": "description"
        }
        df.rename(columns=rename_map, inplace=True)
        return df.dropna(subset=["product_name"]) if "product_name" in df.columns else pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading store data: {e}")
        return pd.DataFrame()

def load_competitor_data(uploaded_file) -> pd.DataFrame:
    """تحميل بيانات المنافس مع كشف ذكي للأعمدة (Salla Scraper Compatibility)."""
    if uploaded_file is None: return pd.DataFrame()
    try:
        df = pd.read_csv(uploaded_file, encoding="utf-8-sig")
        
        # كشف تلقائي ذكي للأعمدة بناءً على الكلمات المفتاحية
        mapping = {
            "product_name": ["اسم", "product", "name", "title"],
            "price": ["سعر", "price", "text-sm", "amount"],
            "image_url": ["صورة", "image", "img", "src", "thumbnail"],
            "brand": ["ماركة", "brand"]
        }
        
        detected_cols = {}
        for internal_name, keywords in mapping.items():
            for col in df.columns:
                col_lower = str(col).lower()
                if any(kw in col_lower for kw in keywords):
                    detected_cols[col] = internal_name
                    break # نأخذ أول تطابق لكل عمود داخلي
        
        df.rename(columns=detected_cols, inplace=True)
        
        # التأكد من وجود عمود الاسم على الأقل
        if "product_name" not in df.columns:
            st.warning(f"⚠️ لم يتم التعرف على عمود الاسم في {uploaded_file.name}. الأعمدة المتاحة: {list(df.columns)}")
            return pd.DataFrame()
            
        # معالجة آمنة للبيانات الناقصة
        # نستخدم fillna بدلاً من dropna مباشرة لتجنب حذف كافة الصفوف إذا فشل الكشف عن عمود معين
        for col in ["price", "image_url", "brand"]:
            if col not in df.columns:
                df[col] = 0.0 if col == "price" else ""
        
        # حذف الصفوف التي ليس لها اسم منتج فقط
        return df.dropna(subset=["product_name"]).copy()
        
    except Exception as e:
        st.error(f"Error loading competitor data: {e}")
        return pd.DataFrame()

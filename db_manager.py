"""
db_manager.py v12.0 — مدير تحميل البيانات الذكي
══════════════════════════════════════════════════════════════════════
- إصلاح روابط الصور التي تبدأ بـ "//" لجعلها مقروءة في المتصفح.
- كشف ذكي جداً للأعمدة المعقدة الخاصة بأدوات سحب البيانات (Scrapers).
- تنظيف متقدم للأسعار لتجنب أخطاء التحويل الرقمي.
"""

import pandas as pd
import streamlit as st
import re
from typing import Dict, Optional

def load_mahwous_store_data(uploaded_file) -> pd.DataFrame:
    """تحميل بيانات متجر مهووس والتأكد من توافقها وتنظيف أسعارها."""
    if uploaded_file is None: 
        return pd.DataFrame()
        
    try:
        # محاولة قراءة الملف، وتخطي الصف الأول إذا كان مجرد عنوان عام
        df = pd.read_csv(uploaded_file, header=1, encoding="utf-8-sig")
        
        # إذا لم نجد العمود، نجرب القراءة من الصف الأول
        if "أسم المنتج" not in df.columns and "اسم المنتج" not in df.columns:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, header=0, encoding="utf-8-sig")
        
        # توحيد أسماء الأعمدة للتعامل البرمجي
        rename_map = {
            "أسم المنتج": "product_name", 
            "اسم المنتج": "product_name",
            "سعر المنتج": "price", 
            "صورة المنتج": "image_url",
            "الماركة": "brand", 
            "الوصف": "description",
            "رمز المنتج sku": "sku",
            "SKU": "sku"
        }
        df.rename(columns=rename_map, inplace=True)
        
        if "product_name" in df.columns:
            df['product_name'] = df['product_name'].fillna("")
            df = df[df['product_name'].str.strip() != ""].copy()
            
            # تنظيف صارم للأسعار
            if 'price' in df.columns:
                df['price'] = pd.to_numeric(df['price'].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce').fillna(0.0)
                
            return df
        else:
            st.error("❌ ملف متجر مهووس لا يحتوي على عمود 'أسم المنتج'.")
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"❌ خطأ أثناء تحميل بيانات متجر مهووس: {e}")
        return pd.DataFrame()

def load_competitor_data(uploaded_file) -> pd.DataFrame:
    """
    تحميل بيانات المنافس مع كشف ذكي للأعمدة وإصلاح روابط الصور والأسعار.
    """
    if uploaded_file is None: 
        return pd.DataFrame()
        
    try:
        df = pd.read_csv(uploaded_file, encoding="utf-8-sig")
        
        # خريطة الكلمات المفتاحية للكشف الذكي (شاملة لأدوات السحب)
        mapping = {
            "product_name": ["اسم", "product", "name", "title", "عنوان", "styles_productcard__name"],
            "price": ["سعر", "price", "amount", "cost", "السعر", "text-sm-2"],
            "image_url": ["صورة", "image", "img", "src", "thumbnail", "رابط الصورة", "w-full src"],
            "brand": ["ماركة", "brand", "شركة", "علامة"]
        }
        
        detected_cols = {}
        for col in df.columns:
            col_lower = str(col).lower().strip()
            for internal_name, keywords in mapping.items():
                if internal_name not in detected_cols.values():
                    if any(kw in col_lower for kw in keywords):
                        detected_cols[col] = internal_name
                        break
        
        df.rename(columns=detected_cols, inplace=True)
        
        if "product_name" not in df.columns:
            st.warning(f"⚠️ لم يتم التعرف على عمود 'اسم المنتج' في ملف: {uploaded_file.name}")
            return pd.DataFrame()
            
        # معالجة وتنظيف السعر
        if "price" not in df.columns:
            df["price"] = 0.0
        else:
            df["price"] = pd.to_numeric(df["price"].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce').fillna(0.0)

        # إصلاح الصور المقفلة أو الروابط الناقصة
        if "image_url" not in df.columns:
            df["image_url"] = ""
        else:
            df["image_url"] = df["image_url"].fillna("").astype(str)
            # إضافة https:// للروابط التي تبدأ بـ // وتسبب عدم ظهور الصورة
            df["image_url"] = df["image_url"].apply(lambda x: f"https:{x}" if str(x).startswith("//") else x)

        if "brand" not in df.columns:
            df["brand"] = "غير معروف"
        else:
            df["brand"] = df["brand"].fillna("غير معروف")
            
        df['product_name'] = df['product_name'].fillna("").astype(str).str.strip()
        
        return df[df['product_name'] != ""].copy()
        
    except Exception as e:
        st.error(f"❌ خطأ في معالجة ملف المنافس '{uploaded_file.name}': {e}")
        return pd.DataFrame()

"""
db_manager.py v7.1 — مدير تحميل البيانات (Smarter Detection & Salla Support)
══════════════════════════════════════════════════════════════════════
- كشف ذكي جداً للأعمدة يتوافق مع ملفات "سلة" (Salla) المجمعة أو المصدرة
- مرونة عالية في التعامل مع العناوين المتغيرة أو غير المرتبة
- معالجة آمنة للبيانات الناقصة لتجنب الانهيارات الصامتة (Silent Crashes)
"""

import pandas as pd
import streamlit as st
from typing import Dict, Optional

def load_mahwous_store_data(uploaded_file) -> pd.DataFrame:
    """تحميل بيانات متجر مهووس والتأكد من توافقها."""
    if uploaded_file is None: 
        return pd.DataFrame()
        
    try:
        # محاولة قراءة الملف، وتخطي الصف الأول إذا كان مجرد عنوان عام
        df = pd.read_csv(uploaded_file, header=1, encoding="utf-8-sig")
        
        # إذا لم نجد عمود "أسم المنتج" (كما هو في ملفات مهووس)، نجرب القراءة من الصف الأول
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
        
        # التأكد من وجود عمود الاسم الأساسي
        if "product_name" in df.columns:
            # تحويل القيم الفارغة إلى نصوص فارغة بدلاً من حذفها لمنع الأخطاء
            df['product_name'] = df['product_name'].fillna("")
            # استبعاد الصفوف التي لا تحتوي على اسم منتج فعلي
            return df[df['product_name'].str.strip() != ""].copy()
        else:
            st.error("❌ ملف متجر مهووس لا يحتوي على عمود 'أسم المنتج'.")
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"❌ خطأ أثناء تحميل بيانات المتجر: {e}")
        return pd.DataFrame()

def load_competitor_data(uploaded_file) -> pd.DataFrame:
    """
    تحميل بيانات المنافس مع كشف ذكي للأعمدة يتوافق مع "سلة" وغيرها.
    يتعامل بمرونة مع العناوين المتغيرة أو غير المرتبة.
    """
    if uploaded_file is None: 
        return pd.DataFrame()
        
    try:
        df = pd.read_csv(uploaded_file, encoding="utf-8-sig")
        
        # خريطة الكلمات المفتاحية للكشف الذكي عن الأعمدة (يدعم سلة وأي سكرابر)
        mapping = {
            "product_name": ["اسم", "product", "name", "title", "عنوان"],
            "price": ["سعر", "price", "amount", "cost", "السعر"],
            "image_url": ["صورة", "image", "img", "src", "thumbnail", "رابط الصورة"],
            "brand": ["ماركة", "brand", "شركة", "علامة"]
        }
        
        detected_cols = {}
        # فحص كل عمود في الملف المرفوع ومطابقته مع الكلمات المفتاحية
        for col in df.columns:
            col_lower = str(col).lower().strip()
            
            for internal_name, keywords in mapping.items():
                # إذا لم يتم تعيين هذا العمود الداخلي بعد، ووجدنا تطابقاً
                if internal_name not in detected_cols.values():
                    if any(kw in col_lower for kw in keywords):
                        detected_cols[col] = internal_name
                        break
        
        # إعادة تسمية الأعمدة التي تم التعرف عليها
        df.rename(columns=detected_cols, inplace=True)
        
        # التحقق الحرج: يجب أن يكون هناك عمود للاسم
        if "product_name" not in df.columns:
            st.warning(f"⚠️ لم يتم التعرف على عمود 'اسم المنتج' في ملف: {uploaded_file.name}. تأكد من ترويسة الأعمدة.")
            return pd.DataFrame()
            
        # معالجة البيانات الناقصة بذكاء بدلاً من الحذف العشوائي (لتجنب الانهيارات)
        if "price" not in df.columns:
            df["price"] = 0.0
        else:
            # تنظيف عمود السعر من أي نصوص أو رموز (مثل ر.س أو $)
            df["price"] = pd.to_numeric(df["price"].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce').fillna(0.0)

        if "image_url" not in df.columns:
            df["image_url"] = ""
        else:
            df["image_url"] = df["image_url"].fillna("")

        if "brand" not in df.columns:
            df["brand"] = "غير معروف"
        else:
            df["brand"] = df["brand"].fillna("غير معروف")
            
        # تنظيف عمود الاسم والتأكد من عدم وجود قيم فارغة
        df['product_name'] = df['product_name'].fillna("").astype(str).str.strip()
        
        # إرجاع الصفوف التي تحتوي على اسم منتج فقط
        return df[df['product_name'] != ""].copy()
        
    except Exception as e:
        st.error(f"❌ خطأ في معالجة ملف المنافس '{uploaded_file.name}': {e}")
        return pd.DataFrame()

"""
db_manager.py v3.0 — مدير تحميل وتنظيف البيانات المتوافق مع AI Matcher v3.0
═══════════════════════════════════════════════════
- تحميل ذكي لملف مهووس (header=1)
- كشف تلقائي لأعمدة المنافسين
- تنظيف الأسعار والروابط
- متوافق مع محرك المطابقة الهجين
"""

import re
import pandas as pd
import streamlit as st
from typing import List, Dict, Optional
from ai_matcher import normalize_arabic


# ══════════════════════════════════════════════════════════════
#  تحميل بيانات متجر مهووس
# ══════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600, show_spinner=False)
def load_mahwous_store_data(uploaded_file) -> pd.DataFrame:
    """تحميل وتنظيف بيانات متجر مهووس."""
    if uploaded_file is None:
        return pd.DataFrame()
    try:
        # محاولة القراءة بـ header=1 أولاً
        df = pd.read_csv(uploaded_file, header=1, encoding="utf-8-sig")

        # التحقق: هل الأعمدة تحتوي على "أسم المنتج"؟
        if "أسم المنتج" not in df.columns:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, header=0, encoding="utf-8-sig")

        # إعادة تسمية الأعمدة المعروفة للبنية الداخلية الموحدة
        rename_map = {
            "أسم المنتج": "product_name",
            "اسم المنتج": "product_name",
            "سعر المنتج": "price",
            "صورة المنتج": "image_url",
            "رمز المنتج sku": "sku",
            "رمز المنتج SKU": "sku",
            "الماركة": "brand",
            "الوصف": "description",
            "النوع": "category",
            "تصنيف المنتج": "category",
        }
        df.rename(columns=rename_map, inplace=True)

        # التأكد من العمود الأساسي
        if "product_name" not in df.columns:
            st.error("❌ لم يتم العثور على عمود 'أسم المنتج' في ملف مهووس.")
            return pd.DataFrame()

        # تنظيف الأسعار
        if "price" in df.columns:
            df["price"] = pd.to_numeric(
                df["price"].astype(str).str.replace(r'[^\d.]', '', regex=True),
                errors='coerce'
            ).fillna(0)

        # إزالة الصفوف الفارغة
        df = df.dropna(subset=["product_name"]).copy()
        df = df[df["product_name"].astype(str).str.strip() != ""].copy()

        return df

    except Exception as e:
        st.error(f"❌ خطأ في قراءة ملف متجر مهووس: {e}")
        return pd.DataFrame()


# ══════════════════════════════════════════════════════════════
#  تحميل بيانات المنافسين
# ══════════════════════════════════════════════════════════════

def _detect_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    """البحث عن عمود بأسماء مرشحة."""
    for c in candidates:
        for col in df.columns:
            if c.lower() in col.lower():
                return col
    return None

@st.cache_data(ttl=3600, show_spinner=False)
def load_competitor_data(uploaded_file) -> pd.DataFrame:
    """تحميل بيانات منافس واحد مع كشف تلقائي للأعمدة."""
    if uploaded_file is None:
        return pd.DataFrame()

    try:
        df = pd.read_csv(uploaded_file, encoding="utf-8-sig")
        if df.empty:
            return pd.DataFrame()

        # كشف الأعمدة
        name_col = _detect_column(df, ["اسم المنتج", "أسم المنتج", "product_name", "name", "title"])
        price_col = _detect_column(df, ["سعر", "السعر", "price"])
        image_col = _detect_column(df, ["صورة", "image", "img", "src"])
        brand_col = _detect_column(df, ["ماركة", "الماركة", "brand"])

        if not name_col:
            st.warning(f"⚠️ لم يتم التعرف على عمود الاسم في {uploaded_file.name}")
            return pd.DataFrame()

        # بناء DataFrame موحد
        clean_df = pd.DataFrame()
        clean_df["product_name"] = df[name_col].astype(str).str.strip()
        clean_df["price"] = pd.to_numeric(df[price_col].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce').fillna(0) if price_col else 0.0
        clean_df["image_url"] = df[image_col].astype(str).str.strip() if image_col else ""
        clean_df["brand"] = df[brand_col].astype(str).str.strip() if brand_col else "غير معروف"
        
        # تنظيف إضافي
        clean_df = clean_df[clean_df["product_name"].str.len() > 2].copy()
        
        return clean_df

    except Exception as e:
        st.error(f"❌ خطأ في ملف المنافس: {e}")
        return pd.DataFrame()

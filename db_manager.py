"""
db_manager.py v2.0 — مدير تحميل وتنظيف البيانات
═══════════════════════════════════════════════════
- تحميل ذكي لملف مهووس (header=1)
- كشف تلقائي لأعمدة المنافسين
- تنظيف الأسعار والروابط
"""

import re
import pandas as pd
import streamlit as st
from typing import List, Dict, Optional
from ai_matcher import normalize_aggressive


# ══════════════════════════════════════════════════════════════
#  تحميل بيانات متجر مهووس
# ══════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600, show_spinner=False)
def load_mahwous_store_data(uploaded_file) -> Optional[pd.DataFrame]:
    """
    تحميل وتنظيف بيانات متجر مهووس.
    - الصف الأول وصفي، الصف الثاني هو الـ Header الحقيقي → header=1
    """
    if uploaded_file is None:
        return None
    try:
        # محاولة القراءة بـ header=1 أولاً
        df = pd.read_csv(uploaded_file, header=1, encoding="utf-8-sig")

        # التحقق: هل الأعمدة تحتوي على "أسم المنتج"؟
        if "أسم المنتج" not in df.columns:
            # ربما الملف بدون صف وصفي → نحاول header=0
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, header=0, encoding="utf-8-sig")

        # إعادة تسمية الأعمدة المعروفة
        rename_map = {
            "أسم المنتج": "name",
            "اسم المنتج": "name",
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

        # التأكد من الأعمدة الأساسية
        if "name" not in df.columns:
            st.error("❌ لم يتم العثور على عمود 'أسم المنتج' في ملف مهووس.")
            return None

        # تنظيف الأسعار
        if "price" in df.columns:
            df["price"] = pd.to_numeric(
                df["price"].astype(str).str.replace(r'[^\d.]', '', regex=True),
                errors='coerce'
            ).fillna(0)

        # إزالة الصفوف الفارغة
        df = df.dropna(subset=["name"]).copy()
        df = df[df["name"].astype(str).str.strip() != ""].copy()

        # إضافة عمود التطبيع
        df["normalized_name"] = df["name"].apply(normalize_aggressive)

        return df

    except Exception as e:
        st.error(f"❌ خطأ في قراءة ملف متجر مهووس: {e}")
        return None


# ══════════════════════════════════════════════════════════════
#  كشف تلقائي لأعمدة المنافسين
# ══════════════════════════════════════════════════════════════

def _detect_column(df: pd.DataFrame, candidates: List[str], fallback_heuristic: str = "") -> Optional[str]:
    """البحث عن عمود بأسماء مرشحة أو بتحليل المحتوى."""
    # بحث بالاسم
    for c in candidates:
        for col in df.columns:
            if c.lower() in col.lower():
                return col

    # بحث بالمحتوى
    if fallback_heuristic == "url":
        for col in df.columns:
            sample = df[col].dropna().head(5).astype(str)
            if sample.str.contains(r'https?://', regex=True).mean() > 0.5:
                return col

    elif fallback_heuristic == "price":
        for col in df.columns:
            try:
                numeric = pd.to_numeric(
                    df[col].astype(str).str.replace(r'[^\d.]', '', regex=True),
                    errors='coerce'
                )
                if numeric.notna().mean() > 0.5 and 5 < numeric.median() < 10000:
                    return col
            except Exception:
                continue

    elif fallback_heuristic == "text":
        for col in df.columns:
            sample = df[col].dropna().head(10).astype(str)
            avg_len = sample.str.len().mean()
            if avg_len > 10 and not sample.str.contains(r'https?://', regex=True).any():
                return col

    return None


def _detect_image_columns(df: pd.DataFrame) -> Optional[str]:
    """كشف عمود الصور (URL يحتوي على امتدادات صور أو CDN معروف)."""
    img_patterns = [r'\.jpg', r'\.jpeg', r'\.png', r'\.webp', r'cdn\.salla', r'cdn-cgi/image']
    for col in df.columns:
        sample = df[col].dropna().head(5).astype(str)
        for pat in img_patterns:
            if sample.str.contains(pat, case=False, regex=True).mean() > 0.3:
                return col
    return _detect_column(df, ["صورة", "image", "img", "src", "photo"], "url")


# ══════════════════════════════════════════════════════════════
#  تحميل بيانات المنافسين
# ══════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600, show_spinner=False)
def load_competitor_data(uploaded_files: List) -> Dict[str, pd.DataFrame]:
    """
    تحميل بيانات المنافسين مع كشف تلقائي للأعمدة.
    يُعيد: {اسم_المنافس: DataFrame}
    """
    competitors_data = {}
    if not uploaded_files:
        return competitors_data

    for file in uploaded_files:
        try:
            # استخلاص اسم المنافس من اسم الملف
            raw_name = file.name.replace(".csv", "").replace("_", " ")
            # محاولة ذكية لاستخلاص الاسم
            for sep in ["بكل", "بالكامل", "كامل", "جميع", "all"]:
                if sep in raw_name:
                    raw_name = raw_name.split(sep)[0]
                    break
            comp_name = raw_name.replace("متجر", "").replace("منتجات", "").strip()
            if not comp_name or len(comp_name) < 2:
                comp_name = file.name.split(".")[0][:30]

            df = pd.read_csv(file, encoding="utf-8-sig")
            if df.empty or len(df.columns) < 2:
                st.warning(f"⚠️ ملف '{comp_name}' فارغ أو بعمود واحد.")
                continue

            # — كشف تلقائي للأعمدة —
            name_col = _detect_column(df, [
                "اسم المنتج", "أسم المنتج", "اسم", "product_name", "name", "title",
                "styles_productCard__name", "productCard__name"
            ], "text")

            price_col = _detect_column(df, [
                "سعر", "السعر", "price", "text-sm-2", "سعر المنتج"
            ], "price")

            image_col = _detect_image_columns(df)

            url_col = _detect_column(df, [
                "رابط", "href", "url", "link", "product_url", "abs-size href"
            ], "url")

            if not name_col:
                st.warning(f"⚠️ لم يتم التعرف على عمود اسم المنتج في ملف '{comp_name}'. سيتم تخطيه.")
                continue

            # بناء DataFrame موحد
            clean_df = pd.DataFrame()
            clean_df["name"] = df[name_col].astype(str).str.strip()

            if price_col:
                clean_df["price"] = pd.to_numeric(
                    df[price_col].astype(str).str.replace(r'[^\d.]', '', regex=True),
                    errors='coerce'
                ).fillna(0)
            else:
                clean_df["price"] = 0.0

            if image_col:
                clean_df["image_url"] = df[image_col].astype(str).str.strip()
            else:
                clean_df["image_url"] = ""

            if url_col:
                clean_df["product_url"] = df[url_col].astype(str).str.strip()
            else:
                clean_df["product_url"] = ""

            # تنظيف
            clean_df = clean_df[clean_df["name"].str.len() > 3].copy()
            clean_df = clean_df.dropna(subset=["name"]).copy()
            clean_df["competitor_name"] = comp_name
            clean_df["normalized_name"] = clean_df["name"].apply(normalize_aggressive)

            if len(clean_df) > 0:
                competitors_data[comp_name] = clean_df
                st.success(f"✅ تم تحميل {len(clean_df)} منتج من '{comp_name}'")
            else:
                st.warning(f"⚠️ لم يتبقَ أي منتج صالح من ملف '{comp_name}'.")

        except Exception as e:
            st.warning(f"❌ خطأ في معالجة ملف '{file.name}': {e}")
            continue

    return competitors_data

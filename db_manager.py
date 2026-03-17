"""
db_manager.py v13.0 — مدير تحميل البيانات السيادي
══════════════════════════════════════════════════════════════════════
[v12.0] إصلاح روابط الصور التي تبدأ بـ "//" + كشف ذكي للأعمدة + تنظيف الأسعار.
[v13.0] تعديلات جراحية:
  - استخراج رابط الصورة الأصلي من مسارات CDN-CGI الطويلة (Salla Scraper).
  - كشف أعمدة CSS-class المعقدة (styles_productCard__name__pakbB, w-full src, text-sm-2).
  - استخراج السعر الصحيح حتى لو كان مصحوباً بنسبة خصم في عمود مجاور.
  - حفظ بيانات الجلسة في JSON لمنع فقدان النتائج عند تغيير التبويب.
"""

import pandas as pd
import streamlit as st
import re
import json
import os
from typing import Dict, Optional

# ─── مسار ملف حفظ الجلسة ───
SESSION_FILE = os.path.join(os.path.dirname(__file__), "session_cache.json")


def save_session_to_disk(data: dict):
    """حفظ بيانات الجلسة على القرص لمنع فقدانها عند إعادة التشغيل."""
    try:
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_session_from_disk() -> dict:
    """تحميل بيانات الجلسة المحفوظة من القرص."""
    try:
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _clean_cdn_cgi_url(url: str) -> str:
    """
    استخراج رابط الصورة الأصلي من مسار CDN-CGI الطويل الخاص بـ Salla.
    مثال:
      https://cdn.salla.sa/cdn-cgi/image/fit=scale-down,width=500,.../STORE_ID/UUID-500x500-HASH.jpg
      → https://cdn.salla.sa/STORE_ID/UUID-500x500-HASH.jpg
    """
    if not isinstance(url, str) or not url.strip():
        return url

    # إصلاح الروابط التي تبدأ بـ //
    if url.startswith("//"):
        url = "https:" + url

    # استخراج الرابط من مسار cdn-cgi/image/...
    cgi_match = re.search(r'cdn-cgi/image/[^/]+/(.+)', url)
    if cgi_match:
        remainder = cgi_match.group(1)
        # الـ remainder يبدأ بـ STORE_ID/filename
        return f"https://cdn.salla.sa/{remainder}"

    return url


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
            "SKU": "sku",
        }
        df.rename(columns=rename_map, inplace=True)

        if "product_name" in df.columns:
            df["product_name"] = df["product_name"].fillna("")
            df = df[df["product_name"].str.strip() != ""].copy()

            # تنظيف صارم للأسعار
            if "price" in df.columns:
                df["price"] = pd.to_numeric(
                    df["price"].astype(str).str.replace(r"[^\d.]", "", regex=True),
                    errors="coerce",
                ).fillna(0.0)

            # إصلاح روابط الصور
            if "image_url" in df.columns:
                df["image_url"] = df["image_url"].fillna("").astype(str).apply(_clean_cdn_cgi_url)

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
    [v13.0] يدعم أعمدة CSS-class المعقدة الناتجة عن أدوات السحب (Scrapers).
    """
    if uploaded_file is None:
        return pd.DataFrame()

    try:
        df = pd.read_csv(uploaded_file, encoding="utf-8-sig")

        # ─── خريطة الكشف الذكي (شاملة لأدوات السحب وأسماء CSS) ───
        mapping = {
            "product_name": [
                "اسم", "product", "name", "title", "عنوان",
                "styles_productcard__name",          # ساراء ميكاب / جيفنشي
                "productcard__name",
            ],
            "price": [
                "سعر", "price", "amount", "cost", "السعر",
                "text-sm-2",                          # ساراء ميكاب / جيفنشي
                "font-normal",                        # السعر الأساسي
            ],
            "image_url": [
                "صورة", "image", "img", "src", "thumbnail", "رابط الصورة",
                "w-full src",                         # ساراء ميكاب / جيفنشي
            ],
            "brand": ["ماركة", "brand", "شركة", "علامة"],
            "product_url": [
                "href", "link", "رابط", "abs-size href",
            ],
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

        # ─── معالجة السعر ───
        if "price" not in df.columns:
            df["price"] = 0.0
        else:
            # إزالة نسب الخصم (مثل -33%) والرموز غير الرقمية
            df["price"] = (
                df["price"]
                .astype(str)
                .str.replace(r"[^\d.]", "", regex=True)
                .replace("", "0")
            )
            df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0.0)

        # ─── إصلاح الصور ───
        if "image_url" not in df.columns:
            df["image_url"] = ""
        else:
            df["image_url"] = (
                df["image_url"]
                .fillna("")
                .astype(str)
                .apply(_clean_cdn_cgi_url)
            )

        # ─── الماركة ───
        if "brand" not in df.columns:
            df["brand"] = "غير معروف"
        else:
            df["brand"] = df["brand"].fillna("غير معروف")

        df["product_name"] = df["product_name"].fillna("").astype(str).str.strip()

        return df[df["product_name"] != ""].copy()

    except Exception as e:
        st.error(f"❌ خطأ في معالجة ملف المنافس '{uploaded_file.name}': {e}")
        return pd.DataFrame()

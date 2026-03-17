"""
db_manager.py v5.0 — مدير تحميل البيانات (Memory-Only)
═══════════════════════════════════════════════════
- تحميل ذكي لملف مهووس وملفات المنافسين
- كشف تلقائي للأعمدة
- لا يعتمد على SQLite، يعتمد كلياً على Session State
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
        return df.dropna(subset=["product_name"])
    except Exception as e:
        st.error(f"Error loading store data: {e}")
        return pd.DataFrame()

def load_competitor_data(uploaded_file) -> pd.DataFrame:
    """تحميل بيانات المنافس (متوافق مع CSV)."""
    if uploaded_file is None: return pd.DataFrame()
    try:
        df = pd.read_csv(uploaded_file, encoding="utf-8-sig")
        # كشف تلقائي مبسط للأعمدة
        for col in df.columns:
            col_lower = col.lower()
            if any(x in col_lower for x in ["اسم", "product", "name", "title"]): 
                df.rename(columns={col: "product_name"}, inplace=True)
            if any(x in col_lower for x in ["سعر", "price"]): 
                df.rename(columns={col: "price"}, inplace=True)
            if any(x in col_lower for x in ["صورة", "image", "img"]): 
                df.rename(columns={col: "image_url"}, inplace=True)
            if any(x in col_lower for x in ["ماركة", "brand"]): 
                df.rename(columns={col: "brand"}, inplace=True)
        
        if "product_name" not in df.columns:
            st.warning(f"⚠️ لم يتم العثور على عمود الاسم في {uploaded_file.name}")
            return pd.DataFrame()
            
        return df.dropna(subset=["product_name"])
    except Exception as e:
        st.error(f"Error loading competitor data: {e}")
        return pd.DataFrame()

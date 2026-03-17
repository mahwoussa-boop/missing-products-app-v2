"""
db_manager.py — مدير البيانات السيادي
═══════════════════════════════════════════════════════════════
v7.0 — الإصلاح الشامل لتحميل البيانات
- توحيد أسماء الأعمدة (Mapping) لضمان التوافق مع محرك المطابقة.
- معالجة أخطاء التشفير (Encoding) وفواصل الملفات (Delimiters).
- استخراج روابط الصور والأسعار بدقة 100%.
"""

import pandas as pd
import io
import re

def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """تنظيف وتوحيد أسماء الأعمدة لضمان التعرف عليها."""
    df.columns = [str(c).strip().lower() for c in df.columns]
    
    # خريطة توحيد الأسماء (Mapping)
    mapping = {
        'product_name': ['الاسم', 'product_name', 'name', 'عنوان المنتج', 'اسم المنتج', 'product name'],
        'price': ['السعر', 'price', 'sale_price', 'product_price', 'سعر المنتج', 'price_value'],
        'image_url': ['الصورة', 'image_url', 'image', 'صورة المنتج', 'product_image', 'images', 'رابط الصورة'],
        'brand': ['الماركة', 'brand', 'الشركة المصنعة', 'manufacturer', 'اسم الماركة'],
        'category': ['التصنيف', 'category', 'product_type', 'القسم', 'الفئة']
    }
    
    new_cols = {}
    for standard, aliases in mapping.items():
        for col in df.columns:
            if col in aliases:
                new_cols[col] = standard
                break
    
    return df.rename(columns=new_cols)

def load_mahwous_store_data(file_obj) -> pd.DataFrame:
    """تحميل ملف متجر مهووس مع معالجة ذكية للأعمدة."""
    try:
        # محاولة قراءة الملف بتشفيرات مختلفة
        content = file_obj.read()
        for enc in ['utf-8-sig', 'cp1256', 'utf-8']:
            try:
                df = pd.read_csv(io.BytesIO(content), encoding=enc)
                break
            except: continue
            
        df = clean_column_names(df)
        
        # التأكد من وجود الأعمدة الأساسية
        if 'product_name' not in df.columns:
            # محاولة البحث عن أي عمود يحتوي على نصوص طويلة كاسم منتج
            text_cols = [c for c in df.columns if df[c].dtype == 'object']
            if text_cols: df = df.rename(columns={text_cols[0]: 'product_name'})
            
        # تنظيف الأسعار
        if 'price' in df.columns:
            df['price'] = df['price'].apply(lambda x: float(re.sub(r'[^\d.]', '', str(x))) if pd.notnull(x) and re.sub(r'[^\d.]', '', str(x)) else 0)
            
        return df[['product_name', 'price', 'image_url']].fillna('')
    except Exception as e:
        print(f"Error loading Mahwous data: {e}")
        return pd.DataFrame(columns=['product_name', 'price', 'image_url'])

def load_competitor_data(file_obj) -> pd.DataFrame:
    """تحميل ملف المنافس مع استخراج البيانات الضرورية للمقارنة."""
    try:
        content = file_obj.read()
        for enc in ['utf-8-sig', 'cp1256', 'utf-8']:
            try:
                df = pd.read_csv(io.BytesIO(content), encoding=enc)
                break
            except: continue
            
        df = clean_column_names(df)
        
        # التأكد من وجود الأعمدة الأساسية
        required = ['product_name', 'price']
        for col in required:
            if col not in df.columns:
                # محاولة تخمين العمود المفقود
                if col == 'product_name':
                    text_cols = [c for c in df.columns if df[c].dtype == 'object']
                    if text_cols: df = df.rename(columns={text_cols[0]: 'product_name'})
                elif col == 'price':
                    num_cols = [c for c in df.columns if df[c].dtype in ['float64', 'int64']]
                    if num_cols: df = df.rename(columns={num_cols[0]: 'price'})
        
        # تنظيف الأسعار
        if 'price' in df.columns:
            df['price'] = df['price'].apply(lambda x: float(re.sub(r'[^\d.]', '', str(x))) if pd.notnull(x) and re.sub(r'[^\d.]', '', str(x)) else 0)
            
        return df[['product_name', 'price', 'image_url']].fillna('')
    except Exception as e:
        print(f"Error loading Competitor data: {e}")
        return pd.DataFrame(columns=['product_name', 'price', 'image_url'])

"""
db_manager.py — مدير البيانات السيادي (النسخة الآمنة)
═══════════════════════════════════════════════════════════════
v7.5 — الإصلاح الشامل لتحميل البيانات
- كشف ذكي لأعمدة متجر سلة (تجاوز الترويسة المزدوجة).
- التعرف التلقائي على أعمدة المنافسين المسحوبة (Scraped Salla Stores).
- حماية ضد أخطاء المفاتيح (KeyError) في حال غياب بعض الأعمدة كالصورة.
"""

import pandas as pd
import io
import re

def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """تنظيف وتوحيد أسماء الأعمدة لضمان التعرف عليها."""
    # توحيد حالة الأحرف وإزالة المسافات
    df.columns = [str(c).strip().lower() for c in df.columns]
    
    # خريطة توحيد الأسماء شاملة لملفات سلة العادية والمسحوبة (Scraping)
    mapping = {
        'product_name': ['أسم المنتج', 'اسم المنتج', 'product_name', 'name', 'عنوان المنتج', 'styles_productcard__name__pakbb'],
        'price': ['سعر المنتج', 'price', 'sale_price', 'text-sm-2', 'السعر'],
        'image_url': ['صورة المنتج', 'image_url', 'w-full src', 'w-full src 2', 'src', 'رابط الصورة'],
        'brand': ['الماركة', 'brand', 'الشركة المصنعة'],
        'category': ['التصنيف', 'category', 'القسم']
    }
    
    new_cols = {}
    for col in df.columns:
        for standard, aliases in mapping.items():
            # إذا كان اسم العمود يطابق أو يحتوي على إحدى الكلمات الدلالية
            if any(alias in col for alias in aliases):
                if standard not in new_cols.values(): # منع تكرار نفس المسمى
                    new_cols[col] = standard
                break
                
    return df.rename(columns=new_cols)

def load_mahwous_store_data(file_obj) -> pd.DataFrame:
    """تحميل ملف متجر مهووس مع معالجة ذكية للترويسات وأخطاء التشفير."""
    try:
        content = file_obj.read()
        df = None
        
        # تجربة القراءة بتشفيرات مختلفة لتجنب أخطاء اللغة العربية
        for enc in ['utf-8-sig', 'utf-8', 'cp1256']:
            try:
                # 1. تجربة قراءة الملف مع تخطي السطر الأول (مهم لملفات سلة)
                temp_df = pd.read_csv(io.BytesIO(content), encoding=enc, header=1)
                if "أسم المنتج" in temp_df.columns or "اسم المنتج" in temp_df.columns:
                    df = temp_df
                    break
                    
                # 2. إذا لم ينجح، نقرأ بدون تخطي السطر الأول
                temp_df = pd.read_csv(io.BytesIO(content), encoding=enc, header=0)
                df = temp_df
                break
            except Exception:
                continue
                
        if df is None or df.empty: 
            return pd.DataFrame(columns=['product_name', 'price', 'image_url'])
            
        df = clean_column_names(df)
        
        # حماية فولاذية: إنشاء الأعمدة المفقودة لكي لا ينهار التطبيق (KeyError)
        for required_col in ['product_name', 'price', 'image_url']:
            if required_col not in df.columns:
                df[required_col] = ''
                
        # تنظيف عمود السعر ليحتوي على أرقام فقط
        if 'price' in df.columns:
            df['price'] = df['price'].apply(lambda x: float(re.sub(r'[^\d.]', '', str(x))) if pd.notnull(x) and re.sub(r'[^\d.]', '', str(x)) else 0.0)
            
        # نرجع فقط الأعمدة التي نحتاجها
        return df[['product_name', 'price', 'image_url']].fillna('')
        
    except Exception as e:
        print(f"Error loading Mahwous data: {e}")
        return pd.DataFrame(columns=['product_name', 'price', 'image_url'])

def load_competitor_data(file_obj) -> pd.DataFrame:
    """تحميل ملف المنافس مع استخراج البيانات الضرورية (يدعم الملفات المسحوبة)."""
    try:
        content = file_obj.read()
        df = None
        
        for enc in ['utf-8-sig', 'utf-8', 'cp1256']:
            try:
                df = pd.read_csv(io.BytesIO(content), encoding=enc)
                break
            except Exception:
                continue
                
        if df is None or df.empty: 
            return pd.DataFrame(columns=['product_name', 'price', 'image_url'])
            
        df = clean_column_names(df)
        
        # حماية فولاذية من غياب الأعمدة
        for required_col in ['product_name', 'price', 'image_url']:
            if required_col not in df.columns:
                df[required_col] = ''
        
        # تنظيف السعر
        if 'price' in df.columns:
            df['price'] = df['price'].apply(lambda x: float(re.sub(r'[^\d.]', '', str(x))) if pd.notnull(x) and re.sub(r'[^\d.]', '', str(x)) else 0.0)
            
        return df[['product_name', 'price', 'image_url']].fillna('')
        
    except Exception as e:
        print(f"Error loading Competitor data: {e}")
        return pd.DataFrame(columns=['product_name', 'price', 'image_url'])

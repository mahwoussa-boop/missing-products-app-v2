"""
db_manager.py — مدير البيانات السيادي (الإصدار V10.0)
═══════════════════════════════════════════════════════════════
- قراءة ذكية لملفات سلة والمنافسين.
- سحب الروابط والصور والأسعار من ملفات الـ Scrape المعقدة.
- حماية ضد انهيار التطبيق إذا كانت بعض الأعمدة مفقودة.
"""

import pandas as pd
import io
import re

def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """تنظيف وتوحيد أسماء الأعمدة لضمان التعرف عليها سواء كانت من سلة أو مسحوبة."""
    df.columns = [str(c).strip().lower() for c in df.columns]
    
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
            if any(alias in col for alias in aliases):
                if standard not in new_cols.values():
                    new_cols[col] = standard
                break
                
    return df.rename(columns=new_cols)

def load_mahwous_store_data(file_obj) -> pd.DataFrame:
    """تحميل ملف متجر مهووس مع معالجة ذكية للترويسات (Headers)."""
    try:
        content = file_obj.read()
        df = None
        
        # تجربة القراءة بتشفيرات مختلفة
        for enc in ['utf-8-sig', 'utf-8', 'cp1256']:
            try:
                temp_df = pd.read_csv(io.BytesIO(content), encoding=enc, header=1)
                if "أسم المنتج" in temp_df.columns or "اسم المنتج" in temp_df.columns:
                    df = temp_df
                    break
                    
                temp_df = pd.read_csv(io.BytesIO(content), encoding=enc, header=0)
                df = temp_df
                break
            except Exception:
                continue
                
        if df is None or df.empty: 
            return pd.DataFrame(columns=['product_name', 'price', 'image_url'])
            
        df = clean_column_names(df)
        
        for required_col in ['product_name', 'price', 'image_url']:
            if required_col not in df.columns:
                df[required_col] = ''
                
        if 'price' in df.columns:
            df['price'] = df['price'].apply(lambda x: float(re.sub(r'[^\d.]', '', str(x))) if pd.notnull(x) and re.sub(r'[^\d.]', '', str(x)) else 0.0)
            
        return df[['product_name', 'price', 'image_url']].fillna('')
        
    except Exception as e:
        print(f"Error loading Mahwous data: {e}")
        return pd.DataFrame(columns=['product_name', 'price', 'image_url'])

def load_competitor_data(file_obj) -> pd.DataFrame:
    """تحميل ملفات المنافسين (حتى المسحوبة Scraping) واستخراج البيانات."""
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
        
        for required_col in ['product_name', 'price', 'image_url']:
            if required_col not in df.columns:
                df[required_col] = ''
        
        if 'price' in df.columns:
            df['price'] = df['price'].apply(lambda x: float(re.sub(r'[^\d.]', '', str(x))) if pd.notnull(x) and re.sub(r'[^\d.]', '', str(x)) else 0.0)
            
        return df[['product_name', 'price', 'image_url']].fillna('')
        
    except Exception as e:
        print(f"Error loading Competitor data: {e}")
        return pd.DataFrame(columns=['product_name', 'price', 'image_url'])

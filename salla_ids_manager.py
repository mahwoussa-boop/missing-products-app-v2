"""
salla_ids_manager.py - إدارة IDs التصنيفات والماركات من سلة
═══════════════════════════════════════════════════════════════
يحفظ ويقرأ IDs التصنيفات والماركات في ملف JSON محلي.
يُستخدم من صفحة الإعدادات في Streamlit ومن make_sender.py
"""

import json
import os
import csv

# مسار ملف الحفظ
IDS_FILE = os.path.join(os.path.dirname(__file__), 'salla_ids_data.json')

# ─── هيكل البيانات الافتراضي ───
DEFAULT_DATA = {
    "categories": {},   # {"اسم التصنيف": "ID رقمي"}
    "brands": {},       # {"اسم الماركة العربي": "ID رقمي"}
    "updated_at": ""
}

def load_ids() -> dict:
    """تحميل IDs المحفوظة من الملف"""
    if os.path.exists(IDS_FILE):
        try:
            with open(IDS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # ضمان وجود المفاتيح الأساسية
                if "categories" not in data: data["categories"] = {}
                if "brands" not in data: data["brands"] = {}
                return data
        except Exception:
            pass
    return DEFAULT_DATA.copy()

def save_ids(data: dict) -> bool:
    """حفظ IDs في الملف"""
    try:
        from datetime import datetime
        data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(IDS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"خطأ في الحفظ: {e}")
        return False

def get_category_id(category_name: str) -> str:
    """جلب ID التصنيف بالاسم - يرجع سلسلة فارغة إذا لم يوجد"""
    if not category_name:
        return ""
    data = load_ids()
    cats = data.get("categories", {})
    # بحث مباشر
    if category_name in cats:
        return str(cats[category_name])
    # بحث جزئي
    for name, id_ in cats.items():
        if category_name in name or name in category_name:
            return str(id_)
    return ""

def get_brand_id(brand_name: str) -> str:
    """جلب ID الماركة بالاسم - يرجع سلسلة فارغة إذا لم يوجد"""
    if not brand_name:
        return ""
    data = load_ids()
    brands = data.get("brands", {})
    # بحث مباشر
    if brand_name in brands:
        return str(brands[brand_name])
    # بحث جزئي
    for name, id_ in brands.items():
        if brand_name.lower() in name.lower() or name.lower() in brand_name.lower():
            return str(id_)
    return ""

def load_mahwous_categories_list() -> list:
    """تحميل قائمة أسماء التصنيفات من ملف CSV"""
    cats = []
    csv_paths = [
        '/home/ubuntu/upload/تصنيفاتمهووس.csv',
        os.path.join(os.path.dirname(__file__), '..', 'upload', 'تصنيفاتمهووس.csv'),
    ]
    for path in csv_paths:
        try:
            with open(path, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                for i, row in enumerate(reader):
                    if i == 0: continue
                    if row and row[0].strip():
                        cats.append(row[0].strip())
            break
        except Exception:
            continue
    return sorted(cats)

def load_mahwous_brands_list() -> list:
    """تحميل قائمة أسماء الماركات من ملف CSV"""
    brands = []
    csv_paths = [
        '/home/ubuntu/upload/ماركاتمهووس.csv',
        os.path.join(os.path.dirname(__file__), '..', 'upload', 'ماركاتمهووس.csv'),
    ]
    for path in csv_paths:
        try:
            with open(path, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                for i, row in enumerate(reader):
                    if i == 0: continue
                    if row and row[0].strip():
                        full = row[0].strip()
                        ar = full.split('|')[0].strip()
                        if ar:
                            brands.append(ar)
            break
        except Exception:
            continue
    return sorted(brands)

def get_stats() -> dict:
    """إحصائيات IDs المحفوظة"""
    data = load_ids()
    cats_with_id = {k: v for k, v in data.get("categories", {}).items() if v}
    brands_with_id = {k: v for k, v in data.get("brands", {}).items() if v}
    return {
        "categories_total": len(load_mahwous_categories_list()),
        "categories_saved": len(cats_with_id),
        "brands_total": len(load_mahwous_brands_list()),
        "brands_saved": len(brands_with_id),
        "updated_at": data.get("updated_at", "لم يتم الحفظ بعد")
    }

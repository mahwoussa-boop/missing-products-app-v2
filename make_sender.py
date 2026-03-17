"""make_sender.py v14.120 — مدير الإرسال الهجين الصارم (AI + Python)
═══════════════════════════════════════════════════════════════
- إصلاح وتشفير روابط الصور برمجياً (Python) لضمان توافق ميك وسلة 100%.
- دالة prepare_final_payload لضمان جودة الوصف والصور قبل الإرسال.
- معالجة الروابط التي تحتوي على حروف عربية أو رموز معقدة باستخدام urllib.parse.
"""

import requests
import os
import csv
import re
import urllib.parse
from typing import List, Dict, Any

# ─── تحميل قائمة تصنيفات مهووس المعتمدة (من ملف CSV) ───
def _load_mahwous_categories() -> list:
    """تحميل قائمة تصنيفات مهووس الكاملة من ملف تصنيفاتمهووس.csv"""
    cats = []
    csv_paths = [
        '/home/ubuntu/upload/تصنيفاتمهووس.csv',
        os.path.join(os.path.dirname(__file__), '..', 'upload', 'تصنيفاتمهووس.csv'),
    ]
    for path in csv_paths:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for i, row in enumerate(reader):
                    if i == 0: continue
                    if row and row[0].strip():
                        cats.append({
                            'name': row[0].strip(),
                            'parent': row[2].strip() if len(row) > 2 and row[2].strip() else '',
                        })
            break
        except Exception:
            continue
    return cats

MAHWOUS_CATEGORIES = _load_mahwous_categories()

def _smart_categorize(product_name: str, brand: str = '') -> list:
    """
    التصنيف الذكي للمنتج: يُحدد 1-3 تصنيفات مناسبة بناءً على اسم المنتج.
    القواعد:
    - تستر → عطور التستر + (رجالية/نسائية)
    - عطر رجالي → عطور رجالية + العطور
    - عطر نسائي → عطور نسائية + العطور
    - مجموعة/طقم → مجموعات وأطقم هدايا + (رجالية/نسائية)
    - بخور/عود → العود و البخور
    - مكياج → المكياج + الجمال و العناية
    - عناية → الجمال و العناية
    - جل/كريم/لوشن/بودر → للشعر والجسم
    - عينة/ميني → عطور عينات ميني
    - نيش → عطور النيش + (رجالية/نسائية)
    - أطفال → عطور الأطفال
    - بديل → بدائل العطور
    - فرموني → عطور فرمونية
    - افتراضي → العطور
    """
    name_lower = product_name.lower()
    cats = []

    # تحديد الجنس
    is_female = any(w in name_lower for w in ['نسائي', 'نسائية', 'women', 'woman', 'femme', 'pour femme', 'her', 'lady', 'ladies'])
    is_male   = any(w in name_lower for w in ['رجالي', 'رجالية', 'men', 'man', 'homme', 'pour homme', 'him', 'his'])

    # --- قواعد التصنيف الذكي ---
    if any(w in name_lower for w in ['تستر', 'tester']):
        cats.append('عطور التستر')
        if is_female: cats.append('عطور التستر نسائية')
        elif is_male: cats.append('عطور التستر رجالية')

    elif any(w in name_lower for w in ['مجموعة', 'طقم', 'set', 'gift', 'هدية', 'collection', 'pack']):
        cats.append('مجموعات وأطقم هدايا')
        if is_female: cats.append('مجموعات عطور نسائية')
        elif is_male: cats.append('مجموعات عطور رجالية')

    elif any(w in name_lower for w in ['عينة', 'ميني', 'sample', 'mini', 'travel']):
        cats.append('عطور عينات ميني')
        if is_female: cats.append('عينات عطور نسائية')
        elif is_male: cats.append('عينات عطور رجالية')

    elif any(w in name_lower for w in ['بخور', 'عود', 'oud', 'bakhour', 'bukhoor', 'incense', 'مبخرة']):
        cats.append('العود و البخور')
        if 'بخور' in name_lower or 'incense' in name_lower: cats.append('بخور فاخر')
        elif 'عود' in name_lower or 'oud' in name_lower: cats.append('عود طبيعي')

    elif any(w in name_lower for w in ['مكياج', 'ماسكارا', 'ريميل', 'احمر', 'كحل', 'makeup', 'mascara', 'lipstick', 'foundation', 'blush', 'contour']):
        cats.append('المكياج')
        cats.append('الجمال و العناية')

    elif any(w in name_lower for w in ['كريم', 'لوشن', 'بودر', 'بودرة', 'جل استحمام', 'شامبو', 'cream', 'lotion', 'powder', 'shower', 'shampoo', 'body']):
        cats.append('للشعر والجسم')
        if any(w in name_lower for w in ['جل', 'shower', 'body wash']): cats.append('عطور الجسم')
        elif any(w in name_lower for w in ['بودر', 'powder']): cats.append('بودراة الجسم')

    elif any(w in name_lower for w in ['نيش', 'niche']):
        cats.append('عطور النيش')
        if is_female: cats.append('عطور النيش نسائية')
        elif is_male: cats.append('عطور النيش رجالية')
        else: cats.append('عطور النيش للجنسين')

    elif any(w in name_lower for w in ['بديل', 'alternative', 'inspired']):
        cats.append('بدائل العطور')
        if is_female: cats.append('بدائل العطور نسائية')
        elif is_male: cats.append('بدائل العطور رجالية')

    elif any(w in name_lower for w in ['فرموني', 'pheromone', 'فيرومون']):
        cats.append('عطور فرمونية')
        if is_female: cats.append('عطور فرمونية نسائية')
        elif is_male: cats.append('عطور فرمونية رجالية')

    elif any(w in name_lower for w in ['اطفال', 'طفل', 'kids', 'children', 'baby', 'child']):
        cats.append('عطور الأطفال')

    elif any(w in name_lower for w in ['عناية', 'سيروم', 'serum', 'mask', 'قناع', 'تونر', 'toner']):
        cats.append('الجمال و العناية')
        cats.append('العناية')

    else:
        # عطر عام - تحديد الجنس
        cats.append('العطور')
        if is_female: cats.append('عطور نسائية')
        elif is_male: cats.append('عطور رجالية')

    # التحقق من وجود التصنيفات في قائمة مهووس المعتمدة
    valid_cat_names = {c['name'] for c in MAHWOUS_CATEGORIES}
    validated = [c for c in cats if c in valid_cat_names]
    # إذا لم يُطابق أي تصنيف، استخدم "العطور" كافتراضي
    if not validated:
        validated = ['العطور']
    # حد أقصى 3 تصنيفات
    return validated[:3]

# ─── تحميل قائمة ماركات مهووس المعتمدة (من ملف CSV) ───
def _load_mahwous_brands() -> dict:
    """تحميل قاموس الماركات: {اسم_إنجليزي_lowercase: اسم_عربي} من ملف ماركاتمهووس.csv"""
    brands = {}
    csv_paths = [
        os.path.join(os.path.dirname(__file__), '..', 'upload', 'ماركاتمهووس.csv'),
        '/home/ubuntu/upload/ماركاتمهووس.csv',
        os.path.join(os.path.dirname(__file__), 'ماركاتمهووس.csv'),
    ]
    for path in csv_paths:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for i, row in enumerate(reader):
                    if i == 0: continue
                    if row and row[0].strip():
                        full = row[0].strip()
                        parts = full.split('|')
                        ar = parts[0].strip()
                        en = parts[1].strip() if len(parts) > 1 else ''
                        if ar and en:
                            brands[en.lower()] = ar
                        elif ar:
                            brands[ar.lower()] = ar
            break
        except Exception:
            continue
    return brands

MAHWOUS_BRANDS = _load_mahwous_brands()

def _resolve_brand(brand_input: str) -> str:
    """
    البحث عن الماركة في قائمة مهووس المعتمدة.
    إذا لم تكن موجودة → إرجاع سلسلة فارغة (تجاهلها).
    """
    if not brand_input: return ''
    key = brand_input.strip().lower()
    # بحث مباشر
    if key in MAHWOUS_BRANDS:
        return MAHWOUS_BRANDS[key]
    # بحث جزئي (إذا كان الاسم الإنجليزي جزءاً من مفتاح الماركة)
    for k, v in MAHWOUS_BRANDS.items():
        if key in k or k in key:
            return v
    return ''

# رابط Webhook الخاص بسيناريو المنتجات المفقودة في Make
WEBHOOK_URL = os.environ.get(
    "WEBHOOK_NEW_PRODUCTS", 
    "https://hook.eu2.make.com/xvubj23dmpxu8qzilstd25cnumrwtdxm"
)

def _clean_url_for_make(url: str) -> str:
    """
    تنظيف وإصلاح روابط الصور برمجياً (Python) لضمان عملها في سلة و Make.
    تتعامل مع الروابط التي تحتوي على حروف عربية أو رموز معقدة.
    """
    if not url: return ""
    url = str(url).strip()
    
    # 1. إصلاح الروابط التي لا تحتوي على بروتوكول
    if url.startswith("//"): 
        url = "https:" + url
        
    try:
        # 2. فك التشفير أولاً لتجنب التشفير المزدوج
        url = urllib.parse.unquote(url)
        
        # 3. معالجة روابط CDN سلة (تحويل webp وتنظيف المسارات)
        if "cdn.salla.sa" in url:
            url = re.sub(r'/cdn-cgi/image/[^/]+/', '/', url)
            
        # 4. تحليل الرابط وإعادة تشفيره بشكل آمن (خصوصاً المسار الذي قد يحتوي على حروف عربية)
        parsed = urllib.parse.urlparse(url)
        # تشفير المسار (Path) فقط لأنه المكان الأكثر عرضة للحروف العربية والمسافات
        clean_path = urllib.parse.quote(parsed.path, safe="/%")
        # تشفير الاستعلام (Query) بشكل آمن
        clean_query = urllib.parse.quote(parsed.query, safe="=&%")
        
        clean_url = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, clean_path, parsed.params, clean_query, parsed.fragment))
        return clean_url
    except Exception:
        return url

def _build_seo_fields(name: str, brand: str, category: str = 'عطور') -> dict:
    """
    بناء حقول SEO الكاملة وفق معايير سلة:
    - عنوان صفحة المنتج (Page Title)
    - رابط صفحة المنتج (SEO Page URL)
    - وصف صفحة المنتج (Page Description)
    """
    # تنظيف الاسم من الأحرف الخاصة لبناء الـ Slug
    slug_name = re.sub(r'[^\u0600-\u06FFa-zA-Z0-9\s-]', '', name).strip()
    slug_name = re.sub(r'\s+', '-', slug_name).lower()
    slug_brand = re.sub(r'[^\u0600-\u06FFa-zA-Z0-9\s-]', '', brand).strip()
    slug_brand = re.sub(r'\s+', '-', slug_brand).lower()
    slug_cat = re.sub(r'[^\u0600-\u06FFa-zA-Z0-9\s-]', '', category).strip()
    slug_cat = re.sub(r'\s+', '-', slug_cat).lower()

    # Page Title: اسم المنتج : التصنيف : الماركة
    page_title = f"{name} : {category} : {brand}" if brand else f"{name} : {category}"

    # SEO Page URL: اسم-المنتج/تصنيف/ماركة (slug)
    if brand:
        seo_url = f"{slug_name}/{slug_cat}/{slug_brand}"
    else:
        seo_url = f"{slug_name}/{slug_cat}"

    # Page Description: وصف مختصر وفق معايير سلة (150-160 حرف)
    if brand:
        page_desc = f"اشتري {name} من {brand} بأفضل سعر في متجر مهووس للعطور الفاخرة. تسوق الآن وتمتع بتجربة عطرية استثنائية مع ضمان الأصالة والجودة."
    else:
        page_desc = f"اشتري {name} بأفضل سعر في متجر مهووس للعطور الفاخرة. تسوق الآن وتمتع بتجربة عطرية استثنائية مع ضمان الأصالة والجودة."

    # اقتصار الوصف على 160 حرف
    if len(page_desc) > 160:
        page_desc = page_desc[:157] + '...'

    return {
        'عنوان الصفحة': page_title,
        'رابط الصفحة SEO': seo_url,
        'وصف الصفحة': page_desc,
    }

def prepare_final_payload(p: Dict[str, Any]) -> Dict[str, Any]:
    """
    تجهيز الـ Payload النهائي للمنتج وضمان جودة الوصف والصور برمجياً.
    """
    name = str(p.get("product_name", p.get("name", ""))).strip()
    price = p.get("price", 0)
    brand_raw = str(p.get("brand", "")).strip()
    # ربط الماركة من قائمة مهووس المعتمدة فقط - تجاهل الماركات غير المعتمدة
    brand = _resolve_brand(brand_raw)
    
    try:
        price = float(price)
    except (ValueError, TypeError):
        price = 0.0

    # بناء حقول SEO
    seo = _build_seo_fields(name, brand)

    # التصنيف الذكي (1-3 تصنيفات حسب نوع المنتج)
    categories = _smart_categorize(name, brand_raw)

    # بناء الهيكلة الصارمة (المفاتيح العربية ثابتة لا تتغير)
    item = {
        "أسم المنتج": name,
        "سعر المنتج": price,
        "الوزن": 1,
        "سعر التكلفة": 0,
        "السعر المخفض": 0,
        "الماركة": brand,
        "اسم الماركة": brand_raw,
        "التصنيف": categories[0] if categories else 'العطور',
        "التصنيفات": categories,
        "الوصف": str(p.get("description", "")).strip(),
        "صورة المنتج": "",
        "صور إضافية": [],
        "عنوان الصفحة": seo["عنوان الصفحة"],
        "رابط الصفحة SEO": seo["رابط الصفحة SEO"],
        "وصف الصفحة": seo["وصف الصفحة"],
    }
    
    # 1. التحقق من الوصف (إذا كان فارغاً، يتم إنشاؤه برمجياً فوراً)
    if not item["الوصف"]:
        # حقن الروابط الثابتة لمهووس برمجياً في حال عدم توفر وصف
        item["الوصف"] = f"""
        <h2>{name}</h2>
        <p>اكتشف الفخامة مع <strong>{name}</strong> من {brand if brand else 'ماركة عالمية'}، متوفر الآن في متجر مهووس بسعر {price} ريال سعودي.</p>
        <p>لمشاهدة المزيد من <a href="https://mahwous.com/tags/perfumes">العطور الفاخرة</a> أو استكشاف <a href="https://mahwous.com/brands">أشهر الماركات</a>، تفضل بزيارة متجرنا.</p>
        """
    
    # 2. التحقق من الصور وإصلاحها برمجياً (Python URL Fix)
    # الأولوية: all_images > image_url > competitor_image (الصورة المباشرة من ملف المنافس)
    all_images = p.get("all_images", [])
    if not all_images and p.get("image_url"):
        all_images = [p.get("image_url")]
    if not all_images and p.get("competitor_image"):
        all_images = [p.get("competitor_image")]
        
    cleaned_images = []
    for img_url in all_images:
        if img_url:
            cleaned_images.append(_clean_url_for_make(str(img_url)))
    
    if cleaned_images:
        item["صورة المنتج"] = cleaned_images[0]
        if len(cleaned_images) > 1:
            item["صور إضافية"] = cleaned_images[1:]
    else:
        # صورة بديلة في حال عدم توفر أي صورة
        safe_name = urllib.parse.quote(name)
        item["صورة المنتج"] = f"https://ui-avatars.com/api/?name={safe_name}&background=random&size=512"

    return item

def send_products_to_make(products: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    إرسال المنتجات لـ Make بعد تجهيزها عبر prepare_final_payload.
    """
    if not products:
        return {"success": False, "message": "❌ لا توجد بيانات للإرسال"}

    formatted_products = []
    for p in products:
        item = prepare_final_payload(p)
        if item["أسم المنتج"] and item["سعر المنتج"] > 0:
            formatted_products.append(item)

    if not formatted_products:
        return {"success": False, "message": "❌ لم يتم العثور على منتجات صالحة للإرسال"}

    # إرسال كل منتج في طلب HTTP منفصل مغلف داخل {"data": [item]}
    # الـ Iterator في Make يبحث عن Array باسم "data" → كل طلب يحتوي على منتج واحد
    sent_count = 0
    failed_count = 0
    errors = []

    for item in formatted_products:
        try:
            # تغليف المنتج داخل مصفوفة data ليقرأها Iterator في Make
            payload_wrapped = {"data": [item]}
            response = requests.post(
                WEBHOOK_URL,
                json=payload_wrapped,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            if response.status_code in (200, 201, 204):
                sent_count += 1
            else:
                failed_count += 1
                errors.append(f"{item.get('أسم المنتج','؟')[:30]}: HTTP {response.status_code}")
        except Exception as e:
            failed_count += 1
            errors.append(f"{item.get('أسم المنتج','؟')[:30]}: {str(e)[:50]}")

    if sent_count > 0 and failed_count == 0:
        return {"success": True, "message": f"✅ تم إرسال {sent_count} منتج بنجاح لـ Make"}
    elif sent_count > 0:
        return {"success": True, "message": f"⚠️ تم إرسال {sent_count} منتج، فشل {failed_count}: {'; '.join(errors[:3])}"}
    else:
        return {"success": False, "message": f"❌ فشل إرسال جميع المنتجات: {'; '.join(errors[:3])}"}

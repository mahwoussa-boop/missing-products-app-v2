"""
make_sender.py - إرسال المنتجات إلى Make.com Webhook
═══════════════════════════════════════════════════════════════
- يرسل الحقول بالأسماء العربية المتوافقة مع Blueprint v5
- الحقول المرسلة: أسم المنتج، سعر المنتج، الوصف، صورة المنتج، إلخ
- يتعامل مع الصور وتنظيف الروابط برمجياً
- يبني وصف المنتج وفق أسلوب مهووس إذا كان فارغاً
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
    """
    name_lower = product_name.lower()
    cats = []

    # تحديد الجنس
    is_female = any(w in name_lower for w in ['نسائي', 'نسائية', 'women', 'woman', 'femme', 'pour femme', 'her', 'lady', 'ladies'])
    is_male   = any(w in name_lower for w in ['رجالي', 'رجالية', 'men', 'man', 'homme', 'pour homme', 'him', 'his'])

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
        cats.append('العطور')
        if is_female: cats.append('عطور نسائية')
        elif is_male: cats.append('عطور رجالية')

    # التحقق من وجود التصنيفات في قائمة مهووس المعتمدة
    valid_cat_names = {c['name'] for c in MAHWOUS_CATEGORIES}
    validated = [c for c in cats if c in valid_cat_names]
    if not validated:
        validated = ['العطور']
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
    if key in MAHWOUS_BRANDS:
        return MAHWOUS_BRANDS[key]
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
    تنظيف وإصلاح روابط الصور برمجياً لضمان عملها في سلة و Make.
    """
    if not url: return ""
    url = str(url).strip()
    
    if url.startswith("//"): 
        url = "https:" + url
        
    try:
        url = urllib.parse.unquote(url)
        
        if "cdn.salla.sa" in url:
            url = re.sub(r'/cdn-cgi/image/[^/]+/', '/', url)
            
        parsed = urllib.parse.urlparse(url)
        clean_path = urllib.parse.quote(parsed.path, safe="/%")
        clean_query = urllib.parse.quote(parsed.query, safe="=&%")
        
        clean_url = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, clean_path, parsed.params, clean_query, parsed.fragment))
        return clean_url
    except Exception:
        return url

def _build_seo_fields(name: str, brand: str, category: str = 'عطور') -> dict:
    """
    بناء حقول SEO الكاملة وفق معايير سلة.
    """
    if brand:
        page_title = f"{name} : {category} : {brand}"
        page_desc = f"اشتري {name} من {brand} بأفضل سعر في متجر مهووس للعطور الفاخرة. تسوق الآن وتمتع بتجربة عطرية استثنائية مع ضمان الأصالة والجودة."
    else:
        page_title = f"{name} : {category}"
        page_desc = f"اشتري {name} بأفضل سعر في متجر مهووس للعطور الفاخرة. تسوق الآن وتمتع بتجربة عطرية استثنائية مع ضمان الأصالة والجودة."

    if len(page_desc) > 160:
        page_desc = page_desc[:157] + '...'

    return {
        'عنوان الصفحة': page_title,
        'وصف الصفحة': page_desc,
    }

def _build_description(name: str, brand: str, price: float) -> str:
    """
    بناء وصف المنتج وفق أسلوب مهووس.
    """
    brand_text = brand if brand else 'ماركة عالمية'
    desc = f"""<h2>{name}</h2>
<p>اكتشف الفخامة مع <strong>{name}</strong> من <strong>{brand_text}</strong>، متوفر الآن في متجر مهووس بسعر <strong>{int(price)} ريال سعودي</strong>.</p>
<p>يتميز هذا العطر بتركيبة فريدة تجمع بين الأناقة والجودة العالية، ليمنحك تجربة عطرية لا تُنسى طوال اليوم.</p>
<p>لمشاهدة المزيد من <a href="https://mahwous.com/tags/perfumes">العطور الفاخرة</a> أو استكشاف <a href="https://mahwous.com/brands">أشهر الماركات</a>، تفضل بزيارة متجرنا.</p>"""
    return desc

def prepare_final_payload(p: Dict[str, Any]) -> Dict[str, Any]:
    """
    تجهيز الـ Payload النهائي للمنتج.
    يرسل الحقول بالأسماء العربية المتوافقة مع Blueprint v8.
    يستخدم IDs التصنيفات والماركات المحفوظة في salla_ids_manager.
    """
    # استيراد مدير IDs سلة
    try:
        from salla_ids_manager import get_category_id, get_brand_id
        _ids_manager_available = True
    except ImportError:
        _ids_manager_available = False
        def get_category_id(x): return ""
        def get_brand_id(x): return ""

    # استخراج البيانات الأساسية
    name = str(p.get("product_name", p.get("name", ""))).strip()
    brand_raw = str(p.get("brand", "")).strip()
    brand = _resolve_brand(brand_raw)
    
    try:
        price = float(p.get("price", 0))
    except (ValueError, TypeError):
        price = 0.0

    # التصنيف الذكي
    categories = _smart_categorize(name, brand_raw)
    category_name = categories[0] if categories else 'العطور'

    # ─── جلب IDs التصنيفات والماركات من قاعدة البيانات المحلية ───
    category_id = get_category_id(category_name)
    brand_id = get_brand_id(brand) if brand else ""

    # بناء حقول SEO
    seo = _build_seo_fields(name, brand, category_name)

    # الوصف
    description = str(p.get("description", "")).strip()
    if not description:
        description = _build_description(name, brand, price)

    # ─── بناء الـ Payload بالأسماء العربية المتوافقة مع Blueprint v8 ───
    item = {
        # الحقول الأساسية (عربية - تتوافق مع Blueprint v8 mapper)
        "أسم المنتج": name,
        "سعر المنتج": price,
        "الوصف": description,
        "رمز المنتج sku": str(p.get("sku", "")).strip(),
        "الوزن": 1,
        "سعر التكلفة": 0,
        "السعر المخفض": 0,
        # الصورة (ستُملأ لاحقاً)
        "صورة المنتج": "",
        # SEO
        "metadata_title": seo["عنوان الصفحة"],
        "metadata_description": seo["وصف الصفحة"],
        # التصنيف: ID رقمي إذا متوفر، وإلا الاسم كنص
        "category_id": category_id,
        "category_name": category_name,
        # الماركة: ID رقمي إذا متوفر، وإلا الاسم كنص
        "brand_id": brand_id,
        "brand_name": brand if brand else "",
        # حقل مرجعي
        "product_id": str(p.get("product_id", "")).strip(),
    }

    # ─── معالجة الصور ───
    all_images = p.get("all_images", [])
    if not all_images and p.get("image_url"):
        all_images = [p.get("image_url")]
    if not all_images and p.get("competitor_image"):
        all_images = [p.get("competitor_image")]
        
    cleaned_images = []
    for img_url in all_images:
        if img_url:
            cleaned = _clean_url_for_make(str(img_url))
            if cleaned:
                cleaned_images.append(cleaned)
    
    if cleaned_images:
        item["صورة المنتج"] = cleaned_images[0]
    else:
        # صورة بديلة إذا لم تتوفر أي صورة
        safe_name = urllib.parse.quote(name)
        item["صورة المنتج"] = f"https://ui-avatars.com/api/?name={safe_name}&background=random&size=512"

    return item

def send_products_to_make(products: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    إرسال المنتجات لـ Make بعد تجهيزها عبر prepare_final_payload.
    كل منتج يُرسل في طلب HTTP منفصل مغلف داخل {"data": [item]}
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

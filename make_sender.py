"""
make_sender.py v14.10 — مدير الإرسال الهجين الصارم (AI + Python)
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

    # بناء الهيكلة الصارمة (المفاتيح العربية ثابتة لا تتغير)
    item = {
        "أسم المنتج": name,
        "سعر المنتج": price,
        "الوزن": 1,
        "سعر التكلفة": 0,
        "السعر المخفض": 0,
        "الماركة": brand,
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

    payload = {"data": formatted_products}

    try:
        response = requests.post(
            WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code in (200, 201, 204):
            return {"success": True, "message": f"✅ تم إرسال {len(formatted_products)} منتج بنجاح لـ Make"}
        else:
            return {"success": False, "message": f"❌ خطأ من Make ({response.status_code})"}
            
    except Exception as e:
        return {"success": False, "message": f"❌ خطأ في الاتصال: {str(e)[:100]}"}

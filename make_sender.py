"""
make_sender.py v14.7 — مدير الإرسال الهجين الصارم (AI + Python)
═══════════════════════════════════════════════════════════════
- إصلاح وتشفير روابط الصور برمجياً (Python) لضمان توافق ميك وسلة 100%.
- دالة prepare_final_payload لضمان جودة الوصف والصور قبل الإرسال.
- معالجة الروابط التي تحتوي على حروف عربية أو رموز معقدة باستخدام urllib.parse.
"""

import requests
import os
import urllib.parse
import re
from typing import List, Dict, Any

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

def prepare_final_payload(p: Dict[str, Any]) -> Dict[str, Any]:
    """
    تجهيز الـ Payload النهائي للمنتج وضمان جودة الوصف والصور برمجياً.
    """
    name = str(p.get("product_name", p.get("name", ""))).strip()
    price = p.get("price", 0)
    brand = str(p.get("brand", "")).strip()
    
    try:
        price = float(price)
    except (ValueError, TypeError):
        price = 0.0

    # بناء الهيكلة الصارمة
    item = {
        "أسم المنتج": name,
        "سعر المنتج": price,
        "الوزن": 1,
        "سعر التكلفة": 0,
        "السعر المخفض": 0,
        "الوصف": str(p.get("description", "")).strip(),
        "صورة المنتج": "",
        "صور إضافية": []
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
    all_images = p.get("all_images", [])
    if not all_images and p.get("image_url"):
        all_images = [p.get("image_url")]
        
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

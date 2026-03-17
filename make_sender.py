"""
make_sender.py v14.1 — مدير الإرسال لأتمتة Make.com (دعم الصور المتعددة والوصف المطول)
═══════════════════════════════════════════════════════════════
- معالجة وتشفير روابط صور المنافسين بذكاء (فك التشفير ثم إعادة التشفير) لكي تقبلها سلة و Make.
- تثبيت هيكلة الـ JSON لضمان إرسال "الوصف" بتنسيق مهووس دائماً.
- دعم إرسال مصفوفة من الصور ("صور إضافية") لضمان سحب جميع صور المنتج.
- توفير صورة بديلة (Placeholder) في حال فشل سحب الصورة لكي لا يتوقف السيناريو.
- الحفاظ على المفاتيح العربية المتوافقة مع سيناريو متجر مهووس ("أسم المنتج", "الوصف", "صورة المنتج").
"""

import requests
import os
import urllib.parse
from typing import List, Dict, Any

# رابط Webhook الخاص بسيناريو المنتجات المفقودة في Make
WEBHOOK_URL = os.environ.get(
    "WEBHOOK_NEW_PRODUCTS", 
    "https://hook.eu2.make.com/xvubj23dmpxu8qzilstd25cnumrwtdxm"
)

def _clean_url_for_make(url: str) -> str:
    """
    تنظيف وتشفير روابط الصور القادمة من المنافسين أو الويب.
    يمنع "التشفير المزدوج" الذي يكسر روابط CDN الخاصة بسلة وغيرها.
    """
    if not url: return ""
    url = str(url).strip()
    
    # إصلاح الروابط التي لا تحتوي على بروتوكول
    if url.startswith("//"): 
        url = "https:" + url
        
    try:
        # 1. فك التشفير أولاً لتجنب التشفير المزدوج
        url = urllib.parse.unquote(url)
        # 2. تحليل الرابط
        parsed = urllib.parse.urlparse(url)
        # 3. إعادة التشفير الآمن للمسار والاستعلام فقط
        clean_path = urllib.parse.quote(parsed.path, safe="/%")
        clean_query = urllib.parse.quote_plus(parsed.query, safe="=&")
        
        clean_url = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, clean_path, parsed.params, clean_query, parsed.fragment))
        return clean_url
    except Exception:
        return url

def send_products_to_make(products: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    إرسال المنتجات المفقودة لإضافتها في سلة عبر Make.
    مع ضمان إرفاق الوصف والصور المتعددة وتجاوز أخطاء الروابط.
    """
    if not products:
        return {"success": False, "message": "❌ لا توجد بيانات للإرسال"}

    formatted_products = []
    
    for p in products:
        # استخراج البيانات الأساسية
        name = str(p.get("product_name", p.get("name", ""))).strip()
        price = p.get("price", 0)
        
        try:
            price = float(price)
        except (ValueError, TypeError):
            price = 0.0

        if not name or price <= 0:
            continue

        # ── بناء الهيكلة الصارمة التي يطلبها سيناريو Make ──
        item = {
            "أسم المنتج": name,
            "سعر المنتج": price,
            "الوزن": 1,
            "سعر التكلفة": 0,
            "السعر المخفض": 0,
            "الوصف": "",
            "صورة المنتج": "",
            "صور إضافية": [] # دعم الصور المتعددة
        }
        
        # 1. إضافة الوصف (تم توليده مسبقاً من الذكاء الاصطناعي بتنسيق مهووس المطول)
        description = str(p.get("description", "")).strip()
        if description:
            item["الوصف"] = description
        else:
            item["الوصف"] = f"<h2>{name}</h2><p>اكتشف الفخامة مع هذا المنتج الرائع، متوفر الآن في متجر مهووس.</p>"
            
        # 2. إضافة الصور ومعالجتها
        # نحاول الحصول على قائمة الصور أولاً
        all_images = p.get("all_images", [])
        if not all_images and p.get("image_url"):
            all_images = [p.get("image_url")]
            
        cleaned_images = []
        for img_url in all_images:
            if img_url and str(img_url).startswith("http"):
                cleaned_images.append(_clean_url_for_make(str(img_url)))
        
        if cleaned_images:
            item["صورة المنتج"] = cleaned_images[0]
            if len(cleaned_images) > 1:
                item["صور إضافية"] = cleaned_images[1:]
        else:
            # حماية السناريو: صورة بديلة لتجنب تعطل Make
            safe_name = urllib.parse.quote(name)
            item["صورة المنتج"] = f"https://ui-avatars.com/api/?name={safe_name}&background=random&size=512"

        formatted_products.append(item)

    if not formatted_products:
        return {"success": False, "message": "❌ لم يتم العثور على منتجات صالحة للإرسال"}

    # ── تغليف البيانات في مفتاح "data" كما يقرأها السيناريو في Make ──
    payload = {"data": formatted_products}

    try:
        response = requests.post(
            WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30 # زيادة المهلة للوصف الطويل والصور المتعددة
        )
        
        if response.status_code in (200, 201, 204):
            return {"success": True, "message": f"✅ تم إرسال {len(formatted_products)} منتج بنجاح لـ Make متضمناً الوصف والصور"}
        else:
            return {"success": False, "message": f"❌ خطأ من Make ({response.status_code}): يرجى فحص السيناريو"}
            
    except requests.exceptions.Timeout:
        return {"success": False, "message": "❌ انتهت مهلة الاتصال بخادم Make، قد يكون الوصف طويلاً جداً."}
    except Exception as e:
        return {"success": False, "message": f"❌ خطأ في الاتصال: {str(e)[:100]}"}

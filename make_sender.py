"""
make_sender.py v14.0 — مدير الإرسال لأتمتة Make.com (مضاد للتعطل والتشفير المزدوج)
═══════════════════════════════════════════════════════════════
- معالجة وتشفير روابط صور المنافسين بذكاء (فك التشفير ثم إعادة التشفير) لكي تقبلها سلة و Make.
- تثبيت هيكلة الـ JSON لضمان إرسال "الوصف" بتنسيق مهووس دائماً.
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
    "https://hook.eu2.make.com/xvubj23dmpxu8qzilstd25cnumrwtdxm" # تأكد من أن هذا الرابط هو الصحيح لسيناريو مهووس
)

def _clean_url_for_make(url: str) -> str:
    """
    تنظيف وتشفير روابط الصور القادمة من المنافسين.
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
    مع ضمان إرفاق الوصف والصورة وتجاوز أخطاء الروابط.
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
        # نضع المفاتيح بشكل ثابت لكي لا يختل السيناريو في Make
        item = {
            "أسم المنتج": name,
            "سعر المنتج": price,
            "الوزن": 1,
            "سعر التكلفة": 0,
            "السعر المخفض": 0,
            "الوصف": "",
            "صورة المنتج": ""
        }
        
        # 1. إضافة الوصف (تم توليده مسبقاً من الذكاء الاصطناعي بتنسيق مهووس)
        description = str(p.get("description", "")).strip()
        if description:
            item["الوصف"] = description
        else:
            # حماية: وصف افتراضي إذا تعطل الذكاء الاصطناعي لكي لا يرسل قيمة فارغة تماماً
            item["الوصف"] = f"<h2>{name}</h2><p>اكتشف الفخامة مع هذا المنتج الرائع، متوفر الآن في متجر مهووس.</p>"
            
        # 2. إضافة الصورة (سواء مسحوبة من المنافس أو من الإنترنت) ومعالجتها
        image_url = str(p.get("image_url", "")).strip()
        if image_url and image_url.startswith("http"):
            item["صورة المنتج"] = _clean_url_for_make(image_url)
        else:
            # حماية السناريو: إذا لم تتوفر صورة نهائياً، نرسل صورة بديلة لتجنب تعطل Make
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
            timeout=25 # زيادة المهلة لـ 25 ثانية لضمان رفع الصور والوصف الطويل
        )
        
        if response.status_code in (200, 201, 204):
            return {"success": True, "message": f"✅ تم إرسال {len(formatted_products)} منتج بنجاح لـ Make متضمناً الوصف والصور"}
        else:
            return {"success": False, "message": f"❌ خطأ من Make ({response.status_code}): يرجى فحص السيناريو"}
            
    except requests.exceptions.Timeout:
        return {"success": False, "message": "❌ انتهت مهلة الاتصال بخادم Make، قد يكون الوصف طويلاً جداً."}
    except requests.exceptions.ConnectionError:
        return {"success": False, "message": "❌ فشل الاتصال بالخادم. يرجى التحقق من اتصال الإنترنت."}
    except Exception as e:
        return {"success": False, "message": f"❌ خطأ في الاتصال: {str(e)[:100]}"}

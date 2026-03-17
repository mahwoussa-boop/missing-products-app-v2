"""
make_sender.py v14.2 — مدير الإرسال لأتمتة Make.com (إصلاح الصور برمجياً + دعم النظام الهجين)
═══════════════════════════════════════════════════════════════
- إصلاح روابط الصور برمجياً (Python) لتحويل صيغ webp المعقدة وتجاوز قيود CDN سلة.
- دعم إرسال الصور والوصف سواء تم توليدها بالذكاء الاصطناعي أو بالبرمجة المباشرة.
- ضمان التوافق التام مع سيناريو Make ومنصة سلة لمنع توقف الأتمتة.
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
    تتعامل مع روابط CDN سلة المعقدة وصيغ webp وتمنع التشفير المزدوج.
    """
    if not url: return ""
    url = str(url).strip()
    
    # 1. إصلاح الروابط التي لا تحتوي على بروتوكول
    if url.startswith("//"): 
        url = "https:" + url
        
    try:
        # 2. فك التشفير أولاً لتجنب التشفير المزدوج
        url = urllib.parse.unquote(url)
        
        # 3. معالجة روابط CDN سلة (تحويل webp إلى jpg إذا لزم الأمر أو تنظيف البارامترات)
        # روابط سلة غالباً تحتوي على معالجة صور مثل: /fit=scale-down,format=webp/
        if "cdn.salla.sa" in url:
            # إزالة معالجات الصور التي قد تسبب مشاكل في بعض المتصفحات أو المنصات
            # نحتفظ بالرابط الأصلي للصورة قدر الإمكان
            url = re.sub(r'/cdn-cgi/image/[^/]+/', '/', url)
            
        # 4. تحليل الرابط وإعادة تشفيره بشكل آمن
        parsed = urllib.parse.urlparse(url)
        clean_path = urllib.parse.quote(parsed.path, safe="/%")
        clean_query = urllib.parse.quote_plus(parsed.query, safe="=&")
        
        clean_url = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, clean_path, parsed.params, clean_query, parsed.fragment))
        return clean_url
    except Exception:
        return url

def send_products_to_make(products: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    إرسال المنتجات لـ Make مع ضمان جودة البيانات (الصور والوصف) برمجياً.
    """
    if not products:
        return {"success": False, "message": "❌ لا توجد بيانات للإرسال"}

    formatted_products = []
    
    for p in products:
        name = str(p.get("product_name", p.get("name", ""))).strip()
        price = p.get("price", 0)
        
        try:
            price = float(price)
        except (ValueError, TypeError):
            price = 0.0

        if not name or price <= 0:
            continue

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
        
        # حماية الوصف
        if not item["الوصف"]:
            item["الوصف"] = f"<h2>{name}</h2><p>اكتشف الفخامة مع هذا المنتج الرائع، متوفر الآن في متجر مهووس.</p>"
            
        # معالجة الصور برمجياً
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
                item["صور إاضافية"] = cleaned_images[1:]
        else:
            safe_name = urllib.parse.quote(name)
            item["صورة المنتج"] = f"https://ui-avatars.com/api/?name={safe_name}&background=random&size=512"

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

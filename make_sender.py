"""
make_sender.py v13.1 — مدير الإرسال لأتمتة Make.com (مستعاد ومحسن)
═══════════════════════════════════════════════════════════════
- تم استعادة الكود الأصلي بالكامل لضمان توافق هيكلة {"data": [...]} مع سيناريو مهووس.
- الحفاظ على المفاتيح العربية ("أسم المنتج"، "سعر المنتج"، "الوصف"، "صورة المنتج").
- يتضمن نظام التقاط الأخطاء (Try/Except) ليعرض سبب العطل للمستخدم بدلاً من توقف التطبيق.
"""

import requests
import os
from typing import List, Dict, Any

# رابط Webhook الخاص بسيناريو المنتجات المفقودة في Make
WEBHOOK_URL = os.environ.get(
    "WEBHOOK_NEW_PRODUCTS", 
    "https://hook.eu2.make.com/xvubj23dmpxu8qzilstd25cnumrwtdxm" # تأكد من أن هذا الرابط هو الصحيح لسيناريو مهووس
)

def send_products_to_make(products: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    إرسال المنتجات المفقودة لإضافتها في سلة عبر Make.
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
            "السعر المخفض": 0
        }
        
        # 1. إضافة الوصف (يتم توليده بتنسيق مهووس من app.py قبل الإرسال)
        description = str(p.get("description", "")).strip()
        if description:
            item["الوصف"] = description
            
        # 2. إضافة الصورة (يتم سحبها من المنافس أو الإنترنت في app.py)
        image_url = str(p.get("image_url", "")).strip()
        if image_url and image_url.startswith("http"):
            item["صورة المنتج"] = image_url

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
            timeout=20
        )
        
        if response.status_code in (200, 201, 204):
            return {"success": True, "message": f"✅ تم إرسال {len(formatted_products)} منتج بنجاح لـ Make"}
        else:
            return {"success": False, "message": f"❌ خطأ من Make ({response.status_code}): يرجى فحص السيناريو"}
            
    except requests.exceptions.Timeout:
        return {"success": False, "message": "❌ انتهت مهلة الاتصال بخادم Make"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "message": "❌ فشل الاتصال بالخادم. يرجى التحقق من اتصال الإنترنت."}
    except Exception as e:
        return {"success": False, "message": f"❌ خطأ في الاتصال: {str(e)[:100]}"}

"""
make_sender.py v2.0 — إرسال آمن إلى Make.com
══════════════════════════════════════════════════
⚠️ القاعدة الحرجة: بنية الـ Payload ثابتة ولا تتغير أبداً!
{"data": [{"أسم المنتج":"...","سعر المنتج":...,...}]}
"""

import time
import requests
import streamlit as st
from typing import List, Dict, Any
from config import WEBHOOK_NEW_PRODUCTS


def _safe_float(val, default: float = 0.0) -> float:
    """تحويل آمن إلى float."""
    try:
        if val is None or str(val).strip() in ("", "nan", "None", "NaN"):
            return default
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_str(val, default: str = "") -> str:
    """تحويل آمن إلى string."""
    if val is None:
        return default
    s = str(val).strip()
    if s in ("nan", "None", "NaN"):
        return default
    return s


def build_payload(product: Dict) -> Dict:
    """
    بناء الـ Payload بالبنية الإلزامية الثابتة.
    ⚠️ لا تُغيّر أسماء المفاتيح العربية — Make.com يعتمد عليها!
    """
    return {
        "data": [{
            "أسم المنتج":      _safe_str(product.get("product_name", "")),
            "سعر المنتج":      _safe_float(product.get("price", 0)),
            "رمز المنتج sku":  _safe_str(product.get("sku", "")),
            "الوزن":           1,
            "سعر التكلفة":     0.0,
            "السعر المخفض":    0.0,
            "الوصف":           _safe_str(product.get("description", "")),
            "صورة المنتج":     _safe_str(product.get("image_url", "")),
        }]
    }


def send_products_to_make(
    products: List[Dict],
    delay: float = 0.3,
    webhook_url: str = "",
) -> Dict[str, Any]:
    """
    إرسال المنتجات إلى Make.com — كل منتج في طلب مستقل.
    
    ⚠️ لماذا كل منتج على حدة؟
    لأن سيناريو Make يستخدم BasicFeeder يقرأ {{1.data}}
    ويتوقع عنصراً واحداً في كل طلب.
    """
    url = webhook_url or WEBHOOK_NEW_PRODUCTS

    if not products:
        return {"success": False, "message": "❌ لا توجد منتجات محددة للإرسال.", "sent": 0, "failed": 0}

    if not url or "hook" not in url:
        return {"success": False, "message": "❌ رابط Webhook غير صحيح. تحقق من الإعدادات.", "sent": 0, "failed": 0}

    sent = 0
    failed = 0
    errors = []

    progress = st.progress(0, text="🚀 بدء الإرسال إلى Make.com...")

    for i, product in enumerate(products):
        name = _safe_str(product.get("product_name", "منتج"))
        payload = build_payload(product)

        try:
            resp = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=20,
            )
            if resp.status_code in (200, 201, 202, 204):
                sent += 1
            else:
                failed += 1
                errors.append(f"{name[:30]}: HTTP {resp.status_code}")
        except requests.exceptions.RequestException as e:
            failed += 1
            errors.append(f"{name[:30]}: {str(e)[:50]}")

        # تحديث شريط التقدم
        pct = (i + 1) / len(products)
        progress.progress(pct, text=f"📤 إرسال {i+1}/{len(products)}: {name[:40]}...")

        # تأخير بين الطلبات لحماية السيناريو
        if i < len(products) - 1:
            time.sleep(delay)

    progress.progress(1.0, text="✅ اكتمل الإرسال!")

    # رسالة النتيجة
    if sent == len(products):
        return {
            "success": True,
            "message": f"✅ نجاح! تم إرسال {sent} منتج إلى Make.com.",
            "sent": sent,
            "failed": 0,
        }
    else:
        err_summary = " | ".join(errors[:5])
        return {
            "success": failed == 0,
            "message": f"تم إرسال {sent} من {len(products)} منتج. فشل {failed}.\n{err_summary}",
            "sent": sent,
            "failed": failed,
        }


def verify_webhook() -> Dict:
    """فحص الاتصال بـ Webhook."""
    url = WEBHOOK_NEW_PRODUCTS
    if not url:
        return {"success": False, "message": "❌ رابط Webhook غير محدد"}

    test_payload = {
        "data": [{
            "أسم المنتج": "اختبار اتصال",
            "سعر المنتج": 0.0,
            "رمز المنتج sku": "TEST-000",
            "الوزن": 1,
            "سعر التكلفة": 0.0,
            "السعر المخفض": 0.0,
            "الوصف": "هذا اختبار اتصال فقط",
            "صورة المنتج": "",
        }]
    }

    try:
        resp = requests.post(url, json=test_payload, timeout=10)
        if resp.status_code in (200, 201, 202, 204):
            return {"success": True, "message": f"✅ الاتصال ناجح ({resp.status_code})"}
        return {"success": False, "message": f"❌ HTTP {resp.status_code}: {resp.text[:100]}"}
    except Exception as e:
        return {"success": False, "message": f"❌ فشل الاتصال: {str(e)[:80]}"}

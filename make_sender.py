"""
make_sender.py v3.0 — إرسال آمن وغير متزامن إلى Make.com
══════════════════════════════════════════════════
الأولوية: الحفاظ على بنية Payload الثابتة وضمان السرعة عبر aiohttp.
"""

import asyncio
import aiohttp
import requests
import streamlit as st
from typing import List, Dict, Any
from config import WEBHOOK_NEW_PRODUCTS

def _safe_float(val, default: float = 0.0) -> float:
    try:
        if val is None or str(val).strip() in ("", "nan", "None", "NaN"):
            return default
        return float(val)
    except (ValueError, TypeError):
        return default

def _safe_str(val, default: str = "") -> str:
    if val is None:
        return default
    s = str(val).strip()
    if s in ("nan", "None", "NaN"):
        return default
    return s

def build_payload(product: Dict) -> Dict:
    """بناء الـ Payload بالبنية الإلزامية الثابتة لـ Make.com."""
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

async def send_single_product_async(session: aiohttp.ClientSession, url: str, product: Dict) -> bool:
    """إرسال منتج واحد بشكل غير متزامن."""
    payload = build_payload(product)
    try:
        async with session.post(url, json=payload, timeout=20) as resp:
            return resp.status in (200, 201, 202, 204)
    except Exception as e:
        print(f"Error sending product: {e}")
        return False

def send_products_to_make(products: List[Dict], webhook_url: str = "") -> Dict[str, Any]:
    """إرسال مجموعة منتجات إلى Make.com بشكل متزامن (wrapper لسهولة الاستخدام)."""
    url = webhook_url or WEBHOOK_NEW_PRODUCTS
    if not url or "hook" not in url:
        return {"success": False, "message": "❌ رابط Webhook غير صحيح.", "sent": 0, "failed": 0}
    
    sent = 0
    failed = 0
    
    # محاولة تشغيل حلقة الأحداث بشكل آمن
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    async def run_batch():
        nonlocal sent, failed
        async with aiohttp.ClientSession() as session:
            tasks = [send_single_product_async(session, url, p) for p in products]
            results = await asyncio.gather(*tasks)
            sent = sum(1 for r in results if r)
            failed = len(results) - sent

    if loop.is_running():
        # إذا كانت الحلقة تعمل بالفعل (كما في Streamlit)، نستخدم Thread لإرسال البيانات
        import threading
        def start_loop(loop):
            asyncio.set_event_loop(loop)
            loop.run_until_complete(run_batch())
        
        new_loop = asyncio.new_event_loop()
        t = threading.Thread(target=start_loop, args=(new_loop,))
        t.start()
        t.join()
    else:
        loop.run_until_complete(run_batch())
    
    return {
        "success": failed == 0,
        "message": f"تم إرسال {sent} من {len(products)} منتج.",
        "sent": sent,
        "failed": failed
    }

def verify_webhook() -> Dict:
    """فحص الاتصال بـ Webhook."""
    url = WEBHOOK_NEW_PRODUCTS
    if not url: return {"success": False, "message": "❌ رابط Webhook غير محدد"}
    
    try:
        resp = requests.post(url, json=build_payload({"product_name": "Test Connection"}), timeout=10)
        if resp.status_code in (200, 201, 202, 204):
            return {"success": True, "message": f"✅ الاتصال ناجح ({resp.status_code})"}
        return {"success": False, "message": f"❌ HTTP {resp.status_code}"}
    except Exception as e:
        return {"success": False, "message": f"❌ فشل الاتصال: {str(e)}"}

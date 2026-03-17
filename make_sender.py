"""
make_sender.py — مدير الإرسال لأتمتة Make.com
═══════════════════════════════════════════════════════════════
- تم تحديث الهيكلة لتطابق سيناريو "المنتجات المفقودة/الجديدة".
- إضافة دعم (صورة المنتج) و (الوصف) المولد بأسلوب متجر مهووس.
- إرسال البيانات داخل مصفوفة {"data": [...]} كما يطلبها السيناريو.
"""

import requests
import json
import os
from typing import List, Dict

# رابط Webhook الخاص بإضافة المنتجات الجديدة (المفقودة)
WEBHOOK_URL = os.environ.get(
    "WEBHOOK_NEW_PRODUCTS", 
    "https://hook.eu2.make.com/xvubj23dmpxu8qzilstd25cnumrwtdxm" # رابط افتراضي احتياطي
)

def send_products_to_make(products: List[Dict]) -> Dict:
    """
    إرسال المنتجات المفقودة لإضافتها في سلة عبر Make.
    """
    if not products:
        return {"success": False, "message": "❌ لا توجد بيانات للإرسال"}

    formatted_products = []
    
    for p in products:
        # استخراج البيانات بذكاء لتدعم مفاتيح مختلفة
        name = str(p.get("product_name", p.get("name", p.get("منتج_المنافس", "")))).strip()
        price = p.get("price", p.get("سعر_المنافس", 0))
        
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
        
        # إضافة الوصف إذا تم توليده عبر خبير مهووس
        description = str(p.get("description", p.get("الوصف", ""))).strip()
        if description:
            item["الوصف"] = description
            
        # إضافة رابط الصورة إذا تم جلبه
        image_url = str(p.get("image_url", p.get("صورة المنتج", ""))).strip()
        if image_url and image_url.startswith("http"):
            item["صورة المنتج"] = image_url

        formatted_products.append(item)

    if not formatted_products:
        return {"success": False, "message": "❌ لم يتم العثور على منتجات صالحة للإرسال"}

    # ── تغليف البيانات في مفتاح "data" كما يقرأها BasicFeeder في Make ──
    payload = {"data": formatted_products}

    try:
        response = requests.post(
            WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        
        if response.status_code in (200, 201, 204):
            return {"success": True, "message": f"✅ تم إرسال {len(formatted_products)} منتج إلى Make بنجاح"}
        else:
            return {"success": False, "message": f"❌ خطأ من Make ({response.status_code}): {response.text[:100]}"}
            
    except requests.exceptions.Timeout:
        return {"success": False, "message": "❌ انتهت مهلة الاتصال بالخادم (Timeout)"}
    except Exception as e:
        return {"success": False, "message": f"❌ خطأ في الاتصال: {str(e)[:100]}"}

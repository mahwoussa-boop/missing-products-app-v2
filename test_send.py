"""
test_send.py — سكريبت اختبار إرسال منتج تجريبي
═══════════════════════════════════════════════
يرسل منتج "طقم بلاك إنسينس مالاكي من شوبارد" كمنتج تجريبي كامل
مع صورة ووصف بتنسيق مهووس الكامل إلى Make.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))

from ai_engine import fetch_product_images, fetch_fragrantica_info, generate_mahwous_description
from make_sender import prepare_final_payload, send_products_to_make

# ─── بيانات المنتج التجريبي ───
PRODUCT = {
    "product_name": "طقم بلاك إنسينس مالاكي شوبارد أو دو بارفان 80 مل + جل استحمام 150 مل",
    "brand": "Chopard",
    "price": 299.0,
    "competitor_image": "https://cdn.salla.sa/form-builder/KVXmGnFCNHhWAHMXCfJSgMfHLBBNGVFHYGqFBrXK.jpg"
}

print("=" * 60)
print("🧪 اختبار إرسال منتج تجريبي - مهووس")
print("=" * 60)

# الخطوة 1: سحب الصور
print("\n📸 الخطوة 1: سحب صور المنتج...")
img_result = fetch_product_images(
    PRODUCT["product_name"],
    brand=PRODUCT["brand"],
    competitor_image=PRODUCT["competitor_image"]
)
images = img_result.get("images", [])
print(f"   ✅ عدد الصور المسحوبة: {len(images)}")
for i, img in enumerate(images):
    print(f"   [{i+1}] {img.get('source','')}: {img.get('url','')[:80]}...")

# الخطوة 2: سحب المكونات من Fragrantica
print("\n🌸 الخطوة 2: سحب المكونات الحقيقية...")
frag_data = fetch_fragrantica_info(PRODUCT["product_name"])
if frag_data.get("success"):
    print(f"   ✅ مقدمة: {frag_data.get('top_notes', [])}")
    print(f"   ✅ قلب: {frag_data.get('middle_notes', [])}")
    print(f"   ✅ قاعدة: {frag_data.get('base_notes', [])}")
else:
    print("   ⚠️  لم يتم سحب المكونات (سيتم استخدام الوصف الهيكلي)")

# الخطوة 3: توليد الوصف
print("\n📝 الخطوة 3: توليد الوصف بتنسيق مهووس...")
description = generate_mahwous_description(
    PRODUCT["product_name"],
    PRODUCT["price"],
    brand=PRODUCT["brand"],
    fragrantica_data=frag_data if frag_data.get("success") else None
)
print(f"   ✅ طول الوصف: {len(description)} حرف")
print(f"   ✅ يحتوي على H2: {'<h2>' in description}")
print(f"   ✅ يحتوي على تفاصيل المنتج: {'تفاصيل المنتج' in description}")
print(f"   ✅ يحتوي على رحلة العطر: {'رحلة العطر' in description}")
print(f"   ✅ يحتوي على FAQ: {'FAQ' in description or 'الأسئلة الشائعة' in description}")
print(f"   ✅ يحتوي على روابط مهووس: {'mahwous.com' in description}")
print(f"   ✅ يحتوي على الروابط الثابتة: {'العطور الفاخرة' in description}")
print(f"   ✅ لا إيموجي: {not any(ord(c) > 127000 for c in description)}")

# الخطوة 4: تجهيز الـ Payload
print("\n📦 الخطوة 4: تجهيز الـ Payload...")
product_data = {
    **PRODUCT,
    "description": description,
    "image_url": images[0]["url"] if images else "",
    "all_images": [img["url"] for img in images]
}
payload_item = prepare_final_payload(product_data)
print(f"   ✅ اسم المنتج: {payload_item['أسم المنتج']}")
print(f"   ✅ السعر: {payload_item['سعر المنتج']}")
print(f"   ✅ صورة المنتج: {payload_item['صورة المنتج'][:80]}...")
print(f"   ✅ صور إضافية: {len(payload_item['صور إضافية'])} صورة")
print(f"   ✅ طول الوصف في الـ Payload: {len(payload_item['الوصف'])} حرف")

# عرض الـ Payload كاملاً (بدون الوصف الطويل)
payload_preview = {k: v for k, v in payload_item.items() if k != "الوصف"}
payload_preview["الوصف"] = f"[{len(payload_item['الوصف'])} حرف - أول 200: {payload_item['الوصف'][:200]}...]"
print("\n📋 معاينة الـ Payload المرسل لـ Make:")
print(json.dumps(payload_preview, ensure_ascii=False, indent=2))

# الخطوة 5: الإرسال الفعلي لـ Make
print("\n🚀 الخطوة 5: الإرسال الفعلي لـ Make...")
result = send_products_to_make([product_data])
print(f"\n{'✅ نجح الإرسال!' if result['success'] else '❌ فشل الإرسال!'}")
print(f"   الرسالة: {result['message']}")

# حفظ الوصف الكامل في ملف للمراجعة
with open("/tmp/test_description.html", "w", encoding="utf-8") as f:
    f.write(f"<html><body dir='rtl'>\n{description}\n</body></html>")
print(f"\n💾 تم حفظ الوصف الكامل في: /tmp/test_description.html")
print("=" * 60)

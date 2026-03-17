#!/usr/bin/env python3
"""
سكريبت اختبار تجريبي - إرسال منتج حقيقي إلى Make
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from make_sender import prepare_final_payload, send_products_to_make

# ═══════════ بيانات المنتج التجريبي ═══════════
test_product = {
    "product_name": "طقم بلاك إنسينس مالاكي شوبارد أو دو بارفان 80 مل + جل استحمام معطر 150 مل",
    "price": 299.0,
    "cost_price": 0,
    "sale_price": 0,
    "weight": 1,
    "brand": "Chopard",
    "sku": "CHOPARD-BLACK-INCENSE-SET-80",
    "category": "عطور",
    "description": "",  # سيتم بناؤه برمجياً (بدون AI في الاختبار)
    "image_url": "https://cdn.salla.sa/form-builder/KVXmGnFCNHhWAHMXCfJSgMfHLBBNGVFHYGqFBrXK.jpg",
    "all_images": [
        "https://cdn.salla.sa/form-builder/KVXmGnFCNHhWAHMXCfJSgMfHLBBNGVFHYGqFBrXK.jpg"
    ],
    "competitor_image": "https://cdn.salla.sa/form-builder/KVXmGnFCNHhWAHMXCfJSgMfHLBBNGVFHYGqFBrXK.jpg",
}

print("=" * 60)
print("🧪 اختبار إرسال منتج تجريبي إلى Make")
print("=" * 60)

# ═══════════ تجهيز الـ Payload ═══════════
print("\n📦 تجهيز الـ Payload...")
payload = prepare_final_payload(test_product)

print(f"  ✅ أسم المنتج:    {payload['أسم المنتج']}")
print(f"  ✅ سعر المنتج:    {payload['سعر المنتج']} ريال")
print(f"  ✅ الماركة:        {payload['الماركة']}")
print(f"  ✅ التصنيف:        {payload['التصنيف']}")
print(f"  ✅ التصنيفات:     {payload['التصنيفات']}")
print(f"  ✅ صورة المنتج:   {payload['صورة المنتج'][:70]}...")
print(f"  ✅ عنوان الصفحة: {payload['عنوان الصفحة']}")
print(f"  ✅ رابط الصفحة:   {payload['رابط الصفحة SEO']}")
print(f"  ✅ وصف الصفحة:   {payload['وصف الصفحة'][:80]}...")
print(f"  ✅ طول الوصف:     {len(payload['الوصف'])} حرف")
print(f"  ✅ رمز التخزين:   {payload['رمز التخزين']}")

# ═══════════ الإرسال الفعلي ═══════════
print("\n🚀 إرسال المنتج إلى Make...")
result = send_products_to_make([test_product])

print(f"\n{'✅' if result['success'] else '❌'} النتيجة: {result['message']}")
print("\n" + "=" * 60)
print("📋 الـ Payload الكامل المرسل:")
print("=" * 60)
for key, val in payload.items():
    if key == "الوصف":
        print(f"  {key}: [{len(str(val))} حرف - HTML كامل]")
    else:
        print(f"  {key}: {str(val)[:80]}")

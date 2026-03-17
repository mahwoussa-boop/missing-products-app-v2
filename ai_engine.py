"""
ai_engine.py — محرك الذكاء الاصطناعي والميزات المتقدمة
═══════════════════════════════════════════════════════════════
- جلب صور المنتجات من الإنترنت و Fragrantica.
- استخراج الهرم العطري (مكونات العطر).
- توليد وصف احترافي SEO بأسلوب متجر مهووس.
- البحث في السوق السعودي عن الأسعار.
- التحقق التلقائي في متجر مهووس.
"""

import requests
import json
import re
import asyncio
import google.generativeai as genai
from config import GEMINI_API_KEY

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def _parse_json(txt):
    if not txt: return None
    try:
        clean = re.sub(r'```json|```', '', txt).strip()
        s = clean.find('{'); e = clean.rfind('}') + 1
        if s >= 0 and e > s:
            return json.loads(clean[s:e])
    except: pass
    return None

def _search_ddg(query, num_results=3):
    """بحث DuckDuckGo مجاني للإنترنت"""
    try:
        r = requests.get("https://api.duckduckgo.com/", params={
            "q": query, "format": "json", "no_html": "1", "skip_disambig": "1"
        }, timeout=8)
        if r.status_code == 200:
            data = r.json()
            results = []
            if data.get("AbstractText"):
                results.append({"snippet": data["AbstractText"], "url": data.get("AbstractURL", "")})
            for rel in data.get("RelatedTopics", [])[:num_results]:
                if isinstance(rel, dict) and rel.get("Text"):
                    results.append({"snippet": rel.get("Text", ""), "url": rel.get("FirstURL", "")})
            return results
    except: pass
    return []

def fetch_product_images(product_name, brand=""):
    """جلب روابط صور المنتج من Fragrantica و Google"""
    if not GEMINI_API_KEY: return {"images": [], "success": False}
    
    images = []
    fragrantica_url = ""
    model = genai.GenerativeModel('gemini-2.0-flash')

    prompt_frag = f"""ابحث عن العطر "{product_name}" في موقع fragranticarabia.com
أريد فقط:
1. رابط URL مباشر للصورة الرئيسية للعطر (.jpg أو .png أو .webp)
2. روابط صور إضافية إذا وجدت
3. رابط صفحة المنتج على Fragrantica Arabia

أجب JSON فقط:
{{
  "main_image": "رابط الصورة",
  "extra_images": ["رابط2"],
  "fragrantica_url": "رابط الصفحة",
  "found": true/false
}}"""

    try:
        response = model.generate_content(prompt_frag)
        data = _parse_json(response.text)
        if data and data.get("found") and data.get("main_image"):
            main = data["main_image"]
            if main.startswith("http"):
                images.append({"url": main, "source": "Fragrantica", "alt": product_name})
            fragrantica_url = data.get("fragrantica_url", "")
    except: pass

    # إضافة بحث DDG كبديل سريع
    if not images:
        ddg = _search_ddg(f"{product_name} perfume bottle image official")
        for r in ddg[:2]:
            url = r.get("url", "")
            if any(ext in url.lower() for ext in [".jpg", ".png", ".webp"]):
                images.append({"url": url, "source": "Web", "alt": product_name})

    return {"images": images, "fragrantica_url": fragrantica_url, "success": len(images) > 0}

def fetch_fragrantica_info(product_name):
    """جلب الهرم العطري ومكونات العطر من Fragrantica"""
    if not GEMINI_API_KEY: return {"success": False}
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    prompt = f"""ابحث عن العطر "{product_name}" في موقع fragranticarabia.com واستخرج:
1. رابط الصورة
2. مكونات العطر (القمة، القلب، القاعدة)
3. وصف قصير بالعربية
4. الماركة والنوع (EDP/EDT)
5. رابط الصفحة

اجب JSON فقط:
{{
  "image_url": "رابط الصورة",
  "top_notes": ["مكون1","مكون2"],
  "middle_notes": ["مكون1","مكون2"],
  "base_notes": ["مكون1","مكون2"],
  "description_ar": "وصف قصير",
  "brand": "", "type": "", "year": "", "fragrance_family": "",
  "fragrantica_url": "رابط"
}}"""

    try:
        response = model.generate_content(prompt)
        data = _parse_json(response.text)
        if data: return {"success": True, **data}
    except: pass
    return {"success": False}

def generate_mahwous_description(product_name, price, fragrantica_data=None):
    """خبير مهووس لتوليد وصف SEO حصري بطول 1200 كلمة"""
    if not GEMINI_API_KEY: return "الذكاء الاصطناعي غير مفعل."
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    frag_info = ""
    if fragrantica_data and fragrantica_data.get("success"):
        top  = ", ".join(fragrantica_data.get("top_notes", []))
        mid  = ", ".join(fragrantica_data.get("middle_notes", []))
        base = ", ".join(fragrantica_data.get("base_notes", []))
        frag_info = f"الماركة: {fragrantica_data.get('brand','')} | القمة: {top} | القلب: {mid} | القاعدة: {base}"

    prompt = f"""أنت خبير عطور عالمي تعمل لمتجر "مهووس" في السعودية.
اكتب وصفاً احترافياً طويلاً (SEO) لهذا العطر بتنسيق متجر مهووس:
المنتج: {product_name}
السعر: {price} ريال
{frag_info}

اكتب وصفاً جذاباً يتضمن:
1. مقدمة عاطفية قوية تبرز جمال العطر.
2. تفاصيل المنتج (الماركة، الجنس، التركيز).
3. الهرم العطري (القمة، القلب، القاعدة) بأسلوب حسي وليس مجرد سرد.
4. لماذا تختار هذا العطر؟ (مميزات وثبات).
5. متى وأين ترتدي العطر؟ (أوقات ومناسبات).
6. لمسة خبير من مهووس (تقييم احترافي).
7. الأسئلة الشائعة (FAQ).
8. خاتمة تشجع على الشراء من مهووس مع التأكيد على الأصالة 100%.

القواعد:
- لغة عربية فصحى راقية ومقنعة تسويقياً.
- استخدم **Bold** للكلمات المهمة ولا تستخدم إيموجي.
- لا تكتب بصيغة JSON، فقط النص الجاهز للنسخ بصيغة Markdown."""

    try:
        response = model.generate_content(prompt)
        # تنظيف أي أكواد Markdown برمجية قد تظهر بالخطأ
        text = re.sub(r'```markdown|```', '', response.text).strip()
        return text
    except Exception as e:
        return f"حدث خطأ أثناء توليد الوصف: {str(e)}"

def search_market_price(product_name, our_price=0):
    """بحث ذكي عن أسعار المنتج في السوق السعودي للمقارنة"""
    if not GEMINI_API_KEY: return {"success": False}
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    ddg = _search_ddg(f"سعر {product_name} السعودية نايس ون قولدن سنت سلة")
    web_ctx = "\n".join(f"- {r['snippet'][:120]}" for r in ddg)
    
    prompt = f"""تحليل سوق للمنتج في السعودية:
المنتج: {product_name}
سعرنا المقترح: {our_price} ريال
المعلومات من الويب: {web_ctx}

أجب JSON فقط:
{{
  "market_price": 0,
  "price_range": {{"min": 0, "max": 0}},
  "competitors": [{{"name": "اسم المتجر", "price": 0}}],
  "recommendation": "توصية تسعير قصيرة"
}}"""

    try:
        response = model.generate_content(prompt)
        data = _parse_json(response.text)
        if data: return {"success": True, **data}
    except: pass
    return {"success": False, "market_price": 0}

def search_mahwous(product_name):
    """التحقق مما إذا كان المنتج متوفراً بالفعل في متجر مهووس"""
    if not GEMINI_API_KEY: return {"success": False}
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    ddg = _search_ddg(f"site:mahwous.com {product_name}")
    web_ctx = "\n".join(r["snippet"][:100] for r in ddg)
    
    prompt = f"""هل العطر {product_name} متوفر في موقع mahwous.com بناءً على هذه النتائج؟
{web_ctx}
اجب JSON: {{"likely_available": true/false, "reason": "سبب قصير بالعربية"}}"""

    try:
        response = model.generate_content(prompt)
        data = _parse_json(response.text)
        if data: return {"success": True, **data}
    except: pass
    return {"success": False}

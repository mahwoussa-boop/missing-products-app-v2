"""
ai_engine.py — محرك الذكاء الاصطناعي والميزات المتقدمة (الإصدار الشامل V12.0)
═══════════════════════════════════════════════════════════════
- جلب صور المنتجات من الإنترنت و Fragrantica.
- استخراج الهرم العطري (مكونات العطر).
- توليد وصف احترافي SEO بأسلوب متجر مهووس عند الإرسال لـ Make.
- البحث في السوق السعودي عن الأسعار.
- التحقق التلقائي في متجر مهووس.
- نظام التقاط الأخطاء الصارم لعرض سبب العطل للمستخدم مباشرة.
"""

import requests
import json
import re
import asyncio
import google.generativeai as genai
from config import GEMINI_API_KEY

# إعداد مفتاح جوجل جيميناي
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def _parse_json(txt):
    """دالة مساعدة لاستخراج وتحليل JSON من رد الذكاء الاصطناعي بأمان."""
    if not txt: return None
    try:
        clean = re.sub(r'```json|```', '', txt).strip()
        s = clean.find('{')
        e = clean.rfind('}') + 1
        if s >= 0 and e > s:
            return json.loads(clean[s:e])
    except Exception as e:
        print(f"JSON Parse Error: {e}")
    return None

def _search_ddg(query, num_results=3):
    """بحث DuckDuckGo مجاني للإنترنت كبديل سريع لجلب المعلومات."""
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
    except Exception as e:
        print(f"DDG Search Error: {e}")
    return []

def fetch_product_images(product_name, brand=""):
    """جلب روابط صور المنتج النظيفة من Fragrantica أو Google مع التقاط الأخطاء."""
    if not GEMINI_API_KEY: return {"images": [], "success": False, "message": "مفتاح API غير متوفر"}
    
    images = []
    fragrantica_url = ""
    model = genai.GenerativeModel('gemini-2.0-flash')

    prompt_frag = f"""ابحث عن العطر "{product_name}" في موقع fragranticarabia.com
أريد فقط:
1. رابط URL مباشر للصورة الرئيسية للعطر (.jpg أو .png أو .webp)
2. روابط صور إضافية إذا وجدت
3. رابط صفحة المنتج على Fragrantica Arabia

أجب بصيغة JSON فقط:
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
    except Exception as e:
        return {"images": [], "success": False, "message": f"خطأ في الاتصال بالذكاء الاصطناعي: {str(e)}"}

    # إذا لم يجد صورة، نستخدم البحث كبديل
    if not images:
        try:
            ddg = _search_ddg(f"{product_name} perfume bottle image official")
            for r in ddg[:2]:
                url = r.get("url", "")
                if any(ext in url.lower() for ext in [".jpg", ".png", ".webp"]):
                    images.append({"url": url, "source": "Web", "alt": product_name})
        except Exception as e:
            return {"images": [], "success": False, "message": f"خطأ في محرك البحث: {str(e)}"}

    if not images:
        return {"images": [], "fragrantica_url": fragrantica_url, "success": False, "message": "لم يتم العثور على صور مناسبة."}

    return {"images": images, "fragrantica_url": fragrantica_url, "success": True, "message": "تم جلب الصور بنجاح."}

def fetch_fragrantica_info(product_name):
    """جلب الهرم العطري ومكونات العطر من Fragrantica مع التقاط الأخطاء."""
    if not GEMINI_API_KEY: return {"success": False, "message": "مفتاح API غير متوفر"}
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    prompt = f"""ابحث عن العطر "{product_name}" في موقع fragranticarabia.com واستخرج:
1. رابط الصورة
2. مكونات العطر (القمة، القلب، القاعدة)
3. وصف قصير بالعربية
4. الماركة والنوع (EDP/EDT)
5. رابط الصفحة

اجب بصيغة JSON فقط:
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
        if data: 
            return {"success": True, **data}
        else:
            return {"success": False, "message": "لم يتم العثور على معلومات العطر في Fragrantica."}
    except Exception as e:
        return {"success": False, "message": f"خطأ أثناء جلب المكونات: {str(e)}"}

def generate_mahwous_description(product_name, price, fragrantica_data=None):
    """خبير مهووس لتوليد وصف SEO حصري بطول 1000-1200 كلمة عند الإرسال لـ Make."""
    if not GEMINI_API_KEY: return "وصف افتراضي: " + product_name
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    frag_info = ""
    if fragrantica_data and fragrantica_data.get("success"):
        top  = ", ".join(fragrantica_data.get("top_notes", []))
        mid  = ", ".join(fragrantica_data.get("middle_notes", []))
        base = ", ".join(fragrantica_data.get("base_notes", []))
        frag_info = f"الماركة: {fragrantica_data.get('brand','')} | القمة: {top} | القلب: {mid} | القاعدة: {base}"

    prompt = f"""أنت خبير عطور عالمي تعمل لمتجر "مهووس" في السعودية.
اكتب وصفاً احترافياً طويلاً (SEO) لهذا العطر ليتم إدراجه مباشرة في المتجر.
المنتج: {product_name}
السعر: {price} ريال
{frag_info}

يجب أن يحتوي الوصف على الهيكلة التالية باستخدام HTML و Markdown (بدون استخدام لغة برمجة في المخرجات، فقط نص جاهز):
1. **مقدمة عاطفية قوية** تبرز جمال وجاذبية العطر.
2. **تفاصيل المنتج** (الماركة، الجنس، التركيز).
3. **الهرم العطري** (القمة، القلب، القاعدة) بأسلوب حسي وجذاب.
4. **لماذا تختار هذا العطر؟** (مميزات العطر، الثبات، والفوحان).
5. **متى وأين ترتدي العطر؟** (الأوقات والمناسبات المناسبة).
6. **لمسة خبير من مهووس** (تقييم احترافي وسر جاذبية العطر).
7. **الأسئلة الشائعة (FAQ)** - ضع 3 أسئلة وإجاباتها.
8. **خاتمة تشجع على الشراء** من متجر مهووس مع التأكيد على الأصالة 100%.

القواعد:
- لغة عربية فصحى راقية ومقنعة تسويقياً للعميل السعودي.
- استخدم **Bold** للكلمات المهمة ولا تستخدم إيموجي بشكل مبالغ فيه.
- لا تضع مخرجاتك ككود برمجي، بل نص منسق وجاهز للقراءة."""

    try:
        response = model.generate_content(prompt)
        text = re.sub(r'```markdown|```html|```', '', response.text).strip()
        return text
    except Exception as e:
        # إرجاع وصف بسيط في حال فشل الذكاء الاصطناعي لكي لا يتوقف الإرسال لـ Make
        return f"عطر {product_name} الرائع متوفر الآن في متجر مهووس بسعر {price} ريال. (ملاحظة: تعذر توليد الوصف المطول بسبب خطأ: {str(e)})"

def search_market_price(product_name, our_price=0):
    """بحث ذكي عن أسعار المنتج في السوق السعودي للمقارنة مع التقاط الأخطاء."""
    if not GEMINI_API_KEY: return {"success": False, "message": "مفتاح API غير متوفر"}
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    try:
        ddg = _search_ddg(f"سعر {product_name} السعودية نايس ون قولدن سنت سلة")
        web_ctx = "\n".join(f"- {r['snippet'][:120]}" for r in ddg)
        
        prompt = f"""تحليل سوق للمنتج في السعودية:
المنتج: {product_name}
سعرنا/سعر المنافس الحالي: {our_price} ريال
المعلومات من الويب: {web_ctx}

أجب بصيغة JSON فقط:
{{
  "market_price": 0,
  "price_range": {{"min": 0, "max": 0}},
  "competitors": [{{"name": "اسم المتجر", "price": 0}}],
  "recommendation": "توصية تسعير قصيرة"
}}"""

        response = model.generate_content(prompt)
        data = _parse_json(response.text)
        if data: 
            return {"success": True, **data}
        else:
            return {"success": False, "message": "تعذر استخراج بيانات السعر من السوق."}
    except Exception as e:
        return {"success": False, "message": f"خطأ أثناء جلب الأسعار: {str(e)}"}

def search_mahwous(product_name):
    """التحقق السريع مما إذا كان المنتج متوفراً بالفعل في متجر مهووس عبر محرك البحث."""
    if not GEMINI_API_KEY: return {"success": False, "message": "مفتاح API غير متوفر"}
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    try:
        ddg = _search_ddg(f"site:mahwous.com {product_name}")
        web_ctx = "\n".join(r["snippet"][:100] for r in ddg)
        
        prompt = f"""هل العطر {product_name} متوفر في موقع mahwous.com بناءً على هذه النتائج؟
{web_ctx}

اجب بصيغة JSON: {{"likely_available": "نعم/لا/غير مؤكد", "reason": "سبب قصير بالعربية"}}"""

        response = model.generate_content(prompt)
        data = _parse_json(response.text)
        if data: 
            return {"success": True, **data}
        else:
            return {"success": False, "message": "تعذر التحقق من المتجر."}
    except Exception as e:
        return {"success": False, "message": f"خطأ أثناء البحث في المتجر: {str(e)}"}

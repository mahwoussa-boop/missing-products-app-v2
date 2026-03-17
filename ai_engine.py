"""
ai_engine.py — محرك الذكاء الاصطناعي والميزات المتقدمة (الإصدار الشامل V13.3)
═══════════════════════════════════════════════════════════════
- جلب صور المنتجات من الإنترنت و Fragrantica بشكل موثوق للعمل مع Make.
- توفير صورة بديلة (Placeholder) في حال عدم توفر صورة لمنع توقف سيناريو Make.
- استخراج الهرم العطري (مكونات العطر).
- توليد وصف احترافي SEO بأسلوب "خبير منتجات مهووس" الدقيق.
- البحث في السوق السعودي عن الأسعار.
- التحقق التلقائي في متجر مهووس.
- نظام التقاط الأخطاء الصارم لعرض سبب العطل للمستخدم مباشرة وبدون توقف السناريو.
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
            if data.get("Image"):
                img_url = data.get("Image")
                if img_url.startswith("/"): img_url = "https://duckduckgo.com" + img_url
                results.append({"image": img_url})
            for rel in data.get("RelatedTopics", [])[:num_results]:
                if isinstance(rel, dict) and rel.get("Text"):
                    results.append({"snippet": rel.get("Text", ""), "url": rel.get("FirstURL", "")})
            return results
    except Exception as e:
        print(f"DDG Search Error: {e}")
    return []

def fetch_product_images(product_name, brand=""):
    """جلب روابط صور المنتج النظيفة لضمان عدم تعارض سناريو Make."""
    if not GEMINI_API_KEY: return {"images": [], "success": False, "message": "مفتاح API غير متوفر"}
    
    images = []
    fragrantica_url = ""
    model = genai.GenerativeModel('gemini-2.0-flash')

    prompt_frag = f"""قم بالبحث عن العطر "{product_name} {brand}"
أحتاج رابط مباشر لصورة العطر بخلفية بيضاء أو شفافة (تنتهي بـ .jpg أو .png).
حاول جلبها من مواقع موثوقة مثل fragrantica.com أو sephora أو غيرها.

أجب بصيغة JSON فقط:
{{
  "main_image": "رابط الصورة هنا يبدأ بـ https",
  "fragrantica_url": "رابط الصفحة",
  "found": true/false
}}"""

    try:
        response = model.generate_content(prompt_frag)
        data = _parse_json(response.text)
        if data and data.get("found") and data.get("main_image"):
            main = data["main_image"]
            if main.startswith("http"):
                images.append({"url": main, "source": "AI", "alt": product_name})
            fragrantica_url = data.get("fragrantica_url", "")
    except Exception as e:
        print(f"AI Image Fetch Error: {e}")

    # إذا لم يجد صورة عبر الذكاء الاصطناعي، نبحث عبر DDG
    if not images:
        try:
            ddg = _search_ddg(product_name)
            for r in ddg:
                img = r.get("image", "")
                if img and img.startswith("http"):
                    images.append({"url": img, "source": "DDG", "alt": product_name})
                    break
        except Exception:
            pass

    # 🔥 حماية سيناريو Make.com: إذا فشل كل شيء، لا نرسل فارغاً بل صورة بديلة تعمل!
    if not images:
        safe_name = product_name.replace(' ', '+')
        placeholder = f"https://ui-avatars.com/api/?name={safe_name}&background=random&size=512"
        return {"images": [{"url": placeholder, "source": "Placeholder"}], "fragrantica_url": "", "success": True, "message": "تم استخدام صورة بديلة لمنع تعطل Make."}

    return {"images": images, "fragrantica_url": fragrantica_url, "success": True, "message": "تم جلب الصور بنجاح."}

def fetch_fragrantica_info(product_name):
    """جلب الهرم العطري ومكونات العطر من Fragrantica مع التقاط الأخطاء."""
    if not GEMINI_API_KEY: return {"success": False, "message": "مفتاح API غير متوفر"}
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    prompt = f"""ابحث عن العطر "{product_name}" في موقع fragranticarabia.com واستخرج:
1. مكونات العطر (القمة، القلب، القاعدة)
2. وصف قصير بالعربية
3. الماركة والنوع (EDP/EDT)

اجب بصيغة JSON فقط:
{{
  "top_notes": ["مكون1","مكون2"],
  "middle_notes": ["مكون1","مكون2"],
  "base_notes": ["مكون1","مكون2"],
  "description_ar": "وصف قصير",
  "brand": "", "type": ""
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
    """توليد وصف متوافق 100% مع 'خبير وصف منتجات مهووس' SEO."""
    if not GEMINI_API_KEY: return f"اكتشف روعة عطر {product_name} المتوفر الآن في متجر مهووس بسعر {price} ريال."
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    frag_info = ""
    if fragrantica_data and fragrantica_data.get("success"):
        top  = ", ".join(fragrantica_data.get("top_notes", []))
        mid  = ", ".join(fragrantica_data.get("middle_notes", []))
        base = ", ".join(fragrantica_data.get("base_notes", []))
        frag_info = f"الماركة: {fragrantica_data.get('brand','')} | القمة: {top} | القلب: {mid} | القاعدة: {base}"

    prompt = f"""أنت "خبير وصف منتجات مهووس"، خبير عالمي في كتابة أوصاف منتجات العطور محسّنة لمحركات البحث (Google SEO و AI).
تعمل حصرياً لمتجر "مهووس" (Mahwous) - الوجهة الأولى للعطور الفاخرة في السعودية.

اكتب وصفاً حصرياً، راقياً، وعاطفياً لهذا المنتج ليتم إدراجه في المتجر مباشرة:
المنتج: {product_name}
السعر: {price} ريال
{frag_info}

يجب أن يحتوي الوصف على الهيكلة الإلزامية التالية (بدون استخدام لغة برمجة في المخرجات، فقط نص منسق وجاهز بـ HTML/Markdown):

<h2>سحر [اسم العطر]: تجربة عطرية لا تُنسى</h2>
<p>[مقدمة عاطفية تسويقية تبرز جاذبية العطر ولماذا يجب اقتناؤه...]</p>

<h3>تفاصيل العطر</h3>
<ul>
<li><strong>الماركة:</strong> [اسم الماركة]</li>
<li><strong>التركيز:</strong> [مثال: أو دو بارفان]</li>
<li><strong>الحجم:</strong> [حجم العطر]</li>
</ul>

<h3>الهرم العطري (نوتات العطر)</h3>
<p>[وصف حسي للمكونات وكيف تتدرج...]</p>
<ul>
<li><strong>الافتتاحية:</strong> [مكونات القمة]</li>
<li><strong>القلب:</strong> [مكونات القلب]</li>
<li><strong>القاعدة:</strong> [مكونات القاعدة]</li>
</ul>

<h3>لماذا تتسوق من متجر مهووس؟</h3>
<ul>
<li>ضمان أصالة 100% لجميع العطور.</li>
<li>تغليف فاخر يليق بك أو كهدية لمن تحب.</li>
<li>توصيل سريع وآمن لجميع مناطق المملكة.</li>
</ul>

<h3>الأسئلة الشائعة (FAQ)</h3>
<p><strong>س: هل العطر مناسب للاستخدام اليومي أم للمناسبات؟</strong></p>
<p>ج: [إجابة مقنعة]</p>
<p><strong>س: ما هو مدى ثبات وفوحان العطر؟</strong></p>
<p>ج: [إجابة مقنعة]</p>

<br>
<strong>اطلبه الآن من مهووس وعش الفخامة بكل تفاصيلها!</strong>
"""

    try:
        response = model.generate_content(prompt)
        text = re.sub(r'```html|```markdown|```', '', response.text).strip()
        return text
    except Exception as e:
        # إرجاع وصف بسيط في حال فشل الذكاء الاصطناعي لكي لا يتوقف الإرسال لـ Make
        return f"<h2>{product_name}</h2><p>عطر رائع متوفر الآن في متجر مهووس بسعر {price} ريال. احصل عليه اليوم!</p>"

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

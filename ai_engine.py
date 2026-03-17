"""
ai_engine.py v14.7 — المحرك الهجين الصارم (AI + Python)
═══════════════════════════════════════════════════════════════
- تفعيل المنطق الهجين الصارم لسحب الصور وتوليد الوصف.
- حقن الروابط الداخلية الثابتة لمهووس برمجياً في كافة الأوصاف.
- ضمان العودة لبيانات المنافس (Python Fallback) في حال فشل الـ AI.
"""

import requests
import json
import re
import urllib.parse
import asyncio
import os
import google.generativeai as genai
from config import GEMINI_API_KEY, GEMINI_API_KEYS, GEMINI_MODEL

# ─── نظام تناوب مفاتيح Gemini (Key Rotation) ───
_key_index = 0

def _call_gemini_with_rotation(prompt, model_name=None):
    """
    استدعاء Gemini مع نظام التناوب التلقائي:
    - يجرب كل مفتاح Gemini بالترتيب حتى ينجح أحدها.
    - إذا فشلت جميع مفاتيح Gemini → يجرب OpenRouter كبديل طوارئ.
    """
    if not model_name: model_name = GEMINI_MODEL or 'gemini-2.0-flash'
    # قراءة المفاتيح في وقت الاستدعاء (runtime) لضمان قراءة Streamlit Secrets بشكل صحيح
    from config import _parse_gemini_keys
    runtime_keys = _parse_gemini_keys()
    keys = runtime_keys if runtime_keys else (list(GEMINI_API_KEYS) if GEMINI_API_KEYS else ([GEMINI_API_KEY] if GEMINI_API_KEY else []))

    # جرب كل مفتاح Gemini
    for key in keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            if response and response.text and len(response.text) > 10:
                return response.text
        except Exception:
            continue

    # بديل طوارئ 1: OpenAI API (Gemini 2.5 Flash عبر بيئة Streamlit)
    try:
        from openai import OpenAI as _OpenAI
        _client = _OpenAI()
        _resp = _client.chat.completions.create(
            model='gemini-2.5-flash',
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=4096
        )
        _text = _resp.choices[0].message.content
        if _text and len(_text) > 10:
            return _text
    except Exception: pass

    # بديل طوارئ 2: OpenRouter
    openrouter_key = os.environ.get('OPENROUTER_API_KEY', '')
    try:
        import streamlit as st
        if not openrouter_key:
            openrouter_key = st.secrets.get('OPENROUTER_API_KEY', '')
    except Exception: pass

    if openrouter_key:
        for or_model in ['google/gemini-2.0-flash-exp:free', 'meta-llama/llama-3.3-70b-instruct:free', 'deepseek/deepseek-chat:free']:
            try:
                r = requests.post(
                    'https://openrouter.ai/api/v1/chat/completions',
                    headers={
                        'Authorization': f'Bearer {openrouter_key}',
                        'Content-Type': 'application/json',
                        'HTTP-Referer': 'https://mahwous.com',
                        'X-Title': 'Mahwous AI Engine'
                    },
                    json={
                        'model': or_model,
                        'messages': [{'role': 'user', 'content': prompt}],
                        'max_tokens': 4096
                    },
                    timeout=30
                )
                if r.status_code == 200:
                    data = r.json()
                    text = data.get('choices', [{}])[0].get('message', {}).get('content', '')
                    if text and len(text) > 10:
                        return text
            except Exception: continue

    return None

# إعداد مفتاح Gemini الأول عند التشغيل (للتوافق مع الكود القديم)
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# ─── قاعدة بيانات الروابط الداخلية لمهووس (Hyperlinks) ───
MAHWOUS_INTERNAL_LINKS = {
    "عطور نسائية": "https://mahwous.com/عطور-نسائية/c1119010419",
    "عطور رجالية": "https://mahwous.com/عطور-رجالية/c2020281682",
    "عطور النيش": "https://mahwous.com/عطور-النيش/c1015622154",
    "عطور التستر": "https://mahwous.com/عطور-التستر-نسائية/c734563747",
    "متجر مهووس": "https://mahwous.com/"
}

# الروابط الثابتة المطلوب حقنها في نهاية كل وصف
MAHWOUS_FIXED_FOOTER = '<p>لمشاهدة المزيد من <a href="https://mahwous.com/tags/perfumes">العطور الفاخرة</a> أو استكشاف <a href="https://mahwous.com/brands">أشهر الماركات</a>، تفضل بزيارة متجرنا.</p>'

def _parse_json(txt):
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
    except Exception: pass
    return []

def fetch_product_images(product_name, brand="", competitor_image=None):
    """جلب روابط صور المنتج (دالة هجينة صارمة)."""
    images = []
    fragrantica_url = ""
    
    # الحالة أ: توفر ذكاء صناعي لفلترة الصور
    if GEMINI_API_KEY:
        model = genai.GenerativeModel('gemini-2.0-flash')
        prompt = f"""ابحث عن صور نظيفة للعطر "{product_name} {brand}" بخلفية بيضاء.
أجب بصيغة JSON فقط: {{"images": [{{"url": "رابط الصورة"}}], "fragrantica_url": "رابط الصفحة", "found": true}}"""
        try:
            response = model.generate_content(prompt)
            data = _parse_json(response.text)
            if data and data.get("found") and data.get("images"):
                for img in data["images"]:
                    if img.get("url") and img["url"].startswith("http"):
                        images.append({"url": img["url"], "source": "AI"})
                fragrantica_url = data.get("fragrantica_url", "")
        except Exception: pass

    # الحالة ب: فشل الـ AI - العودة لرابط المنافس وتنظيفه برمجياً (Python)
    if not images and competitor_image:
        url = str(competitor_image).strip()
        if url.startswith("//"): url = "https:" + url
        try:
            # تشفير الروابط التي قد تحتوي على حروف عربية أو رموز
            parsed = urllib.parse.urlparse(url)
            clean_path = urllib.parse.quote(parsed.path, safe="/%")
            url = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, clean_path, parsed.params, parsed.query, parsed.fragment))
            images.append({"url": url, "source": "Competitor_Fixed"})
        except Exception: pass

    # الملاذ الأخير: Placeholder
    if not images:
        safe_name = urllib.parse.quote(product_name)
        images.append({"url": f"https://ui-avatars.com/api/?name={safe_name}&background=random&size=512", "source": "Placeholder"})

    return {"images": images, "fragrantica_url": fragrantica_url, "success": True}

def fetch_fragrantica_info(product_name):
    """جلب الهرم العطري (النظام الهجين)."""
    if not GEMINI_API_KEY: return {"success": False}
    model = genai.GenerativeModel('gemini-2.0-flash')
    prompt = f"""استخرج المكونات (القمة، القلب، القاعدة) للعطر "{product_name}" من Fragrantica.
أجب بصيغة JSON فقط: {{"top_notes": [], "middle_notes": [], "base_notes": [], "brand": "", "type": ""}}"""
    try:
        response = model.generate_content(prompt)
        data = _parse_json(response.text)
        if data: return {"success": True, **data}
    except Exception: pass
    return {"success": False}

def _generate_structural_html_description(product_name, price, brand=""):
    """بناء وصف هيكلي (Structural HTML) برمجياً بدون ذكاء صناعي - بتنسيق مهووس الكامل."""
    brand_display = brand if brand else 'ماركة عالمية'
    link_nisa = f'<a href="{MAHWOUS_INTERNAL_LINKS["عطور نسائية"]}">العطور النسائية</a>'
    link_rijal = f'<a href="{MAHWOUS_INTERNAL_LINKS["عطور رجالية"]}">العطور الرجالية</a>'
    link_nish = f'<a href="{MAHWOUS_INTERNAL_LINKS["عطور النيش"]}">عطور النيش</a>'
    link_store = f'<a href="{MAHWOUS_INTERNAL_LINKS["متجر مهووس"]}">متجر مهووس</a>'
    desc = f"""<h2>{product_name}</h2>
<p>اكتشف الفخامة والأناقة الحقيقية مع <strong>{product_name}</strong> من {brand_display}، العطر الذي يصوغ جاذبية فريدة ويمنحك حضوراً لا يُقاوم. تجربة عطرية استثنائية تجمع بين الأصالة والرقي، متوفرة الآن في {link_store} بسعر حصري {price} ريال سعودي.</p>

<h3>تفاصيل المنتج</h3>
<ul>
<li><strong>الماركة:</strong> {brand_display}.</li>
<li><strong>النوع:</strong> عطر.</li>
<li><strong>التركيز:</strong> أو دو بارفيوم (Eau de Parfum).</li>
<li><strong>سنة الإصدار:</strong> (غير متوفر).</li>
</ul>

<h3>رحلة العطر: النفحات والمكونات</h3>
<p>يُقدم <strong>{product_name}</strong> رحلة عطرية مثيرة، تكشف عن طبقاتها بانسجام تام:</p>
<ul>
<li><strong>مقدمة العطر:</strong> انفتاح منعش يمنحك شعوراً فورياً بالحيوية والانتعاش.</li>
<li><strong>قلب العطر:</strong> قلب زهري فاخر يخلق مزيجاً ناعماً ومميزاً.</li>
<li><strong>قاعدة العطر:</strong> قاعدة دافئة تضفي على العطر عمقاً فاخراً وثباتاً مذهلاً يدوم لساعات.</li>
</ul>

<h3>لماذا تختار {product_name}؟</h3>
<ul>
<li><strong>أناقة فاخرة:</strong> عطر يجسد الجاذبية والرقي من خلال توليفة عطرية مميزة.</li>
<li><strong>ثبات وفوحان استثنائي:</strong> بتركيز أو دو بارفيوم يضمن لك رائحة غنية تدوم لساعات طويلة.</li>
<li><strong>تصميم راقٍ:</strong> تركيبة متوازنة تناسب الأذواق الرفيعة.</li>
<li><strong>رائحة فريدة:</strong> عطر يقدم تجربة لا تُنسى تميزك في كل مناسبة.</li>
</ul>

<h3>الأسئلة الشائعة (FAQ)</h3>
<p><strong>س: هل {product_name} مناسب للاستخدام اليومي؟</strong><br>ج: يُناسب هذا العطر المناسبات الخاصة والسهرات والمواعيد التي تتطلب حضوراً لافتاً.</p>
<p><strong>س: ما مدة ثبات {product_name}؟</strong><br>ج: بفضل تركيز أو دو بارفيوم العالي، يثبت العطر لمدة 6-8 ساعات على الجلد.</p>

<h3>اكتشف أكثر من مهووس للعطور</h3>
<p>تصفح مجموعتنا من {link_nisa}، أو استكشف {link_nish} الفاخرة، وتعرف على {link_rijal} المميزة.</p>

<p>امتلك سحر <strong>{product_name}</strong> ودع عبيره يحكي قصة أناقتك وجاذبيتك التي لا تتضاهى.</p>

{MAHWOUS_FIXED_FOOTER}"""
    return desc.strip()

def generate_mahwous_description(product_name, price, brand="", fragrantica_data=None):
    """توليد الوصف (AI أولاً بتنسيق مهووس الكامل، ثم الهيكل البرمجي)."""
    # الحالة أ: توفر ذكاء اصطناعي (نظام التناوب)
    if GEMINI_API_KEYS or GEMINI_API_KEY:
        brand_display = brand if brand else 'ماركة عالمية'
        frag_ctx = ""
        if fragrantica_data and fragrantica_data.get('top_notes'):
            frag_ctx = f"""المكونات الحقيقية:
- مقدمة العطر: {', '.join(fragrantica_data.get('top_notes', []))}
- قلب العطر: {', '.join(fragrantica_data.get('middle_notes', []))}
- قاعدة العطر: {', '.join(fragrantica_data.get('base_notes', []))}"""
        else:
            frag_ctx = "ابحث عن المكونات الحقيقية من Fragrantica وأدرجها."

        prompt = f"""أنت خبير وصف منتجات متجر مهووس للعطور. اكتب وصفاً احترافياً كاملاً بالعربي لعطر "{product_name}" من {brand_display} بسعر {price} ريال.

يجب أن يتبع الوصف هذا الهيكل الصارم بالضبط (HTML نظيف):
1. <h2> اسم العطر بالعربي والإنجليزي
2. مقدمة عاطفية تسويقية (فقرة واحدة بدون إيموجي)
3. <h3>تفاصيل المنتج</h3> كقائمة <ul><li> تشمل: الماركة، النوع، الجنس، الحجم، التركيز، سنة الإصدار، الخط العطري
4. <h3>رحلة العطر: النفحات والمكونات</h3> مع مقدمة وقلب وقاعدة العطر بالمكونات الحقيقية
5. <h3>لماذا تختار {product_name}؟</h3> 4 نقاط مميزات بعنوان <strong>بولد</strong>
6. <h3>الأسئلة الشائعة (FAQ)</h3> سؤالان بصيغة س: وج:
7. <h3>اكتشف أكثر من مهووس للعطور</h3> مع روابط داخلية مخفية تحت الكلمات:
   - <a href="https://mahwous.com/عطور-نسائية/c1119010419">العطور النسائية</a>
   - <a href="https://mahwous.com/عطور-رجالية/c2020281682">العطور الرجالية</a>
   - <a href="https://mahwous.com/عطور-النيش/c1015622154">عطور النيش</a>
8. خاتمة تسويقية + فقرة "تجربة تسوق استثنائية بانتظرك في مهووس!"
9. في النهاية أضف هذا النص تماماً: {MAHWOUS_FIXED_FOOTER}

{frag_ctx}

تعليمات صارمة:
- لا إيموجي إطلاقاً
- الوصف بالعربي فقط (الأسماء العلمية للمكونات بالإنجليزي بين قوسين)
- الروابط الداخلية مخفية تحت الكلمات (Hyperlinks) وليست ظاهرة
- الطول: 800-1200 كلمة
- HTML نظيف بدون CSS"""
        try:
            text = _call_gemini_with_rotation(prompt)
            if text:
                text = re.sub(r'```html|```markdown|```', '', text).strip()
                if len(text) > 500:
                    if MAHWOUS_FIXED_FOOTER not in text: text += "\n" + MAHWOUS_FIXED_FOOTER
                    return text
        except Exception: pass

    # الحالة ب: بدون ذكاء اصطناعي (بناء هيكلي برمجياً بتنسيق مهووس الكامل)
    return _generate_structural_html_description(product_name, price, brand)

def search_market_price(product_name, our_price=0):
    if not GEMINI_API_KEY: return {"success": False}
    model = genai.GenerativeModel('gemini-2.0-flash')
    try:
        ddg = _search_ddg(f"سعر {product_name} السعودية")
        web_ctx = "\n".join(f"- {r['snippet'][:100]}" for r in ddg)
        prompt = f"حلل سعر السوق للمنتج {product_name} بناءً على: {web_ctx}\nأجب بصيغة JSON: {{\"market_price\": 0, \"recommendation\": \"\"}}"
        response = model.generate_content(prompt)
        data = _parse_json(response.text)
        if data: return {"success": True, **data}
    except Exception: pass
    return {"success": False}

def search_mahwous(product_name):
    if not GEMINI_API_KEY: return {"success": False}
    model = genai.GenerativeModel('gemini-2.0-flash')
    try:
        ddg = _search_ddg(f"site:mahwous.com {product_name}")
        web_ctx = "\n".join(r["snippet"][:100] for r in ddg)
        prompt = f"هل المنتج {product_name} متوفر في مهووس؟ {web_ctx}\nأجب بصيغة JSON: {{\"likely_available\": \"نعم/لا\"}}"
        response = model.generate_content(prompt)
        data = _parse_json(response.text)
        if data: return {"success": True, **data}
    except Exception: pass
    return {"success": False}

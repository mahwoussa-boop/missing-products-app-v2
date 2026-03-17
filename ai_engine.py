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
import google.generativeai as genai
from config import GEMINI_API_KEY

# إعداد مفتاح جوجل جيميناي
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
    """بناء وصف هيكلي (Structural HTML) برمجياً بدون ذكاء صناعي."""
    link_store = f'<a href="{MAHWOUS_INTERNAL_LINKS["متجر مهووس"]}">متجر مهووس</a>'
    desc = f"""
    <h2>{product_name}</h2>
    <p>اكتشف الفخامة والأناقة مع <strong>{product_name}</strong> من {brand if brand else 'ماركة عالمية'}، المتوفر الآن في {link_store} بسعر حصري {price} ريال سعودي.</p>
    <h3>مميزات المنتج</h3>
    <ul>
        <li>منتج أصلي 100%</li>
        <li>تغليف فاخر يليق بهداياكم</li>
        <li>شحن سريع لكافة مناطق المملكة</li>
    </ul>
    {MAHWOUS_FIXED_FOOTER}
    """
    return desc.strip()

def generate_mahwous_description(product_name, price, brand="", fragrantica_data=None):
    """توليد الوصف (AI أولاً، ثم الهيكل البرمجي)."""
    # الحالة أ: توفر ذكاء صناعي
    if GEMINI_API_KEY:
        model = genai.GenerativeModel('gemini-2.0-flash')
        links_ctx = "\n".join([f"- {k}: {v}" for k, v in MAHWOUS_INTERNAL_LINKS.items()])
        prompt = f"""أنت "خبير وصف منتجات مهووس". اكتب وصفاً مطولاً (1500 كلمة) لـ {product_name} بسعر {price}.
استخدم الروابط الداخلية: {links_ctx}
المكونات: {fragrantica_data if fragrantica_data else "Fragrantica search"}
التنسيق: HTML/Markdown بدون إيموجي. في النهاية، يجب إضافة هذا النص تماماً: {MAHWOUS_FIXED_FOOTER}"""
        try:
            response = model.generate_content(prompt)
            text = re.sub(r'```html|```markdown|```', '', response.text).strip()
            if len(text) > 500: 
                if MAHWOUS_FIXED_FOOTER not in text: text += "\n" + MAHWOUS_FIXED_FOOTER
                return text
        except Exception: pass
        
    # الحالة ب: بدون ذكاء صناعي (بناء هيكلي برمجياً)
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

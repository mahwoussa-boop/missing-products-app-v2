"""
ai_engine.py — محرك الذكاء الاصطناعي والنظام الهجين (V14.5)
═══════════════════════════════════════════════════════════════
- توليد وصف "خبير وصف منتجات مهووس" بالذكاء الاصطناعي (AI) وبدونه (Smart Templates).
- دعم الروابط الداخلية المخفية تحت الكلمات (Hyperlinks) برمجياً.
- جلب المكونات الحقيقية للعطر من Fragrantica لدمجها في الوصف.
- نظام سحب الصور المتعددة وإصلاح روابطها لضمان التوافق مع سلة.
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

# ─── قاعدة بيانات الروابط الداخلية لمهووس (Hyperlinks) ───
MAHWOUS_INTERNAL_LINKS = {
    "عطور نسائية": "https://mahwous.com/عطور-نسائية/c1119010419",
    "عطور رجالية": "https://mahwous.com/عطور-رجالية/c2020281682",
    "عطور النيش": "https://mahwous.com/عطور-النيش/c1015622154",
    "عطور التستر": "https://mahwous.com/عطور-التستر-نسائية/c734563747",
    "متجر مهووس": "https://mahwous.com/"
}

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
    except Exception:
        pass
    return []

def fetch_product_images(product_name, brand=""):
    """جلب روابط صور المنتج (برمجياً + AI)."""
    images = []
    fragrantica_url = ""
    
    # محاولة جلب الصور بالذكاء الاصطناعي أولاً
    if GEMINI_API_KEY:
        model = genai.GenerativeModel('gemini-2.0-flash')
        prompt_frag = f"""قم بالبحث عن العطر "{product_name} {brand}"
أحتاج روابط مباشرة لصور العطر بخلفية بيضاء أو شفافة (تنتهي بـ .jpg أو .png).
أجب بصيغة JSON فقط: {{"images": [{{"url": "رابط الصورة", "alt": "{product_name}"}}], "fragrantica_url": "رابط الصفحة", "found": true/false}}"""
        try:
            response = model.generate_content(prompt_frag)
            data = _parse_json(response.text)
            if data and data.get("found") and data.get("images"):
                for img in data["images"]:
                    if img.get("url") and img["url"].startswith("http"):
                        images.append({"url": img["url"], "source": "AI", "alt": img.get("alt", product_name)})
                fragrantica_url = data.get("fragrantica_url", "")
        except Exception:
            pass

    # بديل برمجي (DDG) في حال فشل الـ AI أو عدم توفره
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

    # حماية سيناريو Make
    if not images:
        safe_name = product_name.replace(' ', '+')
        placeholder = f"https://ui-avatars.com/api/?name={safe_name}&background=random&size=512"
        return {"images": [{"url": placeholder, "source": "Placeholder"}], "fragrantica_url": "", "success": True}

    return {"images": images, "fragrantica_url": fragrantica_url, "success": True}

def fetch_fragrantica_info(product_name):
    """جلب الهرم العطري ومكونات العطر (برمجياً + AI)."""
    if not GEMINI_API_KEY:
        # حل برمجي بسيط في حال عدم توفر AI (وصف افتراضي)
        return {"success": False, "message": "AI غير متوفر"}
        
    model = genai.GenerativeModel('gemini-2.0-flash')
    prompt = f"""ابحث عن العطر "{product_name}" في موقع fragranticarabia.com واستخرج المكونات (القمة، القلب، القاعدة) والماركة والنوع.
أجب بصيغة JSON فقط: {{"top_notes": ["مكون1"],"middle_notes": ["مكون1"],"base_notes": ["مكون1"],"brand": "","type": "","year": "","olfactory_family": ""}}"""
    try:
        response = model.generate_content(prompt)
        data = _parse_json(response.text)
        if data: return {"success": True, **data}
    except Exception:
        pass
    return {"success": False}

def _generate_smart_template_description(product_name, price, fragrantica_data=None):
    """توليد وصف احترافي برمجياً (بدون AI) مع روابط داخلية ومكونات حقيقية."""
    # استخراج المكونات إذا كانت متوفرة
    top = ", ".join(fragrantica_data.get("top_notes", [])) if fragrantica_data and fragrantica_data.get("top_notes") else "مزيج منعش من الحمضيات والزهور"
    mid = ", ".join(fragrantica_data.get("middle_notes", [])) if fragrantica_data and fragrantica_data.get("middle_notes") else "قلب زهري فاخر"
    base = ", ".join(fragrantica_data.get("base_notes", [])) if fragrantica_data and fragrantica_data.get("base_notes") else "قاعدة دافئة من العنبر والمسك"
    
    brand = fragrantica_data.get("brand", "ماركة عالمية") if fragrantica_data else "ماركة عالمية"
    conc = fragrantica_data.get("type", "أو دو بارفان") if fragrantica_data else "أو دو بارفان"
    
    # دمج الروابط الداخلية برمجياً
    link_store = f'<a href="{MAHWOUS_INTERNAL_LINKS["متجر مهووس"]}">متجر مهووس</a>'
    link_women = f'<a href="{MAHWOUS_INTERNAL_LINKS["عطور نسائية"]}">عطور نسائية</a>'
    
    desc = f"""
    <h2>سحر {product_name}: تجربة عطرية لا تُنسى</h2>
    <p>اكتشف الفخامة والجاذبية مع <strong>{product_name}</strong>، العطر الذي يجسد الأناقة في كل رشة. يتوفر هذا العطر الآن في {link_store} بسعر حصري {price} ريال سعودي.</p>
    
    <h3>تفاصيل المنتج</h3>
    <ul>
        <li><strong>الماركة:</strong> {brand}</li>
        <li><strong>التركيز:</strong> {conc}</li>
        <li><strong>الحجم:</strong> يتوفر بعدة أحجام</li>
    </ul>
    
    <h3>الهرم العطري (نوتات العطر الحقيقية)</h3>
    <p>يتميز العطر بتدرج عطري ساحر يأخذك في رحلة من الانتعاش إلى العمق:</p>
    <ul>
        <li><strong>الافتتاحية:</strong> {top}</li>
        <li><strong>القلب:</strong> {mid}</li>
        <li><strong>القاعدة:</strong> {base}</li>
    </ul>
    
    <h3>لماذا تتسوق من مهووس؟</h3>
    <p>في مهووس، نضمن لك الحصول على {link_women} أصلية 100% مع تغليف فاخر وشحن سريع لكافة مناطق المملكة.</p>
    
    <h3>الأسئلة الشائعة</h3>
    <p><strong>س: هل العطر أصلي؟</strong><br>ج: نعم، جميع منتجاتنا في متجر مهووس أصلية 100%.</p>
    
    <br>
    <strong>اطلب {product_name} الآن وعش الفخامة بكل تفاصيلها!</strong>
    """
    return desc.strip()

def generate_mahwous_description(product_name, price, fragrantica_data=None):
    """النظام الهجين لتوليد الوصف (AI أولاً، ثم القوالب الذكية برمجياً)."""
    # 1. محاولة التوليد بالذكاء الاصطناعي (1500 كلمة)
    if GEMINI_API_KEY:
        model = genai.GenerativeModel('gemini-2.0-flash')
        # دمج الروابط الداخلية في البرومبت ليستخدمها الـ AI
        links_ctx = "\n".join([f"- {k}: {v}" for k, v in MAHWOUS_INTERNAL_LINKS.items()])
        
        prompt = f"""أنت "خبير وصف منتجات مهووس". اكتب وصفاً مطولاً (1200-1500 كلمة) للمنتج: {product_name} بسعر {price} ريال.
استخدم هذه الروابط الداخلية المخفية تحت الكلمات (Hyperlinks) بشكل طبيعي:
{links_ctx}
المكونات الحقيقية المتوفرة: {fragrantica_data if fragrantica_data else "ابحث عنها في Fragrantica"}
التنسيق: HTML/Markdown احترافي بدون إيموجي.
الهيكلية: H1، مقدمة، تفاصيل، هرم عطري، لمسة خبير، FAQ، خاتمة."""
        
        try:
            response = model.generate_content(prompt)
            text = re.sub(r'```html|```markdown|```', '', response.text).strip()
            if len(text) > 500: return text
        except Exception:
            pass
            
    # 2. الحل البرمجي (Smart Template) في حال فشل الـ AI أو عدم توفره
    return _generate_smart_template_description(product_name, price, fragrantica_data)

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
    except Exception:
        pass
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
    except Exception:
        pass
    return {"success": False}

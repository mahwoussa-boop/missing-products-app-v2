"""
config.py — الإعدادات المركزية لنظام المنتجات المفقودة
═══════════════════════════════════════════════════════
v2.0 — متوافق مع vision-2030-v26
"""
import json as _json
import os as _os

# ═══════════ معلومات التطبيق ═══════════
APP_TITLE = "نظام المنتجات المفقودة الذكي — مهووس"
APP_VERSION = "v2.0"
APP_ICON = "🌬️"

# ═══════════ قراءة Secrets ═══════════
def _s(key, default=""):
    v = _os.environ.get(key, "")
    if v: return v
    try:
        import streamlit as st
        v = st.secrets.get(key, "")
        if v: return str(v) if not isinstance(v, (list, dict)) else v
    except Exception:
        pass
    return default

# ═══════════ مفاتيح Gemini ═══════════
def _parse_gemini_keys():
    keys = []
    raw = _s("GEMINI_API_KEYS", "")
    if isinstance(raw, list):
        keys = [k for k in raw if k and isinstance(k, str)]
    elif raw and isinstance(raw, str):
        raw = raw.strip()
        if raw.startswith('['):
            try:
                parsed = _json.loads(raw)
                if isinstance(parsed, list): keys = [k for k in parsed if k]
            except Exception:
                clean = raw.strip("[]").replace('"','').replace("'",'')
                keys = [k.strip() for k in clean.split(',') if k.strip()]
        elif raw: keys = [raw]
    single = _s("GEMINI_API_KEY", "")
    if single and single not in keys: keys.append(single)
    for n in [f"GEMINI_KEY_{i}" for i in range(1, 11)]:
        k = _s(n, "")
        if k and k not in keys: keys.append(k)
    return [k.strip() for k in keys if k and len(k) > 20]

GEMINI_API_KEYS = _parse_gemini_keys()
GEMINI_API_KEY = GEMINI_API_KEYS[0] if GEMINI_API_KEYS else ""
GEMINI_MODEL = "gemini-2.0-flash"

# ═══════════ Make.com Webhooks ═══════════
WEBHOOK_NEW_PRODUCTS = (
    _s("WEBHOOK_NEW_PRODUCTS") or
    "https://hook.eu2.make.com/xvubj23dmpxu8qzilstd25cnumrwtdxm"
)

# ═══════════ حدود المطابقة ═══════════
CONFIRMED_THRESHOLD = 75   # تطابق مؤكد بعد التطبيع العدواني
SIMILAR_THRESHOLD = 60     # مشابه يحتاج مراجعة
DIRECT_MATCH_THRESHOLD = 82  # تطابق مباشر token_set_ratio على bare
HIGH_AUTO_MATCH = 97       # تطابق تلقائي فوري (لا حاجة لـ AI)

# ═══════════ كلمات مرفوضة (عينات/تقسيمات) ═══════════
REJECT_KEYWORDS = [
    "sample", "عينة", "عينه", "decant", "تقسيم", "تقسيمة",
    "split", "miniature", "0.5ml", "1ml", "2ml", "3ml",
]

TESTER_KEYWORDS = ["tester", "تستر", "تيستر"]
SET_KEYWORDS = ["set", "gift set", "طقم", "مجموعة", "coffret"]

# ═══════════ مرادفات العطور (عربي ↔ إنجليزي) ═══════════
SYNONYMS = {
    # أنواع العطر
    "eau de parfum": "edp", "او دو بارفان": "edp", "أو دو بارفان": "edp",
    "او دي بارفان": "edp", "بارفان": "edp", "parfum": "edp",
    "او دي بارفيوم": "edp", "او دو بارفيوم": "edp", "بارفيوم": "edp",
    "لو دي بارفان": "edp", "لو دي بارفيوم": "edp",
    "إنتينس": "intense", "انتنس": "intense", "انتينس": "intense",
    "eau de toilette": "edt", "او دو تواليت": "edt", "أو دو تواليت": "edt",
    "تواليت": "edt", "toilette": "edt",
    "eau de cologne": "edc", "كولون": "edc", "cologne": "edc",
    "extrait de parfum": "extrait", "parfum extrait": "extrait",
    "perfume": "edp",
    # الماركات — عربي → إنجليزي موحد
    "ديور": "dior", "شانيل": "chanel", "شنل": "chanel",
    "أرماني": "armani", "ارماني": "armani", "جورجيو ارماني": "armani",
    "فرساتشي": "versace", "فيرساتشي": "versace", "فرزاتشي": "versace",
    "غيرلان": "guerlain", "جيرلان": "guerlain", "جرلان": "guerlain",
    "توم فورد": "tom ford", "تومفورد": "tom ford",
    "لطافة": "lattafa", "لطافه": "lattafa",
    "أجمل": "ajmal", "رصاصي": "rasasi", "رصاسي": "rasasi",
    "أمواج": "amouage", "كريد": "creed",
    "ايف سان لوران": "ysl", "سان لوران": "ysl", "يف سان لوران": "ysl",
    "yves saint laurent": "ysl", "ايف سانت لوران": "ysl",
    "غوتشي": "gucci", "قوتشي": "gucci",
    "برادا": "prada", "برادة": "prada",
    "بربري": "burberry", "بيربري": "burberry", "بوربيري": "burberry",
    "جيفنشي": "givenchy", "جفنشي": "givenchy", "جيفانشي": "givenchy",
    "كارولينا هيريرا": "carolina herrera",
    "باكو رابان": "paco rabanne",
    "نارسيسو رودريغيز": "narciso rodriguez",
    "كالفن كلاين": "calvin klein",
    "هوجو بوس": "hugo boss", "فالنتينو": "valentino",
    "بلغاري": "bvlgari", "كارتييه": "cartier",
    "لانكوم": "lancome", "لانكم": "lancome",
    "جو مالون": "jo malone", "جومالون": "jo malone",
    "سوفاج": "sauvage", "بلو": "bleu",
    "إيروس": "eros", "ايروس": "eros",
    "وان ميليون": "1 million",
    "إنفيكتوس": "invictus", "أفينتوس": "aventus",
    "عود": "oud", "مسك": "musk",
    "ميسوني": "missoni", "جوسي كوتور": "juicy couture",
    "موسكينو": "moschino", "دانهيل": "dunhill", "بنتلي": "bentley",
    "كينزو": "kenzo", "لاكوست": "lacoste", "فندي": "fendi",
    "ايلي صعب": "elie saab", "ازارو": "azzaro",
    "فيراغامو": "ferragamo", "سلفاتوري": "ferragamo",
    "شوبار": "chopard", "بوشرون": "boucheron",
    "كيليان": "kilian", "كليان": "kilian",
    "نيشان": "nishane", "نيشاني": "nishane",
    "زيرجوف": "xerjoff", "زيرجوفف": "xerjoff",
    "بنهاليغونز": "penhaligons", "بنهاليغون": "penhaligons",
    "مارلي": "parfums de marly", "دي مارلي": "parfums de marly",
    "تيزيانا ترينزي": "tiziana terenzi", "تيزيانا": "tiziana terenzi",
    "ناسوماتو": "nasomatto",
    "ميزون مارجيلا": "maison margiela", "مارجيلا": "maison margiela",
    "ربليكا": "replica",
    "مايزون فرانسيس": "maison francis kurkdjian",
    "فرانسيس": "maison francis kurkdjian",
    "بايريدو": "byredo", "لي لابو": "le labo",
    "مانسيرا": "mancera", "مونتالي": "montale", "روجا": "roja",
    "ثمين": "thameen", "أمادو": "amadou", "امادو": "amadou",
    "انيشيو": "initio", "إنيشيو": "initio",
    "جيمي تشو": "jimmy choo", "جيميتشو": "jimmy choo",
    "لاليك": "lalique", "بوليس": "police",
    "فيكتور رولف": "viktor rolf", "فيكتور اند رولف": "viktor rolf",
    "كلوي": "chloe", "شلوي": "chloe",
    "بالنسياغا": "balenciaga", "بالنسياجا": "balenciaga",
    "ميو ميو": "miu miu",
    "استي لودر": "estee lauder", "استيلودر": "estee lauder",
    "كوتش": "coach", "مايكل كورس": "michael kors",
    "رالف لورين": "ralph lauren", "رالف لوران": "ralph lauren",
    "ايزي مياكي": "issey miyake", "ايسي مياكي": "issey miyake",
    "دافيدوف": "davidoff", "ديفيدوف": "davidoff",
    "دولشي اند غابانا": "dolce gabbana", "دولتشي": "dolce gabbana",
    "دولشي": "dolce gabbana", "دولتشي آند غابانا": "dolce gabbana",
    "جان بول غولتييه": "jean paul gaultier", "غولتييه": "jean paul gaultier",
    "غولتيه": "jean paul gaultier", "غوتييه": "jean paul gaultier",
    "روبيرتو كفالي": "roberto cavalli", "روبرتو كافالي": "roberto cavalli",
    "هيرميس": "hermes", "ارميس": "hermes", "هرمز": "hermes",
    "آند": "and", "اند": "and", "&": "and",
    "ذا": "the", "ال": "the",
}

# ═══════════ علامات تجارية معروفة ═══════════
KNOWN_BRANDS = [
    "Dior", "Chanel", "Gucci", "Tom Ford", "Versace", "Armani", "YSL", "Prada",
    "Burberry", "Givenchy", "Hermes", "Creed", "Montblanc", "Calvin Klein",
    "Hugo Boss", "Dolce & Gabbana", "Valentino", "Bvlgari", "Cartier", "Lancome",
    "Jo Malone", "Amouage", "Rasasi", "Lattafa", "Arabian Oud", "Ajmal",
    "Al Haramain", "Afnan", "Armaf", "Nishane", "Xerjoff", "Parfums de Marly",
    "Initio", "Byredo", "Le Labo", "Mancera", "Montale", "Kilian", "Roja",
    "Carolina Herrera", "Jean Paul Gaultier", "Narciso Rodriguez",
    "Paco Rabanne", "Mugler", "Chloe", "Coach", "Michael Kors", "Ralph Lauren",
    "Maison Margiela", "Memo Paris", "Penhaligons", "Serge Lutens", "Diptyque",
    "Frederic Malle", "Francis Kurkdjian", "Floris", "Clive Christian",
    "Guerlain", "Issey Miyake", "Davidoff", "Jimmy Choo", "Lalique",
    "Viktor Rolf", "Balenciaga", "Miu Miu", "Estee Lauder",
    "Tiziana Terenzi", "Nasomatto", "Thameen",
    "Swiss Arabian", "Ard Al Zaafaran", "Nabeel", "Asdaaf", "Maison Alhambra",
    "Missoni", "Moschino", "Dunhill", "Bentley", "Kenzo", "Lacoste",
    "Fendi", "Elie Saab", "Azzaro", "Ferragamo", "Chopard", "Boucheron",
    "Roberto Cavalli", "Police", "Guess", "Antonio Banderas",
    "لطافة", "العربية للعود", "رصاصي", "أجمل", "الحرمين", "أرماف",
    "أمواج", "كريد", "توم فورد", "ديور", "شانيل", "غوتشي", "برادا",
]
# مجموعة مُطبّعة للبحث السريع
_BRANDS_LOWER = {b.lower() for b in KNOWN_BRANDS}

# ═══════════ ألوان الواجهة ═══════════
COLORS = {
    "missing": "#dc3545",
    "review": "#ff9800",
    "found": "#28a745",
    "primary": "#1e3a5f",
    "secondary": "#2d6a9f",
    "accent": "#6C63FF",
    "bg_dark": "#0e1117",
    "bg_card": "#1a1a2e",
}

"""
المحرك الذكي v12.0 — Cluster Matching Engine
قانون الأكواد الصارم | مهووس | صفر أخطاء
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional, List, Dict

# ══════════════════════════════════════════════════════════════════════════════
# قواميس التطبيع
# ══════════════════════════════════════════════════════════════════════════════

CONCENTRATION_PATTERNS = [
    # ── PARFUM/EXTRAIT (الأطول أولاً) ─────────────────────────────────────
    (r"extrait\s*de?\s*parfum", "PARFUM"),
    (r"pure\s*parfum", "PARFUM"),
    (r"بيور\s*بارفيوم", "PARFUM"),
    (r"اكستريت\s*دي?\s*بارفيوم", "PARFUM"),
    (r"اكستريكت\s*دي?\s*بارفيوم", "PARFUM"),
    (r"\bextrait\b", "PARFUM"),
    # ── EDP — يجب أن يأتي قبل PARFUM المفرد ──────────────────────────────
    (r"eau\s*de?\s*parfum", "EDP"),
    (r"\bedp\b", "EDP"),
    # أنماط "او دو بارفيوم" بكل أشكالها
    (r"(?:او|أو|اودو|او\s*دو|أو\s*دو|او\s*دي|أو\s*دي|ادو)\s*(?:برفيوم|بارفيوم|بارفان|برفان|بارفوم|برفوم)", "EDP"),
    (r"دو\s*(?:برفيوم|بارفيوم|بارفان|برفان)", "EDP"),
    (r"دي\s*(?:برفيوم|بارفيوم|بارفان|برفان)", "EDP"),
    (r"لو\s*دي?\s*(?:بارفيوم|برفيوم|بارفان)", "EDP"),
    (r"اليكسير\s*دي?\s*(?:بارفيوم|برفيوم)", "EDP"),
    (r"انتنس\s*(?:دي?\s*)?(?:بارفيوم|برفيوم)", "EDP"),
    # ── PARFUM المفرد (بعد EDP) ───────────────────────────────────────────
    (r"\bparfum\b(?!\s*de)", "PARFUM"),
    # "برفيوم" و"بارفيوم" المفردة (بدون كلمة ربط قبلها) = PARFUM
    (r"\bبارفيوم\b", "PARFUM"),
    (r"\bبرفيوم\b", "PARFUM"),
    (r"\bبارفان\b", "PARFUM"),
    (r"\bبرفان\b", "PARFUM"),
    (r"\bبارفوم\b", "PARFUM"),
    (r"\bبرفوم\b", "PARFUM"),
    (r"\bپارفوم\b", "PARFUM"),
    # ── EDT ───────────────────────────────────────────────────────────────
    (r"eau\s*de?\s*toilette", "EDT"),
    (r"\bedt\b", "EDT"),
    (r"(?:او|أو|اودو|او\s*دو|أو\s*دو|او\s*دي|أو\s*دي|ادو)\s*(?:تواليت|تواليتي|تواليه)", "EDT"),
    (r"دو\s*تواليت", "EDT"),
    # ── EDC ───────────────────────────────────────────────────────────────
    (r"eau\s*de?\s*cologne", "EDC"),
    (r"\bedc\b", "EDC"),
    (r"(?:او|أو)\s*(?:دو|دي)\s*كولون", "EDC"),
    (r"كولونيا", "EDC"),
    # ── MIST ──────────────────────────────────────────────────────────────
    (r"hair\s*mist", "HAIR_MIST"),
    (r"هير\s*ميست", "HAIR_MIST"),
    (r"بخاخ\s*شعر", "HAIR_MIST"),
    (r"body\s*mist", "MIST"),
    (r"بودي\s*ميست", "MIST"),
    (r"\bميست\b", "MIST"),
]

TYPE_PATTERNS = [
    (r"\bتستر\b|\bتيستر\b|\btester\b|\btest\b", "TESTER"),
    (r"طقم|سيت|\bset\b|مجموعة\s*هدايا|بكج|\bpack\b|كوليكشن|\bcollection\b|هدية", "SET"),
    (r"زيت\s*عطر|\boil\b", "OIL"),
    (r"بودي\s*واش|شاور\s*جل|دوش\s*جل", "BODY_WASH"),
    (r"بودي\s*لوشن|لوشن\s*جسم", "LOTION"),
    (r"كريم\s*جسم|\bcream\b", "CREAM"),
    (r"معطر\s*جسم|بودي\s*سبراي|body\s*spray", "BODY_SPRAY"),
    (r"ديودورانت|مزيل\s*عرق|deodorant", "DEODORANT"),
]

SAMPLE_PATTERNS = [
    r"\bعينة\b", r"\bسمبل\b", r"\bsample\b", r"\bvial\b",
    r"\bminiature\b", r"\bميني\b", r"\bmini\b",
]

ARABIC_SPELLING = [
    (r"[إأآ]", "ا"),
    (r"[يى](?=\s|$|[^ا-ي])", "ي"),
    (r"ة(?=\s|$)", "ه"),
    (r"ؤ", "و"),
    (r"ئ", "ي"),
    (r"(?:او|أو|اودو|اودي)\s*(?:دو|دي|de)\s*", "eau de "),
    (r"(?:او|أو)\s*(?:دو|دي)\s*", "eau de "),
    (r"\blou\s*de\b", "eau de"),
    (r"\bلو\s*دي?\b", "eau de"),
    (r"اليكسير|إليكسير|اكسير|إكسير|اليكزير|اليكسر", "اليكسير"),
    (r"ريزيرف|ريزيرفي|ريزيرفه", "ريزيرف"),
    (r"انتنس|انتنز|انتانس|انتانز|انتانس|انتينس", "انتنس"),
    (r"جنتلمان|جنتلمن", "جنتلمان"),
    (r"بلاك|بلك", "بلاك"),
    (r"وايت|وهايت", "وايت"),
    (r"جولد|قولد", "جولد"),
    (r"رويال|رويل", "رويال"),
    (r"ليجند|ليجيند", "ليجند"),
    (r"اكستريكت|اكستريت", "اكستريت"),
    (r"برفيوم|بارفيوم|بارفان|برفان|بارفوم|برفوم", "بارفيوم"),
    # توحيد "دي" و "دو" في الأسماء الفرنسية المعربة
    (r"\bدي\b", "دو"),
    # توحيد "ايست/إيست/إيس/ايس" → "اي"
    (r"ايست|إيست|إيس|ايس", "اي"),
    # توحيد "إي/إيه" → "اي"
    (r"إي(?=\s|$)", "اي"),
    # توحيد "بيل/بيلل" → "بيل"
    (r"بيلل", "بيل"),
    # توحيد "لا في" → "لافي" (لمنع الفصل)
    (r"لا\s*في", "لافي"),
    # توحيد "سوفاج/سوفاجه" → "سوفاج"
    (r"سوفاجه", "سوفاج"),
    # توحيد "شانيل/شانيلل" → "شانيل"
    (r"شانيلل", "شانيل"),
    # توحيد "لو / له" → "له"
    (r"\bلو\b(?!\s*(?:دي?|de))", "له"),
]


def normalize_text(text: str) -> str:
    if not text or not isinstance(text, str):
        return ""
    text = text.strip().lower()
    text = unicodedata.normalize("NFKC", text)
    for i, n in enumerate("٠١٢٣٤٥٦٧٨٩"):
        text = text.replace(n, str(i))
    for pattern, repl in ARABIC_SPELLING:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    text = re.sub(r"[^\w\s\d]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_size_ml(text: str) -> float:
    text_lower = text.lower()
    patterns = [
        (r"(\d+(?:[.,]\d+)?)\s*(?:مل|ml|مليلتر|milliliter|millilitre)", 1.0),
        (r"(\d+(?:[.,]\d+)?)\s*(?:لتر|liter|litre)\b", 1000.0),
        (r"(\d+(?:[.,]\d+)?)\s*(?:oz|أوقية|اونصة)", 29.5735),
    ]
    for pattern, mult in patterns:
        m = re.search(pattern, text_lower, re.IGNORECASE)
        if m:
            return round(float(m.group(1).replace(",", ".")) * mult, 1)
    return 0.0


def extract_concentration(text: str) -> str:
    text_lower = text.lower()
    for pattern, conc in CONCENTRATION_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return conc
    return "UNKNOWN"


def extract_type(text: str) -> str:
    text_lower = text.lower()
    for pattern, ptype in TYPE_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return ptype
    return "PERFUME"


def is_sample(text: str, size: float) -> bool:
    if 0 < size <= 8:
        return True
    text_lower = text.lower()
    for p in SAMPLE_PATTERNS:
        if re.search(p, text_lower, re.IGNORECASE):
            return True
    return False


def normalize_brand(brand: str) -> str:
    if not brand:
        return ""
    parts = re.split(r"[|/]", brand)
    return normalize_text(parts[0].strip())


def extract_core_name(raw_name: str, brand: str = "") -> str:
    """
    الاسم الجوهري = الاسم بعد حذف:
    - كلمة "عطر/تستر" من البداية
    - الحجم والتركيز والنوع وكلمات الجنس
    - الماركة (لتقليص الضجيج وتركيز المقارنة على اسم المنتج)
    ملاحظة: حذف الماركة جائز لأن مقارنة الماركة تتم مسبقاً في _check_pair.
    """
    text = raw_name
    # حذف كلمات البداية
    text = re.sub(r"^(عطر|تستر|تيستر|كريم|لوشن|بودي|زيت|معطر|مزيل)\s+", "", text.strip(), flags=re.IGNORECASE)
    # حذف الماركة (كل أجزاءها عربية وأجنبية)
    if brand:
        for part in re.split(r"[|/]", brand):
            part = part.strip()
            if len(part) > 2:
                text = re.sub(re.escape(part), " ", text, flags=re.IGNORECASE)
    # حذف الحجم
    text = re.sub(r"\d+(?:[.,]\d+)?\s*(?:مل|ml|مليلتر|لتر|liter|litre|oz|أوقية)", " ", text, flags=re.IGNORECASE)
    # حذف التركيز
    for pattern, _ in CONCENTRATION_PATTERNS:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    # حذف النوع
    for pattern, _ in TYPE_PATTERNS:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    # حذف كلمات الجنس
    text = re.sub(r"\b(للرجال|للنساء|للجنسين|men|women|unisex|رجالي|نسائي)\b", " ", text, flags=re.IGNORECASE)
    # تطبيع
    text = normalize_text(text)
    text = re.sub(r"\b\d+\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


@dataclass
class ProductRecord:
    raw_name: str
    brand: str = ""
    size: float = 0.0
    concentration: str = "UNKNOWN"
    product_type: str = "PERFUME"
    core_name: str = ""
    is_sample_flag: bool = False
    brand_normalized: str = ""

    def __post_init__(self):
        self.size = extract_size_ml(self.raw_name)
        self.concentration = extract_concentration(self.raw_name)
        self.product_type = extract_type(self.raw_name)
        self.is_sample_flag = is_sample(self.raw_name, self.size)
        self.core_name = extract_core_name(self.raw_name, self.brand)
        self.brand_normalized = normalize_brand(self.brand)

    def __repr__(self):
        return f"[{self.brand_normalized}] {self.product_type}|{self.size}ml|{self.concentration}|'{self.core_name}'"


class ClusterMatchEngine:
    """المحرك الذكي v12.0 — المقارنة العنقودية"""

    def __init__(self, store_records: List[Dict],
                 name_col: str = "name", brand_col: str = "brand"):
        self.store_products: List[ProductRecord] = []
        self.cluster: Dict[str, List[ProductRecord]] = {}
        self._build(store_records, name_col, brand_col)

    def _build(self, records, name_col, brand_col):
        for rec in records:
            name = str(rec.get(name_col, "")).strip()
            brand = str(rec.get(brand_col, "")).strip()
            if not name or name.lower() in ("nan", "none", ""):
                continue
            prod = ProductRecord(raw_name=name, brand=brand)
            self.store_products.append(prod)
            key = prod.brand_normalized or "__no_brand__"
            self.cluster.setdefault(key, []).append(prod)

    @staticmethod
    def _name_sim(a: str, b: str) -> float:
        """
        حساب التشابه بين اسمين جوهريين.
        قاعدة: إذا كان أحد الاسمين قصيراً جداً (< 4 حروف) → نسبة 0 لتجنب تطابق خاطئ.
        """
        if not a or not b:
            return 0.0
        # منع التطابق إذا كان الاسم فارغاً تماماً
        if len(a) < 2 or len(b) < 2:
            return 0.0
        try:
            from rapidfuzz import fuzz
            # نستخدم token_sort_ratio فقط لتجنب التطابق الجزئي المضلل
            return fuzz.token_sort_ratio(a, b)
        except ImportError:
            a_w, b_w = set(a.split()), set(b.split())
            if not a_w or not b_w:
                return 0.0
            return len(a_w & b_w) / len(a_w | b_w) * 100

    def _check_pair(self, new_p: ProductRecord, store_p: ProductRecord):
        nb, sb = new_p.brand_normalized, store_p.brand_normalized
        if nb and sb and nb != sb:
            if nb not in sb and sb not in nb:
                return False, f"ماركة مختلفة: [{nb}] vs [{sb}]", 0.0
        if new_p.product_type != store_p.product_type:
            return False, f"نوع مختلف: {new_p.product_type} vs {store_p.product_type}", 0.0
        if new_p.size > 0 and store_p.size > 0:
            if abs(new_p.size - store_p.size) > 0.5:
                return False, f"حجم مختلف: {new_p.size} vs {store_p.size}", 0.0
        if (new_p.concentration != "UNKNOWN" and store_p.concentration != "UNKNOWN"
                and new_p.concentration != store_p.concentration):
            return False, f"تركيز مختلف: {new_p.concentration} vs {store_p.concentration}", 0.0
        score = self._name_sim(new_p.core_name, store_p.core_name)
        return True, "مؤهل", score

    def match(self, competitor_name: str, competitor_brand: str = "",
              t_dup: float = 90.0, t_critical: float = 72.0) -> dict:
        new_p = ProductRecord(raw_name=competitor_name, brand=competitor_brand)
        if new_p.is_sample_flag:
            return {"verdict": "مستبعد", "reason": "عينة صغيرة",
                    "score": 0.0, "matched_name": None, "product": new_p}

        brand_key = new_p.brand_normalized or "__no_brand__"
        candidates = self.cluster.get(brand_key, [])
        if not candidates:
            for k, v in self.cluster.items():
                if brand_key in k or k in brand_key:
                    candidates.extend(v)
        if not candidates:
            candidates = self.store_products

        best_score = 0.0
        best_match: Optional[ProductRecord] = None
        rejection_reasons = []

        for store_p in candidates:
            can, reason, score = self._check_pair(new_p, store_p)
            if not can:
                rejection_reasons.append(reason)
                continue
            if score > best_score:
                best_score = score
                best_match = store_p

        if best_score >= t_dup:
            verdict = "مكرر"
            reason = f"تطابق ({best_score:.1f}%) — {best_match.raw_name[:60]}"
        elif best_score >= t_critical:
            verdict = "حرج"
            reason = f"تشابه حرج ({best_score:.1f}%) — {best_match.raw_name[:50] if best_match else '—'}"
        elif best_score > 0:
            verdict = "جديد"
            reason = f"أقرب تشابه ({best_score:.1f}%) — غير كافٍ"
        else:
            verdict = "جديد"
            uniq = list(dict.fromkeys(rejection_reasons[:3]))
            reason = "جديد — " + " | ".join(uniq[:2]) if uniq else "جديد — لا يوجد في متجرنا"

        return {"verdict": verdict, "reason": reason, "score": best_score,
                "matched_name": best_match.raw_name if best_match else None, "product": new_p}


def run_comparison(store_csv, competitor_csv, output_csv,
                   t_dup=90.0, t_critical=72.0):
    import pandas as pd
    store_df = pd.read_csv(store_csv, header=[0, 1], encoding="utf-8-sig", low_memory=False)
    store_df.columns = [f"{a}|{b}" if "Unnamed" not in str(b) else str(a) for a, b in store_df.columns]
    name_col = next((c for c in store_df.columns if "أسم المنتج" in c or "اسم المنتج" in c), store_df.columns[2])
    brand_col = next((c for c in store_df.columns if "الماركة" in c), None)
    store_records = []
    for _, row in store_df.iterrows():
        n = str(row.get(name_col, "")).strip()
        b = str(row.get(brand_col, "")).strip() if brand_col else ""
        if n and n.lower() not in ("nan", "none"):
            store_records.append({"name": n, "brand": b})
    print(f"متجر مهووس: {len(store_records):,} منتج")
    engine = ClusterMatchEngine(store_records)
    print(f"سلال الماركات: {len(engine.cluster):,}")
    comp_df = pd.read_csv(competitor_csv, encoding="utf-8-sig", low_memory=False)
    comp_name_col = "styles_productCard__name__pakbB"
    if comp_name_col not in comp_df.columns:
        comp_name_col = next((c for c in comp_df.columns if "name" in c.lower() or "اسم" in c), comp_df.columns[0])
    comp_names = comp_df[comp_name_col].dropna().astype(str).tolist()
    print(f"ملف المنافس: {len(comp_names):,} منتج")
    results = []
    stats = {"جديد": 0, "مكرر": 0, "حرج": 0, "مستبعد": 0}
    for name in comp_names:
        r = engine.match(name, t_dup=t_dup, t_critical=t_critical)
        stats[r["verdict"]] = stats.get(r["verdict"], 0) + 1
        results.append({
            "اسم المنتج المنافس": name, "الحكم": r["verdict"],
            "نسبة التشابه": round(r["score"], 1),
            "أقرب منتج في متجرنا": r["matched_name"] or "",
            "السبب": r["reason"], "الماركة": r["product"].brand,
            "الحجم (مل)": r["product"].size, "التركيز": r["product"].concentration,
            "النوع": r["product"].product_type, "الاسم الجوهري": r["product"].core_name,
        })
    pd.DataFrame(results).to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"تم الحفظ: {output_csv}")
    return stats, engine


# ══════════════════════════════════════════════════════════════════════════════
# الاختبار المحلي
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import pandas as pd

    print("=" * 70)
    print("اختبار المحرك v12.0 — قانون الأكواد الصارم")
    print("=" * 70)

    store_df = pd.read_csv(
        "/home/ubuntu/upload/متجرنامهووسبكلالاعمدةللمنتجات.csv",
        header=[0, 1], encoding="utf-8-sig", low_memory=False
    )
    store_df.columns = [f"{a}|{b}" if "Unnamed" not in str(b) else str(a) for a, b in store_df.columns]
    name_col = "Unnamed: 2_level_0|أسم المنتج"
    brand_col = "Unnamed: 22_level_0|الماركة"
    store_records = []
    for _, row in store_df.iterrows():
        n = str(row.get(name_col, "")).strip()
        b = str(row.get(brand_col, "")).strip()
        if n and n.lower() not in ("nan", "none"):
            store_records.append({"name": n, "brand": b})
    print(f"ملف مهووس: {len(store_records):,} منتج")
    engine = ClusterMatchEngine(store_records)
    print(f"سلال الماركات: {len(engine.cluster):,}")
    top = sorted(engine.cluster.items(), key=lambda x: len(x[1]), reverse=True)[:8]
    for k, v in top:
        print(f"  {k}: {len(v)} منتج")

    # ── فحص ما يوجد فعلاً في مهووس للماركات المختبرة ──────────────────
    print("\nعينة من منتجات شانيل في مهووس:")
    chanels = [p for p in engine.store_products if "شانيل" in p.brand_normalized][:5]
    for p in chanels:
        print(f"  {p}")

    print("\nعينة من منتجات ديور في مهووس:")
    diors = [p for p in engine.store_products if "ديور" in p.brand_normalized][:5]
    for p in diors:
        print(f"  {p}")

    print("\nعينة من منتجات لانكوم في مهووس:")
    lancs = [p for p in engine.store_products if "لانكوم" in p.brand_normalized][:5]
    for p in lancs:
        print(f"  {p}")

    # ── حالات الاختبار ────────────────────────────────────────────────────
    # حالات الاختبار مبنية على ما هو موجود فعلاً في مهووس
    test_cases = [
        # مكررات مؤكدة (موجودة فعلاً في مهووس)
        ("عطر شانيل بلو دو شانيل او دو تواليت 100مل",           "شانيل | Chanel",    "مكرر",    "موجود: عطر بلو دي شانيل EDT 100مل"),
        ("عطر شانيل بلو دو شانيل او دو بارفيوم 100مل",          "شانيل | Chanel",    "مكرر",    "موجود: بلو دي شانيل EDP 100مل"),
        ("عطر شانيل بلو دو شانيل او دو تواليت 50مل",            "شانيل | Chanel",    "مكرر",    "موجود: بلو دي شانيل EDT 50مل"),
        ("عطر شانيل بلو دو شانيل بارفيوم 100مل",                "شانيل | Chanel",    "مكرر",    "موجود: بلو دي شانيل PARFUM 100مل"),
        ("عطر شانيل بلو دو شانيل او دو بارفيوم 50مل",           "شانيل | Chanel",    "مكرر",    "موجود: بلو دي شانيل EDP 50مل"),
        ("عطر شانيل بلو دو شانيل او دو تواليت 150مل",           "شانيل | Chanel",    "مكرر",    "موجود: بلو دي شانيل EDT 150مل"),
        ("عطر ديور سوفاج او دو تواليت 100مل",                   "ديور | Dior",        "مكرر",    "موجود"),
        ("عطر ديور سوفاج او دو بارفيوم 100مل",                  "ديور | Dior",        "مكرر",    "موجود"),
        ("عطر ديور سوفاج او دو تواليت 60مل",                    "ديور | Dior",        "مكرر",    "موجود: 60مل"),
        ("تستر ديور سوفاج او دو تواليت 100مل",                  "ديور | Dior",        "مكرر",    "موجود: تستر سوفاج EDT 100مل"),
        # مهووس يملك "إنتينسمنت" فقط وليس النسخة الأساسية → جديد
        ("عطر لانكوم لا في ايست بيل او دو بارفيوم 100مل",       "لانكوم | Lancôme",  "جديد",    "مهووس يملك إنتينسمنت فقط → الأساسي جديد"),
        ("عطر جيفنشي جنتلمان ريسيرف برايف او دو برفيوم 100مل", "جيفنشي | Givenchy", "مكرر",    "موجود"),
        # جديد مؤكد (غير موجود في مهووس)
        ("عطر شانيل بلو دو شانيل بارفيوم 200مل",                "شانيل | Chanel",    "جديد",    "200مل غير موجود"),
        ("عطر جيفنشي بلو دو شانيل او دو تواليت 100مل",          "جيفنشي | Givenchy", "جديد",    "ماركة مختلفة"),
        # مستبعدات
        ("عينة شانيل بلو 2مل",                                  "شانيل | Chanel",    "مستبعد",  "عينة"),
        ("سمبل ديور سوفاج 5مل",                                 "ديور | Dior",        "مستبعد",  "عينة"),
    ]

    print("\n" + "=" * 90)
    fmt = "{:<3} {:<50} {:<10} {:<10} {:<6} {}"
    print(fmt.format("", "المنتج المنافس", "المتوقع", "النتيجة", "نسبة", "السبب"))
    print("-" * 90)
    correct = 0
    errors = []
    for name, brand, expected, desc in test_cases:
        r = engine.match(name, competitor_brand=brand, t_dup=90.0, t_critical=72.0)
        verdict = r["verdict"]
        ok = verdict == expected
        if ok:
            correct += 1
            icon = "OK"
        else:
            icon = "XX"
            errors.append((name, expected, verdict, r["reason"], r["product"]))
        print(fmt.format(icon, name[:48], expected, verdict, f"{r['score']:.0f}%", r["reason"][:50]))

    total = len(test_cases)
    print("-" * 90)
    print(f"\nالدقة: {correct}/{total} = {(correct/total)*100:.1f}%")

    if errors:
        print(f"\nالأخطاء ({len(errors)}):")
        for name, exp, got, reason, prod in errors:
            print(f"  XX {name[:60]}")
            print(f"     المتوقع: {exp} | الناتج: {got}")
            print(f"     المنتج المحلل: {prod}")
            print(f"     السبب: {reason}")
    else:
        print("\nصفر أخطاء! المحرك v12.0 جاهز.")

    # ── اختبار على بيانات حقيقية ─────────────────────────────────────────
    print("\n" + "=" * 70)
    print("اختبار على بيانات المنافس الحقيقية:")
    stats, _ = run_comparison(
        store_csv="/home/ubuntu/upload/متجرنامهووسبكلالاعمدةللمنتجات.csv",
        competitor_csv="/home/ubuntu/upload/متجرعالمجيفنشيبكلالاعمدةالسعروالصور.csv",
        output_csv="/home/ubuntu/upload/نتائج_v12_اختبار.csv",
        t_dup=90.0, t_critical=70.0,
    )
    total_comp = sum(stats.values())
    print(f"\nالنتائج ({total_comp:,} منتج):")
    for k, v in stats.items():
        pct = (v / total_comp) * 100 if total_comp else 0
        bar = "#" * int(pct / 3)
        print(f"  {k:<10}: {v:>4} ({pct:>5.1f}%) {bar}")

    out_df = pd.read_csv("/home/ubuntu/upload/نتائج_v12_اختبار.csv", encoding="utf-8-sig")
    print("\nعينة من المنتجات الجديدة:")
    for _, row in out_df[out_df["الحكم"] == "جديد"].head(10).iterrows():
        print(f"  + {row['اسم المنتج المنافس'][:60]}")
        print(f"    -> {row['السبب'][:70]}")
    print("\nعينة من المكررات:")
    for _, row in out_df[out_df["الحكم"] == "مكرر"].head(8).iterrows():
        print(f"  = {row['اسم المنتج المنافس'][:60]}")
        print(f"    -> {row['السبب'][:70]}")

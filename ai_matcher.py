"""
ai_matcher.py v2.0 — محرك المطابقة الذكي متعدد الطبقات
═══════════════════════════════════════════════════════════
الطبقات:
  1. تطبيع عدواني (Aggressive Normalize) + مرادفات عربي↔إنجليزي
  2. استخلاص الماركة + خط المنتج + الحجم + النوع
  3. Fuzzy matching باستخدام rapidfuzz (أسرع 10x من thefuzz)
  4. كشف التستر/الأساسي والأحجام المختلفة
  5. (اختياري) تحقق AI عبر Gemini للحالات الغامضة
"""

import re
import json
import time
import hashlib
import requests
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from rapidfuzz import fuzz, process as rf_process

from config import (
    SYNONYMS, KNOWN_BRANDS, _BRANDS_LOWER,
    REJECT_KEYWORDS, TESTER_KEYWORDS, SET_KEYWORDS,
    CONFIRMED_THRESHOLD, SIMILAR_THRESHOLD, DIRECT_MATCH_THRESHOLD,
    GEMINI_API_KEYS, GEMINI_MODEL,
)


# ══════════════════════════════════════════════════════════════
#  الطبقة 1: التطبيع العدواني
# ══════════════════════════════════════════════════════════════

def normalize_aggressive(text: str) -> str:
    """
    تطبيع عدواني: يحوّل النص إلى صيغة موحدة قابلة للمقارنة.
    - أحرف صغيرة
    - استبدال المرادفات (عربي→إنجليزي)
    - إزالة التشكيل والرموز الخاصة
    - توحيد المسافات
    """
    if not isinstance(text, str) or not text.strip():
        return ""

    t = text.strip().lower()

    # إزالة التشكيل العربي
    t = re.sub(r'[\u0610-\u061A\u064B-\u065F\u0670]', '', t)

    # استبدال المرادفات (الأطول أولاً لتجنب التداخل)
    for ar, en in sorted(SYNONYMS.items(), key=lambda x: -len(x[0])):
        t = t.replace(ar, en)

    # إزالة الرموز الخاصة (عدا الأحرف والأرقام والمسافات)
    t = re.sub(r'[^\w\s]', ' ', t)

    # إزالة "ml" / "مل" مع الأرقام المرتبطة (نحتفظ بها في extract_size)
    t = re.sub(r'\b\d+\s*(ml|مل|ملي)\b', '', t)

    # إزالة كلمات شائعة لا تؤثر على الهوية
    noise = [
        "for men", "for women", "pour homme", "pour femme",
        "unisex", "للرجال", "للنساء", "رجالي", "نسائي",
        "عطر", "perfume", "spray", "بخاخ", "new", "جديد",
        "original", "اصلي", "أصلي",
    ]
    for w in noise:
        t = t.replace(w, "")

    # توحيد المسافات
    t = " ".join(t.split())
    return t


def normalize_bare(text: str) -> str:
    """تطبيع أكثر عدوانية: يزيل حتى كلمات التستر والنوع."""
    t = normalize_aggressive(text)
    for kw in TESTER_KEYWORDS + ["edp", "edt", "edc", "extrait", "intense", "parfum"]:
        t = re.sub(rf'\b{re.escape(kw)}\b', '', t)
    return " ".join(t.split())


# ══════════════════════════════════════════════════════════════
#  الطبقة 2: استخلاص المكونات (ماركة، حجم، نوع، جنس)
# ══════════════════════════════════════════════════════════════

def extract_brand(text: str) -> str:
    """استخلاص اسم الماركة من اسم المنتج."""
    if not text:
        return ""
    t_lower = text.lower()

    # أولاً: بحث في المرادفات العربية
    for ar, en in SYNONYMS.items():
        if ar in t_lower and en.lower() in _BRANDS_LOWER:
            return en.title()

    # ثانياً: بحث مباشر في الماركات المعروفة
    for brand in KNOWN_BRANDS:
        if brand.lower() in t_lower:
            return brand
    return ""


def extract_size(text: str) -> Optional[int]:
    """استخلاص حجم العبوة بالمل."""
    if not text:
        return None
    m = re.search(r'(\d+)\s*(ml|مل|ملي)', text.lower())
    if m:
        return int(m.group(1))
    return None


def extract_type(text: str) -> str:
    """استخلاص نوع العطر (EDP, EDT, إلخ)."""
    t = text.lower()
    if any(k in t for k in ["edp", "eau de parfum", "او دو بارفان", "بارفان", "بارفيوم", "لو دي بارفان"]):
        return "EDP"
    if any(k in t for k in ["edt", "eau de toilette", "او دو تواليت", "تواليت"]):
        return "EDT"
    if any(k in t for k in ["edc", "cologne", "كولون"]):
        return "EDC"
    if any(k in t for k in ["extrait", "parfum extrait"]):
        return "Extrait"
    if any(k in t for k in ["intense", "إنتينس", "انتنس", "انتينس"]):
        return "Intense"
    return ""


def extract_gender(text: str) -> str:
    """استخلاص الجنس."""
    t = text.lower()
    if any(k in t for k in ["for men", "pour homme", "للرجال", "رجالي", "homme"]):
        return "رجالي"
    if any(k in t for k in ["for women", "pour femme", "للنساء", "نسائي", "femme"]):
        return "نسائي"
    return "مشترك"


def is_tester(text: str) -> bool:
    """هل المنتج تستر؟"""
    t = text.lower()
    return any(kw in t for kw in TESTER_KEYWORDS)


def is_set(text: str) -> bool:
    """هل المنتج طقم/مجموعة؟"""
    t = text.lower()
    return any(kw in t for kw in SET_KEYWORDS)


def is_sample(text: str) -> bool:
    """هل المنتج عينة/تقسيمة؟"""
    t = text.lower()
    return any(kw in t for kw in REJECT_KEYWORDS)


# ══════════════════════════════════════════════════════════════
#  الطبقة 3: محرك المقارنة الرئيسي
# ══════════════════════════════════════════════════════════════

def _prepare_our_items(mahwous_df: pd.DataFrame) -> List[Dict]:
    """تجهيز منتجاتنا مرة واحدة (مُخزَّنة مؤقتاً)."""
    items = []
    for _, row in mahwous_df.iterrows():
        raw = str(row.get("name", "")).strip()
        if not raw:
            continue
        norm = normalize_aggressive(raw)
        bare = normalize_bare(raw)
        if not norm or len(bare) < 3:
            continue
        items.append({
            "raw": raw,
            "norm": norm,
            "bare": bare,
            "brand": extract_brand(raw),
            "size": extract_size(raw),
            "type": extract_type(raw),
            "is_tester": is_tester(raw),
        })
    return items


def _find_best_match(
    comp_name: str,
    comp_norm: str,
    comp_bare: str,
    comp_brand: str,
    comp_size: Optional[int],
    comp_type: str,
    comp_is_tester: bool,
    our_items: List[Dict],
) -> Tuple[bool, float, str, Optional[Dict]]:
    """
    البحث عن أفضل تطابق لمنتج منافس في منتجاتنا.
    يُعيد: (found, score, reason, variant_info)
    """
    if not our_items or not comp_bare:
        return False, 0.0, "", None

    best_same_score = 0.0
    best_same_item = None
    best_variant_score = 0.0
    best_variant_item = None

    # — مقارنة مع كل منتج من منتجاتنا —
    for item in our_items:
        # المطابقة الرئيسية: token_set_ratio على النص المُطبّع
        score = fuzz.token_set_ratio(comp_bare, item["bare"])

        # مكافأة تطابق الماركة
        if comp_brand and item["brand"] and comp_brand.lower() == item["brand"].lower():
            score = min(100, score + 5)

        # عقوبة اختلاف الحجم (إذا كلاهما معروف)
        if comp_size and item["size"] and comp_size != item["size"]:
            score = max(0, score - 8)

        # تفريق التستر من الأصلي
        same_tester_status = (comp_is_tester == item["is_tester"])

        if same_tester_status:
            if score > best_same_score:
                best_same_score = score
                best_same_item = item
        else:
            if score > best_variant_score:
                best_variant_score = score
                best_variant_item = item

    # — تقييم النتائج —
    # تطابق مؤكد (نفس النوع: تستر/أساسي)
    if best_same_score >= CONFIRMED_THRESHOLD:
        return True, best_same_score, f"✅ متطابق: {best_same_item['raw'][:60]}", None

    # منطقة مشبوهة
    if best_same_score >= SIMILAR_THRESHOLD:
        vinfo = {
            "type": "similar",
            "product": best_same_item["raw"] if best_same_item else "",
            "score": best_same_score
        }
        return False, best_same_score, f"⚠️ مشابه ({best_same_score:.0f}%): {best_same_item['raw'][:60]}", vinfo

    # كشف التستر/الأساسي المتوفر
    variant_info = None
    if best_variant_score >= 55 and best_variant_item:
        v_type = "tester" if best_variant_item["is_tester"] else "base"
        variant_info = {
            "type": v_type,
            "label": "🏷️ يتوفر لدينا تستر منه" if v_type == "tester" else "✅ يتوفر لدينا العطر الأساسي",
            "product": best_variant_item["raw"],
            "score": best_variant_score,
        }

    return False, best_same_score, "", variant_info


# ══════════════════════════════════════════════════════════════
#  الطبقة 4: (اختياري) تحقق AI عبر Gemini
# ══════════════════════════════════════════════════════════════

_gemini_key_idx = 0

def _call_gemini(prompt: str, temperature: float = 0.1) -> Optional[str]:
    """استدعاء Gemini API مع تدوير المفاتيح."""
    global _gemini_key_idx
    if not GEMINI_API_KEYS:
        return None

    url_base = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

    for attempt in range(min(len(GEMINI_API_KEYS), 3)):
        key = GEMINI_API_KEYS[_gemini_key_idx % len(GEMINI_API_KEYS)]
        _gemini_key_idx += 1

        try:
            resp = requests.post(
                f"{url_base}?key={key}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": temperature,
                        "maxOutputTokens": 500,
                    }
                },
                timeout=15
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            elif resp.status_code == 429:
                time.sleep(1)
                continue
        except Exception:
            continue
    return None


def ai_verify_batch(items: List[Dict], our_sample: List[str]) -> Dict[str, str]:
    """
    تحقق AI لدفعة من المنتجات المشبوهة.
    يُعيد: {product_name: "same"|"different"|"unsure"}
    """
    if not GEMINI_API_KEYS or not items:
        return {}

    lines = []
    for i, item in enumerate(items[:10]):  # حد أقصى 10 لكل دفعة
        lines.append(f"{i+1}. منتج المنافس: {item.get('comp', '')}")
        lines.append(f"   أقرب منتج لدينا: {item.get('our', '')}")

    prompt = f"""أنت خبير عطور. لكل زوج، حدد: هل المنتجان هما نفس العطر؟
الإجابة JSON فقط بدون أي نص آخر:
{{"results": [{{"index":1,"verdict":"same"|"different"|"unsure","reason":"..."}}]}}

{chr(10).join(lines)}

تذكر: الأسماء قد تكون بالعربي والإنجليزي، "تستر" ≠ "أصلي" (مختلفان)،
"EDP" ≠ "EDT" (مختلفان)، "50ml" ≠ "100ml" (مختلفان في الحجم فقط).
"""
    txt = _call_gemini(prompt)
    if not txt:
        return {}

    try:
        # تنظيف الرد (أحياناً يكون ملفوفاً بعلامات كود)
        clean = re.sub(r'```json|```', '', txt).strip()
        data = json.loads(clean)
        result = {}
        for r in data.get("results", []):
            idx = r.get("index", 0)
            if 1 <= idx <= len(items):
                result[items[idx-1].get("comp", "")] = r.get("verdict", "unsure")
        return result
    except Exception:
        return {}


# ══════════════════════════════════════════════════════════════
#  الطبقة 5: نظام الأسماء البديلة (Alias Memory)
# ══════════════════════════════════════════════════════════════

def load_aliases(path: str = "aliases.json") -> Dict[str, str]:
    """تحميل ملف الربط المحفوظ."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_alias(comp_name: str, our_name: str, path: str = "aliases.json"):
    """حفظ ربط جديد."""
    aliases = load_aliases(path)
    key = normalize_bare(comp_name)
    aliases[key] = our_name
    with open(path, "w", encoding="utf-8") as f:
        json.dump(aliases, f, ensure_ascii=False, indent=2)


def check_alias(comp_name: str, path: str = "aliases.json") -> Optional[str]:
    """التحقق من وجود ربط محفوظ."""
    aliases = load_aliases(path)
    key = normalize_bare(comp_name)
    return aliases.get(key)


# ══════════════════════════════════════════════════════════════
#  الدالة الرئيسية: معالجة جميع المنافسين
# ══════════════════════════════════════════════════════════════

def process_competitors(
    mahwous_df: pd.DataFrame,
    competitors_data: Dict[str, pd.DataFrame],
    use_ai: bool = False,
    progress_callback=None,
) -> pd.DataFrame:
    """
    معالجة جميع منتجات المنافسين وتصنيفها إلى:
    - مفقود مؤكد (🟢 green)
    - مفقود محتمل / يحتاج مراجعة (🟡 yellow)
    - مشبوه / محظور الإرسال (🔴 red)
    - موجود / متطابق (found)
    """
    # تجهيز منتجاتنا
    our_items = _prepare_our_items(mahwous_df)
    if not our_items:
        return pd.DataFrame()

    results = []
    seen_bare = set()  # لمنع التكرار بين المنافسين
    total_products = sum(len(df) for df in competitors_data.values())
    processed = 0

    for comp_name, comp_df in competitors_data.items():
        for _, row in comp_df.iterrows():
            processed += 1
            if progress_callback and processed % 10 == 0:
                progress_callback(processed, total_products, "")

            cp = str(row.get("name", "")).strip()
            if not cp or is_sample(cp):
                continue

            # — التطبيع —
            cp_norm = normalize_aggressive(cp)
            cp_bare = normalize_bare(cp)
            if not cp_bare or len(cp_bare) < 3:
                continue

            # — إزالة التكرار بين المنافسين —
            bare_key = cp_bare
            if bare_key in seen_bare:
                continue

            # — التحقق من الأسماء البديلة المحفوظة —
            alias = check_alias(cp)
            if alias:
                # هذا المنتج تم تأكيده سابقاً كموجود
                results.append({
                    "product_name": cp,
                    "price": float(row.get("price", 0) or 0),
                    "image_url": str(row.get("image_url", "")),
                    "product_url": str(row.get("product_url", "")),
                    "brand": extract_brand(cp),
                    "size": f"{extract_size(cp)}ml" if extract_size(cp) else "",
                    "type": extract_type(cp),
                    "is_tester": is_tester(cp),
                    "is_set": is_set(cp),
                    "confidence_score": 95.0,
                    "confidence_level": "found",
                    "competitor_name": comp_name,
                    "matched_product": alias,
                    "note": "✅ تم تأكيده مسبقاً (Alias)",
                    "variant_info": "",
                    "variant_product": "",
                    "detection_date": datetime.now().strftime("%Y-%m-%d"),
                })
                seen_bare.add(bare_key)
                continue

            # — المطابقة متعددة الطبقات —
            c_brand = extract_brand(cp)
            c_size = extract_size(cp)
            c_type = extract_type(cp)
            c_is_tester = is_tester(cp)

            found, score, reason, variant = _find_best_match(
                cp, cp_norm, cp_bare, c_brand, c_size, c_type, c_is_tester, our_items
            )

            if found:
                results.append({
                    "product_name": cp,
                    "price": float(row.get("price", 0) or 0),
                    "image_url": str(row.get("image_url", "")),
                    "product_url": str(row.get("product_url", "")),
                    "brand": c_brand,
                    "size": f"{c_size}ml" if c_size else "",
                    "type": c_type,
                    "is_tester": c_is_tester,
                    "is_set": is_set(cp),
                    "confidence_score": score,
                    "confidence_level": "found",
                    "competitor_name": comp_name,
                    "matched_product": reason,
                    "note": reason,
                    "variant_info": "",
                    "variant_product": "",
                    "detection_date": datetime.now().strftime("%Y-%m-%d"),
                })
                seen_bare.add(bare_key)
                continue

            # — Cross-check إضافي: token_set_ratio مباشر —
            cross_found = False
            for item in our_items:
                direct = fuzz.token_set_ratio(cp_bare, item["bare"])
                if direct >= DIRECT_MATCH_THRESHOLD:
                    cross_found = True
                    results.append({
                        "product_name": cp,
                        "price": float(row.get("price", 0) or 0),
                        "image_url": str(row.get("image_url", "")),
                        "product_url": str(row.get("product_url", "")),
                        "brand": c_brand,
                        "size": f"{c_size}ml" if c_size else "",
                        "type": c_type,
                        "is_tester": c_is_tester,
                        "is_set": is_set(cp),
                        "confidence_score": direct,
                        "confidence_level": "found",
                        "competitor_name": comp_name,
                        "matched_product": f"✅ متطابق مباشر: {item['raw'][:60]}",
                        "note": f"✅ متطابق مباشر ({direct}%)",
                        "variant_info": "",
                        "variant_product": "",
                        "detection_date": datetime.now().strftime("%Y-%m-%d"),
                    })
                    break
            if cross_found:
                seen_bare.add(bare_key)
                continue

            # — تصنيف مستوى الثقة —
            _has_similar = bool(reason and "⚠️" in reason)
            _has_variant = bool(variant)

            if score < 40 and not _has_variant and not _has_similar:
                conf_level = "green"      # مفقود مؤكد
            elif score < 55 and not _has_similar:
                conf_level = "green"      # مفقود مؤكد
            elif _has_similar or (55 <= score < 68):
                conf_level = "yellow"     # يحتاج مراجعة
            elif _has_variant and variant.get("type") == "similar":
                conf_level = "red"        # مشبوه
            else:
                conf_level = "green"

            results.append({
                "product_name": cp,
                "price": float(row.get("price", 0) or 0),
                "image_url": str(row.get("image_url", "")),
                "product_url": str(row.get("product_url", "")),
                "brand": c_brand,
                "size": f"{c_size}ml" if c_size else "",
                "type": c_type,
                "is_tester": c_is_tester,
                "is_set": is_set(cp),
                "confidence_score": score,
                "confidence_level": conf_level,
                "competitor_name": comp_name,
                "matched_product": "",
                "note": reason if reason else "",
                "variant_info": variant.get("label", "") if variant else "",
                "variant_product": variant.get("product", "") if variant else "",
                "detection_date": datetime.now().strftime("%Y-%m-%d"),
            })
            seen_bare.add(bare_key)

    if progress_callback:
        progress_callback(total_products, total_products, "✅")

    return pd.DataFrame(results) if results else pd.DataFrame()

"""
app.py v2.0 — نظام المنتجات المفقودة الذكي لمتجر مهووس
═══════════════════════════════════════════════════════════
🌬️ اكتشف الفرص الذهبية — تحقق بدقة — أرسل بأمان
"""

import streamlit as st
import pandas as pd
import json
import time
from datetime import datetime

from config import APP_TITLE, APP_VERSION, APP_ICON, COLORS, WEBHOOK_NEW_PRODUCTS
from db_manager import load_mahwous_store_data, load_competitor_data
from ai_matcher import (
    process_competitors, save_alias, is_tester, is_set,
    ai_verify_batch, normalize_bare,
)
from make_sender import send_products_to_make, build_payload, verify_webhook

# ═══════════════════════════════════════════════════════════════
#  إعدادات الصفحة
# ═══════════════════════════════════════════════════════════════

st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════════════════════════════
#  CSS مخصص — RTL + تصميم احترافي
# ═══════════════════════════════════════════════════════════════

st.markdown("""
<style>
    /* اتجاه RTL */
    .stApp { direction: rtl; }
    .stApp [data-testid="stSidebar"] { direction: rtl; }
    .stApp [data-testid="stMarkdownContainer"] { text-align: right; }
    
    /* العنوان الرئيسي */
    .main-title {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        border-radius: 16px;
        padding: 28px 32px;
        margin-bottom: 24px;
        border: 1px solid rgba(108, 99, 255, 0.2);
        position: relative;
        overflow: hidden;
    }
    .main-title::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 3px;
        background: linear-gradient(90deg, #6C63FF, #00d2ff, #6C63FF);
    }
    .main-title h1 {
        color: #e8e8ff;
        font-size: 1.8rem;
        margin: 0 0 6px 0;
        font-weight: 700;
    }
    .main-title p {
        color: #8888aa;
        font-size: 0.95rem;
        margin: 0;
    }
    
    /* بطاقات الإحصاء */
    .stat-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 14px;
        margin: 16px 0 24px 0;
    }
    .stat-card {
        border-radius: 14px;
        padding: 20px 18px;
        text-align: center;
        border: 1px solid rgba(255,255,255,0.06);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .stat-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 24px rgba(0,0,0,0.3);
    }
    .stat-card .value {
        font-size: 2.4rem;
        font-weight: 800;
        line-height: 1.1;
    }
    .stat-card .label {
        font-size: 0.85rem;
        opacity: 0.8;
        margin-top: 6px;
    }
    .card-green  { background: linear-gradient(135deg, #064e3b, #065f46); color: #a7f3d0; }
    .card-green .value { color: #34d399; }
    .card-yellow { background: linear-gradient(135deg, #78350f, #92400e); color: #fde68a; }
    .card-yellow .value { color: #fbbf24; }
    .card-red    { background: linear-gradient(135deg, #7f1d1d, #991b1b); color: #fecaca; }
    .card-red .value { color: #f87171; }
    .card-blue   { background: linear-gradient(135deg, #1e3a5f, #1e40af); color: #bfdbfe; }
    .card-blue .value { color: #60a5fa; }
    .card-purple { background: linear-gradient(135deg, #3b0764, #4c1d95); color: #ddd6fe; }
    .card-purple .value { color: #a78bfa; }
    
    /* شريحة الثقة */
    .conf-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 0.78rem;
        font-weight: 600;
    }
    .conf-green  { background: #065f46; color: #34d399; }
    .conf-yellow { background: #78350f; color: #fbbf24; }
    .conf-red    { background: #7f1d1d; color: #f87171; }
    
    /* نص المعاينة */
    .preview-box {
        background: #1a1a2e;
        border: 1px solid #2d2d4a;
        border-radius: 10px;
        padding: 14px;
        margin: 8px 0;
        font-size: 0.85rem;
        direction: ltr;
        text-align: left;
        font-family: monospace;
        max-height: 300px;
        overflow-y: auto;
    }
    
    /* تحسين الأزرار */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #6C63FF, #4834d4);
        border: none;
        font-weight: 600;
    }
    
    /* إخفاء عناصر Streamlit الافتراضية */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    .stDeployButton { display: none; }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
#  دوال مساعدة للواجهة
# ═══════════════════════════════════════════════════════════════

def render_header():
    """عرض العنوان الرئيسي."""
    st.markdown(f"""
    <div class="main-title">
        <h1>{APP_ICON} {APP_TITLE}</h1>
        <p>اكتشف الفرص الذهبية — تحقق بدقة — أرسل بأمان إلى Make.com &nbsp; | &nbsp; {APP_VERSION}</p>
    </div>
    """, unsafe_allow_html=True)


def render_stats(green_count, yellow_count, red_count, found_count, total_count, competitors_count):
    """عرض بطاقات الإحصاء."""
    st.markdown(f"""
    <div class="stat-grid">
        <div class="stat-card card-green">
            <div class="value">{green_count}</div>
            <div class="label">🟢 مفقود مؤكد — جاهز للإرسال</div>
        </div>
        <div class="stat-card card-yellow">
            <div class="value">{yellow_count}</div>
            <div class="label">🟡 يحتاج مراجعة</div>
        </div>
        <div class="stat-card card-red">
            <div class="value">{red_count}</div>
            <div class="label">🔴 مشبوه — قد يكون مكرراً</div>
        </div>
        <div class="stat-card card-blue">
            <div class="value">{found_count}</div>
            <div class="label">✅ موجود بالفعل</div>
        </div>
        <div class="stat-card card-purple">
            <div class="value">{total_count}</div>
            <div class="label">📊 إجمالي المنتجات من {competitors_count} منافس</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_product_card(row, show_checkbox=False, key_prefix=""):
    """عرض بطاقة منتج صغيرة."""
    img = row.get("image_url", "")
    name = row.get("product_name", "")
    price = row.get("price", 0)
    brand = row.get("brand", "")
    comp = row.get("competitor_name", "")
    conf = row.get("confidence_level", "green")
    score = row.get("confidence_score", 0)

    badge_class = f"conf-{conf}" if conf in ("green", "yellow", "red") else "conf-green"
    badge_text = {
        "green": "🟢 مفقود مؤكد",
        "yellow": "🟡 مراجعة",
        "red": "🔴 مشبوه",
    }.get(conf, "✅ موجود")

    return f"""
    <div style="display:flex; align-items:center; gap:12px; padding:8px 0; border-bottom:1px solid #2d2d4a;">
        <img src="{img}" style="width:50px; height:50px; border-radius:8px; object-fit:cover;" onerror="this.style.display='none'"/>
        <div style="flex:1;">
            <div style="font-weight:600; font-size:0.9rem;">{name[:80]}</div>
            <div style="font-size:0.78rem; opacity:0.7;">{brand} — {comp} — {price:.0f} ر.س</div>
        </div>
        <span class="conf-badge {badge_class}">{badge_text} ({score:.0f}%)</span>
    </div>
    """


# ═══════════════════════════════════════════════════════════════
#  الشريط الجانبي
# ═══════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown(f"### {APP_ICON} مهووس — المنتجات المفقودة")
    st.caption(APP_VERSION)
    st.divider()

    st.markdown("#### 📂 مصادر البيانات")

    st.markdown("**1. ملف متجر مهووس**")
    mahwous_file = st.file_uploader(
        "ارفع CSV لمتجر مهووس",
        type=["csv"],
        help="الملف الذي يحتوي على كامل منتجات متجرك (الصف الأول وصفي، الثاني هو الـ Header).",
        key="mahwous_upload",
    )

    st.markdown("**2. ملفات المنافسين**")
    competitor_files = st.file_uploader(
        "ارفع CSV للمنافسين (حتى 15 ملف)",
        type=["csv"],
        accept_multiple_files=True,
        help="سيتم استخلاص اسم المنافس تلقائياً من اسم الملف.",
        key="comp_upload",
    )

    st.divider()

    # خيارات متقدمة
    with st.expander("⚙️ خيارات متقدمة"):
        use_ai = st.checkbox(
            "تفعيل التحقق بالذكاء الاصطناعي (Gemini)",
            value=False,
            help="يستخدم Gemini للتحقق من الحالات المشبوهة. يتطلب مفتاح API.",
        )
        custom_webhook = st.text_input(
            "رابط Webhook مخصص (اختياري)",
            value="",
            help="اتركه فارغاً لاستخدام الرابط الافتراضي.",
        )

    st.divider()

    analyze_btn = st.button(
        "🔍 بدء التحليل والمقارنة",
        type="primary",
        use_container_width=True,
        disabled=(mahwous_file is None or not competitor_files),
    )

    if not mahwous_file or not competitor_files:
        st.info("📎 ارفع الملفات أعلاه لتفعيل زر التحليل.")


# ═══════════════════════════════════════════════════════════════
#  منطق التحليل الرئيسي
# ═══════════════════════════════════════════════════════════════

render_header()

if analyze_btn or ("all_results" in st.session_state):

    if analyze_btn:
        # — تحميل بيانات مهووس —
        with st.spinner("📦 جاري تحميل بيانات متجر مهووس..."):
            mahwous_df = load_mahwous_store_data(mahwous_file)

        if mahwous_df is None or mahwous_df.empty:
            st.error("❌ فشل تحميل ملف مهووس. تأكد من صحة الملف وبنية الأعمدة.")
            st.stop()

        st.success(f"✅ تم تحميل {len(mahwous_df):,} منتج من متجر مهووس")

        # — تحميل بيانات المنافسين —
        with st.spinner(f"📦 جاري تحميل بيانات {len(competitor_files)} منافس..."):
            competitors_data = load_competitor_data(competitor_files)

        if not competitors_data:
            st.error("❌ فشل تحميل ملفات المنافسين.")
            st.stop()

        # — تشغيل محرك المطابقة —
        progress_placeholder = st.empty()
        status_text = st.empty()

        def _progress_cb(current, total, label):
            pct = current / max(total, 1)
            progress_placeholder.progress(pct, text=f"🔍 تحليل {current}/{total} منتج...")

        with st.spinner("🧠 جاري تشغيل محرك المطابقة الذكي..."):
            all_results = process_competitors(
                mahwous_df, competitors_data,
                use_ai=use_ai,
                progress_callback=_progress_cb,
            )

        progress_placeholder.empty()
        status_text.empty()

        if all_results.empty:
            st.warning("لم يتم العثور على أي نتائج. تأكد من صحة ملفات المنافسين.")
            st.stop()

        # — تصنيف النتائج —
        st.session_state["all_results"] = all_results
        st.session_state["mahwous_count"] = len(mahwous_df)
        st.session_state["competitors_count"] = len(competitors_data)

        st.success(f"✅ اكتمل التحليل — تم فحص {len(all_results):,} منتج")

    # — استرجاع النتائج —
    all_results = st.session_state.get("all_results", pd.DataFrame())
    mahwous_count = st.session_state.get("mahwous_count", 0)
    competitors_count = st.session_state.get("competitors_count", 0)

    if all_results.empty:
        st.info("لا توجد نتائج للعرض.")
        st.stop()

    # تصنيف حسب مستوى الثقة
    green_df = all_results[all_results["confidence_level"] == "green"].copy()
    yellow_df = all_results[all_results["confidence_level"] == "yellow"].copy()
    red_df = all_results[all_results["confidence_level"] == "red"].copy()
    found_df = all_results[all_results["confidence_level"] == "found"].copy()

    # ═══════════════════════════════════════════════════════════
    #  الإحصائيات
    # ═══════════════════════════════════════════════════════════
    render_stats(
        len(green_df), len(yellow_df), len(red_df), len(found_df),
        len(all_results), competitors_count
    )

    st.divider()

    # ═══════════════════════════════════════════════════════════
    #  الأقسام الرئيسية (Tabs)
    # ═══════════════════════════════════════════════════════════

    tab1, tab2, tab3, tab4 = st.tabs([
        f"🟢 مفقود مؤكد ({len(green_df)})",
        f"🟡 يحتاج مراجعة ({len(yellow_df)})",
        f"🔴 مشبوه ({len(red_df)})",
        f"✅ موجود بالفعل ({len(found_df)})",
    ])

    # ══════════════ القسم 1: مفقود مؤكد ══════════════
    with tab1:
        st.markdown("### 🟢 منتجات مفقودة مؤكدة — جاهزة للإرسال إلى Make.com")
        st.caption("هذه المنتجات غير موجودة في متجرك بنسبة ثقة عالية.")

        if green_df.empty:
            st.success("🎉 ممتاز! لم يتم العثور على أي منتجات مفقودة مؤكدة.")
        else:
            # — فلاتر —
            with st.expander("🔧 فلاتر البحث المتقدمة", expanded=False):
                fc1, fc2, fc3, fc4 = st.columns(4)
                with fc1:
                    g_comp_filter = st.multiselect(
                        "المنافس",
                        sorted(green_df["competitor_name"].unique()),
                        key="g_comp"
                    )
                with fc2:
                    g_brand_filter = st.multiselect(
                        "الماركة",
                        sorted(green_df["brand"].dropna().unique()),
                        key="g_brand"
                    )
                with fc3:
                    max_price = max(int(green_df["price"].max() + 1), 100)
                    g_price = st.slider(
                        "نطاق السعر (ر.س)",
                        0, max_price, (0, max_price),
                        key="g_price"
                    )
                with fc4:
                    g_type_filter = st.multiselect(
                        "النوع",
                        ["تستر", "طقم/مجموعة", "عادي"],
                        key="g_type"
                    )

            # تطبيق الفلاتر
            filtered_green = green_df.copy()
            if g_comp_filter:
                filtered_green = filtered_green[filtered_green["competitor_name"].isin(g_comp_filter)]
            if g_brand_filter:
                filtered_green = filtered_green[filtered_green["brand"].isin(g_brand_filter)]
            filtered_green = filtered_green[
                (filtered_green["price"] >= g_price[0]) &
                (filtered_green["price"] <= g_price[1])
            ]
            if g_type_filter:
                masks = []
                if "تستر" in g_type_filter:
                    masks.append(filtered_green["is_tester"] == True)
                if "طقم/مجموعة" in g_type_filter:
                    masks.append(filtered_green["is_set"] == True)
                if "عادي" in g_type_filter:
                    masks.append((filtered_green["is_tester"] == False) & (filtered_green["is_set"] == False))
                if masks:
                    combined = masks[0]
                    for m in masks[1:]:
                        combined = combined | m
                    filtered_green = filtered_green[combined]

            st.caption(f"يُعرض {len(filtered_green)} منتج من أصل {len(green_df)}")

            # إضافة عمود الاختيار
            display_cols = ["product_name", "price", "image_url", "brand", "competitor_name", "confidence_score", "size", "type"]
            display_df = filtered_green[
                [c for c in display_cols if c in filtered_green.columns]
            ].copy()
            display_df.insert(0, "اختر", False)

            # الجدول التفاعلي
            edited_df = st.data_editor(
                display_df,
                column_config={
                    "اختر": st.column_config.CheckboxColumn("✅", default=False, width="small"),
                    "product_name": st.column_config.TextColumn("اسم المنتج", width="large"),
                    "price": st.column_config.NumberColumn("السعر", format="%.0f ر.س", width="small"),
                    "image_url": st.column_config.ImageColumn("الصورة", width="small"),
                    "brand": st.column_config.TextColumn("الماركة", width="medium"),
                    "competitor_name": st.column_config.TextColumn("المنافس", width="medium"),
                    "confidence_score": st.column_config.ProgressColumn(
                        "نسبة التشابه", format="%d%%", min_value=0, max_value=100, width="small"
                    ),
                    "size": st.column_config.TextColumn("الحجم", width="small"),
                    "type": st.column_config.TextColumn("النوع", width="small"),
                },
                hide_index=True,
                use_container_width=True,
                key="green_editor",
            )

            selected = edited_df[edited_df["اختر"] == True]
            selected_indices = selected.index.tolist()

            # استرجاع البيانات الكاملة للمنتجات المحددة
            if selected_indices:
                selected_full = filtered_green.iloc[
                    [filtered_green.index.get_loc(i) if i in filtered_green.index
                     else -1 for i in selected_indices]
                ]
                # في حالة عدم تطابق الفهارس
                selected_full = filtered_green.loc[
                    filtered_green.index.isin(selected_indices)
                ] if not selected_full.empty else pd.DataFrame()
            else:
                selected_full = pd.DataFrame()

            st.divider()

            # — أزرار الإرسال والتصدير —
            btn_col1, btn_col2, btn_col3 = st.columns([0.4, 0.3, 0.3])

            with btn_col1:
                if not selected.empty:
                    st.info(f"📦 تم تحديد **{len(selected)} منتج** للإرسال")
                else:
                    st.warning("حدد منتجاً واحداً على الأقل من الجدول أعلاه.")

            with btn_col2:
                send_disabled = selected.empty
                if st.button(
                    "🚀 إرسال إلى Make.com",
                    type="primary",
                    use_container_width=True,
                    disabled=send_disabled,
                    key="send_btn",
                ):
                    # تجهيز البيانات للإرسال
                    products_to_send = []
                    for idx in selected_indices:
                        if idx in filtered_green.index:
                            r = filtered_green.loc[idx]
                            products_to_send.append({
                                "product_name": r.get("product_name", ""),
                                "price": r.get("price", 0),
                                "image_url": r.get("image_url", ""),
                                "description": f"عطر من {r.get('brand', '')} — {r.get('type', '')} {r.get('size', '')}".strip(),
                                "sku": "",
                            })

                    if products_to_send:
                        webhook = custom_webhook if custom_webhook else ""
                        result = send_products_to_make(products_to_send, webhook_url=webhook)
                        if result["success"]:
                            st.success(result["message"])
                            st.balloons()
                        else:
                            st.error(result["message"])

            with btn_col3:
                if not filtered_green.empty:
                    csv_data = filtered_green.drop(
                        columns=["confidence_level"], errors="ignore"
                    ).to_csv(index=False).encode("utf-8-sig")
                    st.download_button(
                        "📥 تصدير CSV",
                        data=csv_data,
                        file_name=f"missing_products_{datetime.now():%Y%m%d}.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )

            # — معاينة Payload —
            if not selected.empty:
                with st.expander("👁️ معاينة بنية Payload الأول (Make.com)"):
                    if selected_indices:
                        first_idx = selected_indices[0]
                        if first_idx in filtered_green.index:
                            sample = filtered_green.loc[first_idx]
                            payload = build_payload({
                                "product_name": sample.get("product_name", ""),
                                "price": sample.get("price", 0),
                                "image_url": sample.get("image_url", ""),
                                "description": f"عطر من {sample.get('brand', '')}",
                                "sku": "",
                            })
                            st.markdown(f'<div class="preview-box">{json.dumps(payload, ensure_ascii=False, indent=2)}</div>', unsafe_allow_html=True)

    # ══════════════ القسم 2: يحتاج مراجعة ══════════════
    with tab2:
        st.markdown("### 🟡 منتجات تحتاج مراجعة — قد تكون موجودة بأسماء مختلفة")
        st.caption("نسبة التشابه بين 60-75%. راجعها يدوياً قبل اتخاذ أي قرار.")

        if yellow_df.empty:
            st.success("لا توجد منتجات تحتاج مراجعة.")
        else:
            for idx, row in yellow_df.iterrows():
                with st.container():
                    c1, c2, c3 = st.columns([0.6, 0.25, 0.15])
                    with c1:
                        st.markdown(f"**{row['product_name'][:80]}**")
                        st.caption(f"المنافس: {row['competitor_name']} | السعر: {row['price']:.0f} ر.س | الماركة: {row['brand']}")
                        if row.get("note"):
                            st.markdown(f"<small>{row['note'][:100]}</small>", unsafe_allow_html=True)
                        if row.get("variant_info"):
                            st.info(f"ℹ️ {row['variant_info']}")
                    with c2:
                        img = row.get("image_url", "")
                        if img and img.startswith("http"):
                            st.image(img, width=80)
                    with c3:
                        col_a, col_b = st.columns(2)
                        with col_a:
                            if st.button("✅ نفسه", key=f"same_{idx}", help="هذا المنتج موجود في متجرنا"):
                                matched = row.get("note", "").replace("⚠️ مشابه", "").strip()
                                save_alias(row["product_name"], matched)
                                st.success("تم حفظ الربط!")
                                st.rerun()
                        with col_b:
                            if st.button("❌ مختلف", key=f"diff_{idx}", help="هذا منتج مختلف"):
                                # نقله إلى المفقودات
                                if "all_results" in st.session_state:
                                    st.session_state["all_results"].loc[idx, "confidence_level"] = "green"
                                    st.success("تم نقله للمفقودات!")
                                    st.rerun()
                    st.divider()

    # ══════════════ القسم 3: مشبوه ══════════════
    with tab3:
        st.markdown("### 🔴 منتجات مشبوهة — احتمال تكرار عالٍ")
        st.caption("هذه المنتجات لها تشابه ملحوظ مع منتجات في متجرنا. راجعها بعناية.")

        if red_df.empty:
            st.success("لا توجد منتجات مشبوهة.")
        else:
            st.dataframe(
                red_df[["product_name", "price", "image_url", "competitor_name",
                         "confidence_score", "brand", "note", "variant_info", "variant_product"]],
                column_config={
                    "product_name": st.column_config.TextColumn("اسم المنتج المنافس", width="large"),
                    "image_url": st.column_config.ImageColumn("الصورة", width="small"),
                    "confidence_score": st.column_config.ProgressColumn(
                        "نسبة التشابه", format="%d%%", min_value=0, max_value=100
                    ),
                    "competitor_name": st.column_config.TextColumn("المنافس"),
                    "price": st.column_config.NumberColumn("السعر", format="%.0f ر.س"),
                    "brand": st.column_config.TextColumn("الماركة"),
                    "note": st.column_config.TextColumn("ملاحظة", width="large"),
                    "variant_info": st.column_config.TextColumn("نوع متاح"),
                    "variant_product": st.column_config.TextColumn("المنتج المتاح"),
                },
                hide_index=True,
                use_container_width=True,
            )

    # ══════════════ القسم 4: موجود بالفعل ══════════════
    with tab4:
        st.markdown("### ✅ منتجات موجودة في متجرنا — تم التحقق منها")
        st.caption("هذه المنتجات موجودة بالفعل بنسبة تطابق عالية. لا حاجة لإضافتها.")

        if found_df.empty:
            st.info("لم يتم العثور على تطابقات.")
        else:
            # فلتر سريع
            found_comp = st.multiselect(
                "تصفية حسب المنافس",
                sorted(found_df["competitor_name"].unique()),
                key="found_comp"
            )
            display_found = found_df if not found_comp else found_df[found_df["competitor_name"].isin(found_comp)]

            st.dataframe(
                display_found[["product_name", "price", "image_url", "competitor_name",
                                "confidence_score", "matched_product"]],
                column_config={
                    "product_name": st.column_config.TextColumn("اسم المنتج المنافس", width="large"),
                    "image_url": st.column_config.ImageColumn("الصورة", width="small"),
                    "confidence_score": st.column_config.ProgressColumn(
                        "نسبة التطابق", format="%d%%", min_value=0, max_value=100
                    ),
                    "competitor_name": st.column_config.TextColumn("المنافس"),
                    "price": st.column_config.NumberColumn("السعر", format="%.0f ر.س"),
                    "matched_product": st.column_config.TextColumn("المنتج المطابق في مهووس", width="large"),
                },
                hide_index=True,
                use_container_width=True,
            )

            st.caption(f"إجمالي: {len(display_found)} منتج متطابق")

else:
    # ═══════════════════════════════════════════════════════════
    #  صفحة الترحيب
    # ═══════════════════════════════════════════════════════════

    st.markdown("""
    <div style="text-align:center; padding:40px 20px;">
        <div style="font-size:4rem; margin-bottom:16px;">🌬️</div>
        <h2 style="color:#e8e8ff; margin-bottom:8px;">مرحباً بك في نظام المنتجات المفقودة</h2>
        <p style="color:#8888aa; font-size:1.1rem;">ارفع ملفات CSV في الشريط الجانبي واضغط "بدء التحليل" للبدء</p>
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns(2)

    with c1:
        with st.expander("📖 كيفية الاستخدام", expanded=True):
            st.markdown("""
**الخطوات:**
1. ارفع ملف CSV لمتجر مهووس (يحتوي على كامل منتجاتك).
2. ارفع ملفات CSV للمنافسين (حتى 15 ملف).
3. اضغط "بدء التحليل والمقارنة".
4. راجع النتائج في الأقسام الأربعة.
5. حدد المنتجات المفقودة وأرسلها إلى Make.com.
            """)

    with c2:
        with st.expander("🧠 آلية التحقق الذكية", expanded=True):
            st.markdown("""
**المحرك يعمل بـ 5 طبقات:**
1. **تطبيع عدواني** — توحيد الأسماء عربي/إنجليزي.
2. **استخلاص المكونات** — الماركة، الحجم، النوع، التستر.
3. **مطابقة ذكية** — `token_set_ratio` مع مكافآت وعقوبات.
4. **كشف البدائل** — هل لدينا التستر فقط؟ أو حجم مختلف؟
5. **ذاكرة الأسماء** — تعلّم من مراجعاتك السابقة.

**مستويات الثقة:**
- 🟢 **مفقود مؤكد** — جاهز للإرسال
- 🟡 **يحتاج مراجعة** — تشابه جزئي
- 🔴 **مشبوه** — احتمال تكرار عالٍ
- ✅ **موجود** — تم التحقق منه
            """)

    # فحص اتصال Make.com
    with st.expander("🔌 فحص اتصال Make.com"):
        if st.button("فحص الاتصال", key="test_webhook"):
            with st.spinner("جاري الفحص..."):
                result = verify_webhook()
            if result["success"]:
                st.success(result["message"])
            else:
                st.error(result["message"])
        st.caption(f"Webhook: `{WEBHOOK_NEW_PRODUCTS[:50]}...`")

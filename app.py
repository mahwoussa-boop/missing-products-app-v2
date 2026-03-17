"""
app.py v14.8 — الواجهة السيادية المتكاملة (النسخة الضخمة الشاملة + المنطق الهجين الصارم)
══════════════════════════════════════════════════════════════════════
- جميع ميزات V10 + V12 + V13 + V14.5 محفوظة بالكامل.
- شريط تقدم (Progress Bar) لحظي دقيق ومؤشر حالة.
- نظام صفحات (25 منتج/صفحة) لكل قسم بشكل مستقل.
- فلاتر شاملة (البحث، المنافس، الماركة) لكل تبويب.
- نظام حماية الصور (HTML Rendering) لمنع تعطل الواجهة.
- سحب تلقائي للصور المفقودة وتوليد وصف "خبير مهووس" عند الإرسال لـ Make.
- عرض المتاجر المتعددة (Tags) داخل بطاقة المنتج الواحد.
- دمج المنطق الهجين الصارم: تمرير رابط صورة المنافس للدالة الهجينة.
"""

import streamlit as st
import pandas as pd
import asyncio
import time
import math
import urllib.parse

from config import APP_TITLE, APP_VERSION, APP_ICON
from db_manager import load_mahwous_store_data, load_competitor_data
from sovereign_matcher import start_sovereign_analysis, ai_verify_match
from make_sender import send_products_to_make

# استيراد أدوات الذكاء الاصطناعي
from ai_engine import (
    fetch_product_images, 
    fetch_fragrantica_info, 
    generate_mahwous_description, 
    search_market_price, 
    search_mahwous
)

# 1. إعدادات الصفحة (يجب أن تكون في السطر الأول)
st.set_page_config(page_title=f"{APP_TITLE} {APP_VERSION}", page_icon=APP_ICON, layout="wide")

# 2. تهيئة Session State لضمان عدم ضياع البيانات أو الحالة
if 'analysis_running' not in st.session_state: st.session_state.analysis_running = False
if 'processed_count' not in st.session_state: st.session_state.processed_count = 0
if 'total_count' not in st.session_state: st.session_state.total_count = 0
if 'analysis_results' not in st.session_state: st.session_state.analysis_results = []
if 'ignore_list' not in st.session_state: st.session_state.ignore_list = set()
if 'needs_rerun' not in st.session_state: st.session_state.needs_rerun = False
if 'ai_verifications' not in st.session_state: st.session_state.ai_verifications = {}

# فصل التحديد الجماعي لكل قسم
if 'selected_green' not in st.session_state: st.session_state.selected_green = set()
if 'selected_yellow' not in st.session_state: st.session_state.selected_yellow = set()

# تهيئة أرقام الصفحات لكل تبويب بشكل مستقل
if 'page_green' not in st.session_state: st.session_state.page_green = 1
if 'page_yellow' not in st.session_state: st.session_state.page_yellow = 1
if 'page_red' not in st.session_state: st.session_state.page_red = 1

# دوال التنقل بين الصفحات
def next_page(key): st.session_state[key] += 1
def prev_page(key): st.session_state[key] -= 1

def render_image(url, width=150):
    """حماية وعرض الصور: معالجة الروابط المعطوبة وعرض صورة بديلة آمنة"""
    if pd.isna(url) or not url:
        url = "https://via.placeholder.com/150?text=No+Image"
    return f'<img src="{url}" onerror="this.onerror=null;this.src=\'https://via.placeholder.com/150?text=Image+Locked\';" style="width:100%; max-width:{width}px; border-radius:8px; object-fit:contain; border: 1px solid #2d3748; padding: 5px; background: #0e1117;">'

# 🎛️ CSS مخصص للهوية البصرية لمتجر مهووس
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap');
    html, body, [class*="st-"] { font-family: 'Cairo', sans-serif; }
    .stApp { direction: rtl; }
    .price-text { color: #00d2ff; font-weight: bold; font-size: 1.2rem; }
    .match-score { font-size: 1.1rem; font-weight: 800; padding: 5px 10px; border-radius: 5px; }
    .score-yellow { color: #ffc107; background: rgba(255, 193, 7, 0.1); }
    .score-red { color: #dc3545; background: rgba(220, 53, 69, 0.1); }
    .competitor-tag { background: #1e3a5f; color: #ffffff; padding: 3px 10px; border-radius: 15px; font-size: 0.85rem; margin-left: 5px; margin-bottom: 5px; display: inline-block; border: 1px solid #00d2ff;}
    .stProgress > div > div > div > div { background-image: linear-gradient(to right, #4facfe 0%, #00f2fe 100%); }
    .product-card { border: 1px solid #2d3748; border-radius: 10px; padding: 20px; background: #1a1a2e; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

def main():
    st.title(f"{APP_ICON} {APP_TITLE}")
    st.markdown(f"<p style='color: #a0aec0;'>إصدار مهندس نظام مهووس الذكي الشامل {APP_VERSION}</p>", unsafe_allow_html=True)

    # ─── الشريط الجانبي (إدارة البيانات والتحكم) ───
    with st.sidebar:
        st.header("📂 لوحة البيانات")
        mahwous_file = st.file_uploader("ملف متجر مهووس (المرجع الرئيسي)", type=["csv"])
        competitor_files = st.file_uploader("ملفات المنافسين (متعدد)", type=["csv"], accept_multiple_files=True)
        
        st.divider()
        
        if st.button("🚀 بدء التحليل السيادي", key="start_btn", type="primary", use_container_width=True, disabled=st.session_state.analysis_running):
            if mahwous_file and competitor_files:
                try:
                    st.session_state.analysis_running = True
                    st.session_state.processed_count = 0
                    st.session_state.total_count = 0
                    st.session_state.analysis_results = []
                    
                    with st.spinner("جاري تهيئة المحرك وتصفية البيانات..."):
                        m_df = load_mahwous_store_data(mahwous_file)
                        c_data = {f.name: load_competitor_data(f) for f in competitor_files}
                        start_sovereign_analysis(m_df, c_data)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ حدث عطل أثناء التجهيز: {e}")
                    st.session_state.analysis_running = False
            else:
                st.warning("⚠️ يرجى رفع الملفات المطلوبة للبدء.")
        
        if st.session_state.analysis_running:
            if st.button("🛑 إيقاف التحليل فوراً", use_container_width=True, type="secondary"):
                st.session_state.analysis_running = False
                st.rerun()

    # ─── شريط التقدم اللحظي (Progress Bar) ───
    if st.session_state.analysis_running:
        st.divider()
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        if st.session_state.total_count > 0:
            progress_val = min(st.session_state.processed_count / st.session_state.total_count, 1.0)
            progress_bar.progress(progress_val)
            status_text.info(f"⏳ جاري فحص ومطابقة المنتجات: {st.session_state.processed_count} من {st.session_state.total_count} ({int(progress_val*100)}%)")
            time.sleep(0.5)
            st.rerun()
        else:
            status_text.warning("🔄 جاري تجميع البيانات من ملفات المنافسين... يرجى الانتظار")
            time.sleep(0.5)
            st.rerun()

    # إعادة تشغيل الواجهة عند اكتمال التحليل بالخلفية
    if st.session_state.needs_rerun:
        st.session_state.needs_rerun = False
        st.rerun()

    # ─── لوحة النتائج الرئيسية ───
    if not st.session_state.analysis_running and st.session_state.analysis_results:
        # تحويل النتائج لـ DataFrame وتطبيق قائمة التجاهل
        results_df = pd.DataFrame(st.session_state.analysis_results)
        results_df = results_df[~results_df['product_name'].isin(st.session_state.ignore_list)]
        
        if results_df.empty:
            st.info("لم يتم العثور على منتجات مطابقة للمعايير.")
            return

        # إحصائيات علوية سريعة
        stat1, stat2, stat3, stat4 = st.columns(4)
        stat1.metric("إجمالي المنتجات", len(results_df))
        stat2.metric("🟢 مفقود أكيد", len(results_df[results_df['confidence_level'] == 'green']))
        stat3.metric("🟡 مراجعة بصرية", len(results_df[results_df['confidence_level'] == 'yellow']))
        stat4.metric("🔴 مكرر/متوفر", len(results_df[results_df['confidence_level'] == 'red']))

        # تقسيم التبويبات بنسب التأكد المطلوبة
        tab_missing, tab_review, tab_matched = st.tabs([
            f"🟢 مفقودة (تأكد 95%-100%) ({len(results_df[results_df['confidence_level'] == 'green'])})", 
            f"🟡 مراجعة بصرية (شک 80%-95%) ({len(results_df[results_df['confidence_level'] == 'yellow'])})", 
            f"🔴 مكررة (تأكد 90%-100%) ({len(results_df[results_df['confidence_level'] == 'red'])})"
        ])

        # دالة الفلترة الديناميكية
        def get_filter_options(df_part, col):
            if col == 'competitor_name':
                items = []
                for s in df_part[col].dropna(): items.extend([x.strip() for x in str(s).split('،')])
                return ["الكل"] + sorted(list(set(items)))
            return ["الكل"] + sorted([str(x) for x in df_part[col].dropna().unique() if str(x).strip()])

        ITEMS_PER_PAGE = 25

        # =========================================================
        # 🟢 التبويب الأول: منتجات مفقودة (عرض المنافس فقط)
        # =========================================================
        with tab_missing:
            df_g = results_df[results_df['confidence_level'] == 'green']
            
            f1, f2, f3 = st.columns(3)
            with f1: s_g = st.text_input("🔍 بحث بالاسم...", key="s_g")
            with f2: c_g = st.selectbox("🏬 فلترة المنافس", get_filter_options(df_g, 'competitor_name'), key="c_g")
            with f3: b_g = st.selectbox("🏷️ فلترة الماركة", get_filter_options(df_g, 'brand'), key="b_g")
            
            if s_g: df_g = df_g[df_g['product_name'].str.contains(s_g, case=False, na=False)]
            if c_g != "الكل": df_g = df_g[df_g['competitor_name'].str.contains(c_g, case=False, na=False)]
            if b_g != "الكل": df_g = df_g[df_g['brand'].astype(str) == b_g]

            if not df_g.empty:
                # نظام الصفحات
                total_p_g = math.ceil(len(df_g) / ITEMS_PER_PAGE)
                if st.session_state.page_green > total_p_g: st.session_state.page_green = total_p_g
                
                # التحكم الجماعي والصفحات
                ctrl1, ctrl2, nav1, nav2, nav3 = st.columns([2, 2, 1, 1, 1])
                with ctrl1:
                    if st.button("🚀 إرسال المحدد لـ Make", key="bulk_g", type="primary", use_container_width=True):
                        selected = [r for _, r in df_g.iterrows() if r['product_name'] in st.session_state.selected_green]
                        if selected:
                            with st.spinner("جاري معالجة الصور والوصف بالنظام الهجين..."):
                                payloads = []
                                for r in selected:
                                    r_dict = r.to_dict()
                                    # المنطق الهجين الصارم: توليد الوصف وسحب الصور
                                    r_dict['description'] = generate_mahwous_description(r['product_name'], r['price'], r.get('brand', ''))
                                    img_res = fetch_product_images(r['product_name'], r.get('brand', ''), r.get('image_url'))
                                    if img_res['success']:
                                        r_dict['image_url'] = img_res['images'][0]['url']
                                        r_dict['all_images'] = [img['url'] for img in img_res['images']]
                                    payloads.append(r_dict)
                                res = send_products_to_make(payloads)
                                if res['success']: st.success(res['message'])
                                else: st.error(res['message'])
                        else: st.warning("قم بتحديد المنتجات أولاً.")
                
                with nav1: st.button("⬅️ السابق", key="prev_g", on_click=prev_page, args=("page_green",), disabled=(st.session_state.page_green == 1))
                with nav2: st.markdown(f"<p style='text-align:center; padding-top:5px;'>{st.session_state.page_green} / {total_p_g}</p>", unsafe_allow_html=True)
                with nav3: st.button("التالي ➡️", key="next_g", on_click=next_page, args=("page_green",), disabled=(st.session_state.page_green == total_p_g))

                st.divider()

                # عرض المنتجات
                start_idx = (st.session_state.page_green - 1) * ITEMS_PER_PAGE
                for idx, row in df_g.iloc[start_idx : start_idx + ITEMS_PER_PAGE].iterrows():
                    with st.container():
                        st.markdown(f'<div class="product-card">', unsafe_allow_html=True)
                        c_chk, c_img, c_info = st.columns([0.5, 2, 7])
                        
                        with c_chk:
                            if st.checkbox("", key=f"chk_g_{idx}", value=row['product_name'] in st.session_state.selected_green):
                                st.session_state.selected_green.add(row['product_name'])
                            elif row['product_name'] in st.session_state.selected_green:
                                st.session_state.selected_green.remove(row['product_name'])
                        
                        with c_img:
                            st.markdown(render_image(row.get('image_url')), unsafe_allow_html=True)
                        
                        with c_info:
                            st.subheader(row['product_name'])
                            st.markdown(f"<span class='price-text'>{row['price']} ر.س</span>", unsafe_allow_html=True)
                            
                            # عرض المنافسين بشكل أنيق
                            comp_list = str(row.get('competitor_name', '')).split('،')
                            comp_html = "".join([f"<span class='competitor-tag'>🏪 {c.strip()}</span>" for c in comp_list if c.strip()])
                            st.markdown(comp_html, unsafe_allow_html=True)
                            st.caption(f"🏷️ الماركة: {row.get('brand', 'غير محدد')}")
                            
                            # أزرار الإجراءات الفردية (6 أزرار كاملة)
                            b_cols = st.columns(6)
                            if b_cols[0].button("🖼️ صور", key=f"btn_img_g_{idx}"):
                                with st.spinner(".."):
                                    # المنطق الهجين: تمرير رابط صورة المنافس كبديل
                                    res = fetch_product_images(row['product_name'], row.get('brand', ''), row.get('image_url'))
                                    if res['success']: st.markdown(render_image(res['images'][0]['url'], 100), unsafe_allow_html=True)
                                    else: st.error("لم يتم العثور")
                            
                            if b_cols[1].button("🌸 مكونات", key=f"btn_frag_g_{idx}"):
                                with st.spinner(".."):
                                    res = fetch_fragrantica_info(row['product_name'])
                                    if res['success']: st.info(f"المكونات: {', '.join(res.get('top_notes', []))}")
                            
                            if b_cols[2].button("🔎 متوفر؟", key=f"btn_ai_g_{idx}"):
                                with st.spinner(".."):
                                    res = search_mahwous(row['product_name'])
                                    if res['success']: st.info(res.get('likely_available'))
                            
                            if b_cols[3].button("💹 السوق", key=f"btn_prc_g_{idx}"):
                                with st.spinner(".."):
                                    res = search_market_price(row['product_name'], row['price'])
                                    if res['success']: st.info(f"متوسط السوق: {res.get('market_price')} ر.س")
                            
                            if b_cols[4].button("📤 إرسال", key=f"btn_send_g_{idx}", type="primary"):
                                try:
                                    with st.spinner("يولد الوصف ويرسل..."):
                                        row_dict = row.to_dict()
                                        # المنطق الهجين الصارم: توليد الوصف وسحب الصور
                                        row_dict['description'] = generate_mahwous_description(row['product_name'], row['price'], row.get('brand', ''))
                                        img_res = fetch_product_images(row['product_name'], row.get('brand', ''), row.get('image_url'))
                                        if img_res['success']:
                                            row_dict['image_url'] = img_res['images'][0]['url']
                                            row_dict['all_images'] = [img['url'] for img in img_res['images']]
                                        
                                        res = send_products_to_make([row_dict])
                                        if res['success']: st.toast("تم الإرسال لـ Make بنجاح!", icon="✅")
                                        else: st.error(res['message'])
                                except Exception as e: st.error(f"خطأ: {e}")

                            if b_cols[5].button("🗑️", key=f"btn_ign_g_{idx}"):
                                st.session_state.ignore_list.add(row['product_name'])
                                st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)

        # =========================================================
        # 🟡 التبويب الثاني: مراجعة بصرية (مقارنة المنافس vs مهووس)
        # =========================================================
        with tab_review:
            df_y = results_df[results_df['confidence_level'] == 'yellow']
            fy1, fy2, fy3 = st.columns(3)
            with fy1: sy_y = st.text_input("🔍 بحث بالمراجعة...", key="sy_y")
            with fy2: cy_y = st.selectbox("🏬 منافس", get_filter_options(df_y, 'competitor_name'), key="cy_y")
            with fy3: by_y = st.selectbox("🏷️ ماركة", get_filter_options(df_y, 'brand'), key="by_y")
            
            if sy_y: df_y = df_y[df_y['product_name'].str.contains(sy_y, case=False, na=False)]
            if cy_y != "الكل": df_y = df_y[df_y['competitor_name'].str.contains(cy_y, case=False, na=False)]
            if by_y != "الكل": df_y = df_y[df_y['brand'].astype(str) == by_y]

            if not df_y.empty:
                total_p_y = math.ceil(len(df_y) / ITEMS_PER_PAGE)
                if st.session_state.page_yellow > total_p_y: st.session_state.page_yellow = total_p_y
                
                nav_y1, nav_y2, nav_y3 = st.columns([1, 2, 1])
                with nav_y1: st.button("⬅️", key="p_y", on_click=prev_page, args=("page_yellow",), disabled=(st.session_state.page_yellow == 1))
                with nav_y2: st.markdown(f"<p style='text-align:center;'>{st.session_state.page_yellow} / {total_p_y}</p>", unsafe_allow_html=True)
                with nav_y3: st.button("➡️", key="n_y", on_click=next_page, args=("page_yellow",), disabled=(st.session_state.page_yellow == total_p_y))

                st.divider()
                
                start_y = (st.session_state.page_yellow - 1) * ITEMS_PER_PAGE
                for idx, row in df_y.iloc[start_y : start_y + ITEMS_PER_PAGE].iterrows():
                    with st.container():
                        st.markdown(f'<div class="product-card">', unsafe_allow_html=True)
                        st.markdown(f"**شك بنسبة:** <span class='match-score score-yellow'>{row.get('match_score')}%</span>", unsafe_allow_html=True)
                        
                        comp_col, mah_col = st.columns(2)
                        with comp_col:
                            st.caption("🛒 عطر المنافس")
                            st.markdown(render_image(row.get('image_url')), unsafe_allow_html=True)
                            st.write(f"**{row['product_name']}**")
                            st.markdown(f"<span class='price-text'>{row['price']} ر.س</span>", unsafe_allow_html=True)
                            
                        with mah_col:
                            st.caption("📦 أقرب عطر لدينا (مهووس)")
                            st.markdown(render_image(row.get('match_image')), unsafe_allow_html=True)
                            st.write(f"**{row.get('match_name')}**")
                            st.markdown(f"<span class='price-text'>{row.get('match_price')} ر.س</span>", unsafe_allow_html=True)

                        st.divider()
                        btn_col = st.columns(5)
                        if btn_col[0].checkbox("تحديد", key=f"chk_y_{idx}", value=row['product_name'] in st.session_state.selected_yellow):
                            st.session_state.selected_yellow.add(row['product_name'])
                        
                        if btn_col[1].button("🤖 تحقق AI", key=f"ai_y_{idx}"):
                            res = asyncio.run(ai_verify_match(row['product_name'], row.get('match_name','')))
                            st.info(f"النتيجة: {res['reason']}")
                        
                        if btn_col[3].button("📤 إرسال لـ Make", key=f"send_y_{idx}", type="primary"):
                            with st.spinner("يولد الوصف ويرسل..."):
                                p_dict = row.to_dict()
                                # المنطق الهجين الصارم
                                p_dict['description'] = generate_mahwous_description(row['product_name'], row['price'], row.get('brand', ''))
                                img_res = fetch_product_images(row['product_name'], row.get('brand', ''), row.get('image_url'))
                                if img_res['success']:
                                    p_dict['image_url'] = img_res['images'][0]['url']
                                    p_dict['all_images'] = [img['url'] for img in img_res['images']]
                                res = send_products_to_make([p_dict])
                                if res['success']: st.toast("تم الإرسال!", icon="✅")
                                else: st.error(res['message'])

                        if btn_col[4].button("🗑️", key=f"ign_y_{idx}"):
                            st.session_state.ignore_list.add(row['product_name'])
                            st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)

        # =========================================================
        # 🔴 التبويب الثالث: منتجات متطابقة (تأكيد بصري)
        # =========================================================
        with tab_matched:
            df_r = results_df[results_df['confidence_level'] == 'red']
            
            fr1, fr2, fr3 = st.columns(3)
            with fr1: sr_r = st.text_input("🔍 بحث متطابقة...", key="sr_r")
            with fr2: cr_r = st.selectbox("🏬 منافس", get_filter_options(df_r, 'competitor_name'), key="cr_r")
            with fr3: br_r = st.selectbox("🏷️ ماركة", get_filter_options(df_r, 'brand'), key="br_r")
            
            if sr_r: df_r = df_r[df_r['product_name'].str.contains(sr_r, case=False, na=False)]
            if cr_r != "الكل": df_r = df_r[df_r['competitor_name'].str.contains(cr_r, case=False, na=False)]
            if br_r != "الكل": df_r = df_r[df_r['brand'].astype(str) == br_r]

            if not df_r.empty:
                total_p_r = math.ceil(len(df_r) / ITEMS_PER_PAGE)
                if st.session_state.page_red > total_p_r: st.session_state.page_red = total_p_r
                nav_r1, nav_r2, nav_r3 = st.columns([1, 2, 1])
                with nav_r1: st.button("⬅️", key="p_r", on_click=prev_page, args=("page_red",), disabled=(st.session_state.page_red == 1))
                with nav_r2: st.markdown(f"<p style='text-align:center;'>{st.session_state.page_red} / {total_p_r}</p>", unsafe_allow_html=True)
                with nav_r3: st.button("➡️", key="n_r", on_click=next_page, args=("page_red",), disabled=(st.session_state.page_red == total_p_r))

                st.divider()

                start_r = (st.session_state.page_red - 1) * ITEMS_PER_PAGE
                for idx, row in df_r.iloc[start_r : start_r + ITEMS_PER_PAGE].iterrows():
                    with st.container():
                        st.markdown(f'<div class="product-card">', unsafe_allow_html=True)
                        st.markdown(f"**متطابق بنسبة:** <span class='match-score score-red'>{row.get('match_score')}%</span>", unsafe_allow_html=True)
                        
                        c1, c2 = st.columns(2)
                        with c1:
                            st.caption("🛒 عطر المنافس")
                            st.markdown(render_image(row.get('image_url'), 120), unsafe_allow_html=True)
                            st.write(row['product_name'])
                        with c2:
                            st.caption("📦 عطر مهووس المتوفر")
                            st.markdown(render_image(row.get('match_image'), 120), unsafe_allow_html=True)
                            st.write(row.get('match_name'))
                        
                        st.divider()
                        act_col = st.columns(4)
                        if act_col[0].button("🤖 فحص دقة", key=f"ai_r_{idx}"):
                            res = asyncio.run(ai_verify_match(row['product_name'], row.get('match_name','')))
                            st.info(f"قرار AI: {res['reason']}")
                        
                        if act_col[1].button("💹 سعر السوق", key=f"prc_r_{idx}"):
                            res = search_market_price(row['product_name'], row['price'])
                            if res['success']: st.info(f"السوق: {res.get('market_price')} ر.س")
                        
                        if act_col[2].button("🗑️ إخفاء", key=f"ign_r_{idx}"):
                            st.session_state.ignore_list.add(row['product_name'])
                            st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()

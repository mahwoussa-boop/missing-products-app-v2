"""
app.py v12.0 — الواجهة الذكية المتفاعلة (نظام الصفحات، التقاط الأخطاء، وحماية الصور)
══════════════════════════════════════════════════════════════════════
- جميع ميزات V10 محفوظة (فلاتر، تحديد جماعي، توليد وصف، أزرار AI مفردة).
- تم إضافة نظام الصفحات (25 منتج/صفحة) لمنع التعليق.
- تم إضافة نظام حماية الصور (يستبدل الصورة المقفلة أو المكسورة تلقائياً).
- تم تغليف جميع الأزرار بنظام التقاط الأخطاء لمعرفة سبب أي عطل.
"""

import streamlit as st
import pandas as pd
import asyncio
import time
import math

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

# 2. تهيئة Session State الأساسية ومفاتيح الصفحات
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

# تهيئة أرقام الصفحات
if 'page_green' not in st.session_state: st.session_state.page_green = 1
if 'page_yellow' not in st.session_state: st.session_state.page_yellow = 1
if 'page_red' not in st.session_state: st.session_state.page_red = 1

# دوال التنقل بين الصفحات
def next_page(key): st.session_state[key] += 1
def prev_page(key): st.session_state[key] -= 1

def render_image(url, width=150):
    """حماية وعرض الصور: إذا كان الرابط تالفاً يعرض صورة بديلة بدل الخطأ"""
    if pd.isna(url) or not url:
        url = "https://via.placeholder.com/150?text=No+Image"
    return f'<img src="{url}" onerror="this.onerror=null;this.src=\'https://via.placeholder.com/150?text=Image+Locked\';" style="width:100%; max-width:{width}px; border-radius:8px; object-fit:contain; border: 1px solid #2d3748;">'

# CSS خفيف للترتيب بدون إفساد الوضع الليلي
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap');
    html, body, [class*="st-"] { font-family: 'Cairo', sans-serif; }
    .stApp { direction: rtl; }
    .price-text { color: #00d2ff; font-weight: bold; font-size: 1.2rem; }
    .match-score { font-size: 1.1rem; font-weight: 800; padding: 5px 10px; border-radius: 5px; }
    .score-yellow { color: #ffc107; background: rgba(255, 193, 7, 0.1); }
    .score-red { color: #dc3545; background: rgba(220, 53, 69, 0.1); }
</style>
""", unsafe_allow_html=True)

def main():
    st.title(f"{APP_ICON} {APP_TITLE} (النسخة 12.0 - المتكاملة)")
    st.markdown("محرك المطابقة السيادي وخبير المنتجات المفقودة")

    # ─── الشريط الجانبي (إدارة البيانات) ───
    with st.sidebar:
        st.header("📂 رفع البيانات")
        mahwous_file = st.file_uploader("ملف متجر مهووس (المرجع)", type=["csv"])
        competitor_files = st.file_uploader("ملفات المنافسين", type=["csv"], accept_multiple_files=True)
        
        if st.button("🚀 بدء التحليل", type="primary", use_container_width=True, disabled=st.session_state.analysis_running):
            if mahwous_file and competitor_files:
                try:
                    st.session_state.analysis_running = True
                    with st.spinner("جاري تهيئة البيانات والمحرك..."):
                        m_df = load_mahwous_store_data(mahwous_file)
                        c_data = {f.name: load_competitor_data(f) for f in competitor_files}
                        start_sovereign_analysis(m_df, c_data)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ خطأ أثناء رفع البيانات: {e}")
                    st.session_state.analysis_running = False
            else:
                st.error("الرجاء رفع الملفات أولاً.")
        
        if st.session_state.analysis_running:
            if st.button("🛑 إيقاف فوري", use_container_width=True):
                st.session_state.analysis_running = False
                st.rerun()

    # ─── شريط التقدم اللحظي ───
    progress_container = st.empty()
    if st.session_state.analysis_running:
        if st.session_state.total_count > 0:
            progress = min(st.session_state.processed_count / st.session_state.total_count, 1.0)
            progress_container.progress(progress, text=f"🚀 جاري الفحص: {st.session_state.processed_count} من {st.session_state.total_count}...")
            time.sleep(0.5)
            st.rerun()

    if st.session_state.needs_rerun:
        st.session_state.needs_rerun = False
        st.rerun()

    # ─── لوحة النتائج الرئيسية ───
    if not st.session_state.analysis_running and st.session_state.analysis_results:
        # تحويل البيانات واستبعاد المتجاهل
        df = pd.DataFrame(st.session_state.analysis_results)
        df = df[~df['product_name'].isin(st.session_state.ignore_list)]
        
        if df.empty:
            st.info("لا توجد بيانات لعرضها. جميع المنتجات تمت معالجتها أو تجاهلها.")
            return

        # إحصائيات علوية
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("إجمالي المنتجات", len(df))
        c2.metric("🟢 مفقود أكيد", len(df[df['confidence_level'] == 'green']))
        c3.metric("🟡 تتطلب مراجعة", len(df[df['confidence_level'] == 'yellow']))
        c4.metric("🔴 متطابقة", len(df[df['confidence_level'] == 'red']))

        # تقسيم التبويبات
        tab_green, tab_yellow, tab_red = st.tabs([
            f"🟢 منتجات مفقودة ({len(df[df['confidence_level'] == 'green'])})", 
            f"🟡 تتطلب مراجعة ({len(df[df['confidence_level'] == 'yellow'])})", 
            f"🔴 منتجات متطابقة ({len(df[df['confidence_level'] == 'red'])})"
        ])

        # دالة لاستخراج قائمة المنافسين لفلتر محدد
        def get_competitors_list(df_part):
            comps = []
            for comp_str in df_part['competitor_name'].dropna():
                comps.extend([c.strip() for c in str(comp_str).split('،')])
            return ["الكل"] + list(set(comps))

        ITEMS_PER_PAGE = 25

        # =========================================================
        # 🟢 القسم الأخضر: منتجات مفقودة (بدون مقارنة)
        # =========================================================
        with tab_green:
            df_g = df[df['confidence_level'] == 'green']
            
            # فلاتر القسم الأخضر
            cg1, cg2 = st.columns(2)
            with cg1: search_g = st.text_input("🔍 بحث في المفقودة...", key="search_g")
            with cg2: comp_g = st.selectbox("🏬 فلترة المنافسين (المفقودة)", get_competitors_list(df_g), key="comp_g")
            
            if search_g: df_g = df_g[df_g['product_name'].str.contains(search_g, case=False, na=False)]
            if comp_g != "الكل": df_g = df_g[df_g['competitor_name'].str.contains(comp_g, case=False, na=False)]

            if not df_g.empty:
                # نظام الصفحات للقسم الأخضر
                total_pages_g = math.ceil(len(df_g) / ITEMS_PER_PAGE)
                if st.session_state.page_green > total_pages_g: st.session_state.page_green = total_pages_g
                
                # أزرار التحكم الجماعي والتنقل
                col_bulk1, col_bulk2, col_pg1, col_pg2, col_pg3 = st.columns([2, 2, 1, 2, 1])
                with col_bulk1:
                    if st.button("🚀 إرسال المحدد لـ Make", key="bulk_g", type="primary"):
                        try:
                            selected = [row for _, row in df_g.iterrows() if row['product_name'] in st.session_state.selected_green]
                            if selected:
                                with st.spinner("جاري توليد الوصف والصور والإرسال..."):
                                    payloads = []
                                    for row in selected:
                                        p_dict = row.to_dict()
                                        p_dict['description'] = generate_mahwous_description(row['product_name'], row['price'])
                                        if not p_dict.get('image_url'):
                                            img_res = fetch_product_images(row['product_name'])
                                            if img_res['success'] and img_res['images']:
                                                p_dict['image_url'] = img_res['images'][0]['url']
                                        payloads.append(p_dict)
                                    res = send_products_to_make(payloads)
                                    if res['success']: st.success(res['message'])
                                    else: st.error(res['message'])
                            else:
                                st.warning("الرجاء تحديد منتج واحد على الأقل.")
                        except Exception as e:
                            st.error(f"❌ خطأ أثناء الإرسال الجماعي: {e}")
                
                # أزرار التنقل للصفحات
                with col_pg1: st.button("⬅️ السابق", key="pg_prev_g", on_click=prev_page, args=("page_green",), disabled=(st.session_state.page_green == 1))
                with col_pg2: st.markdown(f"<div style='text-align:center; padding-top:10px;'>صفحة {st.session_state.page_green} من {total_pages_g}</div>", unsafe_allow_html=True)
                with col_pg3: st.button("التالي ➡️", key="pg_next_g", on_click=next_page, args=("page_green",), disabled=(st.session_state.page_green == total_pages_g))

                st.divider()

                # استقطاع منتجات الصفحة الحالية
                start_idx_g = (st.session_state.page_green - 1) * ITEMS_PER_PAGE
                page_df_g = df_g.iloc[start_idx_g : start_idx_g + ITEMS_PER_PAGE]

                # عرض بطاقات المنتجات
                for idx, row in page_df_g.iterrows():
                    p_name = row['product_name']
                    p_price = row['price']
                    
                    with st.container(border=True):
                        c_chk, c_img, c_info = st.columns([0.5, 2, 7])
                        
                        with c_chk:
                            if st.checkbox("تحديد", key=f"chk_g_{idx}", value=p_name in st.session_state.selected_green):
                                st.session_state.selected_green.add(p_name)
                            elif p_name in st.session_state.selected_green:
                                st.session_state.selected_green.remove(p_name)
                        
                        with c_img:
                            st.markdown(render_image(row.get('image_url')), unsafe_allow_html=True)
                            
                        with c_info:
                            st.subheader(p_name)
                            st.markdown(f"<span class='price-text'>{p_price} ر.س</span>", unsafe_allow_html=True)
                            st.write(f"🏢 **متوفر لدى:** {row.get('competitor_name')}")
                            
                            # الأزرار الفردية مع التقاط الأخطاء
                            b_cols = st.columns(6)
                            if b_cols[0].button("🖼️ بحث صور", key=f"img_g_{idx}"):
                                try:
                                    with st.spinner(".."):
                                        res = fetch_product_images(p_name)
                                        if res['success'] and res['images']: st.markdown(render_image(res['images'][0]['url'], 100), unsafe_allow_html=True)
                                        else: st.warning("لم يتم العثور على صور.")
                                except Exception as e: st.error(f"خطأ: {e}")
                            
                            if b_cols[1].button("🌸 مكونات", key=f"not_g_{idx}"):
                                try:
                                    with st.spinner(".."):
                                        res = fetch_fragrantica_info(p_name)
                                        if res['success']: st.info(f"القمة: {', '.join(res.get('top_notes', []))}")
                                        else: st.warning("لم يتم العثور على مكونات.")
                                except Exception as e: st.error(f"خطأ: {e}")
                            
                            if b_cols[2].button("🔎 هل متوفر لدينا؟", key=f"chk_g_ai_{idx}"):
                                try:
                                    with st.spinner(".."):
                                        res = search_mahwous(p_name)
                                        if res['success']: st.info(res.get('likely_available'))
                                except Exception as e: st.error(f"خطأ: {e}")
                            
                            if b_cols[3].button("💹 تسعيرة السوق", key=f"prc_g_{idx}"):
                                try:
                                    with st.spinner(".."):
                                        res = search_market_price(p_name, p_price)
                                        if res['success']: st.info(f"متوسط السوق: {res.get('market_price')} ر.س")
                                except Exception as e: st.error(f"خطأ: {e}")
                            
                            if b_cols[4].button("📤 إرسال مفرد", key=f"snd_g_{idx}", type="primary"):
                                try:
                                    with st.spinner("يولد الوصف ويرسل..."):
                                        p_dict = row.to_dict()
                                        p_dict['description'] = generate_mahwous_description(p_name, p_price)
                                        res = send_products_to_make([p_dict])
                                        if res['success']: st.toast("تم الإرسال!", icon="✅")
                                        else: st.error(res['message'])
                                except Exception as e: st.error(f"خطأ أثناء الإرسال: {e}")
                                
                            if b_cols[5].button("🗑️ تجاهل", key=f"ign_g_{idx}"):
                                st.session_state.ignore_list.add(p_name)
                                st.rerun()

        # =========================================================
        # 🟡 القسم الأصفر: تتطلب مراجعة (مقارنة بصرية)
        # =========================================================
        with tab_yellow:
            df_y = df[df['confidence_level'] == 'yellow']
            
            cy1, cy2 = st.columns(2)
            with cy1: search_y = st.text_input("🔍 بحث في المراجعة...", key="search_y")
            with cy2: comp_y = st.selectbox("🏬 فلترة المنافسين (المراجعة)", get_competitors_list(df_y), key="comp_y")
            
            if search_y: df_y = df_y[df_y['product_name'].str.contains(search_y, case=False, na=False)]
            if comp_y != "الكل": df_y = df_y[df_y['competitor_name'].str.contains(comp_y, case=False, na=False)]

            if not df_y.empty:
                # نظام الصفحات للقسم الأصفر
                total_pages_y = math.ceil(len(df_y) / ITEMS_PER_PAGE)
                if st.session_state.page_yellow > total_pages_y: st.session_state.page_yellow = total_pages_y

                col_bulk_y, col_space, col_py1, col_py2, col_py3 = st.columns([2, 2, 1, 2, 1])
                with col_bulk_y:
                    if st.button("🚀 إرسال المحدد لـ Make", key="bulk_y", type="primary"):
                        try:
                            selected = [row for _, row in df_y.iterrows() if row['product_name'] in st.session_state.selected_yellow]
                            if selected:
                                with st.spinner("جاري الإرسال..."):
                                    payloads = []
                                    for row in selected:
                                        p_dict = row.to_dict()
                                        p_dict['description'] = generate_mahwous_description(row['product_name'], row['price'])
                                        payloads.append(p_dict)
                                    res = send_products_to_make(payloads)
                                    if res['success']: st.success(res['message'])
                                    else: st.error(res['message'])
                            else: st.warning("حدد منتجاً أولاً.")
                        except Exception as e: st.error(f"❌ خطأ: {e}")

                # أزرار التنقل للصفحات
                with col_py1: st.button("⬅️ السابق", key="py_prev_y", on_click=prev_page, args=("page_yellow",), disabled=(st.session_state.page_yellow == 1))
                with col_py2: st.markdown(f"<div style='text-align:center; padding-top:10px;'>صفحة {st.session_state.page_yellow} من {total_pages_y}</div>", unsafe_allow_html=True)
                with col_py3: st.button("التالي ➡️", key="py_next_y", on_click=next_page, args=("page_yellow",), disabled=(st.session_state.page_yellow == total_pages_y))

                st.divider()

                start_idx_y = (st.session_state.page_yellow - 1) * ITEMS_PER_PAGE
                page_df_y = df_y.iloc[start_idx_y : start_idx_y + ITEMS_PER_PAGE]

                for idx, row in page_df_y.iterrows():
                    p_name = row['product_name']
                    with st.container(border=True):
                        st.markdown(f"**المنافسين:** {row.get('competitor_name')} | <span class='match-score score-yellow'>نسبة التطابق: {row.get('match_score')}%</span>", unsafe_allow_html=True)
                        
                        comp_col, mah_col = st.columns(2)
                        with comp_col:
                            st.caption("🛒 منتج المنافس")
                            st.markdown(render_image(row.get('image_url')), unsafe_allow_html=True)
                            st.write(f"**{p_name}**")
                            st.markdown(f"<span class='price-text'>{row['price']} ر.س</span>", unsafe_allow_html=True)
                            
                        with mah_col:
                            st.caption("📦 أقرب منتج لدينا (مهووس)")
                            st.markdown(render_image(row.get('match_image')), unsafe_allow_html=True)
                            st.write(f"**{row.get('match_name')}**")
                            st.markdown(f"<span class='price-text'>{row.get('match_price')} ر.س</span>", unsafe_allow_html=True)

                        st.divider()
                        b_cols = st.columns([0.5, 1, 1, 1, 1])
                        with b_cols[0]:
                            if st.checkbox("تحديد", key=f"chk_y_{idx}", value=p_name in st.session_state.selected_yellow):
                                st.session_state.selected_yellow.add(p_name)
                            elif p_name in st.session_state.selected_yellow:
                                st.session_state.selected_yellow.remove(p_name)
                        
                        key_ai = f"ai_y_{idx}"
                        if b_cols[1].button("🤖 تحقق ذكي (AI)", key=f"btn_ai_y_{idx}"):
                            try:
                                with st.spinner(".."):
                                    res = asyncio.run(ai_verify_match(p_name, row.get('match_name', '')))
                                    st.session_state[key_ai] = res
                            except Exception as e: st.error(f"خطأ: {e}")
                                
                        if b_cols[2].button("💹 تسعيرة السوق", key=f"btn_prc_y_{idx}"):
                            try:
                                with st.spinner(".."):
                                    res = search_market_price(p_name, row['price'])
                                    if res['success']: st.info(f"السوق: {res.get('market_price')} ر.س")
                            except Exception as e: st.error(f"خطأ: {e}")
                                
                        if b_cols[3].button("📤 إرسال لـ Make", key=f"btn_snd_y_{idx}", type="primary"):
                            try:
                                with st.spinner(".."):
                                    p_dict = row.to_dict()
                                    p_dict['description'] = generate_mahwous_description(p_name, row['price'])
                                    res = send_products_to_make([p_dict])
                                    if res['success']: st.toast("تم الإرسال!", icon="✅")
                                    else: st.error(res['message'])
                            except Exception as e: st.error(f"خطأ: {e}")
                                
                        if b_cols[4].button("🗑️ تجاهل", key=f"btn_ign_y_{idx}"):
                            st.session_state.ignore_list.add(p_name)
                            st.rerun()
                            
                        if key_ai in st.session_state:
                            st.info(f"نتيجة AI: {st.session_state[key_ai]['reason']}")

        # =========================================================
        # 🔴 القسم الأحمر: منتجات متطابقة (مقارنة بصرية)
        # =========================================================
        with tab_red:
            df_r = df[df['confidence_level'] == 'red']
            
            cr1, cr2 = st.columns(2)
            with cr1: search_r = st.text_input("🔍 بحث في المتطابقة...", key="search_r")
            with cr2: comp_r = st.selectbox("🏬 فلترة المنافسين (المتطابقة)", get_competitors_list(df_r), key="comp_r")
            
            if search_r: df_r = df_r[df_r['product_name'].str.contains(search_r, case=False, na=False)]
            if comp_r != "الكل": df_r = df_r[df_r['competitor_name'].str.contains(comp_r, case=False, na=False)]

            if not df_r.empty:
                # نظام الصفحات للقسم الأحمر
                total_pages_r = math.ceil(len(df_r) / ITEMS_PER_PAGE)
                if st.session_state.page_red > total_pages_r: st.session_state.page_red = total_pages_r

                col_empty, col_pr1, col_pr2, col_pr3 = st.columns([4, 1, 2, 1])
                with col_pr1: st.button("⬅️ السابق", key="pr_prev_r", on_click=prev_page, args=("page_red",), disabled=(st.session_state.page_red == 1))
                with col_pr2: st.markdown(f"<div style='text-align:center; padding-top:10px;'>صفحة {st.session_state.page_red} من {total_pages_r}</div>", unsafe_allow_html=True)
                with col_pr3: st.button("التالي ➡️", key="pr_next_r", on_click=next_page, args=("page_red",), disabled=(st.session_state.page_red == total_pages_r))

                st.divider()

                start_idx_r = (st.session_state.page_red - 1) * ITEMS_PER_PAGE
                page_df_r = df_r.iloc[start_idx_r : start_idx_r + ITEMS_PER_PAGE]

                for idx, row in page_df_r.iterrows():
                    p_name = row['product_name']
                    with st.container(border=True):
                        st.markdown(f"**المنافسين:** {row.get('competitor_name')} | <span class='match-score score-red'>متطابق بنسبة: {row.get('match_score')}%</span>", unsafe_allow_html=True)
                        
                        comp_col, mah_col = st.columns(2)
                        with comp_col:
                            st.caption("🛒 منتج المنافس")
                            st.markdown(render_image(row.get('image_url'), 120), unsafe_allow_html=True)
                            st.write(f"**{p_name}**")
                            st.write(f"{row['price']} ر.س")
                            
                        with mah_col:
                            st.caption("📦 منتجنا (مهووس)")
                            st.markdown(render_image(row.get('match_image'), 120), unsafe_allow_html=True)
                            st.write(f"**{row.get('match_name')}**")
                            st.write(f"{row.get('match_price')} ر.س")

                        st.divider()
                        b_cols = st.columns([1, 1, 1, 3])
                        key_ai_r = f"ai_r_{idx}"
                        
                        if b_cols[0].button("🤖 تحقق ذكي", key=f"btn_ai_r_{idx}"):
                            try:
                                with st.spinner(".."):
                                    res = asyncio.run(ai_verify_match(p_name, row.get('match_name', '')))
                                    st.session_state[key_ai_r] = res
                            except Exception as e: st.error(f"خطأ: {e}")
                                
                        if b_cols[1].button("💹 تسعيرة", key=f"btn_prc_r_{idx}"):
                            try:
                                with st.spinner(".."):
                                    res = search_market_price(p_name, row['price'])
                                    if res['success']: st.info(f"السوق: {res.get('market_price')} ر.س")
                            except Exception as e: st.error(f"خطأ: {e}")
                                
                        if b_cols[2].button("🗑️ إخفاء", key=f"btn_ign_r_{idx}"):
                            st.session_state.ignore_list.add(p_name)
                            st.rerun()
                            
                        if key_ai_r in st.session_state:
                            st.info(f"نتيجة AI: {st.session_state[key_ai_r]['reason']}")

if __name__ == "__main__":
    main()

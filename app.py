"""
app.py v14.0 — الواجهة الذكية المتفاعلة (دعم سحب الصور المتعددة والوصف المطول لمهووس)
══════════════════════════════════════════════════════════════════════
- تقسيم الأقسام بنسب تأكد واضحة (مفقود 95-100%، مراجعة 80-95%، متطابق 90-100%).
- سحب جميع صور المنتج المتوفرة وتوليد الوصف بأسلوب مهووس المطور تلقائياً قبل الإرسال.
- دعم إرسال الصور المتعددة لسيناريو Make لضمان ظهورها في سلة.
- حماية الأزرار والتقاط الأخطاء مع شريط تقدم لحظي.
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

# 1. إعدادات الصفحة
st.set_page_config(page_title=f"{APP_TITLE} {APP_VERSION}", page_icon=APP_ICON, layout="wide")

# 2. تهيئة Session State
if 'analysis_running' not in st.session_state: st.session_state.analysis_running = False
if 'processed_count' not in st.session_state: st.session_state.processed_count = 0
if 'total_count' not in st.session_state: st.session_state.total_count = 0
if 'analysis_results' not in st.session_state: st.session_state.analysis_results = []
if 'ignore_list' not in st.session_state: st.session_state.ignore_list = set()
if 'needs_rerun' not in st.session_state: st.session_state.needs_rerun = False
if 'ai_verifications' not in st.session_state: st.session_state.ai_verifications = {}

if 'selected_green' not in st.session_state: st.session_state.selected_green = set()
if 'selected_yellow' not in st.session_state: st.session_state.selected_yellow = set()

if 'page_green' not in st.session_state: st.session_state.page_green = 1
if 'page_yellow' not in st.session_state: st.session_state.page_yellow = 1
if 'page_red' not in st.session_state: st.session_state.page_red = 1

def next_page(key): st.session_state[key] += 1
def prev_page(key): st.session_state[key] -= 1

def render_image(url, width=150):
    """حماية وعرض الصور"""
    if pd.isna(url) or not url:
        url = "https://via.placeholder.com/150?text=No+Image"
    return f'<img src="{url}" onerror="this.onerror=null;this.src=\'https://via.placeholder.com/150?text=Image+Locked\';" style="width:100%; max-width:{width}px; border-radius:8px; object-fit:contain; border: 1px solid #2d3748;">'

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap');
    html, body, [class*="st-"] { font-family: 'Cairo', sans-serif; }
    .stApp { direction: rtl; }
    .price-text { color: #00d2ff; font-weight: bold; font-size: 1.2rem; }
    .match-score { font-size: 1.1rem; font-weight: 800; padding: 5px 10px; border-radius: 5px; }
    .score-yellow { color: #ffc107; background: rgba(255, 193, 7, 0.1); }
    .score-red { color: #dc3545; background: rgba(220, 53, 69, 0.1); }
    .competitor-tag { background: #2d3748; color: #e2e8f0; padding: 3px 8px; border-radius: 4px; font-size: 0.9rem; margin-left: 5px; display: inline-block;}
</style>
""", unsafe_allow_html=True)

def prepare_product_for_sending(row):
    """تجهيز المنتج بالوصف المطور وجميع الصور المتاحة"""
    p_name = row['product_name']
    p_price = row['price']
    p_dict = row.to_dict()
    
    # 1. جلب معلومات إضافية للهرم العطري لتحسين الوصف
    frag_res = fetch_fragrantica_info(p_name)
    
    # 2. توليد الوصف المطور (خبير وصف منتجات مهووس)
    p_dict['description'] = generate_mahwous_description(p_name, p_price, frag_res if frag_res['success'] else None)
    
    # 3. سحب جميع الصور المتاحة
    img_res = fetch_product_images(p_name)
    if img_res['success'] and img_res['images']:
        p_dict['image_url'] = img_res['images'][0]['url']
        p_dict['all_images'] = [img['url'] for img in img_res['images']]
    else:
        # استخدام صورة المنافس إذا فشل سحب صور جديدة
        p_dict['all_images'] = [row.get('image_url')] if row.get('image_url') else []
        
    return p_dict

def main():
    st.title(f"{APP_ICON} {APP_TITLE} (النسخة 14.0)")
    st.markdown("محرك المطابقة السيادي وخبير المنتجات المفقودة")

    with st.sidebar:
        st.header("📂 رفع البيانات")
        mahwous_file = st.file_uploader("ملف متجر مهووس (المرجع)", type=["csv"])
        competitor_files = st.file_uploader("ملفات المنافسين", type=["csv"], accept_multiple_files=True)
        
        if st.button("🚀 بدء التحليل", type="primary", use_container_width=True, disabled=st.session_state.analysis_running):
            if mahwous_file and competitor_files:
                try:
                    st.session_state.analysis_running = True
                    st.session_state.processed_count = 0
                    st.session_state.total_count = 0
                    st.session_state.analysis_results = []
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

    if st.session_state.analysis_running:
        progress_placeholder = st.empty()
        status_placeholder = st.empty()
        if st.session_state.total_count > 0:
            current = st.session_state.processed_count
            total = st.session_state.total_count
            percent_complete = min(current / total, 1.0)
            with progress_placeholder.container(): st.progress(percent_complete)
            with status_placeholder.container(): st.info(f"⏳ جاري الفحص والمطابقة: تمت معالجة **{current}** من أصل **{total}** منتج... ({int(percent_complete * 100)}%)")
            time.sleep(0.5)
            st.rerun()
        else:
            with status_placeholder.container(): st.info("🔄 جاري تجهيز المنتجات... يرجى الانتظار.")
            time.sleep(0.5)
            st.rerun()

    if st.session_state.needs_rerun:
        st.session_state.needs_rerun = False
        st.rerun()

    if not st.session_state.analysis_running and st.session_state.analysis_results:
        df = pd.DataFrame(st.session_state.analysis_results)
        df = df[~df['product_name'].isin(st.session_state.ignore_list)]
        
        if df.empty:
            st.info("لا توجد بيانات لعرضها.")
            return

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("إجمالي المنتجات", len(df))
        c2.metric("🟢 مفقود أكيد", len(df[df['confidence_level'] == 'green']))
        c3.metric("🟡 تتطلب مراجعة", len(df[df['confidence_level'] == 'yellow']))
        c4.metric("🔴 متطابقة", len(df[df['confidence_level'] == 'red']))

        tab_green, tab_yellow, tab_red = st.tabs([
            f"🟢 منتجات مفقودة ({len(df[df['confidence_level'] == 'green'])})", 
            f"🟡 تتطلب مراجعة ({len(df[df['confidence_level'] == 'yellow'])})", 
            f"🔴 منتجات متطابقة ({len(df[df['confidence_level'] == 'red'])})"
        ])

        def get_unique_list(df_part, column_name):
            if column_name == 'competitor_name':
                items = []
                for comp_str in df_part[column_name].dropna():
                    items.extend([c.strip() for c in str(comp_str).split('،')])
                return ["الكل"] + sorted(list(set(items)))
            else:
                items = df_part[column_name].dropna().unique().tolist()
                return ["الكل"] + sorted([str(i) for i in items if str(i).strip()])

        ITEMS_PER_PAGE = 25

        # 🟢 القسم الأخضر
        with tab_green:
            df_g = df[df['confidence_level'] == 'green']
            cg1, cg2, cg3 = st.columns(3)
            with cg1: search_g = st.text_input("🔍 بحث بالاسم...", key="search_g")
            with cg2: comp_g = st.selectbox("🏬 فلترة المنافسين", get_unique_list(df_g, 'competitor_name'), key="comp_g")
            with cg3: brand_g = st.selectbox("🏷️ فلترة الماركة", get_unique_list(df_g, 'brand'), key="brand_g")
            
            if search_g: df_g = df_g[df_g['product_name'].str.contains(search_g, case=False, na=False)]
            if comp_g != "الكل": df_g = df_g[df_g['competitor_name'].str.contains(comp_g, case=False, na=False)]
            if brand_g != "الكل": df_g = df_g[df_g['brand'].astype(str) == brand_g]

            if not df_g.empty:
                total_pages_g = math.ceil(len(df_g) / ITEMS_PER_PAGE)
                if st.session_state.page_green > total_pages_g: st.session_state.page_green = total_pages_g
                
                col_bulk1, col_bulk2, col_pg1, col_pg2, col_pg3 = st.columns([2, 2, 1, 2, 1])
                with col_bulk1:
                    if st.button("🚀 إرسال المحدد لـ Make", key="bulk_g", type="primary"):
                        try:
                            selected = [row for _, row in df_g.iterrows() if row['product_name'] in st.session_state.selected_green]
                            if selected:
                                with st.spinner("جاري توليد الوصف وسحب الصور والإرسال..."):
                                    payloads = []
                                    for row in selected:
                                        payloads.append(prepare_product_for_sending(row))
                                    res = send_products_to_make(payloads)
                                    if res['success']: st.success(res['message'])
                                    else: st.error(res['message'])
                            else: st.warning("الرجاء تحديد منتج واحد على الأقل.")
                        except Exception as e: st.error(f"❌ خطأ أثناء الإرسال الجماعي: {e}")
                
                with col_pg1: st.button("⬅️ السابق", key="pg_prev_g", on_click=prev_page, args=("page_green",), disabled=(st.session_state.page_green == 1))
                with col_pg2: st.markdown(f"<div style='text-align:center; padding-top:10px;'>صفحة {st.session_state.page_green} من {total_pages_g}</div>", unsafe_allow_html=True)
                with col_pg3: st.button("التالي ➡️", key="pg_next_g", on_click=next_page, args=("page_green",), disabled=(st.session_state.page_green == total_pages_g))

                st.divider()
                start_idx_g = (st.session_state.page_green - 1) * ITEMS_PER_PAGE
                page_df_g = df_g.iloc[start_idx_g : start_idx_g + ITEMS_PER_PAGE]

                for idx, row in page_df_g.iterrows():
                    p_name = row['product_name']
                    with st.container(border=True):
                        c_chk, c_img, c_info = st.columns([0.5, 2, 7])
                        with c_chk:
                            if st.checkbox("تحديد", key=f"chk_g_{idx}", value=p_name in st.session_state.selected_green): st.session_state.selected_green.add(p_name)
                            elif p_name in st.session_state.selected_green: st.session_state.selected_green.remove(p_name)
                        with c_img: st.markdown(render_image(row.get('image_url')), unsafe_allow_html=True)
                        with c_info:
                            st.subheader(p_name)
                            st.markdown(f"<span class='price-text'>{row['price']} ر.س</span>", unsafe_allow_html=True)
                            comps = str(row.get('competitor_name', '')).split('،')
                            comps_html = "".join([f"<span class='competitor-tag'>🏪 {c.strip()}</span>" for c in comps if c.strip()])
                            st.markdown(f"**متوفر لدى:** {comps_html}", unsafe_allow_html=True)
                            st.write(f"🏷️ **الماركة:** {row.get('brand', 'غير محدد')}")
                            
                            b_cols = st.columns(6)
                            if b_cols[0].button("🖼️ بحث صور", key=f"img_g_{idx}"):
                                try:
                                    with st.spinner(".."):
                                        res = fetch_product_images(p_name)
                                        if res['success'] and res['images']: 
                                            for img in res['images'][:2]: st.markdown(render_image(img['url'], 100), unsafe_allow_html=True)
                                        else: st.warning("لم يتم العثور.")
                                except Exception as e: st.error(f"خطأ: {e}")
                            
                            if b_cols[1].button("🌸 مكونات", key=f"not_g_{idx}"):
                                try:
                                    with st.spinner(".."):
                                        res = fetch_fragrantica_info(p_name)
                                        if res['success']: st.info(f"القمة: {', '.join(res.get('top_notes', []))}")
                                        else: st.warning("لم يتم العثور.")
                                except Exception as e: st.error(f"خطأ: {e}")
                            
                            if b_cols[4].button("📤 إرسال مفرد", key=f"snd_g_{idx}", type="primary"):
                                try:
                                    with st.spinner("يولد الوصف ويسحب الصور..."):
                                        p_payload = prepare_product_for_sending(row)
                                        res = send_products_to_make([p_payload])
                                        if res['success']: st.toast("تم الإرسال!", icon="✅")
                                        else: st.error(res['message'])
                                except Exception as e: st.error(f"خطأ: {e}")
                            
                            if b_cols[5].button("🗑️ تجاهل", key=f"ign_g_{idx}"):
                                st.session_state.ignore_list.add(p_name)
                                st.rerun()

        # 🟡 القسم الأصفر
        with tab_yellow:
            df_y = df[df['confidence_level'] == 'yellow']
            cy1, cy2, cy3 = st.columns(3)
            with cy1: search_y = st.text_input("🔍 بحث بالمراجعة...", key="search_y")
            with cy2: comp_y = st.selectbox("🏬 فلترة المنافسين", get_unique_list(df_y, 'competitor_name'), key="comp_y")
            with cy3: brand_y = st.selectbox("🏷️ فلترة الماركة", get_unique_list(df_y, 'brand'), key="brand_y")
            
            if search_y: df_y = df_y[df_y['product_name'].str.contains(search_y, case=False, na=False)]
            if comp_y != "الكل": df_y = df_y[df_y['competitor_name'].str.contains(comp_y, case=False, na=False)]
            if brand_y != "الكل": df_y = df_y[df_y['brand'].astype(str) == brand_y]

            if not df_y.empty:
                total_pages_y = math.ceil(len(df_y) / ITEMS_PER_PAGE)
                if st.session_state.page_yellow > total_pages_y: st.session_state.page_yellow = total_pages_y
                col_bulk_y, col_space, col_py1, col_py2, col_py3 = st.columns([2, 2, 1, 2, 1])
                with col_bulk_y:
                    if st.button("🚀 إرسال المحدد لـ Make", key="bulk_y", type="primary"):
                        try:
                            selected = [row for _, row in df_y.iterrows() if row['product_name'] in st.session_state.selected_yellow]
                            if selected:
                                with st.spinner("جاري الإرسال وتوليد الوصف..."):
                                    payloads = [prepare_product_for_sending(row) for row in selected]
                                    res = send_products_to_make(payloads)
                                    if res['success']: st.success(res['message'])
                                    else: st.error(res['message'])
                            else: st.warning("حدد منتجاً أولاً.")
                        except Exception as e: st.error(f"❌ خطأ: {e}")

                with col_py1: st.button("⬅️ السابق", key="py_prev_y", on_click=prev_page, args=("page_yellow",), disabled=(st.session_state.page_yellow == 1))
                with col_py2: st.markdown(f"<div style='text-align:center; padding-top:10px;'>صفحة {st.session_state.page_yellow} من {total_pages_y}</div>", unsafe_allow_html=True)
                with col_py3: st.button("التالي ➡️", key="py_next_y", on_click=next_page, args=("page_yellow",), disabled=(st.session_state.page_yellow == total_pages_y))

                st.divider()
                start_idx_y = (st.session_state.page_yellow - 1) * ITEMS_PER_PAGE
                page_df_y = df_y.iloc[start_idx_y : start_idx_y + ITEMS_PER_PAGE]

                for idx, row in page_df_y.iterrows():
                    p_name = row['product_name']
                    with st.container(border=True):
                        st.markdown(f"**متوفر لدى:** {row.get('competitor_name')} | <span class='match-score score-yellow'>شك بنسبة: {row.get('match_score')}%</span>", unsafe_allow_html=True)
                        comp_col, mah_col = st.columns(2)
                        with comp_col:
                            st.caption("🛒 منتج المنافس")
                            st.markdown(render_image(row.get('image_url')), unsafe_allow_html=True)
                            st.write(f"**{p_name}**")
                            st.markdown(f"<span class='price-text'>{row['price']} ر.س</span>", unsafe_allow_html=True)
                        with mah_col:
                            st.caption("📦 أقرب منتج لدينا")
                            st.markdown(render_image(row.get('match_image')), unsafe_allow_html=True)
                            st.write(f"**{row.get('match_name')}**")
                            st.markdown(f"<span class='price-text'>{row.get('match_price')} ر.س</span>", unsafe_allow_html=True)

                        st.divider()
                        b_cols = st.columns([0.5, 1.5, 1.5, 1.5, 1])
                        with b_cols[0]:
                            if st.checkbox("تحديد", key=f"chk_y_{idx}", value=p_name in st.session_state.selected_yellow): st.session_state.selected_yellow.add(p_name)
                            elif p_name in st.session_state.selected_yellow: st.session_state.selected_yellow.remove(p_name)
                        
                        if b_cols[3].button("📤 إرسال لـ Make", key=f"btn_snd_y_{idx}", type="primary"):
                            try:
                                with st.spinner("يولد الوصف ويسحب الصور..."):
                                    p_payload = prepare_product_for_sending(row)
                                    res = send_products_to_make([p_payload])
                                    if res['success']: st.toast("تم الإرسال!", icon="✅")
                                    else: st.error(res['message'])
                            except Exception as e: st.error(f"خطأ: {e}")

        # 🔴 القسم الأحمر
        with tab_red:
            df_r = df[df['confidence_level'] == 'red']
            if not df_r.empty:
                st.info("هذه المنتجات متوفرة بالفعل في متجر مهووس بنسبة تطابق عالية.")
                st.dataframe(df_r[['product_name', 'price', 'match_name', 'match_score', 'competitor_name']], use_container_width=True)
            else:
                st.write("لا توجد منتجات متطابقة تماماً.")

if __name__ == "__main__":
    main()

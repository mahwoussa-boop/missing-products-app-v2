"""
app.py v14.5 — الواجهة الذكية المتفاعلة (النظام الهجين: AI + البرمجة المباشرة لمهووس)
══════════════════════════════════════════════════════════════════════
- سحب جميع صور المنتج وإصلاح روابطها برمجياً (Python) لضمان التوافق مع سلة.
- توليد الوصف بتنسيق مهووس (AI أولاً، ثم القوالب الذكية برمجياً) مع روابط داخلية.
- جلب المكونات الحقيقية للعطر من Fragrantica لدمجها في الوصف.
- دعم الإرسال الجماعي والفردي لسيناريو Make وسلة بدون أخطاء.
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

# استيراد أدوات الذكاء الاصطناعي والنظام الهجين
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

if 'selected_green' not in st.session_state: st.session_state.selected_green = set()
if 'selected_yellow' not in st.session_state: st.session_state.selected_yellow = set()

if 'page_green' not in st.session_state: st.session_state.page_green = 1
if 'page_yellow' not in st.session_state: st.session_state.page_yellow = 1

def next_page(key): st.session_state[key] += 1
def prev_page(key): st.session_state[key] -= 1

def render_image(url, width=150):
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
    .competitor-tag { background: #2d3748; color: #e2e8f0; padding: 3px 8px; border-radius: 4px; font-size: 0.9rem; margin-left: 5px; display: inline-block;}
</style>
""", unsafe_allow_html=True)

def prepare_product_for_sending(row):
    """تجهيز المنتج بالنظام الهجين: سحب الصور برمجياً + توليد الوصف (AI/Smart Template)"""
    p_name = row['product_name']
    p_price = row['price']
    p_dict = row.to_dict()
    
    # 1. جلب المكونات الحقيقية (AI/برمجي)
    frag_res = fetch_fragrantica_info(p_name)
    
    # 2. توليد الوصف (النظام الهجين: AI أو قوالب ذكية مع روابط داخلية)
    p_dict['description'] = generate_mahwous_description(p_name, p_price, frag_res if frag_res['success'] else None)
    
    # 3. سحب الصور وإصلاح روابطها برمجياً
    img_res = fetch_product_images(p_name)
    if img_res['success'] and img_res['images']:
        p_dict['image_url'] = img_res['images'][0]['url']
        p_dict['all_images'] = [img['url'] for img in img_res['images']]
    else:
        # استخدام صورة المنافس كبديل طوارئ
        p_dict['all_images'] = [row.get('image_url')] if row.get('image_url') else []
        
    return p_dict

def main():
    st.title(f"{APP_ICON} {APP_TITLE} (النسخة 14.5)")
    st.markdown("محرك المطابقة السيادي وخبير المنتجات المفقودة - النظام الهجين")

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

    if st.session_state.needs_rerun:
        st.session_state.needs_rerun = False
        st.rerun()

    if not st.session_state.analysis_running and st.session_state.analysis_results:
        df = pd.DataFrame(st.session_state.analysis_results)
        df = df[~df['product_name'].isin(st.session_state.ignore_list)]
        
        if df.empty:
            st.info("لا توجد بيانات لعرضها.")
            return

        tab_green, tab_yellow = st.tabs([
            f"🟢 منتجات مفقودة ({len(df[df['confidence_level'] == 'green'])})", 
            f"🟡 تتطلب مراجعة ({len(df[df['confidence_level'] == 'yellow'])})"
        ])

        ITEMS_PER_PAGE = 25

        # 🟢 القسم الأخضر
        with tab_green:
            df_g = df[df['confidence_level'] == 'green']
            if not df_g.empty:
                total_pages_g = math.ceil(len(df_g) / ITEMS_PER_PAGE)
                if st.session_state.page_green > total_pages_g: st.session_state.page_green = total_pages_g
                
                col_bulk1, col_pg1, col_pg2, col_pg3 = st.columns([2, 1, 2, 1])
                with col_bulk1:
                    if st.button("🚀 إرسال المحدد لـ Make", key="bulk_g", type="primary"):
                        selected = [row for _, row in df_g.iterrows() if row['product_name'] in st.session_state.selected_green]
                        if selected:
                            with st.spinner("جاري التجهيز والإرسال بالنظام الهجين..."):
                                payloads = [prepare_product_for_sending(row) for row in selected]
                                res = send_products_to_make(payloads)
                                if res['success']: st.success(res['message'])
                                else: st.error(res['message'])
                        else: st.warning("الرجاء تحديد منتج.")
                
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
                            st.write(f"🏪 **المنافس:** {row.get('competitor_name')} | 🏷️ **الماركة:** {row.get('brand')}")
                            
                            b_cols = st.columns(6)
                            if b_cols[0].button("🖼️ بحث صور", key=f"img_g_{idx}"):
                                with st.spinner(".."):
                                    res = fetch_product_images(p_name)
                                    if res['success']: st.markdown(render_image(res['images'][0]['url'], 100), unsafe_allow_html=True)
                            
                            if b_cols[4].button("📤 إرسال مفرد", key=f"snd_g_{idx}", type="primary"):
                                with st.spinner("جاري التجهيز..."):
                                    p_payload = prepare_product_for_sending(row)
                                    res = send_products_to_make([p_payload])
                                    if res['success']: st.toast("تم الإرسال!", icon="✅")
                                    else: st.error(res['message'])

        # 🟡 القسم الأصفر
        with tab_yellow:
            df_y = df[df['confidence_level'] == 'yellow']
            if not df_y.empty:
                total_pages_y = math.ceil(len(df_y) / ITEMS_PER_PAGE)
                if st.session_state.page_yellow > total_pages_y: st.session_state.page_yellow = total_pages_y
                
                col_bulk_y, col_py1, col_py2, col_py3 = st.columns([2, 1, 2, 1])
                with col_bulk_y:
                    if st.button("🚀 إرسال المحدد لـ Make", key="bulk_y", type="primary"):
                        selected = [row for _, row in df_y.iterrows() if row['product_name'] in st.session_state.selected_yellow]
                        if selected:
                            with st.spinner("جاري الإرسال..."):
                                payloads = [prepare_product_for_sending(row) for row in selected]
                                res = send_products_to_make(payloads)
                                if res['success']: st.success(res['message'])
                                else: st.error(res['message'])
                
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
                            with st.spinner("جاري التجهيز..."):
                                p_payload = prepare_product_for_sending(row)
                                res = send_products_to_make([p_payload])
                                if res['success']: st.toast("تم الإرسال!", icon="✅")
                                else: st.error(res['message'])

if __name__ == "__main__":
    main()

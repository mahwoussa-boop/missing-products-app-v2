"""
app.py v9.0 — الواجهة الذكية المتفاعلة (تصميم سليم، فلاتر، وتحكم جماعي)
══════════════════════════════════════════════════════════════════════
- حل مشكلة الشاشة السوداء (استخدام Native Streamlit Containers).
- تقسيم ذكي للواجهة: (مفقود بدون مقارنة | مشتبه ومتطابق مع مقارنة بصرية).
- دعم التحديد الجماعي (Bulk Actions) والفلاتر.
"""

import streamlit as st
import pandas as pd
import asyncio
import time

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

# 2. تهيئة Session State الأساسية
if 'analysis_running' not in st.session_state: st.session_state.analysis_running = False
if 'processed_count' not in st.session_state: st.session_state.processed_count = 0
if 'total_count' not in st.session_state: st.session_state.total_count = 0
if 'analysis_results' not in st.session_state: st.session_state.analysis_results = []
if 'ignore_list' not in st.session_state: st.session_state.ignore_list = set()
if 'needs_rerun' not in st.session_state: st.session_state.needs_rerun = False
if 'ai_verifications' not in st.session_state: st.session_state.ai_verifications = {}
if 'selected_products' not in st.session_state: st.session_state.selected_products = set()

# CSS خفيف جداً لترتيب العناصر بدون التأثير على الوضع الليلي
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap');
    html, body, [class*="st-"] { font-family: 'Cairo', sans-serif; }
    .stApp { direction: rtl; }
    .product-card { border: 1px solid #444; border-radius: 10px; padding: 15px; margin-bottom: 15px; background-color: rgba(255,255,255,0.02); }
    .price-text { color: #00d2ff; font-weight: bold; font-size: 1.2rem; }
    .badge-green { color: #28a745; font-weight: bold; }
    .badge-yellow { color: #ffc107; font-weight: bold; }
    .badge-red { color: #dc3545; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

def main():
    st.title(f"{APP_ICON} {APP_TITLE} (النسخة 9.0)")
    st.markdown("محرك المطابقة السيادي وخبير المنتجات المفقودة")

    # ─── الشريط الجانبي (إدارة البيانات) ───
    with st.sidebar:
        st.header("📂 رفع البيانات")
        mahwous_file = st.file_uploader("ملف متجر مهووس (المرجع)", type=["csv"])
        competitor_files = st.file_uploader("ملفات المنافسين", type=["csv"], accept_multiple_files=True)
        
        if st.button("🚀 بدء التحليل", type="primary", use_container_width=True, disabled=st.session_state.analysis_running):
            if mahwous_file and competitor_files:
                st.session_state.analysis_running = True
                with st.spinner("جاري تهيئة البيانات..."):
                    m_df = load_mahwous_store_data(mahwous_file)
                    c_data = {f.name: load_competitor_data(f) for f in competitor_files}
                    start_sovereign_analysis(m_df, c_data)
                st.rerun()
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
        df = pd.DataFrame(st.session_state.analysis_results)
        df = df[~df['product_name'].isin(st.session_state.ignore_list)]
        
        if df.empty:
            st.info("لا توجد بيانات لعرضها. جميع المنتجات تمت معالجتها أو تجاهلها.")
            return

        # فلاتر علوية
        c1, c2, c3 = st.columns(3)
        with c1: search_query = st.text_input("🔍 بحث برقم أو اسم المنتج...")
        with c2: 
            all_comps = ["الكل"] + list(set(comp.strip() for comps in df['competitor_name'].dropna() for comp in str(comps).split('،')))
            selected_comp = st.selectbox("🏬 فلترة حسب المنافس", all_comps)
            
        # تطبيق الفلاتر
        if search_query:
            df = df[df['product_name'].str.contains(search_query, case=False, na=False)]
        if selected_comp != "الكل":
            df = df[df['competitor_name'].str.contains(selected_comp, case=False, na=False)]

        # تقسيم التبويبات
        tab_green, tab_yellow, tab_red = st.tabs([
            f"🟢 مفقود أكيد ({len(df[df['confidence_level'] == 'green'])})", 
            f"🟡 مشتبه به ({len(df[df['confidence_level'] == 'yellow'])})", 
            f"🔴 متطابق ({len(df[df['confidence_level'] == 'red'])})"
        ])

        # =========================================================
        # القسم الأخضر: مفقود أكيد (بدون مقارنة - تفاصيل المنافس فقط)
        # =========================================================
        with tab_green:
            df_green = df[df['confidence_level'] == 'green']
            
            if not df_green.empty:
                # زر إرسال جماعي
                if st.button("🚀 إرسال المنتجات المحددة إلى Make", type="primary"):
                    selected = [row for _, row in df_green.iterrows() if row['product_name'] in st.session_state.selected_products]
                    if selected:
                        with st.spinner("جاري توليد الوصف والإرسال..."):
                            payloads = []
                            for row in selected:
                                p_dict = row.to_dict()
                                # توليد الوصف تلقائياً عند الإرسال
                                p_dict['description'] = generate_mahwous_description(row['product_name'], row['price'])
                                payloads.append(p_dict)
                            res = send_products_to_make(payloads)
                            if res['success']: st.success(res['message'])
                            else: st.error(res['message'])
                    else:
                        st.warning("الرجاء تحديد منتج واحد على الأقل.")
            
            for idx, row in df_green.iterrows():
                p_name = row['product_name']
                p_price = row['price']
                
                with st.container(border=True):
                    col_chk, col_img, col_info = st.columns([0.5, 2, 7])
                    
                    with col_chk:
                        is_selected = st.checkbox("تحديد", key=f"chk_{idx}", value=p_name in st.session_state.selected_products)
                        if is_selected: st.session_state.selected_products.add(p_name)
                        elif p_name in st.session_state.selected_products: st.session_state.selected_products.remove(p_name)
                        
                    with col_img:
                        img_url = st.session_state.get(f"img_{idx}", row.get('image_url', ''))
                        if img_url: st.image(img_url, use_container_width=True)
                        else: st.write("📷 لا توجد صورة")
                        
                    with col_info:
                        st.subheader(p_name)
                        st.markdown(f"<span class='price-text'>{p_price} ر.س</span>", unsafe_allow_html=True)
                        st.write(f"🏢 **متوفر لدى:** {row.get('competitor_name', 'غير محدد')}")
                        
                        # أزرار الذكاء الاصطناعي السفلية
                        btn_cols = st.columns(6)
                        if btn_cols[0].button("🖼️ جلب صورة", key=f"btn_img_{idx}"):
                            with st.spinner(".."):
                                res = fetch_product_images(p_name)
                                if res['success'] and res['images']:
                                    st.session_state[f"img_{idx}"] = res['images'][0]['url']
                                    st.rerun()
                        if btn_cols[1].button("🌸 مكونات", key=f"btn_not_{idx}"):
                            with st.spinner(".."):
                                res = fetch_fragrantica_info(p_name)
                                if res['success']: st.info(f"القمة: {', '.join(res.get('top_notes', []))}")
                        if btn_cols[2].button("🔎 هل متوفر لدينا؟", key=f"btn_chk_{idx}"):
                            with st.spinner(".."):
                                res = search_mahwous(p_name)
                                if res['success']: st.info(f"النتيجة: {res.get('likely_available')}")
                        if btn_cols[3].button("💹 تسعيرة السوق", key=f"btn_mkt_{idx}"):
                            with st.spinner(".."):
                                res = search_market_price(p_name, p_price)
                                if res['success']: st.info(f"متوسط السوق: {res.get('market_price')} ر.س")
                        if btn_cols[4].button("✍️ وصف يدوي", key=f"btn_dsc_{idx}"):
                            with st.spinner(".."):
                                desc = generate_mahwous_description(p_name, p_price)
                                st.session_state[f"desc_{idx}"] = desc
                        if btn_cols[5].button("🗑️ تجاهل", key=f"btn_ign_{idx}"):
                            st.session_state.ignore_list.add(p_name)
                            st.rerun()
                            
                        # إظهار الوصف للتعديل إن وجد
                        if f"desc_{idx}" in st.session_state:
                            st.text_area("وصف مهووس", value=st.session_state[f"desc_{idx}"], height=150, key=f"ta_{idx}")

        # =========================================================
        # دالة مساعدة لطباعة الأقسام (الأصفر والأحمر) بمقارنة بصرية
        # =========================================================
        def render_comparison_section(level_name):
            df_filtered = df[df['confidence_level'] == level_name]
            for idx, row in df_filtered.iterrows():
                p_name = row['product_name']
                with st.container(border=True):
                    comp_col, mahwous_col = st.columns(2)
                    
                    # بطاقة المنافس
                    with comp_col:
                        st.caption(f"🛒 منتج المنافس ({row.get('competitor_name')})")
                        if row.get('image_url'): st.image(row['image_url'], width=120)
                        st.write(f"**{p_name}**")
                        st.markdown(f"<span class='price-text'>{row['price']} ر.س</span>", unsafe_allow_html=True)

                    # بطاقة متجر مهووس (للمقارنة)
                    with mahwous_col:
                        st.caption("📦 أقرب منتج في مهووس")
                        if row.get('match_image'): st.image(row['match_image'], width=120)
                        st.write(f"**{row.get('match_name')}**")
                        st.markdown(f"<span class='price-text'>{row.get('match_price', 0)} ر.س</span>", unsafe_allow_html=True)
                        st.markdown(f"نسبة التطابق: **{row.get('match_score', 0)}%**")

                    # أزرار الإجراءات
                    b_cols = st.columns(4)
                    
                    key_ai = f"ai_res_{idx}"
                    if key_ai in st.session_state:
                        st.info(f"💡 الذكاء الاصطناعي: {st.session_state[key_ai]['reason']}")

                    if b_cols[0].button("🤖 تحقق بالذكاء", key=f"btn_ai_{idx}"):
                        with st.spinner(".."):
                            res = asyncio.run(ai_verify_match(p_name, row.get('match_name', '')))
                            st.session_state[key_ai] = res
                            st.rerun()
                            
                    if b_cols[1].button("✅ إضافة لمهووس (ميك)", key=f"btn_add_{idx}", type="primary"):
                        with st.spinner(".."):
                            p_dict = row.to_dict()
                            p_dict['description'] = generate_mahwous_description(p_name, row['price'])
                            res = send_products_to_make([p_dict])
                            if res['success']: st.toast("تم الإرسال!", icon="✅")
                            else: st.error("فشل الإرسال")
                            
                    if b_cols[2].button("💹 تسعيرة", key=f"btn_prc_{idx}"):
                        with st.spinner(".."):
                            res = search_market_price(p_name, row['price'])
                            if res['success']: st.info(f"متوسط السوق: {res.get('market_price')} ر.س")
                            
                    if b_cols[3].button("🗑️ تجاهل", key=f"btn_del_{idx}"):
                        st.session_state.ignore_list.add(p_name)
                        st.rerun()

        # تشغيل الأقسام
        with tab_yellow: render_comparison_section('yellow')
        with tab_red: render_comparison_section('red')

if __name__ == "__main__":
    main()

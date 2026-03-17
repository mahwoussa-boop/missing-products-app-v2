"""
app.py v10.0 — الواجهة الذكية المتفاعلة (تصميم سليم، فلاتر لكل قسم، وتحكم جماعي)
══════════════════════════════════════════════════════════════════════
- تقسيم دقيق (مفقود بدون مقارنة | مشتبه ومتطابق مع مقارنة بصرية).
- فلاتر وتحديد جماعي (Bulk Actions) منفصلة لكل قسم.
- توليد الوصف وسحب الصور تلقائياً عند الإرسال إلى Make.
- عرض المتاجر المجمعة في البطاقة.
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
# فصل التحديد الجماعي لكل قسم
if 'selected_green' not in st.session_state: st.session_state.selected_green = set()
if 'selected_yellow' not in st.session_state: st.session_state.selected_yellow = set()

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
    st.title(f"{APP_ICON} {APP_TITLE} (النسخة 10.0)")
    st.markdown("محرك المطابقة السيادي وخبير المنتجات المفقودة")

    # ─── الشريط الجانبي (إدارة البيانات) ───
    with st.sidebar:
        st.header("📂 رفع البيانات")
        mahwous_file = st.file_uploader("ملف متجر مهووس (المرجع)", type=["csv"])
        competitor_files = st.file_uploader("ملفات المنافسين", type=["csv"], accept_multiple_files=True)
        
        if st.button("🚀 بدء التحليل", type="primary", use_container_width=True, disabled=st.session_state.analysis_running):
            if mahwous_file and competitor_files:
                st.session_state.analysis_running = True
                with st.spinner("جاري تهيئة البيانات والمحرك..."):
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
                # أزرار التحكم الجماعي
                col_bulk1, col_bulk2 = st.columns([1, 4])
                with col_bulk1:
                    if st.button("🚀 إرسال المحدد لـ Make", key="bulk_g", type="primary"):
                        selected = [row for _, row in df_g.iterrows() if row['product_name'] in st.session_state.selected_green]
                        if selected:
                            with st.spinner("جاري توليد الوصف والصور والإرسال..."):
                                payloads = []
                                for row in selected:
                                    p_dict = row.to_dict()
                                    p_dict['description'] = generate_mahwous_description(row['product_name'], row['price'])
                                    # إذا كانت الصورة مفقودة، حاول جلبها
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
                
                # عرض بطاقات المنتجات
                for idx, row in df_g.iterrows():
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
                            if row.get('image_url'): st.image(row['image_url'], use_container_width=True)
                            else: st.info("لا توجد صورة للمنافس")
                            
                        with c_info:
                            st.subheader(p_name)
                            st.markdown(f"<span class='price-text'>{p_price} ر.س</span>", unsafe_allow_html=True)
                            st.write(f"🏢 **متوفر لدى:** {row.get('competitor_name')}")
                            
                            # الأزرار الفردية
                            b_cols = st.columns(6)
                            if b_cols[0].button("🖼️ بحث صور", key=f"img_g_{idx}"):
                                with st.spinner(".."):
                                    res = fetch_product_images(p_name)
                                    if res['success'] and res['images']: st.image(res['images'][0]['url'], width=100)
                            if b_cols[1].button("🌸 مكونات", key=f"not_g_{idx}"):
                                with st.spinner(".."):
                                    res = fetch_fragrantica_info(p_name)
                                    if res['success']: st.info(f"القمة: {', '.join(res.get('top_notes', []))}")
                            if b_cols[2].button("🔎 هل متوفر لدينا؟", key=f"chk_g_ai_{idx}"):
                                with st.spinner(".."):
                                    res = search_mahwous(p_name)
                                    if res['success']: st.info(res.get('likely_available'))
                            if b_cols[3].button("💹 تسعيرة السوق", key=f"prc_g_{idx}"):
                                with st.spinner(".."):
                                    res = search_market_price(p_name, p_price)
                                    if res['success']: st.info(f"متوسط السوق: {res.get('market_price')} ر.س")
                            if b_cols[4].button("📤 إرسال مفرد", key=f"snd_g_{idx}", type="primary"):
                                with st.spinner("يولد الوصف ويرسل..."):
                                    p_dict = row.to_dict()
                                    p_dict['description'] = generate_mahwous_description(p_name, p_price)
                                    res = send_products_to_make([p_dict])
                                    if res['success']: st.toast("تم الإرسال!", icon="✅")
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
                col_bulk_y, _ = st.columns([1, 4])
                with col_bulk_y:
                    if st.button("🚀 إرسال المحدد لـ Make", key="bulk_y", type="primary"):
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
                        else: st.warning("حدد منتجاً.")

                for idx, row in df_y.iterrows():
                    p_name = row['product_name']
                    with st.container(border=True):
                        st.markdown(f"**المنافسين:** {row.get('competitor_name')} | <span class='match-score score-yellow'>نسبة التطابق: {row.get('match_score')}%</span>", unsafe_allow_html=True)
                        
                        comp_col, mah_col = st.columns(2)
                        with comp_col:
                            st.caption("🛒 منتج المنافس")
                            if row.get('image_url'): st.image(row['image_url'], width=150)
                            st.write(f"**{p_name}**")
                            st.markdown(f"<span class='price-text'>{row['price']} ر.س</span>", unsafe_allow_html=True)
                            
                        with mah_col:
                            st.caption("📦 أقرب منتج لدينا (مهووس)")
                            if row.get('match_image'): st.image(row['match_image'], width=150)
                            st.write(f"**{row.get('match_name')}**")
                            st.markdown(f"<span class='price-text'>{row.get('match_price')} ر.س</span>", unsafe_allow_html=True)

                        # أزرار الإجراءات للقسم الأصفر
                        st.divider()
                        b_cols = st.columns([0.5, 1, 1, 1, 1])
                        with b_cols[0]:
                            if st.checkbox("تحديد", key=f"chk_y_{idx}", value=p_name in st.session_state.selected_yellow):
                                st.session_state.selected_yellow.add(p_name)
                            elif p_name in st.session_state.selected_yellow:
                                st.session_state.selected_yellow.remove(p_name)
                        
                        key_ai = f"ai_y_{idx}"
                        if b_cols[1].button("🤖 تحقق ذكي (AI)", key=f"btn_ai_y_{idx}"):
                            with st.spinner(".."):
                                res = asyncio.run(ai_verify_match(p_name, row.get('match_name', '')))
                                st.session_state[key_ai] = res
                        if b_cols[2].button("💹 تسعيرة السوق", key=f"btn_prc_y_{idx}"):
                            with st.spinner(".."):
                                res = search_market_price(p_name, row['price'])
                                if res['success']: st.info(f"السوق: {res.get('market_price')} ر.س")
                        if b_cols[3].button("📤 إرسال لـ Make", key=f"btn_snd_y_{idx}", type="primary"):
                            with st.spinner(".."):
                                p_dict = row.to_dict()
                                p_dict['description'] = generate_mahwous_description(p_name, row['price'])
                                res = send_products_to_make([p_dict])
                                if res['success']: st.toast("تم الإرسال!", icon="✅")
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

            for idx, row in df_r.iterrows():
                p_name = row['product_name']
                with st.container(border=True):
                    st.markdown(f"**المنافسين:** {row.get('competitor_name')} | <span class='match-score score-red'>متطابق بنسبة: {row.get('match_score')}%</span>", unsafe_allow_html=True)
                    
                    comp_col, mah_col = st.columns(2)
                    with comp_col:
                        st.caption("🛒 منتج المنافس")
                        if row.get('image_url'): st.image(row['image_url'], width=120)
                        st.write(f"**{p_name}**")
                        st.write(f"{row['price']} ر.س")
                        
                    with mah_col:
                        st.caption("📦 منتجنا (مهووس)")
                        if row.get('match_image'): st.image(row['match_image'], width=120)
                        st.write(f"**{row.get('match_name')}**")
                        st.write(f"{row.get('match_price')} ر.س")

                    st.divider()
                    b_cols = st.columns([1, 1, 1, 3])
                    key_ai_r = f"ai_r_{idx}"
                    if b_cols[0].button("🤖 تحقق ذكي", key=f"btn_ai_r_{idx}"):
                        with st.spinner(".."):
                            res = asyncio.run(ai_verify_match(p_name, row.get('match_name', '')))
                            st.session_state[key_ai_r] = res
                    if b_cols[1].button("💹 تسعيرة", key=f"btn_prc_r_{idx}"):
                        with st.spinner(".."):
                            res = search_market_price(p_name, row['price'])
                            if res['success']: st.info(f"السوق: {res.get('market_price')} ر.س")
                    if b_cols[2].button("🗑️ إخفاء", key=f"btn_ign_r_{idx}"):
                        st.session_state.ignore_list.add(p_name)
                        st.rerun()
                        
                    if key_ai_r in st.session_state:
                        st.info(f"نتيجة AI: {st.session_state[key_ai_r]['reason']}")

if __name__ == "__main__":
    main()

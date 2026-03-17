"""
app.py v8.0 — الواجهة الذكية المتفاعلة (تتضمن خبير مهووس للمنتجات المفقودة)
══════════════════════════════════════════════════════════════════════
- دمج ميزات Vision 2030 (جلب الصور، المكونات، خبير الوصف، بحث السوق).
- أتمتة Make.com محسنة مع دعم إرسال الوصف المولد والصور.
"""

import streamlit as st
import pandas as pd
import asyncio
import time

from config import APP_TITLE, APP_VERSION, APP_ICON, COLORS
from db_manager import load_mahwous_store_data, load_competitor_data
from sovereign_matcher import start_sovereign_analysis, ai_verify_match
from make_sender import send_products_to_make

# استيراد محرك الذكاء الاصطناعي الجديد
from ai_engine import (
    fetch_product_images, 
    fetch_fragrantica_info, 
    generate_mahwous_description, 
    search_market_price, 
    search_mahwous
)

st.set_page_config(page_title=f"{APP_TITLE} {APP_VERSION}", page_icon=APP_ICON, layout="wide")

# Session State
if 'analysis_running' not in st.session_state: st.session_state.analysis_running = False
if 'processed_count' not in st.session_state: st.session_state.processed_count = 0
if 'total_count' not in st.session_state: st.session_state.total_count = 0
if 'analysis_results' not in st.session_state: st.session_state.analysis_results = []
if 'ignore_list' not in st.session_state: st.session_state.ignore_list = set()
if 'needs_rerun' not in st.session_state: st.session_state.needs_rerun = False
if 'ai_verifications' not in st.session_state: st.session_state.ai_verifications = {}

# CSS مخصص
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap');
    html, body, [data-testid="stAppViewContainer"] {{
        font-family: 'Cairo', sans-serif; direction: rtl; text-align: right;
        background-color: {COLORS['bg_dark']}; color: #e0e0e0;
    }}
    .main-header {{
        background: linear-gradient(135deg, {COLORS['primary']} 0%, {COLORS['secondary']} 100%);
        padding: 2rem; border-radius: 1rem; color: white; margin-bottom: 2rem; text-align: center;
    }}
    .product-card {{
        background: {COLORS['bg_card']}; border: 1px solid rgba(255,255,255,0.1);
        border-radius: 1rem; padding: 1.5rem; margin-bottom: 1.5rem;
    }}
    .comparison-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; align-items: center; }}
    .product-box {{ background: rgba(255,255,255,0.02); padding: 1rem; border-radius: 1rem; text-align: center; }}
    .product-img {{ width: 140px; height: 140px; object-fit: contain; border-radius: 0.5rem; background: #fff; padding: 5px; }}
    .badge {{ padding: 0.3rem 1rem; border-radius: 2rem; font-size: 0.85rem; font-weight: 700; display: inline-block; }}
    .badge-green {{ background: rgba(40, 167, 69, 0.2); color: #28a745; }}
    .badge-yellow {{ background: rgba(255, 152, 0, 0.2); color: #ff9800; }}
    .badge-red {{ background: rgba(220, 53, 69, 0.2); color: #dc3545; }}
    .price-tag {{ font-size: 1.3rem; font-weight: 800; color: #00d2ff; }}
</style>
""", unsafe_allow_html=True)

def main():
    st.markdown(f'<div class="main-header"><h1>{APP_ICON} {APP_TITLE}</h1><p>محرك المطابقة السيادي مع خبير مهووس للمنتجات المفقودة</p></div>', unsafe_allow_html=True)

    with st.sidebar:
        st.header("📂 إدارة البيانات")
        mahwous_file = st.file_uploader("ملف متجر مهووس (المرجع)", type=["csv"])
        competitor_files = st.file_uploader("ملفات المنافسين (للمقارنة)", type=["csv"], accept_multiple_files=True)
        
        st.divider()
        if st.button("🚀 بدء التحليل الشامل", type="primary", use_container_width=True, disabled=st.session_state.analysis_running):
            if mahwous_file and competitor_files:
                st.session_state.analysis_running = True
                with st.spinner("جاري تهيئة المحرك..."):
                    m_df = load_mahwous_store_data(mahwous_file)
                    c_data = {f.name: load_competitor_data(f) for f in competitor_files}
                    start_sovereign_analysis(m_df, c_data)
                    st.rerun()
            else:
                st.error("الرجاء رفع الملفات.")
        
        if st.session_state.analysis_running:
            if st.button("🛑 إيقاف فوري", use_container_width=True):
                st.session_state.analysis_running = False
                st.rerun()

    # شريط التقدم
    if st.session_state.analysis_running or st.session_state.processed_count > 0:
        if st.session_state.total_count > 0:
            progress = min(st.session_state.processed_count / st.session_state.total_count, 1.0)
            st.progress(progress, text=f"جاري الفحص: {st.session_state.processed_count} من {st.session_state.total_count} منتج...")
            if st.session_state.analysis_running:
                time.sleep(0.5)
                st.rerun()

    # لوحة النتائج
    if not st.session_state.analysis_running and st.session_state.analysis_results:
        df = pd.DataFrame(st.session_state.analysis_results)
        df = df[~df['product_name'].isin(st.session_state.ignore_list)]
        
        if not df.empty:
            tab1, tab2, tab3 = st.tabs(["🟢 فرص إضافة (مفقود)", "🟡 مراجعة دقيقة (مشتبه)", "🔴 منتجات متوفرة (مكرر)"])
            
            def render_smart_cards(level):
                filtered = df[df['confidence_level'] == level]
                for idx, row in filtered.iterrows():
                    with st.container():
                        st.markdown(f"""
                        <div class="product-card">
                            <div class="comparison-grid">
                                <div class="product-box">
                                    <p style="font-size: 0.8rem; color: #aaa;">منتج المنافس</p>
                                    <img src="{row.get('image_url', '')}" class="product-img">
                                    <p style="font-weight: 700;">{row['product_name']}</p>
                                    <p class="price-tag">{row['price']} ر.س</p>
                                </div>
                                <div class="product-box">
                                    <p style="font-size: 0.8rem; color: #aaa;">أقرب مطابقة لدينا</p>
                                    <img src="{row.get('match_image', '')}" class="product-img">
                                    <p style="font-weight: 700;">{row.get('match_name', 'لا يوجد مطابقة قريبة')}</p>
                                    <p class="price-tag">{row.get('match_price', 0)} ر.س</p>
                                    <span class="badge badge-{row['confidence_level']}">{row['status']} ({row.get('match_score', 0)}%)</span>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # ─── أزرار خبير مهووس للمنتجات المفقودة (القسم الأخضر) ───
                        if level == 'green':
                            b_cols = st.columns(7)
                            p_name = row['product_name']
                            p_price = row['price']
                            
                            with b_cols[0]:
                                if st.button("🖼️ صور", key=f"img_{idx}"):
                                    with st.spinner("..."):
                                        res = fetch_product_images(p_name)
                                        if res['success'] and res['images']:
                                            st.session_state[f"img_url_{idx}"] = res['images'][0]['url']
                                            st.image(res['images'][0]['url'], width=100)
                                        else: st.warning("لا يوجد")
                            with b_cols[1]:
                                if st.button("🌸 مكونات", key=f"not_{idx}"):
                                    with st.spinner("..."):
                                        res = fetch_fragrantica_info(p_name)
                                        if res['success']:
                                            st.session_state[f"frag_data_{idx}"] = res
                                            st.info(f"القمة: {', '.join(res.get('top_notes', []))}")
                                        else: st.warning("لا يوجد")
                            with b_cols[2]:
                                if st.button("🔎 مهووس", key=f"mhw_{idx}"):
                                    with st.spinner("..."):
                                        res = search_mahwous(p_name)
                                        if res['success']: st.info(f"متوفر؟ {res.get('likely_available')}")
                            with b_cols[3]:
                                if st.button("💹 سوق", key=f"mkt_{idx}"):
                                    with st.spinner("..."):
                                        res = search_market_price(p_name, p_price)
                                        if res['success']: st.info(f"متوسط السوق: {res.get('market_price')} ر.س")
                            with b_cols[4]:
                                if st.button("✍️ وصف", key=f"desc_{idx}"):
                                    with st.spinner("يكتب..."):
                                        frag_data = st.session_state.get(f"frag_data_{idx}")
                                        desc = generate_mahwous_description(p_name, p_price, frag_data)
                                        st.session_state[f"desc_text_{idx}"] = desc
                            with b_cols[5]:
                                if st.button("📤 Make", key=f"mk_grn_{idx}", type="primary"):
                                    payload = row.to_dict()
                                    if f"desc_text_{idx}" in st.session_state:
                                        payload['description'] = st.session_state[f"desc_text_{idx}"]
                                    if f"img_url_{idx}" in st.session_state:
                                        payload['image_url'] = st.session_state[f"img_url_{idx}"]
                                        
                                    res = send_products_to_make([payload])
                                    if res['success']: st.toast("تم الإرسال لـ Make!", icon="🚀")
                                    else: st.error("فشل الإرسال")
                            with b_cols[6]:
                                if st.button("🗑️ تجاهل", key=f"ign_grn_{idx}"):
                                    st.session_state.ignore_list.add(p_name)
                                    st.rerun()

                            # عرض مربع الوصف إذا تم توليده
                            if f"desc_text_{idx}" in st.session_state:
                                edited_desc = st.text_area("راجع الوصف (يمكنك التعديل):", 
                                                           value=st.session_state[f"desc_text_{idx}"], 
                                                           height=250, key=f"ta_{idx}")
                                st.session_state[f"desc_text_{idx}"] = edited_desc

                        # ─── أزرار الأقسام الأخرى (الأصفر والأحمر) ───
                        else:
                            b_cols = st.columns([2, 1, 1, 1])
                            key_check = f"ai_check_{idx}"
                            if key_check in st.session_state.ai_verifications:
                                st.info(f"💡 نتيجة التحقق: {st.session_state.ai_verifications[key_check]['reason']}")
                            
                            with b_cols[1]:
                                if st.button("🔍 تحقق ذكي", key=f"btn_ai_{idx}"):
                                    with st.spinner("جاري التحليل..."):
                                        res = asyncio.run(ai_verify_match(row['product_name'], row.get('match_name', '')))
                                        st.session_state.ai_verifications[key_check] = res
                                        st.rerun()
                            with b_cols[2]:
                                if st.button("✅ أضف لمهووس", key=f"btn_add_{idx}", type="primary"):
                                    res = send_products_to_make([row.to_dict()])
                                    if res['success']: st.toast("تم الإرسال لـ Make!", icon="🚀")
                                    else: st.error("فشل الإرسال")
                            with b_cols[3]:
                                if st.button("🗑️ تجاهل", key=f"btn_ign_{idx}"):
                                    st.session_state.ignore_list.add(row['product_name'])
                                    st.rerun()
                                    
                        st.markdown("<hr style='border: 0.5px solid rgba(255,255,255,0.05);'>", unsafe_allow_html=True)

            with tab1: render_smart_cards('green')
            with tab2: render_smart_cards('yellow')
            with tab3: render_smart_cards('red')

if __name__ == "__main__":
    main()

"""
app.py v7.5 — الواجهة الذكية المتفاعلة (Smart Interactive Dashboard)
══════════════════════════════════════════════════════════════════════
- تصميم عصري يركز على "المقارنة البصرية" والتدقيق اليدوي السريع.
- أزرار ذكاء اصطناعي تفاعلية لكل منتج (إضافة، تجاهل، إعادة تحقق).
- شريط تقدم مباشر يعمل بكفاءة ولا يتجمد.
"""

import streamlit as st
import pandas as pd
import asyncio
import time
from datetime import datetime

from config import APP_TITLE, APP_VERSION, APP_ICON, COLORS
from db_manager import load_mahwous_store_data, load_competitor_data
from sovereign_matcher import start_sovereign_analysis, ai_verify_match
from make_sender import send_products_to_make

# 1. إعدادات الصفحة الاحترافية
st.set_page_config(
    page_title=f"{APP_TITLE} {APP_VERSION}",
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# 2. تهيئة Session State للتحكم الكامل وشريط التقدم
if 'analysis_running' not in st.session_state: st.session_state.analysis_running = False
if 'processed_count' not in st.session_state: st.session_state.processed_count = 0
if 'total_count' not in st.session_state: st.session_state.total_count = 0
if 'analysis_results' not in st.session_state: st.session_state.analysis_results = []
if 'ignore_list' not in st.session_state: st.session_state.ignore_list = set()
if 'needs_rerun' not in st.session_state: st.session_state.needs_rerun = False
if 'ai_verifications' not in st.session_state: st.session_state.ai_verifications = {}

# 3. CSS مخصص (التصميم السيادي)
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap');
    html, body, [data-testid="stAppViewContainer"] {{
        font-family: 'Cairo', sans-serif;
        direction: rtl;
        text-align: right;
        background-color: {COLORS['bg_dark']};
        color: #e0e0e0;
    }}
    .main-header {{
        background: linear-gradient(135deg, {COLORS['primary']} 0%, {COLORS['secondary']} 100%);
        padding: 2.5rem;
        border-radius: 1.5rem;
        color: white;
        margin-bottom: 2.5rem;
        text-align: center;
        box-shadow: 0 10px 20px rgba(0,0,0,0.3);
        border: 1px solid rgba(255,255,255,0.1);
    }}
    .product-card {{
        background: {COLORS['bg_card']};
        border: 1px solid rgba(255,255,255,0.05);
        border-radius: 1.2rem;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        transition: transform 0.2s, box-shadow 0.2s;
    }}
    .product-card:hover {{
        transform: translateY(-5px);
        box-shadow: 0 8px 25px rgba(0,0,0,0.4);
        border-color: {COLORS['accent']};
    }}
    .comparison-grid {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 2rem;
        align-items: center;
    }}
    .product-box {{
        background: rgba(255,255,255,0.03);
        padding: 1rem;
        border-radius: 1rem;
        text-align: center;
    }}
    .product-img {{
        width: 160px;
        height: 160px;
        object-fit: contain;
        border-radius: 0.8rem;
        background: #fff;
        padding: 5px;
        margin-bottom: 0.8rem;
    }}
    .badge {{
        padding: 0.5rem 1.2rem;
        border-radius: 2rem;
        font-size: 0.9rem;
        font-weight: 700;
        display: inline-block;
        margin-bottom: 1rem;
    }}
    .badge-green {{ background: rgba(40, 167, 69, 0.2); color: #28a745; border: 1px solid #28a745; }}
    .badge-yellow {{ background: rgba(255, 152, 0, 0.2); color: #ff9800; border: 1px solid #ff9800; }}
    .badge-red {{ background: rgba(220, 53, 69, 0.2); color: #dc3545; border: 1px solid #dc3545; }}
    .price-tag {{
        font-size: 1.4rem;
        font-weight: 800;
        color: #00d2ff;
        margin: 0.5rem 0;
    }}
    .stButton > button {{
        width: 100%;
        border-radius: 0.8rem;
        font-weight: 700;
        transition: all 0.3s;
    }}
</style>
""", unsafe_allow_html=True)

def main():
    st.markdown(f'<div class="main-header"><h1>{APP_ICON} {APP_TITLE}</h1><p>{APP_VERSION} | محرك المطابقة السيادي — دقة 100% بذكاء اصطناعي تفاعلي</p></div>', unsafe_allow_html=True)

    # الشريط الجانبي الذكي
    with st.sidebar:
        st.header("📂 إدارة البيانات")
        mahwous_file = st.file_uploader("ملف متجر مهووس (المرجع)", type=["csv"])
        competitor_files = st.file_uploader("ملفات المنافسين (للمقارنة)", type=["csv"], accept_multiple_files=True)
        
        st.divider()
        if st.button("🚀 بدء التحليل السيادي", type="primary", use_container_width=True, disabled=st.session_state.analysis_running):
            if mahwous_file and competitor_files:
                # تفعيل حالة التشغيل لكي يظهر شريط التقدم فوراً
                st.session_state.analysis_running = True
                
                with st.spinner("جاري تهيئة محرك المطابقة وتحميل البيانات..."):
                    m_df = load_mahwous_store_data(mahwous_file)
                    c_data = {f.name: load_competitor_data(f) for f in competitor_files}
                    # تشغيل التحليل
                    start_sovereign_analysis(m_df, c_data)
                    st.rerun()
            else:
                st.error("الرجاء رفع كافة الملفات المطلوبة.")
        
        if st.session_state.analysis_running:
            if st.button("🛑 إيقاف فوري", type="secondary", use_container_width=True):
                st.session_state.analysis_running = False
                st.rerun()

    # ==========================================
    # إظهار شريط التقدم المباشر (Progress Bar)
    # ==========================================
    if st.session_state.analysis_running or st.session_state.processed_count > 0:
        if st.session_state.total_count > 0:
            progress = min(st.session_state.processed_count / st.session_state.total_count, 1.0)
            st.progress(progress, text=f"جاري الفحص الذكي: {st.session_state.processed_count} من {st.session_state.total_count} منتج...")
            
            # تحديث الواجهة إذا كان التحليل لا يزال جارياً
            if st.session_state.analysis_running:
                time.sleep(0.5)
                st.rerun()

    # ==========================================
    # لوحة التحكم بالنتائج
    # ==========================================
    if not st.session_state.analysis_running and st.session_state.analysis_results:
        df = pd.DataFrame(st.session_state.analysis_results)
        df = df[~df['product_name'].isin(st.session_state.ignore_list)]
        
        if not df.empty:
            # إحصائيات سريعة
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("إجمالي المكتشف", len(df))
            c2.metric("🟢 مفقود مؤكد", len(df[df['confidence_level'] == 'green']))
            c3.metric("🟡 مشتبه به", len(df[df['confidence_level'] == 'yellow']))
            c4.metric("🔴 مكرر لدينا", len(df[df['confidence_level'] == 'red']))

            # التبويبات الذكية
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
                                    <p style="font-size: 0.75rem; color: #888;">المنافس: {row.get('competitor_name', 'غير معروف')}</p>
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
                        
                        # أزرار الذكاء الاصطناعي التفاعلية
                        b_cols = st.columns([2, 1, 1, 1])
                        
                        # حالة التحقق الذكي
                        key = f"ai_check_{idx}"
                        if key in st.session_state.ai_verifications:
                            res = st.session_state.ai_verifications[key]
                            st.info(f"💡 نتيجة التحقق: {res['reason']}")
                        
                        with b_cols[1]:
                            if st.button("🔍 تحقق ذكي", key=f"btn_ai_{idx}"):
                                with st.spinner("جاري التحليل..."):
                                    res = asyncio.run(ai_verify_match(row['product_name'], row.get('match_name', '')))
                                    st.session_state.ai_verifications[key] = res
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

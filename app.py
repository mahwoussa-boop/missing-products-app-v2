"""
app.py v6.0 — واجهة المستخدم التفاعلية (Visual Comparison & Live Progress)
═══════════════════════════════════════════════════════════
- تصميم عريض وتفاعلي مع مقارنة بصرية (صورة بصورة)
- إصلاح ظهور شريط التقدم فور بدء التحليل
- معالجة في الخلفية (Threading)
- تحديث التقدم لحظياً (Live Updates)
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import asyncio
import time
from datetime import datetime

from config import APP_TITLE, APP_VERSION, APP_ICON
from db_manager import load_mahwous_store_data, load_competitor_data
from ai_matcher import start_background_analysis, ai_deep_verify_single
from make_sender import send_products_to_make

# 1. إعدادات الصفحة
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# 2. تهيئة Session State
if 'analysis_running' not in st.session_state: st.session_state.analysis_running = False
if 'processed_count' not in st.session_state: st.session_state.processed_count = 0
if 'total_count' not in st.session_state: st.session_state.total_count = 0
if 'analysis_results' not in st.session_state: st.session_state.analysis_results = []
if 'ignore_list' not in st.session_state: st.session_state.ignore_list = set()

# 3. CSS مخصص
st.markdown("""
<style>
    .stApp { direction: rtl; }
    [data-testid="stSidebar"] { direction: rtl; }
    .main-header {
        background: linear-gradient(90deg, #0f172a 0%, #1e293b 100%);
        padding: 2rem;
        border-radius: 1rem;
        color: white;
        margin-bottom: 2rem;
        text-align: center;
        border-bottom: 4px solid #3b82f6;
    }
    .product-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 1rem;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
    }
    .badge {
        padding: 0.4rem 1rem;
        border-radius: 2rem;
        font-size: 0.85rem;
        font-weight: 700;
        display: inline-block;
        margin-bottom: 0.5rem;
    }
    .badge-green { background: #dcfce7; color: #166534; }
    .badge-yellow { background: #fef9c3; color: #854d0e; }
    .badge-red { background: #fee2e2; color: #991b1b; }
    .stButton > button {
        border-radius: 0.5rem;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

def main():
    st.markdown(f'<div class="main-header"><h1>{APP_ICON} {APP_TITLE}</h1><p>{APP_VERSION} | نظام ذكاء الأعمال للمنافسين - معالجة فائقة السرعة</p></div>', unsafe_allow_html=True)

    # الشريط الجانبي
    with st.sidebar:
        st.header("📂 مصادر البيانات")
        mahwous_file = st.file_uploader("ملف متجر مهووس (CSV)", type=["csv"])
        competitor_files = st.file_uploader("ملفات المنافسين (CSV)", type=["csv"], accept_multiple_files=True)
        
        st.divider()
        if st.button("🚀 بدء التحليل الشامل", type="primary", use_container_width=True, disabled=st.session_state.analysis_running):
            if mahwous_file and competitor_files:
                # تحميل البيانات
                m_df = load_mahwous_store_data(mahwous_file)
                c_data = {f.name: load_competitor_data(f) for f in competitor_files}
                
                # تفعيل حالة التشغيل فوراً ليعمل شريط التقدم دون تأخير
                st.session_state.analysis_running = True
                
                # بدء المعالجة في الخلفية
                start_background_analysis(m_df, c_data)
                st.rerun()
            else:
                st.error("الرجاء رفع كافة الملفات المطلوبة.")
        
        if st.session_state.analysis_running:
            if st.button("🛑 إيقاف المعالجة", type="secondary", use_container_width=True):
                st.session_state.analysis_running = False
                st.rerun()

    # عرض التقدم المباشر
    if st.session_state.analysis_running or st.session_state.processed_count > 0:
        progress_container = st.container()
        with progress_container:
            cols = st.columns([4, 1])
            progress = st.session_state.processed_count / st.session_state.total_count if st.session_state.total_count > 0 else 0
            cols[0].progress(progress, text=f"جاري المعالجة: {st.session_state.processed_count} / {st.session_state.total_count}")
            cols[1].write(f"**{progress*100:.1f}%**")
            
            if st.session_state.analysis_running:
                time.sleep(0.5)
                st.rerun()

    # لوحة الإحصائيات والنتائج
    if st.session_state.analysis_results:
        df = pd.DataFrame(st.session_state.analysis_results)
        # تصفية المتجاهلة
        df = df[~df['product_name'].isin(st.session_state.ignore_list)]
        
        if not df.empty:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("إجمالي المكتشف", len(df))
            c2.metric("🟢 مفقود مؤكد", len(df[df['confidence_level'] == 'green']))
            c3.metric("🟡 مراجعة", len(df[df['confidence_level'] == 'yellow']))
            c4.metric("🔴 مكرر", len(df[df['confidence_level'] == 'red']))

            # عرض النتائج في Tabs
            tab1, tab2, tab3 = st.tabs(["🟢 مفقود مؤكد", "🟡 يحتاج مراجعة", "🔴 مكرر"])
            
            def render_products(level):
                filtered = df[df['confidence_level'] == level]
                for _, row in filtered.iterrows():
                    with st.container():
                        st.markdown(f"""
                        <div class="product-card">
                            <div style="display: flex; gap: 1.5rem; align-items: start;">
                                <div style="flex: 1; text-align: center;">
                                    <p style="font-size: 0.8rem; color: #64748b;">🏪 المنافس</p>
                                    <img src="{row.get('image_url', '')}" style="width: 100%; max-width: 140px; border-radius: 0.5rem; border: 1px solid #e2e8f0; object-fit: contain;" onerror="this.src='https://via.placeholder.com/140?text=No+Image'">
                                </div>
                                <div style="flex: 1; text-align: center;">
                                    <p style="font-size: 0.8rem; color: #64748b;">📦 أقرب مطابقة لدينا</p>
                                    <img src="{row.get('match_image', '')}" style="width: 100%; max-width: 140px; border-radius: 0.5rem; border: 1px solid #e2e8f0; object-fit: contain;" onerror="this.style.display='none'">
                                </div>
                                <div style="flex: 3;">
                                    <span class="badge badge-{row['confidence_level']}">{row['status']}</span>
                                    <h3 style="margin: 0.5rem 0; font-size: 1.1rem;">{row['product_name']}</h3>
                                    <p style="color: #3b82f6; font-weight: 700; font-size: 1.2rem;">{row['price']} ر.س</p>
                                    <p style="color: #64748b; font-size: 0.9rem;">المنافس: {row.get('competitor_name', 'غير معروف')}</p>
                                    <hr style="margin: 1rem 0; border: 0; border-top: 1px solid #e2e8f0;">
                                    <p style="font-size: 0.95rem;"><b>أقرب مطابقة لدينا:</b> {row.get('match_name', 'لا يوجد')}</p>
                                </div>
                                <div style="flex: 1; display: flex; flex-direction: column; gap: 0.5rem;">
                                    <p style="text-align: center; font-weight: 700; font-size: 0.9rem;">الإجراءات</p>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # أزرار الإجراءات (خارج الـ HTML لتعمل مع Streamlit)
                        btn_cols = st.columns([4, 1.5, 1.5, 1.5])
                        with btn_cols[1]:
                            if st.button("✅ أضف لـ Make", key=f"make_{row['product_name']}"):
                                res = send_products_to_make([row.to_dict()])
                                if res['success']: st.toast("✅ تم الإرسال بنجاح!", icon="🚀")
                                else: st.error("فشل الإرسال")
                        with btn_cols[2]:
                            if st.button("🔍 تحقق عميق", key=f"ai_{row['product_name']}"):
                                with st.spinner("جاري إعادة التحقق..."):
                                    res = asyncio.run(ai_deep_verify_single(row['product_name'], row.get('match_name', '')))
                                    st.info(f"النتيجة: {res['reason']}")
                        with btn_cols[3]:
                            if st.button("🗑️ تجاهل", key=f"ign_{row['product_name']}"):
                                st.session_state.ignore_list.add(row['product_name'])
                                st.rerun()

            with tab1: render_products('green')
            with tab2: render_products('yellow')
            with tab3: render_products('red')

if __name__ == "__main__":
    main()

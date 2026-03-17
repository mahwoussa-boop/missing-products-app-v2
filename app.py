"""
app.py v3.0 — واجهة المستخدم الاحترافية لنظام المنتجات المفقودة
═══════════════════════════════════════════════════════════
تصميم عريض - بطاقات عرض ذكية - لوحة إحصائيات متقدمة
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import asyncio
from datetime import datetime

from config import APP_TITLE, APP_VERSION, APP_ICON
from db_manager import load_mahwous_store_data, load_competitor_data
from ai_matcher import process_competitors, ai_deep_verify
from make_sender import send_products_to_make, verify_webhook

# 1. إعدادات الصفحة
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# 2. CSS مخصص
st.markdown("""
<style>
    .stApp { direction: rtl; }
    [data-testid="stSidebar"] { direction: rtl; }
    .main-header {
        background: linear-gradient(90deg, #1e3a8a 0%, #3b82f6 100%);
        padding: 2rem;
        border-radius: 1rem;
        color: white;
        margin-bottom: 2rem;
        text-align: center;
    }
    .metric-card {
        background: #f8fafc;
        padding: 1.5rem;
        border-radius: 0.75rem;
        border-right: 5px solid #3b82f6;
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
    }
    .product-card {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 0.75rem;
        padding: 1rem;
        margin-bottom: 1rem;
        transition: transform 0.2s;
    }
    .product-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1);
    }
    .badge {
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.875rem;
        font-weight: 600;
    }
    .badge-green { background: #dcfce7; color: #166534; }
    .badge-yellow { background: #fef9c3; color: #854d0e; }
    .badge-red { background: #fee2e2; color: #991b1b; }
</style>
""", unsafe_allow_html=True)

# 3. واجهة المستخدم الرئيسية
def main():
    st.markdown(f'<div class="main-header"><h1>{APP_ICON} {APP_TITLE}</h1><p>{APP_VERSION} | نظام ذكاء الأعمال للمنافسين</p></div>', unsafe_allow_html=True)

    # الشريط الجانبي
    with st.sidebar:
        st.header("📂 رفع البيانات")
        mahwous_file = st.file_uploader("ملف متجر مهووس (CSV)", type=["csv"])
        competitor_files = st.file_uploader("ملفات المنافسين (CSV)", type=["csv"], accept_multiple_files=True)
        
        st.divider()
        st.header("⚙️ الإعدادات")
        use_ai = st.checkbox("تفعيل التحقق العميق بالـ AI", value=True)
        
        if st.button("🚀 بدء التحليل", type="primary", use_container_width=True):
            if mahwous_file and competitor_files:
                st.session_state.analyze = True
            else:
                st.error("الرجاء رفع كافة الملفات المطلوبة.")

    # عرض النتائج
    if 'analyze' in st.session_state and st.session_state.analyze:
        with st.spinner("جاري تحليل البيانات ومطابقة المنتجات..."):
            # تحميل البيانات
            mahwous_df = load_mahwous_store_data(mahwous_file)
            competitor_data = {}
            for f in competitor_files:
                name = f.name.replace(".csv", "")
                competitor_data[name] = load_competitor_data(f)
            
            # المعالجة
            results_df = process_competitors(mahwous_df, competitor_data, 
                                          progress_callback=lambda p, t, m: st.sidebar.progress(p/t, text=m))
            st.session_state.results = results_df
            st.session_state.analyze = False

    if 'results' in st.session_state:
        df = st.session_state.results
        
        # 1. لوحة الإحصائيات
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("إجمالي المنتجات", len(df))
        with c2:
            missing = len(df[df['confidence_level'] == 'green'])
            st.metric("🟢 مفقود مؤكد", missing)
        with c3:
            review = len(df[df['confidence_level'] == 'yellow'])
            st.metric("🟡 يحتاج مراجعة", review)
        with c4:
            dupes = len(df[df['confidence_level'] == 'red'])
            st.metric("🔴 مكرر", dupes)

        # 2. الرسوم البيانية
        col_left, col_right = st.columns(2)
        with col_left:
            fig = px.pie(df, names='status', title='توزيع حالة المنتجات', hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
        with col_right:
            brand_counts = df[df['confidence_level'] == 'green']['brand'].value_counts().head(10)
            fig2 = px.bar(brand_counts, title='أعلى 10 ماركات مفقودة')
            st.plotly_chart(fig2, use_container_width=True)

        # 3. عرض المنتجات
        st.header("🔍 تفاصيل المنتجات المكتشفة")
        
        tab1, tab2, tab3 = st.tabs(["🟢 مفقود مؤكد", "🟡 يحتاج مراجعة", "🔴 مكرر"])
        
        def render_tab_content(status_level):
            filtered = df[df['confidence_level'] == status_level]
            if filtered.empty:
                st.info("لا توجد منتجات في هذه الفئة.")
                return

            for _, row in filtered.iterrows():
                with st.container():
                    cols = st.columns([1, 4, 2])
                    with cols[0]:
                        st.image(row.get('image_url', ''), use_container_width=True)
                    with cols[1]:
                        st.subheader(row['product_name'])
                        st.write(f"**الماركة:** {row.get('brand', 'غير معروف')} | **المنافس:** {row['competitor_name']}")
                        st.write(f"**السعر:** {row['price']} ر.س")
                        if status_level != 'green':
                            st.write(f"**أقرب مطابقة:** {row['match_name']} ({row['confidence_score']:.1f}%)")
                    
                    with cols[2]:
                        st.write("### الإجراءات")
                        if st.button("➕ إضافة لـ Make", key=f"add_{row['product_name']}"):
                            res = send_products_to_make([row.to_dict()])
                            if res['success']: st.success("تم الإرسال!")
                            else: st.error("فشل الإرسال")
                        
                        if st.button("🧐 تحقق ذكي", key=f"verify_{row['product_name']}"):
                            is_match, reason = asyncio.run(ai_deep_verify(row['product_name'], row.get('match_name', '')))
                            st.info(f"النتيجة: {'متطابق' if is_match else 'مختلف'} \n\n {reason}")

        with tab1: render_tab_content('green')
        with tab2: render_tab_content('yellow')
        with tab3: render_tab_content('red')

if __name__ == "__main__":
    main()

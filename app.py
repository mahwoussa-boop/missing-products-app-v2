"""
app.py v7.1 — واجهة المستخدم التفاعلية التحديث الشامل
═══════════════════════════════════════════════════════════════
- تصميم احترافي باستخدام layout='wide'
- عرض الصور جنباً إلى جنب للمقارنة اليدوية الدقيقة
- معالجة آمنة للحالة (Session State) وتحديث حي لشريط التقدم
- هوية بصرية تتناسب مع متجر "مهووس" باللغة العربية
"""

import streamlit as st
import pandas as pd
import time
import asyncio
from db_manager import load_mahwous_store_data, load_competitor_data
from ai_matcher import start_background_analysis, ai_deep_verify_single
from make_sender import send_products_to_make
from config import APP_TITLE, APP_ICON

# إعدادات الصفحة (Wide Layout)
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded"
)

# تنسيق CSS احترافي (RTL & Cards)
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
        border-bottom: 4px solid #6C63FF;
    }
    
    .product-card {
        background: #1a1a2e;
        border: 1px solid #2d3748;
        border-radius: 1rem;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
        color: #e2e8f0;
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
    
    .img-container {
        text-align: center;
        padding: 10px;
        background: #ffffff;
        border-radius: 0.5rem;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
    }
    
    .img-container img {
        max-width: 150px;
        max-height: 150px;
        object-fit: contain;
    }
    
    .img-title {
        font-size: 0.8rem;
        color: #4a5568;
        margin-bottom: 5px;
        font-weight: bold;
    }
    
    .stButton > button {
        border-radius: 0.5rem;
        font-weight: 600;
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# تهيئة المتغيرات في Session State
if 'analysis_running' not in st.session_state:
    st.session_state.analysis_running = False
if 'processed_count' not in st.session_state:
    st.session_state.processed_count = 0
if 'total_count' not in st.session_state:
    st.session_state.total_count = 0
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = []
if 'ignore_list' not in st.session_state:
    st.session_state.ignore_list = set()

def render_products(level: str, filtered_results: list):
    """عرض المنتجات داخل بطاقات أنيقة مع مقارنة الصور جنباً إلى جنب."""
    if not filtered_results:
        st.info("لا توجد منتجات في هذا التصنيف حالياً.")
        return

    for idx, row in enumerate(filtered_results):
        prod_name = row.get("product_name", "بدون اسم")
        
        # تخطي المنتجات المتجاهلة
        if prod_name in st.session_state.ignore_list:
            continue

        comp_img = row.get("image_url", "")
        mah_img = row.get("match_image", "")
        status = row.get("status", "")
        price = row.get("price", 0.0)
        brand = row.get("brand", "غير معروف")
        comp_name = row.get("competitor_name", "")
        match_name = row.get("match_name", "لا يوجد")
        confidence = row.get("confidence_level", "yellow")

        st.markdown('<div class="product-card">', unsafe_allow_html=True)
        
        # تقسيم البطاقة إلى 3 أعمدة (صورة المنافس | التفاصيل والإجراءات | صورة منتجنا)
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col1:
            st.markdown(f'''
                <div class="img-container">
                    <div class="img-title">صورة المنافس</div>
                    <img src="{comp_img}" onerror="this.src='https://via.placeholder.com/150?text=No+Image'">
                </div>
            ''', unsafe_allow_html=True)
            
        with col2:
            st.markdown(f'<span class="badge badge-{confidence}">{status}</span>', unsafe_allow_html=True)
            st.markdown(f'<h3 style="margin: 0.5rem 0; color: white;">{prod_name}</h3>', unsafe_allow_html=True)
            st.markdown(f'<p style="color: #6C63FF; font-weight: 700; font-size: 1.2rem;">{price} ر.س</p>', unsafe_allow_html=True)
            st.markdown(f'<p style="color: #a0aec0;">الماركة: {brand} | المنافس: {comp_name}</p>', unsafe_allow_html=True)
            st.markdown('<hr style="border-top: 1px solid #2d3748; margin: 1rem 0;">', unsafe_allow_html=True)
            st.markdown(f'<p style="color: #e2e8f0;"><b>أقرب مطابقة لدينا:</b> {match_name}</p>', unsafe_allow_html=True)
            
            # أزرار الإجراءات
            btn_cols = st.columns(3)
            with btn_cols[0]:
                if st.button("✅ أضف لـ Make", key=f"make_{level}_{idx}"):
                    with st.spinner("جاري الإرسال..."):
                        res = send_products_to_make([row])
                        if res.get("success"):
                            st.toast("✅ تم الإرسال بنجاح!", icon="🚀")
                            st.session_state.ignore_list.add(prod_name)
                            st.rerun()
                        else:
                            st.error("فشل الإرسال")
            with btn_cols[1]:
                if st.button("🔍 تحقق عميق", key=f"ai_{level}_{idx}"):
                    with st.spinner("جاري التحقق عبر الذكاء الاصطناعي..."):
                        ai_res = asyncio.run(ai_deep_verify_single(prod_name, match_name))
                        st.info(f"النتيجة: {ai_res.get('reason')}")
            with btn_cols[2]:
                if st.button("🗑️ تجاهل", key=f"ign_{level}_{idx}"):
                    st.session_state.ignore_list.add(prod_name)
                    st.rerun()
                    
        with col3:
            if mah_img:
                st.markdown(f'''
                    <div class="img-container">
                        <div class="img-title">منتجنا (للمقارنة)</div>
                        <img src="{mah_img}" onerror="this.src='https://via.placeholder.com/150?text=No+Image'">
                    </div>
                ''', unsafe_allow_html=True)
            else:
                st.markdown('''
                    <div class="img-container" style="background: #f8fafc;">
                        <div class="img-title">لا يوجد منتج مطابق بصرياً</div>
                    </div>
                ''', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

def main():
    st.markdown(f'''
        <div class="main-header">
            <h1>{APP_ICON} {APP_TITLE}</h1>
            <p>نظام ذكاء الأعمال للمنافسين - معالجة فائقة السرعة ودقة مطلقة</p>
        </div>
    ''', unsafe_allow_html=True)

    with st.sidebar:
        st.header("📂 مصادر البيانات")
        mahwous_file = st.file_uploader("ملف متجر مهووس (CSV)", type=['csv'])
        st.divider()
        competitor_files = st.file_uploader("ملفات المنافسين (CSV)", type=['csv'], accept_multiple_files=True)
        
        st.divider()
        if st.button("🚀 بدء التحليل الشامل", type="primary", use_container_width=True, disabled=st.session_state.analysis_running):
            if not mahwous_file or not competitor_files:
                st.error("الرجاء رفع كافة الملفات المطلوبة.")
            else:
                st.session_state.analysis_results = []
                st.session_state.processed_count = 0
                st.session_state.ignore_list = set()
                st.session_state.analysis_running = True
                
                # تحميل البيانات
                m_df = load_mahwous_store_data(mahwous_file)
                c_data = {f.name: load_competitor_data(f) for f in competitor_files}
                
                # بدء المعالجة في الخلفية
                start_background_analysis(m_df, c_data)
                st.rerun()

        if st.session_state.analysis_running:
            if st.button("🛑 إيقاف المعالجة", type="secondary", use_container_width=True):
                st.session_state.analysis_running = False
                st.rerun()

    # شريط التقدم اللحظي
    if st.session_state.analysis_running:
        progress_container = st.container()
        with progress_container:
            total = st.session_state.total_count
            current = st.session_state.processed_count
            if total > 0:
                pct = min(current / total, 1.0)
                st.progress(pct, text=f"جاري المعالجة: {current} / {total} (**{pct*100:.1f}%**)")
            else:
                st.progress(0, text="جاري تحضير البيانات...")
            time.sleep(1)
            st.rerun()

    # عرض النتائج
    if st.session_state.analysis_results:
        results = st.session_state.analysis_results
        
        green_list = [r for r in results if r.get('confidence_level') == 'green']
        yellow_list = [r for r in results if r.get('confidence_level') == 'yellow']
        red_list = [r for r in results if r.get('confidence_level') == 'red']

        st.subheader(f"📊 إجمالي المكتشف: {len(results)}")
        
        tab1, tab2, tab3 = st.tabs([
            f"🟢 مفقود مؤكد ({len(green_list)})", 
            f"🟡 يحتاج مراجعة ({len(yellow_list)})", 
            f"🔴 مكرر (>90%) ({len(red_list)})"
        ])

        with tab1:
            render_products("green", green_list)
        with tab2:
            render_products("yellow", yellow_list)
        with tab3:
            render_products("red", red_list)

if __name__ == "__main__":
    main()

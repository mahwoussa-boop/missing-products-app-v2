"""
missing_products_app/app.py
نظام إدارة المنتجات المفقودة الذكي — متجر مهووس
الإصدار V9.0 الشامل - مهندس نظام مهووس الذكي (المصحح والمتوافق 100%)
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from db_manager import load_mahwous_store_data, load_competitor_data
from ai_matcher import process_competitors, get_brand_statistics
from make_sender import send_products_to_make

# --- إعدادات الصفحة --- #
st.set_page_config(
    page_title="نظام المنتجات المفقودة V9.0 — مهووس",
    page_icon="🌬️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS مخصص للواجهة العربية والهوية البصرية لمهووس --- #
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Tajawal', sans-serif;
        direction: rtl;
        text-align: right;
    }
    .stApp { background-color: #0e1117; color: #ffffff; }
    
    /* تنسيق البطاقات الإحصائية */
    .metric-card {
        background: linear-gradient(135deg, #1e3a5f 0%, #0a192f 100%);
        border: 1px solid #2d6a9f;
        border-radius: 15px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
    .metric-value { font-size: 2.2rem; font-weight: bold; color: #00d4ff; }
    .metric-label { font-size: 1rem; color: #a0aec0; margin-top: 5px; }
    
    /* تنسيق الجداول */
    .stDataFrame { border-radius: 10px; overflow: hidden; border: 1px solid #2d3748; }
</style>
""", unsafe_allow_html=True)

# --- إدارة حالة الجلسة (Session State) --- #
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None

# --- الواجهة الرئيسية --- #
col_title, col_logo = st.columns([0.8, 0.2])
with col_title:
    st.title("🌬️ نظام إدارة المنتجات المفقودة الذكي V9.0")
    st.markdown("<p style='font-size: 1.2rem; color: #00d4ff;'>إصدار مهندس نظام مهووس الذكي الشامل</p>", unsafe_allow_html=True)

# --- الشريط الجانبي (Sidebar) --- #
with st.sidebar:
    st.header("📂 مصادر البيانات")
    
    st.subheader("1. ملف متجر مهووس (CSV)")
    mahwous_file = st.file_uploader("ارفع ملف متجر مهووس", type=["csv"], key="mahwous_upload")
    
    st.subheader("2. ملفات المنافسين (CSV)")
    competitor_files = st.file_uploader("ارفع ملفات المنافسين (حتى 15 ملف)", type=["csv"], accept_multiple_files=True, key="comp_upload")
    
    st.divider()
    
    if st.button("🚀 بدء التحليل الشامل V9.0", type="primary", use_container_width=True):
        if mahwous_file and competitor_files:
            with st.spinner("جاري تحميل ومعالجة البيانات بدقة متناهية..."):
                try:
                    # تحميل بيانات مهووس
                    mahwous_df = load_mahwous_store_data(mahwous_file)
                    
                    # إصلاح: تحميل بيانات المنافسين كقاموس (Dictionary) ليتوافق مع ai_matcher
                    competitors_data = {f.name: load_competitor_data(f) for f in competitor_files}
                    
                    if not mahwous_df.empty and competitors_data:
                        # عملية المطابقة الذكية V9.0
                        st.session_state.analysis_results = process_competitors(mahwous_df, competitors_data)
                        st.success("✅ اكتمل التحليل بنجاح! تم تحديث كافة التبويبات.")
                    else:
                        st.error("❌ حدث خطأ: البيانات فارغة أو غير صالحة. يرجى التأكد من صيغة CSV.")
                except Exception as e:
                    st.error(f"❌ حدث خطأ أثناء المعالجة: {e}")
        else:
            st.warning("⚠️ يرجى رفع كافة الملفات المطلوبة أولاً.")

# --- عرض النتائج في حال توفرها --- #
if st.session_state.analysis_results is not None:
    results_df = st.session_state.analysis_results
    
    # تصنيف النتائج بناءً على العتبات الجديدة V9.0
    missing_confirmed = results_df[results_df['status'] == "منتج مفقود مؤكد"]
    needs_review = results_df[results_df['status'] == "يحتاج مراجعة"]
    available_duplicate = results_df[results_df['status'] == "متوفر (مكرر)"]

    # --- بطاقات الإحصاء العلوية --- #
    st.subheader("📊 نظرة عامة على السوق")
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f"<div class='metric-card'><div class='metric-value'>{len(missing_confirmed)}</div><div class='metric-label'>مفقود مؤكد 🔴</div></div>", unsafe_allow_html=True)
    with m2:
        st.markdown(f"<div class='metric-card'><div class='metric-value'>{len(needs_review)}</div><div class='metric-label'>يحتاج مراجعة 🟡</div></div>", unsafe_allow_html=True)
    with m3:
        st.markdown(f"<div class='metric-card'><div class='metric-value'>{len(available_duplicate)}</div><div class='metric-label'>مكرر/متوفر ✅</div></div>", unsafe_allow_html=True)
    with m4:
        st.markdown(f"<div class='metric-card'><div class='metric-value'>{len(results_df)}</div><div class='metric-label'>إجمالي المنتجات</div></div>", unsafe_allow_html=True)

    st.divider()

    # --- التبويبات المحدثة V9.0 --- #
    tab1, tab2, tab3, tab4 = st.tabs([
        "🔴 مفقود مؤكد (فرص بيعية)", 
        "🟡 يحتاج مراجعة دقيقة", 
        "✅ التحقق من المتوفر", 
        "🔥 أهم 10 ماركات مفقودة"
    ])

    # 1. تبويب المنتجات المفقودة المؤكدة
    with tab1:
        st.subheader("المنتجات المفقودة بنسبة 100% (غير متوفرة لدينا)")
        if not missing_confirmed.empty:
            # فلاتر سريعة
            fcol1, fcol2 = st.columns(2)
            with fcol1:
                comp_filter = st.multiselect("تصفية حسب المنافس", options=missing_confirmed['competitor_name'].unique())
            with fcol2:
                brand_filter = st.multiselect("تصفية حسب الماركة", options=missing_confirmed['brand'].unique())
            
            display_df = missing_confirmed.copy()
            if comp_filter: display_df = display_df[display_df['competitor_name'].isin(comp_filter)]
            if brand_filter: display_df = display_df[display_df['brand'].isin(brand_filter)]
            
            display_df.insert(0, "تحديد", False)
            edited_df = st.data_editor(
                display_df[['تحديد', 'product_name', 'price', 'competitor_name', 'brand', 'image_url']],
                column_config={
                    "image_url": st.column_config.ImageColumn("صورة المنتج"),
                    "price": st.column_config.NumberColumn("السعر", format="%.2f ر.س"),
                    "product_name": "اسم المنتج المفقود",
                    "competitor_name": "المنافس",
                    "brand": "الماركة"
                },
                hide_index=True,
                use_container_width=True,
                key="missing_editor"
            )
            
            selected_to_send = edited_df[edited_df["تحديد"] == True]
            if st.button(f"🚀 إرسال {len(selected_to_send)} منتج إلى Make.com", type="primary", disabled=len(selected_to_send)==0):
                with st.spinner("جاري الإرسال للأتمتة..."):
                    result = send_products_to_make(selected_to_send.to_dict('records'))
                    st.success("تم إرسال المنتجات المحددة بنجاح!")
        else:
            st.info("لا توجد منتجات مفقودة مؤكدة حالياً.")

    # 2. تبويب يحتاج مراجعة (لمنع إضاعة الفرص)
    with tab2:
        st.subheader("منتجات مشبوهة (تطابق 40% - 80%)")
        st.warning("هذه المنتجات قد تكون متوفرة لدينا بأسماء مختلفة. يرجى المراجعة يدوياً لمنع التكرار.")
        if not needs_review.empty:
            st.dataframe(
                needs_review[['product_name', 'matched_product', 'confidence_score', 'competitor_name', 'image_url']],
                column_config={
                    "image_url": st.column_config.ImageColumn("صورة المنافس"),
                    "confidence_score": st.column_config.ProgressColumn("نسبة التطابق", format="%f%%", min_value=0, max_value=100),
                    "product_name": "اسم المنتج عند المنافس",
                    "matched_product": "أقرب منتج مطابق لدينا"
                },
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("لا توجد منتجات تحتاج مراجعة.")

    # 3. تبويب التحقق من المتوفر
    with tab3:
        st.subheader("التحقق من المنتجات المتوفرة (تطابق > 80%)")
        st.info("هنا نعرض ما صنفناه كـ 'مكرر'. تأكد من صحة المطابقة البصرية.")
        if not available_duplicate.empty:
            for idx, row in available_duplicate.head(20).iterrows(): # عرض أول 20 للتحقق
                with st.container():
                    c1, c2, c3 = st.columns([0.4, 0.2, 0.4])
                    with c1:
                        # حماية في حال عدم توفر الصورة
                        comp_img = row['image_url'] if pd.notna(row['image_url']) and row['image_url'] else "https://via.placeholder.com/150?text=No+Image"
                        st.image(comp_img, width=150, caption="صورة المنافس")
                        st.write(f"**{row['product_name']}**")
                    with c2:
                        st.markdown(f"<div style='text-align:center; margin-top:50px;'><h2 style='color:#00ff00;'>{int(row['confidence_score'])}%</h2><p>تطابق</p></div>", unsafe_allow_html=True)
                    with c3:
                        # حماية في حال عدم توفر الصورة
                        mah_img = row['matched_image'] if pd.notna(row['matched_image']) and row['matched_image'] else "https://via.placeholder.com/150?text=No+Image"
                        st.image(mah_img, width=150, caption="منتجنا المطابق")
                        st.write(f"**{row['matched_product']}**")
                    st.divider()
        else:
            st.info("لا توجد منتجات مكررة.")

    # 4. تبويب أهم 10 ماركات مفقودة
    with tab4:
        st.subheader("🔥 رادار الفرص: أهم 10 ماركات مفقودة")
        brand_stats = get_brand_statistics(results_df)
        if not brand_stats.empty:
            col_chart, col_data = st.columns([0.6, 0.4])
            with col_chart:
                fig = px.bar(
                    brand_stats, 
                    x='count', 
                    y='brand', 
                    orientation='h',
                    title="عدد المنتجات المفقودة حسب الماركة",
                    labels={'count': 'عدد المنتجات', 'brand': 'الماركة'},
                    color='count',
                    color_continuous_scale='Blues'
                )
                fig.update_layout(yaxis={'categoryorder':'total ascending'}, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color="white")
                st.plotly_chart(fig, use_container_width=True)
            with col_data:
                st.write("**قائمة الماركات الأكثر طلباً:**")
                st.dataframe(brand_stats, hide_index=True, use_container_width=True)
        else:
            st.info("لا توجد بيانات كافية لحساب إحصائيات الماركات.")

else:
    # واجهة الترحيب في حال عدم وجود نتائج
    st.markdown("""
    <div style='text-align: center; padding: 50px;'>
        <h2 style='color: #a0aec0;'>مرحباً بك في الإصدار V9.0 الشامل</h2>
        <p style='color: #718096;'>يرجى رفع ملفات CSV من القائمة الجانبية للبدء في تحليل السوق واكتشاف الفرص المفقودة.</p>
    </div>
    """, unsafe_allow_html=True)

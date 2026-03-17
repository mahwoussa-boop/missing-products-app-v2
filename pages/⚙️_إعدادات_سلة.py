"""
صفحة إعدادات سلة - إدخال IDs التصنيفات والماركات
═══════════════════════════════════════════════════
أدخل IDs من لوحة تحكم سلة مرة واحدة وسيتم حفظها تلقائياً
"""

import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from salla_ids_manager import (
    load_ids, save_ids,
    load_mahwous_categories_list,
    load_mahwous_brands_list,
    get_stats
)

st.set_page_config(
    page_title="إعدادات سلة - مهووس",
    page_icon="⚙️",
    layout="wide"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap');
    html, body, [class*="st-"] { font-family: 'Cairo', sans-serif; }
    .stApp { direction: rtl; }
    .id-badge { background: #1e3a5f; color: #00d2ff; padding: 3px 10px; border-radius: 8px; font-size: 0.9rem; font-weight: bold; }
    .missing-badge { background: #3a1e1e; color: #ff6b6b; padding: 3px 10px; border-radius: 8px; font-size: 0.9rem; }
</style>
""", unsafe_allow_html=True)

st.title("⚙️ إعدادات سلة - IDs التصنيفات والماركات")
st.markdown("أدخل IDs من **لوحة تحكم سلة** مرة واحدة وسيتم حفظها تلقائياً لاستخدامها عند إرسال المنتجات.")

# ─── إحصائيات ───
stats = get_stats()
col1, col2, col3, col4 = st.columns(4)
col1.metric("📂 التصنيفات الكلية", stats["categories_total"])
col2.metric("✅ تصنيفات بـ ID", stats["categories_saved"])
col3.metric("🏷️ الماركات الكلية", stats["brands_total"])
col4.metric("✅ ماركات بـ ID", stats["brands_saved"])

if stats["updated_at"] != "لم يتم الحفظ بعد":
    st.success(f"✅ آخر حفظ: {stats['updated_at']}")
else:
    st.warning("⚠️ لم يتم حفظ أي IDs بعد. أدخل IDs من سلة أدناه.")

st.divider()

# ─── تحميل البيانات الحالية ───
data = load_ids()

# ─── تبويبات ───
tab1, tab2, tab3 = st.tabs(["📂 التصنيفات", "🏷️ الماركات", "📋 كيفية الحصول على IDs"])

# ══════════════════════════════════════════
# تبويب التصنيفات
# ══════════════════════════════════════════
with tab1:
    st.subheader("📂 IDs التصنيفات")
    st.info("💡 احصل على ID التصنيف من سلة: المنتجات → التصنيفات → اضغط على التصنيف → انظر الرقم في الرابط")
    
    categories_list = load_mahwous_categories_list()
    saved_cats = data.get("categories", {})
    
    # إضافة تصنيف جديد
    with st.expander("➕ إضافة/تعديل ID تصنيف", expanded=True):
        col_a, col_b, col_c = st.columns([3, 2, 1])
        with col_a:
            selected_cat = st.selectbox(
                "اختر التصنيف",
                options=categories_list,
                key="new_cat_name"
            )
        with col_b:
            cat_id_input = st.text_input(
                "ID التصنيف من سلة",
                value=saved_cats.get(selected_cat, ""),
                placeholder="مثال: 1234567890",
                key="new_cat_id"
            )
        with col_c:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("💾 حفظ", key="save_cat", use_container_width=True):
                if selected_cat and cat_id_input.strip():
                    data["categories"][selected_cat] = cat_id_input.strip()
                    if save_ids(data):
                        st.success(f"✅ تم حفظ: {selected_cat} → {cat_id_input.strip()}")
                        st.rerun()
                else:
                    st.error("أدخل ID التصنيف")
    
    # إدخال جماعي
    with st.expander("📥 إدخال جماعي (JSON)", expanded=False):
        st.markdown("الصق JSON بالشكل: `{\"اسم التصنيف\": \"ID\", ...}`")
        bulk_cats = st.text_area("JSON التصنيفات", height=200, key="bulk_cats_json",
                                  placeholder='{"العطور": "1234567", "عطور نسائية": "7654321"}')
        if st.button("💾 حفظ الكل", key="save_bulk_cats"):
            try:
                import json
                new_cats = json.loads(bulk_cats)
                data["categories"].update(new_cats)
                if save_ids(data):
                    st.success(f"✅ تم حفظ {len(new_cats)} تصنيف")
                    st.rerun()
            except Exception as e:
                st.error(f"خطأ في JSON: {e}")
    
    # عرض المحفوظة
    st.subheader("📋 التصنيفات المحفوظة")
    if saved_cats:
        cols = st.columns(3)
        for i, (name, id_) in enumerate(sorted(saved_cats.items())):
            with cols[i % 3]:
                col_n, col_d = st.columns([3, 1])
                with col_n:
                    st.markdown(f"**{name}**  \n`ID: {id_}`")
                with col_d:
                    if st.button("🗑️", key=f"del_cat_{i}", help="حذف"):
                        del data["categories"][name]
                        save_ids(data)
                        st.rerun()
    else:
        st.info("لا توجد تصنيفات محفوظة بعد")
    
    # التصنيفات بدون ID
    missing_cats = [c for c in categories_list if c not in saved_cats]
    if missing_cats:
        with st.expander(f"⚠️ تصنيفات بدون ID ({len(missing_cats)})", expanded=False):
            for c in missing_cats:
                st.markdown(f"- {c}")

# ══════════════════════════════════════════
# تبويب الماركات
# ══════════════════════════════════════════
with tab2:
    st.subheader("🏷️ IDs الماركات")
    st.info("💡 احصل على ID الماركة من سلة: المنتجات → الماركات → اضغط على الماركة → انظر الرقم في الرابط")
    
    brands_list = load_mahwous_brands_list()
    saved_brands = data.get("brands", {})
    
    # بحث سريع
    search_brand = st.text_input("🔍 بحث عن ماركة", placeholder="اكتب اسم الماركة...", key="search_brand")
    filtered_brands = [b for b in brands_list if search_brand.lower() in b.lower()] if search_brand else brands_list
    
    # إضافة ماركة
    with st.expander("➕ إضافة/تعديل ID ماركة", expanded=True):
        col_a, col_b, col_c = st.columns([3, 2, 1])
        with col_a:
            selected_brand = st.selectbox(
                "اختر الماركة",
                options=filtered_brands,
                key="new_brand_name"
            )
        with col_b:
            brand_id_input = st.text_input(
                "ID الماركة من سلة",
                value=saved_brands.get(selected_brand, "") if selected_brand else "",
                placeholder="مثال: 9876543210",
                key="new_brand_id"
            )
        with col_c:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("💾 حفظ", key="save_brand", use_container_width=True):
                if selected_brand and brand_id_input.strip():
                    data["brands"][selected_brand] = brand_id_input.strip()
                    if save_ids(data):
                        st.success(f"✅ تم حفظ: {selected_brand} → {brand_id_input.strip()}")
                        st.rerun()
                else:
                    st.error("أدخل ID الماركة")
    
    # إدخال جماعي
    with st.expander("📥 إدخال جماعي (JSON)", expanded=False):
        st.markdown("الصق JSON بالشكل: `{\"اسم الماركة\": \"ID\", ...}`")
        bulk_brands = st.text_area("JSON الماركات", height=200, key="bulk_brands_json",
                                    placeholder='{"شانيل": "111222333", "ديور": "444555666"}')
        if st.button("💾 حفظ الكل", key="save_bulk_brands"):
            try:
                import json
                new_brands = json.loads(bulk_brands)
                data["brands"].update(new_brands)
                if save_ids(data):
                    st.success(f"✅ تم حفظ {len(new_brands)} ماركة")
                    st.rerun()
            except Exception as e:
                st.error(f"خطأ في JSON: {e}")
    
    # عرض المحفوظة
    st.subheader("📋 الماركات المحفوظة")
    if saved_brands:
        cols = st.columns(3)
        for i, (name, id_) in enumerate(sorted(saved_brands.items())):
            with cols[i % 3]:
                col_n, col_d = st.columns([3, 1])
                with col_n:
                    st.markdown(f"**{name}**  \n`ID: {id_}`")
                with col_d:
                    if st.button("🗑️", key=f"del_brand_{i}", help="حذف"):
                        del data["brands"][name]
                        save_ids(data)
                        st.rerun()
    else:
        st.info("لا توجد ماركات محفوظة بعد")

# ══════════════════════════════════════════
# تبويب التعليمات
# ══════════════════════════════════════════
with tab3:
    st.subheader("📋 كيفية الحصول على IDs من سلة")
    
    st.markdown("""
    ### 📂 ID التصنيف
    1. افتح لوحة تحكم سلة: **المنتجات** → **التصنيفات**
    2. اضغط على أي تصنيف لتعديله
    3. انظر إلى رابط الصفحة: `https://s.salla.sa/categories/**1234567890**/edit`
    4. الرقم في الرابط هو **ID التصنيف**
    
    ---
    
    ### 🏷️ ID الماركة
    1. افتح لوحة تحكم سلة: **المنتجات** → **الماركات**
    2. اضغط على أي ماركة لتعديلها
    3. انظر إلى رابط الصفحة: `https://s.salla.sa/brands/**9876543210**/edit`
    4. الرقم في الرابط هو **ID الماركة**
    
    ---
    
    ### 💡 نصيحة للإدخال السريع
    يمكنك استخدام **الإدخال الجماعي (JSON)** لإدخال جميع IDs مرة واحدة:
    ```json
    {
      "العطور": "1234567890",
      "عطور نسائية": "2345678901",
      "عطور رجالية": "3456789012"
    }
    ```
    
    ---
    
    ### 🔄 كيف يعمل النظام
    - عند إرسال منتج، يبحث التطبيق تلقائياً عن ID التصنيف والماركة
    - إذا وُجد ID → يُرسله لـ Make → يُضيفه سلة للمنتج ✅
    - إذا لم يوجد ID → يُرسل المنتج بدون تصنيف/ماركة (يمكن إضافتهما يدوياً لاحقاً)
    """)

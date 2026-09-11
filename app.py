import streamlit as st
import pandas as pd
import numpy as np
import time

# ==========================================
# 1. การตั้งค่าหน้าจอหลัก (Page Config)
# ==========================================
st.set_page_config(
    page_title="Loan Prediction Challenger",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# 2. ฟังก์ชันจำลองการทำนาย (ให้เพื่อนแต่ละคนมาแก้ตรงนี้)
# ==========================================
# แนะนำให้โหลดโมเดล (.pkl) ไว้ส่วนบนสุดของไฟล์ด้วย joblib หรือ pickle
def predict_naive_bayes(data):
    # TODO: คนที่ 1 ใส่ Logic นำ Data เข้า Model ตัวเอง
    return {"status": "Approve", "confidence": 0.85}

def predict_fuzzy(data):
    # TODO: คนที่ 2 ใส่ Logic นำ Data เข้า Fuzzy Rules
    return {"status": "Reject", "confidence": 0.60}

def predict_adaboost(data):
    # TODO: คนที่ 3 ใส่ Logic นำ Data เข้า Model ตัวเอง
    return {"status": "Approve", "confidence": 0.92}

def predict_catboost(data):
    # TODO: คนที่ 4 ใส่ Logic นำ Data เข้า Model ตัวเอง
    return {"status": "Approve", "confidence": 0.88}

# ==========================================
# 3. การสร้างหน้า UI แต่ละหน้า
# ==========================================

def page_the_arena():
    st.title("⚔️ The Arena: ท้าชนโมเดล (Single Prediction)")
    st.markdown("ทดสอบกรอกข้อมูลลูกค้า 1 ราย เพื่อดูว่าแต่ละโมเดลจะตัดสินใจอย่างไร")
    
    # แบ่งหน้าจอเป็น 2 ฝั่ง: ซ้าย=ฟอร์มกรอกข้อมูล, ขวา=ผลลัพธ์
    col_form, col_results = st.columns([1, 2])
    
    with col_form:
        st.subheader("📝 ข้อมูลผู้ขอสินเชื่อ")
        with st.form("loan_form"):
            age = st.slider("อายุ (ปี)", 18, 70, 30)
            income = st.number_input("รายได้ต่อปี ($)", min_value=0, value=50000, step=1000)
            loan_amount = st.number_input("วงเงินกู้ที่ต้องการ ($)", min_value=0, value=15000, step=500)
            credit_score = st.slider("คะแนนเครดิต (Credit Score)", 300, 850, 650)
            # เพิ่มตัวแปรอื่นๆ ตาม Dataset ของ Kaggle ที่นี่
            
            submitted = st.form_submit_button("🚀 Predict Now")
            
    with col_results:
        st.subheader("📊 ผลการวิเคราะห์จาก 4 โมเดล")
        if submitted:
            # รวบรวมข้อมูลจากฟอร์ม
            input_data = {
                "age": age, "income": income, 
                "loan_amount": loan_amount, "credit_score": credit_score
            }
            
            with st.spinner('กำลังประมวลผลผ่านโมเดลทั้ง 4...'):
                time.sleep(1) # จำลองเวลาโหลด
                
                # เรียกใช้ฟังก์ชันทำนาย
                res_nb = predict_naive_bayes(input_data)
                res_fz = predict_fuzzy(input_data)
                res_ada = predict_adaboost(input_data)
                res_cat = predict_catboost(input_data)
                
                # แสดงผลแบบการ์ดเรียงกัน 4 ใบ
                c1, c2, c3, c4 = st.columns(4)
                
                def render_metric(col, model_name, result):
                    color = "normal" if result["status"] == "Approve" else "inverse"
                    col.metric(
                        label=model_name, 
                        value=result["status"], 
                        delta=f"Conf: {result['confidence']*100:.1f}%",
                        delta_color=color
                    )
                
                render_metric(c1, "Naive Bayes", res_nb)
                render_metric(c2, "Fuzzy Logic", res_fz)
                render_metric(c3, "AdaBoost", res_ada)
                render_metric(c4, "CatBoost", res_cat)
                
                # พื้นที่สำหรับ Hybrid Model
                st.divider()
                st.success("🤖 **Hybrid Ensemble Prediction:** Approve (Confidence: 89%)")
                st.caption("*หมายเหตุ: นี่คือผลลัพธ์จำลองจากการทำ Majority Vote หรือ Stacking*")
        else:
            st.info("👈 กรุณากรอกข้อมูลและกดปุ่ม Predict เพื่อดูผลลัพธ์")


def page_batch_processing():
    st.title("📂 Batch Processing")
    st.markdown("อัปโหลดไฟล์ข้อมูลลูกค้าจำนวนมาก (CSV) เพื่อให้ระบบทำนายผลและจัดระดับความเสี่ยงอัตโนมัติ")
    
    uploaded_file = st.file_uploader("อัปโหลดไฟล์ข้อมูล (รองรับ .csv)", type=['csv'])
    
    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
        st.write("ตัวอย่างข้อมูลที่อัปโหลด:")
        st.dataframe(df.head())
        
        if st.button("ประมวลผลไฟล์นี้"):
            with st.spinner("กำลังรัน Pipeline..."):
                time.sleep(2)
                # จำลองการเพิ่มคอลัมน์ผลลัพธ์
                df['Pred_NaiveBayes'] = np.random.choice(['Approve', 'Reject'], len(df))
                df['Pred_CatBoost'] = np.random.choice(['Approve', 'Reject'], len(df))
                
                st.success("ประมวลผลเสร็จสิ้น! พบเคสที่โมเดลตัดสินใจไม่ตรงกัน 15 เคส")
                st.dataframe(df.head(10))
                
                # ปุ่มดาวน์โหลดผลลัพธ์
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 ดาวน์โหลดผลลัพธ์ (CSV)", csv, "predicted_results.csv", "text/csv")


def page_dashboard():
    st.title("🏆 Model Leaderboard & Dashboard")
    st.markdown("เปรียบเทียบประสิทธิภาพของแต่ละโมเดล (ประเมินจาก Test Set ข้อมูลจาก Kaggle)")
    
    # สร้างตารางจำลอง Metrics
    metrics_df = pd.DataFrame({
        "Model": ["CatBoost", "AdaBoost", "Naive Bayes", "Fuzzy Logic"],
        "Accuracy (%)": [92.5, 90.1, 85.4, 82.0],
        "Precision (%)": [93.0, 91.5, 84.0, 80.5],
        "Recall (%)": [91.2, 88.0, 87.5, 83.0],
        "F1-Score (%)": [92.1, 89.7, 85.7, 81.7],
        "Inference Time (ms)": [45, 32, 12, 150]
    })
    
    st.dataframe(metrics_df, use_container_width=True)
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Feature Importance (จาก CatBoost)")
        # สร้างกราฟแท่งแบบง่ายๆ ด้วย Streamlit bar_chart
        feat_imp = pd.DataFrame({
            "Score": [0.35, 0.25, 0.15, 0.10, 0.08]
        }, index=["Credit Score", "Income", "Loan Amount", "Age", "Employment Length"])
        st.bar_chart(feat_imp)
        
    with col2:
        st.subheader("สัดส่วน Approve / Reject")
        pie_data = pd.DataFrame({"Count": [700, 300]}, index=["Approve", "Reject"])
        st.bar_chart(pie_data) # ใช้ bar_chart แทน Pie chart ชั่วคราวเพื่อให้ไม่ต้องลง library เพิ่ม

# ==========================================
# 4. ระบบ นำทาง (Sidebar Navigation)
# ==========================================
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "เลือกหน้าต่างการทำงาน:",
    ["⚔️ The Arena", "📂 Batch Processing", "🏆 Dashboard"]
)

st.sidebar.divider()
st.sidebar.markdown("**ทีมพัฒนา:**\n- คนที่ 1 (Naive Bayes)\n- คนที่ 2 (Fuzzy)\n- คนที่ 3 (AdaBoost)\n- คนที่ 4 (CatBoost)")

# Render หน้าตามที่เลือก
if page == "⚔️ The Arena":
    page_the_arena()
elif page == "📂 Batch Processing":
    page_batch_processing()
elif page == "🏆 Dashboard":
    page_dashboard()
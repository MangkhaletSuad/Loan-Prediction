import streamlit as st
import pandas as pd
import numpy as np
import time

# ==========================================
# 1. การตั้งค่าหน้าจอหลัก
# ==========================================
st.set_page_config(page_title="Loan Prediction Challenger", page_icon="🏦", layout="wide")

# ==========================================
# 2. ฟังก์ชันจำลองการทำนาย (โหลดโมเดลจริงที่เป็น .joblib ตรงนี้)
# ==========================================
def predict_logistic_regression(data):
    return {"status": "Approve", "confidence": 0.82}

def predict_naive_bayes(data):
    return {"status": "Reject", "confidence": 0.65}

def predict_adaboost(data):
    return {"status": "Approve", "confidence": 0.91}

# ==========================================
# 3. สร้างหน้า UI 
# ==========================================

def page_the_arena():
    st.title("⚔️ The Arena: ท้าชน 3 โมเดล")
    st.markdown("ทดสอบกรอกข้อมูลลูกค้าเพื่อเปรียบเทียบคำตัดสินของ Logistic Regression, Naive Bayes และ AdaBoost")
    
    col_form, col_results = st.columns([1, 2])
    
    with col_form:
        st.subheader("📝 ข้อมูลผู้ขอสินเชื่อ")
        with st.form("loan_form"):
            # TODO: ปรับฟิลด์ให้ตรงกับ Feature ที่ชนะจากการทำ Greedy Search
            income = st.number_input("Annual Income ($)", value=50000)
            loan_amount = st.number_input("Loan Amount ($)", value=15000)
            dti = st.slider("Debt-to-Income Ratio", 0.0, 50.0, 15.0)
            credit_score = st.slider("Credit Score", 300, 850, 650)
            
            submitted = st.form_submit_button("🚀 Predict Now")
            
    with col_results:
        st.subheader("📊 ผลการวิเคราะห์ (Challenger)")
        if submitted:
            input_data = {"income": income, "loan_amount": loan_amount, "dti": dti, "credit_score": credit_score}
            
            with st.spinner('กำลังประมวลผล...'):
                time.sleep(1)
                res_lr = predict_logistic_regression(input_data)
                res_nb = predict_naive_bayes(input_data)
                res_ada = predict_adaboost(input_data)
                
                c1, c2, c3 = st.columns(3)
                
                def render_metric(col, model_name, result):
                    color = "normal" if result["status"] == "Approve" else "inverse"
                    col.metric(label=model_name, value=result["status"], 
                               delta=f"Conf: {result['confidence']*100:.1f}%", delta_color=color)
                
                render_metric(c1, "Logistic Regression", res_lr)
                render_metric(c2, "Naive Bayes", res_nb)
                render_metric(c3, "AdaBoost", res_ada)

def page_greedy_experiment():
    st.title("📉 Greedy Search: Feature Selection Experiment")
    st.markdown("แสดงผลการทดลองลดจำนวน Feature ลง 5 รอบ จนเหลือเพียง 1 Feature เพื่อดูว่า Model ไหนทนทานต่อการสูญเสียข้อมูลได้ดีที่สุด")
    
    # จำลองผลลัพธ์ F1-Score ในแต่ละรอบ (สมมติว่าเริ่มจาก 5 features แล้วคัดออกทีละ 1)
    experiment_data = pd.DataFrame({
        "Round": ["Round 1 (5 Features)", "Round 2 (4 Features)", "Round 3 (3 Features)", 
                  "Round 4 (2 Features)", "Round 5 (1 Feature)"],
        "Logistic Regression": [0.85, 0.84, 0.82, 0.75, 0.60],
        "Naive Bayes": [0.82, 0.83, 0.81, 0.72, 0.58], # NB อาจจะดีขึ้นนิดนึงตอนตัด Noise ออก
        "AdaBoost": [0.90, 0.89, 0.88, 0.82, 0.65]
    })
    
    st.subheader("F1-Score Comparison per Round")
    st.line_chart(experiment_data.set_index("Round"))
    
    st.subheader("ตารางสรุปผล Precision & F1-Score")
    st.dataframe(experiment_data, use_container_width=True)
    
    st.info("💡 **ข้อค้นพบ (Insight):** [รอใส่ข้อสรุป เช่น AdaBoost สามารถรักษา F1-Score ได้ดีที่สุดแม้เหลือเพียง 3 Features...]")

# ==========================================
# 4. ระบบนำทาง (Sidebar Navigation)
# ==========================================
st.sidebar.title("Navigation")
page = st.sidebar.radio("เลือกหน้าต่างการทำงาน:", ["⚔️ The Arena", "📉 Greedy Search Results"])

st.sidebar.divider()
st.sidebar.markdown("**Models in Challenger:**\n1. Logistic Regression\n2. Naive Bayes\n3. AdaBoost")
st.sidebar.markdown("**Feature Selection:**\nGreedy Backward (5 Rounds)")

if page == "⚔️ The Arena":
    page_the_arena()
elif page == "📉 Greedy Search Results":
    page_greedy_experiment()
# 🏦 Loan Prediction Challenger App

โปรเจกต์นี้คือ Web Application ที่สร้างด้วย Streamlit สำหรับเปรียบเทียบประสิทธิภาพของโมเดล Machine Learning 4 รูปแบบ (Naive Bayes, Fuzzy Logic, AdaBoost, CatBoost) ในการพิจารณาอนุมัติสินเชื่อ (Loan Prediction)

---

## 🛠️ ขั้นตอนการติดตั้ง (Setup & Installation)

เพื่อให้สภาพแวดล้อมการทำงานของทุกคนตรงกันและไม่กระทบกับโปรเจกต์อื่นในเครื่อง กรุณาทำตามขั้นตอนการสร้าง Virtual Environment ดังนี้:

### 1. สร้าง Virtual Environment
เปิด Terminal หรือ Command Prompt ในโฟลเดอร์โปรเจกต์นี้ แล้วรันคำสั่ง:
```bash
python -m venv .venv

### 2. เปิดใช้งาน (Activate) Virtual Environment
สำหรับ Windows:
```bash
.venv\Scripts\activate

สำหรับ macOS / Linux:
```bash
source .venv/bin/activate

### 3. ติดตั้ง Dependencies
ติดตั้ง Library ทั้งหมดที่ระบุไว้ในไฟล์ requirements.txt:

### วิธีการรันแอปพลิเคชัน
เมื่อติดตั้งเสร็จเรียบร้อยแล้ว สามารถเปิดใช้งานแอปได้โดยรันคำสั่ง:
streamlit run app.py
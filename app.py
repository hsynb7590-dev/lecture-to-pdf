import streamlit as st
import os
import io
from groq import Groq
from fpdf import FPDF
import arabic_reshaper
from bidi.algorithm import get_display

# 1. إعدادات الصفحة
st.set_page_config(page_title="مساعد الصيدلة الذكي Pro", page_icon="💊", layout="wide")
st.title("🎙️ منصة التفريغ الرباعية (4 API Keys)")
st.markdown("---")

# --- خاصية العداد في الشريط الجانبي ---
if 'used_seconds' not in st.session_state:
    st.session_state.used_seconds = 0

total_limit_seconds = 7200 * 4 # ساعتان لكل مفتاح = 8 ساعات إجمالية
remaining_seconds = max(0, total_limit_seconds - st.session_state.used_seconds)

st.sidebar.header("📊 مراقب الاستهلاك الرباعي")
progress = min(st.session_state.used_seconds / total_limit_seconds, 1.0)
st.sidebar.progress(progress)
st.sidebar.write(f"⏱️ المستهلك: {st.session_state.used_seconds / 3600:.2f} / 8 ساعات")
st.sidebar.write(f"🔓 المتبقي: {remaining_seconds / 3600:.2f} ساعة")
st.sidebar.info("💡 الحدود تتصفر تلقائياً كل ساعة من قبل Groq.")

# 2. جلب 4 مفاتيح API من الأسرار (Secrets)
api_keys = [
    st.secrets.get("groq_api_key_1"),
    st.secrets.get("groq_api_key_2"),
    st.secrets.get("groq_api_key_3"),
    st.secrets.get("groq_api_key_4")
]
api_keys = [k for k in api_keys if k]

if not api_keys:
    st.error("⚠️ لم يتم العثور على مفاتيح API. تأكد من إضافة المفاتيح من 1 إلى 4 في Secrets.")
    st.stop()

# 3. رفع الملف ومعالجته
uploaded_file = st.file_uploader("ارفع ملف المحاضرة (أقل من 25MB)", type=["mp3", "wav", "m4a"])

if uploaded_file:
    file_bytes = uploaded_file.read()
    
    if st.button("🚀 بدء المعالجة الاحترافية"):
        raw_text = ""
        success_client = None
        
        # نظام التبديل التلقائي بين الـ 4 حسابات
        for i, key in enumerate(api_keys):
            try:
                client = Groq(api_key=key)
                with st.spinner(f"جاري المحاولة باستخدام الحساب رقم ({i+1})..."):
                    transcription = client.audio.transcriptions.create(
                        model="whisper-large-v3",
                        file=(uploaded_file.name, io.BytesIO(file_bytes)),
                        language="ar",
                        prompt="Keep Egyptian slang. Write medical terms in English: Pharmacology, Mechanism of action, Dosage."
                    )
                    raw_text = transcription.text
                    success_client = client
                    
                    # تحديث العداد (افتراض ساعة لكل عملية)
                    st.session_state.used_seconds += 3600 
                    break 
            except Exception as e:
                if "rate_limit_exceeded" in str(e):
                    st.warning(f"⚠️ الحساب رقم ({i+1}) وصل للحد الأقصى، جاري التبديل...")
                    continue
                else:
                    st.error(f"❌ حدث خطأ: {e}")
                    st.stop()
        
        if not raw_text:
            st.error("❌ جميع الحسابات الأربعة وصلت للحد الأقصى. يرجى الانتظار قليلاً.")
            st.stop()

        # المرحلة الثانية: التنسيق والتلخيص الطبي (Llama 3.3 70B)
        try:
            with st.spinner("جاري التنسيق الطبي وتصحيح المصطلحات..."):
                med_prompt = f"""
                أنت صيدلي خبير. النص التالي تفريغ لمحاضرة مصرية.
                المطلوب:
                1- حافظ على اللهجة العامية كما هي.
                2- أي مصطلح طبي أو اسم دواء اكتبه بالإنجليزية (English) وبإملاء صحيح.
                3- نسق المحتوى في نقاط واضحة (الخلاصة الطبية).
                
                النص: {raw_text[:15000]}
                """
                completion = success_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": med_prompt}]
                )
                refined_output = completion.choices[0].message.content

            st.success("✅ تمت المعالجة بنجاح!")

            tab1, tab2 = st.tabs(["📝 الملخص والمنقح", "📄 النص كما قيل"])
            with tab1: st.markdown(refined_output)
            with tab2: st.write(raw_text)

            # 5. توليد ملف PDF
            def create_pdf(text_content):
                pdf = FPDF()
                pdf.add_page()
                font_path = "Amiri-Regular.ttf"
                if os.path.exists(font_path):
                    pdf.add_font("Amiri", "", font_path)
                    pdf.set_font("Amiri", size=12)
                else:
                    pdf.set_font("Arial", size=12)
                
                reshaped = arabic_reshaper.reshape(text_content)
                bidi_text = get_display(reshaped)
                pdf.multi_cell(0, 10, bidi_text, align='R')
                pdf_out = "Pharmacy_Summary.pdf"
                pdf.output(pdf_out)
                return pdf_out

            pdf_file = create_pdf(refined_output)
            with open(pdf_file, "rb") as f:
                st.download_button("📥 تحميل الملخص PDF", f, file_name="Pharmacy_Lecture.pdf")

        except Exception as e:
            st.error(f"حدث خطأ في التنسيق: {e}")

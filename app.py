import streamlit as st
import os
import io
from groq import Groq
from PyPDF2 import PdfReader
from fpdf import FPDF
import arabic_reshaper
from bidi.algorithm import get_display

# 1. إعدادات الصفحة
st.set_page_config(page_title="مساعد الصيدلة الذكي Pro", page_icon="💊", layout="wide")
st.title("🎙️+📄 الربط الذكي بين الصوت وملف المحاضرة")

# --- عداد الاستهلاك الموحد ---
if 'used_seconds' not in st.session_state:
    st.session_state.used_seconds = 0

total_limit_seconds = 7200 * 4 # 8 ساعات إجمالية
remaining_seconds = max(0, total_limit_seconds - st.session_state.used_seconds)

st.sidebar.header("📊 رصيد الموقع المتبقي")
st.sidebar.progress(min(st.session_state.used_seconds / total_limit_seconds, 1.0))
st.sidebar.write(f"🔓 المتبقي: {remaining_seconds / 3600:.2f} ساعة")

# 2. جلب مفاتيح API الأربعة
api_keys = [st.secrets.get(f"groq_api_key_{i}") for i in range(1, 5)]
api_keys = [k for k in api_keys if k]

# 3. واجهة الرفع المزدوجة
col1, col2 = st.columns(2)
with col1:
    audio_file = st.file_uploader("🎙️ ارفع تسجيل المحاضرة", type=["mp3", "wav", "m4a"])
with col2:
    pdf_file = st.file_uploader("📄 ارفع ملف المحاضرة المكتوب (PDF)", type=["pdf"])

if audio_file and pdf_file:
    if st.button("🚀 بدء التحليل المرجعي"):
        # أ. استخراج النص من الـ PDF ليكون مرجعاً
        try:
            pdf_reader = PdfReader(pdf_file)
            pdf_context = ""
            for page in pdf_reader.pages:
                pdf_context += page.extract_text()
        except Exception as e:
            st.error(f"خطأ في قراءة ملف PDF: {e}")
            st.stop()
            
        # ب. تفريغ الصوت (Whisper) باستخدام نظام التبديل
        raw_audio_text = ""
        audio_bytes = audio_file.read()
        success_client = None
        
        for i, key in enumerate(api_keys):
            try:
                client = Groq(api_key=key)
                with st.spinner(f"جاري تحويل الصوت (حساب {i+1})..."):
                    transcription = client.audio.transcriptions.create(
                        model="whisper-large-v3",
                        file=(audio_file.name, io.BytesIO(audio_bytes)),
                        language="ar",
                        prompt=f"Medical terms from PDF: {pdf_context[:500]}" 
                    )
                    raw_audio_text = transcription.text
                    success_client = client
                    st.session_state.used_seconds += 3600
                    break
            except Exception as e:
                if "rate_limit_exceeded" in str(e): continue
                else: st.error(f"❌ خطأ تقني: {e}"); st.stop()

        # ج. الربط الذكي وتوليد النص الكامل المصحح
        if raw_audio_text and success_client:
            try:
                with st.spinner("جاري مطابقة المسموع بالمكتوب وتنسيق المحاضرة..."):
                    # نطلب منه هنا تحويل النص كاملاً مع التصحيح
                    final_prompt = f"""
                    أنت مساعد صيدلي محترف. لديك نصين لنفس المحاضرة.
                    النص الأول (مرجع دقيق من PDF): {pdf_context[:5000]}
                    النص الثاني (تفريغ صوتي قد يحتوي أخطاء): {raw_audio_text}
                    
                    المطلوب منك:
                    1. أعد صياغة النص الصوتي بالكامل ليصبح منظماً ومفهوماً.
                    2. استخدم المصطلحات الطبية الصحيحة بالإنجليزية كما وردت في الـ PDF.
                    3. حافظ على شرح الدكتور بالعامية المصرية في الأجزاء التوضيحية.
                    4. ركز على "الزيادات" التي قالها الدكتور ولم تكن مكتوبة في الـ PDF.
                    5. استخرج "الزتونة" في نهاية النص (أهم نقاط ركز عليها الدكتور).
                    """
                    completion = success_client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role": "user", "content": final_prompt}]
                    )
                    final_output = completion.choices[0].message.content

                st.success("✅ تم الانتهاء من التحويل والربط!")
                
                # عرض النتائج في تبويبات
                tab1, tab2 = st.tabs(["📝 المحاضرة المصححة (الكاملة)", "📄 التفريغ الخام"])
                with tab1:
                    st.markdown(final_output)
                with tab2:
                    st.write(raw_audio_text)

                # 5. توليد ملف PDF للنتيجة النهائية
                def create_pdf(content):
                    pdf = FPDF()
                    pdf.add_page()
                    font_path = "Amiri-Regular.ttf"
                    if os.path.exists(font_path):
                        pdf.add_font("Amiri", "", font_path)
                        pdf.set_font("Amiri", size=12)
                    else:
                        pdf.set_font("Arial", size=12)
                    
                    reshaped = arabic_reshaper.reshape(content)
                    bidi_text = get_display(reshaped)
                    pdf.multi_cell(0, 10, bidi_text, align='R')
                    pdf_name = "Final_Lecture_Notes.pdf"
                    pdf.output(pdf_name)
                    return pdf_name

                pdf_result = create_pdf(final_output)
                with open(pdf_result, "rb") as f:
                    st.download_button("📥 تحميل المحاضرة منسقة PDF", f, file_name="Pharma_Notes.pdf")

            except Exception as e:
                st.error(f"خطأ في معالجة النص: {e}")

import streamlit as st
import tempfile
import os
from adaptive_rag import AdaptiveRAGSystem, DEFAULT_CONFIG

# ====================  Page Config ====================
st.set_page_config(
    page_title="Adaptive RAG",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.config.set_option('theme.primaryColor', '#1a73e8')

# ==================== Styles ====================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;500;700;800&display=swap');

    *:not(code):not(pre):not([class*="code"]) {
        font-family: 'Vazirmatn', sans-serif !important;
    }
    .main .block-container {
        direction: rtl !important;
        text-align: right !important;
    }
    code, pre, .stCodeBlock, [class*="code"] {
        direction: ltr !important;
        text-align: left !important;
        font-family: 'Courier New', monospace !important;
    }
    .stTextInput input, .stTextArea textarea, input[type="text"], input[type="password"] {
        direction: rtl !important;
        text-align: right !important;
    }
    section[data-testid="stSidebar"] {
        direction: ltr !important;
    }
    section[data-testid="stSidebar"] .block-container {
        direction: ltr !important;
        text-align: left !important;
    }
    section[data-testid="stSidebar"] * {
        text-align: left !important;
    }
    section[data-testid="stSidebar"] .stButton > button {
        text-align: right !important;
    }

    section[data-testid="stSidebar"] label {
    font-weight: 800 !important;
    color: #202124 !important;
    }
            
    section[data-testid="stSidebar"] .stFileUploader,
    section[data-testid="stSidebar"] .stFileUploader * {
        direction: rtl !important;
        text-align: right !important;
    }

    section[data-testid="stSidebar"] .stButton,
    section[data-testid="stSidebar"] .stButton * {
        direction: rtl !important;
        text-align: right !important;
    }
    section[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
    section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] * {
        direction: rtl !important;
        text-align: right !important;
    }            
    :root {
        --primary-blue: #1a73e8;
    }
    .stButton > button {
        background-color: #1a73e8 !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-family: 'Vazirmatn', sans-serif !important;
        font-weight: 500 !important;
    }
    .stButton > button:hover {
        background-color: #1557b0 !important;
    }
    button[kind="primary"] {
        background-color: #1a73e8 !important;
        border-color: #1a73e8 !important;
    }
    input:focus, textarea:focus, .stTextInput input:focus {
        border-color: #1a73e8 !important;
        box-shadow: 0 0 0 2px rgba(26, 115, 232, 0.2) !important;
    }
    .stSpinner > div {
        border-top-color: #1a73e8 !important;
    }

    h1, h2, h3 {
        color: #1a73e8 !important;
        text-align: right !important;
    }

    .info-cards { display: flex; gap: 1.5rem; margin-top: 2.5rem; flex-wrap: wrap; }
    .info-card {
        flex: 1; background: #f0f4f9; border-radius: 12px; padding: 1.2rem;
        box-shadow: 0 2px 8px rgba(26, 115, 232, 0.08);
        border-right: 4px solid #1a73e8; text-align: right !important;
    }
    .info-card h4 { color: #1a73e8; text-align: right !important; }
    .info-card p, .info-card li { color: #3c4043; font-size: 0.85rem; }

    /* ========== footer  ========== */
    .footer {
        margin: 2rem auto 0 auto;
        width: 90%;
        padding: 1rem;
        border-top: 1px solid #dadce0;
        color: #5f6368;
        font-size: 0.8rem;
        text-align: center !important;
    }

    div[data-testid="stExpander"] details { border: 1px solid #dadce0; border-radius: 8px; }
    div[data-testid="stExpander"] summary {
        text-align: right !important; direction: rtl !important;
        color: #1a73e8 !important; font-weight: 500;
    }
    div[data-testid="stExpander"] div { text-align: right !important; }

    details > summary { list-style: none; }
    details > summary::-webkit-details-marker { display: none; }
    details > summary::marker { display: none; content: ""; }
    details > summary::before {
        content: "▼ "; color: #1a73e8; font-weight: bold;
        float: right; margin-left: 8px; font-size: 0.9rem;
    }
    details[open] > summary::before { content: "▲ "; }
            
    /* =====    Q & A Section ===== */
    .rtl-section {
        direction: rtl;
        text-align: right;
    }
    /* فیلد ورودی متن داخل آن راست‌چین شود */
    .rtl-section .stTextInput > div > div > input {
        direction: rtl;
        text-align: right;
    }
    /* هر بلاک Markdown که داخل این بخش رندر می‌شود راست‌چین شود */
    .rtl-section .stMarkdown {
        text-align: right;
    }

    /* ========== borders  ========== */
    div[data-testid="stInfo"],
    div[data-testid="stSuccess"],
    div[data-testid="stWarning"],
    div[data-testid="stError"] {
        direction: rtl !important;
        text-align: right !important;
        border-radius: 8px !important;
    }
    div[data-testid="stInfo"] *,
    div[data-testid="stSuccess"] *,
    div[data-testid="stWarning"] *,
    div[data-testid="stError"] * {
        direction: rtl !important;
        text-align: right !important;
    }
    div[data-testid="stInfo"] {
        background-color: #e8f0fe !important;
        border-left: 4px solid #1a73e8 !important;
    }
    div[data-testid="stSuccess"] {
        background-color: #e6f4ea !important;
        border-left: 4px solid #1a73e8 !important;
    }
    div[data-testid="stAlert"],
    div[data-testid="stAlert"] * {
        direction: rtl !important;
        text-align: right !important;
    }

    div[data-testid="stSpinner"],
    div[data-testid="stSpinner"] * {
        direction: rtl !important;
        text-align: right !important;
    }
    /* ========== Header  ========== */
    .main-header {
        margin: 0 auto;
        width: fit-content;
        padding: 1.5rem 0 1rem 0;
        direction: center;
    }
    .main-header h1 {
        font-size: 2.2rem; font-weight: 800;
        background: linear-gradient(135deg, #1a73e8, #0d47a1);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        text-align: center !important;
    }
    .main-header p { color: #5f6368; text-align: center !important; }
            

</style>
""", unsafe_allow_html=True)

# ==================== Header ====================
st.markdown('<div class="main-header"><h1>Adaptive RAG</h1><p>پرسش و پاسخ هوشمند با استراتژی تطبیقی</p></div>', unsafe_allow_html=True)

# ==================== Sidebar ====================
with st.sidebar:
    st.header("⚙️ Settings")
    api_key = st.text_input(" API Key", type="password", key="api_key_input")
    st.caption("پس از وارد کردن کلید، تنظیمات پیشرفته در دسترس خواهد بود.")

    with st.expander("⚙️ Advance Settings ", expanded=bool(api_key)):
        base_url = st.text_input(" Base URL", value=DEFAULT_CONFIG['gapgpt_base_url'])
        model_name = st.text_input(" Model Name", value=DEFAULT_CONFIG['gapgpt_model'])
        temperature = st.slider(" Temperature", 0.0, 1.0, DEFAULT_CONFIG['temperature'])
        max_tokens = st.number_input(" Max Tokens", 100, 4000, DEFAULT_CONFIG['max_tokens'], step=100)
        chunk_size = st.slider(" Chunk Size", 200, 2000, DEFAULT_CONFIG['chunk_size'], step=50)
        chunk_overlap = st.slider(" Chunk Overlap", 0, 500, DEFAULT_CONFIG['chunk_overlap'], step=10)
        embedding_model = st.text_input(" Embedding Model", value=DEFAULT_CONFIG['embedding_model'])
        similarity_top_k = st.number_input(" Top K", 1, 20, DEFAULT_CONFIG['similarity_top_k'], step=1)
        collection_name = st.text_input(" Collection Name", value=DEFAULT_CONFIG['collection_name'])
        persist_dir = st.text_input(" Persist Directory", value=DEFAULT_CONFIG['persist_directory'])

    st.divider()
    st.header("📂 File Uploader")
    uploaded_files = st.file_uploader("فایل‌های PDF خود را بارگذاری کنید.", type=['pdf'], accept_multiple_files=True)
    process_btn = st.button("پردازش اسناد و ساخت Vector DB", type="primary", use_container_width=True)

    if 'system' in st.session_state:
        st.success("سیستم آماده است")
    else:
        st.info("⏳ اسناد را بارگذاری و پردازش کنید.")

    if process_btn:
        if not api_key:
            st.error("❌ لطفاً کلید API را وارد کنید")
        elif not uploaded_files:
            st.error("❌ حداقل یک فایل PDF بارگذاری کنید")
        else:
            with st.spinner("⏳ در حال پردازش..."):
                try:
                    temp_dir = tempfile.mkdtemp()
                    pdf_paths = []
                    for uf in uploaded_files:
                        path = os.path.join(temp_dir, uf.name)
                        with open(path, "wb") as f:
                            f.write(uf.getbuffer())
                        pdf_paths.append(path)

                    settings = {
                        'api_key': api_key, 'chunk_size': chunk_size,
                        'chunk_overlap': chunk_overlap, 'gapgpt_base_url': base_url,
                        'gapgpt_model': model_name, 'embedding_model': embedding_model,
                        'temperature': temperature, 'max_tokens': max_tokens,
                        'persist_directory': persist_dir, 'collection_name': collection_name,
                        'similarity_top_k': similarity_top_k,
                    }

                    system = AdaptiveRAGSystem(settings)
                    num_chunks = system.process_documents(pdf_paths)
                    st.session_state['system'] = system
                    st.session_state['ready'] = True
                    st.success(f"✅ پردازش کامل شد! {num_chunks} قطعه متن ایجاد شد.")
                    st.balloons()
                except Exception as e:
                    st.error(f"❌ خطا: {str(e)}")

# ==================== main section ====================
if 'system' in st.session_state and st.session_state.get('ready'):
    st.header(" پرسش و پاسخ")
    question = st.text_input("  ", placeholder="مثلاً: مدل‌های زبانی بزرگ چگونه کار می‌کنند؟")
    if question:
        with st.spinner("  در حال تحلیل..."):
            try:
                result = st.session_state.system.adaptive_query(question)

                st.markdown(f"""
                <div class="rtl-section" style="direction:rtl; text-align:right;">
                <h3>پاسخ</h3>
                <p>{result if isinstance(result, str) else result.get('answer', result)}</p>
                </div>
                """, unsafe_allow_html=True)


            except Exception as e:
                st.error(f"❌ خطا: {str(e)}")
else:
    st.markdown("""
    <div style="
        direction: rtl;
        text-align: right;
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: rgba(28, 131, 225, 0.1);
        border: 1px solid rgba(28, 131, 225, 0.2);
    ">
    <strong>👈 برای شروع:</strong><br>
    ۱. از نوار کناری یک کلید API معتبر خود را وارد کنید.<br>
    ۲. فایل‌های PDF خود را بارگذاری کنید.<br>
    ۳. روی دکمه «File Uploader» کلیک کنید.<br>
    ۴. سپس سوال خود را اینجا بپرسید.
    </div>
    """, unsafe_allow_html=True)

# ====================  explation borders ====================
st.markdown('<div class="info-cards">', unsafe_allow_html=True)
col1, col2 = st.columns(2)
with col1:
    st.markdown("""
<div class="info-card" style="direction: rtl; text-align: right;">
    <h4>📊 تحلیل هوشمند سوالات</h4>
    <p>سیستم به‌طور خودکار سوال شما را تحلیل کرده و بهترین استراتژی را انتخاب می‌کند:</p>
    <ul style="padding-right: 20px;">
        <li><strong>RAG ساده:</strong> برای سوالات کوتاه و ساده</li>
        <li><strong>RAG تجزیه‌شده:</strong> تجزیه سوالات پیچیده به زیرسوالات</li>
        <li><strong>HyDE:</strong> تولید پاسخ فرضی برای بازیابی بهتر</li>
    </ul>
</div>""", unsafe_allow_html=True)
with col2:
    st.markdown("""
    <div class="info-card" style="direction: rtl; text-align: right;">
    <h4>📖 راهنمای سریع</h4>
    <p>
        ۱. کلید API خود را در تنظیمات وارد کنید.<br>
        ۲. اسناد PDF را بارگذاری و پایگاه را بسازید.<br>
        ۳. سوال خود را به فارسی تایپ کرده و Enter بزنید.
    </p>
</div>""", unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ==================== Footer ====================
st.markdown("""
<div class="footer">
    ساخته شده توسط <strong>مهندس سارا افشار</strong><br>
    <span style="font-size:0.75rem;">Adaptive RAG System v2.0 | GapGPT + ChromaDB</span>
</div>
""", unsafe_allow_html=True)

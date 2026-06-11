import streamlit as st
import requests
import json

# 1. Konfigurasi Halaman Web
st.set_page_config(page_title="Enyx - Debugging AI", page_icon="⚙️", layout="centered")

st.title("⚙️ Enyx: Root Cause Analyzer")
st.write("Silakan paste error log, stack trace, atau potongan kode bermasalah di bawah ini.")

# 2. Mengambil API Key secara aman dari Secrets
api_key = st.secrets.get("GEMINI_API_KEY")

# 3. Form Input User
user_input = st.text_area("Log Input:", height=200, placeholder="Fatal error: Allowed memory size of...")

# 4. Tombol Eksekusi
if st.button("Analisis Error"):
    if not api_key:
        st.error("Error: GEMINI_API_KEY belum disetting di Streamlit Secrets!")
    elif not user_input:
        st.warning("Log tidak boleh kosong, mas!")
    else:
        with st.spinner("Enyx sedang mencari root cause..."):
            # Rancang prompt sistem
            system_prompt = """
            Kamu adalah Enyx, seorang Senior Software Engineer. Tugasmu menganalisis error log.
            Batasan:
            - No fluff, langsung ke inti masalah.
            - Output HANYA JSON murni dengan struktur: status, severity, root_cause, solution_steps (array), code_snippet.
            """
            full_prompt = f"{system_prompt}\n\nInput User:\n{user_input}"
            
            # Tembak langsung rute endpoint API Gemini 2.0 Flash via HTTP POST
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [{"parts": [{"text": full_prompt}]}],
                "generationConfig": {"responseMimeType": "application/json"}
            }
            
            try:
                # Eksekusi request jaringan
                response = requests.post(url, headers=headers, json=payload)
                response_data = response.json()
                
                # 🔍 PERBAIKAN DI SINI: Cek apakah ada error dari Google Cloud
                if 'error' in response_data:
                    st.error(f"❌ Google API Error ({response_data['error'].get('code')}): {response_data['error'].get('message')}")
                    st.stop() # Hentikan proses render UI bawah jika error
                
                # Ekstrak teks balasan jika sukses
                ai_text = response_data['candidates'][0]['content']['parts'][0]['text']
                ai_output = json.loads(ai_text)
                
                # 5. Render Output ke Komponen UI Streamlit
                st.success("Analisis Selesai!")
                
                col1, col2 = st.columns(2)
                col1.metric("Severity", ai_output.get('severity', 'N/A'))
                col2.metric("Status", ai_output.get('status', 'N/A'))
                
                st.subheader("🔍 Root Cause")
                st.info(ai_output.get('root_cause', ''))
                
                st.subheader("🛠️ Solution Steps")
                for step in ai_output.get('solution_steps', []):
                    st.write(f"- {step}")
                    
                st.subheader("💻 Code Snippet")
                st.code(ai_output.get('code_snippet', ''), language='php')
                
            except json.JSONDecodeError:
                st.error("Sistem gagal mem-parsing format respons JSON dari AI.")
            except Exception as e:
                st.error(f"Terjadi kegagalan koneksi API: {e}")
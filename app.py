import streamlit as st
import requests
import json
import time
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# 1. Konfigurasi Halaman Web
st.set_page_config(page_title="Enyx - Debugging AI", page_icon="⚙️", layout="centered")

st.title("⚙️ Enyx: Root Cause Analyzer (Groq Engine)")
st.write("Silakan paste error log, stack trace, atau potongan kode bermasalah di bawah ini.")

# 2. Mengambil API Key Groq dari Secrets
api_key = st.secrets.get("GROQ_API_KEY")

# --- RAG: Fungsi untuk load Knowledge Base ---
def load_knowledge_base():
    kb_path = "knowledge_base.txt"
    if os.path.exists(kb_path):
        with open(kb_path, "r", encoding="utf-8") as f:
            content = f.read()
            # Pisahkan per baris/aturan sebagai chunks
            chunks = [chunk.strip() for chunk in content.split("\n") if chunk.strip()]
            return chunks
    return []

kb_chunks = load_knowledge_base()

# --- RAG: Fungsi Retrieval dengan TF-IDF ---
def retrieve_context(query, chunks):
    if not chunks:
        return "", 0.0
    vectorizer = TfidfVectorizer()
    # Gabungkan query dengan chunks untuk membuat vektor
    tfidf_matrix = vectorizer.fit_transform([query] + chunks)
    # Hitung similarity antara query (index 0) dan semua chunks (index 1 dst)
    cosine_similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
    # Cari index dengan similarity tertinggi
    best_idx = cosine_similarities.argmax()
    best_score = cosine_similarities[best_idx]
    
    # Threshold kemiripan dinaikkan agar lebih akurat (tidak asal tebak kata umum)
    if best_score > 0.20:
        return chunks[best_idx], best_score
    return "", best_score

# 3. Form Input User
user_input = st.text_area("Log Input:", height=200, placeholder="Fatal error: Allowed memory size of...")

# 4. Tombol Eksekusi
if st.button("Analisis Error"):
    if not api_key:
        st.error("Error: GROQ_API_KEY belum disetting di Streamlit Secrets!")
    elif not user_input:
        st.warning("Log tidak boleh kosong, mas!")
    else:
        with st.status("Memproses Pipeline RAG...", expanded=True) as status:
            st.write("📥 Menganalisis Log Error User...")
            time.sleep(0.7)
            st.write("🧮 Mengekstrak keywords dan menghitung TF-IDF Cosine Similarity...")
            
            # --- EKSEKUSI RAG RETRIEVAL ---
            retrieved_context, score = retrieve_context(user_input, kb_chunks)
            
            time.sleep(1)
            if retrieved_context:
                st.write(f"📚 Konteks relevan ditemukan! (Skor: {score:.2f})")
            else:
                st.write(f"📚 Tidak ada konteks relevan. (Skor: {score:.2f})")
                retrieved_context = "Tidak ada data yang relevan."
                
            time.sleep(1)
            st.write("🧠 Menyiapkan Konteks RAG dan menghubungi Groq LLM...")
            
            # Rancang prompt sistem Closed-Domain QA
            system_prompt = f"""
            Kamu adalah Enyx, seorang Senior Software Engineer. Tugasmu menganalisis error log.
            
            [DATA KNOWLEDGE BASE]
            {retrieved_context}
            [/DATA KNOWLEDGE BASE]
            
            ATURAN KETAT (CLOSED-DOMAIN QA):
            1. Kamu HANYA boleh memberikan solusi berdasarkan [DATA KNOWLEDGE BASE] di atas.
            2. Jika [DATA KNOWLEDGE BASE] berisi "Tidak ada data yang relevan.", atau jika error log tidak berkaitan dengan data di atas, kamu HARUS menolak menjawab dengan mengisi `root_cause` dan `solution_steps` dengan: "Maaf, data tidak ditemukan di Knowledge Base perusahaan."
            3. DILARANG KERAS mengarang solusi (hallucination) menggunakan pre-trained knowledge-mu di luar Data Knowledge Base.
            4. Output HARUS berupa JSON murni dengan struktur: status, severity, root_cause, solution_steps (array), code_snippet.
            """
            
            full_prompt = f"{system_prompt}\n\nInput User:\n{user_input}"
            
            # Setup endpoint API Groq
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": full_prompt}],
                "response_format": {"type": "json_object"}
            }
            
            try:
                # Eksekusi request ke server Groq
                response = requests.post(url, headers=headers, json=payload)
                response_data = response.json()
                
                # Cek jika ada error dari server Groq
                if 'error' in response_data:
                    status.update(label="Groq API Error", state="error", expanded=True)
                    st.error(f"❌ Groq API Error: {response_data['error'].get('message')}")
                    st.stop()
                
                # Ekstrak teks balasan JSON
                ai_text = response_data['choices'][0]['message']['content']
                ai_output = json.loads(ai_text)
                
                status.update(label="Analisis Selesai! Solusi Ditemukan.", state="complete", expanded=False)
                
                # --- TAMPILKAN BUKTI RAG KE DOSEN ---
                with st.expander("📂 Data Ditemukan di Knowledge Base (Bukti RAG)", expanded=True):
                    if retrieved_context != "Tidak ada data yang relevan.":
                        st.success(retrieved_context)
                    else:
                        st.warning(retrieved_context)
                
                # 5. Render Output UI Streamlit
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
                status.update(label="Gagal mem-parsing JSON", state="error", expanded=True)
                st.error("Sistem gagal mem-parsing format respons JSON dari AI.")
            except Exception as e:
                status.update(label="Kegagalan Koneksi API", state="error", expanded=True)
                st.error(f"Terjadi kegagalan koneksi API: {e}")
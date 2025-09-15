import streamlit as st
import os
from ollama import Client

# Pick up host from env
ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
client = Client(host=ollama_host)

def translator_agent(text: str, target_lang: str, model: str = "qwen2.5-coder:0.5b"):
    system_prompt = f"You are a helpful translator. Translate any input text into {target_lang}."
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text}
    ]
    
    response = client.chat(model=model, messages=messages)
    return response["message"]["content"]

# Streamlit UI
st.title("🌍 Translator Agent (Ollama)")
target_lang = st.selectbox("Select Target Language", ["English", "Bengali", "Hindi", "Japanese"])
text = st.text_area("Enter text to translate")

if st.button("Translate"):
    if text.strip():
        translation = translator_agent(text, target_lang)
        st.success(f"**Translation ({target_lang}):** {translation}")
    else:
        st.warning("⚠ Please enter some text first.")

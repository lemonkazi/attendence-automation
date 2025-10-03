import streamlit as st
import os
from langchain_groq import ChatGroq
from dotenv import load_dotenv
load_dotenv() 

# Get Groq API key from environment
groq_api_key = os.getenv("GROQ_API_KEY")

def translator_agent(text: str, target_lang: str, model: str = "openai/gpt-oss-120b"):
    system_prompt = f"You are a helpful translator. Translate any input text into {target_lang}."
    chat = ChatGroq(temperature=0, groq_api_key=groq_api_key, model_name=model)

    messages = [
        ("system", system_prompt),
        ("human", text)
    ]

    response = chat.invoke(messages)
    return response.content

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

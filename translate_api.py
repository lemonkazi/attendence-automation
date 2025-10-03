from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_groq import ChatGroq
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TranslationRequest(BaseModel):
    text: str
    target_lang: str
    model: str = "phi3-mini"

@app.post("/translate")
async def translate(request: TranslationRequest):
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is not set")

    system_prompt = f"You are a helpful translator. Translate any input text into {request.target_lang}."
    chat = ChatGroq(temperature=0, groq_api_key=groq_api_key, model_name=request.model)

    messages = [
        ("system", system_prompt),
        ("human", request.text)
    ]

    response = chat.invoke(messages)
    return {"translation": response.content}


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8502, debug=True)

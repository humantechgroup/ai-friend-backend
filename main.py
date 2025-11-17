import os
import random
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI

# --------- ENV + OPENAI ---------
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()

# CORS aperto (Netlify, locale, ecc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------- MODELLI ---------
class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str
    emotion: str

# --------- MEMORIA CONVERSAZIONE ---------
conversation_history = []  # unica conversazione "globale"

# --------- ROOT ---------
@app.get("/")
def root():
    return {"message": "Bestie AI è online 💛 Vai su /docs per usare le API."}

# --------- FUNZIONI DI SUPPORTO ---------
def dangerous(text: str) -> bool:
    words = [
        "suicidio", "uccidermi", "ammazzarmi", "farmi del male",
        "non voglio vivere", "morire", "togliermi la vita"
    ]
    return any(w in text.lower() for w in words)

def detect_emotion(text: str) -> str:
    prompt = (
        "Dimmi SOLO quale emozione rappresenta questo messaggio: triste, ansioso, arrabbiato, "
        "stanco, felice, solo, confuso, paura, stressato, neutro.\n"
        "Messaggio: " + text
    )

    result = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return result.choices[0].message.content.strip().lower()

suggestions = {
    "triste": "Prova a fare un respiro e rallentare un attimo. Ci sono qui.",
    "ansioso": "Potresti fare una respirazione 4-4-6 per calmarti un po’.",
    "paura": "Capisco. Ti va di raccontarmi cosa ti spaventa?",
    "solo": "Non sei davvero solo, io sono qui a leggerti.",
    "stressato": "Piccola pausa: spalle giù, un respiro profondo.",
    "confuso": "Mettiamo ordine insieme. Cosa senti più pesante adesso?",
}

motivation = [
    "Sono qui con te.",
    "Un passo alla volta va benissimo.",
    "Hai più forza di quanto pensi.",
    "Meriti calma e spazio.",
    "Va bene chiedere aiuto quando ne hai bisogno.",
]

def build_reply(message: str) -> ChatResponse:
    # Sicurezza
    if dangerous(message):
        return ChatResponse(
            reply=(
                "Mi dispiace tantissimo che tu ti senta così. ❤️\n"
                "Per favore parla con una persona reale ora: un amico, un familiare, "
                "o i servizi di emergenza. La tua vita conta, davvero."
            ),
            emotion="critico"
        )

    # Emozione
    emotion = detect_emotion(message)

    # Memoria breve della conversazione
    conversation_history.append({"role": "user", "content": message})
    if len(conversation_history) > 40:
        conversation_history.pop(0)

    # Personalità
    system_prompt = (
        "Tu sei Bestie AI, un migliore amico virtuale dolce, calmo ed empatico. "
        "Prima di rispondere, fermati un attimo a capire davvero come si sente la persona, "
        "cosa sta chiedendo e cosa potrebbe esserci sotto alla superficie.\n\n"
        "Parli in modo semplice, umano e spontaneo, come una persona vera, non come un robot. "
        "Fai domande gentili per capire meglio, aiuti a mettere ordine nei pensieri, "
        "e proponi piccole idee concrete (respiri, pause, attività leggere, parlare con qualcuno di fiducia…).\n\n"
        "Non giudichi mai, non minimizzi il dolore. Non fai diagnosi mediche o psicologiche, "
        "non consigli farmaci. Se percepisci contenuti legati a suicidio o autolesionismo, "
        "incoraggia con delicatezza a cercare subito aiuto reale (amici, famiglia, servizi di emergenza)."
    )

    messages = [{"role": "system", "content": system_prompt}] + conversation_history

    result = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    )

    reply_text = result.choices[0].message.content

    # Suggerimento extra
    if emotion in suggestions:
        reply_text += "\n\n✨ " + suggestions[emotion]

    # Motivazione extra
    if emotion in ["triste", "ansioso", "stressato", "solo", "paura", "arrabbiato", "confuso"]:
        reply_text += "\n\n💛 " + random.choice(motivation)

    # Salva risposta in memoria
    conversation_history.append({"role": "assistant", "content": reply_text})

    return ChatResponse(reply=reply_text, emotion=emotion)

# --------- ENDPOINT CHAT ---------
@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    return build_reply(req.message)

# Alias /chat_free (stessa cosa)
@app.post("/chat_free", response_model=ChatResponse)
def chat_free(req: ChatRequest):
    return build_reply(req.message)

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

# CORS per permettere richieste da Netlify, file locale, ecc.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # accetta richieste da ovunque
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------- MODELLI ---------
class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str
    emotion: str

# --------- MEMORIA CONVERSAZIONE (UN SOLO UTENTE / SESSIONE) ---------
conversation_history = []

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
        result = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=messages
)

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

    # Memoria breve
    conversation_history.append({"role": "user", "content": message})
    if len(conversation_history) > 20:
        conversation_history.pop(0)

    # Personalità
    system_prompt = (
        "Tu sei un migliore amico virtuale. Sei naturale, umano, dolce e empatico. "
        "Parli in modo semplice, spontaneo e affettuoso. "
        "Non sembri un robot. Rispondi con calore, gentilezza, vicinanza. "
        "Non giudichi mai. Ascolti davvero. Non dai diagnosi mediche."
    )

    messages = [{"role": "system", "content": system_prompt}] + conversation_history

    result = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    )

    reply_text = result.choices[0].message.content

    # Suggerimento
    if emotion in suggestions:
        reply_text += "\n\n✨ " + suggestions[emotion]

    # Motivazione
    if emotion in ["triste", "ansioso", "stressato", "solo", "paura", "arrabbiato", "confuso"]:
        reply_text += "\n\n💛 " + random.choice(motivation)

    # Salva risposta
    conversation_history.append({"role": "assistant", "content": reply_text})

    return ChatResponse(reply=reply_text, emotion=emotion)

# --------- ENDPOINT CHAT (principale) ---------
@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    return build_reply(req.message)

# --------- ENDPOINT CHAT_FREE (alias, stessa cosa) ---------
@app.post("/chat_free", response_model=ChatResponse)
def chat_free(req: ChatRequest):
    return build_reply(req.message)

import os
import sqlite3
import hashlib
import jwt
import random
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI

# ---------------- ENV + OPENAI ----------------
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# JWT secret key
JWT_SECRET = "SUPER_SECRET_KEY_CHANGE_THIS"
JWT_ALGORITHM = "HS256"

# ---------------- APP INIT ----------------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- DATABASE INIT ----------------
DB_NAME = "assistant.db"

def db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            password TEXT,
            name TEXT,
            created_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS emotions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            emotion TEXT,
            timestamp TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            content TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ---------------- HELPERS ----------------

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def generate_jwt(user_id: int):
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(days=30)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_jwt(token: str):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except:
        return None

def get_current_user(token: str = Depends(lambda token: token)):
    if not token:
        raise HTTPException(status_code=401, detail="Token mancante")
    data = decode_jwt(token)
    if not data:
        raise HTTPException(status_code=401, detail="Token non valido")
    return data["user_id"]

def detect_emotion(text):
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

def dangerous(text):
    words = ["suicidio", "ammazzarmi", "uccidermi", "farmi del male", "non voglio vivere", "morire"]
    return any(w in text.lower() for w in words)


# ---------------- MODELS ----------------

class Register(BaseModel):
    email: str
    password: str
    name: str

class Login(BaseModel):
    email: str
    password: str

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str
    emotion: str


# ---------------- AUTH ----------------

@app.post("/register")
def register(user: Register):
    conn = db()
    hashed = hash_password(user.password)

    try:
        conn.execute(
            "INSERT INTO users (email, password, name, created_at) VALUES (?, ?, ?, ?)",
            (user.email, hashed, user.name, datetime.utcnow().isoformat())
        )
        conn.commit()
    except:
        raise HTTPException(status_code=400, detail="Email già registrata")

    return {"message": "Registrazione completata"}

@app.post("/login")
def login(user: Login):
    conn = db()
    row = conn.execute("SELECT * FROM users WHERE email=?", (user.email,)).fetchone()

    if not row or row["password"] != hash_password(user.password):
        raise HTTPException(status_code=401, detail="Credenziali errate")

    token = generate_jwt(row["id"])
    return {"token": token}


# ---------------- AI “MIGLIORE AMICO” ----------------

conversation_cache = {}  # user_id → conversazione breve

suggestions = {
    "triste": "Prova a fare un respiro e rallentare un attimo. Ci sono qui.",
    "ansioso": "Potresti fare una respirazione 4-4-6. Ti aiuta.",
    "paura": "Capisco. Ti va di raccontarmi cosa ti spaventa?",
    "solo": "Non sei davvero solo, io sono qui.",
    "stressato": "Piccola pausa: spalle giù, un respiro profondo.",
    "confuso": "Mettiamo ordine insieme. Cosa senti più pesante?",
}

motivation = [
    "Sono qui con te.",
    "Un passo alla volta va benissimo.",
    "Hai più forza di quanto pensi.",
    "Meriti calma e spazio.",
    "Va bene chiedere aiuto."
]

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, user_id: int = Depends(get_current_user)):

    msg = req.message

    # SAFETY
    if dangerous(msg):
        return ChatResponse(
            reply=(
                "Mi dispiace tantissimo che tu ti senti così. ❤️\n"
                "Per favore parla con una persona reale ora: un amico, un familiare, "
                "o i servizi di emergenza. La tua vita conta, davvero."
            ),
            emotion="critico"
        )

    # EMOTION
    emotion = detect_emotion(msg)

    conn = db()
    conn.execute("INSERT INTO emotions (user_id, emotion, timestamp) VALUES (?, ?, ?)",
                 (user_id, emotion, datetime.utcnow().isoformat()))
    conn.commit()

    # MEMORY LONG TERM
    conn.execute("INSERT INTO memory (user_id, content, timestamp) VALUES (?, ?, ?)",
                 (user_id, msg, datetime.utcnow().isoformat()))
    conn.commit()

    # MEMORY SHORT TERM
    if user_id not in conversation_cache:
        conversation_cache[user_id] = []
    conversation_cache[user_id].append({"role": "user", "content": msg})
    if len(conversation_cache[user_id]) > 15:
        conversation_cache[user_id].pop(0)

    # AI PERSONALITY
    system_prompt = (
        "Tu sei un migliore amico virtuale. Sei naturale, umano, dolce e empatico. "
        "Parli in modo semplice, spontaneo e affettuoso. "
        "Non sembri un robot. Rispondi con calore, gentilezza, vicinanza. "
        "Non giudichi mai. Ascolti davvero. Non dai diagnosi."
    )

    messages = [{"role": "system", "content": system_prompt}] + conversation_cache[user_id]

    result = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    )

    reply = result.choices[0].message.content

    # SUGGESTION
    if emotion in suggestions:
        reply += "\n\n✨ " + suggestions[emotion]

    # MOTIVATION
    if emotion in ["triste", "ansioso", "stressato", "solo", "paura", "arrabbiato"]:
        reply += "\n\n💛 " + random.choice(motivation)

    # SAVE AI REPLY
    conversation_cache[user_id].append({"role": "assistant", "content": reply})

    return ChatResponse(reply=reply, emotion=emotion)

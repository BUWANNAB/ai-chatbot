from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import requests

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
OLLAMA_URL = "http://localhost:11434/api/chat"

# ======================
# 🧠 多用户记忆
# ======================
chat_sessions = {}

class ChatRequest(BaseModel):
    session_id: str
    message: str


@app.get("/")
def home():
    return {"message": "AI聊天系统已启动"}


@app.post("/chat")
def chat(req: ChatRequest):

    # 1️⃣ 初始化session
    if req.session_id not in chat_sessions:
        chat_sessions[req.session_id] = [
            {
                "role": "system",
                "content": "你是一个中文AI助手，回答要简洁清晰"
            }
        ]

    history = chat_sessions[req.session_id]

    # 2️⃣ 加入用户消息
    history.append({
        "role": "user",
        "content": req.message
    })

    # 3️⃣ 调用 Ollama Chat API
    res = requests.post(OLLAMA_URL, json={
        "model": "llama3",
        "messages": history,
        "stream": False
    })

    data = res.json()
    reply = data.get("message", {}).get("content", "")

    # 4️⃣ 保存AI回复
    history.append({
        "role": "assistant",
        "content": reply
    })

    # 5️⃣ 控制长度（防爆）
    if len(history) > 20:
        chat_sessions[req.session_id] = history[-20:]

    return {
        "session_id": req.session_id,
        "reply": reply
    }
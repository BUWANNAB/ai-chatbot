from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import requests
import json
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

app = FastAPI()
# ======================
# SQLite数据库
# ======================

DATABASE_URL = "sqlite:///./chat.db"


engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False
    }
)


SessionLocal = sessionmaker(
    bind=engine
)


Base = declarative_base()

app.mount("/static", StaticFiles(directory="static"), name="static")
OLLAMA_URL = "http://localhost:11434/api/chat"

# ======================
# 🧠 多用户记忆
# ======================
chat_sessions = {}

class Message(Base):

    __tablename__ = "messages"

    id = Column(
        Integer,
        primary_key=True
    )

    session_id = Column(
        String
    )

    role = Column(
        String
    )

    content = Column(
        Text
    )

    created_at = Column(
        DateTime,
        default=datetime.now
    )


class ChatRequest(BaseModel): 
    session_id: str
    message: str

# 创建数据库表 
Base.metadata.create_all(
    bind=engine
)


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
# ======================
# 🚀 WebSocket 流式聊天
# ======================

@app.websocket("/ws")
async def websocket_chat(websocket: WebSocket):

    await websocket.accept()

    session_id = "web_user"
    
    db = SessionLocal()


    while True:

        # 接收网页消息
        message = await websocket.receive_text()


        # 初始化历史
        if session_id not in chat_sessions:
            chat_sessions[session_id] = [
                {
                    "role": "system",
                    "content": "你是一个中文AI助手，回答要简洁清晰"
                }
            ]


        history = chat_sessions[session_id]


        # 添加用户消息
        history.append({
            "role": "user",
            "content": message
        })

        db.add(Message(
            session_id=session_id,
            role="user",
            content=message
        ))

        db.commit()
        



        # 调用 Ollama 流式接口
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": "llama3",
                "messages": history,
                "stream": True
            },
            stream=True
        )


        full_reply = ""


        # 一段一段返回
        for line in response.iter_lines():

            if line:

                data = json.loads(line)

                if "message" in data:

                    text = data["message"]["content"]

                    full_reply += text


                    # 发给浏览器
                    await websocket.send_text(text)



        # 保存完整回答
        history.append({
            "role": "assistant",
            "content": full_reply
        })

        db.add(Message(
            session_id=session_id,
            role="assistant",
            content=full_reply
        ))

        db.commit()



        # 控制长度
        if len(history) > 20:
            chat_sessions[session_id] = history[-20:]


# ======================
# 📜 获取历史聊天记录
# ======================

@app.get("/history/{session_id}")
def get_history(session_id: str):

    db = SessionLocal()

    messages = db.query(Message).filter(
        Message.session_id == session_id
    ).order_by(
        Message.created_at
    ).all()

    result = []

    for msg in messages:
        result.append({
            "role": msg.role,
            "content": msg.content
        })

    db.close()

    return result
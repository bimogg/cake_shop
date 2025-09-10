# main.py
import os
import logging
import threading
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import google.generativeai as genai
from typing import List, Optional
import uvicorn

# --------------- Настройка ---------------
load_dotenv()  # прочитать .env (если есть)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logging.warning("GEMINI_API_KEY не задан. AI-ответы работать не будут.")
else:
    genai.configure(api_key=GEMINI_API_KEY)

# Поддерживаем несколько моделей — попробуем по очереди
CANDIDATE_MODELS = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-1.0"]

# --------------- FastAPI app ---------------
app = FastAPI(title="Cake Shop Chatbot")

# CORS (для локальной разработки разрешаем всё; в проде сузить список)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------- Модель данных ---------------
class Cake(BaseModel):
    name: str = Field(..., example="Медовик")
    description: Optional[str] = Field(None, example="Мёдовый торт со сметанным кремом")
    price: float = Field(..., example=4500.0)
    stock: int = Field(..., example=5)

class ChatMessage(BaseModel):
    message: str

# --------------- In-memory DB (пример) ---------------
# Если позже захочешь — можно заменить на реальную БД (Postgres и SQLAlchemy)
cakes_db = [
    {"id": 1, "name": "Медовик", "description": "Торт с медом", "price": 5500.0, "stock": 4},
    {"id": 2, "name": "Молочная девочка", "description": "Нежный молочный торт", "price": 6000.0, "stock": 3},
]
_db_lock = threading.Lock()  # защита от гонок при параллельных запросах

def get_next_id():
    with _db_lock:
        return max([c["id"] for c in cakes_db], default=0) + 1

# --------------- CRUD endpoints ---------------
@app.get("/cakes", response_model=List[dict])
def get_cakes():
    return cakes_db

@app.get("/cakes/{cake_id}", response_model=dict)
def get_cake(cake_id: int):
    for c in cakes_db:
        if c["id"] == cake_id:
            return c
    raise HTTPException(status_code=404, detail="Торт не найден")

@app.post("/cakes", status_code=201, response_model=dict)
def add_cake(cake: Cake):
    new_id = get_next_id()
    new_cake = {"id": new_id, **cake.dict()}
    with _db_lock:
        cakes_db.append(new_cake)
    return new_cake

@app.put("/cakes/{cake_id}", response_model=dict)
def update_cake(cake_id: int, cake: Cake):
    with _db_lock:
        for i, c in enumerate(cakes_db):
            if c["id"] == cake_id:
                updated = {"id": cake_id, **cake.dict()}
                cakes_db[i] = updated
                return updated
    raise HTTPException(status_code=404, detail="Торт не найден")

@app.delete("/cakes/{cake_id}", response_model=dict)
def delete_cake(cake_id: int):
    with _db_lock:
        for c in cakes_db:
            if c["id"] == cake_id:
                cakes_db.remove(c)
                return {"message": f"Торт {cake_id} удалён"}
    raise HTTPException(status_code=404, detail="Торт не найден")

# --------------- AI helper (Gemini) ---------------
def ask_gemini_short(user_message: str, max_sentences: int = 2) -> str:
    """
    Попытка получить краткий ответ от Gemini.
    Пробуем несколько моделей по порядку; возвращаем первую успешную.
    """
    if not GEMINI_API_KEY:
        return "Извините, AI пока не настроен (нет GEMINI_API_KEY)."

    # Ограничиваем prompt: просим кратко 1-2 предложения
    prompt = (
        f"Ты — вежливый консультант в кондитерской. Очень кратко (1–{max_sentences} предложения) "
        f"ответь на запрос клиента: \"{user_message}\""
    )

    for model_name in CANDIDATE_MODELS:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            # response.text обычно содержит итог — если нет, пробуем безопасно
            text = getattr(response, "text", None)
            if not text:
                # иногда library возвращает .content или другой атрибут
                # попытка взять str(response) в крайнем случае
                text = str(response)
            if text:
                return text.strip()
        except Exception as e:
            logging.debug(f"Model {model_name} failed: {e}")
            # пробуем следующую модель
            continue

    return "Извините, сейчас AI недоступен. Попробуйте позже."

# --------------- Chat endpoint ---------------
@app.post("/chatbot/")
async def chatbot(msg: ChatMessage):
    user_message = (msg.message or "").strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="Сообщение пустое")

    # 1) Простой локальный поиск по названию (более быстрый)
    name_lower = user_message.lower()
    for cake in cakes_db:
        if cake["name"].lower() in name_lower:
            # найдено — возвращаем краткую информацию
            return {
                "source": "local",
                "reply": (
                    f"Да, есть {cake['name']}. {cake.get('description','')}. "
                    f"Цена: {cake['price']}₸. В наличии: {cake['stock']} шт."
                )
            }

    # 2) Если не найдено — обращаемся к Gemini (AI) за коротким советом
    ai_reply = ask_gemini_short(user_message, max_sentences=2)
    return {"source": "ai", "reply": ai_reply}

# --------------- serve index.html if present ---------------
@app.get("/", response_class=HTMLResponse)
def index():
    path = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h3>API работает. Добавьте index.html рядом с main.py для фронтенда.</h3>"

# --------------- Run server (если запускать python main.py) ---------------
if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

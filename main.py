from fastapi import FastAPI, Depends
from sqlalchemy import create_engine, Column, Integer, String, Numeric, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from rapidfuzz import fuzz

# -------------------------
# Настройки базы данных
# -------------------------
DATABASE_URL = "postgresql://alina:12345@localhost/shop_db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# -------------------------
# Модель таблицы Product
# -------------------------
class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    quantity = Column(Integer, default=0)

# -------------------------
# Pydantic схема для валидации
# -------------------------
class ProductCreate(BaseModel):
    name: str
    price: float
    description: str | None = None

# -------------------------
# Создание таблиц
# -------------------------
Base.metadata.create_all(bind=engine)

# -------------------------
# FastAPI app
# -------------------------
app = FastAPI()

# Зависимость для БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------------------------
# Эндпоинты
# -------------------------

# Добавить продукт
@app.post("/products/")
def create_product(product: ProductCreate, db: Session = Depends(get_db)):
    db_product = Product(
        name=product.name,
        price=product.price,
        description=product.description,
        quantity=10
    )
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

# Список продуктов
@app.get("/products/")
def get_products(db: Session = Depends(get_db)):
    return db.query(Product).all()

# -------------------------
# Чат-бот (поиск по товарам)
# -------------------------
@app.get("/chatbot/")
def chatbot(message: str, db: Session = Depends(get_db)):
    products = db.query(Product).all()
    best_match = None
    best_score = 0

    for product in products:
        score = fuzz.ratio(message.lower(), product.name.lower())
        if score > best_score:
            best_score = score
            best_match = product

    if best_match and best_score > 60:  # порог похожести
        return {"answer": f"Да, у нас есть {best_match.name}. Цена: {best_match.price} ₸"}
    else:
        return {"answer": "Извините, такого товара нет в наличии."}
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Укажи свои данные для подключения
DATABASE_URL = "postgresql+psycopg2://alina:12345@localhost:5432/shop_db"


engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

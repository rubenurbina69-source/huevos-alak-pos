import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 🔥 Detecta si estamos en Render o en local
DATABASE_URL = os.getenv("DATABASE_URL")

# 👉 Si NO existe (trabajando en tu PC)
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./huevos_alak.db"

# 👉 Si es postgres (Render)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Configuración especial solo para SQLite
connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
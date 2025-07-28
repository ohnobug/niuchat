from sqlalchemy import Enum, create_engine, Column, Integer, String, Text, TIMESTAMP, Boolean, func, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL

engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    pool_size=70,
    pool_recycle=1800,
    max_overflow=100
)
AsyncSessionLocal: sessionmaker = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_db():
    async with AsyncSessionLocal() as db:
        try:
            yield db
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()


metadata = MetaData()
Base = declarative_base(metadata=metadata)

class TurUsers(Base):
    __tablename__ = "tur_users"
    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String(20), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())


class TurChatSessions(Base):
    __tablename__ = "tur_chat_sessions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    title = Column(String(255), nullable=False, index=False)
    llm_model_name = Column(String(255), nullable=False, index=False)
    me_smart_customer_service_version = Column(String(20), nullable=False, index=False)
    created_at = Column(TIMESTAMP, server_default=func.now())


class TurChatHistory(Base):
    __tablename__ = "tur_chat_history"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    chat_session_id = Column(Integer, index=True)
    sender = Column(Enum("ai", "user"), nullable=False)
    text = Column(Text, nullable=False, index=True)
    created_at = Column(TIMESTAMP, server_default=func.now())


class TurVerifyCodes(Base):
    __tablename__ = "tur_verify_codes"
    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String(20), nullable=False, index=True)
    code = Column(String(10), nullable=False)
    purpose = Column(String(50), nullable=False)
    is_used = Column(Boolean, default=False)
    used_at = Column(TIMESTAMP, default=0)
    created_at = Column(TIMESTAMP, server_default=func.now())

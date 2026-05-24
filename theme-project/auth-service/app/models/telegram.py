from sqlalchemy import Column, String, DateTime, func
from app.database import Base

class TelegramAuthSession(Base):
    __tablename__ = "telegram_auth_sessions"

    state      = Column(String, primary_key=True)
    jwt_token  = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
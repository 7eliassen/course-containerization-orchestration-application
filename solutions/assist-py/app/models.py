from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.database import Base


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text, nullable=False)
    owner = Column(String(100), nullable=False, default="anonymous")
    created_at = Column(DateTime, default=datetime.utcnow)


from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from app.models.incident import Base
from datetime import datetime


class ActionLog(Base):
    __tablename__ = "action_logs"

    id = Column(UUID(as_uuid=True), primary_key=True)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id"), nullable=False)
    command = Column(Text, nullable=False)
    status = Column(String, nullable=False)
    result = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    confidence_score = Column(Float, nullable=True)

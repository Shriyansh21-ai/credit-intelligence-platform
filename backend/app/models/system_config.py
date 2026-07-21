"""System configuration model (Phase 5, Milestone 13).

A single key/value store (value held as JSON) so every tunable — risk thresholds,
rating scale, approval matrix, interest rules, loan limits, industries,
currencies, notification rules, stress scenarios — lives in the database rather
than in code.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, JSON, String, Text

from backend.app.db.database import Base


class SystemConfig(Base):
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, nullable=False, unique=True, index=True)
    value = Column(JSON, nullable=True)
    value_type = Column(String, nullable=False, default="json")  # json/number/string/bool/list
    category = Column(String, nullable=False, default="General", index=True)
    description = Column(Text, nullable=True)

    updated_by = Column(Integer, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

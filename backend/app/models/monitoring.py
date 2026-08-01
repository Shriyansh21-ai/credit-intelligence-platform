"""Post-disbursement monitoring models.

``MonitoringRecord`` captures a periodic update on a live loan (financials, GST
bank statement, payment behaviour, rating change, ...). ``MonitoringAlert`` flags
deterioration detected across successive records.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text

from backend.app.db.database import Base


class MonitoringRecord(Base):
    __tablename__ = "monitoring_records"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(
        Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # financial_update / quarterly_statement / annual_report / gst /
    # bank_statement / payment_behaviour / rating_change
    record_type = Column(String, nullable=False, index=True)
    period = Column(String, nullable=True)

    health_score = Column(Float, nullable=True)   # 0-100 where available
    risk_rating = Column(String, nullable=True)
    payment_status = Column(String, nullable=True)  # on_time / late / default

    data = Column(JSON, nullable=True)
    note = Column(Text, nullable=True)

    recorded_by = Column(Integer, nullable=True)
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)


class MonitoringAlert(Base):
    __tablename__ = "monitoring_alerts"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(
        Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    record_id = Column(Integer, ForeignKey("monitoring_records.id"), nullable=True)

    category = Column(String, nullable=False)  # deterioration / rating_downgrade / payment_delay
    severity = Column(String, nullable=False, default="medium")
    message = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="open")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

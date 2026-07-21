"""Covenant monitoring models (Phase 5, Milestone 5).

A ``Covenant`` is a threshold condition attached to an application/loan (e.g.
"Minimum DSCR >= 1.25"). Each ``CovenantMeasurement`` records the metric's value
at a point in time and its pass/breach status. Breaches raise a ``CovenantAlert``.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.app.db.database import Base


class Covenant(Base):
    __tablename__ = "covenants"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(
        Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )

    metric_key = Column(String, nullable=False, index=True)  # dscr, debt_ratio, ...
    name = Column(String, nullable=False)
    # "min" => breach when value < threshold; "max" => breach when value > threshold.
    operator = Column(String, nullable=False, default="min")
    threshold = Column(Float, nullable=False)
    unit = Column(String, nullable=True)
    description = Column(Text, nullable=True)

    is_active = Column(String, nullable=False, default="active")  # active / waived / closed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    measurements = relationship(
        "CovenantMeasurement",
        back_populates="covenant",
        order_by="CovenantMeasurement.measured_at",
        cascade="all, delete-orphan",
    )


class CovenantMeasurement(Base):
    __tablename__ = "covenant_measurements"

    id = Column(Integer, primary_key=True, index=True)
    covenant_id = Column(
        Integer, ForeignKey("covenants.id", ondelete="CASCADE"), nullable=False, index=True
    )

    value = Column(Float, nullable=True)
    status = Column(String, nullable=False, default="ok")  # ok / warning / breach / unknown
    headroom = Column(Float, nullable=True)  # signed distance from threshold
    period = Column(String, nullable=True)
    source = Column(String, nullable=True)
    note = Column(Text, nullable=True)
    measured_at = Column(DateTime, default=datetime.utcnow, index=True)

    covenant = relationship("Covenant", back_populates="measurements")


class CovenantAlert(Base):
    __tablename__ = "covenant_alerts"

    id = Column(Integer, primary_key=True, index=True)
    covenant_id = Column(Integer, ForeignKey("covenants.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    measurement_id = Column(Integer, ForeignKey("covenant_measurements.id"), nullable=True)

    severity = Column(String, nullable=False, default="high")
    message = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="open")  # open / acknowledged / resolved
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

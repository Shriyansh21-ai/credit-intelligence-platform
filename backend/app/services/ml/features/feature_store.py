"""Versioned persistence for feature vectors.

Saving a vector for an assessment supersedes the previous ``is_current`` row and
inserts an incremented ``version``, so the full history of feature generations
is preserved — the substrate a future training pipeline will read from.
"""

from __future__ import annotations

from typing import List, Mapping, Optional

from sqlalchemy.orm import Session

from backend.app.models.feature_vector import FeatureVector

from .feature_serializer import headline_columns, json_columns


def save_feature_vector(
    db: Session,
    *,
    user_id: int,
    assessment_id: Optional[int],
    vector: Mapping,
) -> FeatureVector:
    """Persist a pipeline payload as a new current version, superseding any
    prior current row for the same assessment."""
    version = 1
    if assessment_id is not None:
        current = (
            db.query(FeatureVector)
            .filter(
                FeatureVector.assessment_id == assessment_id,
                FeatureVector.is_current.is_(True),
            )
            .order_by(FeatureVector.version.desc())
            .first()
        )
        if current is not None:
            version = current.version + 1
            current.is_current = False
            db.add(current)

    record = FeatureVector(
        user_id=user_id,
        assessment_id=assessment_id,
        version=version,
        is_current=True,
        **headline_columns(vector),
        **json_columns(vector),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_current_for_assessment(db: Session, assessment_id: int) -> Optional[FeatureVector]:
    return (
        db.query(FeatureVector)
        .filter(
            FeatureVector.assessment_id == assessment_id,
            FeatureVector.is_current.is_(True),
        )
        .order_by(FeatureVector.version.desc())
        .first()
    )


def latest_for_user(db: Session, user_id: int) -> Optional[FeatureVector]:
    return (
        db.query(FeatureVector)
        .filter(
            FeatureVector.user_id == user_id,
            FeatureVector.is_current.is_(True),
        )
        .order_by(FeatureVector.created_at.desc(), FeatureVector.id.desc())
        .first()
    )


def get_by_id(db: Session, vector_id: int) -> Optional[FeatureVector]:
    return db.query(FeatureVector).filter(FeatureVector.id == vector_id).first()


def history_for_assessment(db: Session, assessment_id: int) -> List[FeatureVector]:
    return (
        db.query(FeatureVector)
        .filter(FeatureVector.assessment_id == assessment_id)
        .order_by(FeatureVector.version.desc())
        .all()
    )

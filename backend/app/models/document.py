"""Document Intelligence persistence models.

`Document` holds metadata + a storage URI (files live in the storage backend
never as DB blobs). `DocumentExtraction` holds each extraction/edit as a
versioned row so the review history is preserved.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String

from backend.app.db.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # Optional link to an enterprise assessment (future: apply extracted fields).
    assessment_id = Column(Integer, ForeignKey("enterprise_assessments.id"), nullable=True)

    document_type = Column(String, nullable=False, default="other")
    original_filename = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    storage_uri = Column(String, nullable=False)
    content_hash = Column(String, nullable=False, index=True)

    status = Column(String, nullable=False, default="uploaded")
    ocr_engine = Column(String, nullable=True)
    ocr_source = Column(String, nullable=True)  # pdf-text / ocr / text
    page_count = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DocumentExtraction(Base):
    __tablename__ = "document_extractions"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    is_current = Column(Boolean, nullable=False, default=True)

    # List of field dicts: {key,label,type,value,raw_text,confidence,bbox,edited}.
    fields = Column(JSON, nullable=False, default=list)
    # List of issue dicts: {field,severity,message}.
    validation = Column(JSON, nullable=False, default=list)

    overall_confidence = Column(Float, nullable=True)
    source = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

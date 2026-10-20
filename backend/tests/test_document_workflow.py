from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.app.core.dependencies import get_db
from backend.app.models.company import Company, CompanyFinancials
from backend.app.models.document import Document, DocumentReviewEvent
from backend.app.models.tenancy import TenantMembership
from backend.app.models.user import User
from backend.app.routes import auth as auth_routes
from backend.app.routes import documents as document_routes
from backend.app.services.documents.document_service import DocumentService
from backend.app.services.documents import storage as storage_module
from backend.app.services.documents.storage import LocalStorageBackend
from backend.app.services.documents.text_extraction import DocumentTextExtractor
from backend.app.services.rbac.seeding import assign_role
from backend.app.services.saas.provisioning import resolve_user_tenant
from backend.tests._demo_portfolio_helpers import auth_headers, fresh_session, signup

try:
    import fitz
except ImportError:  # pragma: no cover
    fitz = None


def _financial_pdf(revenue: str = "24,000,000") -> bytes:
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text(
        (60, 60),
        "Meridian Industrial Pvt Ltd\n"
        "Financial Year: 2024-25\n"
        f"Revenue from operations: {revenue}\n"
        "Gross Profit: 8,400,000\n"
        "Net Profit: 2,600,000\n"
        "Current Assets: 9,200,000\n"
        "Current Liabilities: 4,400,000\n"
        "GSTIN: 27ABCDE1234F1Z5",
        fontsize=11,
    )
    content = pdf.tobytes()
    pdf.close()
    return content


def _client(session_factory: sessionmaker) -> TestClient:
    app = FastAPI()
    app.include_router(auth_routes.router)
    app.include_router(document_routes.router)

    def override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def _new_user(client: TestClient, session_factory: sessionmaker, email: str, role: str = "administrator"):
    headers = auth_headers(signup(client, email))
    db = session_factory()
    try:
        user = db.query(User).filter(User.email == email).one()
        assign_role(db, user, role, replace=True)
        tenant = resolve_user_tenant(db, user)
        assert tenant is not None
        return headers, tenant.id, user.id
    finally:
        db.close()


def _company(session_factory: sessionmaker, tenant_id: int, name: str = "Meridian Industrial"):
    db = session_factory()
    try:
        company = Company(
            tenant_id=tenant_id,
            external_id=f"test-{tenant_id}-{name}",
            name=name,
            industry="Manufacturing",
            currency="INR",
            is_demo=False,
            data_source="test",
        )
        db.add(company)
        db.commit()
        db.refresh(company)
        return company.id
    finally:
        db.close()


def _upload(client, headers, company_id: int, content: bytes | None = None):
    return client.post(
        "/documents/upload",
        headers=headers,
        data={
            "document_type": "balance_sheet",
            "company_id": str(company_id),
            "fiscal_year": "2025",
            "currency": "INR",
            "unit": "thousands",
        },
        files={"files": ("statement.pdf", content or _financial_pdf(), "application/pdf")},
    )


@pytest.fixture
def workflow(tmp_path, monkeypatch):
    engine, session_factory = fresh_session()
    monkeypatch.setattr(storage_module, "_backend", LocalStorageBackend(tmp_path))
    client = _client(session_factory)
    yield engine, session_factory, client
    client.close()
    engine.dispose()


@pytest.mark.skipif(fitz is None, reason="PyMuPDF not available")
def test_document_approval_persists_with_provenance_and_analysis(workflow):
    _, session_factory, client = workflow
    headers, tenant_id, user_id = _new_user(
        client, session_factory, "document-analyst@workflow.example", "senior_analyst"
    )
    company_id = _company(session_factory, tenant_id)

    upload = _upload(client, headers, company_id)
    assert upload.status_code == 200, upload.text
    document = upload.json()["documents"][0]
    assert document["status"] == "uploaded"
    assert document["tenant_id"] == tenant_id
    assert document["company_id"] == company_id

    extracted_response = client.post(f"/documents/{document['id']}/extract", headers=headers)
    assert extracted_response.status_code == 200, extracted_response.text
    extracted = extracted_response.json()["document"]
    assert extracted["status"] == "needs_review"
    revenue = next(field for field in extracted["current_extraction"]["fields"] if field["key"] == "revenue")
    assert revenue["value"] == 24000000
    assert revenue["extracted_value"] == 24000000
    assert revenue["raw_text"]
    assert revenue["bbox"]["page"] == 0
    assert extracted["current_extraction"]["provider"] == "pdf-text"

    reviewed_response = client.put(
        f"/documents/{document['id']}/review",
        headers=headers,
        json={
            "fields": {"revenue": 27000000},
            "company_id": company_id,
            "fiscal_year": 2025,
            "currency": "INR",
            "unit": "thousands",
            "reviewed_by": 999999,
            "reviewed_at": "2000-01-01T00:00:00",
        },
    )
    assert reviewed_response.status_code == 422
    assert client.get(f"/documents/{document['id']}", headers=headers).json()["status"] == "needs_review"

    reviewed_response = client.put(
        f"/documents/{document['id']}/review",
        headers=headers,
        json={
            "fields": {"revenue": 27000000},
            "company_id": company_id,
            "fiscal_year": 2025,
            "currency": "INR",
            "unit": "thousands",
        },
    )
    assert reviewed_response.status_code == 200, reviewed_response.text
    reviewed = reviewed_response.json()["document"]
    assert reviewed["status"] == "reviewed"
    assert reviewed["reviewed_by"] == user_id
    assert reviewed["reviewed_at"] is not None
    assert reviewed["current_extraction"]["version"] == 2
    assert reviewed["current_extraction"]["fields"][0]["confidence"] is not None

    approved_response = client.post(
        f"/documents/{document['id']}/approve",
        headers=headers,
        json={"acknowledged_warnings": []},
    )
    assert approved_response.status_code == 200, approved_response.text
    assert approved_response.json()["persistence_status"] == "persisted"
    assert approved_response.json()["document"]["status"] == "approved"

    db = session_factory()
    try:
        period = db.query(CompanyFinancials).filter_by(company_id=company_id, fiscal_year=2025).one()
        assert period.tenant_id == tenant_id
        assert period.revenue == 27000000
        assert period.currency == "INR"
        assert period.unit == "thousands"
        assert period.source_document_id == document["id"]
        assert period.source_document_extraction_id is not None
        assert period.reviewed_by == user_id
        versions = (
            db.query(document_routes.DocumentExtraction)
            .filter_by(document_id=document["id"])
            .order_by(document_routes.DocumentExtraction.version)
            .all()
        )
        original_revenue = next(field for field in versions[0].fields if field["key"] == "revenue")
        assert original_revenue["value"] == 24000000
        events = db.query(DocumentReviewEvent).filter_by(document_reference_id=document["id"]).all()
        assert [event.event_type for event in events] == ["review", "approval"]
        assert events[0].changes["revenue"] == {"from": 24000000, "to": 27000000}
    finally:
        db.close()

    retry = client.post(
        f"/documents/{document['id']}/approve",
        headers=headers,
        json={"acknowledged_warnings": []},
    )
    assert retry.status_code == 200
    analysis = client.get(f"/documents/{document['id']}/analysis", headers=headers)
    assert analysis.status_code == 200
    assert analysis.json()["analysis_status"] == "incomplete"
    assert analysis.json()["analysis"] is not None


@pytest.mark.skipif(fitz is None, reason="PyMuPDF not available")
def test_tenant_b_cannot_access_or_associate_tenant_a_documents(workflow):
    _, session_factory, client = workflow
    headers_a, tenant_a, _ = _new_user(client, session_factory, "tenant-a@workflow.example")
    headers_b, tenant_b, _ = _new_user(client, session_factory, "tenant-b@workflow.example")
    company_a = _company(session_factory, tenant_a, "Tenant A Company")
    company_b = _company(session_factory, tenant_b, "Tenant B Company")
    uploaded = _upload(client, headers_a, company_a)
    document_id = uploaded.json()["documents"][0]["id"]

    assert client.get(f"/documents/{document_id}", headers=headers_b).status_code == 404
    assert client.get(f"/documents/{document_id}/file", headers=headers_b).status_code == 404
    assert client.get(f"/documents/{document_id}/review-history", headers=headers_b).status_code == 404
    assert client.post(f"/documents/{document_id}/extract", headers=headers_b).status_code == 404
    assert client.put(
        f"/documents/{document_id}/review", headers=headers_b, json={"fields": {"revenue": 2}}
    ).status_code == 404
    assert client.post(
        f"/documents/{document_id}/approve", headers=headers_b, json={}
    ).status_code == 404
    assert client.post(
        f"/documents/{document_id}/reject", headers=headers_b, json={"reason": "test"}
    ).status_code == 404
    assert client.delete(f"/documents/{document_id}", headers=headers_b).status_code == 404
    assert client.get("/documents/history", headers=headers_b).json()["documents"] == []
    assert client.get("/documents/history", headers=headers_a).json()["documents"][0]["id"] == document_id

    forbidden_association = _upload(client, headers_a, company_b)
    assert forbidden_association.status_code == 404

    assert client.post(f"/documents/{document_id}/extract", headers=headers_a).status_code == 200
    rejected_review = client.put(
        f"/documents/{document_id}/review",
        headers=headers_a,
        json={"fields": {}, "company_id": company_b, "fiscal_year": 2025, "currency": "INR"},
    )
    assert rejected_review.status_code == 422
    document = client.get(f"/documents/{document_id}", headers=headers_a).json()
    assert document["company_id"] == company_a


@pytest.mark.skipif(fitz is None, reason="PyMuPDF not available")
def test_extraction_failure_is_recorded_without_exposing_provider_error(workflow, monkeypatch):
    _, session_factory, client = workflow
    headers, tenant_id, _ = _new_user(client, session_factory, "extract-failure@workflow.example")
    company_id = _company(session_factory, tenant_id)
    document_id = _upload(client, headers, company_id).json()["documents"][0]["id"]

    def fail_extraction(*args, **kwargs):
        raise RuntimeError("provider internals")

    monkeypatch.setattr(DocumentTextExtractor, "extract", fail_extraction)
    response = client.post(f"/documents/{document_id}/extract", headers=headers)
    assert response.status_code == 500
    assert response.json()["detail"] == "Document extraction failed."

    db = session_factory()
    try:
        document = db.query(Document).filter_by(id=document_id, tenant_id=tenant_id).one()
        assert document.status == "failed"
    finally:
        db.close()


@pytest.mark.skipif(fitz is None, reason="PyMuPDF not available")
def test_approval_role_gate_period_conflict_and_explicit_restatement(workflow):
    _, session_factory, client = workflow
    headers, tenant_id, user_id = _new_user(client, session_factory, "restatement@workflow.example")
    company_id = _company(session_factory, tenant_id)
    document_id = _upload(client, headers, company_id).json()["documents"][0]["id"]
    assert client.post(f"/documents/{document_id}/extract", headers=headers).status_code == 200
    reviewed = client.put(
        f"/documents/{document_id}/review",
        headers=headers,
        json={
            "fields": {},
            "company_id": company_id,
            "fiscal_year": 2025,
            "currency": "INR",
            "unit": "units",
        },
    )
    assert reviewed.status_code == 200, reviewed.text

    db = session_factory()
    try:
        db.add(CompanyFinancials(
            tenant_id=tenant_id,
            company_id=company_id,
            fiscal_year=2025,
            revenue=100,
            ebitda=77,
            currency="INR",
        ))
        db.commit()
    finally:
        db.close()

    conflict = client.post(
        f"/documents/{document_id}/approve", headers=headers, json={}
    )
    assert conflict.status_code == 409
    assert "explicit conflict resolution" in conflict.json()["detail"]

    unauthorized_headers, _, _ = _new_user(
        client, session_factory, "auditor@workflow.example", "auditor"
    )
    denied = client.post(
        f"/documents/{document_id}/approve", headers=unauthorized_headers, json={}
    )
    assert denied.status_code == 403

    db = session_factory()
    try:
        auditor = db.query(User).filter_by(email="auditor@workflow.example").one()
        db.query(TenantMembership).filter_by(user_id=auditor.id).update(
            {TenantMembership.is_default: False}
        )
        db.add(TenantMembership(
            tenant_id=tenant_id,
            user_id=auditor.id,
            org_role="member",
            status="active",
            is_default=True,
        ))
        db.commit()
        assign_role(db, auditor, "auditor", replace=True)
    finally:
        db.close()
    denied = client.post(
        f"/documents/{document_id}/approve", headers=unauthorized_headers, json={}
    )
    assert denied.status_code == 403

    restated = client.post(
        f"/documents/{document_id}/approve",
        headers=headers,
        json={"replace_existing_financials": True},
    )
    assert restated.status_code == 200, restated.text
    db = session_factory()
    try:
        period = db.query(CompanyFinancials).filter_by(company_id=company_id, fiscal_year=2025).one()
        assert period.revenue == 24000000
        assert period.net_income == 2600000
        assert period.ebitda == 77
        assert period.source_document_id == document_id
        assert period.reviewed_by == user_id
        event = (
            db.query(DocumentReviewEvent)
            .filter_by(document_reference_id=document_id, event_type="restatement")
            .one()
        )
        assert event.changes["replaced_financials"]["revenue"] == 100
    finally:
        db.close()


@pytest.mark.skipif(fitz is None, reason="PyMuPDF not available")
def test_delete_removes_private_file_and_extraction_rows_but_retains_event(workflow):
    _, session_factory, client = workflow
    headers, tenant_id, user_id = _new_user(client, session_factory, "delete@workflow.example")
    company_id = _company(session_factory, tenant_id)
    document_id = _upload(client, headers, company_id).json()["documents"][0]["id"]
    assert client.post(f"/documents/{document_id}/extract", headers=headers).status_code == 200

    db = session_factory()
    try:
        document = db.query(Document).filter_by(id=document_id).one()
        uri = document.storage_uri
        storage = DocumentService(db).storage
        assert storage.exists(uri)
    finally:
        db.close()

    deleted = client.delete(f"/documents/{document_id}", headers=headers)
    assert deleted.status_code == 204, deleted.text
    db = session_factory()
    try:
        assert db.query(Document).filter_by(id=document_id).count() == 0
        assert db.query(document_routes.DocumentExtraction).filter_by(document_id=document_id).count() == 0
        event = db.query(DocumentReviewEvent).filter_by(document_reference_id=document_id).one()
        assert event.document_id is None
        assert event.actor_id == user_id
    finally:
        db.close()
    assert not storage.exists(uri)


@pytest.mark.skipif(fitz is None, reason="PyMuPDF not available")
def test_approved_document_cannot_be_deleted_while_financials_reference_it(workflow):
    _, session_factory, client = workflow
    headers, tenant_id, _ = _new_user(client, session_factory, "protected-delete@workflow.example")
    company_id = _company(session_factory, tenant_id)
    document_id = _upload(client, headers, company_id).json()["documents"][0]["id"]
    assert client.post(f"/documents/{document_id}/extract", headers=headers).status_code == 200

    reviewed = client.put(
        f"/documents/{document_id}/review",
        headers=headers,
        json={
            "fields": {},
            "company_id": company_id,
            "fiscal_year": 2025,
            "currency": "INR",
            "unit": "units",
        },
    )
    assert reviewed.status_code == 200, reviewed.text
    approved = client.post(f"/documents/{document_id}/approve", headers=headers, json={})
    assert approved.status_code == 200, approved.text

    deleted = client.delete(f"/documents/{document_id}", headers=headers)
    assert deleted.status_code == 409
    assert client.get(f"/documents/{document_id}", headers=headers).status_code == 200

    db = session_factory()
    try:
        financials = db.query(CompanyFinancials).filter_by(company_id=company_id).one()
        assert financials.source_document_id == document_id
    finally:
        db.close()

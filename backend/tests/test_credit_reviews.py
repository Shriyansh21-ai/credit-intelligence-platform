from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.core.dependencies import get_current_tenant_id, get_current_user
from backend.app.db.database import get_db
from backend.app.models.company import Company, CompanyFinancials
from backend.app.models.document import Document
from backend.app.models.tenancy import Organization, Tenant, TenantMembership
from backend.app.models.user import User
from backend.app.routes.credit_reviews import router
from backend.app.services.rbac.seeding import assign_role
from backend.tests._demo_portfolio_helpers import fresh_session


@pytest.fixture
def review_setup():
    engine, session_factory = fresh_session()
    db = session_factory()
    org_a = Organization(slug="review-bank-a", name="Review Bank A")
    org_b = Organization(slug="review-bank-b", name="Review Bank B")
    db.add_all([org_a, org_b])
    db.flush()
    tenant_a = Tenant(organization_id=org_a.id, slug="default", name="Bank A", is_default=True)
    tenant_b = Tenant(organization_id=org_b.id, slug="default", name="Bank B", is_default=True)
    db.add_all([tenant_a, tenant_b])
    db.flush()

    def add_user(email: str, role: str, tenant_id: int) -> int:
        user = User(email=email, password="hash")
        db.add(user)
        db.flush()
        db.add(
            TenantMembership(
                tenant_id=tenant_id,
                user_id=user.id,
                org_role="member",
                status="active",
                is_default=True,
            )
        )
        db.commit()
        assign_role(db, user, role, replace=True)
        return user.id

    analyst_id = add_user("review-analyst@example.test", "credit_analyst", tenant_a.id)
    reviewer_id = add_user("review-reviewer@example.test", "senior_analyst", tenant_a.id)
    manager_id = add_user("review-manager@example.test", "risk_manager", tenant_a.id)
    viewer_id = add_user("review-viewer@example.test", "viewer", tenant_a.id)
    outsider_id = add_user("review-outsider@example.test", "risk_manager", tenant_b.id)

    company_a = Company(
        tenant_id=tenant_a.id,
        external_id="review-company-a",
        name="Borrower A",
        industry="Manufacturing",
        is_demo=False,
        data_source="test",
    )
    company_b = Company(
        tenant_id=tenant_b.id,
        external_id="review-company-b",
        name="Borrower B",
        industry="Manufacturing",
        is_demo=False,
        data_source="test",
    )
    db.add_all([company_a, company_b])
    db.flush()
    approved_document = Document(
        tenant_id=tenant_a.id,
        user_id=analyst_id,
        company_id=company_a.id,
        fiscal_year=2025,
        document_type="financial_statement",
        original_filename="approved-2025.pdf",
        mime_type="application/pdf",
        size_bytes=123,
        storage_uri="private://approved-2025",
        content_hash="a" * 64,
        status="approved",
    )
    unapproved_document = Document(
        tenant_id=tenant_a.id,
        user_id=analyst_id,
        company_id=company_a.id,
        fiscal_year=2024,
        document_type="financial_statement",
        original_filename="reviewed-2024.pdf",
        mime_type="application/pdf",
        size_bytes=123,
        storage_uri="private://reviewed-2024",
        content_hash="b" * 64,
        status="reviewed",
    )
    db.add_all([approved_document, unapproved_document])
    db.flush()
    approved_financial = CompanyFinancials(
        tenant_id=tenant_a.id,
        company_id=company_a.id,
        fiscal_year=2025,
        revenue=1000000,
        source_document_id=approved_document.id,
        reviewed_by=reviewer_id,
    )
    unapproved_financial = CompanyFinancials(
        tenant_id=tenant_a.id,
        company_id=company_a.id,
        fiscal_year=2024,
        revenue=900000,
        source_document_id=unapproved_document.id,
        reviewed_by=reviewer_id,
    )
    db.add_all([approved_financial, unapproved_financial])
    db.commit()
    company_a_id = company_a.id
    company_b_id = company_b.id
    financial_id = approved_financial.id
    unapproved_financial_id = unapproved_financial.id
    tenant_a_id = tenant_a.id
    tenant_b_id = tenant_b.id
    db.close()

    state = {"user_id": analyst_id, "tenant_id": tenant_a_id}
    app = FastAPI()
    app.include_router(router)

    def override_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def override_user():
        session = session_factory()
        try:
            return session.query(User).filter(User.id == state["user_id"]).one()
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_current_tenant_id] = lambda: state["tenant_id"]
    client = TestClient(app)
    yield {
        "client": client,
        "session_factory": session_factory,
        "state": state,
        "tenant_a": tenant_a_id,
        "tenant_b": tenant_b_id,
        "analyst_id": analyst_id,
        "reviewer_id": reviewer_id,
        "manager_id": manager_id,
        "viewer_id": viewer_id,
        "outsider_id": outsider_id,
        "company_a_id": company_a_id,
        "company_b_id": company_b_id,
        "financial_id": financial_id,
        "unapproved_financial_id": unapproved_financial_id,
    }
    client.close()
    engine.dispose()


def _create_case(setup, company_id=None):
    response = setup["client"].post(
        "/api/credit-reviews/cases",
        json={
            "company_id": company_id or setup["company_a_id"],
            "review_type": "initial_assessment",
            "title": "Annual credit review",
            "purpose": "Renewal review",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _submit_assessment(setup, case_id, *, submit=True, financial_id=None):
    return setup["client"].post(
        f"/api/credit-reviews/cases/{case_id}/assessments",
        json={
            "summary": "Cash generation supports the requested renewal.",
            "strengths": ["Stable revenue"],
            "weaknesses": ["Working capital needs monitoring"],
            "risk_indicators": ["Concentration"],
            "data_quality_concerns": [],
            "mitigations": ["Quarterly reporting"],
            "outstanding_questions": [],
            "evidence_refs": {
                "financial_ids": [financial_id or setup["financial_id"]]
            },
            "recommendation": "recommend_approval_with_conditions",
            "recommendation_rationale": "Approved source statements support review.",
            "submit": submit,
        },
    )


def test_case_links_only_approved_financial_evidence(review_setup):
    response = _create_case(review_setup)
    assert response["status"] == "draft"
    assert response["reporting_periods"] == [2025]
    assert [row["fiscal_year"] for row in response["financials"]] == [2025]
    assert response["financials"][0]["approved"] is True
    assert response["financials"][0]["source_document_name"] == "approved-2025.pdf"


def test_case_creation_rejects_cross_tenant_company_and_hides_other_cases(review_setup):
    created = _create_case(review_setup)
    client = review_setup["client"]
    response = client.post(
        "/api/credit-reviews/cases",
        json={"company_id": review_setup["company_b_id"], "title": "Cross-tenant"},
    )
    assert response.status_code == 404
    review_setup["state"].update(
        user_id=review_setup["outsider_id"], tenant_id=review_setup["tenant_b"]
    )
    assert client.get(f"/api/credit-reviews/cases/{created['id']}").status_code == 404
    assert client.get("/api/credit-reviews/cases").json()["total"] == 0
    assert client.patch(
        f"/api/credit-reviews/cases/{created['id']}/assignment",
        json={
            "analyst_id": review_setup["outsider_id"],
            "reviewer_id": None,
        },
    ).status_code == 404
    assert client.post(
        f"/api/credit-reviews/cases/{created['id']}/decisions",
        json={"outcome": "approved", "rationale": "Cross-tenant attempt."},
    ).status_code == 404


def test_assessment_submission_requires_complete_fields(review_setup):
    case = _create_case(review_setup)
    response = _submit_assessment(review_setup, case["id"], submit=False)
    assert response.status_code == 201
    response = review_setup["client"].post(
        f"/api/credit-reviews/cases/{case['id']}/assessments",
        json={"submit": True},
    )
    assert response.status_code == 422
    detail = review_setup["client"].get(f"/api/credit-reviews/cases/{case['id']}").json()
    assert detail["status"] == "draft"


def test_assessment_cannot_reference_unapproved_financials(review_setup):
    case = _create_case(review_setup)
    response = _submit_assessment(
        review_setup,
        case["id"],
        financial_id=review_setup["unapproved_financial_id"],
    )
    assert response.status_code == 404
    detail = review_setup["client"].get(f"/api/credit-reviews/cases/{case['id']}").json()
    assert detail["assessments"] == []


def test_assessments_are_versioned_and_submitted_to_approval(review_setup):
    case = _create_case(review_setup)
    assert _submit_assessment(review_setup, case["id"], submit=False).status_code == 201
    response = _submit_assessment(review_setup, case["id"])
    assert response.status_code == 201, response.text
    detail = response.json()
    assert detail["status"] == "in_review"
    assert [assessment["version"] for assessment in detail["assessments"]] == [1, 2]
    response = review_setup["client"].post(
        f"/api/credit-reviews/cases/{case['id']}/submit-for-approval"
    )
    assert response.status_code == 200
    assert response.json()["status"] == "pending_approval"
    duplicate = review_setup["client"].post(
        f"/api/credit-reviews/cases/{case['id']}/submit-for-approval"
    )
    assert duplicate.status_code == 409


def test_analyst_cannot_make_final_decision(review_setup):
    case = _create_case(review_setup)
    assert _submit_assessment(review_setup, case["id"]).status_code == 201
    setup = review_setup
    setup["client"].post(f"/api/credit-reviews/cases/{case['id']}/submit-for-approval")
    response = setup["client"].post(
        f"/api/credit-reviews/cases/{case['id']}/decisions",
        json={"outcome": "approved", "rationale": "Not permitted"},
    )
    assert response.status_code == 403


def test_reviewer_decision_conditions_and_completion_history(review_setup):
    case = _create_case(review_setup)
    denied = review_setup["client"].patch(
        f"/api/credit-reviews/cases/{case['id']}/assignment",
        json={
            "analyst_id": review_setup["analyst_id"],
            "reviewer_id": review_setup["reviewer_id"],
        },
    )
    assert denied.status_code == 403
    review_setup["state"]["user_id"] = review_setup["manager_id"]
    same_person = review_setup["client"].patch(
        f"/api/credit-reviews/cases/{case['id']}/assignment",
        json={
            "analyst_id": review_setup["analyst_id"],
            "reviewer_id": review_setup["analyst_id"],
        },
    )
    assert same_person.status_code == 409
    assignment = review_setup["client"].patch(
        f"/api/credit-reviews/cases/{case['id']}/assignment",
        json={
            "analyst_id": review_setup["analyst_id"],
            "reviewer_id": review_setup["reviewer_id"],
        },
    )
    assert assignment.status_code == 200
    review_setup["state"]["user_id"] = review_setup["analyst_id"]
    assert _submit_assessment(review_setup, case["id"]).status_code == 201
    assert (
        review_setup["client"]
        .post(f"/api/credit-reviews/cases/{case['id']}/submit-for-approval")
        .status_code
        == 200
    )
    review_setup["state"]["user_id"] = review_setup["reviewer_id"]
    queue = review_setup["client"].get("/api/credit-reviews/dashboard")
    assert queue.status_code == 200
    assert [item["id"] for item in queue.json()["approval_queue"]] == [case["id"]]
    response = review_setup["client"].post(
        f"/api/credit-reviews/cases/{case['id']}/decisions",
        json={
            "outcome": "approved_with_conditions",
            "rationale": "Approval is subject to quarterly reporting.",
            "conditions": [
                {
                    "description": "Submit quarterly management accounts.",
                    "responsible_user_id": review_setup["analyst_id"],
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    detail = response.json()
    assert detail["status"] == "approved"
    assert detail["decisions"][0]["outcome"] == "approved_with_conditions"
    condition = detail["conditions"][0]
    completed = review_setup["client"].patch(
        f"/api/credit-reviews/cases/{case['id']}/conditions/{condition['id']}",
        json={"status": "completed", "notes": "2026 Q1 accounts received and reviewed."},
    )
    assert completed.status_code == 200
    assert completed.json()["conditions"][0]["status"] == "completed"
    assert len(completed.json()["condition_history"]) == 2
    duplicate = review_setup["client"].patch(
        f"/api/credit-reviews/cases/{case['id']}/conditions/{condition['id']}",
        json={"status": "waived", "notes": "A second, conflicting action."},
    )
    assert duplicate.status_code == 409


def test_assignments_require_workflow_permissions(review_setup):
    case = _create_case(review_setup)
    review_setup["state"]["user_id"] = review_setup["manager_id"]
    candidates = review_setup["client"].get("/api/credit-reviews/assignment-candidates")
    assert candidates.status_code == 200
    candidate_by_id = {item["id"]: item for item in candidates.json()}
    assert candidate_by_id[review_setup["viewer_id"]]["can_be_analyst"] is False
    assert review_setup["outsider_id"] not in candidate_by_id
    response = review_setup["client"].patch(
        f"/api/credit-reviews/cases/{case['id']}/assignment",
        json={
            "analyst_id": review_setup["viewer_id"],
            "reviewer_id": review_setup["reviewer_id"],
        },
    )
    assert response.status_code == 422


def test_decisions_require_distinct_approver_rationale_and_conditions(review_setup):
    case = _create_case(review_setup)
    review_setup["state"]["user_id"] = review_setup["manager_id"]
    review_setup["client"].patch(
        f"/api/credit-reviews/cases/{case['id']}/assignment",
        json={
            "analyst_id": review_setup["analyst_id"],
            "reviewer_id": review_setup["reviewer_id"],
        },
    )
    review_setup["state"]["user_id"] = review_setup["analyst_id"]
    assert _submit_assessment(review_setup, case["id"]).status_code == 201
    review_setup["client"].post(f"/api/credit-reviews/cases/{case['id']}/submit-for-approval")
    review_setup["state"]["user_id"] = review_setup["manager_id"]
    response = review_setup["client"].post(
        f"/api/credit-reviews/cases/{case['id']}/decisions",
        json={"outcome": "approved", "rationale": "Manager is not the assigned reviewer."},
    )
    assert response.status_code == 403
    review_setup["state"]["user_id"] = review_setup["reviewer_id"]
    response = review_setup["client"].post(
        f"/api/credit-reviews/cases/{case['id']}/decisions",
        json={"outcome": "approved_with_conditions", "rationale": "Need covenants."},
    )
    assert response.status_code == 422
    response = review_setup["client"].post(
        f"/api/credit-reviews/cases/{case['id']}/decisions",
        json={
            "outcome": "declined",
            "rationale": " ",
        },
    )
    assert response.status_code == 422


def test_invalid_condition_assignee_rolls_back_decision_and_state(review_setup):
    case = _create_case(review_setup)
    review_setup["state"]["user_id"] = review_setup["manager_id"]
    review_setup["client"].patch(
        f"/api/credit-reviews/cases/{case['id']}/assignment",
        json={
            "analyst_id": review_setup["analyst_id"],
            "reviewer_id": review_setup["reviewer_id"],
        },
    )
    review_setup["state"]["user_id"] = review_setup["analyst_id"]
    assert _submit_assessment(review_setup, case["id"]).status_code == 201
    review_setup["client"].post(f"/api/credit-reviews/cases/{case['id']}/submit-for-approval")
    review_setup["state"]["user_id"] = review_setup["reviewer_id"]
    response = review_setup["client"].post(
        f"/api/credit-reviews/cases/{case['id']}/decisions",
        json={
            "outcome": "approved_with_conditions",
            "rationale": "Conditional approval must not persist for invalid assignment.",
            "conditions": [
                {
                    "description": "Provide quarterly statements.",
                    "responsible_user_id": review_setup["outsider_id"],
                }
            ],
        },
    )
    assert response.status_code == 404
    detail = review_setup["client"].get(f"/api/credit-reviews/cases/{case['id']}").json()
    assert detail["status"] == "pending_approval"
    assert detail["decisions"] == []
    assert detail["conditions"] == []


def test_reopen_keeps_prior_decision_and_links_next_decision(review_setup):
    case = _create_case(review_setup)
    review_setup["client"].patch(
        f"/api/credit-reviews/cases/{case['id']}/assignment",
        json={
            "analyst_id": review_setup["analyst_id"],
            "reviewer_id": review_setup["reviewer_id"],
        },
    )
    assert _submit_assessment(review_setup, case["id"]).status_code == 201
    review_setup["client"].post(f"/api/credit-reviews/cases/{case['id']}/submit-for-approval")
    review_setup["state"]["user_id"] = review_setup["reviewer_id"]
    first = review_setup["client"].post(
        f"/api/credit-reviews/cases/{case['id']}/decisions",
        json={"outcome": "deferred", "rationale": "Awaiting updated management accounts."},
    )
    assert first.status_code == 201
    review_setup["state"]["user_id"] = review_setup["analyst_id"]
    review_setup["client"].post(
        f"/api/credit-reviews/cases/{case['id']}/resume",
        json={"reason": "Requested accounts have been added to the assessment."},
    )
    assert _submit_assessment(review_setup, case["id"]).status_code == 201
    review_setup["client"].post(f"/api/credit-reviews/cases/{case['id']}/submit-for-approval")
    review_setup["state"]["user_id"] = review_setup["reviewer_id"]
    second = review_setup["client"].post(
        f"/api/credit-reviews/cases/{case['id']}/decisions",
        json={"outcome": "approved", "rationale": "Updated evidence supports approval."},
    )
    assert second.status_code == 201
    decisions = second.json()["decisions"]
    assert len(decisions) == 2
    assert decisions[1]["previous_decision_id"] == decisions[0]["id"]


def test_finalized_case_reopen_starts_an_audited_new_cycle(review_setup):
    case = _create_case(review_setup)
    review_setup["state"]["user_id"] = review_setup["manager_id"]
    review_setup["client"].patch(
        f"/api/credit-reviews/cases/{case['id']}/assignment",
        json={
            "analyst_id": review_setup["analyst_id"],
            "reviewer_id": review_setup["reviewer_id"],
        },
    )
    review_setup["state"]["user_id"] = review_setup["analyst_id"]
    assert _submit_assessment(review_setup, case["id"]).status_code == 201
    review_setup["client"].post(f"/api/credit-reviews/cases/{case['id']}/submit-for-approval")
    review_setup["state"]["user_id"] = review_setup["reviewer_id"]
    first = review_setup["client"].post(
        f"/api/credit-reviews/cases/{case['id']}/decisions",
        json={"outcome": "approved", "rationale": "Original review approved."},
    )
    assert first.status_code == 201
    first_decision_id = first.json()["decisions"][0]["id"]

    review_setup["state"]["user_id"] = review_setup["manager_id"]
    reopened = review_setup["client"].post(
        f"/api/credit-reviews/cases/{case['id']}/reopen",
        json={"reason": "A material change requires a new review cycle."},
    )
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "in_review"
    assert reopened.json()["cycle_number"] == 2

    review_setup["state"]["user_id"] = review_setup["analyst_id"]
    assert _submit_assessment(review_setup, case["id"]).status_code == 201
    review_setup["client"].post(f"/api/credit-reviews/cases/{case['id']}/submit-for-approval")
    review_setup["state"]["user_id"] = review_setup["reviewer_id"]
    second = review_setup["client"].post(
        f"/api/credit-reviews/cases/{case['id']}/decisions",
        json={"outcome": "declined", "rationale": "Updated risk is outside appetite."},
    )
    assert second.status_code == 201
    decisions = second.json()["decisions"]
    assert [decision["id"] for decision in decisions][0] == first_decision_id
    assert decisions[1]["previous_decision_id"] == first_decision_id
    assert decisions[1]["cycle_number"] == 2
    assert "credit_review.reopened" in [event["action"] for event in second.json()["history"]]


def test_case_history_records_actor_and_state_transitions(review_setup):
    case = _create_case(review_setup)
    response = _submit_assessment(review_setup, case["id"])
    actions = [event["action"] for event in response.json()["history"]]
    assert "credit_review.created" in actions
    assert "credit_review.assessment_submitted" in actions
    assert "credit_review.transition" in actions
    assert all(event["actor_id"] is not None for event in response.json()["history"])

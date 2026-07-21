"""Phase 5, Milestone 7 tests: report builders, renderers, API."""

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.dependencies import get_current_user
from backend.app.db.database import Base, get_db
from backend.app.models import audit as audit_model  # noqa: F401
from backend.app.models import approval as approval_model  # noqa: F401
from backend.app.models import covenant as covenant_model  # noqa: F401
from backend.app.models import monitoring as monitoring_model  # noqa: F401
from backend.app.models import financial_analysis as financial_model  # noqa: F401
from backend.app.models import rbac as rbac_model  # noqa: F401
from backend.app.models.enterprise_assessment import EnterpriseAssessment
from backend.app.models.application import Application  # noqa: F401
from backend.app.models.user import User
from backend.app.routes import reports as report_routes
from backend.app.services import lifecycle, reports
from backend.app.services.rbac import sync_rbac
from backend.app.services.rbac.seeding import assign_role


class _Actor:
    def __init__(self, uid=1, email="a@x.com"):
        self.id = uid
        self.email = email


class ReportServiceTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def _app(self, db):
        return lifecycle.create_application(db, actor=_Actor(), company_name="Acme Ltd")

    def test_credit_memo_json(self):
        db = self.Session()
        app = self._app(db)
        result = reports.generate_report(db, report_type="credit_memo", fmt="json", application_id=app.id)
        self.assertEqual(result["format"], "json")
        self.assertTrue(len(result["document"]["sections"]) >= 1)
        db.close()

    def test_pdf_render(self):
        db = self.Session()
        app = self._app(db)
        result = reports.generate_report(db, report_type="credit_memo", fmt="pdf", application_id=app.id)
        # reportlab is installed -> real PDF bytes.
        self.assertEqual(result["content_type"], "application/pdf")
        self.assertTrue(result["content"].startswith(b"%PDF"))
        db.close()

    def test_csv_and_rtf(self):
        db = self.Session()
        app = self._app(db)
        csv_r = reports.generate_report(db, report_type="executive_summary", fmt="csv", application_id=app.id)
        self.assertEqual(csv_r["content_type"], "text/csv")
        rtf_r = reports.generate_report(db, report_type="executive_summary", fmt="rtf", application_id=app.id)
        self.assertTrue(rtf_r["content"].startswith(b"{\\rtf"))
        db.close()

    def test_portfolio_and_audit_no_app(self):
        db = self.Session()
        self._app(db)
        pr = reports.generate_report(db, report_type="portfolio_report", fmt="json")
        self.assertEqual(pr["document"]["type"], "portfolio_report")
        ar = reports.generate_report(db, report_type="audit_report", fmt="json")
        self.assertEqual(ar["document"]["type"], "audit_report")
        db.close()

    def test_app_scoped_requires_id(self):
        db = self.Session()
        with self.assertRaises(reports.service.ReportError):
            reports.generate_report(db, report_type="credit_memo", fmt="json")
        db.close()


class ReportApiTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        db = self.Session()
        sync_rbac(db)
        self.app_id = lifecycle.create_application(db, actor=_Actor(), company_name="Acme").id
        db.close()

    def _user(self, email, role):
        db = self.Session()
        try:
            u = User(email=email, password="x")
            db.add(u)
            db.commit()
            db.refresh(u)
            assign_role(db, u, role)
            return u.id
        finally:
            db.close()

    def _client(self, uid):
        app = FastAPI()
        app.include_router(report_routes.router)

        def override_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        def override_user():
            db = self.Session()
            try:
                return db.query(User).filter(User.id == uid).first()
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = override_user
        return TestClient(app)

    def test_export_requires_export_permission(self):
        uid = self._user("viewer@x.com", "viewer")  # reports.view but not reports.export
        client = self._client(uid)
        # JSON view is allowed
        self.assertEqual(
            client.get(f"/api/reports/credit_memo?application_id={self.app_id}").status_code, 200
        )
        # PDF export is not
        self.assertEqual(
            client.get(f"/api/reports/credit_memo?format=pdf&application_id={self.app_id}").status_code,
            403,
        )

    def test_senior_analyst_can_export_pdf(self):
        uid = self._user("sa@x.com", "senior_analyst")  # has reports.export
        client = self._client(uid)
        resp = client.get(f"/api/reports/credit_memo?format=pdf&application_id={self.app_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["content-type"], "application/pdf")

    def test_types_endpoint(self):
        uid = self._user("analyst@x.com", "credit_analyst")
        client = self._client(uid)
        body = client.get("/api/reports/types").json()
        self.assertIn("credit_memo", body["report_types"])
        self.assertTrue(body["available_formats"]["pdf"])


if __name__ == "__main__":
    unittest.main()

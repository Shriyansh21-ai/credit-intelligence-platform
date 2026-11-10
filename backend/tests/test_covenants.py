""" tests: covenant tracking, breach alerts, trend, API."""

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.dependencies import get_current_user
from backend.app.db.database import Base, get_db
from backend.app.models import audit as audit_model  # noqa: F401
from backend.app.models import company as company_model  # noqa: F401
from backend.app.models import document as document_model  # noqa: F401
from backend.app.models import enterprise_assessment  # noqa: F401
from backend.app.models import rbac as rbac_model  # noqa: F401
from backend.app.models.application import Application
from backend.app.models.covenant import (
    Covenant,
    CovenantAlert,
    CovenantMeasurement,
)
from backend.app.models.user import User
from backend.app.routes import covenants as covenant_routes
from backend.app.routes import dashboards as dashboard_routes
from backend.app.services import covenants
from backend.app.services.covenants.service import CovenantOwnershipError, evaluate_covenant
from backend.app.services.rbac import sync_rbac
from backend.app.services.rbac.seeding import assign_role
from backend.tests.tenant_test_utils import ensure_test_membership


class _Actor:
    def __init__(self, user_id, email):
        self.id = user_id
        self.email = email


class CovenantEvalTest(unittest.TestCase):
    def test_min_operator(self):
        self.assertEqual(evaluate_covenant("min", 1.25, 1.5)["status"], "ok")
        self.assertEqual(evaluate_covenant("min", 1.25, 1.0)["status"], "breach")
        self.assertEqual(evaluate_covenant("min", 1.25, 1.26)["status"], "warning")
        self.assertEqual(evaluate_covenant("min", 1.25, None)["status"], "unknown")

    def test_max_operator(self):
        self.assertEqual(evaluate_covenant("max", 0.6, 0.4)["status"], "ok")
        self.assertEqual(evaluate_covenant("max", 0.6, 0.8)["status"], "breach")
        self.assertEqual(evaluate_covenant("max", 0.6, 0.59)["status"], "warning")


class CovenantServiceTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        db = self.Session()
        self.tenant_id = ensure_test_membership(db, 101, "service@x.com")
        self.actor = _Actor(101, "service@x.com")
        application = Application(
            user_id=101,
            tenant_id=self.tenant_id,
            company_name="Service test application",
        )
        db.add(application)
        db.commit()
        self.application_id = application.id
        db.close()

    def test_breach_creates_alert(self):
        db = self.Session()
        cov = covenants.create_covenant(
            db, application_id=self.application_id, tenant_id=self.tenant_id,
            metric_key="dscr", threshold=1.25, actor=self.actor,
        )
        result = covenants.record_measurement(
            db, cov, tenant_id=self.tenant_id, value=1.0, period="Q1", actor=self.actor
        )
        self.assertEqual(result["measurement"]["status"], "breach")
        self.assertIsNotNone(result["alert"])
        self.assertEqual(db.query(CovenantAlert).count(), 1)
        db.close()

    def test_no_alert_when_compliant(self):
        db = self.Session()
        cov = covenants.create_covenant(
            db, application_id=self.application_id, tenant_id=self.tenant_id,
            metric_key="dscr", threshold=1.25, actor=self.actor,
        )
        result = covenants.record_measurement(
            db, cov, tenant_id=self.tenant_id, value=1.8, actor=self.actor
        )
        self.assertEqual(result["measurement"]["status"], "ok")
        self.assertIsNone(result["alert"])
        db.close()

    def test_trend_direction(self):
        db = self.Session()
        cov = covenants.create_covenant(
            db, application_id=self.application_id, tenant_id=self.tenant_id,
            metric_key="dscr", threshold=1.25, actor=self.actor,
        )
        for v in (1.2, 1.4, 1.6):
            covenants.record_measurement(
                db, cov, tenant_id=self.tenant_id, value=v, actor=self.actor
            )
        trend = covenants.covenant_trend(db, cov, tenant_id=self.tenant_id)
        self.assertEqual(trend["direction"], "improving")
        self.assertEqual(len(trend["points"]), 3)
        db.close()

    def test_creation_rejects_foreign_or_unassigned_applications(self):
        db = self.Session()
        other_tenant_id = ensure_test_membership(db, 102, "other-service@x.com")
        foreign_application = Application(
            user_id=102,
            tenant_id=other_tenant_id,
            company_name="Foreign application",
        )
        unassigned_application = Application(
            user_id=101,
            tenant_id=None,
            company_name="Historical application",
        )
        db.add_all([foreign_application, unassigned_application])
        db.commit()

        for application_id in (foreign_application.id, unassigned_application.id):
            with self.assertRaises(CovenantOwnershipError):
                covenants.create_covenant(
                    db,
                    application_id=application_id,
                    tenant_id=self.tenant_id,
                    metric_key="dscr",
                    threshold=1.25,
                    actor=self.actor,
                )
        self.assertEqual(db.query(Covenant).count(), 0)
        db.close()

    def test_null_tenant_scope_cannot_read_unassigned_covenants(self):
        db = self.Session()
        application = Application(
            user_id=101,
            tenant_id=None,
            company_name="Unassigned application",
        )
        db.add(application)
        db.flush()
        covenant = Covenant(
            application_id=application.id,
            metric_key="dscr",
            name="Unassigned covenant",
            operator="min",
            threshold=1.25,
        )
        db.add(covenant)
        db.commit()

        self.assertIsNone(covenants.get_covenant(db, covenant.id, None))
        with self.assertRaises(CovenantOwnershipError):
            covenants.list_covenants(db, application.id, tenant_id=None)
        db.close()


class CovenantApiTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        db = self.Session()
        sync_rbac(db)
        db.close()

    def _user(self, email, role):
        db = self.Session()
        try:
            u = User(email=email, password="x")
            db.add(u)
            db.commit()
            db.refresh(u)
            assign_role(db, u, role)
            ensure_test_membership(db, u.id, email)
            return u.id
        finally:
            db.close()

    def _application(self, uid, company_name="Tenant application", tenant_id=None):
        db = self.Session()
        try:
            if tenant_id is None:
                from backend.app.models.tenancy import TenantMembership

                tenant_id = (
                    db.query(TenantMembership.tenant_id)
                    .filter(
                        TenantMembership.user_id == uid,
                        TenantMembership.status == "active",
                    )
                    .order_by(TenantMembership.is_default.desc(), TenantMembership.id)
                    .first()[0]
                )
            application = Application(
                user_id=uid,
                tenant_id=tenant_id,
                company_name=company_name,
            )
            db.add(application)
            db.commit()
            return application.id
        finally:
            db.close()

    def _covenant(self, uid, application_id, value=1.0):
        client = self._client(uid)
        created = client.post(
            f"/api/covenants/applications/{application_id}",
            json={"metric_key": "dscr", "threshold": 1.25},
        )
        self.assertEqual(created.status_code, 201)
        measured = client.post(
            f"/api/covenants/{created.json()['id']}/measurements", json={"value": value}
        )
        self.assertEqual(measured.status_code, 200)
        return created.json()["id"], measured.json().get("alert")

    def _client(self, uid):
        app = FastAPI()
        app.include_router(covenant_routes.router)
        app.include_router(dashboard_routes.router)

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

    def test_create_requires_manage(self):
        uid = self._user("viewer@x.com", "viewer")
        client = self._client(uid)
        resp = client.post("/api/covenants/applications/1", json={"metric_key": "dscr", "threshold": 1.25})
        self.assertEqual(resp.status_code, 403)

    def test_flow_with_breach(self):
        uid = self._user("rm@x.com", "risk_manager")
        client = self._client(uid)
        application_id = self._application(uid)
        created = client.post(
            f"/api/covenants/applications/{application_id}",
            json={"metric_key": "dscr", "threshold": 1.25},
        )
        self.assertEqual(created.status_code, 201)
        cov_id = created.json()["id"]

        m = client.post(f"/api/covenants/{cov_id}/measurements", json={"value": 1.0})
        self.assertEqual(m.json()["measurement"]["status"], "breach")

        alerts = client.get(f"/api/covenants/applications/{application_id}/alerts").json()["alerts"]
        self.assertEqual(len(alerts), 1)

        # Covenant listing reflects current value/status.
        listed = client.get(f"/api/covenants/applications/{application_id}").json()["covenants"]
        self.assertEqual(listed[0]["current_status"], "breach")

    def test_foreign_tenant_reads_and_writes_are_rejected_without_side_effects(self):
        owner_id = self._user("owner@x.com", "risk_manager")
        owner_app_id = self._application(owner_id, "Tenant A")
        covenant_id, alert = self._covenant(owner_id, owner_app_id)
        alert_id = alert["id"]

        other_id = self._user("other@x.com", "risk_manager")
        other_app_id = self._application(other_id, "Tenant B")
        other = self._client(other_id)
        own_covenant = other.post(
            f"/api/covenants/applications/{other_app_id}",
            json={"metric_key": "current_ratio", "threshold": 1.5},
        )
        self.assertEqual(own_covenant.status_code, 201)
        before = self._counts()

        foreign_create = other.post(
            f"/api/covenants/applications/{owner_app_id}",
            json={"metric_key": "dscr", "threshold": 1.25},
        )
        self.assertEqual(foreign_create.status_code, 404)
        self.assertEqual(other.get(f"/api/covenants/applications/{owner_app_id}").status_code, 404)
        self.assertEqual(other.get(f"/api/covenants/{covenant_id}/trend").status_code, 404)
        self.assertEqual(
            other.get(f"/api/covenants/applications/{owner_app_id}/alerts").status_code, 404
        )
        self.assertEqual(
            other.post(f"/api/covenants/{covenant_id}/measurements", json={"value": 0.1}).status_code,
            404,
        )
        batch = other.post(
            "/api/covenants/batch-measurements",
            json={
                "items": [
                    {"covenant_id": own_covenant.json()["id"], "value": 1.0},
                    {"covenant_id": covenant_id, "value": 0.1},
                ]
            },
        )
        self.assertEqual(batch.status_code, 404)
        self.assertEqual(other.patch(f"/api/covenants/alerts/{alert_id}", json={"status": "resolved"}).status_code, 404)
        self.assertEqual(self._counts(), before)
        self.assertEqual(
            other.get("/api/dashboards/operations").json()["totals"]["open_alerts"], 0
        )
        self.assertEqual(
            self._client(owner_id).get("/api/dashboards/operations").json()["totals"]["open_alerts"],
            1,
        )
        visible_ids = {
            covenant["id"]
            for covenant in other.get(
                f"/api/covenants/applications/{other_app_id}"
            ).json()["covenants"]
        }
        self.assertEqual(visible_ids, {own_covenant.json()["id"]})

    def test_client_tenant_id_cannot_override_application_ownership(self):
        uid = self._user("spoof@x.com", "risk_manager")
        application_id = self._application(uid)
        client = self._client(uid)
        response = client.post(
            f"/api/covenants/applications/{application_id}",
            json={"metric_key": "dscr", "threshold": 1.25, "tenant_id": 999999},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["application_id"], application_id)

    def test_mismatched_legacy_alert_references_are_not_visible_or_mutable(self):
        owner_id = self._user("alert-owner@x.com", "risk_manager")
        owner_app_id = self._application(owner_id, "Tenant A")
        _covenant_id, valid_alert = self._covenant(owner_id, owner_app_id)

        other_id = self._user("alert-other@x.com", "risk_manager")
        other_app_id = self._application(other_id, "Tenant B")
        other_client = self._client(other_id)
        other_covenant = other_client.post(
            f"/api/covenants/applications/{other_app_id}",
            json={"metric_key": "current_ratio", "threshold": 1.5},
        ).json()
        db = self.Session()
        try:
            foreign_measurement = CovenantMeasurement(
                covenant_id=other_covenant["id"],
                value=2.0,
                status="ok",
            )
            db.add(foreign_measurement)
            db.flush()
            mismatched_application_alert = CovenantAlert(
                covenant_id=valid_alert["covenant_id"],
                application_id=other_app_id,
                measurement_id=valid_alert["measurement_id"],
                severity="high",
                message="Mismatched application",
                status="open",
            )
            mismatched_measurement_alert = CovenantAlert(
                covenant_id=valid_alert["covenant_id"],
                application_id=owner_app_id,
                measurement_id=foreign_measurement.id,
                severity="high",
                message="Mismatched measurement",
                status="open",
            )
            db.add_all([mismatched_application_alert, mismatched_measurement_alert])
            db.commit()
            invalid_alert_ids = [
                mismatched_application_alert.id,
                mismatched_measurement_alert.id,
            ]
        finally:
            db.close()

        owner_client = self._client(owner_id)
        alerts = owner_client.get(
            f"/api/covenants/applications/{owner_app_id}/alerts"
        ).json()["alerts"]
        self.assertEqual([row["id"] for row in alerts], [valid_alert["id"]])
        for alert_id in invalid_alert_ids:
            self.assertEqual(
                owner_client.patch(
                    f"/api/covenants/alerts/{alert_id}",
                    json={"status": "resolved"},
                ).status_code,
                404,
            )

    def test_unassigned_and_orphaned_legacy_covenants_are_inaccessible_but_preserved(self):
        owner_id = self._user("history@x.com", "risk_manager")
        tenant_application_id = self._application(owner_id)
        db = self.Session()
        try:
            historical = Application(
                user_id=owner_id,
                tenant_id=None,
                company_name="Unassigned historical application",
            )
            db.add(historical)
            db.flush()
            unassigned = Covenant(
                application_id=historical.id,
                metric_key="dscr",
                name="Historical",
                operator="min",
                threshold=1.25,
            )
            orphaned = Covenant(
                application_id=999999,
                metric_key="dscr",
                name="Orphaned",
                operator="min",
                threshold=1.25,
            )
            db.add_all([unassigned, orphaned])
            db.flush()
            unassigned_measurement = CovenantMeasurement(
                covenant_id=unassigned.id,
                value=1.0,
                status="ok",
            )
            orphaned_measurement = CovenantMeasurement(
                covenant_id=orphaned.id,
                value=1.0,
                status="ok",
            )
            db.add_all([unassigned_measurement, orphaned_measurement])
            db.flush()
            unassigned_alert = CovenantAlert(
                covenant_id=unassigned.id,
                application_id=historical.id,
                measurement_id=unassigned_measurement.id,
                message="Unassigned historical alert",
            )
            orphaned_alert = CovenantAlert(
                covenant_id=orphaned.id,
                application_id=999999,
                measurement_id=orphaned_measurement.id,
                message="Orphaned alert",
            )
            db.add_all([unassigned_alert, orphaned_alert])
            db.commit()
            unassigned_id, orphaned_id = unassigned.id, orphaned.id
            historical_id = historical.id
            unassigned_alert_id, orphaned_alert_id = unassigned_alert.id, orphaned_alert.id
        finally:
            db.close()

        client = self._client(owner_id)
        self.assertEqual(client.get(f"/api/covenants/{unassigned_id}/trend").status_code, 404)
        self.assertEqual(client.get(f"/api/covenants/{orphaned_id}/trend").status_code, 404)
        self.assertEqual(
            client.get(f"/api/covenants/applications/{historical_id}/alerts").status_code, 404
        )
        self.assertEqual(
            client.get("/api/covenants/applications/999999/alerts").status_code, 404
        )
        self.assertEqual(
            client.patch(
                f"/api/covenants/alerts/{orphaned_alert_id}",
                json={"status": "resolved"},
            ).status_code,
            404,
        )
        self.assertEqual(
            client.get(f"/api/covenants/applications/{tenant_application_id}").status_code, 200
        )
        db = self.Session()
        try:
            self.assertEqual(
                db.query(Covenant).filter(Covenant.id.in_([unassigned_id, orphaned_id])).count(),
                2,
            )
            self.assertEqual(
                db.query(CovenantMeasurement)
                .filter(
                    CovenantMeasurement.covenant_id.in_([unassigned_id, orphaned_id])
                )
                .count(),
                2,
            )
            self.assertEqual(
                db.query(CovenantAlert)
                .filter(
                    CovenantAlert.id.in_([unassigned_alert_id, orphaned_alert_id])
                )
                .count(),
                2,
            )
        finally:
            db.close()

    def test_tenant_administrator_and_auditor_are_still_scoped(self):
        owner_id = self._user("admin-owner@x.com", "risk_manager")
        application_id = self._application(owner_id)
        covenant_id, _alert = self._covenant(owner_id, application_id, value=1.8)

        admin_id = self._user("tenant-admin@x.com", "administrator")
        auditor_id = self._user("auditor@x.com", "auditor")
        self.assertEqual(
            self._client(admin_id).get(f"/api/covenants/{covenant_id}/trend").status_code, 404
        )
        self.assertEqual(
            self._client(auditor_id).get(f"/api/covenants/{covenant_id}/trend").status_code, 404
        )

    def _tenant_for(self, uid):
        from backend.app.models.tenancy import TenantMembership

        db = self.Session()
        try:
            return (
                db.query(TenantMembership.tenant_id)
                .filter(
                    TenantMembership.user_id == uid,
                    TenantMembership.status == "active",
                )
                .order_by(TenantMembership.is_default.desc(), TenantMembership.id)
                .first()[0]
            )
        finally:
            db.close()

    def _counts(self):
        db = self.Session()
        try:
            from backend.app.models.covenant import CovenantMeasurement

            return (
                db.query(Covenant).count(),
                db.query(CovenantMeasurement).count(),
                db.query(CovenantAlert).count(),
            )
        finally:
            db.close()

    def test_metrics_catalog(self):
        uid = self._user("rm@x.com", "risk_manager")
        client = self._client(uid)
        metrics = client.get("/api/covenants/metrics").json()["metrics"]
        self.assertTrue(any(m["key"] == "dscr" for m in metrics))


if __name__ == "__main__":
    unittest.main()

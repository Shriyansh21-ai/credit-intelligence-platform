"""Phase 5, Milestone 14 tests: TTL cache, background jobs, batch processing."""

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.cache import TTLCache
from backend.app.core.dependencies import get_current_user
from backend.app.db.database import Base, get_db
from backend.app.models import audit as audit_model  # noqa: F401
from backend.app.models import covenant as covenant_model  # noqa: F401
from backend.app.models import monitoring as monitoring_model  # noqa: F401
from backend.app.models import notification as notification_model  # noqa: F401
from backend.app.models import task as task_model  # noqa: F401
from backend.app.models import enterprise_assessment  # noqa: F401
from backend.app.models.application import Application  # noqa: F401
from backend.app.models.user import User
from backend.app.routes import covenants as covenant_routes
from backend.app.routes import jobs as job_routes
from backend.app.services import covenants, jobs
from backend.app.services.rbac import sync_rbac
from backend.app.services.rbac.seeding import assign_role


class TTLCacheTest(unittest.TestCase):
    def test_expiry_via_injected_clock(self):
        now = {"t": 0.0}
        cache = TTLCache(ttl_seconds=10, clock=lambda: now["t"])
        cache.set("k", 42)
        self.assertEqual(cache.get("k"), 42)
        now["t"] = 11
        self.assertIsNone(cache.get("k"))

    def test_get_or_set_and_invalidate(self):
        cache = TTLCache(ttl_seconds=100)
        calls = {"n": 0}

        def factory():
            calls["n"] += 1
            return "v"

        self.assertEqual(cache.get_or_set("k", factory), "v")
        self.assertEqual(cache.get_or_set("k", factory), "v")
        self.assertEqual(calls["n"], 1)  # factory only ran once
        cache.invalidate("k")
        self.assertIsNone(cache.get("k"))


class JobRunnerTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def test_run_all_jobs(self):
        db = self.Session()
        results = jobs.run_all_jobs(db)
        names = {r["job"] for r in results}
        self.assertIn("due_task_scan", names)
        self.assertIn("open_alert_summary", names)
        self.assertTrue(all(r["ok"] for r in results))
        db.close()

    def test_unknown_job(self):
        db = self.Session()
        with self.assertRaises(KeyError):
            jobs.run_job(db, "nope")
        db.close()


class BatchAndJobsApiTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        db = self.Session()
        sync_rbac(db)
        # Two covenants to batch-measure.
        self.c1 = covenants.create_covenant(db, application_id=1, metric_key="dscr", threshold=1.25).id
        self.c2 = covenants.create_covenant(db, application_id=1, metric_key="current_ratio", threshold=1.5).id
        db.close()

    def _user(self, role):
        db = self.Session()
        try:
            u = User(email=f"{role}@x.com", password="x")
            db.add(u)
            db.commit()
            db.refresh(u)
            assign_role(db, u, role)
            return u.id
        finally:
            db.close()

    def _client(self, uid, router):
        app = FastAPI()
        app.include_router(router)

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

    def test_batch_measurements(self):
        uid = self._user("risk_manager")
        client = self._client(uid, covenant_routes.router)
        resp = client.post(
            "/api/covenants/batch-measurements",
            json={"items": [
                {"covenant_id": self.c1, "value": 1.0},   # breach
                {"covenant_id": self.c2, "value": 2.0},   # ok
            ]},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["processed"], 2)
        self.assertEqual(body["breaches"], 1)

    def test_jobs_api_permission(self):
        analyst = self._user("credit_analyst")
        client = self._client(analyst, job_routes.router)
        self.assertEqual(client.post("/api/jobs/run-all").status_code, 403)

    def test_jobs_run_all_as_admin(self):
        admin = self._user("administrator")
        client = self._client(admin, job_routes.router)
        self.assertEqual(client.get("/api/jobs").status_code, 200)
        resp = client.post("/api/jobs/run-all")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(len(resp.json()["results"]) >= 2)


if __name__ == "__main__":
    unittest.main()

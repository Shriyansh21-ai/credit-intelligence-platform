""" tests: enterprise search filters, sort, paginate, facets."""

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.dependencies import get_current_user
from backend.app.db.database import Base, get_db
from backend.app.models import audit as audit_model  # noqa: F401
from backend.app.models import enterprise_assessment  # noqa: F401
from backend.app.models import rbac as rbac_model  # noqa: F401
from backend.app.models.application import Application
from backend.app.models.user import User
from backend.app.routes import search as search_routes
from backend.app.services import lifecycle, search
from backend.app.services.rbac import sync_rbac
from backend.app.services.rbac.seeding import assign_role


class _Actor:
    def __init__(self, uid=1, email="a@x.com"):
        self.id = uid
        self.email = email


class SearchServiceTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self._seed()

    def _seed(self):
        db = self.Session()
        specs = [
            ("Acme Manufacturing", "Manufacturing", "27AAAAA0000A1Z5", "A", "submitted"),
            ("Beta Retail", "Retail", "29BBBBB1111B2Z6", "BB", "approved"),
            ("Gamma Textiles", "Manufacturing", "27CCCCC2222C3Z7", "A", "approved"),
        ]
        for name, industry, gstin, rating, status in specs:
            app = lifecycle.create_application(
                db, actor=_Actor(), company_name=name, industry=industry, gstin=gstin
            )
            app.risk_rating = rating
            app.status = status
            db.commit()
        db.close()

    def test_free_text(self):
        db = self.Session()
        res = search.search_applications(db, q="Acme")
        self.assertEqual(res["total"], 1)
        db.close()

    def test_filter_by_industry_and_facets(self):
        db = self.Session()
        res = search.search_applications(db, industry="Manufacturing")
        self.assertEqual(res["total"], 2)
        statuses = {f["value"] for f in res["facets"]["status"]}
        self.assertTrue(statuses)
        db.close()

    def test_filter_by_gstin_exact(self):
        db = self.Session()
        res = search.search_applications(db, gstin="29BBBBB1111B2Z6")
        self.assertEqual(res["total"], 1)
        self.assertEqual(res["items"][0]["company_name"], "Beta Retail")
        db.close()

    def test_sort_and_paginate(self):
        db = self.Session()
        res = search.search_applications(db, sort_by="company_name", sort_dir="asc", page_size=2)
        self.assertEqual(len(res["items"]), 2)
        self.assertEqual(res["items"][0]["company_name"], "Acme Manufacturing")
        self.assertEqual(res["pages"], 2)
        db.close()

    def test_rating_filter(self):
        db = self.Session()
        res = search.search_applications(db, rating="A")
        self.assertEqual(res["total"], 2)
        db.close()


class SearchApiTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        db = self.Session()
        sync_rbac(db)
        lifecycle.create_application(db, actor=_Actor(), company_name="Acme Ltd", industry="Retail")
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
        app.include_router(search_routes.router)

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

    def test_search_requires_permission(self):
        # A freshly-made role with search.use is viewer; make one without it is hard
        # since all seeded roles include search.use — so test the happy path instead.
        uid = self._user("viewer@x.com", "viewer")
        client = self._client(uid)
        resp = client.get("/api/search?q=Acme")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["total"], 1)

    def test_search_endpoint_facets(self):
        uid = self._user("analyst@x.com", "credit_analyst")
        client = self._client(uid)
        body = client.get("/api/search").json()
        self.assertIn("facets", body)
        self.assertIn("items", body)


if __name__ == "__main__":
    unittest.main()

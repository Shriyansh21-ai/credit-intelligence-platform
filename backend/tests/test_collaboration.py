""" tests: notes, threads, mentions, pins, activity feed."""

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
from backend.app.models import notification as notification_model  # noqa: F401
from backend.app.models import rbac as rbac_model  # noqa: F401
from backend.app.models import task as task_model  # noqa: F401
from backend.app.models import approval as approval_model  # noqa: F401
from backend.app.models.application import Application  # noqa: F401
from backend.app.models.collaboration import Note  # noqa: F401
from backend.app.models.user import User
from backend.app.routes import collaboration as collaboration_routes
from backend.app.services import collaboration, lifecycle, notifications
from backend.app.services.rbac import sync_rbac
from backend.app.services.rbac.seeding import assign_role


class _Actor:
    def __init__(self, uid=1, email="a@x.com"):
        self.id = uid
        self.email = email


class CollaborationServiceTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def _app(self, db):
        return lifecycle.create_application(db, actor=_Actor(), company_name="Acme")

    def test_note_and_reply_thread(self):
        db = self.Session()
        app = self._app(db)
        root = collaboration.create_note(db, application_id=app.id, actor=_Actor(), body="Root note")
        collaboration.create_note(
            db, application_id=app.id, actor=_Actor(), body="A reply", parent_id=root.id
        )
        threaded = collaboration.service.threaded_notes(db, app.id)
        self.assertEqual(len(threaded), 1)
        self.assertEqual(len(threaded[0]["replies"]), 1)
        db.close()

    def test_mention_notifies_user(self):
        db = self.Session()
        # Create a mentionable user.
        u = User(email="mentioned@x.com", password="x")
        db.add(u)
        db.commit()
        db.refresh(u)
        app = self._app(db)
        collaboration.create_note(
            db, application_id=app.id, actor=_Actor(uid=99),
            body="hey @mentioned@x.com please review",
        )
        self.assertEqual(notifications.unread_count(db, u.id), 1)
        db.close()

    def test_explicit_mentions(self):
        db = self.Session()
        app = self._app(db)
        note = collaboration.create_note(
            db, application_id=app.id, actor=_Actor(uid=1), body="fyi", mentions=[2, 3]
        )
        self.assertEqual(sorted(m.user_id for m in note.mentions), [2, 3])
        db.close()

    def test_pin_and_soft_delete(self):
        db = self.Session()
        app = self._app(db)
        note = collaboration.create_note(db, application_id=app.id, actor=_Actor(), body="pin me")
        collaboration.set_pinned(db, note, pinned=True)
        self.assertTrue(note.is_pinned)
        collaboration.delete_note(db, note, actor=_Actor())
        self.assertTrue(note.is_deleted)
        db.close()

    def test_activity_feed_aggregates(self):
        db = self.Session()
        app = self._app(db)
        lifecycle.transition(db, app, "submitted", actor=_Actor())
        collaboration.create_note(db, application_id=app.id, actor=_Actor(), body="note")
        feed = collaboration.activity_feed(db, app.id)
        kinds = {e["kind"] for e in feed}
        self.assertIn("status", kinds)
        self.assertIn("note", kinds)
        db.close()


class CollaborationApiTest(unittest.TestCase):
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
        app.include_router(collaboration_routes.router)

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

    def test_participate_required_to_post(self):
        uid = self._user("viewer@x.com", "viewer")  # has collaboration.view? no
        client = self._client(uid)
        resp = client.post(
            f"/api/collaboration/applications/{self.app_id}/notes",
            json={"body": "hi"},
        )
        self.assertEqual(resp.status_code, 403)

    def test_analyst_can_post_and_list(self):
        uid = self._user("analyst@x.com", "credit_analyst")
        client = self._client(uid)
        created = client.post(
            f"/api/collaboration/applications/{self.app_id}/notes",
            json={"body": "First note"},
        )
        self.assertEqual(created.status_code, 201)
        notes = client.get(f"/api/collaboration/applications/{self.app_id}/notes").json()["notes"]
        self.assertEqual(len(notes), 1)

    def test_activity_endpoint(self):
        uid = self._user("analyst@x.com", "credit_analyst")
        client = self._client(uid)
        client.post(
            f"/api/collaboration/applications/{self.app_id}/notes",
            json={"body": "note"},
        )
        feed = client.get(f"/api/collaboration/applications/{self.app_id}/activity").json()
        self.assertTrue(len(feed["activity"]) >= 1)


if __name__ == "__main__":
    unittest.main()

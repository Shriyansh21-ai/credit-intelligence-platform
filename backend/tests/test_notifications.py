""" tests: notification dispatch, preferences, read state."""

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.dependencies import get_current_user
from backend.app.db.database import Base, get_db
from backend.app.models import enterprise_assessment  # noqa: F401
from backend.app.models import application as application_model  # noqa: F401
from backend.app.models import task as task_model  # noqa: F401
from backend.app.models import rbac as rbac_model  # noqa: F401
from backend.app.models.notification import Notification, NotificationPreference  # noqa: F401
from backend.app.models.user import User
from backend.app.routes import notifications as notification_routes
from backend.app.services import notifications
from backend.app.services.rbac import sync_rbac
from backend.app.services.rbac.seeding import assign_role


class NotificationServiceTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def test_in_app_default_creates_notification(self):
        db = self.Session()
        n = notifications.notify(db, user_id=1, event_type="task_assigned", message="Do X")
        self.assertIsNotNone(n)
        self.assertEqual(notifications.unread_count(db, 1), 1)
        db.close()

    def test_none_recipient_is_noop(self):
        db = self.Session()
        self.assertIsNone(notifications.notify(db, user_id=None, event_type="risk_alert"))
        db.close()

    def test_disabling_in_app_suppresses(self):
        db = self.Session()
        notifications.set_preference(db, 1, "task_assigned", in_app=False)
        n = notifications.notify(db, user_id=1, event_type="task_assigned")
        self.assertIsNone(n)
        self.assertEqual(notifications.unread_count(db, 1), 0)
        db.close()

    def test_mark_read_and_all(self):
        db = self.Session()
        n1 = notifications.notify(db, user_id=1, event_type="risk_alert")
        notifications.notify(db, user_id=1, event_type="risk_alert")
        notifications.mark_read(db, 1, n1.id)
        self.assertEqual(notifications.unread_count(db, 1), 1)
        notifications.mark_all_read(db, 1)
        self.assertEqual(notifications.unread_count(db, 1), 0)
        db.close()

    def test_severity_from_catalog(self):
        db = self.Session()
        n = notifications.notify(db, user_id=1, event_type="covenant_breach")
        self.assertEqual(n.severity, "critical")
        db.close()


class NotificationApiTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        db = self.Session()
        sync_rbac(db)
        db.close()

    def _user(self, email="u@x.com", role="credit_analyst"):
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
        app.include_router(notification_routes.router)

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

    def test_list_and_read_flow(self):
        uid = self._user()
        db = self.Session()
        notifications.notify(db, user_id=uid, event_type="risk_alert", message="danger")
        db.close()

        client = self._client(uid)
        listing = client.get("/api/notifications").json()
        self.assertEqual(listing["unread"], 1)
        nid = listing["items"][0]["id"]

        client.post(f"/api/notifications/{nid}/read")
        self.assertEqual(client.get("/api/notifications/unread-count").json()["unread"], 0)

    def test_only_own_notifications(self):
        me = self._user("me@x.com")
        other = self._user("other@x.com")
        db = self.Session()
        notifications.notify(db, user_id=other, event_type="risk_alert")
        db.close()
        client = self._client(me)
        self.assertEqual(client.get("/api/notifications").json()["total"], 0)

    def test_preferences_update(self):
        uid = self._user()
        client = self._client(uid)
        prefs = client.get("/api/notifications/preferences").json()["preferences"]
        self.assertTrue(len(prefs) >= 5)
        resp = client.put(
            "/api/notifications/preferences",
            json={"event_type": "task_assigned", "email": True},
        )
        self.assertTrue(resp.json()["email"])


if __name__ == "__main__":
    unittest.main()

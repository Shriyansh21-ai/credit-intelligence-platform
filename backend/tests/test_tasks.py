""" tests: task CRUD, notifications on assign/complete, API."""

import unittest
from datetime import datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.dependencies import get_current_user
from backend.app.db.database import Base, get_db
from backend.app.models import enterprise_assessment  # noqa: F401
from backend.app.models import application as application_model  # noqa: F401
from backend.app.models import rbac as rbac_model  # noqa: F401
from backend.app.models.notification import Notification  # noqa: F401
from backend.app.models.task import Task  # noqa: F401
from backend.app.models.user import User
from backend.app.routes import tasks as task_routes
from backend.app.services import notifications, tasks
from backend.app.services.rbac import sync_rbac
from backend.app.services.rbac.seeding import assign_role


class _Actor:
    def __init__(self, uid=1, email="a@x.com"):
        self.id = uid
        self.email = email


class TaskServiceTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def test_create_notifies_owner(self):
        db = self.Session()
        tasks.create_task(db, title="Collect GST", actor=_Actor(1), owner_id=2)
        self.assertEqual(notifications.unread_count(db, 2), 1)
        db.close()

    def test_completion_notifies_creator(self):
        db = self.Session()
        task = tasks.create_task(db, title="Review", actor=_Actor(1), owner_id=2)
        # creator=1; owner=2 completes it
        tasks.update_task(db, task, actor=_Actor(2), updates={"status": "completed"})
        self.assertIsNotNone(task.completed_at)
        # creator (1) should have a task_completed notification
        self.assertGreaterEqual(notifications.unread_count(db, 1), 1)
        db.close()

    def test_reassign_notifies_new_owner(self):
        db = self.Session()
        task = tasks.create_task(db, title="X", actor=_Actor(1), owner_id=2)
        tasks.update_task(db, task, actor=_Actor(1), updates={"owner_id": 3})
        self.assertEqual(notifications.unread_count(db, 3), 1)
        db.close()

    def test_scan_due_tasks(self):
        db = self.Session()
        past = datetime.utcnow() - timedelta(days=1)
        tasks.create_task(db, title="Overdue", actor=_Actor(1), owner_id=2, due_date=past)
        future = datetime.utcnow() + timedelta(days=5)
        tasks.create_task(db, title="Later", actor=_Actor(1), owner_id=2, due_date=future)
        notified = tasks.scan_due_tasks(db)
        self.assertEqual(notified, 1)
        db.close()

    def test_comments(self):
        db = self.Session()
        task = tasks.create_task(db, title="X", actor=_Actor(1), owner_id=2)
        tasks.add_comment(db, task, actor=_Actor(2), body="working on it")
        self.assertEqual(len(tasks.list_comments(db, task)), 1)
        db.close()


class TaskApiTest(unittest.TestCase):
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
            return u.id
        finally:
            db.close()

    def _client(self, uid):
        app = FastAPI()
        app.include_router(task_routes.router)

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
        self.assertEqual(client.post("/api/tasks", json={"title": "X"}).status_code, 403)

    def test_full_flow(self):
        uid = self._user("analyst@x.com", "credit_analyst")
        client = self._client(uid)
        created = client.post(
            "/api/tasks",
            json={"title": "Collect GST", "task_type": "collect_gst", "priority": "high", "owner_id": uid},
        )
        self.assertEqual(created.status_code, 201)
        tid = created.json()["id"]

        upd = client.patch(f"/api/tasks/{tid}", json={"status": "completed"})
        self.assertEqual(upd.json()["status"], "completed")

        client.post(f"/api/tasks/{tid}/comments", json={"body": "done"})
        detail = client.get(f"/api/tasks/{tid}").json()
        self.assertEqual(len(detail["comments"]), 1)

        mine = client.get("/api/tasks?mine=true").json()["tasks"]
        self.assertEqual(len(mine), 1)


if __name__ == "__main__":
    unittest.main()

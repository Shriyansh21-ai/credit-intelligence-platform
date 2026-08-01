""" end-to-end integration across the platform spine.

Exercises the full journey — create -> submit -> analysis -> approvals ->
covenant breach -> monitoring deterioration — and asserts that audit records and
cross-module notifications are produced along the way.
"""

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.database import Base
from backend.app.models import approval as approval_model  # noqa: F401
from backend.app.models import enterprise_assessment  # noqa: F401
from backend.app.models import rbac as rbac_model  # noqa: F401
from backend.app.models.application import Application  # noqa: F401
from backend.app.models.audit import AuditLog
from backend.app.models.covenant import Covenant  # noqa: F401
from backend.app.models.monitoring import MonitoringAlert  # noqa: F401
from backend.app.models.notification import Notification  # noqa: F401
from backend.app.models.task import Task  # noqa: F401
from backend.app.services import (
    approvals,
    covenants,
    lifecycle,
    monitoring,
    notifications,
)
from backend.app.services.approvals.workflow import ensure_default_workflow
from backend.app.services.lifecycle.state_machine import ApplicationStatus


class _Actor:
    def __init__(self, uid, email):
        self.id = uid
        self.email = email


class Phase5IntegrationTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        db = self.Session()
        ensure_default_workflow(db)
        db.close()

    def test_full_journey(self):
        db = self.Session()
        rm = _Actor(1, "rm@x.com")
        analyst = _Actor(2, "analyst@x.com")

        # 1) Create application owned by the RM, assigned to the analyst.
        app = lifecycle.create_application(db, actor=rm, company_name="Acme Ltd", assigned_to=2)
        self.assertEqual(app.status, ApplicationStatus.DRAFT)

        # 2) Walk the lifecycle forward. Each transition notifies the assignee (2).
        for target in [
            ApplicationStatus.SUBMITTED,
            ApplicationStatus.UNDER_AI_ANALYSIS,
            ApplicationStatus.ANALYST_REVIEW,
            ApplicationStatus.SENIOR_ANALYST_REVIEW,
        ]:
            lifecycle.transition(db, app, target, actor=rm)

        # Assignee received status notifications.
        self.assertGreaterEqual(notifications.unread_count(db, 2), 1)

        # 3) Senior analyst approves -> advances to credit committee.
        result = approvals.submit_decision(
            db, app, action="approve", actor=_Actor(3, "sa@x.com"), stage_key="senior_analyst"
        )
        self.assertTrue(result["status_changed"])
        self.assertEqual(app.status, ApplicationStatus.CREDIT_COMMITTEE)

        # 4) Covenant breach -> notifies the owner/assignee.
        before = notifications.unread_count(db, 2)
        cov = covenants.create_covenant(db, application_id=app.id, metric_key="dscr", threshold=1.25)
        covenants.record_measurement(db, cov, value=0.9, period="Q1", actor=rm)
        self.assertGreater(notifications.unread_count(db, 2), before)

        # 5) Monitoring deterioration -> notifies the owner/assignee.
        monitoring.add_record(db, application_id=app.id, record_type="quarterly_statement", health_score=80)
        before2 = notifications.unread_count(db, 2)
        monitoring.add_record(db, application_id=app.id, record_type="quarterly_statement", health_score=55)
        self.assertGreater(notifications.unread_count(db, 2), before2)

        # 6) The whole journey left an audit trail.
        actions = {a.action for a in db.query(AuditLog).all()}
        self.assertIn("application.create", actions)
        self.assertIn("application.transition", actions)
        self.assertIn("approval.approve", actions)
        self.assertIn("covenant.breach", actions)

        db.close()

    def test_rollback_after_journey(self):
        db = self.Session()
        rm = _Actor(1, "rm@x.com")
        app = lifecycle.create_application(db, actor=rm, company_name="Beta")
        lifecycle.transition(db, app, ApplicationStatus.SUBMITTED, actor=rm)
        lifecycle.rollback(db, app, actor=rm, reason="mistake")
        self.assertEqual(app.status, ApplicationStatus.DRAFT)
        # History has create, submit, rollback.
        self.assertEqual(len(lifecycle.get_timeline(db, app)), 3)
        db.close()


if __name__ == "__main__":
    unittest.main()

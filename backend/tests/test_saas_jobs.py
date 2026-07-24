"""Phase 8 — Background job platform (M6)."""

import unittest
import warnings

warnings.filterwarnings("ignore")

from datetime import datetime, timedelta

from backend.app.services.saas import jobs
from backend.tests._saas_helpers import fresh_session, seed_all


@jobs.register_handler("test.echo")
def _echo(db, job, ctx):
    ctx.progress(50.0, "halfway")
    return {"echoed": job.payload.get("msg")}


@jobs.register_handler("test.boom")
def _boom(db, job, ctx):
    raise RuntimeError("kaboom")


class JobsTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()
        seed_all(self.db)

    def tearDown(self):
        self.db.close()

    def test_enqueue_and_run(self):
        job = jobs.enqueue(self.db, "test.echo", {"msg": "hi"})
        self.assertEqual(job.status, "queued")
        jobs.run_pending(self.db)
        self.db.refresh(job)
        self.assertEqual(job.status, "succeeded")
        self.assertEqual(job.result["echoed"], "hi")
        self.assertEqual(job.progress, 100.0)

    def test_priority_ordering(self):
        low = jobs.enqueue(self.db, "test.echo", {"msg": "low"}, priority=9)
        high = jobs.enqueue(self.db, "test.echo", {"msg": "high"}, priority=1)
        first = jobs.run_next(self.db)
        self.assertEqual(first.id, high.id)

    def test_retry_then_dead_letter(self):
        job = jobs.enqueue(self.db, "test.boom", {}, max_attempts=2)
        jobs.run_next(self.db)  # attempt 1 -> retrying
        self.db.refresh(job)
        self.assertEqual(job.status, "retrying")
        # make it available now (bypass backoff)
        job.available_at = datetime.utcnow() - timedelta(seconds=1)
        self.db.commit()
        jobs.run_next(self.db)  # attempt 2 -> dead
        self.db.refresh(job)
        self.assertEqual(job.status, "dead")
        self.assertEqual(len(jobs.dead_letters(self.db)), 1)

    def test_requeue_dead(self):
        job = jobs.enqueue(self.db, "test.boom", {}, max_attempts=1)
        jobs.run_next(self.db)
        self.db.refresh(job)
        self.assertEqual(job.status, "dead")
        jobs.requeue_dead(self.db, job.id)
        self.db.refresh(job)
        self.assertEqual(job.status, "queued")
        self.assertEqual(job.attempts, 0)

    def test_cancel_queued(self):
        job = jobs.enqueue(self.db, "test.echo", {})
        jobs.cancel_job(self.db, job.id)
        self.db.refresh(job)
        self.assertEqual(job.status, "canceled")
        # canceled jobs are not run
        jobs.run_pending(self.db)
        self.db.refresh(job)
        self.assertEqual(job.status, "canceled")

    def test_idempotency_key(self):
        j1 = jobs.enqueue(self.db, "test.echo", {}, idempotency_key="k1")
        j2 = jobs.enqueue(self.db, "test.echo", {}, idempotency_key="k1")
        self.assertEqual(j1.id, j2.id)

    def test_backoff_delays_retry(self):
        job = jobs.enqueue(self.db, "test.boom", {}, max_attempts=3)
        jobs.run_next(self.db)
        self.db.refresh(job)
        # after first failure, available_at is in the future (backoff)
        self.assertGreater(job.available_at, datetime.utcnow())
        # run_pending should skip it (not yet available)
        processed = jobs.run_pending(self.db)
        self.assertEqual(processed, [])

    def test_no_handler_goes_dead(self):
        job = jobs.enqueue(self.db, "unregistered.type", {}, max_attempts=1)
        jobs.run_next(self.db)
        self.db.refresh(job)
        self.assertEqual(job.status, "dead")

    def test_queue_isolation(self):
        jobs.enqueue(self.db, "test.echo", {}, queue="high")
        jobs.enqueue(self.db, "test.echo", {}, queue="low")
        processed = jobs.run_pending(self.db, queue="high")
        self.assertEqual(len(processed), 1)

    def test_recurring_schedule_tick(self):
        sched = jobs.create_schedule(self.db, "nightly", "test.echo", 3600)
        enq = jobs.tick_schedules(self.db)
        self.assertEqual(len(enq), 1)
        self.db.refresh(sched)
        self.assertGreater(sched.next_run_at, datetime.utcnow())
        # not due again immediately
        self.assertEqual(jobs.tick_schedules(self.db), [])

    def test_builtin_noop_handler(self):
        job = jobs.enqueue(self.db, "noop", {"x": 1})
        jobs.run_pending(self.db)
        self.db.refresh(job)
        self.assertEqual(job.status, "succeeded")


if __name__ == "__main__":
    unittest.main()

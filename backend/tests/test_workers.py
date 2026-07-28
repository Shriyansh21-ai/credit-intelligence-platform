"""Phase 11, Milestone 2 — worker & scheduler process tests.

Exercises the shared poll-loop runtime, the liveness heartbeat/healthcheck, and
the worker/scheduler ticks against a throwaway in-memory database using the
existing SaaS job primitives.
"""

import os
import tempfile
import time
import unittest
import warnings

warnings.filterwarnings("ignore")

from backend.app.services.saas import jobs
from backend.app.workers import healthcheck, scheduler, worker
from backend.app.workers.runtime import GracefulShutdown, run_loop
from backend.tests._saas_helpers import fresh_session, seed_all


@jobs.register_handler("workers.test.echo")
def _echo(db, job, ctx):
    return {"echoed": job.payload.get("msg")}


class RunLoopTest(unittest.TestCase):
    def setUp(self):
        self._hb = os.path.join(tempfile.gettempdir(), f"hb-{os.getpid()}-{id(self)}")

    def tearDown(self):
        try:
            os.remove(self._hb)
        except OSError:
            pass

    def _factory(self):
        # A session factory that returns a lightweight throwaway session.
        engine, Session = fresh_session()
        return Session()

    def test_runs_bounded_iterations(self):
        calls = {"n": 0}

        def tick(db):
            calls["n"] += 1
            return 1

        total = run_loop(
            "t", tick, interval=0.001, shutdown=GracefulShutdown(),
            max_iterations=3, session_factory=self._factory,
            heartbeat_file=self._hb,
        )
        self.assertEqual(calls["n"], 3)
        self.assertEqual(total, 3)

    def test_stops_when_shutdown_requested(self):
        sd = GracefulShutdown()

        def tick(db):
            sd._event.set()  # request shutdown from within the first tick
            return 0

        total = run_loop("t", tick, interval=0.001, shutdown=sd,
                         session_factory=self._factory, heartbeat_file=self._hb)
        self.assertEqual(total, 0)

    def test_isolates_tick_exceptions(self):
        state = {"n": 0}

        def tick(db):
            state["n"] += 1
            raise RuntimeError("boom")

        # Must not propagate; loop completes all iterations despite failures.
        total = run_loop("t", tick, interval=0.001, shutdown=GracefulShutdown(),
                         max_iterations=2, session_factory=self._factory,
                         heartbeat_file=self._hb)
        self.assertEqual(state["n"], 2)
        self.assertEqual(total, 0)

    def test_writes_heartbeat(self):
        run_loop("t", lambda db: 0, interval=0.001, shutdown=GracefulShutdown(),
                 max_iterations=1, session_factory=self._factory,
                 heartbeat_file=self._hb)
        self.assertTrue(os.path.exists(self._hb))
        self.assertTrue(healthcheck.check(max_age=60, path=self._hb))


class HealthcheckTest(unittest.TestCase):
    def test_missing_file_is_unhealthy(self):
        self.assertFalse(healthcheck.check(max_age=60, path="/nonexistent/hb"))

    def test_fresh_is_healthy(self):
        path = os.path.join(tempfile.gettempdir(), f"hb-fresh-{os.getpid()}")
        with open(path, "w") as fh:
            fh.write(str(time.time()))
        try:
            self.assertTrue(healthcheck.check(max_age=60, path=path))
            self.assertEqual(healthcheck.main(["--max-age", "60", "--path", path]), 0)
        finally:
            os.remove(path)

    def test_stale_is_unhealthy(self):
        path = os.path.join(tempfile.gettempdir(), f"hb-stale-{os.getpid()}")
        with open(path, "w") as fh:
            fh.write(str(time.time() - 10_000))
        try:
            self.assertFalse(healthcheck.check(max_age=60, path=path))
            self.assertEqual(healthcheck.main(["--max-age", "60", "--path", path]), 1)
        finally:
            os.remove(path)


class WorkerTickTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()
        seed_all(self.db)

    def tearDown(self):
        self.db.close()

    def test_worker_tick_drains_queue(self):
        jobs.enqueue(self.db, "workers.test.echo", {"msg": "hi"})
        processed = worker._tick(self.db)
        self.assertEqual(processed, 1)
        # Idempotent: nothing left to do on the next pass.
        self.assertEqual(worker._tick(self.db), 0)

    def test_scheduler_tick_enqueues_due_schedule(self):
        jobs.create_schedule(self.db, "nightly", "workers.test.echo",
                             interval_seconds=3600, payload={"msg": "tick"})
        actions = scheduler._tick(self.db)
        self.assertGreaterEqual(actions, 1)
        # The schedule's next run has advanced, so an immediate re-tick is a no-op
        # for that schedule.
        self.assertEqual(len(jobs.due_schedules(self.db)), 0)


if __name__ == "__main__":
    unittest.main()

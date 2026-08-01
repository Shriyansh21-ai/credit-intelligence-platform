""" performance engineering + pagination tests."""

import unittest

from sqlalchemy import Column, Integer, String, create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core import pagination, performance
from backend.app.services.saas import observability as obs

Base = declarative_base()


class Widget(Base):
    __tablename__ = "perf_widgets"
    id = Column(Integer, primary_key=True)
    name = Column(String)


def _session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine)()


class BenchmarkTest(unittest.TestCase):
    def test_benchmark_stats(self):
        res = performance.benchmark(lambda: sum(range(100)), iterations=20, warmup=2, name="sum")
        d = res.as_dict()
        self.assertEqual(d["name"], "sum")
        self.assertEqual(d["iterations"], 20)
        self.assertGreaterEqual(d["max_ms"], d["min_ms"])
        self.assertGreaterEqual(d["p95_ms"], d["p50_ms"])


class SlowQueryAnalysisTest(unittest.TestCase):
    def setUp(self):
        obs._slow_queries.clear()

    def test_analyze_and_recommend(self):
        # Seed the slow-query buffer directly with recognisable patterns.
        for i in range(3):
            obs.record_query(
                f"SELECT * FROM applications WHERE tenant_id = {i} AND status = 'open'", 250.0
            )
        report = performance.analyze_slow_queries()
        self.assertEqual(report.count, 3)
        self.assertTrue(report.by_pattern)
        recs = performance.recommend_indexes(report.by_pattern, min_occurrences=1)
        self.assertTrue(recs)
        rec = recs[0]
        self.assertEqual(rec["table"], "applications")
        self.assertIn("tenant_id", rec["columns"])
        self.assertIn("CREATE INDEX", rec["ddl"])


class QueryProfilerTest(unittest.TestCase):
    def test_n_plus_one_detection(self):
        engine, session = _session()
        session.add_all([Widget(name=f"w{i}") for i in range(5)])
        session.commit()

        prof = performance.QueryProfiler()
        self.assertTrue(prof.attach(engine))

        with performance.profiling_scope() as stats:
            for i in range(12):
                session.execute(text("SELECT * FROM perf_widgets WHERE id = :i"), {"i": i}).all()
        report = stats()
        self.assertGreaterEqual(report.total_queries, 12)
        self.assertTrue(report.n_plus_one, "expected an N+1 pattern to be flagged")

    def test_attach_is_idempotent(self):
        engine, _ = _session()
        prof = performance.QueryProfiler()
        self.assertTrue(prof.attach(engine))
        self.assertFalse(prof.attach(engine))


class PaginationTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.session = _session()
        self.session.add_all([Widget(name=f"w{i:03d}") for i in range(125)])
        self.session.commit()

    def test_clamp_page_size(self):
        self.assertEqual(pagination.clamp_page_size(None), pagination.DEFAULT_PAGE_SIZE)
        self.assertEqual(pagination.clamp_page_size(0), pagination.DEFAULT_PAGE_SIZE)
        self.assertEqual(pagination.clamp_page_size(10_000), pagination.MAX_PAGE_SIZE)
        self.assertEqual(pagination.clamp_page_size(25), 25)

    def test_offset_pagination(self):
        q = self.session.query(Widget).order_by(Widget.id)
        page = pagination.paginate(q, page=2, page_size=50)
        self.assertEqual(page.total, 125)
        self.assertEqual(len(page.items), 50)
        self.assertEqual(page.page, 2)
        self.assertEqual(page.pages, 3)
        self.assertTrue(page.has_next)
        self.assertTrue(page.has_prev)
        d = page.as_dict()
        self.assertEqual(d["pagination"]["total"], 125)

    def test_keyset_pagination(self):
        q = self.session.query(Widget)
        first = pagination.keyset_paginate(q, order_column=Widget.id, page_size=40)
        self.assertEqual(len(first.items), 40)
        self.assertTrue(first.has_next)
        self.assertIsNotNone(first.next_cursor)
        second = pagination.keyset_paginate(
            q, order_column=Widget.id, page_size=40, after=first.next_cursor
        )
        self.assertEqual(second.items[0].id, first.items[-1].id + 1)

    def test_stream_ndjson(self):
        import anyio

        rows = [{"id": i} for i in range(5)]
        resp = pagination.stream_ndjson(rows)

        async def _collect():
            chunks = []
            async for c in resp.body_iterator:
                chunks.append(c if isinstance(c, bytes) else c.encode())
            return b"".join(chunks)

        body = anyio.run(_collect).decode()
        self.assertEqual(body.strip().count("\n"), 4)
        self.assertIn('"id": 0', body)


if __name__ == "__main__":
    unittest.main()

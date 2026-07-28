"""Phase 11, M14 — expanded performance, pagination & API-platform tests."""

import unittest

from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core import api_versioning as ver
from backend.app.core import pagination, performance, webhooks
from backend.app.services.saas import observability as obs

Base = declarative_base()


class Row(Base):
    __tablename__ = "m14_rows"
    id = Column(Integer, primary_key=True)
    name = Column(String)


def _session(n=0):
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    if n:
        s.add_all([Row(name=f"r{i}") for i in range(n)])
        s.commit()
    return s


class NormalizeTest(unittest.TestCase):
    def test_numbers_and_strings_collapse(self):
        a = performance._normalize_sql("SELECT * FROM t WHERE id = 5 AND s = 'x'")
        b = performance._normalize_sql("SELECT * FROM t WHERE id = 9 AND s = 'y'")
        self.assertEqual(a, b)

    def test_in_clause_collapses(self):
        n = performance._normalize_sql("SELECT * FROM t WHERE id IN (1, 2, 3)")
        self.assertIn("in (?)", n)

    def test_whitespace_normalized(self):
        n = performance._normalize_sql("SELECT   *\n  FROM   t")
        self.assertEqual(n, "select * from t")


class SlowQueryExtraTest(unittest.TestCase):
    def setUp(self):
        obs._slow_queries.clear()

    def test_empty_report(self):
        rep = performance.analyze_slow_queries()
        self.assertEqual(rep.count, 0)
        self.assertEqual(rep.by_pattern, [])

    def test_recommend_respects_min_occurrences(self):
        obs.record_query("SELECT * FROM t WHERE a = 1", 300)
        recs = performance.recommend_indexes(min_occurrences=2)
        self.assertEqual(recs, [])  # only one occurrence

    def test_join_columns_recommended(self):
        pat = [
            {
                "pattern": "select * from a join b on a.bid = b.id where a.x = ?",
                "occurrences": 3,
                "max_ms": 500,
            }
        ]
        recs = performance.recommend_indexes(pat, min_occurrences=1)
        self.assertTrue(recs)


class BenchmarkExtraTest(unittest.TestCase):
    def test_single_iteration(self):
        res = performance.benchmark(lambda: 1, iterations=1, warmup=0)
        self.assertEqual(res.iterations, 1)

    def test_percentile_helper(self):
        self.assertEqual(performance._percentile([], 50), 0.0)
        self.assertEqual(performance._percentile([1.0, 2.0, 3.0, 4.0], 50), 3.0)


class PaginationExtraTest(unittest.TestCase):
    def test_last_page_partial(self):
        s = _session(125)
        page = pagination.paginate(s.query(Row).order_by(Row.id), page=3, page_size=50)
        self.assertEqual(len(page.items), 25)
        self.assertFalse(page.has_next)
        self.assertTrue(page.has_prev)

    def test_empty_result(self):
        s = _session(0)
        page = pagination.paginate(s.query(Row), page=1, page_size=10)
        self.assertEqual(page.total, 0)
        self.assertEqual(page.pages, 0)
        self.assertFalse(page.has_next)

    def test_keyset_descending(self):
        s = _session(30)
        ks = pagination.keyset_paginate(
            s.query(Row), order_column=Row.id, page_size=10, descending=True
        )
        ids = [r.id for r in ks.items]
        self.assertEqual(ids, sorted(ids, reverse=True))

    def test_keyset_last_page_no_next(self):
        s = _session(10)
        ks = pagination.keyset_paginate(s.query(Row), order_column=Row.id, page_size=50)
        self.assertFalse(ks.has_next)
        self.assertIsNone(ks.next_cursor)

    def test_page_as_dict_shape(self):
        s = _session(5)
        d = pagination.paginate(s.query(Row), page=1, page_size=10).as_dict()
        self.assertIn("items", d)
        self.assertEqual(
            set(d["pagination"]), {"total", "page", "page_size", "pages", "has_next", "has_prev"}
        )


class VersioningExtraTest(unittest.TestCase):
    def test_sunset_status_is_deprecated(self):
        v = ver.APIVersion("v0", status=ver.VersionStatus.SUNSET)
        self.assertTrue(v.is_deprecated())

    def test_registry_all_and_get(self):
        reg = ver.VersionRegistry()
        reg.register(ver.APIVersion("v1"), current=True)
        self.assertIn("v1", reg.all())
        self.assertIsNone(reg.get("v9"))

    def test_extract_ignores_non_api_paths(self):
        reg = ver.VersionRegistry()
        reg.register(ver.APIVersion("v1"))
        self.assertIsNone(reg.extract_version("/v1/x"))  # no /api/ prefix


class WebhookExtraTest(unittest.TestCase):
    def test_bytes_body_signing(self):
        header = webhooks.sign("s", b"raw-bytes", timestamp=1000)
        self.assertTrue(webhooks.verify("s", b"raw-bytes", header, now=1000))

    def test_string_body_signing(self):
        header = webhooks.sign("s", "plain", timestamp=1000)
        self.assertTrue(webhooks.verify("s", "plain", header, now=1000))

    def test_retry_schedule_length(self):
        p = webhooks.RetryPolicy(max_attempts=3)
        self.assertEqual(len(p.schedule()), 3)

    def test_dispatcher_records_status_codes(self):
        seq = iter([500, 503, 200])
        d = webhooks.WebhookDispatcher(
            lambda u, h, b: next(seq),
            policy=webhooks.RetryPolicy(max_attempts=5),
            sleep=lambda s: None,
            clock=lambda: 1000,
        )
        res = d.deliver("u", "s", "e", {})
        self.assertTrue(res.delivered)
        self.assertEqual([a.status_code for a in res.attempts], [500, 503, 200])

    def test_future_timestamp_within_tolerance(self):
        header = webhooks.sign("s", {}, timestamp=1000)
        self.assertTrue(webhooks.verify("s", {}, header, now=900))  # 100s future, within 300


if __name__ == "__main__":
    unittest.main()

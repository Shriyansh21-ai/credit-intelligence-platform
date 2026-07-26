import unittest

from backend.tests._banking_os_helpers import (
    client_for, fresh_session, make_user, seed_rbac,
)
from backend.app.services.banking_os import llm_router


class LLMRouterServiceTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def _fleet(self):
        llm_router.register_provider(self.db, name="gpt", kind="openai", model="gpt-x",
                                     priority=10, cost_per_1k_input=0.01, cost_per_1k_output=0.03,
                                     avg_latency_ms=800, quality_score=0.9, capabilities=["chat", "json"])
        llm_router.register_provider(self.db, name="claude", kind="anthropic", model="opus",
                                     priority=5, cost_per_1k_input=0.015, cost_per_1k_output=0.075,
                                     avg_latency_ms=1200, quality_score=0.95, capabilities=["chat", "json", "long_context"])
        llm_router.register_provider(self.db, name="ollama", kind="ollama", model="llama3",
                                     priority=50, cost_per_1k_input=0.0, cost_per_1k_output=0.0,
                                     avg_latency_ms=400, quality_score=0.55, capabilities=["chat"])

    def test_unknown_kind_rejected(self):
        with self.assertRaises(ValueError):
            llm_router.register_provider(self.db, name="x", kind="not-real")

    def test_duplicate_name_rejected(self):
        llm_router.register_provider(self.db, name="dup", kind="local")
        with self.assertRaises(ValueError):
            llm_router.register_provider(self.db, name="dup", kind="openai")

    def test_route_cost_prefers_cheapest(self):
        self._fleet()
        out = llm_router.route(self.db, strategy="cost")
        # ollama + local are free; cheapest by (cost, priority) → local(200) vs ollama(50) → ollama
        self.assertIn(out["chosen"]["name"], ("ollama", "local-deterministic"))
        self.assertEqual(out["chosen"]["est_cost"], 0.0)

    def test_route_quality_prefers_best(self):
        self._fleet()
        out = llm_router.route(self.db, strategy="quality")
        self.assertEqual(out["chosen"]["name"], "claude")

    def test_route_latency_prefers_fastest(self):
        self._fleet()
        out = llm_router.route(self.db, strategy="latency")
        # local(5ms) is fastest of all once auto-registered
        self.assertEqual(out["chosen"]["name"], "local-deterministic")

    def test_capability_filter(self):
        self._fleet()
        out = llm_router.route(self.db, strategy="quality", capabilities=["long_context"])
        self.assertEqual(out["chosen"]["name"], "claude")

    def test_no_eligible_provider_raises(self):
        self._fleet()
        with self.assertRaises(ValueError):
            llm_router.route(self.db, capabilities=["vision"])

    def test_local_always_available(self):
        # No providers registered → local is auto-created and chosen.
        out = llm_router.route(self.db, strategy="balanced")
        self.assertEqual(out["chosen"]["kind"], "local")

    def test_complete_logs_invocation(self):
        self._fleet()
        res = llm_router.complete(self.db, prompt="Explain the current ratio", strategy="quality",
                                  prompt_ref="memo-1")
        self.assertEqual(res["provider"], "claude")
        self.assertEqual(res["kind"], "anthropic")
        self.assertIn("anthropic", res["text"].lower())
        self.assertGreater(res["tokens_in"], 0)
        self.assertIn("confidence", res)
        an = llm_router.analytics(self.db)
        self.assertEqual(an["total_invocations"], 1)
        self.assertIn("claude", an["by_provider"])

    def test_disabled_provider_skipped(self):
        self._fleet()
        p = [x for x in llm_router.list_providers(self.db) if x.name == "claude"][0]
        llm_router.update_provider(self.db, p.id, enabled=False)
        out = llm_router.route(self.db, strategy="quality")
        self.assertNotEqual(out["chosen"]["name"], "claude")


class LLMApiTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        db = self.Session()
        seed_rbac(db)
        db.close()
        self.risk = make_user(self.Session, "risk@l.test", "risk_manager")
        self.analyst = make_user(self.Session, "a@l.test", "credit_analyst")

    def test_register_and_route(self):
        c = client_for(self.Session, self.risk)
        r = c.post("/api/os/llm/providers", json={"name": "gpt", "kind": "openai",
                   "quality_score": 0.9, "avg_latency_ms": 800, "capabilities": ["chat"]})
        self.assertEqual(r.status_code, 200, r.text)
        r = c.post("/api/os/llm/route", json={"strategy": "quality"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn("chosen", r.json())

    def test_analyst_cannot_manage_providers(self):
        c = client_for(self.Session, self.analyst)
        # credit_analyst has llm.view but not llm.manage → registering a provider is 403
        r = c.post("/api/os/llm/providers", json={"name": "x", "kind": "openai"})
        self.assertEqual(r.status_code, 403)


if __name__ == "__main__":
    unittest.main()

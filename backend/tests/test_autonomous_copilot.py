import unittest

from backend.tests._autonomous_helpers import fresh_session, seed_assessment
from backend.app.services.autonomous import copilot, llm


class LLMProviderTest(unittest.TestCase):
    def test_local_provider_grounded_only(self):
        prov = llm.LocalDeterministicProvider()
        out = prov.compose(question="q", intent="explain_assessment", grounding={
            "headline": "H", "facts": [{"label": "PD", "value": "5%"}],
            "recommended_actions": ["do x"]})
        self.assertIn("H", out)
        self.assertIn("PD", out)
        self.assertIn("do x", out)

    def test_local_provider_empty(self):
        out = llm.LocalDeterministicProvider().compose(question="q", intent="x", grounding={})
        self.assertIn("could not find", out.lower())

    def test_get_provider_defaults_local(self):
        self.assertEqual(llm.get_provider().name, "local")

    def test_claude_degrades_when_unavailable(self):
        # No API key in test env -> not available -> factory returns local
        prov = llm.get_provider("claude")
        self.assertEqual(prov.name, "local")

    def test_provider_status(self):
        st = llm.provider_status()
        self.assertTrue(st["local_available"])
        self.assertIn("active", st)


class CopilotTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()
        seed_assessment(self.db, company_name="Acme", industry="textile",
                        probability_of_default=0.08, enterprise_credit_score=610,
                        risk_rating="BB")

    def tearDown(self):
        self.db.close()

    def test_detect_intent(self):
        self.assertEqual(copilot.detect_intent("explain the SHAP drivers"), "explain_shap")
        self.assertEqual(copilot.detect_intent("is there any fraud?"), "explain_fraud")
        self.assertEqual(copilot.detect_intent("summarize the financials"), "summarize_financials")
        self.assertEqual(copilot.detect_intent("what should I do next"), "next_actions")
        self.assertEqual(copilot.detect_intent("where do I find stress testing"), "navigate")

    def test_ask_creates_conversation(self):
        res = copilot.ask(self.db, "Explain the assessment for Acme", company_ref="Acme")
        self.assertIn("conversation_id", res)
        self.assertEqual(res["provider"], "local")
        self.assertIn("Acme", res["answer"])

    def test_ask_grounded_facts(self):
        res = copilot.ask(self.db, "What is the credit rating?", company_ref="Acme")
        # answer only contains grounded values
        self.assertIn("BB", res["answer"])
        self.assertGreater(len(res["grounding"]["facts"]), 0)

    def test_ask_persists_messages(self):
        res = copilot.ask(self.db, "Give exec summary", company_ref="Acme")
        msgs = copilot.get_messages(self.db, res["conversation_id"])
        self.assertEqual(len(msgs), 2)  # user + assistant
        self.assertEqual(msgs[0].role, "user")
        self.assertEqual(msgs[1].role, "assistant")

    def test_ask_continues_conversation(self):
        r1 = copilot.ask(self.db, "hi", company_ref="Acme")
        r2 = copilot.ask(self.db, "more", conversation_id=r1["conversation_id"])
        self.assertEqual(r1["conversation_id"], r2["conversation_id"])
        self.assertEqual(len(copilot.get_messages(self.db, r1["conversation_id"])), 4)

    def test_navigate_intent(self):
        res = copilot.ask(self.db, "where is the stress testing page", company_ref="Acme")
        self.assertEqual(res["intent"], "navigate")
        self.assertIn("/stress", res["answer"])

    def test_next_actions_grounded(self):
        res = copilot.ask(self.db, "what should I do next for Acme", company_ref="Acme")
        self.assertEqual(res["intent"], "next_actions")

    def test_missing_company_is_honest(self):
        res = copilot.ask(self.db, "explain assessment", company_ref="DoesNotExist")
        self.assertIn("No assessment", res["answer"])


if __name__ == "__main__":
    unittest.main()

import unittest

from backend.tests._autonomous_helpers import fresh_session, seed_assessment, seed_portfolio
from backend.app.services.autonomous import data_access


class DataAccessTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def test_get_assessment(self):
        a = seed_assessment(self.db, company_name="A")
        self.assertEqual(data_access.get_assessment(self.db, a.id).id, a.id)
        self.assertIsNone(data_access.get_assessment(self.db, 9999))

    def test_latest_for_company_case_insensitive(self):
        seed_assessment(self.db, company_name="Acme")
        self.assertIsNotNone(data_access.latest_assessment_for_company(self.db, "acme"))
        self.assertIsNone(data_access.latest_assessment_for_company(self.db, "nope"))

    def test_latest_per_company_dedups(self):
        seed_assessment(self.db, company_name="Dup")
        seed_assessment(self.db, company_name="Dup")
        seed_assessment(self.db, company_name="Other")
        latest = data_access.latest_per_company(self.db)
        names = {a.company_name for a in latest}
        self.assertEqual(names, {"Dup", "Other"})

    def test_resolve_prefers_id(self):
        a = seed_assessment(self.db, company_name="R")
        self.assertEqual(data_access.resolve(self.db, assessment_id=a.id).id, a.id)
        self.assertEqual(data_access.resolve(self.db, company_ref="R").id, a.id)

    def test_profile_none(self):
        self.assertIsNone(data_access.profile(None))

    def test_profile_fields(self):
        a = seed_assessment(self.db, company_name="P", industry="textile",
                            probability_of_default=0.1, risk_rating="BB",
                            recommended_loan_amount=5000000)
        p = data_access.profile(a)
        self.assertEqual(p["company_ref"], "P")
        self.assertEqual(p["industry"], "textile")
        self.assertEqual(p["pd"], 0.1)
        self.assertEqual(p["exposure"], 5000000)
        self.assertIn("health", p)

    def test_profile_pd_calibrated_when_missing(self):
        a = seed_assessment(self.db, company_name="NoPD", enterprise_credit_score=500)
        a.probability_of_default = None  # in-memory only; column is NOT NULL
        p = data_access.profile(a)
        self.assertIsNotNone(p["pd"])

    def test_portfolio_profiles(self):
        seed_portfolio(self.db)
        profs = data_access.portfolio_profiles(self.db)
        self.assertEqual(len(profs), 3)


if __name__ == "__main__":
    unittest.main()

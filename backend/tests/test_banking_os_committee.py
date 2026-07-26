import unittest

from backend.tests._banking_os_helpers import (
    client_for, fresh_session, make_user, seed_rbac,
)
from backend.app.services.banking_os import committee


class CommitteeServiceTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        self.db = self.Session()

    def tearDown(self):
        self.db.close()

    def _committee_with_item(self, quorum=2):
        c = committee.create_committee(self.db, name="Credit Committee", quorum=quorum,
                                       members=[{"user_id": 1, "name": "A"}, {"user_id": 2, "name": "B"}])
        m = committee.create_meeting(self.db, committee_id=c.id, title="Weekly")
        committee.open_meeting(self.db, m.id)
        item = committee.add_agenda_item(self.db, meeting_id=m.id, title="Acme loan",
                                         subject_ref="Acme", amount=1_000_000)
        return c, m, item

    def test_meeting_requires_committee(self):
        with self.assertRaises(ValueError):
            committee.create_meeting(self.db, committee_id=999, title="x")

    def test_vote_validation(self):
        _, _, item = self._committee_with_item()
        with self.assertRaises(ValueError):
            committee.cast_vote(self.db, item.id, vote="maybe")

    def test_quorum_blocks_finalize(self):
        _, _, item = self._committee_with_item(quorum=2)
        committee.cast_vote(self.db, item.id, vote="approve", voter_user_id=1)
        with self.assertRaises(ValueError):
            committee.finalize_decision(self.db, item.id)

    def test_weighted_majority_approves(self):
        _, _, item = self._committee_with_item(quorum=2)
        committee.cast_vote(self.db, item.id, vote="approve", voter_user_id=1, weight=1.0)
        committee.cast_vote(self.db, item.id, vote="approve", voter_user_id=2, weight=2.0)
        committee.cast_vote(self.db, item.id, vote="reject", voter_user_id=3, weight=0.5)
        t = committee.tally(self.db, item.id)
        self.assertTrue(t["quorum_met"])
        self.assertEqual(t["recommendation"], "approve")
        out = committee.finalize_decision(self.db, item.id)
        self.assertEqual(out["decision"], "approve")

    def test_reject_majority(self):
        _, _, item = self._committee_with_item(quorum=1)
        committee.cast_vote(self.db, item.id, vote="reject", voter_user_id=1)
        out = committee.finalize_decision(self.db, item.id)
        self.assertEqual(out["decision"], "reject")

    def test_revote_updates_in_place(self):
        _, _, item = self._committee_with_item(quorum=1)
        committee.cast_vote(self.db, item.id, vote="approve", voter_user_id=1)
        committee.cast_vote(self.db, item.id, vote="reject", voter_user_id=1)
        t = committee.tally(self.db, item.id)
        self.assertEqual(t["voters"], 1)
        self.assertEqual(t["counts"]["reject"], 1)
        self.assertEqual(t["counts"]["approve"], 0)

    def test_signatures_present(self):
        _, _, item = self._committee_with_item(quorum=1)
        res = committee.cast_vote(self.db, item.id, vote="approve", voter_user_id=1)
        self.assertTrue(res["signature"])
        self.assertTrue(res["tally"]["signatures_valid"])

    def test_closed_meeting_blocks_votes(self):
        _, m, item = self._committee_with_item(quorum=1)
        committee.close_meeting(self.db, m.id)
        with self.assertRaises(ValueError):
            committee.cast_vote(self.db, item.id, vote="approve", voter_user_id=1)

    def test_close_generates_minutes(self):
        _, m, item = self._committee_with_item(quorum=1)
        committee.mark_attendance(self.db, m.id, user_id=1, name="A", present=True)
        detail = committee.close_meeting(self.db, m.id)
        self.assertIn("Minutes", detail["minutes"])
        self.assertEqual(detail["status"], "closed")

    def test_attendance_idempotent(self):
        _, m, _ = self._committee_with_item(quorum=1)
        committee.mark_attendance(self.db, m.id, user_id=1, name="A", present=True)
        committee.mark_attendance(self.db, m.id, user_id=1, name="A", present=False)
        m2 = committee.get_meeting(self.db, m.id)
        present = [a for a in m2.attendees if a["user_id"] == 1]
        self.assertEqual(len(present), 1)
        self.assertFalse(present[0]["present"])

    def test_analytics(self):
        _, _, item = self._committee_with_item(quorum=1)
        committee.cast_vote(self.db, item.id, vote="approve", voter_user_id=1)
        committee.finalize_decision(self.db, item.id)
        a = committee.analytics(self.db)
        self.assertEqual(a["committees"], 1)
        self.assertEqual(a["decided"], 1)
        self.assertEqual(a["by_decision"].get("approve"), 1)
        self.assertEqual(a["approval_rate"], 1.0)


class CommitteeApiTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = fresh_session()
        db = self.Session()
        seed_rbac(db)
        db.close()
        self.admin = make_user(self.Session, "admin@c.test", "administrator")
        self.analyst = make_user(self.Session, "analyst@c.test", "credit_analyst")

    def test_full_committee_flow(self):
        c = client_for(self.Session, self.admin)
        cid = c.post("/api/os/committee/committees",
                     json={"name": "CC", "quorum": 1}).json()["id"]
        mid = c.post("/api/os/committee/meetings",
                     json={"committee_id": cid, "title": "M1"}).json()["id"]
        c.post(f"/api/os/committee/meetings/{mid}/open")
        iid = c.post("/api/os/committee/agenda",
                     json={"meeting_id": mid, "title": "Acme", "subject_ref": "Acme"}).json()["id"]
        r = c.post(f"/api/os/committee/agenda/{iid}/vote", json={"vote": "approve"})
        self.assertEqual(r.status_code, 200, r.text)
        r = c.post(f"/api/os/committee/agenda/{iid}/decide")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["decision"], "approve")
        detail = c.get(f"/api/os/committee/meetings/{mid}").json()
        self.assertEqual(len(detail["agenda"]), 1)

    def test_analyst_can_vote_but_not_manage(self):
        admin = client_for(self.Session, self.admin)
        cid = admin.post("/api/os/committee/committees", json={"name": "CC", "quorum": 1}).json()["id"]
        mid = admin.post("/api/os/committee/meetings", json={"committee_id": cid, "title": "M"}).json()["id"]
        admin.post(f"/api/os/committee/meetings/{mid}/open")
        iid = admin.post("/api/os/committee/agenda", json={"meeting_id": mid, "title": "X"}).json()["id"]
        analyst = client_for(self.Session, self.analyst)
        self.assertEqual(analyst.post(f"/api/os/committee/agenda/{iid}/vote",
                                      json={"vote": "approve"}).status_code, 200)
        # cannot create a committee
        self.assertEqual(analyst.post("/api/os/committee/committees",
                                      json={"name": "Y", "quorum": 1}).status_code, 403)


if __name__ == "__main__":
    unittest.main()

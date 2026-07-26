import unittest

from backend.app.services.banking_os import common


class CommonHelpersTest(unittest.TestCase):
    def test_tokenize_lowercases_and_drops_stopwords(self):
        toks = common.tokenize("The Quick Brown-Fox, and a DOG!")
        self.assertIn("quick", toks)
        self.assertIn("brown", toks)
        self.assertIn("fox", toks)
        self.assertNotIn("the", toks)
        self.assertNotIn("and", toks)

    def test_tokenize_min_len(self):
        # single-char tokens are dropped by the default min_len=2
        self.assertEqual(common.tokenize("a I o k"), [])
        self.assertEqual(common.tokenize("gst filing"), ["gst", "filing"])

    def test_tokenize_empty(self):
        self.assertEqual(common.tokenize(None), [])
        self.assertEqual(common.tokenize(""), [])

    def test_term_frequencies(self):
        tf = common.term_frequencies(["a", "b", "a", "a"])
        self.assertEqual(tf["a"], 3)
        self.assertEqual(tf["b"], 1)

    def test_bm25_idf_bounds(self):
        self.assertEqual(common.bm25_idf(0, 0), 0.0)
        self.assertEqual(common.bm25_idf(10, 0), 0.0)
        self.assertGreater(common.bm25_idf(100, 1), common.bm25_idf(100, 50))

    def test_signature_is_deterministic(self):
        a = common.signature(1, "x", None, 2)
        b = common.signature(1, "x", None, 2)
        c = common.signature(1, "x", None, 3)
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertEqual(len(a), 16)

    def test_content_hash_stable_across_key_order(self):
        h1 = common.content_hash({"a": 1, "b": 2})
        h2 = common.content_hash({"b": 2, "a": 1})
        self.assertEqual(h1, h2)

    def test_confidence_from_evidence_bounded(self):
        self.assertEqual(common.confidence_from_evidence(0), 0.5)
        self.assertLessEqual(common.confidence_from_evidence(100), 0.98)
        self.assertGreater(common.confidence_from_evidence(3), common.confidence_from_evidence(1))

    def test_dedupe_preserve_order(self):
        self.assertEqual(common.dedupe_preserve_order(["a", "b", "a", "c", "b"]),
                         ["a", "b", "c"])


if __name__ == "__main__":
    unittest.main()

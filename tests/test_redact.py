"""
Property 8: API key is never leaked in captured output.

**Validates: Requirements 7.6**
"""
import random
import string
import unittest

from tests.test_live import redact

ALPHABET = string.ascii_letters + string.digits + " \n:/-_.#"


def rand_str(rng, lo, hi, alphabet=ALPHABET):
    return "".join(rng.choice(alphabet) for _ in range(rng.randint(lo, hi)))


class RedactProperty(unittest.TestCase):
    def test_secret_never_appears_after_redaction(self):
        rng = random.Random(8)
        for _ in range(200):
            secret = rand_str(rng, 1, 40, string.ascii_letters + string.digits)
            parts = [rand_str(rng, 0, 20) for _ in range(rng.randint(1, 5))]
            text = secret.join(parts)  # secret appears len(parts)-1 times
            # Also sometimes make secrets overlap/adjacent
            if rng.random() < 0.3:
                text += secret + secret
            with self.subTest(secret=len(secret)):
                self.assertNotIn(secret, redact(text, [secret]))

    def test_multiple_secrets_and_bytes(self):
        out = redact(b"key=abcd1234 other=zz", ["abcd1234", "zz"])
        self.assertNotIn("abcd1234", out)
        self.assertNotIn("zz", out)

    def test_empty_secret_ignored(self):
        self.assertEqual(redact("hello", [""]), "hello")


if __name__ == "__main__":
    unittest.main()

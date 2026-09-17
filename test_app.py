import os
import unittest

import app


class ChatbotTests(unittest.TestCase):
    def test_fallback_response_for_greeting(self):
        self.assertIn("Hello", app.fallback_response("hi there"))

    def test_real_ai_check_requires_api_key(self):
        self.assertFalse(app.has_real_ai_key())

    def test_provider_detection_allows_gemini(self):
        os.environ["AI_PROVIDER"] = "gemini"
        os.environ["GEMINI_API_KEY"] = "test-key"
        self.assertEqual(app.get_active_provider(), "gemini")
        del os.environ["GEMINI_API_KEY"]
        del os.environ["AI_PROVIDER"]


if __name__ == "__main__":
    unittest.main()

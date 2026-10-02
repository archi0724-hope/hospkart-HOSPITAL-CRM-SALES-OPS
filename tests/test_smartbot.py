import json
import os
import unittest
from unittest.mock import patch

import requests
import app


class SmartBotTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"OPENAI_API_KEY": "test-only-key", "OPENAI_MODEL": "gpt-4.1-mini"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.client = app.app.test_client()

    def response(self, status=200, body=None):
        response = requests.Response()
        response.status_code = status
        response._content = json.dumps(body or {}).encode()
        return response

    @patch("app.requests.post")
    def test_chat_aggregates_text_and_keeps_context_separate(self, post):
        post.return_value = self.response(body={"output": [
            {"type": "reasoning", "summary": []},
            {"type": "message", "content": [{"type": "output_text", "text": "Hello."}, {"type": "output_text", "text": "Please review the quotation."}]},
        ]})
        response = self.client.post("/api/chat", json={"message": "Draft a follow-up", "context": {"selected_client": {"name": "ARYAA Hospital", "status": "Quotation Shared"}}})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["reply"], "Hello.\nPlease review the quotation.")
        args, kwargs = post.call_args
        self.assertEqual(args[0], "https://api.openai.com/v1/responses")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-only-key")
        self.assertIn("ARYAA Hospital", kwargs["json"]["input"])
        self.assertNotIn("ARYAA Hospital", kwargs["json"]["instructions"])
        self.assertFalse(kwargs["json"]["store"])

    @patch("app.requests.post")
    def test_missing_key_does_not_call_provider(self, post):
        with patch.dict(os.environ, {"OPENAI_API_KEY": " "}):
            response = self.client.post("/api/chat", json={"message": "Hello"})
            self.assertIn("OPENAI_API_KEY", response.json["reply"])
            self.assertFalse(self.client.get("/api/health").json["openai_configured"])
        post.assert_not_called()

    @patch("app.requests.post")
    def test_empty_message_does_not_call_provider(self, post):
        self.assertEqual(self.client.post("/api/chat", json={"message": " "}).status_code, 400)
        post.assert_not_called()

    @patch("app.requests.post")
    def test_provider_errors_are_actionable_and_do_not_echo_payload(self, post):
        for status, expected in [(401, "API key"), (429, "rate limit"), (404, "model access"), (503, "HTTP 503")]:
            with self.subTest(status=status):
                post.return_value = self.response(status, {"error": {"message": "sensitive provider detail"}})
                response = self.client.post("/api/chat", json={"message": "Hello"})
                self.assertEqual(response.status_code, 500)
                self.assertIn(expected, response.json["error"])
                self.assertNotIn("sensitive provider detail", response.json["error"])
                self.assertNotIn("test-only-key", response.json["error"])

    @patch("app.requests.post")
    def test_exhausted_credits_explain_billing_without_retry_advice(self, post):
        post.return_value = self.response(429, {"error": {"type": "insufficient_quota", "code": "credit_balance_exhausted"}})
        response = self.client.post("/api/chat", json={"message": "Hello"})
        self.assertEqual(response.status_code, 500)
        self.assertIn("Billing", response.json["error"])
        self.assertIn("credit balance", response.json["error"])
        self.assertNotIn("Wait a moment", response.json["error"])

    @patch("app.requests.post")
    def test_timeout_has_a_retry_message(self, post):
        post.side_effect = requests.Timeout()
        response = self.client.post("/api/chat", json={"message": "Hello"})
        self.assertEqual(response.status_code, 500)
        self.assertIn("try again", response.json["error"])

    @patch("app.requests.post")
    def test_refusal_and_empty_output(self, post):
        post.return_value = self.response(body={"output": [{"type": "message", "content": [{"type": "refusal", "refusal": "I cannot help with that request."}]}]})
        self.assertEqual(self.client.post("/api/chat", json={"message": "Hello"}).json["reply"], "I cannot help with that request.")
        post.return_value = self.response(body={"output": []})
        self.assertEqual(self.client.post("/api/chat", json={"message": "Hello"}).status_code, 500)

    def test_health_reports_provider_without_credentials(self):
        health = self.client.get("/api/health").json
        self.assertTrue(health["openai_configured"])
        self.assertEqual(health["ai_provider"], "OpenAI")
        self.assertNotIn("test-only-key", json.dumps(health))


if __name__ == "__main__":
    unittest.main()

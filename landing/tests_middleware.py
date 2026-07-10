from django.test import RequestFactory, SimpleTestCase, override_settings

from landing.middleware import RateLimitMiddleware


class TrustedProxyTests(SimpleTestCase):
    def setUp(self):
        self.middleware = RateLimitMiddleware(lambda request: None)
        self.factory = RequestFactory()

    @override_settings(TRUSTED_PROXY_IPS=["127.0.0.1/32"])
    def test_trusted_proxy_forwarded_ip_is_used(self):
        request = self.factory.post("/contact/", REMOTE_ADDR="127.0.0.1", HTTP_X_FORWARDED_FOR="203.0.113.10")
        self.assertEqual(self.middleware._get_client_ip(request), "203.0.113.10")

    @override_settings(TRUSTED_PROXY_IPS=["127.0.0.1/32"])
    def test_untrusted_forwarded_ip_is_ignored(self):
        request = self.factory.post("/contact/", REMOTE_ADDR="198.51.100.20", HTTP_X_FORWARDED_FOR="203.0.113.10")
        self.assertEqual(self.middleware._get_client_ip(request), "198.51.100.20")

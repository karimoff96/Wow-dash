from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class PrivilegedRouteTests(TestCase):
    def test_regular_user_cannot_open_super_dashboard(self):
        user = get_user_model().objects.create_user("not-superuser")
        self.client.force_login(user)
        response = self.client.get(reverse("superuser_admin"))
        self.assertEqual(response.status_code, 302)

    def test_development_only_routes_are_absent_under_test_production_shape(self):
        self.assertEqual(self.client.get("/test-select2/").status_code, 404)
        self.assertEqual(self.client.post("/bot", data=b"{}", content_type="application/json").status_code, 404)


from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import override


class DashboardTranslationTests(SimpleTestCase):
    def test_admin_login_uses_selected_language_cookie(self):
        response = self.client.get(
            reverse("admin_login"),
            HTTP_COOKIE="django_language=ru",
        )

        self.assertContains(response, '<html lang="ru">')
        self.assertNotContains(response, "data-theme")
        self.assertNotContains(response, "theme-toggle")
        self.assertContains(response, 'window.CURRENT_LANGUAGE = "ru";')

    def test_backend_admin_messages_are_translated(self):
        with override("uz"):
            self.assertEqual(_("Invalid username or password."), "Login yoki parol noto'g'ri.")
            self.assertEqual(_("Create Order"), "Buyurtma yaratish")

        with override("ru"):
            self.assertEqual(_("You do not have admin access."), "У вас нет доступа к админ-панели.")
            self.assertEqual(_("Branch name is required."), "Название филиала обязательно.")

    def test_frontend_catalog_has_template_and_script_keys(self):
        catalog = Path(settings.BASE_DIR, "static/js/translations.js").read_text()

        for key in [
            "filter.search",
            "auth.enterEmail",
            "report.chartNotLoaded",
            "report.noOrderData",
            "report.noStatusData",
            "report.noOrdersThisMonth",
            "report.noDataThisMonth",
        ]:
            self.assertIn(f"'{key}':", catalog)

        self.assertIn("window.translations = buildTranslationsByLanguage(translations);", catalog)
        self.assertIn("translateLiteral(text)", catalog)
        self.assertIn("observeDynamicContent()", catalog)

    def test_dashboard_dark_mode_runtime_removed(self):
        base_dir = Path(settings.BASE_DIR)
        app_js = (base_dir / "static/js/app.js").read_text()
        navbar = (base_dir / "templates/partials/navbar.html").read_text()

        self.assertNotIn("data-theme-toggle", navbar)
        self.assertNotIn("localStorage.getItem(\"theme\")", app_js)
        self.assertNotIn("localStorage.setItem(\"theme\")", app_js)
        self.assertNotIn("setAttribute(\"data-theme\"", app_js)

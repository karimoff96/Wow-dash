import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from core.health import health_snapshot


class HealthEndpointTests(TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        Path(self.tempdir.name, "media").mkdir()
        backup_dir = Path(self.tempdir.name, "backups", "database")
        backup_dir.mkdir(parents=True)
        (backup_dir / "backup_test.sql.gz.enc").write_bytes(b"encrypted-backup")
        self.settings_override = override_settings(
            BASE_DIR=Path(self.tempdir.name),
            MEDIA_ROOT=Path(self.tempdir.name, "media"),
            TESTING=True,
        )
        self.settings_override.enable()
        cache.set("health:telegram-connectivity", {"ok": True}, 60)

    def tearDown(self):
        self.settings_override.disable()
        self.tempdir.cleanup()

    def test_snapshot_contains_operational_checks(self):
        snapshot = health_snapshot()
        self.assertTrue(snapshot["ok"])
        self.assertTrue(snapshot["checks"]["database"]["ok"])
        self.assertTrue(snapshot["checks"]["cache"]["ok"])
        self.assertTrue(snapshot["checks"]["backup"]["ok"])
        self.assertTrue(snapshot["checks"]["telegram"]["ok"])
        self.assertIn("archive", snapshot["checks"])
        self.assertIn("celery", snapshot["checks"])

    def test_public_readiness_redacts_operational_details(self):
        response = self.client.get(reverse("health_ready"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()["checks"]["disk"]), {"ok"})

    def test_superuser_readiness_contains_details(self):
        superuser = get_user_model().objects.create_superuser("health-admin")
        self.client.force_login(superuser)
        response = self.client.get(reverse("health_ready"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("used_percent", response.json()["checks"]["disk"])


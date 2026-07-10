import os
import tempfile
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import BotUser
from billing.models import Subscription, Tariff
from core.models import ArchiveRun, FileArchive
from core.storage_service import StorageArchiveService
from orders.models import Order, OrderMedia, Receipt
from organizations.models import Branch, TranslationCenter
from services.models import Category, Product


class ArchiveSafetyTests(TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.settings_override = override_settings(
            MEDIA_ROOT=self.tempdir.name,
            ARCHIVE_MIN_SIZE_MB=0,
        )
        self.settings_override.enable()
        self.owner = get_user_model().objects.create_user("archive-owner")
        self.center = TranslationCenter.objects.create(
            name="Archive Center",
            owner=self.owner,
            bot_token="archive-token",
            company_orders_channel_id="-100123456",
        )
        self.branch = Branch.objects.create(center=self.center, name="Main", is_main=True)
        self.category = Category.objects.create(
            branch=self.branch, name="Translation", charging="dynamic"
        )
        self.product = Product.objects.create(
            name="Passport",
            category=self.category,
            ordinary_first_page_price=Decimal("10000"),
            ordinary_other_page_price=Decimal("5000"),
            agency_first_page_price=Decimal("9000"),
            agency_other_page_price=Decimal("4000"),
        )
        self.customer = BotUser.objects.create(
            center=self.center,
            branch=self.branch,
            user_id=123,
            name="Customer",
            phone="+998900000000",
            is_active=True,
        )

    def tearDown(self):
        self.settings_override.disable()
        self.tempdir.cleanup()

    def create_archivable_order(self, filename="document.pdf"):
        order = Order.objects.create(
            branch=self.branch,
            bot_user=self.customer,
            product=self.product,
            total_pages=1,
            total_price=Decimal("10000"),
            status="completed",
            completed_at=timezone.now() - timedelta(days=31),
            is_active=False,
        )
        media = OrderMedia.objects.create(
            file=SimpleUploadedFile(filename, b"verified archive content"),
            pages=1,
        )
        order.files.add(media)
        return order, media

    def telegram_bot(self):
        def send_document(channel_id, file_obj, **kwargs):
            return SimpleNamespace(
                message_id=55,
                document=SimpleNamespace(file_id="telegram-file", file_size=os.fstat(file_obj.fileno()).st_size),
            )
        return SimpleNamespace(send_document=send_document)

    @patch("core.storage_service.get_bot_instance")
    def test_canary_verifies_archive_without_deleting_sources(self, get_bot):
        get_bot.return_value = self.telegram_bot()
        order, media = self.create_archivable_order()

        result = StorageArchiveService().archive_orders(
            self.center, force=True, mode=ArchiveRun.MODE_CANARY
        )

        self.assertTrue(result["success"])
        archive = FileArchive.objects.get(orders=order)
        self.assertEqual(archive.verification_status, FileArchive.VERIFICATION_VERIFIED)
        self.assertTrue(archive.sha256)
        self.assertEqual(archive.manifest["source_file_count"], 1)
        self.assertTrue(media.file.storage.exists(media.file.name))
        self.assertIsNone(archive.files_deleted_at)

    @patch("core.storage_service.get_bot_instance")
    def test_live_mode_deletes_only_after_verified_upload(self, get_bot):
        get_bot.return_value = self.telegram_bot()
        order, media = self.create_archivable_order("delete-me.pdf")
        source_name = media.file.name

        result = StorageArchiveService().archive_orders(
            self.center, force=True, mode=ArchiveRun.MODE_LIVE
        )

        self.assertTrue(result["success"])
        archive = FileArchive.objects.get(orders=order)
        self.assertFalse(media.file.storage.exists(source_name))
        self.assertIsNotNone(archive.files_deleted_at)

    @patch("core.storage_service.get_bot_instance")
    def test_verified_archive_continues_after_subscription_expiry(self, get_bot):
        get_bot.return_value = self.telegram_bot()
        tariff = Tariff.objects.create(title="Archive tariff", slug="archive-tariff")
        Subscription.objects.create(
            organization=self.center,
            tariff=tariff,
            start_date=timezone.localdate() - timedelta(days=40),
            end_date=timezone.localdate() - timedelta(days=1),
            status=Subscription.STATUS_EXPIRED,
        )
        order, media = self.create_archivable_order("expired-center.pdf")

        result = StorageArchiveService().archive_orders(
            self.center, force=True, mode=ArchiveRun.MODE_CANARY
        )

        self.assertTrue(result["success"])
        self.assertTrue(FileArchive.objects.filter(orders=order, verified_at__isnull=False).exists())
        self.assertTrue(media.file.storage.exists(media.file.name))

    def test_disabled_maintenance_archive_never_uploads_or_deletes(self):
        self.center.maintenance_archive_enabled = False
        self.center.save(update_fields=["maintenance_archive_enabled"])
        order, media = self.create_archivable_order("disabled-archive.pdf")

        result = StorageArchiveService().archive_orders(
            self.center, force=True, mode=ArchiveRun.MODE_LIVE
        )

        self.assertFalse(result["success"])
        self.assertTrue(media.file.storage.exists(media.file.name))
        order.refresh_from_db()
        self.assertIsNone(order.archived_files_id)

    @patch("core.storage_service.ArchiveConfig.MAX_SIZE_MB", 0)
    def test_oversized_manual_archive_requires_recorded_verification(self):
        order, media = self.create_archivable_order("oversized.pdf")
        result = StorageArchiveService().archive_orders(
            self.center, force=True, mode=ArchiveRun.MODE_CANARY
        )
        self.assertFalse(result["success"])
        archive = FileArchive.objects.get()
        self.assertEqual(archive.verification_status, FileArchive.VERIFICATION_MANUAL)
        self.assertIsNone(order.archived_files_id)

        call_command(
            "verify_manual_archive",
            archive.pk,
            message_id=888,
            file_id="manual-telegram-file",
            uploaded_size=archive.total_size_bytes,
            sha256=archive.sha256,
        )

        archive.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(archive.verification_status, FileArchive.VERIFICATION_VERIFIED)
        self.assertEqual(order.archived_files_id, archive.pk)
        self.assertTrue(media.file.storage.exists(media.file.name))

    @patch("core.storage_service.StorageArchiveService.upload_to_telegram")
    def test_failed_upload_never_links_or_deletes_order_files(self, upload):
        upload.return_value = (False, "network unavailable")
        order, media = self.create_archivable_order("keep-me.pdf")
        source_name = media.file.name

        result = StorageArchiveService().archive_orders(
            self.center, force=True, mode=ArchiveRun.MODE_LIVE
        )

        self.assertFalse(result["success"])
        order.refresh_from_db()
        self.assertIsNone(order.archived_files_id)
        self.assertTrue(media.file.storage.exists(source_name))
        self.assertEqual(FileArchive.objects.get().verification_status, FileArchive.VERIFICATION_FAILED)

    def test_manifest_contains_primary_additional_and_both_receipt_formats(self):
        order, primary = self.create_archivable_order("primary.pdf")
        additional = OrderMedia.objects.create(
            file=SimpleUploadedFile("additional.txt", b"additional"), pages=1
        )
        order.additional_files.add(additional)
        order.recipt = SimpleUploadedFile("legacy-receipt.jpg", b"legacy receipt")
        order.save(update_fields=["recipt"])
        Receipt.objects.create(
            order=order,
            file=SimpleUploadedFile("receipt.png", b"modern receipt"),
            amount=Decimal("10000"),
        )

        build = StorageArchiveService().build_archive(self.center, [order])

        kinds = {
            entry["kind"]
            for order_manifest in build["manifest"]["orders"]
            for entry in order_manifest["files"]
        }
        self.assertEqual(kinds, {"primary", "additional", "legacy_receipt", "receipt"})
        self.assertEqual(build["source_file_count"], 4)
        self.assertGreater(build["source_size_bytes"], 0)
        self.assertTrue(primary.file.storage.exists(primary.file.name))

    def test_archivable_query_uses_default_age_and_ignores_size_hint(self):
        order, _media = self.create_archivable_order()
        service = StorageArchiveService()

        ids = list(service.get_archivable_orders(self.center, min_size_mb=1).values_list("pk", flat=True))

        self.assertEqual(ids, [order.pk])

    def test_field_file_errors_are_treated_as_missing(self):
        class BrokenFile:
            name = "broken.pdf"

            @property
            def path(self):
                raise NotImplementedError

        self.assertFalse(StorageArchiveService()._field_file_exists(BrokenFile()))

    def test_build_skips_missing_file_and_supports_legacy_no_branch_manifest(self):
        order, media = self.create_archivable_order("missing.pdf")
        media.file.storage.delete(media.file.name)
        service = StorageArchiveService()
        build = service.build_archive(self.center, [order], archive_name="missing.zip")
        self.assertEqual(build["source_file_count"], 0)

        fake_order = SimpleNamespace(branch=None, id=987, get_order_number=lambda: 987)
        with patch.object(service, "_get_order_details", return_value={"order_id": 987}), patch.object(
            service, "_iter_order_files", return_value=[]
        ):
            no_branch = service.build_archive(self.center, [fake_order], archive_name="no-branch.zip")
        self.assertEqual(no_branch["manifest"]["orders"][0]["order_id"], 987)

    def test_create_archive_wrapper_and_size_batching_edges(self):
        first, _ = self.create_archivable_order("first.pdf")
        second, _ = self.create_archivable_order("second.pdf")
        service = StorageArchiveService()

        path = service.create_archive(self.center, [first], archive_name="wrapper.zip")
        self.assertTrue(path.exists())
        self.assertEqual(service._split_orders_by_size([], 1), [])
        with patch.object(service, "_estimate_order_size", side_effect=[800, 800]):
            batches = service._split_orders_by_size([first, second], 0.001)
        self.assertEqual(batches, [[first], [second]])

    def _archive_record(self, path):
        return FileArchive.objects.create(
            center=self.center,
            archive_name=os.path.basename(path),
            archive_path=str(path),
            telegram_channel_id=self.center.company_orders_channel_id,
        )

    @patch("core.storage_service.ArchiveConfig.LOCAL_RETENTION_DAYS", 1)
    def test_expired_local_archive_cleanup_clears_recorded_path(self):
        path = os.path.join(self.tempdir.name, "expired.zip")
        with open(path, "wb") as archive_file:
            archive_file.write(b"old archive")
        archive = self._archive_record(path)
        FileArchive.objects.filter(pk=archive.pk).update(
            archive_date=timezone.now() - timedelta(days=2)
        )

        StorageArchiveService()._cleanup_expired_local_archives(center=self.center)

        archive.refresh_from_db()
        self.assertIsNone(archive.archive_path)
        self.assertFalse(os.path.exists(path))

    @patch("core.storage_service.ArchiveConfig.LOCAL_RETENTION_DAYS", 1)
    @patch("core.storage_service.os.remove", side_effect=OSError("busy"))
    def test_expired_local_archive_cleanup_keeps_path_when_delete_fails(self, _remove):
        path = os.path.join(self.tempdir.name, "busy.zip")
        with open(path, "wb") as archive_file:
            archive_file.write(b"busy archive")
        archive = self._archive_record(path)
        FileArchive.objects.filter(pk=archive.pk).update(
            archive_date=timezone.now() - timedelta(days=2)
        )

        StorageArchiveService()._cleanup_expired_local_archives(center=self.center)

        archive.refresh_from_db()
        self.assertEqual(archive.archive_path, path)

    @patch("core.storage_service.ArchiveConfig.LOCAL_RETENTION_DAYS", 0)
    def test_zero_retention_skips_expired_archive_scan(self):
        with patch("core.models.FileArchive.objects.filter") as filtered:
            StorageArchiveService()._cleanup_expired_local_archives(center=self.center)
        filtered.assert_not_called()

    @patch("core.storage_service.get_bot_instance")
    def test_upload_rejects_missing_channel_and_unverifiable_response(self, get_bot):
        path = os.path.join(self.tempdir.name, "upload.zip")
        with open(path, "wb") as archive_file:
            archive_file.write(b"archive")
        service = StorageArchiveService()
        self.center.company_orders_channel_id = ""
        success, error = service.upload_to_telegram(self.center, path)
        self.assertFalse(success)
        self.assertIn("No company orders channel", error)

        self.center.company_orders_channel_id = "-100123456"
        get_bot.return_value.send_document.return_value = SimpleNamespace(
            message_id=1,
            document=SimpleNamespace(file_id="", file_size=999),
        )
        success, error = service.upload_to_telegram(self.center, path)
        self.assertFalse(success)
        self.assertIn("could not be verified", error)

        get_bot.return_value.send_document.side_effect = RuntimeError("telegram timeout")
        success, error = service.upload_to_telegram(self.center, path)
        self.assertFalse(success)
        self.assertIn("telegram timeout", error)

    @patch("core.storage_service.ArchiveConfig.MAX_SIZE_MB", 0)
    @patch("core.storage_service.get_bot_instance")
    def test_upload_preflight_rejects_oversized_archive(self, _get_bot):
        path = os.path.join(self.tempdir.name, "oversized-upload.zip")
        with open(path, "wb") as archive_file:
            archive_file.write(b"not empty")

        success, error = StorageArchiveService().upload_to_telegram(self.center, path)

        self.assertFalse(success)
        self.assertIn("too large", error)

    @patch("core.storage_service.get_bot_instance")
    def test_upload_builds_default_caption_and_accepts_exact_size(self, get_bot):
        path = os.path.join(self.tempdir.name, "verified-upload.zip")
        with open(path, "wb") as archive_file:
            archive_file.write(b"verified")
        get_bot.return_value.send_document.return_value = SimpleNamespace(
            message_id=77,
            document=SimpleNamespace(file_id="telegram-id", file_size=os.path.getsize(path)),
        )

        success, metadata = StorageArchiveService().upload_to_telegram(self.center, path)

        self.assertTrue(success)
        self.assertEqual(metadata["message_id"], 77)
        caption = get_bot.return_value.send_document.call_args.kwargs["caption"]
        self.assertIn("Storage Archive", caption)

    def test_archive_mode_validation_inventory_empty_and_threshold_paths(self):
        service = StorageArchiveService()
        with self.assertRaises(ValueError):
            service.archive_orders(self.center, mode="dangerous")

        empty_center = TranslationCenter.objects.create(name="Empty Archive Center", owner=self.owner)
        empty = service.archive_orders(empty_center, mode=ArchiveRun.MODE_INVENTORY)
        self.assertTrue(empty["success"])
        self.assertEqual(empty["orders_count"], 0)

        self.create_archivable_order("inventory.pdf")
        inventory = service.archive_orders(self.center, mode=ArchiveRun.MODE_INVENTORY)
        self.assertTrue(inventory["success"])
        self.assertEqual(inventory["inventory"]["orders"], 1)

        with patch("core.storage_service.ArchiveConfig.MIN_SIZE_MB", 100):
            below_threshold = service.archive_orders(
                self.center, force=False, mode=ArchiveRun.MODE_CANARY
            )
        self.assertFalse(below_threshold["success"])
        self.assertIn("below threshold", below_threshold["error"])

    def test_inventory_command_records_success_for_center_with_no_orders(self):
        empty_center = TranslationCenter.objects.create(
            name="Empty Command Archive Center", owner=self.owner
        )

        call_command(
            "archive",
            "--run",
            "--center",
            str(empty_center.pk),
            "--mode",
            ArchiveRun.MODE_INVENTORY,
        )

        run = ArchiveRun.objects.get(center=empty_center)
        self.assertEqual(run.status, ArchiveRun.STATUS_COMPLETED)
        self.assertEqual(run.orders_found, 0)

    @patch("core.storage_service.get_bot_instance")
    def test_multiple_batches_include_part_metadata(self, get_bot):
        get_bot.return_value = self.telegram_bot()
        self.create_archivable_order("part-one.pdf")
        self.create_archivable_order("part-two.pdf")

        result = StorageArchiveService().archive_orders(
            self.center,
            force=True,
            max_orders=1,
            mode=ArchiveRun.MODE_CANARY,
        )

        self.assertTrue(result["success"])
        self.assertEqual(len(result["archives_created"]), 2)

    @patch("core.storage_service.ArchiveConfig.MAX_ORDERS_PER_BATCH", 0)
    @patch("core.storage_service.get_bot_instance")
    def test_unlimited_batch_configuration_keeps_orders_together(self, get_bot):
        get_bot.return_value = self.telegram_bot()
        self.create_archivable_order("unlimited.pdf")

        result = StorageArchiveService().archive_orders(
            self.center, force=True, mode=ArchiveRun.MODE_CANARY
        )

        self.assertTrue(result["success"])
        self.assertEqual(len(result["archives_created"]), 1)

    @override_settings(TESTING=False)
    @patch("core.storage_service.time.sleep")
    @patch("core.storage_service.StorageArchiveService.upload_to_telegram")
    def test_transient_upload_failure_retries_with_backoff(self, upload, sleep):
        upload.side_effect = [
            (False, "timeout one"),
            (False, "timeout two"),
            (True, {"message_id": 9, "file_id": "file-9", "file_size": 10}),
        ]
        self.create_archivable_order("retry.pdf")

        result = StorageArchiveService().archive_orders(
            self.center, force=True, mode=ArchiveRun.MODE_CANARY
        )

        self.assertTrue(result["success"])
        self.assertEqual(upload.call_count, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2])

    @patch("core.storage_service.StorageArchiveService._cleanup_local_files", return_value=(0, 1))
    @patch("core.storage_service.get_bot_instance")
    def test_source_delete_failure_marks_archive_run_partial(self, get_bot, _cleanup):
        get_bot.return_value = self.telegram_bot()
        self.create_archivable_order("undeletable.pdf")

        result = StorageArchiveService().archive_orders(
            self.center, force=True, mode=ArchiveRun.MODE_LIVE
        )

        self.assertFalse(result["success"])
        archive = FileArchive.objects.get()
        self.assertIsNone(archive.files_deleted_at)
        self.assertIn("Failed to delete", archive.last_error)
        self.assertEqual(archive.run.status, ArchiveRun.STATUS_PARTIAL)

    @patch("core.storage_service.ArchiveConfig.LOCAL_RETENTION_DAYS", 1)
    @patch("core.storage_service.get_bot_instance")
    def test_verified_zip_is_retained_when_local_retention_is_enabled(self, get_bot):
        get_bot.return_value = self.telegram_bot()
        self.create_archivable_order("retained.pdf")

        result = StorageArchiveService().archive_orders(
            self.center, force=True, mode=ArchiveRun.MODE_CANARY
        )

        self.assertTrue(result["success"])
        archive = FileArchive.objects.get()
        self.assertTrue(os.path.exists(archive.archive_path))

    @patch("core.storage_service.StorageArchiveService.get_archivable_orders", side_effect=RuntimeError("db down"))
    def test_unexpected_archive_failure_is_recorded_on_run(self, _orders):
        result = StorageArchiveService().archive_orders(
            self.center, force=True, mode=ArchiveRun.MODE_CANARY
        )

        self.assertFalse(result["success"])
        self.assertIn("db down", result["error"])
        run = ArchiveRun.objects.get()
        self.assertEqual(run.status, ArchiveRun.STATUS_FAILED)

    def test_cleanup_local_files_counts_storage_errors_without_deleting_record(self):
        order, media = self.create_archivable_order("storage-error.pdf")
        service = StorageArchiveService()
        with patch.object(media.file.storage, "delete", side_effect=OSError("read only")):
            deleted, failed = service._cleanup_local_files([order])

        self.assertEqual((deleted, failed), (0, 1))
        self.assertTrue(media.file.storage.exists(media.file.name))

        media.file.storage.delete(media.file.name)
        self.assertEqual(service._cleanup_local_files([order]), (0, 0))

    def test_archive_can_be_restricted_to_explicit_order_ids(self):
        selected, _ = self.create_archivable_order("selected.pdf")
        unselected, _ = self.create_archivable_order("unselected.pdf")

        result = StorageArchiveService().archive_orders(
            self.center,
            force=True,
            mode=ArchiveRun.MODE_INVENTORY,
            order_ids=[selected.pk],
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["inventory"]["orders"], 1)
        self.assertTrue(Order.objects.filter(pk=unselected.pk, archived_files__isnull=True).exists())

    @patch("core.management.commands.verify_telegram_archive.get_bot_instance")
    def test_telegram_restore_drill_verifies_zip_before_source_deletion(self, get_bot):
        order, media = self.create_archivable_order("restore-drill.pdf")
        build = StorageArchiveService().build_archive(
            self.center, [order], archive_name="restore-drill.zip"
        )
        archive_content = build["path"].read_bytes()
        run = ArchiveRun.objects.create(center=self.center, mode=ArchiveRun.MODE_CANARY)
        archive = FileArchive.objects.create(
            center=self.center,
            run=run,
            archive_name="restore-drill.zip",
            archive_path=str(build["path"]),
            telegram_message_id=123,
            telegram_file_id="restore-file-id",
            telegram_channel_id=self.center.company_orders_channel_id,
            total_orders=1,
            total_size_bytes=len(archive_content),
            sha256=build["sha256"],
            manifest=build["manifest"],
            source_file_count=build["source_file_count"],
            source_size_bytes=build["source_size_bytes"],
            uploaded_size_bytes=len(archive_content),
            verification_status=FileArchive.VERIFICATION_VERIFIED,
            verified_at=timezone.now(),
        )
        order.archived_files = archive
        order.save(update_fields=["archived_files"])
        get_bot.return_value.get_file.return_value = SimpleNamespace(
            file_path="restore-drill.zip",
            file_size=len(archive_content),
        )
        get_bot.return_value.download_file.return_value = archive_content

        call_command("verify_telegram_archive", archive.pk)
        self.assertTrue(media.file.storage.exists(media.file.name))
        archive.refresh_from_db()
        self.assertIn("restore drill passed", archive.notes)

        call_command(
            "verify_telegram_archive",
            archive.pk,
            delete_sources=True,
            confirm_delete=True,
        )
        self.assertFalse(media.file.storage.exists(media.file.name))
        archive.refresh_from_db()
        self.assertIsNotNone(archive.files_deleted_at)

    @patch("core.management.commands.verify_telegram_archive.get_bot_instance")
    def test_telegram_restore_drill_never_deletes_tampered_download(self, get_bot):
        order, media = self.create_archivable_order("tampered-restore.pdf")
        build = StorageArchiveService().build_archive(
            self.center, [order], archive_name="tampered.zip"
        )
        content = build["path"].read_bytes()
        archive = FileArchive.objects.create(
            center=self.center,
            archive_name="tampered.zip",
            telegram_message_id=999,
            telegram_file_id="tampered-id",
            telegram_channel_id=self.center.company_orders_channel_id,
            total_orders=1,
            total_size_bytes=len(content),
            sha256=build["sha256"],
            manifest=build["manifest"],
            source_file_count=build["source_file_count"],
            source_size_bytes=build["source_size_bytes"],
            uploaded_size_bytes=len(content),
            verification_status=FileArchive.VERIFICATION_VERIFIED,
            verified_at=timezone.now(),
        )
        order.archived_files = archive
        order.save(update_fields=["archived_files"])
        get_bot.return_value.get_file.return_value = SimpleNamespace(
            file_path="tampered.zip", file_size=len(content)
        )
        get_bot.return_value.download_file.return_value = b"x" * len(content)

        with self.assertRaisesMessage(Exception, "SHA-256"):
            call_command(
                "verify_telegram_archive",
                archive.pk,
                delete_sources=True,
                confirm_delete=True,
            )

        self.assertTrue(media.file.storage.exists(media.file.name))
        archive.refresh_from_db()
        self.assertIsNone(archive.files_deleted_at)

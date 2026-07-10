import hashlib
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.models import FileArchive
from core.storage_service import StorageArchiveService
from orders.models import Order


class Command(BaseCommand):
    help = "Record and verify an administrator-assisted Telegram archive upload"

    def add_arguments(self, parser):
        parser.add_argument("archive_id", type=int)
        parser.add_argument("--message-id", type=int, required=True)
        parser.add_argument("--file-id", required=True)
        parser.add_argument("--uploaded-size", type=int, required=True)
        parser.add_argument("--sha256", required=True)
        parser.add_argument("--delete-sources", action="store_true")
        parser.add_argument("--confirm-delete", action="store_true")

    def handle(self, *args, **options):
        if options["delete_sources"] and not options["confirm_delete"]:
            raise CommandError("--delete-sources requires --confirm-delete")

        archive = FileArchive.objects.filter(pk=options["archive_id"]).first()
        if not archive:
            raise CommandError("Archive record not found")
        allowed_statuses = {
            FileArchive.VERIFICATION_MANUAL,
            FileArchive.VERIFICATION_FAILED,
        }
        if options["delete_sources"]:
            allowed_statuses.add(FileArchive.VERIFICATION_VERIFIED)
        if archive.verification_status not in allowed_statuses:
            raise CommandError("Only manual/failed archive records can be verified with this command")
        archive_path = Path(archive.archive_path or "")
        if not archive_path.is_file():
            raise CommandError("The retained local archive file is missing")

        digest = hashlib.sha256()
        with archive_path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        local_checksum = digest.hexdigest()
        local_size = archive_path.stat().st_size
        if options["sha256"].lower() != local_checksum or archive.sha256 != local_checksum:
            raise CommandError("SHA-256 mismatch; no database or file changes were made")
        if options["uploaded_size"] != local_size:
            raise CommandError("Uploaded-size mismatch; no database or file changes were made")

        order_ids = [
            item.get("order_id")
            for item in archive.manifest.get("orders", [])
            if item.get("order_id")
        ]
        orders = list(Order.objects.filter(
            pk__in=order_ids,
            branch__center=archive.center,
        ).filter(Q(archived_files__isnull=True) | Q(archived_files=archive)))
        if len(orders) != len(set(order_ids)):
            raise CommandError("Manifest orders do not match eligible center orders")

        with transaction.atomic():
            archive.telegram_message_id = options["message_id"]
            archive.telegram_file_id = options["file_id"]
            archive.uploaded_size_bytes = local_size
            archive.verification_status = FileArchive.VERIFICATION_VERIFIED
            archive.verified_at = timezone.now()
            archive.last_error = ""
            archive.save(update_fields=[
                "telegram_message_id", "telegram_file_id", "uploaded_size_bytes",
                "verification_status", "verified_at", "last_error",
            ])
            Order.objects.filter(pk__in=order_ids).update(archived_files=archive)

        if options["delete_sources"]:
            deleted, failed = StorageArchiveService()._cleanup_local_files(orders)
            if failed:
                archive.last_error = f"Failed to delete {failed} local source file(s)"
                archive.save(update_fields=["last_error"])
                raise CommandError(archive.last_error)
            archive.files_deleted_at = timezone.now()
            archive.save(update_fields=["files_deleted_at"])
            self.stdout.write(self.style.WARNING(f"Deleted {deleted} verified source file(s)"))

        self.stdout.write(self.style.SUCCESS(
            f"Archive {archive.pk} verified and linked to {len(orders)} order(s)"
        ))

import hashlib
import json
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from bot.notification_service import get_bot_instance
from core.models import FileArchive
from core.storage_service import StorageArchiveService
from orders.models import Order


class Command(BaseCommand):
    help = "Download a Telegram archive and verify its ZIP, manifest, and source checksums"

    def add_arguments(self, parser):
        parser.add_argument("archive_id", type=int)
        parser.add_argument("--delete-sources", action="store_true")
        parser.add_argument("--confirm-delete", action="store_true")

    def handle(self, *args, **options):
        if options["delete_sources"] and not options["confirm_delete"]:
            raise CommandError("--delete-sources requires --confirm-delete")

        archive = FileArchive.objects.select_related("center").filter(pk=options["archive_id"]).first()
        if not archive:
            raise CommandError("Archive record not found")
        if archive.verification_status != FileArchive.VERIFICATION_VERIFIED:
            raise CommandError("Archive upload is not verified")
        if not archive.telegram_file_id or not archive.telegram_message_id:
            raise CommandError("Archive has no recorded Telegram file/message ID")

        bot = get_bot_instance(archive.center.bot_token)
        if bot is None:
            raise CommandError("Center bot could not be initialized")

        try:
            telegram_file = bot.get_file(archive.telegram_file_id)
            remote_size = getattr(telegram_file, "file_size", None)
            if remote_size not in {None, archive.uploaded_size_bytes}:
                raise CommandError(
                    f"Telegram size mismatch: recorded={archive.uploaded_size_bytes}, remote={remote_size}"
                )
            content = bot.download_file(telegram_file.file_path)
        except CommandError:
            raise
        except Exception as exc:
            raise CommandError(f"Telegram restore download failed: {exc}") from exc

        with tempfile.TemporaryDirectory(prefix="wowdash-archive-restore-") as temp_dir:
            archive_path = Path(temp_dir) / archive.archive_name
            archive_path.write_bytes(content)
            if archive_path.stat().st_size != archive.uploaded_size_bytes:
                raise CommandError("Downloaded archive size does not match the recorded upload")
            digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
            if digest != archive.sha256:
                raise CommandError("Downloaded archive SHA-256 does not match")

            try:
                with zipfile.ZipFile(archive_path) as zipped:
                    if zipped.testzip() is not None:
                        raise CommandError("ZIP CRC verification failed")
                    manifest = json.loads(zipped.read("archive_manifest.json"))
                    if manifest != archive.manifest:
                        raise CommandError("Telegram ZIP manifest does not match the database record")
                    if manifest.get("center_id") != archive.center_id:
                        raise CommandError("Manifest center does not match the archive center")
                    for order_entry in manifest.get("orders", []):
                        for file_entry in order_entry.get("files", []):
                            member_name = file_entry.get("archive_name", "")
                            member_path = PurePosixPath(member_name)
                            if member_path.is_absolute() or ".." in member_path.parts:
                                raise CommandError("Unsafe ZIP member path in manifest")
                            payload = zipped.read(member_name)
                            if len(payload) != file_entry.get("size_bytes"):
                                raise CommandError(f"Restored size mismatch for {member_name}")
                            if hashlib.sha256(payload).hexdigest() != file_entry.get("sha256"):
                                raise CommandError(f"Restored checksum mismatch for {member_name}")
            except (KeyError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
                raise CommandError(f"Invalid Telegram archive: {exc}") from exc

        drill_note = f"Telegram restore drill passed at {timezone.now().isoformat()}"
        archive.notes = "\n".join(filter(None, [archive.notes, drill_note]))
        archive.save(update_fields=["notes"])

        if options["delete_sources"]:
            order_ids = [item.get("order_id") for item in archive.manifest.get("orders", []) if item.get("order_id")]
            orders = list(Order.objects.filter(
                pk__in=order_ids,
                branch__center=archive.center,
            ).filter(Q(archived_files=archive)))
            if len(orders) != len(set(order_ids)):
                raise CommandError("Manifest orders no longer match the linked archive")
            deleted, failed = StorageArchiveService()._cleanup_local_files(orders)
            if failed:
                archive.last_error = f"Failed to delete {failed} source file(s) after restore drill"
                archive.save(update_fields=["last_error"])
                raise CommandError(archive.last_error)
            archive.files_deleted_at = timezone.now()
            archive.save(update_fields=["files_deleted_at"])
            self.stdout.write(self.style.WARNING(f"Deleted {deleted} restored-and-verified source file(s)"))

        self.stdout.write(self.style.SUCCESS(f"Archive {archive.pk} Telegram restore verification passed"))

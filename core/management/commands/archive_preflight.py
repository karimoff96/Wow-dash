import os

from django.core.management.base import BaseCommand, CommandError

from WowDash.archive_config import ArchiveConfig
from bot.access import center_can_archive
from bot.notification_service import get_bot_instance
from core.storage_service import StorageArchiveService
from organizations.models import TranslationCenter


class Command(BaseCommand):
    help = "Audit eligible archive data and optionally verify Telegram channel access"

    def add_arguments(self, parser):
        parser.add_argument("--center", type=int)
        parser.add_argument("--check-telegram", action="store_true")

    def handle(self, *args, **options):
        centers = TranslationCenter.objects.filter(
            is_active=True,
            maintenance_archive_enabled=True,
        ).order_by("pk")
        if options["center"]:
            centers = centers.filter(pk=options["center"])
        if not centers.exists():
            raise CommandError("No matching centers")

        service = StorageArchiveService()
        max_bytes = int(ArchiveConfig.MAX_SIZE_MB * 1024 * 1024)
        failures = []

        for center in centers:
            orders = list(service.get_archivable_orders(center))
            order_sizes = []
            source_names = set()
            source_bytes = 0
            source_count = 0
            oversized = []

            for order in orders:
                order_bytes = 0
                for _kind, _index, field_file in service._iter_order_files(order):
                    if not service._field_file_exists(field_file):
                        continue
                    size = os.path.getsize(field_file.path)
                    order_bytes += size
                    source_bytes += size
                    source_count += 1
                    source_names.add(field_file.name)
                order_sizes.append((order_bytes, order.pk))
                if order_bytes > max_bytes:
                    oversized.append((order.pk, order_bytes))

            canary = next(
                ((order_id, size) for size, order_id in sorted(order_sizes) if 0 < size <= 15 * 1024 * 1024),
                None,
            )
            self.stdout.write(
                f"center={center.pk} name={center.name!r} orders={len(orders)} "
                f"files={source_count} unique_paths={len(source_names)} "
                f"bytes={source_bytes} oversized_orders={len(oversized)} "
                f"canary_order={canary[0] if canary else None} "
                f"canary_bytes={canary[1] if canary else None}"
            )

            if oversized:
                largest = sorted(oversized, key=lambda item: item[1], reverse=True)[:10]
                self.stdout.write(self.style.WARNING(f"  oversized={largest}"))

            if not options["check_telegram"] or not orders:
                continue
            if not center_can_archive(center):
                failures.append(f"{center.pk}: archive permission/channel configuration incomplete")
                continue

            try:
                bot = get_bot_instance(center.bot_token)
                if bot is None:
                    raise RuntimeError("bot initialization failed")
                me = bot.get_me()
                chat = bot.get_chat(center.company_orders_channel_id)
                member = bot.get_chat_member(center.company_orders_channel_id, me.id)
                status = getattr(member, "status", "unknown")
                can_post = getattr(member, "can_post_messages", None)
                if status not in {"administrator", "creator", "member"} or can_post is False:
                    raise RuntimeError(f"bot status={status}, can_post_messages={can_post}")
                self.stdout.write(self.style.SUCCESS(
                    f"  telegram_ok chat={getattr(chat, 'title', '')!r} "
                    f"type={getattr(chat, 'type', '')} bot_status={status}"
                ))
            except Exception as exc:
                failures.append(f"{center.pk}: {type(exc).__name__}: {exc}")

        if failures:
            raise CommandError("Telegram preflight failed: " + "; ".join(failures))

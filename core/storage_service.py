"""
Storage Archive Service

This service handles automatic archiving of order files and receipts to:
1. Compress files by branch/month into organized ZIP archives
2. Upload archives to center's Telegram channel
3. Clean up local storage after successful backup
4. Track archived files in database for easy retrieval
"""
import os
import hashlib
import time
import zipfile
import logging
import json
from datetime import datetime, timedelta
from pathlib import Path
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from bot.notification_service import get_bot_instance
from WowDash.archive_config import ArchiveConfig

logger = logging.getLogger(__name__)


class StorageArchiveService:
    """Service for managing file archives"""
    
    def __init__(self):
        self.media_root = Path(settings.MEDIA_ROOT)
        self.archive_dir = self.media_root / "archives"
        self.archive_dir.mkdir(exist_ok=True)
    
    def get_archivable_orders(self, center, age_days=None, min_size_mb=0):
        """
        Get orders that are eligible for archiving based on:
        - Completed orders older than age_days
        - Not already archived
        - Have files attached
        
        Args:
            center: Center instance
            age_days: Minimum age in days for orders to be archived (None = use config setting)
            min_size_mb: Minimum total size in MB (0 = no minimum)
        
        Returns:
            QuerySet of Order objects
        """
        from orders.models import Order
        
        # Use config setting if age_days not provided
        if age_days is None:
            age_days = ArchiveConfig.MIN_AGE_DAYS
        
        cutoff_date = timezone.now() - timedelta(days=age_days)
        
        # Get completed orders older than cutoff date
        orders = Order.objects.filter(
            branch__center=center,
            status='completed',
            completed_at__lt=cutoff_date,
        ).filter(
            Q(files__isnull=False)
            | Q(additional_files__isnull=False)
            | Q(recipt__isnull=False)
            | Q(receipts__file__isnull=False)
        ).exclude(
            # Exclude orders already archived
            archived_files__isnull=False
        ).select_related(
            "branch", "product", "language", "assigned_to__user"
        ).prefetch_related(
            "files", "additional_files", "receipts"
        ).distinct()
        
        # If minimum size specified, filter further
        if min_size_mb > 0:
            # This would require calculating actual file sizes
            # For now, we'll return all matching orders
            pass
        
        return orders
    
    def calculate_total_size(self, orders):
        """
        Calculate total size of all files in orders
        
        Args:
            orders: QuerySet of Order objects
        
        Returns:
            Total size in bytes
        """
        total_size = 0
        
        for order in orders:
            for _, _, field_file in self._iter_order_files(order):
                if self._field_file_exists(field_file):
                    total_size += os.path.getsize(field_file.path)
        
        return total_size
    
    def _field_file_exists(self, field_file):
        try:
            return bool(field_file and field_file.name and os.path.exists(field_file.path))
        except (NotImplementedError, ValueError, OSError):
            return False

    def _iter_order_files(self, order):
        """Yield every distinct local file belonging to an order."""
        seen = set()

        for kind, related in (
            ("primary", order.files.all()),
            ("additional", order.additional_files.all()),
        ):
            for index, media in enumerate(related, 1):
                field_file = media.file
                identity = (getattr(field_file, "storage", None), field_file.name)
                if field_file and field_file.name and identity not in seen:
                    seen.add(identity)
                    yield kind, index, field_file

        if order.recipt and order.recipt.name:
            identity = (getattr(order.recipt, "storage", None), order.recipt.name)
            if identity not in seen:
                seen.add(identity)
                yield "legacy_receipt", 1, order.recipt

        for index, receipt in enumerate(order.receipts.all(), 1):
            field_file = receipt.file
            identity = (getattr(field_file, "storage", None), field_file.name)
            if field_file and field_file.name and identity not in seen:
                seen.add(identity)
                yield "receipt", index, field_file

    def _sha256_file(self, path):
        digest = hashlib.sha256()
        with open(path, "rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def build_archive(self, center, orders, archive_name=None, compression_level=None):
        """
        Create a ZIP archive of orders organized by branch/order
        
        Archive structure (with Order IDs in filenames for easy identification):
        Archive_2026-01_Center_Name.zip
        ├── Branch_01_BranchName/
        │   ├── Order_12345/
        │   │   ├── Order_12345_details.json
        │   │   ├── Order_12345_file_001.pdf
        │   │   ├── Order_12345_file_002.jpg
        │   │   └── Order_12345_receipt.jpg
        │   └── Order_12346/
        │       ├── Order_12346_details.json
        │       ├── Order_12346_file_001.pdf
        │       └── Order_12346_receipt.jpg
        └── Branch_02_BranchName/
        
        NOTE: Order IDs are included in filenames so files can be searched/filtered
        by order number even after extraction from archive.
        
        Args:
            center: Center instance
            orders: QuerySet of Order objects
            archive_name: Custom archive name (optional)
            compression_level: ZIP compression level 0-9 (None = use center/global setting)
        
        Returns a path plus a checksum-protected source manifest.
        """
        if not archive_name:
            timestamp = timezone.now().strftime("%Y-%m")
            safe_center_name = self._sanitize_filename(center.name)
            archive_name = f"Archive_{timestamp}_{safe_center_name}.zip"
        
        archive_path = self.archive_dir / archive_name
        
        # Use provided compression or config default
        if compression_level is None:
            compression_level = ArchiveConfig.COMPRESSION_LEVEL
        
        manifest = {
            "version": 1,
            "center_id": center.id,
            "center_name": center.name,
            "created_at": timezone.now().isoformat(),
            "orders": [],
            "source_file_count": 0,
            "source_size_bytes": 0,
        }

        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=compression_level) as zipf:
            # Group orders by branch
            branches_dict = {}
            for order in orders:
                branch_id = order.branch.id if order.branch else 0
                if branch_id not in branches_dict:
                    branches_dict[branch_id] = []
                branches_dict[branch_id].append(order)
            
            # Process each branch
            for branch_id, branch_orders in branches_dict.items():
                if branch_id == 0:
                    branch_name = "No_Branch"
                else:
                    branch = branch_orders[0].branch
                    branch_name = f"Branch_{branch.id:02d}_{self._sanitize_filename(branch.name)}"
                
                # Process each order in branch
                for order in branch_orders:
                    order_number = order.get_order_number()
                    order_folder = f"{branch_name}/Order_{order_number:05d}"
                    
                    # Add order details JSON with order ID in filename
                    order_details = self._get_order_details(order)
                    details_json = json.dumps(order_details, indent=2, ensure_ascii=False, default=str)
                    zipf.writestr(f"{order_folder}/Order_{order_number:05d}_details.json", details_json)

                    order_manifest = {
                        "order_id": order.id,
                        "order_number": order_number,
                        "files": [],
                    }
                    for kind, index, field_file in self._iter_order_files(order):
                        if not self._field_file_exists(field_file):
                            continue
                        extension = os.path.splitext(field_file.name)[1]
                        arcname = (
                            f"{order_folder}/Order_{order_number:05d}_"
                            f"{kind}_{index:03d}{extension}"
                        )
                        size_bytes = os.path.getsize(field_file.path)
                        checksum = self._sha256_file(field_file.path)
                        zipf.write(field_file.path, arcname)
                        order_manifest["files"].append({
                            "kind": kind,
                            "source_name": field_file.name,
                            "archive_name": arcname,
                            "size_bytes": size_bytes,
                            "sha256": checksum,
                        })
                        manifest["source_file_count"] += 1
                        manifest["source_size_bytes"] += size_bytes
                    manifest["orders"].append(order_manifest)

            zipf.writestr(
                "archive_manifest.json",
                json.dumps(manifest, indent=2, ensure_ascii=False),
            )
        
        logger.info(f"Created archive: {archive_path} with {len(orders)} orders")
        return {
            "path": archive_path,
            "sha256": self._sha256_file(archive_path),
            "manifest": manifest,
            "source_file_count": manifest["source_file_count"],
            "source_size_bytes": manifest["source_size_bytes"],
            "archive_size_bytes": os.path.getsize(archive_path),
        }

    def create_archive(self, center, orders, archive_name=None, compression_level=None):
        """Backward-compatible path-only wrapper around :meth:`build_archive`."""
        return self.build_archive(
            center, orders, archive_name, compression_level
        )["path"]

    def _estimate_order_size(self, order):
        """Estimate total file size for a single order in bytes."""
        order_size = 0

        for _, _, field_file in self._iter_order_files(order):
            if self._field_file_exists(field_file):
                order_size += os.path.getsize(field_file.path)

        return order_size

    def _split_orders_by_size(self, orders_list, max_size_mb):
        """
        Split order list into batches so each batch stays within max_size_mb.
        Keeps at least one order per batch even if a single order exceeds limit.
        """
        if not orders_list:
            return []

        max_size_bytes = int(max_size_mb * 1024 * 1024)
        if max_size_bytes <= 0:
            return [orders_list]

        batches = []
        current_batch = []
        current_size = 0

        for order in orders_list:
            order_size = self._estimate_order_size(order)

            # Start a new batch if adding this order would exceed the limit.
            if current_batch and (current_size + order_size > max_size_bytes):
                batches.append(current_batch)
                current_batch = []
                current_size = 0

            current_batch.append(order)
            current_size += order_size

        if current_batch:
            batches.append(current_batch)

        return batches

    def _cleanup_expired_local_archives(self, center=None):
        """Delete expired local archive files and clear stale archive_path values."""
        retention_days = ArchiveConfig.LOCAL_RETENTION_DAYS
        if retention_days <= 0:
            return

        from core.models import FileArchive

        cutoff = timezone.now() - timedelta(days=retention_days)
        archives_qs = FileArchive.objects.filter(
            archive_path__isnull=False,
            archive_date__lt=cutoff,
        )
        if center is not None:
            archives_qs = archives_qs.filter(center=center)

        for archive in archives_qs:
            if archive.archive_path and os.path.exists(archive.archive_path):
                try:
                    os.remove(archive.archive_path)
                except Exception as e:
                    logger.warning(f"Failed to remove expired archive {archive.archive_path}: {e}")
                    continue

            archive.archive_path = None
            archive.save(update_fields=['archive_path'])
    
    def upload_to_telegram(self, center, archive_path, caption=None):
        """
        Upload archive to center's company orders Telegram channel
        
        Args:
            center: Center instance
            archive_path: Path to archive file
            caption: Custom caption for the file (optional)
        
        Returns ``(True, metadata)`` only when Telegram confirms the same file size.
        """
        try:
            bot = get_bot_instance(center.bot_token)
            # Use company_orders_channel_id for archives
            channel_id = center.company_orders_channel_id

            if not channel_id:
                logger.error(f"No company orders channel configured for center: {center.name}")
                return False, "No company orders channel configured"

            # Pre-flight size check — Telegram bot API hard limit is 50 MB
            TELEGRAM_BOT_MAX_BYTES = int(ArchiveConfig.MAX_SIZE_MB * 1024 * 1024)
            archive_size = os.path.getsize(archive_path)
            if archive_size > TELEGRAM_BOT_MAX_BYTES:
                error_msg = (
                    f"Archive too large for Telegram bot API "
                    f"({archive_size / (1024*1024):.1f} MB > {ArchiveConfig.MAX_SIZE_MB} MB limit): "
                    f"{os.path.basename(archive_path)}"
                )
                logger.error(error_msg)
                return False, error_msg
            
            # Prepare caption
            if not caption:
                file_size = os.path.getsize(archive_path)
                size_mb = file_size / (1024 * 1024)
                archive_name = os.path.basename(archive_path)
                caption = (
                    f"📦 <b>Storage Archive</b>\n\n"
                    f"📁 File: {archive_name}\n"
                    f"💾 Size: {size_mb:.2f} MB\n"
                    f"📅 Date: {timezone.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                    f"ℹ️ This archive contains completed orders with all files.\n"
                    f"📂 Files organized by branch and order number.\n"
                    f"🔍 All filenames include Order ID for easy searching."
                )
            
            # Upload file
            with open(archive_path, 'rb') as f:
                msg = bot.send_document(
                    channel_id,
                    f,
                    caption=caption,
                    parse_mode='HTML'
                )
            
            document = getattr(msg, "document", None)
            uploaded_size = getattr(document, "file_size", None)
            telegram_file_id = getattr(document, "file_id", "")
            if uploaded_size != archive_size or not telegram_file_id:
                return False, (
                    "Telegram upload could not be verified "
                    f"(local={archive_size}, remote={uploaded_size}, file_id={bool(telegram_file_id)})"
                )

            logger.info(f"Uploaded and verified archive on Telegram: {archive_path}")
            return True, {
                "message_id": msg.message_id,
                "file_id": telegram_file_id,
                "file_size": uploaded_size,
            }
            
        except Exception as e:
            logger.error(f"Failed to upload archive to Telegram: {e}")
            return False, str(e)
    
    def archive_orders(
        self,
        center,
        age_days=30,
        force=False,
        max_orders=None,
        split_size_mb=None,
        mode="inventory",
        created_by=None,
        order_ids=None,
    ):
        """
        Main archiving process:
        1. Find eligible orders
        2. Create archive(s) - splits if too large
        3. Upload to Telegram
        4. Mark orders as archived
        5. Clean up local files
        
        Args:
            center: Center instance
            age_days: Minimum age in days for orders to be archived
            force: Force archiving even if below size threshold
            max_orders: Maximum number of orders per archive (for splitting)
            split_size_mb: Split archives if exceeding this size in MB
        
        Returns:
            Dict with results
        """
        from core.models import ArchiveRun, FileArchive

        if mode not in {ArchiveRun.MODE_INVENTORY, ArchiveRun.MODE_CANARY, ArchiveRun.MODE_LIVE}:
            raise ValueError(f"Unknown archive mode: {mode}")

        delete_after_verified = mode == ArchiveRun.MODE_LIVE and ArchiveConfig.DELETE_LOCAL_FILES
        run = ArchiveRun.objects.create(
            center=center,
            mode=mode,
            age_days=age_days,
            delete_after_verified=delete_after_verified,
            created_by=created_by,
        )

        result = {
            'success': False,
            'run_id': run.id,
            'mode': mode,
            'orders_count': 0,
            'archive_size': 0,
            'archive_name': None,
            'message_id': None,
            'error': None,
            'archives_created': []
        }

        if mode != ArchiveRun.MODE_INVENTORY:
            from bot.access import center_can_archive

            if not center_can_archive(center):
                result['error'] = "Maintenance archival is disabled or incomplete for this center"
                run.status = ArchiveRun.STATUS_FAILED
                run.error = result['error']
                run.completed_at = timezone.now()
                run.save(update_fields=["status", "error", "completed_at"])
                return result
        
        try:
            # Keep local archive records in sync with retention policy.
            self._cleanup_expired_local_archives(center=center)

            # Get archivable orders
            orders = self.get_archivable_orders(center, age_days)
            if order_ids is not None:
                orders = orders.filter(pk__in=order_ids)
            
            orders_list = list(orders)
            run.orders_found = len(orders_list)

            if not orders_list:
                run.status = ArchiveRun.STATUS_COMPLETED
                run.completed_at = timezone.now()
                run.save(update_fields=["orders_found", "status", "completed_at"])
                result.update(success=True, error=None)
                return result
            
            # Check total size
            total_size = self.calculate_total_size(orders_list)
            total_file_count = sum(
                1
                for order in orders_list
                for _, _, field_file in self._iter_order_files(order)
                if self._field_file_exists(field_file)
            )
            run.source_size_bytes = total_size
            run.source_file_count = total_file_count
            run.save(update_fields=["orders_found", "source_size_bytes", "source_file_count"])
            size_mb = total_size / (1024 * 1024)

            if mode == ArchiveRun.MODE_INVENTORY:
                run.status = ArchiveRun.STATUS_COMPLETED
                run.completed_at = timezone.now()
                run.save(update_fields=["status", "completed_at"])
                result.update(
                    success=True,
                    archive_size=total_size,
                    inventory={
                        "orders": len(orders_list),
                        "files": total_file_count,
                        "size_bytes": total_size,
                    },
                )
                return result
            
            # Check if meets minimum size threshold (from config)
            min_size_mb = ArchiveConfig.MIN_SIZE_MB
            
            if not force and size_mb < min_size_mb:
                result['error'] = f"Total size ({size_mb:.2f} MB) below threshold ({min_size_mb} MB)"
                run.status = ArchiveRun.STATUS_COMPLETED
                run.error = result['error']
                run.completed_at = timezone.now()
                run.save(update_fields=["status", "error", "completed_at"])
                return result
            
            # Determine if we need to split archives
            max_size_mb = split_size_mb or ArchiveConfig.MAX_SIZE_MB
            # First split by order count if configured.
            if max_orders:
                initial_batches = [orders_list[i:i + max_orders] for i in range(0, len(orders_list), max_orders)]
            elif ArchiveConfig.MAX_ORDERS_PER_BATCH > 0:
                batch_size = ArchiveConfig.MAX_ORDERS_PER_BATCH
                initial_batches = [orders_list[i:i + batch_size] for i in range(0, len(orders_list), batch_size)]
            else:
                initial_batches = [orders_list]

            # Then enforce archive file size limits.
            batches = []
            for initial_batch in initial_batches:
                batches.extend(self._split_orders_by_size(initial_batch, max_size_mb))
            
            total_archived = 0
            total_deleted = 0
            had_failure = False
            
            for batch_idx, batch_orders in enumerate(batches):
                # Include the immutable run ID so retries and later runs never
                # overwrite a retained failed/manual archive with the same part
                # number.
                timestamp = timezone.now().strftime("%Y-%m")
                safe_center_name = self._sanitize_filename(center.name)
                archive_name = f"Archive_{timestamp}_{safe_center_name}_Run{run.pk}"
                if len(batches) > 1:
                    archive_name += f"_Part{batch_idx + 1}"
                archive_name += ".zip"
                
                build = self.build_archive(center, batch_orders, archive_name)
                archive_path = build["path"]
                archive_size = build["archive_size_bytes"]
                archive_size_mb = archive_size / (1024 * 1024)
                
                # Generate summary caption
                batch_total_size = build["source_size_bytes"]
                caption = self._generate_archive_caption(center, batch_orders, batch_total_size)
                if len(batches) > 1:
                    caption += f"\n📦 Part {batch_idx + 1} of {len(batches)}"
                
                if archive_size > int(ArchiveConfig.MAX_SIZE_MB * 1024 * 1024):
                    FileArchive.objects.create(
                        center=center,
                        run=run,
                        archive_name=os.path.basename(archive_path),
                        archive_path=str(archive_path),
                        telegram_channel_id=center.company_orders_channel_id or "",
                        total_orders=len(batch_orders),
                        total_size_bytes=archive_size,
                        sha256=build["sha256"],
                        manifest=build["manifest"],
                        source_file_count=build["source_file_count"],
                        source_size_bytes=build["source_size_bytes"],
                        verification_status=FileArchive.VERIFICATION_MANUAL,
                        last_error="Archive exceeds automatic Telegram upload limit",
                    )
                    had_failure = True
                    result['error'] = "One or more archives require administrator-assisted upload"
                    continue

                success = False
                upload_result = None
                upload_attempts = 0
                for upload_attempts in range(1, 4):
                    success, upload_result = self.upload_to_telegram(center, archive_path, caption)
                    if success:
                        break
                    if upload_attempts < 3 and not getattr(settings, "TESTING", False):
                        time.sleep(2 ** (upload_attempts - 1))

                if not success:
                    FileArchive.objects.create(
                        center=center,
                        run=run,
                        archive_name=os.path.basename(archive_path),
                        archive_path=str(archive_path),
                        telegram_channel_id=center.company_orders_channel_id or "",
                        total_orders=len(batch_orders),
                        total_size_bytes=archive_size,
                        sha256=build["sha256"],
                        manifest=build["manifest"],
                        source_file_count=build["source_file_count"],
                        source_size_bytes=build["source_size_bytes"],
                        upload_attempts=upload_attempts,
                        verification_status=FileArchive.VERIFICATION_FAILED,
                        last_error=str(upload_result),
                    )
                    had_failure = True
                    result['error'] = f"Failed to upload part {batch_idx + 1}: {upload_result}"
                    continue

                with transaction.atomic():
                    archive = FileArchive.objects.create(
                        center=center,
                        run=run,
                        archive_name=os.path.basename(archive_path),
                        archive_path=str(archive_path),
                        telegram_message_id=upload_result["message_id"],
                        telegram_file_id=upload_result["file_id"],
                        telegram_channel_id=center.company_orders_channel_id,
                        total_orders=len(batch_orders),
                        total_size_bytes=archive_size,
                        sha256=build["sha256"],
                        manifest=build["manifest"],
                        source_file_count=build["source_file_count"],
                        source_size_bytes=build["source_size_bytes"],
                        uploaded_size_bytes=upload_result["file_size"],
                        upload_attempts=upload_attempts,
                        verification_status=FileArchive.VERIFICATION_VERIFIED,
                        verified_at=timezone.now(),
                    )
                    from orders.models import Order
                    Order.objects.filter(pk__in=[order.pk for order in batch_orders]).update(
                        archived_files=archive
                    )
                
                total_archived += len(batch_orders)
                result['archives_created'].append({
                    'name': archive.archive_name,
                    'orders': len(batch_orders),
                    'size_mb': archive_size_mb,
                    'message_id': upload_result["message_id"],
                    'sha256': build["sha256"],
                })
                
                if delete_after_verified:
                    deleted_count, failed_count = self._cleanup_local_files(batch_orders)
                    total_deleted += deleted_count
                    if failed_count == 0:
                        archive.files_deleted_at = timezone.now()
                        archive.save(update_fields=["files_deleted_at"])
                    else:
                        archive.last_error = f"Failed to delete {failed_count} local source file(s)"
                        archive.save(update_fields=["last_error"])
                        had_failure = True
                    logger.info(
                        "Deleted %s local files from batch %s (%s failed)",
                        deleted_count,
                        batch_idx + 1,
                        failed_count,
                    )
                
                # Keep or delete local archive file based on retention policy.
                if os.path.exists(archive_path):
                    if ArchiveConfig.LOCAL_RETENTION_DAYS <= 0:
                        os.remove(archive_path)
                        archive.archive_path = None
                        archive.save(update_fields=['archive_path'])
                        logger.info(f"Deleted local archive file: {archive_path}")
                    else:
                        logger.info(
                            f"Retained local archive for {ArchiveConfig.LOCAL_RETENTION_DAYS} days: {archive_path}"
                        )
            
            result.update({
                'success': not had_failure,
                'orders_count': total_archived,
                'archive_size': total_size,
                'archive_name': result['archives_created'][0]['name'] if result['archives_created'] else None,
                'message_id': result['archives_created'][0]['message_id'] if result['archives_created'] else None
            })

            run.orders_archived = total_archived
            run.deleted_file_count = total_deleted
            run.status = ArchiveRun.STATUS_PARTIAL if had_failure else ArchiveRun.STATUS_COMPLETED
            run.error = result['error'] or ""
            run.completed_at = timezone.now()
            run.save(update_fields=[
                "orders_archived", "deleted_file_count", "status", "error", "completed_at"
            ])
            logger.info(f"Successfully archived {total_archived} orders in {len(batches)} archive(s) for center {center.name}")
            
        except Exception as e:
            logger.error(f"Error in archive_orders: {e}", exc_info=True)
            result['error'] = str(e)
            run.status = ArchiveRun.STATUS_FAILED
            run.error = str(e)
            run.completed_at = timezone.now()
            run.save(update_fields=["status", "error", "completed_at"])
        
        return result
    
    def _cleanup_local_files(self, orders):
        """
        Delete local files for archived orders
        
        Args:
            orders: QuerySet of Order objects
        
        Returns:
            Number of files deleted
        """
        deleted_count = 0
        failed_count = 0
        deleted_names = set()

        for order in orders:
            for _, _, field_file in self._iter_order_files(order):
                if not self._field_file_exists(field_file) or field_file.name in deleted_names:
                    continue
                try:
                    field_file.storage.delete(field_file.name)
                    deleted_names.add(field_file.name)
                    deleted_count += 1
                except Exception as e:
                    failed_count += 1
                    logger.warning(f"Failed to delete archived source {field_file.name}: {e}")

        return deleted_count, failed_count
    
    def _generate_archive_caption(self, center, orders, total_size):
        """Generate detailed caption for archive upload"""
        size_mb = total_size / (1024 * 1024)
        orders_count = len(orders) if isinstance(orders, list) else orders.count()
        
        # Count by branch
        branch_counts = {}
        for order in orders:
            branch_name = order.branch.name if order.branch else "No Branch"
            branch_counts[branch_name] = branch_counts.get(branch_name, 0) + 1
        
        branch_summary = "\n".join([f"  • {name}: {count} orders" for name, count in branch_counts.items()])
        
        caption = (
            f"📦 <b>Storage Archive</b>\n\n"
            f"🏢 Center: {center.name}\n"
            f"📅 Archive Date: {timezone.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"📋 Total Orders: {orders_count}\n"
            f"💾 Total Size: {size_mb:.2f} MB\n\n"
            f"<b>Orders by Branch:</b>\n{branch_summary}\n\n"
            f"ℹ️ Download and unzip to access files.\n"
            f"📂 Files are organized by: Branch/Order_XXXXX/\n"
            f"🔍 All filenames include Order ID for easy searching"
        )
        
        return caption
    
    def _get_order_details(self, order):
        """Extract order details for JSON export"""
        return {
            'order_id': order.id,
            'order_number': order.get_order_number(),
            'customer_name': order.get_customer_display_name(),
            'customer_phone': order.get_customer_phone(),
            'product': order.product.name,
            'language': order.language.name if order.language else None,
            'total_pages': order.total_pages,
            'copy_number': order.copy_number,
            'total_price': float(order.total_price),
            'payment_type': order.payment_type,
            'status': order.status,
            'created_at': order.created_at.isoformat(),
            'completed_at': order.completed_at.isoformat() if order.completed_at else None,
            'branch': order.branch.name if order.branch else None,
            'assigned_to': order.assigned_to.user.get_full_name() if order.assigned_to else None,
            'description': order.description or ''
        }
    
    def _sanitize_filename(self, filename):
        """Sanitize filename for safe use in archive paths"""
        # Remove/replace problematic characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename[:50]  # Limit length

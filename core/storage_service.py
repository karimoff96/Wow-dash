"""
Storage Archive Service

This service handles automatic archiving of order files and receipts to:
1. Compress files by branch/month into organized ZIP archives
2. Upload archives to center's Telegram channel
3. Clean up local storage after successful backup
4. Track archived files in database for easy retrieval
"""
import os
import zipfile
import logging
import json
from datetime import datetime, timedelta
from pathlib import Path
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, Count, Q
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
            files__isnull=False  # Has files
        ).exclude(
            # Exclude orders already archived
            archived_files__isnull=False
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
            # Order media files
            for media in order.files.all():
                if media.file and os.path.exists(media.file.path):
                    total_size += os.path.getsize(media.file.path)
            
            # Receipt file
            if order.recipt and os.path.exists(order.recipt.path):
                total_size += os.path.getsize(order.recipt.path)
        
        return total_size
    
    def create_archive(self, center, orders, archive_name=None, compression_level=None):
        """
        Create a ZIP archive of orders organized by branch/order
        
        Archive structure:
        Archive_2026-01_Center_Name.zip
        ├── Branch_01_BranchName/
        │   ├── Order_12345/
        │   │   ├── order_details.json
        │   │   ├── file_001.pdf
        │   │   ├── file_002.jpg
        │   │   └── receipt.jpg
        │   └── Order_12346/
        └── Branch_02_BranchName/
        
        Args:
            center: Center instance
            orders: QuerySet of Order objects
            archive_name: Custom archive name (optional)
            compression_level: ZIP compression level 0-9 (None = use center/global setting)
        
        Returns:
            Path to created archive file
        """
        if not archive_name:
            timestamp = timezone.now().strftime("%Y-%m")
            safe_center_name = self._sanitize_filename(center.name)
            archive_name = f"Archive_{timestamp}_{safe_center_name}.zip"
        
        archive_path = self.archive_dir / archive_name
        
        # Use provided compression or config default
        if compression_level is None:
            compression_level = ArchiveConfig.COMPRESSION_LEVEL
        
        # Create archive with optimized compression
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
                    order_folder = f"{branch_name}/Order_{order.get_order_number():05d}"
                    
                    # Add order details JSON
                    order_details = self._get_order_details(order)
                    details_json = json.dumps(order_details, indent=2, ensure_ascii=False, default=str)
                    zipf.writestr(f"{order_folder}/order_details.json", details_json)
                    
                    # Add order media files
                    for idx, media in enumerate(order.files.all(), 1):
                        if media.file and os.path.exists(media.file.path):
                            file_ext = os.path.splitext(media.file.name)[1]
                            arcname = f"{order_folder}/file_{idx:03d}{file_ext}"
                            zipf.write(media.file.path, arcname)
                    
                    # Add receipt if exists
                    if order.recipt and os.path.exists(order.recipt.path):
                        receipt_ext = os.path.splitext(order.recipt.name)[1]
                        arcname = f"{order_folder}/receipt{receipt_ext}"
                        zipf.write(order.recipt.path, arcname)
        
        logger.info(f"Created archive: {archive_path} with {len(orders)} orders")
        return archive_path
    
    def upload_to_telegram(self, center, archive_path, caption=None):
        """
        Upload archive to center's company orders Telegram channel
        
        Args:
            center: Center instance
            archive_path: Path to archive file
            caption: Custom caption for the file (optional)
        
        Returns:
            Tuple of (success: bool, message_id or error_message)
        """
        try:
            bot = get_bot_instance(center.bot_token)
            # Use company_orders_channel_id for archives
            channel_id = center.company_orders_channel_id
            
            if not channel_id:
                logger.error(f"No company orders channel configured for center: {center.name}")
                return False, "No company orders channel configured"
            
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
                    f"Download and unzip to access files by branch and order number."
                )
            
            # Upload file
            with open(archive_path, 'rb') as f:
                msg = bot.send_document(
                    channel_id,
                    f,
                    caption=caption,
                    parse_mode='HTML'
                )
            
            logger.info(f"Uploaded archive to Telegram: {archive_path}")
            return True, msg.message_id
            
        except Exception as e:
            logger.error(f"Failed to upload archive to Telegram: {e}")
            return False, str(e)
    
    @transaction.atomic
    def archive_orders(self, center, age_days=30, force=False, max_orders=None, split_size_mb=None):
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
        result = {
            'success': False,
            'orders_count': 0,
            'archive_size': 0,
            'archive_name': None,
            'message_id': None,
            'error': None,
            'archives_created': []
        }
        
        try:
            # Get archivable orders
            orders = self.get_archivable_orders(center, age_days)
            
            if not orders.exists():
                result['error'] = "No orders to archive"
                return result
            
            # Check total size
            total_size = self.calculate_total_size(orders)
            size_mb = total_size / (1024 * 1024)
            
            # Check if meets minimum size threshold (from config)
            min_size_mb = ArchiveConfig.MIN_SIZE_MB
            
            if not force and size_mb < min_size_mb:
                result['error'] = f"Total size ({size_mb:.2f} MB) below threshold ({min_size_mb} MB)"
                return result
            
            # Determine if we need to split archives
            max_size_mb = split_size_mb or ArchiveConfig.MAX_SIZE_MB
            orders_list = list(orders)
            
            # Split into batches if needed
            if max_orders:
                batches = [orders_list[i:i + max_orders] for i in range(0, len(orders_list), max_orders)]
            elif ArchiveConfig.MAX_ORDERS_PER_BATCH > 0:
                batch_size = ArchiveConfig.MAX_ORDERS_PER_BATCH
                batches = [orders_list[i:i + batch_size] for i in range(0, len(orders_list), batch_size)]
            else:
                batches = [orders_list]
            
            total_archived = 0
            
            for batch_idx, batch_orders in enumerate(batches):
                # Create batch archive name
                if len(batches) > 1:
                    timestamp = timezone.now().strftime("%Y-%m")
                    safe_center_name = self._sanitize_filename(center.name)
                    archive_name = f"Archive_{timestamp}_{safe_center_name}_Part{batch_idx + 1}.zip"
                else:
                    archive_name = None
                
                # Create archive
                archive_path = self.create_archive(center, batch_orders, archive_name)
                
                # Check archive size
                archive_size = os.path.getsize(archive_path)
                archive_size_mb = archive_size / (1024 * 1024)
                
                # Generate summary caption
                caption = self._generate_archive_caption(center, batch_orders, self.calculate_total_size(batch_orders))
                if len(batches) > 1:
                    caption += f"\n📦 Part {batch_idx + 1} of {len(batches)}"
                
                # Upload to Telegram
                success, msg_id_or_error = self.upload_to_telegram(center, archive_path, caption)
                
                if not success:
                    result['error'] = f"Failed to upload part {batch_idx + 1}: {msg_id_or_error}"
                    # Clean up local archive
                    if os.path.exists(archive_path):
                        os.remove(archive_path)
                    return result
                
                # Create FileArchive record
                from core.models import FileArchive
                archive = FileArchive.objects.create(
                    center=center,
                    archive_name=os.path.basename(archive_path),
                    archive_path=str(archive_path),
                    telegram_message_id=msg_id_or_error,
                    telegram_channel_id=center.company_orders_channel_id,
                    total_orders=len(batch_orders),
                    total_size_bytes=self.calculate_total_size(batch_orders),
                    archive_date=timezone.now()
                )
                
                # Link orders to archive
                for order in batch_orders:
                    order.archived_files = archive
                    order.save(update_fields=['archived_files'])
                
                total_archived += len(batch_orders)
                result['archives_created'].append({
                    'name': archive.archive_name,
                    'orders': len(batch_orders),
                    'size_mb': archive_size_mb,
                    'message_id': msg_id_or_error
                })
                
                # Clean up local files for this batch
                if ArchiveConfig.DELETE_LOCAL_FILES:
                    deleted_count = self._cleanup_local_files(batch_orders)
                    logger.info(f"Deleted {deleted_count} local files from batch {batch_idx + 1}")
                
                # Delete local archive file (already uploaded to Telegram)
                if os.path.exists(archive_path):
                    os.remove(archive_path)
                    logger.info(f"Deleted local archive file: {archive_path}")
            
            result.update({
                'success': True,
                'orders_count': total_archived,
                'archive_size': total_size,
                'archive_name': result['archives_created'][0]['name'] if result['archives_created'] else None,
                'message_id': result['archives_created'][0]['message_id'] if result['archives_created'] else None
            })
            
            logger.info(f"Successfully archived {total_archived} orders in {len(batches)} archive(s) for center {center.name}")
            
        except Exception as e:
            logger.error(f"Error in archive_orders: {e}", exc_info=True)
            result['error'] = str(e)
        
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
        
        for order in orders:
            # Delete order media files
            for media in order.files.all():
                if media.file and os.path.exists(media.file.path):
                    try:
                        os.remove(media.file.path)
                        deleted_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to delete file {media.file.path}: {e}")
            
            # Delete receipt
            if order.recipt and os.path.exists(order.recipt.path):
                try:
                    os.remove(order.recipt.path)
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f"Failed to delete receipt {order.recipt.path}: {e}")
        
        return deleted_count
    
    def _generate_archive_caption(self, center, orders, total_size):
        """Generate detailed caption for archive upload"""
        size_mb = total_size / (1024 * 1024)
        
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
            f"📋 Total Orders: {orders.count()}\n"
            f"💾 Total Size: {size_mb:.2f} MB\n\n"
            f"<b>Orders by Branch:</b>\n{branch_summary}\n\n"
            f"ℹ️ Download and unzip to access files.\n"
            f"Files are organized by: Branch/Order_XXXXX/"
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
            'assigned_to': order.assigned_to.get_full_name() if order.assigned_to else None,
            'description': order.description or ''
        }
    
    def _sanitize_filename(self, filename):
        """Sanitize filename for safe use in archive paths"""
        # Remove/replace problematic characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename[:50]  # Limit length

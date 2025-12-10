"""
Excel Export Service for Reports

Provides multi-sheet Excel export functionality for all report pages.
Supports:
- Multi-tenant data isolation
- Filter-aware exports
- Multiple sheets per export
- Proper data typing (dates, decimals, numbers)
- Performance optimization for large datasets

Dependencies: openpyxl
"""

import io
from datetime import datetime, date
from decimal import Decimal
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass

from django.db.models import Sum, Count, Avg, F, DecimalField
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.utils import timezone

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    OPENPYXL_AVAILABLE = True
    
    # Styling constants - only defined if openpyxl is available
    HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
    HEADER_FILL = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center", wrap_text=True)
    CELL_ALIGNMENT = Alignment(vertical="center", wrap_text=True)
    THIN_BORDER = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
except ImportError:
    OPENPYXL_AVAILABLE = False
    # Define dummy constants to prevent NameError
    HEADER_FONT = None
    HEADER_FILL = None
    HEADER_ALIGNMENT = None
    CELL_ALIGNMENT = None
    THIN_BORDER = None

from orders.models import Order
from accounts.models import BotUser
from organizations.models import Branch, TranslationCenter, AdminUser
from organizations.rbac import get_user_orders, get_user_customers, get_user_branches

# Status display mappings
STATUS_LABELS = {
    "pending": "Pending",
    "payment_pending": "Awaiting",
    "payment_received": "Received",
    "payment_confirmed": "Confirmed",
    "in_progress": "In Process",
    "ready": "Ready",
    "completed": "Done",
    "cancelled": "Cancelled",
}

PAYMENT_TYPE_LABELS = {
    "cash": "Cash",
    "card": "Card",
    "transfer": "Transfer",
    "": "Not Set",
    None: "Not Set",
}


@dataclass
class SheetConfig:
    """Configuration for a single Excel sheet"""
    name: str
    headers: List[str]
    data: List[List[Any]]
    column_widths: Optional[List[int]] = None


class ExcelExporter:
    """
    Main Excel export class with multi-sheet support.
    
    Usage:
        exporter = ExcelExporter()
        exporter.add_sheet(SheetConfig(...))
        response = exporter.generate_response("filename.xlsx")
    """
    
    def __init__(self):
        if not OPENPYXL_AVAILABLE:
            raise ImportError("openpyxl is required for Excel export. Install with: pip install openpyxl")
        self.workbook = Workbook()
        # Remove default sheet
        self.workbook.remove(self.workbook.active)
        self.sheets: List[SheetConfig] = []
    
    def add_sheet(self, config: SheetConfig):
        """Add a sheet configuration to be rendered"""
        self.sheets.append(config)
    
    def _format_cell_value(self, value: Any) -> Any:
        """Format cell value to appropriate Excel type"""
        if value is None:
            return ""
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, datetime):
            return value.replace(tzinfo=None) if value.tzinfo else value
        if isinstance(value, date):
            return value
        if isinstance(value, bool):
            return "Yes" if value else "No"
        return value
    
    def _auto_column_width(self, ws, col_idx: int, values: List[Any], header: str) -> int:
        """Calculate auto column width based on content"""
        max_length = len(str(header))
        for value in values[:100]:  # Check first 100 rows for performance
            cell_length = len(str(value)) if value else 0
            max_length = max(max_length, cell_length)
        # Add padding and cap at reasonable max
        return min(max(max_length + 2, 10), 50)
    
    def _render_sheet(self, config: SheetConfig):
        """Render a single sheet from configuration"""
        ws = self.workbook.create_sheet(title=config.name[:31])  # Excel sheet name limit
        
        # Write headers
        for col_idx, header in enumerate(config.headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = HEADER_ALIGNMENT
            cell.border = THIN_BORDER
        
        # Write data rows
        for row_idx, row_data in enumerate(config.data, 2):
            for col_idx, value in enumerate(row_data, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=self._format_cell_value(value))
                cell.alignment = CELL_ALIGNMENT
                cell.border = THIN_BORDER
                
                # Apply number format for decimals/money
                if isinstance(value, (Decimal, float)) and col_idx > 0:
                    header_lower = config.headers[col_idx - 1].lower()
                    if any(x in header_lower for x in ['price', 'revenue', 'amount', 'sum', 'total', 'paid', 'remaining']):
                        cell.number_format = '#,##0.00'
                    elif 'rate' in header_lower or '%' in header_lower:
                        cell.number_format = '0.0%' if value < 1 else '0.0'
        
        # Set column widths
        if config.column_widths:
            for col_idx, width in enumerate(config.column_widths, 1):
                ws.column_dimensions[get_column_letter(col_idx)].width = width
        else:
            # Auto-calculate widths
            for col_idx, header in enumerate(config.headers, 1):
                col_values = [row[col_idx - 1] if len(row) > col_idx - 1 else "" for row in config.data]
                width = self._auto_column_width(ws, col_idx, col_values, header)
                ws.column_dimensions[get_column_letter(col_idx)].width = width
        
        # Freeze header row
        ws.freeze_panes = "A2"
    
    def render(self):
        """Render all sheets"""
        for config in self.sheets:
            self._render_sheet(config)
    
    def generate_response(self, filename: str) -> HttpResponse:
        """Generate HTTP response with Excel file"""
        self.render()
        
        # Write to buffer
        buffer = io.BytesIO()
        self.workbook.save(buffer)
        buffer.seek(0)
        
        # Create response
        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    
    def is_empty(self) -> bool:
        """Check if all sheets are empty"""
        return all(len(config.data) == 0 for config in self.sheets)
    
    def to_bytes(self) -> bytes:
        """Generate Excel file and return as bytes"""
        self.render()
        buffer = io.BytesIO()
        self.workbook.save(buffer)
        buffer.seek(0)
        return buffer.getvalue()


class ReportExporter:
    """
    Main Report Export facade class.
    
    Wraps all individual report export functions and provides a unified interface
    for exporting any report type with filters.
    
    Usage:
        exporter = ReportExporter(request.user)
        result = exporter.export('orders', {'period': 'month', 'branch_id': 1})
        
        if result['success']:
            # result['file_content'] is the Excel bytes
            # result['filename'] is the suggested filename
        else:
            # result['message'] contains error/warning message
    """
    
    def __init__(self, user):
        self.user = user
    
    def _parse_date_filters(self, filters: Dict) -> tuple:
        """Parse date range from filter parameters"""
        from datetime import timedelta
        
        period = filters.get('period', 'month')
        custom_from = filters.get('date_from')
        custom_to = filters.get('date_to')
        
        today = timezone.now()
        
        if period == 'today':
            date_from = today.replace(hour=0, minute=0, second=0, microsecond=0)
            date_to = today
        elif period == 'yesterday':
            yesterday = today - timedelta(days=1)
            date_from = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            date_to = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif period == 'week':
            start_of_week = today - timedelta(days=today.weekday())
            date_from = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
            date_to = today
        elif period == 'quarter':
            quarter = (today.month - 1) // 3
            start_month = quarter * 3 + 1
            date_from = today.replace(month=start_month, day=1, hour=0, minute=0, second=0, microsecond=0)
            date_to = today
        elif period == 'year':
            date_from = today.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            date_to = today
        elif period == 'custom' and custom_from and custom_to:
            try:
                if isinstance(custom_from, str):
                    date_from = datetime.strptime(custom_from, '%Y-%m-%d')
                    date_from = timezone.make_aware(date_from.replace(hour=0, minute=0, second=0))
                else:
                    date_from = custom_from
                if isinstance(custom_to, str):
                    date_to = datetime.strptime(custom_to, '%Y-%m-%d')
                    date_to = timezone.make_aware(date_to.replace(hour=23, minute=59, second=59))
                else:
                    date_to = custom_to
            except ValueError:
                # Fallback to month
                date_from = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                date_to = today
        else:
            # Default: month
            date_from = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            date_to = today
        
        return date_from, date_to
    
    def export(self, report_type: str, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Export the specified report type with given filters.
        
        Args:
            report_type: One of 'orders', 'financial', 'staff_performance', 
                        'branch_comparison', 'customers', 'unit_economy', 'my_statistics'
            filters: Dict with filter parameters (period, date_from, date_to, branch_id, center_id, etc.)
        
        Returns:
            Dict with keys:
                - success: bool
                - file_content: bytes (if success)
                - filename: str (if success)
                - message: str (error/warning message)
        """
        if filters is None:
            filters = {}
        
        try:
            # Parse date range
            date_from, date_to = self._parse_date_filters(filters)
            
            # Extract common filters
            branch_id = filters.get('branch_id')
            center_id = filters.get('center_id')
            status_filter = filters.get('status')
            
            # Call appropriate export function
            if report_type == 'orders':
                response = export_orders_report(
                    self.user, date_from, date_to, branch_id, center_id, status_filter
                )
            elif report_type == 'financial':
                response = export_financial_report(
                    self.user, date_from, date_to, branch_id, center_id
                )
            elif report_type == 'staff_performance':
                response = export_staff_performance(
                    self.user, date_from, date_to, branch_id, center_id
                )
            elif report_type == 'branch_comparison':
                response = export_branch_comparison(
                    self.user, date_from, date_to, center_id
                )
            elif report_type == 'customers':
                response = export_customer_analytics(
                    self.user, date_from, date_to, branch_id, center_id
                )
            elif report_type == 'unit_economy':
                response = export_unit_economy(
                    self.user, branch_id, center_id
                )
            elif report_type == 'my_statistics':
                response = export_my_statistics(
                    self.user, date_from, date_to
                )
            else:
                return {
                    'success': False,
                    'message': f'Unknown report type: {report_type}'
                }
            
            # Extract file content and filename from HttpResponse
            file_content = response.content
            filename = response['Content-Disposition'].split('filename="')[1].rstrip('"')
            
            # Check if empty (no data)
            if len(file_content) < 1000:  # Very small file likely means empty
                return {
                    'success': False,
                    'message': 'No data found for the selected filters. Try adjusting your date range or filters.'
                }
            
            return {
                'success': True,
                'file_content': file_content,
                'filename': filename,
                'message': 'Export generated successfully'
            }
            
        except ImportError as e:
            return {
                'success': False,
                'message': 'Excel export is not available. Please install openpyxl: pip install openpyxl'
            }
        except Exception as e:
            import logging
            logging.getLogger(__name__).exception(f"Export error for {report_type}")
            return {
                'success': False,
                'message': f'Export failed: {str(e)}'
            }


# ============ Report-Specific Export Functions ============

def export_orders_report(
    user,
    date_from: datetime,
    date_to: datetime,
    branch_id: Optional[str] = None,
    center_id: Optional[str] = None,
    status_filter: Optional[str] = None,
) -> HttpResponse:
    """
    Export Orders Report with multiple sheets:
    - Orders (Detailed)
    - Status Breakdown
    - Language Breakdown
    - Daily Summary
    """
    exporter = ExcelExporter()
    
    # Get filtered orders
    orders = get_user_orders(user).filter(
        created_at__gte=date_from,
        created_at__lte=date_to
    ).select_related('bot_user', 'product', 'product__category', 'branch', 'assigned_to__user', 'language')
    
    if center_id:
        orders = orders.filter(branch__center_id=center_id)
    if branch_id:
        orders = orders.filter(branch_id=branch_id)
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    # Sheet 1: Detailed Orders
    orders_data = []
    for order in orders.order_by('-created_at'):
        orders_data.append([
            order.id,
            order.created_at,
            order.bot_user.name if order.bot_user else "N/A",
            order.bot_user.phone if order.bot_user else "N/A",
            "B2B" if (order.bot_user and order.bot_user.is_agency) else "B2C",
            order.product.name if order.product else "N/A",
            order.product.category.name if (order.product and order.product.category) else "N/A",
            order.language.name if order.language else "N/A",
            order.total_pages or 0,
            order.copy_number or 0,
            order.total_price or 0,
            order.received or 0,
            (order.total_price or 0) - (order.received or 0),
            STATUS_LABELS.get(order.status, order.status),
            PAYMENT_TYPE_LABELS.get(order.payment_type, order.payment_type or "N/A"),
            order.branch.name if order.branch else "N/A",
            order.assigned_to.user.get_full_name() if order.assigned_to else "Unassigned",
            order.completed_at if order.completed_at else None,
        ])
    
    exporter.add_sheet(SheetConfig(
        name="Orders (Detailed)",
        headers=[
            "Order ID", "Created At", "Customer Name", "Phone", "Customer Type",
            "Product", "Category", "Language", "Pages", "Copies",
            "Total Price", "Paid Amount", "Remaining", "Status", "Payment Type",
            "Branch", "Assigned To", "Completed At"
        ],
        data=orders_data
    ))
    
    # Sheet 2: Status Breakdown
    status_breakdown = orders.values('status').annotate(
        count=Count('id'),
        revenue=Coalesce(Sum('total_price'), Decimal('0'), output_field=DecimalField()),
        paid=Coalesce(Sum('received'), Decimal('0'), output_field=DecimalField())
    ).order_by('-count')
    
    status_data = []
    for item in status_breakdown:
        status_data.append([
            STATUS_LABELS.get(item['status'], item['status']),
            item['count'],
            float(item['revenue'] or 0),
            float(item['paid'] or 0),
            float((item['revenue'] or 0) - (item['paid'] or 0)),
        ])
    
    exporter.add_sheet(SheetConfig(
        name="Status Breakdown",
        headers=["Status", "Orders Count", "Total Revenue", "Paid Amount", "Outstanding"],
        data=status_data
    ))
    
    # Sheet 3: Language Breakdown
    lang_breakdown = orders.values('language__name').annotate(
        count=Count('id'),
        revenue=Coalesce(Sum('total_price'), Decimal('0'), output_field=DecimalField())
    ).order_by('-count')
    
    lang_data = []
    for item in lang_breakdown:
        lang_data.append([
            item['language__name'] or "Not Specified",
            item['count'],
            float(item['revenue'] or 0),
        ])
    
    exporter.add_sheet(SheetConfig(
        name="Language Breakdown",
        headers=["Language", "Orders Count", "Revenue"],
        data=lang_data
    ))
    
    # Sheet 4: Daily Summary
    daily_breakdown = orders.annotate(
        date=TruncDate('created_at')
    ).values('date').annotate(
        count=Count('id'),
        revenue=Coalesce(Sum('total_price'), Decimal('0'), output_field=DecimalField()),
        pages=Coalesce(Sum('total_pages'), 0),
        paid=Coalesce(Sum('received'), Decimal('0'), output_field=DecimalField())
    ).order_by('date')
    
    daily_data = []
    for item in daily_breakdown:
        daily_data.append([
            item['date'],
            item['count'],
            item['pages'] or 0,
            float(item['revenue'] or 0),
            float(item['paid'] or 0),
        ])
    
    exporter.add_sheet(SheetConfig(
        name="Daily Summary",
        headers=["Date", "Orders", "Total Pages", "Revenue", "Paid"],
        data=daily_data
    ))
    
    # Generate filename
    center_name = ""
    if center_id:
        try:
            center_name = f"_{TranslationCenter.objects.get(id=center_id).name}"
        except:
            pass
    
    filename = f"orders_report{center_name}_{date_from.strftime('%Y%m%d')}_to_{date_to.strftime('%Y%m%d')}.xlsx"
    
    return exporter.generate_response(filename)


def export_financial_report(
    user,
    date_from: datetime,
    date_to: datetime,
    branch_id: Optional[str] = None,
    center_id: Optional[str] = None,
) -> HttpResponse:
    """
    Export Financial Report with multiple sheets:
    - Revenue Summary
    - Revenue by Status
    - Revenue by Branch
    - Revenue by Product
    - Daily Revenue Trend
    - Payment Details
    """
    exporter = ExcelExporter()
    
    # Get filtered orders
    orders = get_user_orders(user).filter(
        created_at__gte=date_from,
        created_at__lte=date_to
    ).select_related('bot_user', 'product', 'branch')
    
    if center_id:
        orders = orders.filter(branch__center_id=center_id)
    if branch_id:
        orders = orders.filter(branch_id=branch_id)
    
    # Sheet 1: Revenue Summary
    total_revenue = orders.aggregate(total=Sum('total_price'))['total'] or 0
    total_received = orders.aggregate(total=Sum('received'))['total'] or 0
    total_orders = orders.count()
    avg_order = orders.aggregate(avg=Avg('total_price'))['avg'] or 0
    completed_revenue = orders.filter(status='completed').aggregate(total=Sum('total_price'))['total'] or 0
    
    summary_data = [
        ["Total Orders", total_orders],
        ["Total Revenue", float(total_revenue)],
        ["Total Received", float(total_received)],
        ["Outstanding Amount", float(total_revenue - total_received)],
        ["Average Order Value", float(avg_order)],
        ["Completed Orders Revenue", float(completed_revenue)],
        ["Collection Rate (%)", round(float(total_received) / float(total_revenue) * 100, 1) if total_revenue > 0 else 0],
    ]
    
    exporter.add_sheet(SheetConfig(
        name="Revenue Summary",
        headers=["Metric", "Value"],
        data=summary_data,
        column_widths=[30, 20]
    ))
    
    # Sheet 2: Revenue by Status
    status_revenue = orders.values('status').annotate(
        count=Count('id'),
        revenue=Coalesce(Sum('total_price'), Decimal('0'), output_field=DecimalField()),
        received=Coalesce(Sum('received'), Decimal('0'), output_field=DecimalField())
    ).order_by('-revenue')
    
    status_data = []
    for item in status_revenue:
        status_data.append([
            STATUS_LABELS.get(item['status'], item['status']),
            item['count'],
            float(item['revenue'] or 0),
            float(item['received'] or 0),
            float((item['revenue'] or 0) - (item['received'] or 0)),
        ])
    
    exporter.add_sheet(SheetConfig(
        name="Revenue by Status",
        headers=["Status", "Orders", "Revenue", "Received", "Outstanding"],
        data=status_data
    ))
    
    # Sheet 3: Revenue by Branch
    branch_revenue = orders.values('branch__id', 'branch__name', 'branch__center__name').annotate(
        count=Count('id'),
        revenue=Coalesce(Sum('total_price'), Decimal('0'), output_field=DecimalField()),
        received=Coalesce(Sum('received'), Decimal('0'), output_field=DecimalField()),
        avg=Coalesce(Avg('total_price'), Decimal('0'), output_field=DecimalField())
    ).order_by('-revenue')
    
    branch_data = []
    for item in branch_revenue:
        if item['branch__id']:
            branch_data.append([
                item['branch__name'] or "Unassigned",
                item['branch__center__name'] or "N/A",
                item['count'],
                float(item['revenue'] or 0),
                float(item['received'] or 0),
                float((item['revenue'] or 0) - (item['received'] or 0)),
                float(item['avg'] or 0),
            ])
    
    exporter.add_sheet(SheetConfig(
        name="Revenue by Branch",
        headers=["Branch", "Center", "Orders", "Revenue", "Received", "Outstanding", "Avg Order Value"],
        data=branch_data
    ))
    
    # Sheet 4: Revenue by Product
    product_revenue = orders.values('product__name', 'product__category__name').annotate(
        count=Count('id'),
        revenue=Coalesce(Sum('total_price'), Decimal('0'), output_field=DecimalField()),
        pages=Coalesce(Sum('total_pages'), 0)
    ).order_by('-revenue')
    
    product_data = []
    for item in product_revenue:
        if item['product__name']:
            product_data.append([
                item['product__name'] or "Unknown",
                item['product__category__name'] or "N/A",
                item['count'],
                item['pages'] or 0,
                float(item['revenue'] or 0),
            ])
    
    exporter.add_sheet(SheetConfig(
        name="Revenue by Product",
        headers=["Product", "Category", "Orders", "Total Pages", "Revenue"],
        data=product_data
    ))
    
    # Sheet 5: Daily Revenue Trend
    daily_revenue = orders.annotate(
        date=TruncDate('created_at')
    ).values('date').annotate(
        count=Count('id'),
        revenue=Coalesce(Sum('total_price'), Decimal('0'), output_field=DecimalField()),
        received=Coalesce(Sum('received'), Decimal('0'), output_field=DecimalField()),
        avg=Coalesce(Avg('total_price'), Decimal('0'), output_field=DecimalField())
    ).order_by('date')
    
    daily_data = []
    for item in daily_revenue:
        daily_data.append([
            item['date'],
            item['count'],
            float(item['revenue'] or 0),
            float(item['received'] or 0),
            float(item['avg'] or 0),
        ])
    
    exporter.add_sheet(SheetConfig(
        name="Daily Revenue Trend",
        headers=["Date", "Orders", "Revenue", "Received", "Avg Order Value"],
        data=daily_data
    ))
    
    # Sheet 6: Payment Details
    payments_data = []
    for order in orders.filter(received__gt=0).order_by('-created_at')[:500]:
        payments_data.append([
            order.id,
            order.created_at,
            order.bot_user.name if order.bot_user else "N/A",
            order.branch.name if order.branch else "N/A",
            float(order.total_price or 0),
            float(order.received or 0),
            float((order.total_price or 0) - (order.received or 0)),
            PAYMENT_TYPE_LABELS.get(order.payment_type, "N/A"),
            STATUS_LABELS.get(order.status, order.status),
        ])
    
    exporter.add_sheet(SheetConfig(
        name="Payment Details",
        headers=["Order ID", "Date", "Customer", "Branch", "Total", "Paid", "Outstanding", "Payment Type", "Status"],
        data=payments_data
    ))
    
    # Generate filename
    center_name = ""
    if center_id:
        try:
            center_name = f"_{TranslationCenter.objects.get(id=center_id).name}"
        except:
            pass
    
    filename = f"financial_report{center_name}_{date_from.strftime('%Y%m%d')}_to_{date_to.strftime('%Y%m%d')}.xlsx"
    
    return exporter.generate_response(filename)


def export_staff_performance(
    user,
    date_from: datetime,
    date_to: datetime,
    branch_id: Optional[str] = None,
    center_id: Optional[str] = None,
) -> HttpResponse:
    """
    Export Staff Performance Report with multiple sheets:
    - Staff Summary
    - Detailed Orders by Staff
    - Daily Staff Activity
    """
    exporter = ExcelExporter()
    
    # Get filtered orders
    orders = get_user_orders(user).filter(
        created_at__gte=date_from,
        created_at__lte=date_to
    ).select_related('assigned_to__user', 'assigned_to__branch', 'bot_user', 'product')
    
    if center_id:
        orders = orders.filter(branch__center_id=center_id)
    if branch_id:
        orders = orders.filter(branch_id=branch_id)
    
    # Get staff members
    if user.is_superuser:
        staff_members = AdminUser.objects.filter(is_active=True)
        if center_id:
            staff_members = staff_members.filter(branch__center_id=center_id)
        if branch_id:
            staff_members = staff_members.filter(branch_id=branch_id)
    elif hasattr(user, 'admin_profile') and user.admin_profile:
        if user.admin_profile.is_owner:
            staff_members = AdminUser.objects.filter(
                center=user.admin_profile.center, is_active=True
            )
        elif user.admin_profile.is_manager:
            staff_members = AdminUser.objects.filter(
                branch=user.admin_profile.branch, is_active=True
            )
        else:
            staff_members = AdminUser.objects.filter(pk=user.admin_profile.pk)
    else:
        staff_members = AdminUser.objects.none()
    
    # Sheet 1: Staff Summary
    staff_data = []
    for staff in staff_members:
        staff_orders = orders.filter(assigned_to=staff)
        total_assigned = staff_orders.count()
        completed = staff_orders.filter(status='completed').count()
        revenue = staff_orders.filter(status='completed').aggregate(total=Sum('total_price'))['total'] or 0
        pages = staff_orders.aggregate(total=Sum('total_pages'))['total'] or 0
        completion_rate = round(completed / total_assigned * 100, 1) if total_assigned > 0 else 0
        
        staff_data.append([
            staff.user.get_full_name() or staff.user.username,
            staff.branch.name if staff.branch else "N/A",
            staff.branch.center.name if staff.branch and staff.branch.center else "N/A",
            staff.role.name if staff.role else "Staff",
            total_assigned,
            completed,
            completion_rate,
            pages or 0,
            float(revenue),
        ])
    
    # Sort by completed orders
    staff_data.sort(key=lambda x: x[5], reverse=True)
    
    exporter.add_sheet(SheetConfig(
        name="Staff Summary",
        headers=["Staff Name", "Branch", "Center", "Role", "Total Assigned", "Completed", "Completion Rate (%)", "Total Pages", "Revenue"],
        data=staff_data
    ))
    
    # Sheet 2: Detailed Orders by Staff
    staff_orders_data = []
    for order in orders.filter(assigned_to__isnull=False).order_by('-created_at')[:1000]:
        staff_orders_data.append([
            order.id,
            order.created_at,
            order.assigned_to.user.get_full_name() if order.assigned_to else "N/A",
            order.bot_user.name if order.bot_user else "N/A",
            order.product.name if order.product else "N/A",
            order.total_pages or 0,
            float(order.total_price or 0),
            STATUS_LABELS.get(order.status, order.status),
            order.completed_at,
        ])
    
    exporter.add_sheet(SheetConfig(
        name="Orders by Staff",
        headers=["Order ID", "Created At", "Staff", "Customer", "Product", "Pages", "Price", "Status", "Completed At"],
        data=staff_orders_data
    ))
    
    # Sheet 3: Daily Staff Activity
    daily_staff = orders.filter(assigned_to__isnull=False).annotate(
        date=TruncDate('created_at')
    ).values('date', 'assigned_to__user__first_name', 'assigned_to__user__last_name').annotate(
        count=Count('id'),
        completed=Count('id', filter=Q(status='completed')),
        pages=Coalesce(Sum('total_pages'), 0),
        revenue=Coalesce(Sum('total_price'), Decimal('0'), output_field=DecimalField())
    ).order_by('date')
    
    daily_data = []
    for item in daily_staff:
        name = f"{item['assigned_to__user__first_name'] or ''} {item['assigned_to__user__last_name'] or ''}".strip() or "Unknown"
        daily_data.append([
            item['date'],
            name,
            item['count'],
            item['completed'],
            item['pages'] or 0,
            float(item['revenue'] or 0),
        ])
    
    exporter.add_sheet(SheetConfig(
        name="Daily Staff Activity",
        headers=["Date", "Staff", "Orders Assigned", "Orders Completed", "Total Pages", "Revenue"],
        data=daily_data
    ))
    
    # Generate filename
    filename = f"staff_performance_{date_from.strftime('%Y%m%d')}_to_{date_to.strftime('%Y%m%d')}.xlsx"
    
    return exporter.generate_response(filename)


def export_branch_comparison(
    user,
    date_from: datetime,
    date_to: datetime,
    center_id: Optional[str] = None,
) -> HttpResponse:
    """
    Export Branch Comparison Report with multiple sheets:
    - Branch Summary
    - Branch Daily Performance
    - Branch Staff Count
    - Branch Customer Breakdown
    """
    exporter = ExcelExporter()
    
    # Get branches and orders
    branches = get_user_branches(user)
    orders = get_user_orders(user).filter(
        created_at__gte=date_from,
        created_at__lte=date_to
    )
    
    if center_id:
        branches = branches.filter(center_id=center_id)
        orders = orders.filter(branch__center_id=center_id)
    
    # Sheet 1: Branch Summary
    branch_data = []
    for branch in branches:
        branch_orders = orders.filter(branch=branch)
        total_orders = branch_orders.count()
        completed = branch_orders.filter(status='completed').count()
        revenue = branch_orders.aggregate(total=Sum('total_price'))['total'] or 0
        received = branch_orders.aggregate(total=Sum('received'))['total'] or 0
        avg_value = branch_orders.aggregate(avg=Avg('total_price'))['avg'] or 0
        staff_count = AdminUser.objects.filter(branch=branch, is_active=True).count()
        customer_count = BotUser.objects.filter(branch=branch, is_active=True).count()
        completion_rate = round(completed / total_orders * 100, 1) if total_orders > 0 else 0
        collection_rate = round(float(received) / float(revenue) * 100, 1) if revenue > 0 else 0
        
        branch_data.append([
            branch.name,
            branch.center.name if branch.center else "N/A",
            total_orders,
            completed,
            completion_rate,
            float(revenue),
            float(received),
            float(revenue - received),
            collection_rate,
            float(avg_value),
            staff_count,
            customer_count,
        ])
    
    # Sort by revenue
    branch_data.sort(key=lambda x: x[5], reverse=True)
    
    exporter.add_sheet(SheetConfig(
        name="Branch Summary",
        headers=[
            "Branch", "Center", "Total Orders", "Completed", "Completion Rate (%)",
            "Revenue", "Received", "Outstanding", "Collection Rate (%)",
            "Avg Order Value", "Staff Count", "Customer Count"
        ],
        data=branch_data
    ))
    
    # Sheet 2: Branch Daily Performance
    daily_branch = orders.annotate(
        date=TruncDate('created_at')
    ).values('date', 'branch__name').annotate(
        count=Count('id'),
        revenue=Coalesce(Sum('total_price'), Decimal('0'), output_field=DecimalField()),
        received=Coalesce(Sum('received'), Decimal('0'), output_field=DecimalField())
    ).order_by('date', 'branch__name')
    
    daily_data = []
    for item in daily_branch:
        daily_data.append([
            item['date'],
            item['branch__name'] or "Unassigned",
            item['count'],
            float(item['revenue'] or 0),
            float(item['received'] or 0),
        ])
    
    exporter.add_sheet(SheetConfig(
        name="Daily Branch Performance",
        headers=["Date", "Branch", "Orders", "Revenue", "Received"],
        data=daily_data
    ))
    
    # Sheet 3: Branch Staff Details
    staff_data = []
    for branch in branches:
        staff_members = AdminUser.objects.filter(branch=branch, is_active=True)
        for staff in staff_members:
            staff_orders = orders.filter(assigned_to=staff)
            completed = staff_orders.filter(status='completed').count()
            revenue = staff_orders.aggregate(total=Sum('total_price'))['total'] or 0
            
            staff_data.append([
                branch.name,
                staff.user.get_full_name() or staff.user.username,
                staff.role.name if staff.role else "Staff",
                staff_orders.count(),
                completed,
                float(revenue),
            ])
    
    exporter.add_sheet(SheetConfig(
        name="Branch Staff Details",
        headers=["Branch", "Staff Name", "Role", "Orders Assigned", "Completed", "Revenue"],
        data=staff_data
    ))
    
    # Generate filename
    filename = f"branch_comparison_{date_from.strftime('%Y%m%d')}_to_{date_to.strftime('%Y%m%d')}.xlsx"
    
    return exporter.generate_response(filename)


def export_customer_analytics(
    user,
    date_from: datetime,
    date_to: datetime,
    branch_id: Optional[str] = None,
    center_id: Optional[str] = None,
) -> HttpResponse:
    """
    Export Customer Analytics Report with multiple sheets:
    - Customer Summary
    - Top Customers
    - Customer List (Detailed)
    - B2B vs B2C Breakdown
    - New Customers
    """
    exporter = ExcelExporter()
    
    # Get data based on user role
    customers = get_user_customers(user)
    orders = get_user_orders(user).filter(
        created_at__gte=date_from,
        created_at__lte=date_to
    )
    
    if center_id:
        customer_ids = orders.filter(branch__center_id=center_id).values_list('bot_user_id', flat=True).distinct()
        customers = customers.filter(id__in=customer_ids)
        orders = orders.filter(branch__center_id=center_id)
    if branch_id:
        customers = customers.filter(branch_id=branch_id)
        orders = orders.filter(branch_id=branch_id)
    
    # Sheet 1: Customer Summary
    total_customers = customers.count()
    active_customers = customers.filter(is_active=True).count()
    agencies = customers.filter(is_agency=True).count()
    new_customers = customers.filter(created_at__gte=date_from, created_at__lte=date_to).count()
    
    summary_data = [
        ["Total Customers", total_customers],
        ["Active Customers", active_customers],
        ["B2B (Agencies)", agencies],
        ["B2C (Regular)", total_customers - agencies],
        ["New Customers (Period)", new_customers],
    ]
    
    exporter.add_sheet(SheetConfig(
        name="Customer Summary",
        headers=["Metric", "Value"],
        data=summary_data,
        column_widths=[30, 15]
    ))
    
    # Sheet 2: Top Customers by Revenue
    top_customers = orders.values(
        'bot_user__id', 'bot_user__name', 'bot_user__phone', 'bot_user__is_agency'
    ).annotate(
        order_count=Count('id'),
        total_spent=Coalesce(Sum('total_price'), Decimal('0'), output_field=DecimalField()),
        total_paid=Coalesce(Sum('received'), Decimal('0'), output_field=DecimalField())
    ).order_by('-total_spent')[:50]
    
    top_data = []
    for item in top_customers:
        top_data.append([
            item['bot_user__name'] or "Unknown",
            item['bot_user__phone'] or "N/A",
            "B2B" if item['bot_user__is_agency'] else "B2C",
            item['order_count'],
            float(item['total_spent'] or 0),
            float(item['total_paid'] or 0),
            float((item['total_spent'] or 0) - (item['total_paid'] or 0)),
        ])
    
    exporter.add_sheet(SheetConfig(
        name="Top Customers",
        headers=["Customer Name", "Phone", "Type", "Orders", "Total Spent", "Paid", "Outstanding"],
        data=top_data
    ))
    
    # Sheet 3: Detailed Customer List
    customer_data = []
    for customer in customers.select_related('branch', 'agency')[:500]:
        customer_orders = orders.filter(bot_user=customer)
        order_count = customer_orders.count()
        total_spent = customer_orders.aggregate(total=Sum('total_price'))['total'] or 0
        
        customer_data.append([
            customer.id,
            customer.name,
            customer.phone,
            customer.username or "N/A",
            "B2B" if customer.is_agency else "B2C",
            customer.branch.name if customer.branch else "N/A",
            customer.agency.name if customer.agency else "N/A",
            customer.language,
            order_count,
            float(total_spent),
            customer.created_at,
            "Active" if customer.is_active else "Inactive",
        ])
    
    exporter.add_sheet(SheetConfig(
        name="Customer List",
        headers=[
            "ID", "Name", "Phone", "Username", "Type", "Branch", "Agency",
            "Language", "Total Orders", "Total Spent", "Registered At", "Status"
        ],
        data=customer_data
    ))
    
    # Sheet 4: B2B vs B2C Breakdown
    b2b_orders = orders.filter(bot_user__is_agency=True)
    b2c_orders = orders.filter(bot_user__is_agency=False)
    
    type_data = [
        [
            "B2B (Agencies)",
            b2b_orders.count(),
            float(b2b_orders.aggregate(total=Sum('total_price'))['total'] or 0),
            float(b2b_orders.aggregate(total=Sum('received'))['total'] or 0),
            agencies,
        ],
        [
            "B2C (Regular)",
            b2c_orders.count(),
            float(b2c_orders.aggregate(total=Sum('total_price'))['total'] or 0),
            float(b2c_orders.aggregate(total=Sum('received'))['total'] or 0),
            total_customers - agencies,
        ],
    ]
    
    exporter.add_sheet(SheetConfig(
        name="B2B vs B2C",
        headers=["Customer Type", "Orders", "Revenue", "Paid", "Customer Count"],
        data=type_data
    ))
    
    # Sheet 5: New Customers (Period)
    new_customer_list = customers.filter(
        created_at__gte=date_from, created_at__lte=date_to
    ).select_related('branch')
    
    new_data = []
    for customer in new_customer_list:
        new_data.append([
            customer.name,
            customer.phone,
            "B2B" if customer.is_agency else "B2C",
            customer.branch.name if customer.branch else "N/A",
            customer.created_at,
        ])
    
    exporter.add_sheet(SheetConfig(
        name="New Customers",
        headers=["Name", "Phone", "Type", "Branch", "Registered At"],
        data=new_data
    ))
    
    # Generate filename
    filename = f"customer_analytics_{date_from.strftime('%Y%m%d')}_to_{date_to.strftime('%Y%m%d')}.xlsx"
    
    return exporter.generate_response(filename)


def export_unit_economy(
    user,
    branch_id: Optional[str] = None,
    center_id: Optional[str] = None,
) -> HttpResponse:
    """
    Export Unit Economy Report with multiple sheets:
    - Remaining Balance Summary
    - Remaining by Branch
    - Remaining by Client Type
    - Remaining by Center
    - Top Debtors
    - Detailed Outstanding Orders
    """
    from services.analytics import (
        get_remaining_balance_summary,
        get_remaining_by_branch,
        get_remaining_by_client_type,
        get_remaining_by_center,
        get_top_debtors,
    )
    from decimal import Decimal
    from django.db.models.functions import Coalesce
    from django.db.models import Case, When, F, DecimalField
    
    exporter = ExcelExporter()
    
    # Get analytics data
    summary = get_remaining_balance_summary(user)
    by_branch = get_remaining_by_branch(user, limit=100)
    by_client_type = get_remaining_by_client_type(user)
    by_center = get_remaining_by_center(user, limit=50)
    top_debtors = get_top_debtors(user, limit=100)
    
    # Sheet 1: Summary
    summary_data = [
        ["Total Outstanding Balance", summary['total_remaining']],
        ["Orders with Outstanding Balance", summary['total_orders_with_debt']],
        ["Fully Paid Orders", summary['fully_paid_count']],
        ["Total Received", summary['total_received']],
        ["Total Expected Revenue", summary['total_expected']],
        ["Collection Rate (%)", summary['collection_rate']],
    ]
    
    exporter.add_sheet(SheetConfig(
        name="Summary",
        headers=["Metric", "Value"],
        data=summary_data,
        column_widths=[35, 20]
    ))
    
    # Sheet 2: By Branch
    branch_data = []
    for item in by_branch:
        branch_data.append([
            item['branch_name'],
            item['center_name'],
            item['total_orders'],
            item['orders_with_debt'],
            item['remaining'],
            item['total_received'],
            item['total_expected'],
            item['collection_rate'],
        ])
    
    exporter.add_sheet(SheetConfig(
        name="By Branch",
        headers=["Branch", "Center", "Total Orders", "Orders with Debt", "Outstanding", "Received", "Expected", "Collection Rate (%)"],
        data=branch_data
    ))
    
    # Sheet 3: By Client Type
    type_data = [
        [
            by_client_type['agency']['label'],
            by_client_type['agency']['total_orders'],
            by_client_type['agency']['orders_with_debt'],
            by_client_type['agency']['remaining'],
            by_client_type['agency']['total_received'],
            by_client_type['agency']['collection_rate'],
        ],
        [
            by_client_type['regular']['label'],
            by_client_type['regular']['total_orders'],
            by_client_type['regular']['orders_with_debt'],
            by_client_type['regular']['remaining'],
            by_client_type['regular']['total_received'],
            by_client_type['regular']['collection_rate'],
        ],
    ]
    
    exporter.add_sheet(SheetConfig(
        name="By Client Type",
        headers=["Client Type", "Total Orders", "Orders with Debt", "Outstanding", "Received", "Collection Rate (%)"],
        data=type_data
    ))
    
    # Sheet 4: By Center
    center_data = []
    for item in by_center:
        center_data.append([
            item['center_name'],
            item['total_orders'],
            item['orders_with_debt'],
            item['remaining'],
            item['total_received'],
            item['collection_rate'],
        ])
    
    exporter.add_sheet(SheetConfig(
        name="By Center",
        headers=["Center", "Total Orders", "Orders with Debt", "Outstanding", "Received", "Collection Rate (%)"],
        data=center_data
    ))
    
    # Sheet 5: Top Debtors
    debtor_data = []
    for item in top_debtors:
        debtor_data.append([
            item['customer_name'],
            item['customer_phone'],
            "B2B" if item['is_agency'] else "B2C",
            item['total_orders'],
            item['orders_with_debt'],
            item['remaining'],
            item['total_expected'],
            item['total_received'],
        ])
    
    exporter.add_sheet(SheetConfig(
        name="Top Debtors",
        headers=["Customer Name", "Phone", "Type", "Total Orders", "Orders with Debt", "Outstanding", "Total Expected", "Total Paid"],
        data=debtor_data
    ))
    
    # Sheet 6: Detailed Outstanding Orders
    orders = get_user_orders(user).exclude(status='cancelled').select_related(
        'bot_user', 'product', 'branch'
    ).annotate(
        calc_remaining=Case(
            When(payment_accepted_fully=True, then=Decimal('0')),
            default=(
                Coalesce(F('total_price'), Decimal('0')) + Coalesce(F('extra_fee'), Decimal('0'))
            ) - Coalesce(F('received'), Decimal('0')),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        )
    ).filter(calc_remaining__gt=0).order_by('-calc_remaining')[:500]
    
    orders_data = []
    for order in orders:
        remaining = float(order.calc_remaining) if hasattr(order, 'calc_remaining') else 0
        orders_data.append([
            order.id,
            order.created_at,
            order.bot_user.name if order.bot_user else "N/A",
            order.bot_user.phone if order.bot_user else "N/A",
            "B2B" if (order.bot_user and order.bot_user.is_agency) else "B2C",
            order.branch.name if order.branch else "N/A",
            order.product.name if order.product else "N/A",
            float(order.total_price or 0),
            float(order.extra_fee or 0),
            float(order.received or 0),
            remaining,
            STATUS_LABELS.get(order.status, order.status),
        ])
    
    exporter.add_sheet(SheetConfig(
        name="Outstanding Orders",
        headers=["Order ID", "Date", "Customer", "Phone", "Type", "Branch", "Product", "Total Price", "Extra Fee", "Received", "Outstanding", "Status"],
        data=orders_data
    ))
    
    # Generate filename
    today = timezone.now().strftime('%Y%m%d')
    filename = f"unit_economy_{today}.xlsx"
    
    return exporter.generate_response(filename)


def export_my_statistics(
    user,
    date_from: datetime,
    date_to: datetime,
) -> HttpResponse:
    """
    Export My Statistics Report with multiple sheets:
    - Summary
    - My Orders
    - Daily Performance
    """
    exporter = ExcelExporter()
    
    # Get admin profile
    admin_profile = getattr(user, 'admin_profile', None)
    
    if admin_profile:
        my_orders = Order.objects.filter(assigned_to=admin_profile).select_related(
            'bot_user', 'product', 'branch'
        )
    else:
        my_orders = Order.objects.none()
    
    # Filter by period
    period_orders = my_orders.filter(created_at__gte=date_from, created_at__lte=date_to)
    
    # Sheet 1: Summary
    total_count = period_orders.count()
    completed = period_orders.filter(status='completed').count()
    total_pages = period_orders.aggregate(total=Sum('total_pages'))['total'] or 0
    total_revenue = period_orders.aggregate(total=Sum('total_price'))['total'] or 0
    completion_rate = round(completed / total_count * 100, 1) if total_count > 0 else 0
    
    summary_data = [
        ["Period", f"{date_from.strftime('%Y-%m-%d')} to {date_to.strftime('%Y-%m-%d')}"],
        ["Total Orders Assigned", total_count],
        ["Orders Completed", completed],
        ["Completion Rate (%)", completion_rate],
        ["Total Pages Processed", total_pages],
        ["Total Revenue Generated", float(total_revenue)],
    ]
    
    exporter.add_sheet(SheetConfig(
        name="Summary",
        headers=["Metric", "Value"],
        data=summary_data,
        column_widths=[30, 20]
    ))
    
    # Sheet 2: My Orders
    orders_data = []
    for order in period_orders.order_by('-created_at'):
        orders_data.append([
            order.id,
            order.created_at,
            order.bot_user.name if order.bot_user else "N/A",
            order.product.name if order.product else "N/A",
            order.total_pages or 0,
            float(order.total_price or 0),
            STATUS_LABELS.get(order.status, order.status),
            order.completed_at,
        ])
    
    exporter.add_sheet(SheetConfig(
        name="My Orders",
        headers=["Order ID", "Created At", "Customer", "Product", "Pages", "Price", "Status", "Completed At"],
        data=orders_data
    ))
    
    # Sheet 3: Daily Performance
    daily_performance = period_orders.annotate(
        date=TruncDate('created_at')
    ).values('date').annotate(
        count=Count('id'),
        completed=Count('id', filter=Q(status='completed')),
        pages=Coalesce(Sum('total_pages'), 0),
        revenue=Coalesce(Sum('total_price'), 0)
    ).order_by('date')
    
    daily_data = []
    for item in daily_performance:
        daily_data.append([
            item['date'],
            item['count'],
            item['completed'],
            item['pages'] or 0,
            float(item['revenue'] or 0),
        ])
    
    exporter.add_sheet(SheetConfig(
        name="Daily Performance",
        headers=["Date", "Orders Assigned", "Completed", "Pages", "Revenue"],
        data=daily_data
    ))
    
    # Generate filename
    staff_name = user.get_full_name() or user.username
    filename = f"my_statistics_{staff_name}_{date_from.strftime('%Y%m%d')}_to_{date_to.strftime('%Y%m%d')}.xlsx"
    filename = filename.replace(" ", "_")
    
    return exporter.generate_response(filename)

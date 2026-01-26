"""
URL configuration for WowDash project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from WowDash import home_views
from WowDash import reports_views
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect

@login_required
def test_select2(request):
    return render(request, 'test_select2.html')


def subdomain_required_view(request):
    """Redirect to main domain if accessed without subdomain."""
    return HttpResponse(
        "Please access this page through your organization's subdomain (e.g., yourcompany.multilang.uz)",
        status=400
    )


def main_domain_index(request):
    """Route index based on subdomain presence."""
    subdomain = getattr(request, 'subdomain', None)
    
    if subdomain == 'admin':
        # admin.multilang.uz -> superuser admin dashboard
        # TODO: Create custom superuser admin view
        return home_views.index(request)
    elif subdomain:
        # Has other subdomain -> show center dashboard
        return home_views.index(request)
    else:
        # No subdomain -> show landing page
        from landing.views import home
        return home(request)


def superuser_admin_panel(request):
    """Superuser admin panel for managing all centers (dev access at /super)."""
    # TODO: Add superuser permission check
    # For now, just show the dashboard
    return home_views.index(request)


urlpatterns = [
    # Django Admin Panel (accessible on all subdomains at /admin)
    path("admin/", admin.site.urls),
    
    # Superuser Admin Panel (dev environment shortcut)
    path("super/", superuser_admin_panel, name="superuser_admin"),
    
    # Root path - dynamic based on subdomain
    path("", main_domain_index, name="index"),
    
    # Landing Page URLs (only work on main domain)
    path("", include("landing.urls")),
    
    path("test-select2/", test_select2, name="test_select2"),
    
    # Dashboard (accessible on subdomains)
    path("dashboard/", home_views.index, name="dashboard"),
    
    # Authentication & User management (accounts app)
    path("accounts/", include("accounts.urls")),
    path("users/", include("accounts.urls")),
    # Organizations management (centers, branches, staff)
    path("organizations/", include("organizations.urls")),
    # Orders management
    path("orders/", include("orders.urls")),
    # Services management (categories & products)
    path("services/", include("services.urls")),
    # Marketing & Broadcasts
    path("marketing/", include("marketing.urls")),
    # Core utilities (notifications, etc.)
    path("core/", include("core.urls")),
    # home routes
    path("index", home_views.index, name="index"),
    path("view-details", home_views.viewDetails, name="viewDetails"),
    path("sales", home_views.sales, name="sales"),
    path("finance", home_views.finance, name="finance"),
    # chart routes
  
    # Reports & Analytics routes
    path(
        "reports/financial", reports_views.financial_reports, name="financial_reports"
    ),
    path("reports/orders", reports_views.order_reports, name="order_reports"),
    path(
        "reports/staff-performance",
        reports_views.staff_performance,
        name="staff_performance",
    ),
    path(
        "reports/branch-comparison",
        reports_views.branch_comparison,
        name="branch_comparison",
    ),
    path(
        "reports/customers", reports_views.customer_analytics, name="customer_analytics"
    ),
    path(
        "reports/export/<str:report_type>",
        reports_views.export_report,
        name="export_report",
    ),
    path(
        "my-statistics",
        reports_views.my_statistics,
        name="my_statistics",
    ),
    # Unit Economy Analytics
    path(
        "reports/unit-economy",
        reports_views.unit_economy,
        name="unit_economy",
    ),
    path(
        "api/unit-economy",
        reports_views.unit_economy_api,
        name="unit_economy_api",
    ),
    # Debtors Management Page
    path(
        "reports/debtors",
        reports_views.debtors_report,
        name="debtors_report",
    ),
    # Audit Logs (also accessible via core/audit-logs/)
    path("reports/audit-logs", home_views.audit_logs_redirect, name="audit_logs"),
    # Expense Analytics Report
    path(
        "reports/expense-analytics",
        reports_views.expense_analytics_report,
        name="expense_analytics_report",
    ),
]
from django.conf import settings
from django.conf.urls.static import static
from bot.main import index
from bot.webhook_manager import webhook_handler

# Legacy single-bot webhook (for backward compatibility)
urlpatterns += [path("bot", index, name="bot_webhook")]

# Multi-tenant webhook - each center has its own endpoint
urlpatterns += [path("bot/webhook/<int:center_id>/", webhook_handler, name="center_webhook")]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

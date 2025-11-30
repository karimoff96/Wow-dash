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
from django.shortcuts import redirect
from WowDash import chart_views
from WowDash import components_views
from WowDash import home_views
from WowDash import roleAndAccess_views
from WowDash import settings_views
from WowDash import table_views

urlpatterns = [
    path("admin/", admin.site.urls),
    
    # Root URL redirects to dashboard
    path("", home_views.index, name="dashboard"),
    
    # Authentication & User management (accounts app)
    path("accounts/", include("accounts.urls")),
    path("users/", include("accounts.urls")),
    
    # Orders management
    path("orders/", include("orders.urls")),
    
    # Services management (categories & products)
    path("services/", include("services.urls")),
    
    # home routes
    path("index", home_views.index, name="index"),
    path("email", home_views.email, name="email"),
    path("kanban", home_views.kanban, name="kanban"),
    path("stared", home_views.stared, name="stared"),
    path("view-details", home_views.viewDetails, name="viewDetails"),
    path("widgets", home_views.widgets, name="widgets"),
    path("sales", home_views.sales, name="sales"),
    path("finance", home_views.finance, name="finance"),
    
    # chart routes
    path("chart/column-chart", chart_views.columnChart, name="columnChart"),
    path("chart/line-chart", chart_views.lineChart, name="lineChart"),
    path("chart/pie-chart", chart_views.pieChart, name="pieChart"),
    # components routes
    path("components/alerts", components_views.alerts, name="alerts"),
    path("components/avatars", components_views.avatars, name="avatars"),
    path("components/badges", components_views.badges, name="badges"),
    path("components/button", components_views.button, name="button"),
    path("components/calendar", components_views.calendar, name="calendarMain"),
    path("components/card", components_views.card, name="card"),
    path("components/carousel", components_views.carousel, name="carousel"),
    path("components/colors", components_views.colors, name="colors"),
    path("components/dropdown", components_views.dropdown, name="dropdown"),
    path("components/list", components_views.list, name="list"),
    path("components/pagination", components_views.pagination, name="pagination"),
    path("components/progressbar", components_views.progressbar, name="progressbar"),
    path("components/radio", components_views.radio, name="radio"),
    path("components/star-ratings", components_views.starRatings, name="starRatings"),
    path("components/switch", components_views.switch, name="switch"),
    path(
        "components/tab-accordion",
        components_views.tabAndAccordion,
        name="tabAndAccordion",
    ),
    path("components/tags", components_views.tags, name="tags"),
    path("components/tooltip", components_views.tooltip, name="tooltip"),
    path("components/typography", components_views.typography, name="typography"),
    path("components/upload", components_views.upload, name="upload"),
    path("components/videos", components_views.videos, name="videos"),
   
    # role and access routes
    path("role-access/assign-role", roleAndAccess_views.assignRole, name="assignRole"),
    path("role-access/role-access", roleAndAccess_views.roleAccess, name="roleAccess"),
    # settings routes
    path("settings/company", settings_views.company, name="company"),
    path("settings/currencies", settings_views.currencies, name="currencies"),
    path("settings/languages", settings_views.languages, name="languages"),
    path("settings/notification", settings_views.notification, name="notification"),
    path(
        "settings/notification-alert",
        settings_views.notificationAlert,
        name="notificationAlert",
    ),
    path("settings/payment-getway", settings_views.paymentGetway, name="paymentGetway"),
    path("settings/theme", settings_views.theme, name="theme"),
    # tables routes
    path("tables/basic-table", table_views.basicTable, name="basicTable"),
    path("tables/data-table", table_views.dataTable, name="dataTable"),
  
]
from django.conf import settings
from django.conf.urls.static import static
from bot.main import index

urlpatterns += [path("bot", index, name="bot_webhook")]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

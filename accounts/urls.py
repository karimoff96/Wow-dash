"""
URL configuration for accounts app.
Handles admin authentication and user management.
"""

from django.urls import path
from .views import (
    admin_login, 
    admin_logout, 
    forgot_password,
    reset_password,
    addUser, 
    usersList, 
    viewProfile
)

urlpatterns = [
    # Authentication URLs
    path("login/", admin_login, name="admin_login"),
    path("logout/", admin_logout, name="admin_logout"),
    path("forgot-password/", forgot_password, name="forgot_password"),
    path("reset-password/<uidb64>/<token>/", reset_password, name="reset_password"),
    
    # User management URLs
    path("", usersList, name="usersList"),
    path("add-user/", addUser, name="addUser"),
    path("view-profile/", viewProfile, name="viewProfile"),
]

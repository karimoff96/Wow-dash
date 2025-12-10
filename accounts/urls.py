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
    editUser,
    deleteUser,
    usersList, 
    userDetail,
    viewProfile,
    updateProfile,
    changePassword,
    bulk_delete_users
)

urlpatterns = [
    # Authentication URLs
    path("login/", admin_login, name="admin_login"),
    path("logout/", admin_logout, name="admin_logout"),
    path("forgot-password/", forgot_password, name="forgot_password"),
    path("reset-password/<uidb64>/<token>/", reset_password, name="reset_password"),
    
    # User management URLs (BotUsers)
    path("", usersList, name="usersList"),
    path("add-user/", addUser, name="addUser"),
    path("edit-user/<int:user_id>/", editUser, name="editUser"),
    path("delete-user/<int:user_id>/", deleteUser, name="deleteUser"),
    path("bulk-delete/", bulk_delete_users, name="bulk_delete_users"),
    path("user-detail/", userDetail, name="userDetail"),
    
    # Admin profile URLs
    path("profile/", viewProfile, name="viewProfile"),
    path("profile/update/", updateProfile, name="updateProfile"),
    path("profile/change-password/", changePassword, name="changePassword"),
]

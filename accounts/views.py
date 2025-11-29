from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.contrib import messages
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.conf import settings


# ============ Admin Authentication Views ============


def admin_login(request):
    """Admin login view"""
    # If user is already logged in, redirect to dashboard
    if request.user.is_authenticated:
        return redirect("index")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.is_staff or user.is_superuser:
                login(request, user)
                next_url = request.GET.get("next", "index")
                return redirect(next_url)
            else:
                messages.error(request, "You do not have admin access.")
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, "authentication/signin.html")


def admin_logout(request):
    """Admin logout view"""
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect("admin_login")


def forgot_password(request):
    """Forgot password view - sends reset email"""
    if request.method == "POST":
        email = request.POST.get("email")

        try:
            user = User.objects.get(email=email)
            # Generate token
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))

            # Build reset URL
            reset_url = request.build_absolute_uri(
                f"/accounts/reset-password/{uid}/{token}/"
            )

            # Send email
            subject = "Password Reset Request"
            message = f"""
                Hello {user.username},

                You have requested to reset your password. Click the link below to reset it:

                {reset_url}

                If you did not request this, please ignore this email.

                Best regards,
                Admin Team
            """

            try:
                send_mail(
                    subject,
                    message,
                    (
                        settings.DEFAULT_FROM_EMAIL
                        if hasattr(settings, "DEFAULT_FROM_EMAIL")
                        else "noreply@example.com"
                    ),
                    [email],
                    fail_silently=False,
                )
                messages.success(
                    request, "Password reset link has been sent to your email."
                )
            except Exception as e:
                messages.error(request, "Failed to send email. Please try again later.")

        except User.DoesNotExist:
            # Don't reveal that user doesn't exist for security
            messages.success(
                request,
                "If an account with this email exists, a password reset link has been sent.",
            )

    return render(request, "authentication/forgotPassword.html")


def reset_password(request, uidb64, token):
    """Reset password view - handles the reset link"""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        if request.method == "POST":
            password = request.POST.get("password")
            confirm_password = request.POST.get("confirm_password")

            if password != confirm_password:
                messages.error(request, "Passwords do not match.")
            elif len(password) < 8:
                messages.error(request, "Password must be at least 8 characters long.")
            else:
                user.set_password(password)
                user.save()
                messages.success(
                    request, "Your password has been reset successfully. Please login."
                )
                return redirect("admin_login")

        return render(
            request, "authentication/resetPassword.html", {"valid_link": True}
        )
    else:
        messages.error(request, "The password reset link is invalid or has expired.")
        return redirect("forgot_password")


# ============ User Management Views ============

from .models import BotUser
from django.core.paginator import Paginator
from django.db.models import Q


@login_required(login_url='admin_login')
def addUser(request):
    context = {
        "title": "Add User",
        "subTitle": "Add User",
    }
    return render(request, "users/addUser.html", context)


@login_required(login_url='admin_login')
def usersList(request):
    """List all BotUsers with search and filter"""
    users = BotUser.objects.all().order_by('-created_at')
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        users = users.filter(
            Q(name__icontains=search_query) |
            Q(username__icontains=search_query) |
            Q(phone__icontains=search_query)
        )
    
    # Status filter
    status_filter = request.GET.get('status', '')
    if status_filter == 'active':
        users = users.filter(is_active=True)
    elif status_filter == 'inactive':
        users = users.filter(is_active=False)
    elif status_filter == 'agency':
        users = users.filter(is_agency=True)
    
    # Pagination
    per_page = request.GET.get('per_page', 10)
    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 10
    
    paginator = Paginator(users, per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        "title": "Users List",
        "subTitle": "Users List",
        "users": page_obj,
        "paginator": paginator,
        "search_query": search_query,
        "status_filter": status_filter,
        "per_page": per_page,
        "total_users": paginator.count,
    }
    return render(request, "users/usersList.html", context)


@login_required(login_url='admin_login')
def viewProfile(request):
    context = {
        "title": "View Profile",
        "subTitle": "View Profile",
    }
    return render(request, "users/viewProfile.html", context)

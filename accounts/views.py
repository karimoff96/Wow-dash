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
    """Add a new BotUser (Telegram user)"""
    # Get all agencies for the dropdown
    agencies = BotUser.objects.filter(is_agency=True).order_by('name')
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        phone = request.POST.get('phone', '').strip()
        username = request.POST.get('username', '').strip()
        user_id = request.POST.get('user_id', '').strip()
        language = request.POST.get('language', 'uz')
        is_active = request.POST.get('is_active') == 'on'
        is_agency = request.POST.get('is_agency') == 'on'
        agency_id = request.POST.get('agency', '')
        
        # Validation
        if not name:
            messages.error(request, 'Full name is required.')
        elif not phone:
            messages.error(request, 'Phone number is required.')
        else:
            try:
                # Create the BotUser
                bot_user = BotUser(
                    name=name,
                    phone=phone,
                    username=username if username else None,
                    user_id=int(user_id) if user_id else None,
                    language=language,
                    is_active=is_active,
                    is_agency=is_agency,
                )
                
                # Set agency if selected and not an agency itself
                if agency_id and not is_agency:
                    try:
                        agency = BotUser.objects.get(id=agency_id, is_agency=True)
                        bot_user.agency = agency
                    except BotUser.DoesNotExist:
                        pass
                
                bot_user.save()
                messages.success(request, f'User "{name}" has been created successfully.')
                return redirect('usersList')
                
            except Exception as e:
                messages.error(request, f'Error creating user: {str(e)}')
    
    context = {
        "title": "Add User",
        "subTitle": "Add User",
        "agencies": agencies,
        "languages": BotUser.LANGUAGES,
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
def editUser(request, user_id):
    """Edit an existing BotUser"""
    from django.shortcuts import get_object_or_404
    
    user = get_object_or_404(BotUser, id=user_id)
    agencies = BotUser.objects.filter(is_agency=True).exclude(id=user_id).order_by('name')
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        phone = request.POST.get('phone', '').strip()
        username = request.POST.get('username', '').strip()
        user_id_field = request.POST.get('user_id', '').strip()
        language = request.POST.get('language', 'uz')
        is_active = request.POST.get('is_active') == 'on'
        is_agency = request.POST.get('is_agency') == 'on'
        agency_id = request.POST.get('agency', '')
        
        # Validation
        if not name:
            messages.error(request, 'Full name is required.')
        elif not phone:
            messages.error(request, 'Phone number is required.')
        else:
            try:
                # Update the BotUser
                user.name = name
                user.phone = phone
                user.username = username if username else None
                user.user_id = int(user_id_field) if user_id_field else None
                user.language = language
                user.is_active = is_active
                user.is_agency = is_agency
                
                # Set agency if selected and not an agency itself
                if agency_id and not is_agency:
                    try:
                        agency = BotUser.objects.get(id=agency_id, is_agency=True)
                        user.agency = agency
                    except BotUser.DoesNotExist:
                        user.agency = None
                else:
                    user.agency = None
                
                user.save()
                messages.success(request, f'User "{name}" has been updated successfully.')
                return redirect('usersList')
                
            except Exception as e:
                messages.error(request, f'Error updating user: {str(e)}')
    
    context = {
        "title": "Edit User",
        "subTitle": "Edit User",
        "user": user,
        "agencies": agencies,
        "languages": BotUser.LANGUAGES,
    }
    return render(request, "users/editUser.html", context)


@login_required(login_url='admin_login')
def userDetail(request):
    """View BotUser (Telegram user) profile details"""
    from orders.models import Order
    from django.shortcuts import get_object_or_404
    
    user_id = request.GET.get('id')
    if not user_id:
        messages.error(request, "User ID is required.")
        return redirect('usersList')
    
    user = get_object_or_404(BotUser, id=user_id)
    
    # Get user's orders
    orders = Order.objects.filter(bot_user=user).order_by('-created_at')[:10]
    total_orders = Order.objects.filter(bot_user=user).count()
    completed_orders = Order.objects.filter(bot_user=user, status='completed').count()
    pending_orders = Order.objects.filter(bot_user=user, status__in=['pending', 'payment_pending', 'payment_received', 'in_progress']).count()
    
    # Get agency users if this user is an agency
    agency_users = []
    if user.is_agency:
        agency_users = BotUser.objects.filter(agency=user).order_by('-created_at')[:5]
    
    context = {
        "title": "User Details",
        "subTitle": "User Details",
        "bot_user": user,
        "orders": orders,
        "total_orders": total_orders,
        "completed_orders": completed_orders,
        "pending_orders": pending_orders,
        "agency_users": agency_users,
        "agency_users_count": BotUser.objects.filter(agency=user).count() if user.is_agency else 0,
    }
    return render(request, "users/userDetail.html", context)


# ============ Admin Profile Views ============

@login_required(login_url='admin_login')
def viewProfile(request):
    """View admin profile page"""
    context = {
        "title": "My Profile",
        "subTitle": "Profile",
    }
    return render(request, "users/viewProfile.html", context)


@login_required(login_url='admin_login')
def updateProfile(request):
    """Update admin profile"""
    if request.method == 'POST':
        user = request.user
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        
        # Validation
        if not first_name:
            messages.error(request, 'First name is required.')
            return redirect('viewProfile')
        
        if not email:
            messages.error(request, 'Email is required.')
            return redirect('viewProfile')
        
        # Check if email is already used by another user
        if User.objects.filter(email=email).exclude(pk=user.pk).exists():
            messages.error(request, 'This email is already in use.')
            return redirect('viewProfile')
        
        try:
            user.first_name = first_name
            user.last_name = last_name
            user.email = email
            user.save()
            messages.success(request, 'Profile updated successfully.')
        except Exception as e:
            messages.error(request, f'Error updating profile: {str(e)}')
    
    return redirect('viewProfile')


@login_required(login_url='admin_login')
def changePassword(request):
    """Change admin password"""
    if request.method == 'POST':
        user = request.user
        current_password = request.POST.get('current_password', '')
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')
        
        # Validation
        if not current_password:
            messages.error(request, 'Current password is required.')
            return redirect('viewProfile')
        
        if not user.check_password(current_password):
            messages.error(request, 'Current password is incorrect.')
            return redirect('viewProfile')
        
        if not new_password:
            messages.error(request, 'New password is required.')
            return redirect('viewProfile')
        
        if len(new_password) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
            return redirect('viewProfile')
        
        if new_password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return redirect('viewProfile')
        
        try:
            user.set_password(new_password)
            user.save()
            # Re-login the user with new password
            login(request, user)
            messages.success(request, 'Password changed successfully.')
        except Exception as e:
            messages.error(request, f'Error changing password: {str(e)}')
    
    return redirect('viewProfile')

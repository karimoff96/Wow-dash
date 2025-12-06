"""
Views for organization management (Centers, Branches, Staff).
"""
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import TranslationCenter, Branch, Role, AdminUser
from .rbac import (
    permission_required,
    owner_required,
    get_user_branches,
    get_user_staff,
    can_edit_staff,
    get_assignable_roles,
    can_view_staff_required,
)
from core.audit import log_create, log_update, log_delete

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger('audit')


# ============ Translation Center Views ============


@login_required(login_url="admin_login")
@permission_required('can_view_centers')
def center_list(request):
    """List translation centers visible to the user based on permissions"""
    if request.user.is_superuser:
        centers = TranslationCenter.objects.all()
    else:
        profile = getattr(request.user, 'admin_profile', None)
        if profile and profile.center:
            centers = TranslationCenter.objects.filter(pk=profile.center_id)
        else:
            centers = TranslationCenter.objects.none()

    centers = centers.annotate(
        branch_count=Count("branches"),
    ).order_by("-created_at")

    # Pagination - 6 items per page to fit screen nicely
    paginator = Paginator(centers, 6)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "title": "Translation Centers",
        "subTitle": "Manage Your Centers",
        "centers": page_obj,
        "paginator": paginator,
        "total_centers": paginator.count,
    }
    return render(request, "organizations/center_list.html", context)


@login_required(login_url="admin_login")
@permission_required('can_create_centers')
def center_create(request):
    """Create a new translation center - Superuser only"""
    # Get available owners for superuser selection
    available_owners = None
    if request.user.is_superuser:
        available_owners = User.objects.filter(is_active=True).order_by('username')
    
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        phone = request.POST.get("phone", "").strip()
        email = request.POST.get("email", "").strip()
        address = request.POST.get("address", "").strip()
        location_url = request.POST.get("location_url", "").strip()
        
        # Subdomain - only superuser can set
        subdomain = None
        if request.user.is_superuser:
            subdomain = request.POST.get("subdomain", "").strip().lower() or None
        
        # Owner selection - only superuser can set
        owner = request.user
        if request.user.is_superuser:
            owner_id = request.POST.get("owner_id", "").strip()
            if owner_id:
                try:
                    owner = User.objects.get(pk=owner_id, is_active=True)
                except User.DoesNotExist:
                    messages.error(request, "Selected owner not found.")
                    return redirect("center_create")
        
        # Bot fields - only superuser can set bot_token
        bot_token = None
        company_orders_channel_id = request.POST.get("company_orders_channel_id", "").strip() or None
        if request.user.is_superuser:
            bot_token = request.POST.get("bot_token", "").strip() or None

        if not name:
            messages.error(request, "Center name is required.")
        elif subdomain and TranslationCenter.objects.filter(subdomain=subdomain).exists():
            messages.error(request, "This subdomain is already in use by another center.")
        elif bot_token and TranslationCenter.objects.filter(bot_token=bot_token).exists():
            messages.error(request, "This bot token is already in use by another center.")
        else:
            center = TranslationCenter.objects.create(
                name=name,
                owner=owner,
                subdomain=subdomain,
                phone=phone or None,
                email=email or None,
                address=address or None,
                location_url=location_url or None,
                bot_token=bot_token,
                company_orders_channel_id=company_orders_channel_id,
            )
            messages.success(
                request, f'Translation center "{name}" created successfully!'
            )
            return redirect("center_list")

    context = {
        "title": "Create Center",
        "subTitle": "Add New Translation Center",
        "is_superuser": request.user.is_superuser,
        "available_owners": available_owners,
    }
    return render(request, "organizations/center_form.html", context)


@login_required(login_url="admin_login")
@permission_required('can_edit_centers')
def center_edit(request, center_id):
    """Edit an existing translation center"""
    if request.user.is_superuser:
        center = get_object_or_404(TranslationCenter, pk=center_id)
    else:
        # Check if user belongs to this center via their AdminUser profile
        profile = getattr(request.user, 'admin_profile', None)
        if not profile or profile.center_id != center_id:
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden("You don't have access to this center.")
        center = get_object_or_404(TranslationCenter, pk=center_id)

    # Get available owners for superuser selection
    available_owners = None
    if request.user.is_superuser:
        available_owners = User.objects.filter(is_active=True).order_by('username')

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        phone = request.POST.get("phone", "").strip()
        email = request.POST.get("email", "").strip()
        address = request.POST.get("address", "").strip()
        location_url = request.POST.get("location_url", "").strip()
        is_active = request.POST.get("is_active") == "on"
        
        # Subdomain - only superuser can edit
        if request.user.is_superuser:
            subdomain = request.POST.get("subdomain", "").strip().lower() or None
        else:
            subdomain = center.subdomain  # Keep existing
        
        # Owner - only superuser can change
        if request.user.is_superuser:
            owner_id = request.POST.get("owner_id", "").strip()
            if owner_id:
                try:
                    new_owner = User.objects.get(pk=owner_id, is_active=True)
                    center.owner = new_owner
                except User.DoesNotExist:
                    messages.error(request, "Selected owner not found.")
                    return redirect("center_edit", center_id=center_id)
        
        # Bot fields
        company_orders_channel_id = request.POST.get("company_orders_channel_id", "").strip() or None
        bot_username = request.POST.get("bot_username", "").strip().lstrip("@") or None
        # Only superuser can edit bot_token
        if request.user.is_superuser:
            bot_token = request.POST.get("bot_token", "").strip() or None
        else:
            bot_token = center.bot_token  # Keep existing

        if not name:
            messages.error(request, "Center name is required.")
        elif subdomain and TranslationCenter.objects.filter(subdomain=subdomain).exclude(pk=center_id).exists():
            messages.error(request, "This subdomain is already in use by another center.")
        elif bot_token and TranslationCenter.objects.filter(bot_token=bot_token).exclude(pk=center_id).exists():
            messages.error(request, "This bot token is already in use by another center.")
        else:
            center.name = name
            center.subdomain = subdomain
            center.phone = phone or None
            center.email = email or None
            center.address = address or None
            center.location_url = location_url or None
            center.is_active = is_active
            center.bot_token = bot_token
            center.bot_username = bot_username
            center.company_orders_channel_id = company_orders_channel_id
            center.save()
            messages.success(request, f'Center "{name}" updated successfully!')
            return redirect("center_list")

    context = {
        "title": "Edit Center",
        "subTitle": f"Edit {center.name}",
        "center": center,
        "is_superuser": request.user.is_superuser,
        "available_owners": available_owners,
    }
    return render(request, "organizations/center_form.html", context)


@login_required(login_url="admin_login")
@permission_required('can_view_centers')
def center_detail(request, center_id):
    """View translation center details with branches, staff, categories, products"""
    from services.models import Category, Product
    from orders.models import Order
    from accounts.models import BotUser

    if request.user.is_superuser:
        center = get_object_or_404(TranslationCenter, pk=center_id)
    else:
        # Check if user belongs to this center via their AdminUser profile
        profile = getattr(request.user, 'admin_profile', None)
        if not profile or profile.center_id != center_id:
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden("You don't have access to this center.")
        center = get_object_or_404(TranslationCenter, pk=center_id)

    # Get branches for this center
    branches = (
        Branch.objects.filter(center=center)
        .select_related("region", "district")
        .annotate(
            staff_count=Count("staff"),
            customer_count=Count("customers"),
            order_count=Count("orders"),
        )
        .order_by("-is_main", "name")
    )

    # Get staff for this center
    staff = (
        AdminUser.objects.filter(branch__center=center)
        .select_related("user", "branch", "role")
        .order_by("branch", "user__first_name")
    )

    # Get categories for this center's branches
    categories = (
        Category.objects.filter(branch__center=center)
        .select_related("branch")
        .order_by("branch", "name")
    )

    # Get products for this center
    products = (
        Product.objects.filter(category__branch__center=center)
        .select_related("category", "category__branch")
        .order_by("category__branch", "category", "name")[:10]
    )

    # Get recent orders for this center
    recent_orders = (
        Order.objects.filter(branch__center=center)
        .select_related("bot_user", "branch", "product")
        .order_by("-created_at")[:5]
    )

    # Get customers for this center
    customers = (
        BotUser.objects.filter(branch__center=center)
        .select_related("branch")
        .order_by("-created_at")[:10]
    )

    context = {
        "title": center.name,
        "subTitle": "Center Details",
        "center": center,
        "branches": branches,
        "staff": staff,
        "categories": categories,
        "products": products,
        "recent_orders": recent_orders,
        "customers": customers,
        "total_branches": branches.count(),
        "total_staff": staff.count(),
        "total_categories": categories.count(),
        "total_products": Product.objects.filter(
            category__branch__center=center
        ).count(),
        "total_orders": Order.objects.filter(branch__center=center).count(),
        "total_customers": BotUser.objects.filter(branch__center=center).count(),
    }
    return render(request, "organizations/center_detail.html", context)


# ============ Branch Views ============


@login_required(login_url="admin_login")
def branch_list(request):
    """List branches accessible by the current user"""
    branches = (
        get_user_branches(request.user)
        .select_related("center", "region", "district")
        .annotate(
            staff_count=Count("staff"),
            customer_count=Count("customers"),
        )
        .order_by("center", "name")
    )

    # Filter by center if specified
    center_id = request.GET.get("center")
    if center_id:
        branches = branches.filter(center_id=center_id)

    # Pagination - 6 items per page
    paginator = Paginator(branches, 6)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    # Get centers for filter dropdown
    if request.user.is_superuser:
        centers = TranslationCenter.objects.filter(is_active=True)
    else:
        profile = getattr(request.user, 'admin_profile', None)
        if profile and profile.center:
            centers = TranslationCenter.objects.filter(pk=profile.center_id, is_active=True)
        else:
            centers = TranslationCenter.objects.none()

    context = {
        "title": "Branches",
        "subTitle": "Manage Branches",
        "branches": page_obj,
        "paginator": paginator,
        "total_branches": paginator.count,
        "centers": centers,
        "selected_center": center_id,
    }
    return render(request, "organizations/branch_list.html", context)


@login_required(login_url="admin_login")
@permission_required("can_manage_branches")
def branch_create(request, center_id=None):
    """Create a new branch"""
    from core.models import Region, District

    # Get centers the user can manage
    if request.user.is_superuser:
        centers = TranslationCenter.objects.filter(is_active=True)
    else:
        profile = getattr(request.user, 'admin_profile', None)
        if profile and profile.center:
            centers = TranslationCenter.objects.filter(pk=profile.center_id, is_active=True)
        else:
            centers = TranslationCenter.objects.none()

    if center_id:
        center = get_object_or_404(centers, pk=center_id)
    else:
        center = None

    regions = Region.objects.filter(is_active=True)

    if request.method == "POST":
        center_id = request.POST.get("center")
        name = request.POST.get("name", "").strip()
        region_id = request.POST.get("region")
        district_id = request.POST.get("district")
        address = request.POST.get("address", "").strip()
        phone = request.POST.get("phone", "").strip()
        location_url = request.POST.get("location_url", "").strip()
        # Channel fields
        b2c_orders_channel_id = request.POST.get("b2c_orders_channel_id", "").strip() or None
        b2b_orders_channel_id = request.POST.get("b2b_orders_channel_id", "").strip() or None
        # Bot settings
        show_pricelist = request.POST.get("show_pricelist") == "on"

        if not name:
            messages.error(request, "Branch name is required.")
        elif not center_id:
            messages.error(request, "Please select a center.")
        else:
            center = get_object_or_404(centers, pk=center_id)
            branch = Branch.objects.create(
                center=center,
                name=name,
                region_id=region_id or None,
                district_id=district_id or None,
                address=address or None,
                phone=phone or None,
                location_url=location_url or None,
                b2c_orders_channel_id=b2c_orders_channel_id,
                b2b_orders_channel_id=b2b_orders_channel_id,
                show_pricelist=show_pricelist,
            )
            messages.success(request, f'Branch "{name}" created successfully!')
            return redirect("branch_list")

    context = {
        "title": "Create Branch",
        "subTitle": "Add New Branch",
        "centers": centers,
        "selected_center": center,
        "regions": regions,
    }
    return render(request, "organizations/branch_form.html", context)


@login_required(login_url="admin_login")
def branch_detail(request, branch_id):
    """View branch details with staff, categories, products, orders"""
    from services.models import Category, Product
    from orders.models import Order
    from accounts.models import BotUser

    # Get branch with RBAC check
    accessible_branches = get_user_branches(request.user)
    branch = get_object_or_404(
        accessible_branches.select_related("center", "region", "district"), pk=branch_id
    )

    # Get staff for this branch
    staff = (
        AdminUser.objects.filter(branch=branch)
        .select_related("user", "role")
        .order_by("user__first_name")
    )

    # Get categories for this branch
    categories = (
        Category.objects.filter(branch=branch)
        .annotate(product_count=Count("product"))
        .order_by("name")
    )

    # Get products for this branch
    products = (
        Product.objects.filter(category__branch=branch)
        .select_related("category")
        .order_by("category", "name")[:10]
    )

    # Get recent orders for this branch
    recent_orders = (
        Order.objects.filter(branch=branch)
        .select_related("bot_user", "product", "assigned_to__user")
        .order_by("-created_at")[:10]
    )

    # Get customers for this branch
    customers = BotUser.objects.filter(branch=branch).order_by("-created_at")[:10]

    context = {
        "title": branch.name,
        "subTitle": "Branch Details",
        "branch": branch,
        "staff": staff,
        "categories": categories,
        "products": products,
        "recent_orders": recent_orders,
        "customers": customers,
        "total_staff": staff.count(),
        "total_categories": categories.count(),
        "total_products": Product.objects.filter(category__branch=branch).count(),
        "total_orders": Order.objects.filter(branch=branch).count(),
        "total_customers": BotUser.objects.filter(branch=branch).count(),
    }
    return render(request, "organizations/branch_detail.html", context)


@login_required(login_url="admin_login")
@permission_required("can_manage_branches")
def branch_edit(request, branch_id):
    """Edit an existing branch"""
    from core.models import Region, District

    branch = get_object_or_404(Branch, pk=branch_id)

    # Check access - user must belong to this center
    if not request.user.is_superuser:
        profile = getattr(request.user, 'admin_profile', None)
        if not profile or profile.center_id != branch.center_id:
            messages.error(request, "You don't have permission to edit this branch.")
            return redirect("branch_list")

    regions = Region.objects.filter(is_active=True)
    districts = (
        District.objects.filter(region=branch.region)
        if branch.region
        else District.objects.none()
    )

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        region_id = request.POST.get("region")
        district_id = request.POST.get("district")
        address = request.POST.get("address", "").strip()
        phone = request.POST.get("phone", "").strip()
        location_url = request.POST.get("location_url", "").strip()
        is_active = request.POST.get("is_active") == "on"
        # Channel fields
        b2c_orders_channel_id = request.POST.get("b2c_orders_channel_id", "").strip() or None
        b2b_orders_channel_id = request.POST.get("b2b_orders_channel_id", "").strip() or None
        # Bot settings
        show_pricelist = request.POST.get("show_pricelist") == "on"

        if not name:
            messages.error(request, "Branch name is required.")
        else:
            branch.name = name
            branch.region_id = region_id or None
            branch.district_id = district_id or None
            branch.address = address or None
            branch.phone = phone or None
            branch.location_url = location_url or None
            branch.is_active = is_active
            branch.b2c_orders_channel_id = b2c_orders_channel_id
            branch.b2b_orders_channel_id = b2b_orders_channel_id
            branch.show_pricelist = show_pricelist
            branch.save()
            messages.success(request, f'Branch "{name}" updated successfully!')
            return redirect("branch_list")

    context = {
        "title": "Edit Branch",
        "subTitle": f"Edit {branch.name}",
        "branch": branch,
        "regions": regions,
        "districts": districts,
    }
    return render(request, "organizations/branch_form.html", context)


# ============ Staff Management Views ============


@login_required(login_url="admin_login")
@can_view_staff_required
def staff_list(request):
    """List staff members the current user can manage or view"""
    from django.db.models import Count, Q as DQ
    
    staff = (
        get_user_staff(request.user)
        .select_related("user", "role", "branch", "branch__center")
        .annotate(
            orders_in_progress=Count('assigned_orders', filter=DQ(assigned_orders__status='in_progress')),
            orders_completed=Count('assigned_orders', filter=DQ(assigned_orders__status='completed')),
            orders_cancelled=Count('assigned_orders', filter=DQ(assigned_orders__status='cancelled')),
            orders_pending=Count('assigned_orders', filter=DQ(assigned_orders__status='pending')),
            orders_total=Count('assigned_orders'),
        )
        .order_by("-created_at")
    )

    # Determine if user can manage staff (for showing add/edit buttons)
    user_can_manage_staff = (
        request.user.is_superuser or 
        (request.admin_profile and request.admin_profile.has_permission('can_manage_staff'))
    )

    # Center filter for superuser
    centers = None
    center_filter = request.GET.get("center")
    if request.user.is_superuser:
        centers = TranslationCenter.objects.filter(is_active=True)
        if center_filter:
            staff = staff.filter(branch__center_id=center_filter)

    # Filter by role
    role_filter = request.GET.get("role")
    if role_filter:
        staff = staff.filter(role__name=role_filter)

    # Filter by branch
    branch_id = request.GET.get("branch")
    if branch_id:
        staff = staff.filter(branch_id=branch_id)

    # Search
    search = request.GET.get("search", "")
    if search:
        staff = staff.filter(
            Q(user__first_name__icontains=search)
            | Q(user__last_name__icontains=search)
            | Q(user__username__icontains=search)
            | Q(phone__icontains=search)
        )

    # Get branches for filter
    accessible_branches = get_user_branches(request.user)
    if request.user.is_superuser and center_filter:
        accessible_branches = accessible_branches.filter(center_id=center_filter)
    roles = Role.objects.all()

    # Pagination
    paginator = Paginator(staff, 10)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    context = {
        "title": "Staff Management",
        "subTitle": "Manage Staff Members",
        "staff": page_obj,
        "branches": accessible_branches,
        "roles": roles,
        "role_filter": role_filter,
        "branch_filter": branch_id,
        "search": search,
        "centers": centers,
        "center_filter": center_filter,
        "can_manage_staff": user_can_manage_staff,
    }
    return render(request, "organizations/staff_list.html", context)


@login_required(login_url="admin_login")
@permission_required("can_manage_staff")
def staff_create(request):
    """Create a new staff member"""
    accessible_branches = get_user_branches(request.user)

    # Get assignable roles for current user using RBAC helper
    roles = get_assignable_roles(request.user)

    if request.method == "POST":
        # User info
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        password = request.POST.get("password", "")

        # Admin profile info
        role_id = request.POST.get("role")
        branch_id = request.POST.get("branch")
        phone = request.POST.get("phone", "").strip()

        # Validation
        errors = []
        if not username:
            errors.append("Username is required.")
        if not email:
            errors.append("Email is required.")
        if not first_name:
            errors.append("First name is required.")
        if not password:
            errors.append("Password is required.")
        if not role_id:
            errors.append("Role is required.")
        if not branch_id:
            errors.append("Branch is required.")

        if User.objects.filter(username=username).exists():
            errors.append("Username already exists.")

        # Validate role assignment
        if role_id and branch_id:
            try:
                role = Role.objects.get(pk=role_id)
                branch = Branch.objects.get(pk=branch_id)
                center = branch.center
                
                # Validate role assignment using RBAC helper
                is_valid, error_msg = AdminUser.validate_role_assignment(
                    request.user, role, center=center
                )
                if not is_valid:
                    errors.append(error_msg)
                
                # Verify the role is in the assignable roles list
                if not roles.filter(pk=role_id).exists():
                    errors.append("You don't have permission to assign this role.")
            except (Role.DoesNotExist, Branch.DoesNotExist):
                errors.append("Invalid role or branch selected.")

        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_staff=True,  # Allow admin access
            )

            # Get role and branch
            role = get_object_or_404(roles, pk=role_id)
            branch = get_object_or_404(accessible_branches, pk=branch_id)

            # Check if this will replace an existing owner
            previous_owner = None
            if role.name == Role.OWNER:
                previous_owner = AdminUser.objects.filter(
                    role__name=Role.OWNER,
                    center=branch.center,
                    is_active=True
                ).first()

            # Create admin profile
            try:
                admin_profile = AdminUser.objects.create(
                    user=user,
                    role=role,
                    branch=branch,
                    center=branch.center,
                    phone=phone or None,
                    created_by=request.user,
                )

                # Notify about previous owner replacement
                if previous_owner:
                    messages.info(
                        request,
                        f'Previous owner "{previous_owner.user.get_full_name()}" has been unlinked from this center.'
                    )

                # Audit log the creation
                log_create(
                    user=request.user,
                    target=admin_profile,
                    request=request,
                    details=f"Created staff: {first_name} {last_name} ({role.name}) in {branch.name}",
                )

                messages.success(
                    request,
                    f'Staff member "{first_name} {last_name}" created successfully!',
                )
                return redirect("staff_list")
            except Exception as e:
                # Clean up the created user if AdminUser creation fails
                user.delete()
                messages.error(request, f"Failed to create staff member: {str(e)}")

    # Get display permissions organized by category
    all_permissions = Role.get_display_permissions()
    permission_labels = Role.get_permission_labels()
    permission_categories = Role.get_display_permission_categories()

    context = {
        "title": "Add Staff",
        "subTitle": "Create New Staff Member",
        "branches": accessible_branches,
        "roles": roles,
        "all_permissions": all_permissions,
        "permission_labels": permission_labels,
        "permission_categories": permission_categories,
    }
    return render(request, "organizations/staff_form.html", context)


@login_required(login_url="admin_login")
@permission_required("can_manage_staff")
def staff_edit(request, staff_id):
    """Edit an existing staff member"""
    staff_member = get_object_or_404(AdminUser, pk=staff_id)

    # Check if user can edit this staff member
    if not can_edit_staff(request.user, staff_member):
        messages.error(
            request, "You don't have permission to edit this staff member."
        )
        return redirect("staff_detail", staff_id=staff_id)

    accessible_branches = get_user_branches(request.user)

    # Use RBAC helper for assignable roles
    roles = get_assignable_roles(request.user)

    if request.method == "POST":
        # User info
        email = request.POST.get("email", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        password = request.POST.get("password", "")

        # Admin profile info
        role_id = request.POST.get("role")
        branch_id = request.POST.get("branch")
        phone = request.POST.get("phone", "").strip()
        is_active = request.POST.get("is_active") == "on"

        errors = []
        if not first_name:
            errors.append("First name is required.")
        if not email:
            errors.append("Email is required.")

        # Validate role assignment
        if role_id and branch_id:
            try:
                role = Role.objects.get(pk=role_id)
                branch = Branch.objects.get(pk=branch_id)
                center = branch.center
                
                # Validate role assignment using RBAC helper
                is_valid, error_msg = AdminUser.validate_role_assignment(
                    request.user, role, center=center, exclude_pk=staff_member.pk
                )
                if not is_valid:
                    errors.append(error_msg)
                
                # Verify the role is in the assignable roles list
                if not roles.filter(pk=role_id).exists():
                    errors.append("You don't have permission to assign this role.")
            except (Role.DoesNotExist, Branch.DoesNotExist):
                errors.append("Invalid role or branch selected.")

        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            # Update user
            user = staff_member.user
            user.email = email
            user.first_name = first_name
            user.last_name = last_name
            user.is_staff = True  # Ensure admin access is enabled
            if password:
                user.set_password(password)
            user.save()

            # Check if this will replace an existing owner (when changing TO owner role)
            previous_owner = None
            new_role = Role.objects.get(pk=role_id)
            new_branch = Branch.objects.get(pk=branch_id)
            if new_role.name == Role.OWNER:
                previous_owner = AdminUser.objects.filter(
                    role__name=Role.OWNER,
                    center=new_branch.center,
                    is_active=True
                ).exclude(pk=staff_member.pk).first()

            # Update profile
            try:
                old_role = staff_member.role
                staff_member.role_id = role_id
                staff_member.branch_id = branch_id
                staff_member.center = (
                    Branch.objects.get(pk=branch_id).center if branch_id else None
                )
                staff_member.phone = phone or None
                staff_member.is_active = is_active
                staff_member.save()

                # Notify about previous owner replacement
                if previous_owner:
                    messages.info(
                        request,
                        f'Previous owner "{previous_owner.user.get_full_name()}" has been unlinked from this center.'
                    )

                # Log the update
                log_update(
                    user=request.user,
                    target=staff_member,
                    changes={"role": f"{old_role.name} -> {staff_member.role.name}"},
                    request=request,
                )

                messages.success(
                    request,
                    f'Staff member "{first_name} {last_name}" updated successfully!',
                )
                return redirect("staff_list")
            except Exception as e:
                messages.error(request, f"Failed to update staff member: {str(e)}")

    # Get display permissions organized by category
    all_permissions = Role.get_display_permissions()
    permission_labels = Role.get_permission_labels()
    permission_categories = Role.get_display_permission_categories()

    context = {
        "title": "Edit Staff",
        "subTitle": f"Edit {staff_member.user.get_full_name()}",
        "staff_member": staff_member,
        "branches": accessible_branches,
        "roles": roles,
        "all_permissions": all_permissions,
        "permission_labels": permission_labels,
        "permission_categories": permission_categories,
    }
    return render(request, "organizations/staff_form.html", context)


@login_required(login_url="admin_login")
@permission_required("can_manage_staff")
def staff_toggle_active(request, staff_id):
    """Toggle staff member active status"""
    if request.method != "POST":
        return redirect("staff_list")

    staff_member = get_object_or_404(AdminUser, pk=staff_id)

    # Check access
    if not request.user.is_superuser:
        accessible_staff = get_user_staff(request.user)
        if not accessible_staff.filter(pk=staff_id).exists():
            messages.error(
                request, "You don't have permission to modify this staff member."
            )
            return redirect("staff_list")

    staff_member.is_active = not staff_member.is_active
    staff_member.save()

    status = "activated" if staff_member.is_active else "deactivated"
    messages.success(
        request, f"Staff member {staff_member.user.get_full_name()} has been {status}."
    )
    return redirect("staff_list")


@login_required(login_url="admin_login")
@can_view_staff_required
def staff_detail(request, staff_id):
    """
    View staff member details including profile and related objects.
    Managers have read-only access, Owners/Superusers can edit.
    """
    from orders.models import Order
    from django.db.models import Sum, Count
    from django.utils import timezone
    from datetime import timedelta

    staff_member = get_object_or_404(
        AdminUser.objects.select_related("user", "role", "branch", "branch__center", "created_by"),
        pk=staff_id
    )

    # Check access - user must be able to view this staff member
    if not request.user.is_superuser:
        accessible_staff = get_user_staff(request.user)
        # Also allow viewing if user has can_view_staff permission and is in same center
        if not accessible_staff.filter(pk=staff_id).exists():
            if request.admin_profile and request.admin_profile.center:
                if staff_member.center and staff_member.center.id != request.admin_profile.center.id:
                    messages.error(request, "You don't have permission to view this staff member.")
                    return redirect("staff_list")
            else:
                messages.error(request, "You don't have permission to view this staff member.")
                return redirect("staff_list")

    # Determine if user can edit this staff member
    user_can_edit = can_edit_staff(request.user, staff_member)

    # Get assigned orders for this staff member
    assigned_orders = Order.objects.filter(
        assigned_to=staff_member
    ).select_related("bot_user", "product", "branch").order_by("-created_at")[:10]

    # Get orders completed by this staff member
    completed_orders = Order.objects.filter(
        completed_by=staff_member
    ).select_related("bot_user", "product", "branch").order_by("-completed_at")[:10]

    # Get orders where payment was received by this staff member
    payments_received = Order.objects.filter(
        payment_received_by=staff_member
    ).select_related("bot_user", "product", "branch").order_by("-payment_received_at")[:10]

    # Statistics
    today = timezone.now().date()
    last_30_days = today - timedelta(days=30)

    stats = {
        "total_assigned": Order.objects.filter(assigned_to=staff_member).count(),
        "total_completed": Order.objects.filter(completed_by=staff_member).count(),
        "total_payments_received": Order.objects.filter(payment_received_by=staff_member).count(),
        "completed_this_month": Order.objects.filter(
            completed_by=staff_member,
            completed_at__date__gte=last_30_days
        ).count(),
        "total_revenue_received": Order.objects.filter(
            payment_received_by=staff_member
        ).aggregate(total=Sum("total_price"))["total"] or 0,
        "active_orders": Order.objects.filter(
            assigned_to=staff_member,
            status__in=["pending", "in_progress", "payment_pending", "payment_received"]
        ).count(),
    }

    # Get role permissions organized by category for display
    permission_categories = Role.get_permission_categories()
    permission_labels = Role.get_permission_labels()
    
    role_permission_categories = {}
    for key, category in permission_categories.items():
        enabled_perms = []
        for perm in category["permissions"]:
            if getattr(staff_member.role, perm, False):
                label = permission_labels.get(perm, perm.replace("_", " ").title())
                is_master = perm in Role.MASTER_PERMISSIONS
                enabled_perms.append({
                    "name": perm,
                    "label": label,
                    "is_master": is_master,
                })
        if enabled_perms:  # Only include categories that have enabled permissions
            role_permission_categories[key] = {
                "title": category["title"],
                "icon": category["icon"],
                "color": category["color"],
                "permissions": enabled_perms,
            }

    context = {
        "title": staff_member.user.get_full_name() or staff_member.user.username,
        "subTitle": "Staff Details",
        "staff_member": staff_member,
        "assigned_orders": assigned_orders,
        "completed_orders": completed_orders,
        "payments_received": payments_received,
        "stats": stats,
        "permission_categories": role_permission_categories,
        "can_edit": user_can_edit,
        "is_read_only": not user_can_edit,
    }
    return render(request, "organizations/staff_detail.html", context)


# ============ API Endpoints ============

from django.http import JsonResponse


@login_required(login_url="admin_login")
def get_districts(request, region_id):
    """AJAX endpoint to get districts for a region"""
    from core.models import District

    districts = District.objects.filter(region_id=region_id, is_active=True).values(
        "id", "name"
    )
    return JsonResponse(list(districts), safe=False)


@login_required(login_url="admin_login")
def get_branch_staff(request, branch_id):
    """AJAX endpoint to get staff for a branch"""
    branch = get_object_or_404(Branch, pk=branch_id)

    # Check access
    if not request.user.is_superuser:
        accessible_branches = get_user_branches(request.user)
        if not accessible_branches.filter(pk=branch_id).exists():
            return JsonResponse({"error": "Access denied"}, status=403)

    staff = (
        AdminUser.objects.filter(branch=branch, is_active=True)
        .select_related("user", "role")
        .values("id", "user__first_name", "user__last_name", "role__name")
    )

    result = [
        {
            "id": s["id"],
            "name": f"{s['user__first_name']} {s['user__last_name']}",
            "role": s["role__name"],
        }
        for s in staff
    ]

    return JsonResponse(result, safe=False)


@login_required(login_url="admin_login")
def create_region(request):
    """API endpoint to create a new region (superuser only)"""
    if not request.user.is_superuser:
        return JsonResponse({"success": False, "error": "Permission denied"}, status=403)
    
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid method"}, status=405)
    
    from core.models import Region
    
    name = request.POST.get("name", "").strip()
    code = request.POST.get("code", "").strip().upper()
    
    if not name or not code:
        return JsonResponse({"success": False, "error": "Name and code are required"})
    
    # Check for duplicate code
    if Region.objects.filter(code=code).exists():
        return JsonResponse({"success": False, "error": f"Region with code '{code}' already exists"})
    
    try:
        region = Region.objects.create(name=name, code=code, is_active=True)
        return JsonResponse({
            "success": True,
            "region": {"id": region.id, "name": region.name, "code": region.code}
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required(login_url="admin_login")
def create_district(request):
    """API endpoint to create a new district (superuser only)"""
    if not request.user.is_superuser:
        return JsonResponse({"success": False, "error": "Permission denied"}, status=403)
    
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid method"}, status=405)
    
    from core.models import Region, District
    
    region_id = request.POST.get("region")
    name = request.POST.get("name", "").strip()
    code = request.POST.get("code", "").strip().upper()
    
    if not region_id or not name or not code:
        return JsonResponse({"success": False, "error": "Region, name and code are required"})
    
    # Verify region exists
    try:
        region = Region.objects.get(pk=region_id)
    except Region.DoesNotExist:
        return JsonResponse({"success": False, "error": "Region not found"})
    
    # Check for duplicate code
    if District.objects.filter(code=code).exists():
        return JsonResponse({"success": False, "error": f"District with code '{code}' already exists"})
    
    try:
        district = District.objects.create(region=region, name=name, code=code, is_active=True)
        return JsonResponse({
            "success": True,
            "district": {"id": district.id, "name": district.name, "code": district.code, "region_id": region.id}
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required(login_url="admin_login")
@require_POST
def api_create_user(request):
    """API endpoint to create a new user (superuser only)"""
    if not request.user.is_superuser:
        return JsonResponse({"success": False, "error": "Permission denied"}, status=403)
    
    import json
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON data"}, status=400)
    
    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    first_name = data.get("first_name", "").strip()
    last_name = data.get("last_name", "").strip()
    password = data.get("password", "")
    
    # Validation
    if not username:
        return JsonResponse({"success": False, "error": "Username is required"})
    if not first_name:
        return JsonResponse({"success": False, "error": "First name is required"})
    if not password or len(password) < 6:
        return JsonResponse({"success": False, "error": "Password must be at least 6 characters"})
    
    # Check for duplicate username
    if User.objects.filter(username=username).exists():
        return JsonResponse({"success": False, "error": f"Username '{username}' is already taken"})
    
    # Check for duplicate email if provided
    if email and User.objects.filter(email=email).exists():
        return JsonResponse({"success": False, "error": f"Email '{email}' is already in use"})
    
    try:
        user = User.objects.create_user(
            username=username,
            email=email or None,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_staff=True,  # Allow admin access
            is_active=True
        )
        
        return JsonResponse({
            "success": True,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email or "",
                "full_name": user.get_full_name() or user.username
            }
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


# ============ Role Management Views (Superuser Only) ============


@login_required(login_url="admin_login")
def role_list(request):
    """List all roles - superuser only"""
    if not request.user.is_superuser:
        messages.error(request, "Only superusers can manage roles.")
        return redirect("index")

    roles = Role.objects.annotate(user_count=Count("users")).order_by(
        "-is_system_role", "name"
    )

    context = {
        "title": "Role Management",
        "subTitle": "Manage Roles & Permissions",
        "roles": roles,
        "available_permissions": Role.get_all_permissions(),
    }
    return render(request, "organizations/role_list.html", context)


@login_required(login_url="admin_login")
def role_create(request):
    """Create a new role - superuser only"""
    if not request.user.is_superuser:
        messages.error(request, "Only superusers can create roles.")
        return redirect("index")

    available_permissions = Role.get_all_permissions()

    if request.method == "POST":
        name = request.POST.get("name", "").strip().lower().replace(" ", "_")
        display_name = request.POST.get("display_name", "").strip()
        description = request.POST.get("description", "").strip()
        is_active = request.POST.get("is_active") == "on"

        if not name:
            messages.error(request, "Role name is required.")
        elif Role.objects.filter(name=name).exists():
            messages.error(request, "A role with this name already exists.")
        else:
            role = Role.objects.create(
                name=name,
                display_name=display_name or name.replace("_", " ").title(),
                description=description,
                is_active=is_active,
            )

            # Set permissions from checkboxes
            for perm in available_permissions:
                setattr(role, perm, request.POST.get(perm) == "on")
            role.save()

            log_create(user=request.user, target=role, request=request)
            messages.success(
                request, f'Role "{role.display_name}" created successfully!'
            )
            return redirect("role_list")

    context = {
        "title": "Create Role",
        "subTitle": "Create New Role",
        "available_permissions": available_permissions,
        "permission_labels": Role.get_permission_labels(),
    }
    return render(request, "organizations/role_form.html", context)


@login_required(login_url="admin_login")
def role_edit(request, role_id):
    """Edit a role - superuser only"""
    if not request.user.is_superuser:
        messages.error(request, "Only superusers can edit roles.")
        return redirect("index")

    role = get_object_or_404(Role, pk=role_id)
    available_permissions = Role.get_all_permissions()

    if request.method == "POST":
        display_name = request.POST.get("display_name", "").strip()
        description = request.POST.get("description", "").strip()
        is_active = request.POST.get("is_active") == "on"

        # Don't allow changing system role names
        if not role.is_system_role:
            name = request.POST.get("name", "").strip().lower().replace(" ", "_")
            if name and name != role.name:
                if Role.objects.filter(name=name).exclude(pk=role.pk).exists():
                    messages.error(request, "A role with this name already exists.")
                    return redirect("role_edit", role_id=role_id)
                role.name = name

        role.display_name = display_name or role.name.replace("_", " ").title()
        role.description = description
        role.is_active = is_active

        # Set permissions from checkboxes
        for perm in available_permissions:
            setattr(role, perm, request.POST.get(perm) == "on")

        role.save()

        log_update(
            user=request.user,
            target=role,
            changes={"permissions": "updated"},
            request=request,
        )
        messages.success(request, f'Role "{role.display_name}" updated successfully!')
        return redirect("role_list")

    context = {
        "title": "Edit Role",
        "subTitle": f"Edit Role: {role.display_name}",
        "role": role,
        "available_permissions": available_permissions,
        "permission_labels": Role.get_permission_labels(),
    }
    return render(request, "organizations/role_form.html", context)


@login_required(login_url="admin_login")
def role_delete(request, role_id):
    """Delete a role - superuser only, cannot delete system roles"""
    if not request.user.is_superuser:
        messages.error(request, "Only superusers can delete roles.")
        return redirect("index")

    role = get_object_or_404(Role, pk=role_id)

    if role.is_system_role:
        messages.error(request, "System roles cannot be deleted.")
        return redirect("role_list")

    if role.users.exists():
        messages.error(
            request,
            f'Cannot delete role "{role.display_name}" - it has {role.users.count()} users assigned.',
        )
        return redirect("role_list")

    if request.method == "POST":
        role_name = role.display_name
        log_delete(user=request.user, target=role, request=request)
        role.delete()
        messages.success(request, f'Role "{role_name}" deleted successfully!')
        return redirect("role_list")

    return redirect("role_list")


# ============ Webhook Management Views ============

from django.http import JsonResponse
from django.views.decorators.http import require_POST


@login_required(login_url="admin_login")
@require_POST
def setup_center_webhook(request, center_id):
    """Set up Telegram webhook for a center - superuser only"""
    if not request.user.is_superuser:
        return JsonResponse({"success": False, "error": "Superuser access required"}, status=403)
    
    center = get_object_or_404(TranslationCenter, pk=center_id)
    
    if not center.bot_token:
        return JsonResponse({"success": False, "error": "No bot token configured"}, status=400)
    
    # Get base URL from request or settings
    base_url = request.POST.get("base_url") or request.build_absolute_uri("/").rstrip("/")
    
    from bot.webhook_manager import setup_webhook_for_center
    result = setup_webhook_for_center(center, base_url)
    
    if result["success"]:
        log_update(
            user=request.user,
            target=center,
            changes={"webhook": f"Set up: {result.get('webhook_url')}"},
            request=request
        )
    
    return JsonResponse(result)


@login_required(login_url="admin_login")
@require_POST
def remove_center_webhook(request, center_id):
    """Remove Telegram webhook for a center - superuser only"""
    if not request.user.is_superuser:
        return JsonResponse({"success": False, "error": "Superuser access required"}, status=403)
    
    center = get_object_or_404(TranslationCenter, pk=center_id)
    
    from bot.webhook_manager import remove_webhook_for_center
    result = remove_webhook_for_center(center)
    
    if result["success"]:
        log_update(
            user=request.user,
            target=center,
            changes={"webhook": "Removed"},
            request=request
        )
    
    return JsonResponse(result)


@login_required(login_url="admin_login")
def get_center_webhook_info(request, center_id):
    """Get webhook info for a center - superuser only"""
    if not request.user.is_superuser:
        return JsonResponse({"success": False, "error": "Superuser access required"}, status=403)
    
    center = get_object_or_404(TranslationCenter, pk=center_id)
    
    from bot.webhook_manager import get_webhook_info
    result = get_webhook_info(center)
    
    return JsonResponse(result)


# ============ Branch Settings (Additional Info) Views ============


@login_required(login_url="admin_login")
def branch_settings(request, branch_id):
    """
    View branch settings (Additional Info).
    Requires can_view_branch_settings or can_manage_branch_settings permission.
    """
    from accounts.models import AdditionalInfo
    
    branch = get_object_or_404(Branch, pk=branch_id)
    
    # Permission check
    if not request.user.is_superuser:
        if not request.admin_profile:
            messages.error(request, "You need an admin profile to access this page.")
            return redirect('index')
        
        # Check if user has permission
        has_view_perm = request.admin_profile.has_permission('can_view_branch_settings')
        has_manage_perm = request.admin_profile.has_permission('can_manage_branch_settings')
        
        if not (has_view_perm or has_manage_perm):
            messages.error(request, "You don't have permission to view branch settings.")
            return redirect('branch_detail', branch_id=branch_id)
        
        # Check if user has access to this branch
        if not request.is_owner:
            user_branch = request.admin_profile.branch
            if user_branch and user_branch.id != branch_id:
                messages.error(request, "You can only view settings for your own branch.")
                return redirect('branch_detail', branch_id=user_branch.id)
    
    # Get or create additional info for this branch
    additional_info, created = AdditionalInfo.objects.get_or_create(branch=branch)
    
    # Check if user can edit
    can_edit = request.user.is_superuser or (
        request.admin_profile and 
        request.admin_profile.has_permission('can_manage_branch_settings')
    )
    
    context = {
        "title": "Branch Settings",
        "subTitle": f"Settings for {branch.name}",
        "branch": branch,
        "info": additional_info,
        "can_edit": can_edit,
    }
    return render(request, "organizations/branch_settings.html", context)


@login_required(login_url="admin_login")
def branch_settings_edit(request, branch_id):
    """
    Edit branch settings (Additional Info).
    Requires can_manage_branch_settings permission.
    """
    from accounts.models import AdditionalInfo
    
    branch = get_object_or_404(Branch, pk=branch_id)
    
    # Permission check
    if not request.user.is_superuser:
        if not request.admin_profile:
            messages.error(request, "You need an admin profile to access this page.")
            return redirect('index')
        
        # Check if user has permission
        has_manage_perm = request.admin_profile.has_permission('can_manage_branch_settings')
        
        if not has_manage_perm:
            messages.error(request, "You don't have permission to edit branch settings.")
            return redirect('branch_settings', branch_id=branch_id)
        
        # Check if user has access to this branch
        if not request.is_owner:
            user_branch = request.admin_profile.branch
            if user_branch and user_branch.id != branch_id:
                messages.error(request, "You can only edit settings for your own branch.")
                return redirect('branch_settings', branch_id=user_branch.id)
    
    # Get or create additional info for this branch
    additional_info, created = AdditionalInfo.objects.get_or_create(branch=branch)
    
    if request.method == "POST":
        # Payment Information
        additional_info.bank_card = request.POST.get("bank_card", "").strip() or None
        additional_info.holder_name = request.POST.get("holder_name", "").strip() or None
        
        # Contact Information
        additional_info.support_phone = request.POST.get("support_phone", "").strip() or None
        additional_info.support_telegram = request.POST.get("support_telegram", "").strip() or None
        
        # Working Hours
        additional_info.working_hours = request.POST.get("working_hours", "").strip() or None
        additional_info.working_hours_uz = request.POST.get("working_hours_uz", "").strip() or None
        additional_info.working_hours_ru = request.POST.get("working_hours_ru", "").strip() or None
        additional_info.working_hours_en = request.POST.get("working_hours_en", "").strip() or None
        
        # Help Text (translated)
        additional_info.help_text = request.POST.get("help_text", "").strip() or None
        additional_info.help_text_uz = request.POST.get("help_text_uz", "").strip() or None
        additional_info.help_text_ru = request.POST.get("help_text_ru", "").strip() or None
        additional_info.help_text_en = request.POST.get("help_text_en", "").strip() or None
        
        # Description (translated)
        additional_info.description = request.POST.get("description", "").strip() or None
        additional_info.description_uz = request.POST.get("description_uz", "").strip() or None
        additional_info.description_ru = request.POST.get("description_ru", "").strip() or None
        additional_info.description_en = request.POST.get("description_en", "").strip() or None
        
        # About Us (translated)
        additional_info.about_us = request.POST.get("about_us", "").strip() or None
        additional_info.about_us_uz = request.POST.get("about_us_uz", "").strip() or None
        additional_info.about_us_ru = request.POST.get("about_us_ru", "").strip() or None
        additional_info.about_us_en = request.POST.get("about_us_en", "").strip() or None
        
        # Guide URL
        additional_info.guide = request.POST.get("guide", "").strip() or None
        
        additional_info.save()
        
        # Log the update
        log_update(
            user=request.user,
            target=additional_info,
            changes={"branch_settings": f"Updated for {branch.name}"},
            request=request
        )
        
        
        messages.success(request, f"Settings for '{branch.name}' updated successfully!")
        return redirect('branch_settings', branch_id=branch_id)
    
    context = {
        "title": "Edit Branch Settings",
        "subTitle": f"Edit settings for {branch.name}",
        "branch": branch,
        "info": additional_info,
    }
    return render(request, "organizations/branch_settings_form.html", context)

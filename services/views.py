import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from decimal import Decimal, InvalidOperation
from .models import Category, Product, Language, Expense
from organizations.rbac import get_user_categories, get_user_products, get_user_branches, get_user_expenses, permission_required, any_permission_required
from organizations.models import TranslationCenter, Branch

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger('audit')


# ============ Category Views ============

@login_required(login_url='admin_login')
@any_permission_required('can_view_products', 'can_manage_products')
def categoryList(request):
    """List all categories with search and filter"""
    # Use RBAC-filtered categories
    categories = get_user_categories(request.user).select_related(
        'branch', 'branch__center'
    ).annotate(
        product_count=Count('product')
    ).order_by('-created_at')
    
    # Get accessible branches for filter dropdown
    branches = get_user_branches(request.user).select_related('center')
    
    # Center filter (superuser only)
    centers = None
    center_filter = request.GET.get('center', '')
    if request.user.is_superuser:
        centers = TranslationCenter.objects.filter(is_active=True)
        if center_filter:
            categories = categories.filter(branch__center_id=center_filter)
            branches = branches.filter(center_id=center_filter)
    
    # Branch filter
    branch_filter = request.GET.get('branch', '')
    if branch_filter:
        categories = categories.filter(branch_id=branch_filter)
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        categories = categories.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Status filter
    status_filter = request.GET.get('status', '')
    if status_filter == 'active':
        categories = categories.filter(is_active=True)
    elif status_filter == 'inactive':
        categories = categories.filter(is_active=False)
    
    # Pagination
    per_page = request.GET.get('per_page', 10)
    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 10
    
    paginator = Paginator(categories, per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Check if user is owner
    is_owner = False
    if hasattr(request.user, 'staff_profile') and request.user.staff_profile.role:
        is_owner = request.user.staff_profile.role.name == 'owner'
    
    context = {
        "title": "Categories",
        "subTitle": "Categories",
        "categories": page_obj,
        "branches": branches,
        "branch_filter": branch_filter,
        "centers": centers,
        "center_filter": center_filter,
        "search_query": search_query,
        "status_filter": status_filter,
        "per_page": per_page,
        "total_categories": paginator.count,
        "is_owner": is_owner,
    }
    return render(request, "services/categoryList.html", context)


@login_required(login_url='admin_login')
@any_permission_required('can_view_products', 'can_manage_products')
def categoryDetail(request, category_id):
    """View category details with its products"""
    # Get category with RBAC check
    accessible_categories = get_user_categories(request.user)
    category = get_object_or_404(accessible_categories.select_related('branch', 'branch__center'), id=category_id)
    products = Product.objects.filter(category=category).order_by('-created_at')
    
    context = {
        "title": f"Category: {category.name}",
        "subTitle": "Category Details",
        "category": category,
        "products": products,
        "product_count": products.count(),
    }
    return render(request, "services/categoryDetail.html", context)


@login_required(login_url='admin_login')
@any_permission_required('can_create_products', 'can_manage_products')
def addCategory(request):
    """Add a new category"""
    languages = Language.objects.all()
    branches = get_user_branches(request.user).select_related('center')
    
    if request.method == 'POST':
        # Get translated fields
        name_uz = request.POST.get('name_uz', '').strip()
        name_ru = request.POST.get('name_ru', '').strip()
        name_en = request.POST.get('name_en', '').strip()
        description_uz = request.POST.get('description_uz', '').strip()
        description_ru = request.POST.get('description_ru', '').strip()
        description_en = request.POST.get('description_en', '').strip()
        
        branch_id = request.POST.get('branch', '')
        charging = request.POST.get('charging', 'dynamic')
        is_active = request.POST.get('is_active') == 'on'
        selected_languages = request.POST.getlist('languages')
        
        # Use Uzbek name as primary (fallback to any available)
        name = name_uz or name_ru or name_en
        
        if not name:
            messages.error(request, 'Category name is required in at least one language.')
        elif not branch_id:
            messages.error(request, 'Branch is required.')
        elif Category.objects.filter(name_uz__iexact=name_uz, branch_id=branch_id).exists():
            messages.error(request, 'A category with this name already exists for this branch.')
        else:
            try:
                # Verify branch access
                branch = get_object_or_404(branches, id=branch_id)
                category = Category.objects.create(
                    name=name,
                    name_uz=name_uz or None,
                    name_ru=name_ru or None,
                    name_en=name_en or None,
                    description=description_uz or description_ru or description_en,
                    description_uz=description_uz or None,
                    description_ru=description_ru or None,
                    description_en=description_en or None,
                    branch=branch,
                    charging=charging,
                    is_active=is_active,
                )
                # Add selected languages
                if selected_languages:
                    category.languages.set(selected_languages)
                
                messages.success(request, f'Category "{name}" has been created successfully.')
                return redirect('categoryList')
            except Exception as e:
                messages.error(request, f'Error creating category: {str(e)}')
    
    context = {
        "title": "Add Category",
        "subTitle": "Add Category",
        "languages": languages,
        "branches": branches,
        "charge_types": Category.CHARGE_TYPE,
    }
    return render(request, "services/addCategory.html", context)


@login_required(login_url='admin_login')
@any_permission_required('can_edit_products', 'can_manage_products')
def editCategory(request, category_id):
    """Edit an existing category"""
    # Get category with RBAC check
    accessible_categories = get_user_categories(request.user)
    category = get_object_or_404(accessible_categories.select_related('branch', 'branch__center'), id=category_id)
    languages = Language.objects.all()
    branches = get_user_branches(request.user).select_related('center')
    
    if request.method == 'POST':
        # Get translated fields
        name_uz = request.POST.get('name_uz', '').strip()
        name_ru = request.POST.get('name_ru', '').strip()
        name_en = request.POST.get('name_en', '').strip()
        description_uz = request.POST.get('description_uz', '').strip()
        description_ru = request.POST.get('description_ru', '').strip()
        description_en = request.POST.get('description_en', '').strip()
        
        branch_id = request.POST.get('branch', '')
        charging = request.POST.get('charging', 'dynamic')
        is_active = request.POST.get('is_active') == 'on'
        selected_languages = request.POST.getlist('languages')
        
        # Use Uzbek name as primary (fallback to any available)
        name = name_uz or name_ru or name_en
        
        if not name:
            messages.error(request, 'Category name is required in at least one language.')
        elif not branch_id:
            messages.error(request, 'Branch is required.')
        elif Category.objects.filter(name_uz__iexact=name_uz, branch_id=branch_id).exclude(id=category_id).exists():
            messages.error(request, 'A category with this name already exists for this branch.')
        else:
            try:
                # Verify branch access
                branch = get_object_or_404(branches, id=branch_id)
                category.name = name
                category.name_uz = name_uz or None
                category.name_ru = name_ru or None
                category.name_en = name_en or None
                category.description = description_uz or description_ru or description_en
                category.description_uz = description_uz or None
                category.description_ru = description_ru or None
                category.description_en = description_en or None
                category.branch = branch
                category.charging = charging
                category.is_active = is_active
                category.save()
                
                # Update languages
                category.languages.set(selected_languages)
                
                messages.success(request, f'Category "{name}" has been updated successfully.')
                return redirect('categoryList')
            except Exception as e:
                messages.error(request, f'Error updating category: {str(e)}')
    
    context = {
        "title": "Edit Category",
        "subTitle": "Edit Category",
        "category": category,
        "languages": languages,
        "branches": branches,
        "charge_types": Category.CHARGE_TYPE,
    }
    return render(request, "services/editCategory.html", context)


@login_required(login_url='admin_login')
@any_permission_required('can_delete_products', 'can_manage_products')
def deleteCategory(request, category_id):
    """Delete a category"""
    # Get category with RBAC check
    accessible_categories = get_user_categories(request.user)
    category = get_object_or_404(accessible_categories, id=category_id)
    
    if request.method == 'POST':
        name = category.name
        category.delete()
        messages.success(request, f'Category "{name}" has been deleted successfully.')
    
    return redirect('categoryList')


# ============ Product Views ============

@login_required(login_url='admin_login')
@any_permission_required('can_view_products', 'can_manage_products')
def productList(request):
    """List all products with search and filter"""
    # Use RBAC-filtered products
    products = get_user_products(request.user).select_related(
        'category', 'category__branch', 'category__branch__center'
    ).order_by('-created_at')
    
    # Get accessible branches for filter dropdown
    branches = get_user_branches(request.user).select_related('center')
    
    # Center filter (superuser only)
    centers = None
    center_filter = request.GET.get('center', '')
    if request.user.is_superuser:
        centers = TranslationCenter.objects.filter(is_active=True)
        if center_filter:
            products = products.filter(category__branch__center_id=center_filter)
            branches = branches.filter(center_id=center_filter)
    
    # Branch filter
    branch_filter = request.GET.get('branch', '')
    if branch_filter:
        products = products.filter(category__branch_id=branch_filter)
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(category__name__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Category filter
    category_filter = request.GET.get('category', '')
    if category_filter:
        products = products.filter(category_id=category_filter)
    
    # Status filter
    status_filter = request.GET.get('status', '')
    if status_filter == 'active':
        products = products.filter(is_active=True)
    elif status_filter == 'inactive':
        products = products.filter(is_active=False)
    
    # Pagination
    per_page = request.GET.get('per_page', 10)
    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 10
    
    paginator = Paginator(products, per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Get RBAC-filtered categories for filter dropdown
    categories = get_user_categories(request.user).filter(is_active=True).order_by('name')
    
    # Check if user is owner
    is_owner = False
    if hasattr(request.user, 'staff_profile') and request.user.staff_profile.role:
        is_owner = request.user.staff_profile.role.name == 'owner'
    
    context = {
        "title": "Products",
        "subTitle": "Products",
        "products": page_obj,
        "categories": categories,
        "branches": branches,
        "branch_filter": branch_filter,
        "centers": centers,
        "center_filter": center_filter,
        "search_query": search_query,
        "category_filter": category_filter,
        "status_filter": status_filter,
        "per_page": per_page,
        "total_products": paginator.count,
        "is_owner": is_owner,
    }
    return render(request, "services/productList.html", context)


@login_required(login_url='admin_login')
@any_permission_required('can_view_products', 'can_manage_products')
def productDetail(request, product_id):
    """View product details"""
    # Get product with RBAC check
    accessible_products = get_user_products(request.user)
    product = get_object_or_404(
        accessible_products.select_related('category', 'category__branch', 'category__branch__center').prefetch_related('expenses'),
        id=product_id
    )
    
    context = {
        "title": f"Product: {product.name}",
        "subTitle": "Product Details",
        "product": product,
    }
    return render(request, "services/productDetail.html", context)


@login_required(login_url='admin_login')
@any_permission_required('can_create_products', 'can_manage_products')
def addProduct(request):
    """Add a new product"""
    # Get RBAC-filtered categories
    categories = get_user_categories(request.user).filter(is_active=True).select_related(
        'branch', 'branch__center'
    ).order_by('name')
    
    # Get RBAC-filtered expenses for multi-select
    expenses = get_user_expenses(request.user).filter(is_active=True).select_related(
        'branch'
    ).order_by('name')
    
    if request.method == 'POST':
        # Get translated fields
        name_uz = request.POST.get('name_uz', '').strip()
        name_ru = request.POST.get('name_ru', '').strip()
        name_en = request.POST.get('name_en', '').strip()
        description_uz = request.POST.get('description_uz', '').strip()
        description_ru = request.POST.get('description_ru', '').strip()
        description_en = request.POST.get('description_en', '').strip()
        
        category_id = request.POST.get('category', '')
        
        # Use Uzbek name as primary (fallback to any available)
        name = name_uz or name_ru or name_en
        description = description_uz or description_ru or description_en
        
        # Pricing
        ordinary_first_page_price = request.POST.get('ordinary_first_page_price', '0')
        ordinary_other_page_price = request.POST.get('ordinary_other_page_price', '0')
        agency_first_page_price = request.POST.get('agency_first_page_price', '0')
        agency_other_page_price = request.POST.get('agency_other_page_price', '0')
        # New decimal-based copy price fields
        user_copy_price_decimal = request.POST.get('user_copy_price_decimal')
        agency_copy_price_decimal = request.POST.get('agency_copy_price_decimal')
        
        # Other fields
        min_pages = request.POST.get('min_pages', '1')
        estimated_days = request.POST.get('estimated_days', '1')
        is_active = request.POST.get('is_active') == 'on'
        
        # Get selected expenses
        selected_expenses = request.POST.getlist('expenses')
        
        if not name:
            messages.error(request, 'Product name is required in at least one language.')
        elif not category_id:
            messages.error(request, 'Please select a category.')
        else:
            try:
                product = Product.objects.create(
                    name=name,
                    name_uz=name_uz or None,
                    name_ru=name_ru or None,
                    name_en=name_en or None,
                    category_id=category_id,
                    description=description,
                    description_uz=description_uz or None,
                    description_ru=description_ru or None,
                    description_en=description_en or None,
                    ordinary_first_page_price=ordinary_first_page_price or 0,
                    ordinary_other_page_price=ordinary_other_page_price or 0,
                    agency_first_page_price=agency_first_page_price or 0,
                    agency_other_page_price=agency_other_page_price or 0,
                    user_copy_price_decimal=user_copy_price_decimal or None,
                    agency_copy_price_decimal=agency_copy_price_decimal or None,
                    min_pages=min_pages or 1,
                    estimated_days=estimated_days or 1,
                    is_active=is_active,
                )
                
                # Add selected expenses to product
                if selected_expenses:
                    product.expenses.set(selected_expenses)
                
                messages.success(request, f'Product "{name}" has been created successfully.')
                return redirect('productList')
            except Exception as e:
                messages.error(request, f'Error creating product: {str(e)}')
    
    # Get branches for inline expense creation modal
    branches = get_user_branches(request.user).select_related('center').order_by('name')
    
    # Center selection for superadmin
    centers = None
    if request.user.is_superuser:
        centers = TranslationCenter.objects.filter(is_active=True).order_by('name')
    
    context = {
        "title": "Add Product",
        "subTitle": "Add Product",
        "categories": categories,
        "expenses": expenses,
        "expense_types": Expense.EXPENSE_TYPE_CHOICES,
        "branches": branches,
        "centers": centers,
        "is_superuser": request.user.is_superuser,
    }
    return render(request, "services/addProduct.html", context)


@login_required(login_url='admin_login')
@any_permission_required('can_edit_products', 'can_manage_products')
def editProduct(request, product_id):
    """Edit an existing product"""
    # Get product with RBAC check
    accessible_products = get_user_products(request.user)
    product = get_object_or_404(
        accessible_products.select_related('category', 'category__branch', 'category__branch__center'),
        id=product_id
    )
    # Get RBAC-filtered categories
    categories = get_user_categories(request.user).filter(is_active=True).select_related(
        'branch', 'branch__center'
    ).order_by('name')
    
    # Get RBAC-filtered expenses for multi-select
    expenses = get_user_expenses(request.user).filter(is_active=True).select_related(
        'branch'
    ).order_by('name')
    
    # Get currently selected expense IDs
    selected_expense_ids = list(product.expenses.values_list('id', flat=True))
    
    if request.method == 'POST':
        # Get translated fields
        name_uz = request.POST.get('name_uz', '').strip()
        name_ru = request.POST.get('name_ru', '').strip()
        name_en = request.POST.get('name_en', '').strip()
        description_uz = request.POST.get('description_uz', '').strip()
        description_ru = request.POST.get('description_ru', '').strip()
        description_en = request.POST.get('description_en', '').strip()
        
        category_id = request.POST.get('category', '')
        
        # Use Uzbek name as primary (fallback to any available)
        name = name_uz or name_ru or name_en
        description = description_uz or description_ru or description_en
        
        # Pricing
        ordinary_first_page_price = request.POST.get('ordinary_first_page_price', '0')
        ordinary_other_page_price = request.POST.get('ordinary_other_page_price', '0')
        agency_first_page_price = request.POST.get('agency_first_page_price', '0')
        agency_other_page_price = request.POST.get('agency_other_page_price', '0')
        # New decimal-based copy price fields
        user_copy_price_decimal = request.POST.get('user_copy_price_decimal')
        agency_copy_price_decimal = request.POST.get('agency_copy_price_decimal')
        
        # Other fields
        min_pages = request.POST.get('min_pages', '1')
        estimated_days = request.POST.get('estimated_days', '1')
        is_active = request.POST.get('is_active') == 'on'
        
        # Get selected expenses
        selected_expenses = request.POST.getlist('expenses')
        
        if not name:
            messages.error(request, 'Product name is required in at least one language.')
        elif not category_id:
            messages.error(request, 'Please select a category.')
        else:
            try:
                product.name = name
                product.name_uz = name_uz or None
                product.name_ru = name_ru or None
                product.name_en = name_en or None
                product.category_id = category_id
                product.description = description
                product.description_uz = description_uz or None
                product.description_ru = description_ru or None
                product.description_en = description_en or None
                
                # Update prices only if provided (don't overwrite with 0 if empty)
                if ordinary_first_page_price:
                    product.ordinary_first_page_price = ordinary_first_page_price
                if ordinary_other_page_price:
                    product.ordinary_other_page_price = ordinary_other_page_price
                if agency_first_page_price:
                    product.agency_first_page_price = agency_first_page_price
                if agency_other_page_price:
                    product.agency_other_page_price = agency_other_page_price
                # Use new decimal fields
                if user_copy_price_decimal is not None and user_copy_price_decimal != '':
                    product.user_copy_price_decimal = user_copy_price_decimal
                if agency_copy_price_decimal is not None and agency_copy_price_decimal != '':
                    product.agency_copy_price_decimal = agency_copy_price_decimal
                if min_pages:
                    product.min_pages = min_pages
                if estimated_days:
                    product.estimated_days = estimated_days
                    
                product.is_active = is_active
                product.save()
                
                # Update expenses
                product.expenses.set(selected_expenses)
                
                messages.success(request, f'Product "{name}" has been updated successfully.')
                return redirect('productList')
            except Exception as e:
                messages.error(request, f'Error updating product: {str(e)}')
    
    # Get branches for inline expense creation modal
    branches = get_user_branches(request.user).select_related('center').order_by('name')
    
    # Center selection for superadmin
    centers = None
    if request.user.is_superuser:
        centers = TranslationCenter.objects.filter(is_active=True).order_by('name')
    
    context = {
        "title": "Edit Product",
        "subTitle": "Edit Product",
        "product": product,
        "categories": categories,
        "expenses": expenses,
        "selected_expense_ids": selected_expense_ids,
        "expense_types": Expense.EXPENSE_TYPE_CHOICES,
        "branches": branches,
        "centers": centers,
        "is_superuser": request.user.is_superuser,
    }
    return render(request, "services/editProduct.html", context)


@login_required(login_url='admin_login')
@any_permission_required('can_delete_products', 'can_manage_products')
def deleteProduct(request, product_id):
    """Delete a product"""
    # Get product with RBAC check
    accessible_products = get_user_products(request.user)
    product = get_object_or_404(accessible_products, id=product_id)
    
    if request.method == 'POST':
        name = product.name
        product.delete()
        messages.success(request, f'Product "{name}" has been deleted successfully.')
    
    return redirect('productList')


# ============ Expense Views ============

@login_required(login_url='admin_login')
@any_permission_required('can_view_expenses', 'can_manage_expenses', 'can_view_financial_reports', 'can_manage_financial')
def expenseList(request):
    """List all expenses with search and filter"""
    # Use RBAC-filtered expenses
    expenses = get_user_expenses(request.user).select_related(
        'branch', 'branch__center'
    ).prefetch_related('products').annotate(
        product_count=Count('products')
    ).order_by('-created_at')
    
    # Get accessible branches for filter dropdown
    branches = get_user_branches(request.user).select_related('center')
    
    # Center filter (superuser only)
    centers = None
    center_filter = request.GET.get('center', '')
    if request.user.is_superuser:
        centers = TranslationCenter.objects.filter(is_active=True)
        if center_filter:
            expenses = expenses.filter(branch__center_id=center_filter)
            branches = branches.filter(center_id=center_filter)
    
    # Branch filter
    branch_filter = request.GET.get('branch', '')
    if branch_filter:
        expenses = expenses.filter(branch_id=branch_filter)
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        expenses = expenses.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Status filter
    status_filter = request.GET.get('status', '')
    if status_filter == 'active':
        expenses = expenses.filter(is_active=True)
    elif status_filter == 'inactive':
        expenses = expenses.filter(is_active=False)
    
    # Expense type filter
    expense_type_filter = request.GET.get('expense_type', '')
    if expense_type_filter:
        expenses = expenses.filter(expense_type=expense_type_filter)
    
    # Calculate aggregates for current filtered set
    aggregates = expenses.aggregate(
        total_expenses=Sum('price_for_original'),
        b2b_total=Sum('price_for_original', filter=Q(expense_type__in=['b2b', 'both'])),
        b2c_total=Sum('price_for_original', filter=Q(expense_type__in=['b2c', 'both'])),
    )
    
    # Pagination
    per_page = request.GET.get('per_page', 10)
    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 10
    
    paginator = Paginator(expenses, per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        "title": "Expenses",
        "subTitle": "Expenses",
        "expenses": page_obj,
        "branches": branches,
        "branch_filter": branch_filter,
        "centers": centers,
        "center_filter": center_filter,
        "search_query": search_query,
        "status_filter": status_filter,
        "expense_type_filter": expense_type_filter,
        "expense_types": Expense.EXPENSE_TYPE_CHOICES,
        "per_page": per_page,
        "total_expenses": paginator.count,
        "total_amount": aggregates['total_expenses'] or 0,
        "b2b_total": aggregates['b2b_total'] or 0,
        "b2c_total": aggregates['b2c_total'] or 0,
    }
    return render(request, "services/expenseList.html", context)


@login_required(login_url='admin_login')
@any_permission_required('can_view_expenses', 'can_manage_expenses', 'can_view_financial_reports', 'can_manage_financial')
def expenseDetail(request, expense_id):
    """View expense details with linked products"""
    # Get expense with RBAC check
    accessible_expenses = get_user_expenses(request.user)
    expense = get_object_or_404(
        accessible_expenses.select_related('branch', 'branch__center').prefetch_related('products'),
        id=expense_id
    )
    
    context = {
        "title": f"Expense: {expense.name}",
        "subTitle": "Expense Details",
        "expense": expense,
        "linked_products": expense.products.all(),
    }
    return render(request, "services/expenseDetail.html", context)


@login_required(login_url='admin_login')
@any_permission_required('can_create_expenses', 'can_manage_expenses', 'can_manage_financial')
def addExpense(request):
    """Add a new expense"""
    # Get RBAC-filtered branches for validation
    accessible_branches = get_user_branches(request.user)
    
    # Branches for display (with center info for UI)
    branches = accessible_branches.select_related('center').order_by('center__name', 'name')
    
    # Center selection for superadmin
    centers = None
    if request.user.is_superuser:
        centers = TranslationCenter.objects.filter(is_active=True).order_by('name')
        # For superadmin, get all active branches for dynamic filtering in UI
        branches = Branch.objects.filter(is_active=True).select_related('center').order_by('center__name', 'name')
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        price_for_original = request.POST.get('price_for_original', '0')
        price_for_copy = request.POST.get('price_for_copy', '0')
        expense_type = request.POST.get('expense_type', 'both')
        branch_id = request.POST.get('branch', '')
        description = request.POST.get('description', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        
        # Validate prices don't exceed max_digits=12
        try:
            price_original_decimal = Decimal(price_for_original or '0')
            if price_original_decimal >= Decimal('10000000000'):  # 10^10, max safe value for 12 digits with 2 decimals
                messages.error(request, 'Price for original is too large. Maximum is 9,999,999,999.99')
                price_original_decimal = None
        except (InvalidOperation, ValueError):
            messages.error(request, 'Invalid price for original value.')
            price_original_decimal = None
        
        try:
            price_copy_decimal = Decimal(price_for_copy or '0')
            if price_copy_decimal >= Decimal('10000000000'):
                messages.error(request, 'Price for copy is too large. Maximum is 9,999,999,999.99')
                price_copy_decimal = None
        except (InvalidOperation, ValueError):
            messages.error(request, 'Invalid price for copy value.')
            price_copy_decimal = None
        
        if not name:
            messages.error(request, 'Expense name is required.')
        elif not branch_id:
            messages.error(request, 'Please select a branch.')
        elif price_original_decimal is None or price_copy_decimal is None:
            pass  # Error already shown above
        else:
            try:
                # Validate branch access with RBAC-filtered queryset
                branch = get_object_or_404(accessible_branches, id=branch_id)
                expense = Expense.objects.create(
                    name=name,
                    price_for_original=price_original_decimal,
                    price_for_copy=price_copy_decimal,
                    expense_type=expense_type,
                    branch=branch,
                    description=description or None,
                    is_active=is_active,
                )
                messages.success(request, f'Expense "{name}" has been created successfully.')
                return redirect('expenseList')
            except Exception as e:
                messages.error(request, f'Error creating expense: {str(e)}')
    
    context = {
        "title": "Add Expense",
        "subTitle": "Add Expense",
        "branches": branches,
        "centers": centers,
        "expense_types": Expense.EXPENSE_TYPE_CHOICES,
    }
    return render(request, "services/addExpense.html", context)


@login_required(login_url='admin_login')
@any_permission_required('can_edit_expenses', 'can_manage_expenses', 'can_manage_financial')
def editExpense(request, expense_id):
    """Edit an existing expense"""
    # Get expense with RBAC check
    accessible_expenses = get_user_expenses(request.user)
    expense = get_object_or_404(
        accessible_expenses.select_related('branch', 'branch__center'),
        id=expense_id
    )
    # Get RBAC-filtered branches
    branches = get_user_branches(request.user).select_related('center').order_by('name')
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        price_for_original = request.POST.get('price_for_original', '0')
        price_for_copy = request.POST.get('price_for_copy', '0')
        expense_type = request.POST.get('expense_type', 'both')
        branch_id = request.POST.get('branch', '')
        description = request.POST.get('description', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        
        # Validate prices don't exceed max_digits=12
        try:
            price_original_decimal = Decimal(price_for_original or '0')
            if price_original_decimal >= Decimal('10000000000'):
                messages.error(request, 'Price for original is too large. Maximum is 9,999,999,999.99')
                price_original_decimal = None
        except (InvalidOperation, ValueError):
            messages.error(request, 'Invalid price for original value.')
            price_original_decimal = None
        
        try:
            price_copy_decimal = Decimal(price_for_copy or '0')
            if price_copy_decimal >= Decimal('10000000000'):
                messages.error(request, 'Price for copy is too large. Maximum is 9,999,999,999.99')
                price_copy_decimal = None
        except (InvalidOperation, ValueError):
            messages.error(request, 'Invalid price for copy value.')
            price_copy_decimal = None
        
        if not name:
            messages.error(request, 'Expense name is required.')
        elif not branch_id:
            messages.error(request, 'Please select a branch.')
        elif price_original_decimal is None or price_copy_decimal is None:
            pass  # Error already shown above
        else:
            try:
                # Validate branch access
                branch = get_object_or_404(branches, id=branch_id)
                expense.name = name
                expense.price_for_original = price_original_decimal
                expense.price_for_copy = price_copy_decimal
                expense.expense_type = expense_type
                expense.branch = branch
                expense.description = description or None
                expense.is_active = is_active
                expense.save()
                
                messages.success(request, f'Expense "{name}" has been updated successfully.')
                return redirect('expenseList')
            except Exception as e:
                messages.error(request, f'Error updating expense: {str(e)}')
    
    context = {
        "title": "Edit Expense",
        "subTitle": "Edit Expense",
        "expense": expense,
        "branches": branches,
        "expense_types": Expense.EXPENSE_TYPE_CHOICES,
    }
    return render(request, "services/editExpense.html", context)


@login_required(login_url='admin_login')
@any_permission_required('can_delete_expenses', 'can_manage_expenses', 'can_manage_financial')
def deleteExpense(request, expense_id):
    """Delete an expense"""
    # Get expense with RBAC check
    accessible_expenses = get_user_expenses(request.user)
    expense = get_object_or_404(accessible_expenses, id=expense_id)
    
    if request.method == 'POST':
        name = expense.name
        expense.delete()
        messages.success(request, f'Expense "{name}" has been deleted successfully.')
    
    return redirect('expenseList')


# ============ Expense Analytics API ============

@login_required(login_url='admin_login')
@any_permission_required('can_view_expenses', 'can_manage_expenses', 'can_view_financial_reports', 'can_manage_financial')
def expenseAnalytics(request):
    """Get expense analytics by B2B/B2C for center/branch level"""
    branch_id = request.GET.get('branch')
    center_id = request.GET.get('center')
    
    branch = None
    center = None
    
    # Validate access
    if branch_id:
        branches = get_user_branches(request.user)
        branch = get_object_or_404(branches, id=branch_id)
    elif center_id and request.user.is_superuser:
        center = get_object_or_404(TranslationCenter, id=center_id)
    
    # Get aggregated expenses
    analytics = Expense.aggregate_expenses_by_type(
        branch=branch,
        center=center,
        active_only=True
    )
    
    # Get expense breakdown by type
    base_expenses = get_user_expenses(request.user).filter(is_active=True)
    if branch:
        base_expenses = base_expenses.filter(branch=branch)
    elif center:
        base_expenses = base_expenses.filter(branch__center=center)
    
    expense_breakdown = list(base_expenses.values(
        'expense_type'
    ).annotate(
        total=Sum('price'),
        count=Count('id')
    ).order_by('expense_type'))
    
    context = {
        "title": "Expense Analytics",
        "subTitle": "Expense Analytics",
        "analytics": analytics,
        "expense_breakdown": expense_breakdown,
        "branch": branch,
        "center": center,
    }
    return render(request, "services/expenseAnalytics.html", context)


# ============ Inline Expense Creation (AJAX) ============

@login_required(login_url='admin_login')
@permission_required('can_manage_financial')
@require_POST
def createExpenseInline(request):
    """Create an expense inline via AJAX from the product add/edit page"""
    import json
    
    try:
        # Check if JSON or form data
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST
        
        name = data.get('name', '').strip()
        price_for_original = data.get('price_for_original', '0')
        price_for_copy = data.get('price_for_copy', '0')
        expense_type = data.get('expense_type', 'both')
        branch_id = data.get('branch', '')
        description = data.get('description', '').strip()
        
        if not name:
            return JsonResponse({'success': False, 'error': 'Expense name is required.'}, status=400)
        
        if not branch_id:
            return JsonResponse({'success': False, 'error': 'Branch is required.'}, status=400)
        
        # Verify branch access
        branches = get_user_branches(request.user)
        try:
            branch = branches.get(id=branch_id)
        except:
            return JsonResponse({'success': False, 'error': 'Invalid branch.'}, status=400)
        
        # Create the expense
        expense = Expense.objects.create(
            name=name,
            price_for_original=Decimal(str(price_for_original)) if price_for_original else Decimal('0'),
            price_for_copy=Decimal(str(price_for_copy)) if price_for_copy else Decimal('0'),
            expense_type=expense_type,
            branch=branch,
            description=description,
            is_active=True,
        )
        
        return JsonResponse({
            'success': True,
            'expense': {
                'id': expense.id,
                'name': expense.name,
                'price_for_original': str(expense.price_for_original),
                'price_for_copy': str(expense.price_for_copy),
                'expense_type': expense.expense_type,
                'expense_type_display': expense.get_expense_type_display(),
                'branch_name': branch.name,
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data.'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ============ Inline Language Creation (AJAX) ============

@login_required(login_url='admin_login')
@require_POST
def createLanguageInline(request):
    """Create a language inline via AJAX - Superuser only"""
    import json
    
    # Only superusers can create languages
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Only superusers can create languages.'}, status=403)
    
    try:
        # Check if JSON or form data
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST
        
        name = data.get('name', '').strip()
        short_name = data.get('short_name', '').strip()
        
        if not name:
            return JsonResponse({'success': False, 'error': 'Language name is required.'}, status=400)
        
        if not short_name:
            return JsonResponse({'success': False, 'error': 'Short name is required.'}, status=400)
        
        # Check if language already exists
        if Language.objects.filter(name__iexact=name).exists():
            return JsonResponse({'success': False, 'error': f'Language "{name}" already exists.'}, status=400)
        
        if Language.objects.filter(short_name__iexact=short_name).exists():
            return JsonResponse({'success': False, 'error': f'Short name "{short_name}" already exists.'}, status=400)
        
        # Create the language
        language = Language.objects.create(
            name=name,
            short_name=short_name.upper(),
        )
        
        return JsonResponse({
            'success': True,
            'language': {
                'id': language.id,
                'name': language.name,
                'short_name': language.short_name,
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data.'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
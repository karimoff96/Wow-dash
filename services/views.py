from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from decimal import Decimal, InvalidOperation
from .models import Category, Product, Language, Expense
from organizations.rbac import get_user_categories, get_user_products, get_user_branches, get_user_expenses
from organizations.models import TranslationCenter


# ============ Category Views ============

@login_required(login_url='admin_login')
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
    }
    return render(request, "services/categoryList.html", context)


@login_required(login_url='admin_login')
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
    }
    return render(request, "services/productList.html", context)


@login_required(login_url='admin_login')
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
        user_copy_price_percentage = request.POST.get('user_copy_price_percentage', '100')
        agency_copy_price_percentage = request.POST.get('agency_copy_price_percentage', '100')
        
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
                    user_copy_price_percentage=user_copy_price_percentage or 100,
                    agency_copy_price_percentage=agency_copy_price_percentage or 100,
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
        user_copy_price_percentage = request.POST.get('user_copy_price_percentage', '100')
        agency_copy_price_percentage = request.POST.get('agency_copy_price_percentage', '100')
        
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
                product.ordinary_first_page_price = ordinary_first_page_price or 0
                product.ordinary_other_page_price = ordinary_other_page_price or 0
                product.agency_first_page_price = agency_first_page_price or 0
                product.agency_other_page_price = agency_other_page_price or 0
                product.user_copy_price_percentage = user_copy_price_percentage or 100
                product.agency_copy_price_percentage = agency_copy_price_percentage or 100
                product.min_pages = min_pages or 1
                product.estimated_days = estimated_days or 1
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
        total_expenses=Sum('price'),
        b2b_total=Sum('price', filter=Q(expense_type__in=['b2b', 'both'])),
        b2c_total=Sum('price', filter=Q(expense_type__in=['b2c', 'both'])),
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
def addExpense(request):
    """Add a new expense"""
    # Get RBAC-filtered branches
    branches = get_user_branches(request.user).select_related('center').order_by('name')
    
    # Center selection for superadmin
    centers = None
    if request.user.is_superuser:
        centers = TranslationCenter.objects.filter(is_active=True).order_by('name')
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        price = request.POST.get('price', '0')
        expense_type = request.POST.get('expense_type', 'both')
        branch_id = request.POST.get('branch', '')
        description = request.POST.get('description', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        
        # Validate price doesn't exceed max_digits=12
        try:
            price_decimal = Decimal(price or '0')
            if price_decimal >= Decimal('10000000000'):  # 10^10, max safe value for 12 digits with 2 decimals
                messages.error(request, 'Price value is too large. Maximum is 9,999,999,999.99')
                price_decimal = None
        except (InvalidOperation, ValueError):
            messages.error(request, 'Invalid price value.')
            price_decimal = None
        
        if not name:
            messages.error(request, 'Expense name is required.')
        elif not branch_id:
            messages.error(request, 'Please select a branch.')
        elif price_decimal is None:
            pass  # Error already shown above
        else:
            try:
                # Validate branch access
                branch = get_object_or_404(branches, id=branch_id)
                expense = Expense.objects.create(
                    name=name,
                    price=price_decimal,
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
        price = request.POST.get('price', '0')
        expense_type = request.POST.get('expense_type', 'both')
        branch_id = request.POST.get('branch', '')
        description = request.POST.get('description', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        
        # Validate price doesn't exceed max_digits=12
        try:
            price_decimal = Decimal(price or '0')
            if price_decimal >= Decimal('10000000000'):  # 10^10, max safe value for 12 digits with 2 decimals
                messages.error(request, 'Price value is too large. Maximum is 9,999,999,999.99')
                price_decimal = None
        except (InvalidOperation, ValueError):
            messages.error(request, 'Invalid price value.')
            price_decimal = None
        
        if not name:
            messages.error(request, 'Expense name is required.')
        elif not branch_id:
            messages.error(request, 'Please select a branch.')
        elif price_decimal is None:
            pass  # Error already shown above
        else:
            try:
                # Validate branch access
                branch = get_object_or_404(branches, id=branch_id)
                expense.name = name
                expense.price = price_decimal
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
        price = data.get('price', '0')
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
            price=Decimal(str(price)) if price else Decimal('0'),
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
                'price': str(expense.price),
                'expense_type': expense.expense_type,
                'expense_type_display': expense.get_expense_type_display(),
                'branch_name': branch.name,
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data.'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
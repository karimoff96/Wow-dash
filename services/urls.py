from django.urls import path
from . import views

urlpatterns = [
    # Categories
    path("categories/", views.categoryList, name="categoryList"),
    path("categories/add/", views.addCategory, name="addCategory"),
    path("categories/<int:category_id>/", views.categoryDetail, name="categoryDetail"),
    path("categories/<int:category_id>/edit/", views.editCategory, name="editCategory"),
    path("categories/<int:category_id>/delete/", views.deleteCategory, name="deleteCategory"),
    
    # Products
    path("products/", views.productList, name="productList"),
    path("products/add/", views.addProduct, name="addProduct"),
    path("products/<int:product_id>/", views.productDetail, name="productDetail"),
    path("products/<int:product_id>/edit/", views.editProduct, name="editProduct"),
    path("products/<int:product_id>/delete/", views.deleteProduct, name="deleteProduct"),
    
    # Expenses
    path("expenses/", views.expenseList, name="expenseList"),
    path("expenses/add/", views.addExpense, name="addExpense"),
    path("expenses/<int:expense_id>/", views.expenseDetail, name="expenseDetail"),
    path("expenses/<int:expense_id>/edit/", views.editExpense, name="editExpense"),
    path("expenses/<int:expense_id>/delete/", views.deleteExpense, name="deleteExpense"),
    path("expenses/analytics/", views.expenseAnalytics, name="expenseAnalytics"),
    path("expenses/create-inline/", views.createExpenseInline, name="createExpenseInline"),
]

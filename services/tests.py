from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from decimal import Decimal
from .models import Expense, Product, Category, Language
from organizations.models import TranslationCenter, Branch, Role, AdminUser


class ExpenseModelTestCase(TestCase):
    """Test cases for the Expense model"""
    
    def setUp(self):
        """Set up test data"""
        # Create user
        self.owner = User.objects.create_user(
            username='test_owner',
            password='testpass123',
            email='owner@test.com'
        )
        
        # Create translation center
        self.center = TranslationCenter.objects.create(
            name='Test Center',
            owner=self.owner,
            is_active=True
        )
        
        # Create branch
        self.branch = Branch.objects.create(
            center=self.center,
            name='Test Branch',
            is_active=True,
            is_main=True
        )
        
        # Create another branch for multi-tenant tests
        self.branch2 = Branch.objects.create(
            center=self.center,
            name='Test Branch 2',
            is_active=True
        )
        
        # Create expenses
        self.expense_b2b = Expense.objects.create(
            name='B2B Expense',
            price=Decimal('100.00'),
            expense_type='b2b',
            branch=self.branch,
            description='B2B only expense',
            is_active=True
        )
        
        self.expense_b2c = Expense.objects.create(
            name='B2C Expense',
            price=Decimal('50.00'),
            expense_type='b2c',
            branch=self.branch,
            is_active=True
        )
        
        self.expense_both = Expense.objects.create(
            name='Both Expense',
            price=Decimal('75.00'),
            expense_type='both',
            branch=self.branch,
            is_active=True
        )
        
        self.expense_inactive = Expense.objects.create(
            name='Inactive Expense',
            price=Decimal('200.00'),
            expense_type='b2b',
            branch=self.branch,
            is_active=False
        )
    
    def test_expense_creation(self):
        """Test expense is created correctly"""
        self.assertEqual(self.expense_b2b.name, 'B2B Expense')
        self.assertEqual(self.expense_b2b.price, Decimal('100.00'))
        self.assertEqual(self.expense_b2b.expense_type, 'b2b')
        self.assertEqual(self.expense_b2b.branch, self.branch)
        self.assertTrue(self.expense_b2b.is_active)
    
    def test_expense_str(self):
        """Test expense string representation"""
        self.assertEqual(str(self.expense_b2b), 'B2B Expense (100.00)')
    
    def test_expense_center_property(self):
        """Test expense center property"""
        self.assertEqual(self.expense_b2b.center, self.center)
    
    def test_get_expenses_by_type_b2b(self):
        """Test filtering expenses by B2B type"""
        expenses = Expense.get_expenses_by_type(
            branch=self.branch,
            expense_type='b2b'
        )
        # Should include b2b and both types
        self.assertEqual(expenses.count(), 2)
        names = list(expenses.values_list('name', flat=True))
        self.assertIn('B2B Expense', names)
        self.assertIn('Both Expense', names)
    
    def test_get_expenses_by_type_b2c(self):
        """Test filtering expenses by B2C type"""
        expenses = Expense.get_expenses_by_type(
            branch=self.branch,
            expense_type='b2c'
        )
        # Should include b2c and both types
        self.assertEqual(expenses.count(), 2)
        names = list(expenses.values_list('name', flat=True))
        self.assertIn('B2C Expense', names)
        self.assertIn('Both Expense', names)
    
    def test_get_expenses_active_only(self):
        """Test filtering active expenses only"""
        expenses = Expense.get_expenses_by_type(
            branch=self.branch,
            active_only=True
        )
        self.assertEqual(expenses.count(), 3)
        
        expenses_all = Expense.get_expenses_by_type(
            branch=self.branch,
            active_only=False
        )
        self.assertEqual(expenses_all.count(), 4)
    
    def test_aggregate_expenses_by_type(self):
        """Test expense aggregation by B2B/B2C"""
        analytics = Expense.aggregate_expenses_by_type(branch=self.branch)
        
        # B2B: 100 (b2b) + 75 (both) = 175
        self.assertEqual(analytics['b2b_total'], Decimal('175.00'))
        
        # B2C: 50 (b2c) + 75 (both) = 125
        self.assertEqual(analytics['b2c_total'], Decimal('125.00'))
        
        # Total: 100 + 50 + 75 = 225 (inactive not included)
        self.assertEqual(analytics['total'], Decimal('225.00'))
    
    def test_aggregate_expenses_by_center(self):
        """Test expense aggregation at center level"""
        # Create expense in branch2
        Expense.objects.create(
            name='Branch2 Expense',
            price=Decimal('30.00'),
            expense_type='b2b',
            branch=self.branch2,
            is_active=True
        )
        
        analytics = Expense.aggregate_expenses_by_type(center=self.center)
        
        # Total should include expenses from both branches
        self.assertEqual(analytics['total'], Decimal('255.00'))  # 225 + 30
    
    def test_unique_together_constraint(self):
        """Test unique_together constraint on branch and name"""
        with self.assertRaises(Exception):
            Expense.objects.create(
                name='B2B Expense',  # Same name as existing
                price=Decimal('50.00'),
                expense_type='b2c',
                branch=self.branch,  # Same branch
                is_active=True
            )
    
    def test_expense_in_different_branch(self):
        """Test same expense name can exist in different branches"""
        expense2 = Expense.objects.create(
            name='B2B Expense',  # Same name
            price=Decimal('150.00'),
            expense_type='b2b',
            branch=self.branch2,  # Different branch
            is_active=True
        )
        self.assertEqual(expense2.name, 'B2B Expense')
        self.assertEqual(expense2.branch, self.branch2)


class ProductExpenseTestCase(TestCase):
    """Test cases for Product-Expense relationship"""
    
    def setUp(self):
        """Set up test data"""
        self.owner = User.objects.create_user(
            username='test_owner',
            password='testpass123'
        )
        
        self.center = TranslationCenter.objects.create(
            name='Test Center',
            owner=self.owner,
            is_active=True
        )
        
        self.branch = Branch.objects.create(
            center=self.center,
            name='Test Branch',
            is_active=True,
            is_main=True
        )
        
        # Create category
        self.category = Category.objects.create(
            branch=self.branch,
            name='Translation',
            charging='dynamic',
            is_active=True
        )
        
        # Create product
        self.product = Product.objects.create(
            name='Test Document',
            category=self.category,
            ordinary_first_page_price=Decimal('50000.00'),
            ordinary_other_page_price=Decimal('30000.00'),
            agency_first_page_price=Decimal('40000.00'),
            agency_other_page_price=Decimal('25000.00'),
            is_active=True
        )
        
        # Create expenses
        self.expense1 = Expense.objects.create(
            name='Paper Cost',
            price=Decimal('5000.00'),
            expense_type='both',
            branch=self.branch,
            is_active=True
        )
        
        self.expense2 = Expense.objects.create(
            name='Agency Commission',
            price=Decimal('3000.00'),
            expense_type='b2b',
            branch=self.branch,
            is_active=True
        )
        
        self.expense3 = Expense.objects.create(
            name='Delivery Cost',
            price=Decimal('2000.00'),
            expense_type='b2c',
            branch=self.branch,
            is_active=True
        )
        
        # Link expenses to product
        self.product.expenses.add(self.expense1, self.expense2, self.expense3)
    
    def test_product_expenses_relationship(self):
        """Test M2M relationship between Product and Expense"""
        self.assertEqual(self.product.expenses.count(), 3)
    
    def test_expense_products_reverse_relationship(self):
        """Test reverse M2M relationship from Expense to Product"""
        self.assertEqual(self.expense1.products.count(), 1)
        self.assertEqual(self.expense1.products.first(), self.product)
    
    def test_get_expenses_total_all(self):
        """Test getting total expenses for product (all types)"""
        total = self.product.get_expenses_total()
        # 5000 + 3000 + 2000 = 10000
        self.assertEqual(total, Decimal('10000.00'))
    
    def test_get_expenses_total_b2b(self):
        """Test getting B2B expenses for product"""
        total = self.product.get_expenses_total(expense_type='b2b')
        # 5000 (both) + 3000 (b2b) = 8000
        self.assertEqual(total, Decimal('8000.00'))
    
    def test_get_expenses_total_b2c(self):
        """Test getting B2C expenses for product"""
        total = self.product.get_expenses_total(expense_type='b2c')
        # 5000 (both) + 2000 (b2c) = 7000
        self.assertEqual(total, Decimal('7000.00'))
    
    def test_get_profit_margin_b2c(self):
        """Test profit margin calculation for B2C"""
        # Price for 1 page B2C: 50000
        # B2C expenses: 7000
        # Profit margin: 50000 - 7000 = 43000
        margin = self.product.get_profit_margin(is_agency=False, pages=1)
        self.assertEqual(margin, Decimal('43000.00'))
    
    def test_get_profit_margin_b2b(self):
        """Test profit margin calculation for B2B"""
        # Price for 1 page B2B (agency): 40000
        # B2B expenses: 8000
        # Profit margin: 40000 - 8000 = 32000
        margin = self.product.get_profit_margin(is_agency=True, pages=1)
        self.assertEqual(margin, Decimal('32000.00'))
    
    def test_get_profit_margin_multiple_pages(self):
        """Test profit margin calculation with multiple pages"""
        # Price for 3 pages B2C: 50000 + 30000 * 2 = 110000
        # B2C expenses: 7000
        # Profit margin: 110000 - 7000 = 103000
        margin = self.product.get_profit_margin(is_agency=False, pages=3)
        self.assertEqual(margin, Decimal('103000.00'))


class ExpenseViewsTestCase(TestCase):
    """Test cases for Expense views"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        
        # Create superuser
        self.superuser = User.objects.create_superuser(
            username='admin',
            password='adminpass123',
            email='admin@test.com'
        )
        
        # Create regular owner
        self.owner = User.objects.create_user(
            username='owner',
            password='ownerpass123'
        )
        
        # Create translation center
        self.center = TranslationCenter.objects.create(
            name='Test Center',
            owner=self.owner,
            is_active=True
        )
        
        # Create branch
        self.branch = Branch.objects.create(
            center=self.center,
            name='Test Branch',
            is_active=True,
            is_main=True
        )
        
        # Create role
        self.owner_role = Role.objects.create(
            name='Test Owner Role',
            can_view_all_orders=True,
            can_create_orders=True,
            can_edit_orders=True,
            can_delete_orders=True,
            is_active=True
        )
        
        # Create admin profile
        self.admin_profile = AdminUser.objects.create(
            user=self.owner,
            branch=self.branch,
            role=self.owner_role,
            is_active=True
        )
        
        # Create expense
        self.expense = Expense.objects.create(
            name='Test Expense',
            price=Decimal('100.00'),
            expense_type='both',
            branch=self.branch,
            is_active=True
        )
    
    def test_expense_list_requires_login(self):
        """Test expense list requires authentication"""
        response = self.client.get(reverse('expenseList'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_expense_list_superuser(self):
        """Test superuser can access expense list"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('expenseList'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Expense')
    
    def test_expense_list_owner(self):
        """Test owner can access expense list"""
        self.client.login(username='owner', password='ownerpass123')
        response = self.client.get(reverse('expenseList'))
        self.assertEqual(response.status_code, 200)
    
    def test_add_expense_get(self):
        """Test add expense form displays correctly"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('addExpense'))
        self.assertEqual(response.status_code, 200)
    
    def test_add_expense_post(self):
        """Test creating new expense"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.post(reverse('addExpense'), {
            'name': 'New Expense',
            'price': '150.00',
            'expense_type': 'b2b',
            'branch': self.branch.id,
            'is_active': 'on',
        })
        self.assertEqual(response.status_code, 302)  # Redirect after success
        self.assertTrue(Expense.objects.filter(name='New Expense').exists())
    
    def test_edit_expense(self):
        """Test editing expense"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.post(
            reverse('editExpense', args=[self.expense.id]),
            {
                'name': 'Updated Expense',
                'price': '200.00',
                'expense_type': 'b2c',
                'branch': self.branch.id,
                'is_active': 'on',
            }
        )
        self.assertEqual(response.status_code, 302)
        self.expense.refresh_from_db()
        self.assertEqual(self.expense.name, 'Updated Expense')
        self.assertEqual(self.expense.price, Decimal('200.00'))
    
    def test_delete_expense(self):
        """Test deleting expense"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.post(
            reverse('deleteExpense', args=[self.expense.id])
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Expense.objects.filter(id=self.expense.id).exists())
    
    def test_expense_detail(self):
        """Test expense detail view"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(
            reverse('expenseDetail', args=[self.expense.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Expense')
    
    def test_expense_analytics(self):
        """Test expense analytics view"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('expenseAnalytics'))
        self.assertEqual(response.status_code, 200)


class ExpenseAdminTestCase(TestCase):
    """Test cases for Expense admin"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        
        # Create superuser
        self.superuser = User.objects.create_superuser(
            username='admin',
            password='adminpass123',
            email='admin@test.com'
        )
        
        self.center = TranslationCenter.objects.create(
            name='Test Center',
            owner=self.superuser,
            is_active=True
        )
        
        self.branch = Branch.objects.create(
            center=self.center,
            name='Test Branch',
            is_active=True,
            is_main=True
        )
        
        self.expense = Expense.objects.create(
            name='Admin Test Expense',
            price=Decimal('100.00'),
            expense_type='both',
            branch=self.branch,
            is_active=True
        )
    
    def test_expense_admin_list(self):
        """Test expense appears in admin list"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get('/admin/services/expense/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Admin Test Expense')
    
    def test_product_admin_expense_field(self):
        """Test expense field appears in product admin"""
        self.client.login(username='admin', password='adminpass123')
        
        # Create category and product
        category = Category.objects.create(
            branch=self.branch,
            name='Test Category',
            charging='static',
            is_active=True
        )
        product = Product.objects.create(
            name='Test Product',
            category=category,
            ordinary_first_page_price=Decimal('100.00'),
            ordinary_other_page_price=Decimal('50.00'),
            agency_first_page_price=Decimal('80.00'),
            agency_other_page_price=Decimal('40.00'),
            is_active=True
        )
        
        response = self.client.get(f'/admin/services/product/{product.id}/change/')
        self.assertEqual(response.status_code, 200)
        # Check for expenses field in the form
        self.assertContains(response, 'expenses')

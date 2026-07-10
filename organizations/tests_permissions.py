"""
Comprehensive Permission System Tests

Tests different permission combinations and verifies that users:
1. Can access pages when they have the required permissions
2. Cannot access pages when they lack permissions
3. See correct UI elements based on their permissions
4. Master permissions grant related permissions

Run with: python manage.py test organizations.tests_permissions
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from organizations.models import Role, AdminUser, TranslationCenter, Branch
from services.models import Language, Product, Category, Expense


class PermissionTestCase(TestCase):
    """Base test case with common setup for permission tests"""
    
    def setUp(self):
        """Create test data: center, branch, roles, and users"""
        # Create owner user first
        self.owner_user = User.objects.create_user(
            username='test_owner',
            password='testpass123',
            email='owner@test.com'
        )
        
        # Create center and branch
        self.center = TranslationCenter.objects.create(
            name="Test Center",
            address="Test Address",
            owner=self.owner_user
        )
        self.branch = Branch.objects.create(
            name="Test Branch",
            center=self.center,
            address="Branch Address"
        )
        
        # Create test roles with different permission combinations
        self.create_test_roles()
        
        # Create test users
        self.create_test_users()
        
        # Create client for making requests
        self.client = Client()
    
    def create_test_roles(self):
        """Create roles with different permission combinations"""
        
        # Role 1: Full language access
        self.role_language_full = Role.objects.create(
            name='language_full',
            display_name='Language Full Access',
            can_manage_languages=True,
            can_view_languages=True,
            can_create_languages=True,
            can_edit_languages=True,
            can_delete_languages=True,
        )
        
        # Role 2: View languages only
        self.role_language_view = Role.objects.create(
            name='language_view',
            display_name='Language View Only',
            can_view_languages=True,
            can_create_languages=False,
            can_edit_languages=False,
            can_delete_languages=False,
        )
        
        # Role 3: No language permissions
        self.role_no_language = Role.objects.create(
            name='no_language',
            display_name='No Language Access',
            can_view_languages=False,
            can_create_languages=False,
            can_edit_languages=False,
            can_delete_languages=False,
        )
        
        # Role 4: Mixed permissions (products + expenses)
        self.role_mixed = Role.objects.create(
            name='mixed_perms',
            display_name='Mixed Permissions',
            can_manage_products=True,
            can_view_expenses=True,
            can_view_all_orders=True,
        )
        
        # Role 5: Master permission only (should grant all)
        self.role_master_only = Role.objects.create(
            name='master_only',
            display_name='Master Permission Only',
            can_manage_languages=True,
            can_view_languages=False,  # Should still work via master
            can_create_languages=False,  # Should still work via master
        )
    
    def create_test_users(self):
        """Create test users with different roles"""
        
        # User 1: Full language access
        self.user_full = User.objects.create_user(
            username='user_language_full',
            password='testpass123'
        )
        self.admin_full = AdminUser.objects.create(
            user=self.user_full,
            role=self.role_language_full,
            center=self.center,
            branch=self.branch
        )
        
        # User 2: View only
        self.user_view = User.objects.create_user(
            username='user_language_view',
            password='testpass123'
        )
        self.admin_view = AdminUser.objects.create(
            user=self.user_view,
            role=self.role_language_view,
            center=self.center,
            branch=self.branch
        )
        
        # User 3: No language access
        self.user_none = User.objects.create_user(
            username='user_no_language',
            password='testpass123'
        )
        self.admin_none = AdminUser.objects.create(
            user=self.user_none,
            role=self.role_no_language,
            center=self.center,
            branch=self.branch
        )
        
        # User 4: Mixed permissions
        self.user_mixed = User.objects.create_user(
            username='user_mixed',
            password='testpass123'
        )
        self.admin_mixed = AdminUser.objects.create(
            user=self.user_mixed,
            role=self.role_mixed,
            center=self.center,
            branch=self.branch
        )
        
        # User 5: Master permission only
        self.user_master = User.objects.create_user(
            username='user_master',
            password='testpass123'
        )
        self.admin_master = AdminUser.objects.create(
            user=self.user_master,
            role=self.role_master_only,
            center=self.center,
            branch=self.branch
        )


class LanguagePermissionTests(PermissionTestCase):
    """Test language permissions"""
    
    def test_full_access_can_view_language_list(self):
        """User with full access can view language list"""
        self.client.login(username='user_language_full', password='testpass123')
        response = self.client.get(reverse('languageList'))
        self.assertEqual(response.status_code, 200)
        print("✓ Full access user can view language list")
    
    def test_view_only_can_view_language_list(self):
        """User with view permission can view language list"""
        self.client.login(username='user_language_view', password='testpass123')
        response = self.client.get(reverse('languageList'))
        self.assertEqual(response.status_code, 200)
        print("✓ View-only user can view language list")
    
    def test_no_access_cannot_view_language_list(self):
        """User without permission cannot view language list"""
        self.client.login(username='user_no_language', password='testpass123')
        response = self.client.get(reverse('languageList'))
        self.assertNotEqual(response.status_code, 200)
        self.assertIn(response.status_code, [302, 403])  # Redirect or forbidden
        print("✓ No access user cannot view language list")
    
    def test_master_permission_grants_view_access(self):
        """Master permission grants view access even if direct permission is False"""
        self.client.login(username='user_master', password='testpass123')
        response = self.client.get(reverse('languageList'))
        self.assertEqual(response.status_code, 200)
        print("✓ Master permission grants view access")
    
    def test_create_language_requires_permission(self):
        """Only users with create permission can create languages"""
        # Create a test language
        language_data = {
            'name': 'Test Language',
            'short_name': 'TST',
            'branch_id': self.branch.id,
            'agency_page_price': 1000,
            'agency_other_page_price': 500,
            'agency_copy_price': 300,
            'ordinary_page_price': 1500,
            'ordinary_other_page_price': 750,
            'ordinary_copy_price': 400,
        }
        
        # User with full access can create
        self.client.login(username='user_language_full', password='testpass123')
        response = self.client.post(
            reverse('createLanguageInline'),
            data=language_data,
        )
        self.assertIn(response.status_code, [200, 201])
        print("✓ Full access user can create language")
        
        # User with view only cannot create
        self.client.login(username='user_language_view', password='testpass123')
        response = self.client.post(
            reverse('createLanguageInline'),
            data=language_data,
        )
        self.assertNotEqual(response.status_code, 200)
        print("✓ View-only user cannot create language")
    
    def test_edit_language_requires_permission(self):
        """Only users with edit permission can edit languages"""
        # Create a language first
        language = Language.objects.create(
            name='Edit Test Language',
            short_name='ETL',
            branch=self.branch,
        )
        
        # User with full access can edit
        self.client.login(username='user_language_full', password='testpass123')
        response = self.client.get(reverse('editLanguage', args=[language.id]))
        self.assertEqual(response.status_code, 200)
        print("✓ Full access user can access edit page")
        
        # User with view only cannot edit
        self.client.login(username='user_language_view', password='testpass123')
        response = self.client.get(reverse('editLanguage', args=[language.id]))
        self.assertNotEqual(response.status_code, 200)
        print("✓ View-only user cannot access edit page")


class HasPermissionMethodTests(PermissionTestCase):
    """Test the has_permission() method"""
    
    def test_direct_permission_check(self):
        """Test direct permission checking"""
        # Full access user
        self.assertTrue(self.admin_full.has_permission('can_view_languages'))
        self.assertTrue(self.admin_full.has_permission('can_create_languages'))
        self.assertTrue(self.admin_full.has_permission('can_edit_languages'))
        self.assertTrue(self.admin_full.has_permission('can_delete_languages'))
        print("✓ Direct permissions work correctly")
    
    def test_view_only_permissions(self):
        """Test view-only user has correct permissions"""
        self.assertTrue(self.admin_view.has_permission('can_view_languages'))
        self.assertFalse(self.admin_view.has_permission('can_create_languages'))
        self.assertFalse(self.admin_view.has_permission('can_edit_languages'))
        self.assertFalse(self.admin_view.has_permission('can_delete_languages'))
        print("✓ View-only permissions work correctly")
    
    def test_no_permissions(self):
        """Test user with no permissions"""
        self.assertFalse(self.admin_none.has_permission('can_view_languages'))
        self.assertFalse(self.admin_none.has_permission('can_create_languages'))
        self.assertFalse(self.admin_none.has_permission('can_edit_languages'))
        self.assertFalse(self.admin_none.has_permission('can_delete_languages'))
        print("✓ No permissions work correctly")
    
    def test_master_permission_grants_all(self):
        """Test that master permission grants all related permissions"""
        # Master permission user has can_manage_languages=True but others=False
        # Should still have access to all via master permission
        self.assertTrue(self.admin_master.has_permission('can_view_languages'))
        self.assertTrue(self.admin_master.has_permission('can_create_languages'))
        self.assertTrue(self.admin_master.has_permission('can_edit_languages'))
        self.assertTrue(self.admin_master.has_permission('can_delete_languages'))
        print("✓ Master permission grants all related permissions")
    
    def test_mixed_permissions(self):
        """Test user with mixed permissions across categories"""
        # Has product permissions
        self.assertTrue(self.admin_mixed.has_permission('can_manage_products'))
        self.assertTrue(self.admin_mixed.has_permission('can_view_products'))
        self.assertTrue(self.admin_mixed.has_permission('can_create_products'))
        
        # Has expense view only
        self.assertTrue(self.admin_mixed.has_permission('can_view_expenses'))
        self.assertFalse(self.admin_mixed.has_permission('can_create_expenses'))
        
        # No language permissions
        self.assertFalse(self.admin_mixed.has_permission('can_view_languages'))
        print("✓ Mixed permissions work correctly")


class ContextProcessorTests(PermissionTestCase):
    """Test that permissions are correctly available in templates"""
    
    def test_full_access_context(self):
        """Test context processor for full access user"""
        self.client.login(username='user_language_full', password='testpass123')
        response = self.client.get(reverse('languageList'))
        
        # Check that permissions are in context
        self.assertTrue(response.context['permissions']['can_view_languages'])
        self.assertTrue(response.context['permissions']['can_create_languages'])
        self.assertTrue(response.context['permissions']['can_edit_languages'])
        self.assertTrue(response.context['permissions']['can_delete_languages'])
        print("✓ Full access permissions available in template context")
    
    def test_view_only_context(self):
        """Test context processor for view-only user"""
        self.client.login(username='user_language_view', password='testpass123')
        response = self.client.get(reverse('languageList'))
        
        # Check that only view permission is in context
        self.assertTrue(response.context['permissions']['can_view_languages'])
        self.assertFalse(response.context['permissions']['can_create_languages'])
        self.assertFalse(response.context['permissions']['can_edit_languages'])
        self.assertFalse(response.context['permissions']['can_delete_languages'])
        print("✓ View-only permissions correctly limited in template context")
    
    def test_mixed_permissions_context(self):
        """Test context processor for mixed permissions user"""
        self.client.login(username='user_mixed', password='testpass123')
        response = self.client.get(reverse('index'))
        
        # Has product permissions
        self.assertTrue(response.context['permissions']['can_manage_products'])
        self.assertTrue(response.context['permissions']['can_view_products'])
        
        # Has expense view only
        self.assertTrue(response.context['permissions']['can_view_expenses'])
        self.assertFalse(response.context['permissions']['can_create_expenses'])
        
        # No language permissions
        self.assertFalse(response.context['permissions']['can_view_languages'])
        print("✓ Mixed permissions correctly reflected in template context")


class PermissionCombinationTests(PermissionTestCase):
    """Test various permission combinations"""
    
    def test_create_without_view_should_fail(self):
        """User with create but not view permission (unusual case)"""
        # Create a special role with create but not view
        role = Role.objects.create(
            name='create_no_view',
            display_name='Create No View',
            can_view_languages=False,
            can_create_languages=True,
        )
        user = User.objects.create_user(username='user_create_no_view', password='test')
        admin = AdminUser.objects.create(
            user=user,
            role=role,
            center=self.center,
            branch=self.branch
        )
        
        # Should not be able to view list
        self.client.login(username='user_create_no_view', password='test')
        response = self.client.get(reverse('languageList'))
        self.assertNotEqual(response.status_code, 200)
        print("✓ Create without view permission correctly denied access")
    
    def test_edit_without_create(self):
        """User can edit but not create"""
        role = Role.objects.create(
            name='edit_no_create',
            display_name='Edit No Create',
            can_view_languages=True,
            can_create_languages=False,
            can_edit_languages=True,
        )
        user = User.objects.create_user(username='user_edit_no_create', password='test')
        admin = AdminUser.objects.create(
            user=user,
            role=role,
            center=self.center,
            branch=self.branch
        )
        
        # Can view
        self.assertTrue(admin.has_permission('can_view_languages'))
        # Can edit
        self.assertTrue(admin.has_permission('can_edit_languages'))
        # Cannot create
        self.assertFalse(admin.has_permission('can_create_languages'))
        print("✓ Edit without create permission works correctly")
    
    def test_delete_requires_explicit_permission(self):
        """Delete requires explicit permission even with other permissions"""
        role = Role.objects.create(
            name='all_except_delete',
            display_name='All Except Delete',
            can_view_languages=True,
            can_create_languages=True,
            can_edit_languages=True,
            can_delete_languages=False,
        )
        user = User.objects.create_user(username='user_no_delete', password='test')
        admin = AdminUser.objects.create(
            user=user,
            role=role,
            center=self.center,
            branch=self.branch
        )
        
        # Has all except delete
        self.assertTrue(admin.has_permission('can_view_languages'))
        self.assertTrue(admin.has_permission('can_create_languages'))
        self.assertTrue(admin.has_permission('can_edit_languages'))
        self.assertFalse(admin.has_permission('can_delete_languages'))
        print("✓ Delete permission is independent of other permissions")


class MultiCategoryPermissionTests(PermissionTestCase):
    """Test permissions across multiple categories"""
    
    def test_user_with_multiple_category_permissions(self):
        """User with permissions in multiple categories"""
        role = Role.objects.create(
            name='multi_category',
            display_name='Multi Category',
            can_view_languages=True,
            can_create_languages=True,
            can_view_products=True,
            can_view_expenses=True,
            can_create_expenses=True,
            can_view_all_orders=True,
        )
        user = User.objects.create_user(username='user_multi', password='test')
        admin = AdminUser.objects.create(
            user=user,
            role=role,
            center=self.center,
            branch=self.branch
        )
        
        # Languages
        self.assertTrue(admin.has_permission('can_view_languages'))
        self.assertTrue(admin.has_permission('can_create_languages'))
        self.assertFalse(admin.has_permission('can_delete_languages'))
        
        # Products
        self.assertTrue(admin.has_permission('can_view_products'))
        self.assertFalse(admin.has_permission('can_create_products'))
        
        # Expenses
        self.assertTrue(admin.has_permission('can_view_expenses'))
        self.assertTrue(admin.has_permission('can_create_expenses'))
        
        # Orders
        self.assertTrue(admin.has_permission('can_view_all_orders'))
        self.assertFalse(admin.has_permission('can_create_orders'))
        
        print("✓ Multi-category permissions work independently")
    
    def test_master_permissions_dont_cross_categories(self):
        """Master permission in one category doesn't grant permissions in another"""
        role = Role.objects.create(
            name='master_language_only',
            display_name='Master Language Only',
            can_manage_languages=True,
            can_view_products=False,
        )
        user = User.objects.create_user(username='user_master_lang', password='test')
        admin = AdminUser.objects.create(
            user=user,
            role=role,
            center=self.center,
            branch=self.branch
        )
        
        # Has all language permissions via master
        self.assertTrue(admin.has_permission('can_view_languages'))
        self.assertTrue(admin.has_permission('can_create_languages'))
        
        # Does not have product permissions
        self.assertFalse(admin.has_permission('can_view_products'))
        self.assertFalse(admin.has_permission('can_create_products'))
        
        print("✓ Master permissions are category-specific")


class PermissionInheritanceTests(PermissionTestCase):
    """Test permission inheritance and hierarchies"""
    
    def test_manage_permission_grants_all_operations(self):
        """Test all operations that should be granted by manage permission"""
        operations = [
            'can_view_languages',
            'can_create_languages',
            'can_edit_languages',
            'can_delete_languages',
        ]
        
        for operation in operations:
            self.assertTrue(
                self.admin_master.has_permission(operation),
                f"can_manage_languages should grant {operation}"
            )
        
        print("✓ Manage permission grants all related operations")
    
    def test_manage_products_grants_all_product_permissions(self):
        """Test product manage permission grants all product operations"""
        operations = [
            'can_view_products',
            'can_create_products',
            'can_edit_products',
            'can_delete_products',
        ]
        
        for operation in operations:
            self.assertTrue(
                self.admin_mixed.has_permission(operation),
                f"can_manage_products should grant {operation}"
            )
        
        print("✓ Manage products grants all product operations")


def run_all_tests():
    """Run all permission tests and print summary"""
    import sys
    from io import StringIO
    from django.test.runner import DiscoverRunner
    
    # Capture output
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    
    # Run tests
    runner = DiscoverRunner(verbosity=2)
    failures = runner.run_tests(['organizations.tests_permissions'])
    
    # Restore output
    output = sys.stdout.getvalue()
    sys.stdout = old_stdout
    
    # Print results
    print("\n" + "="*80)
    print("PERMISSION SYSTEM TEST RESULTS")
    print("="*80)
    print(output)
    
    if failures:
        print(f"\n❌ {failures} test(s) failed")
    else:
        print("\n✅ All tests passed!")
    
    print("="*80)


if __name__ == '__main__':
    run_all_tests()

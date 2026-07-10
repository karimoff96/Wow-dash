"""
Unit tests for RBAC (Role-Based Access Control) functionality.

Tests cover:
- Owner creation by superuser only
- Owner cannot create another Owner
- Manager can view staff detail but cannot edit
- can_create_orders permission is respected
- Single owner per center enforcement
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.exceptions import ValidationError

from organizations.models import TranslationCenter, Branch, Role, AdminUser
from organizations.rbac import (
    get_admin_profile,
    can_edit_staff,
    get_assignable_roles,
    validate_owner_creation,
)


class RoleModelTests(TestCase):
    """Tests for Role model and permissions"""

    def setUp(self):
        """Set up test data"""
        # Create system roles
        self.owner_role = Role.objects.create(
            name='owner',
            display_name='Owner',
            is_system_role=True,
            can_manage_centers=True,
            can_manage_branches=True,
            can_manage_staff=True,
            can_view_staff=True,
            can_view_all_orders=True,
            can_manage_orders=True,
            can_create_orders=True,
            can_assign_orders=True,
            can_receive_payments=True,
            can_view_reports=True,
            can_manage_products=True,
            can_manage_customers=True,
            can_export_data=True,
        )
        
        self.manager_role = Role.objects.create(
            name='manager',
            display_name='Manager',
            is_system_role=True,
            can_manage_centers=False,
            can_manage_branches=False,
            can_manage_staff=False,
            can_view_staff=True,
            can_view_all_orders=True,
            can_manage_orders=True,
            can_create_orders=True,
            can_assign_orders=True,
            can_receive_payments=True,
            can_view_reports=True,
        )
        
        self.staff_role = Role.objects.create(
            name='staff',
            display_name='Staff',
            is_system_role=True,
            can_manage_orders=True,
            can_receive_payments=True,
        )

    def test_role_has_new_permissions(self):
        """Test that roles have the new permission fields"""
        self.assertTrue(hasattr(self.owner_role, 'can_create_orders'))
        self.assertTrue(hasattr(self.owner_role, 'can_view_staff'))

    def test_owner_has_can_create_orders(self):
        """Test that owner role has can_create_orders permission"""
        self.assertTrue(self.owner_role.can_create_orders)

    def test_staff_no_can_create_orders(self):
        """Test that staff role does not have can_create_orders by default"""
        self.assertFalse(self.staff_role.can_create_orders)

    def test_get_all_permissions_includes_new_permissions(self):
        """Test that get_all_permissions includes new permission fields"""
        perms = Role.get_all_permissions()
        self.assertIn('can_create_orders', perms)
        self.assertIn('can_view_staff', perms)

    def test_get_permission_labels(self):
        """Test that permission labels are defined"""
        labels = Role.get_permission_labels()
        self.assertIn('can_create_orders', labels)
        self.assertIn('can_view_staff', labels)

    def test_get_default_permissions_for_owner(self):
        """Test default permissions for owner role"""
        defaults = Role.get_default_permissions_for_role('owner')
        self.assertTrue(defaults.get('can_manage_centers'))
        self.assertTrue(defaults.get('can_create_orders'))
        self.assertTrue(defaults.get('can_view_staff'))


class OwnerCreationTests(TestCase):
    """Tests for owner creation restrictions"""

    def setUp(self):
        """Set up test data"""
        # Create superuser
        self.superuser = User.objects.create_superuser(
            username='superadmin',
            email='super@test.com',
            password='testpass123'
        )
        
        # Create regular user
        self.regular_user = User.objects.create_user(
            username='regular',
            email='regular@test.com',
            password='testpass123'
        )
        
        # Create owner role
        self.owner_role = Role.objects.create(
            name='owner',
            display_name='Owner',
            is_system_role=True,
            can_manage_centers=True,
            can_manage_staff=True,
        )
        
        self.manager_role = Role.objects.create(
            name='manager',
            display_name='Manager',
            is_system_role=True,
        )
        
        self.staff_role = Role.objects.create(
            name='staff',
            display_name='Staff',
            is_system_role=True,
        )
        
        # Create center
        self.center = TranslationCenter.objects.create(
            name='Test Center',
            owner=self.superuser
        )
        
        # Get the auto-created branch
        self.branch = Branch.objects.filter(center=self.center).first()

    def test_superuser_can_create_owner(self):
        """Test that superuser can create an owner"""
        is_valid, error = validate_owner_creation(self.superuser, self.center)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_regular_user_cannot_create_owner(self):
        """Test that regular user cannot create an owner"""
        is_valid, error = validate_owner_creation(self.regular_user, self.center)
        self.assertFalse(is_valid)
        self.assertIn('superuser', error.lower())

    def test_superuser_can_validate_owner_replacement(self):
        """Superusers may replace an existing center owner."""
        # Create first owner
        owner_user = User.objects.create_user(
            username='owner1',
            email='owner1@test.com',
            password='testpass123'
        )
        
        AdminUser.objects.create(
            user=owner_user,
            role=self.owner_role,
            center=self.center,
            branch=self.branch,
        )
        
        # The replacement is allowed; AdminUser.save unlinks the old owner.
        is_valid, error = validate_owner_creation(self.superuser, self.center)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_owner_cannot_create_another_owner(self):
        """Test that an owner cannot create another owner"""
        # Create owner user
        owner_user = User.objects.create_user(
            username='owner1',
            email='owner1@test.com',
            password='testpass123'
        )
        
        AdminUser.objects.create(
            user=owner_user,
            role=self.owner_role,
            center=self.center,
            branch=self.branch,
        )
        
        # Check assignable roles for owner
        assignable_roles = get_assignable_roles(owner_user)
        role_names = [r.name for r in assignable_roles]
        
        self.assertNotIn('owner', role_names)
        self.assertIn('manager', role_names)
        self.assertIn('staff', role_names)

    def test_admin_user_replaces_existing_owner(self):
        """Saving a replacement leaves only one active linked owner."""
        # Create first owner
        owner_user1 = User.objects.create_user(
            username='owner1',
            email='owner1@test.com',
            password='testpass123'
        )
        
        AdminUser.objects.create(
            user=owner_user1,
            role=self.owner_role,
            center=self.center,
            branch=self.branch,
        )
        
        # Creating a second owner deactivates and unlinks the first.
        owner_user2 = User.objects.create_user(
            username='owner2',
            email='owner2@test.com',
            password='testpass123'
        )
        
        replacement = AdminUser.objects.create(
            user=owner_user2,
            role=self.owner_role,
            center=self.center,
            branch=self.branch,
        )
        first = AdminUser.objects.get(user=owner_user1)
        self.assertFalse(first.is_active)
        self.assertIsNone(first.center)
        self.assertTrue(replacement.is_active)
        self.assertEqual(replacement.center, self.center)


class ManagerStaffDetailAccessTests(TestCase):
    """Tests for manager's staff detail access (read-only)"""

    def setUp(self):
        """Set up test data"""
        # Create superuser
        self.superuser = User.objects.create_superuser(
            username='superadmin',
            email='super@test.com',
            password='testpass123'
        )
        
        # Create roles
        self.owner_role = Role.objects.create(
            name='owner',
            display_name='Owner',
            is_system_role=True,
            can_manage_staff=True,
            can_view_staff=True,
        )
        
        self.manager_role = Role.objects.create(
            name='manager',
            display_name='Manager',
            is_system_role=True,
            can_view_staff=True,
            can_manage_staff=False,
        )
        
        self.staff_role = Role.objects.create(
            name='staff',
            display_name='Staff',
            is_system_role=True,
        )
        
        # Create center
        self.center = TranslationCenter.objects.create(
            name='Test Center',
            owner=self.superuser
        )
        self.branch = Branch.objects.filter(center=self.center).first()
        
        # Create owner
        self.owner_user = User.objects.create_user(
            username='owner',
            email='owner@test.com',
            password='testpass123'
        )
        self.owner_profile = AdminUser.objects.create(
            user=self.owner_user,
            role=self.owner_role,
            center=self.center,
            branch=self.branch,
        )
        
        # Create manager
        self.manager_user = User.objects.create_user(
            username='manager',
            email='manager@test.com',
            password='testpass123'
        )
        self.manager_profile = AdminUser.objects.create(
            user=self.manager_user,
            role=self.manager_role,
            center=self.center,
            branch=self.branch,
        )
        
        # Create staff
        self.staff_user = User.objects.create_user(
            username='staff',
            email='staff@test.com',
            password='testpass123'
        )
        self.staff_profile = AdminUser.objects.create(
            user=self.staff_user,
            role=self.staff_role,
            center=self.center,
            branch=self.branch,
        )
        
        self.client = Client()

    def test_manager_can_view_staff(self):
        """Test that manager with can_view_staff can access staff detail"""
        self.assertTrue(self.manager_profile.has_permission('can_view_staff'))

    def test_manager_cannot_edit_staff(self):
        """Test that manager cannot edit staff"""
        result = can_edit_staff(self.manager_user, self.staff_profile)
        self.assertFalse(result)

    def test_owner_can_edit_staff(self):
        """Test that owner can edit staff"""
        result = can_edit_staff(self.owner_user, self.staff_profile)
        self.assertTrue(result)

    def test_nobody_can_edit_owner(self):
        """Test that non-superuser cannot edit owner"""
        result = can_edit_staff(self.manager_user, self.owner_profile)
        self.assertFalse(result)

    def test_superuser_can_edit_anyone(self):
        """Test that superuser can edit anyone"""
        edit_owner = can_edit_staff(self.superuser, self.owner_profile)
        edit_staff = can_edit_staff(self.superuser, self.staff_profile)
        
        self.assertTrue(edit_owner)
        self.assertTrue(edit_staff)


class CanCreateOrdersPermissionTests(TestCase):
    """Tests for can_create_orders permission"""

    def setUp(self):
        """Set up test data"""
        self.superuser = User.objects.create_superuser(
            username='superadmin',
            email='super@test.com',
            password='testpass123'
        )
        
        # Create roles with different permissions
        self.role_with_permission = Role.objects.create(
            name='translator',
            display_name='Translator',
            can_create_orders=True,
        )
        
        self.role_without_permission = Role.objects.create(
            name='viewer',
            display_name='Viewer',
            can_create_orders=False,
        )
        
        self.center = TranslationCenter.objects.create(
            name='Test Center',
            owner=self.superuser
        )
        self.branch = Branch.objects.filter(center=self.center).first()
        
        # Create users with different roles
        self.user_with_perm = User.objects.create_user(
            username='translator',
            email='translator@test.com',
            password='testpass123'
        )
        self.profile_with_perm = AdminUser.objects.create(
            user=self.user_with_perm,
            role=self.role_with_permission,
            center=self.center,
            branch=self.branch,
        )
        
        self.user_without_perm = User.objects.create_user(
            username='viewer',
            email='viewer@test.com',
            password='testpass123'
        )
        self.profile_without_perm = AdminUser.objects.create(
            user=self.user_without_perm,
            role=self.role_without_permission,
            center=self.center,
            branch=self.branch,
        )

    def test_user_has_create_orders_permission(self):
        """Test user with can_create_orders permission"""
        self.assertTrue(self.profile_with_perm.has_permission('can_create_orders'))

    def test_user_lacks_create_orders_permission(self):
        """Test user without can_create_orders permission"""
        self.assertFalse(self.profile_without_perm.has_permission('can_create_orders'))


class AssignableRolesTests(TestCase):
    """Tests for get_assignable_roles function"""

    def setUp(self):
        """Set up test data"""
        self.superuser = User.objects.create_superuser(
            username='superadmin',
            email='super@test.com',
            password='testpass123'
        )
        
        self.owner_role = Role.objects.create(
            name='owner',
            display_name='Owner',
            is_system_role=True,
            is_active=True,
            can_manage_staff=True,
        )
        
        self.manager_role = Role.objects.create(
            name='manager',
            display_name='Manager',
            is_system_role=True,
            is_active=True,
            can_manage_staff=True,
        )
        
        self.staff_role = Role.objects.create(
            name='staff',
            display_name='Staff',
            is_system_role=True,
            is_active=True,
        )
        
        self.center = TranslationCenter.objects.create(
            name='Test Center',
            owner=self.superuser
        )
        self.branch = Branch.objects.filter(center=self.center).first()
        
        # Create owner user
        self.owner_user = User.objects.create_user(
            username='owner',
            email='owner@test.com',
            password='testpass123'
        )
        AdminUser.objects.create(
            user=self.owner_user,
            role=self.owner_role,
            center=self.center,
            branch=self.branch,
        )
        
        # Create manager user
        self.manager_user = User.objects.create_user(
            username='manager',
            email='manager@test.com',
            password='testpass123'
        )
        AdminUser.objects.create(
            user=self.manager_user,
            role=self.manager_role,
            center=self.center,
            branch=self.branch,
        )

    def test_superuser_can_assign_all_roles(self):
        """Test superuser can assign all roles including owner"""
        roles = get_assignable_roles(self.superuser)
        role_names = [r.name for r in roles]
        
        self.assertIn('owner', role_names)
        self.assertIn('manager', role_names)
        self.assertIn('staff', role_names)

    def test_owner_cannot_assign_owner(self):
        """Test owner cannot assign owner role"""
        roles = get_assignable_roles(self.owner_user)
        role_names = [r.name for r in roles]
        
        self.assertNotIn('owner', role_names)
        self.assertIn('manager', role_names)
        self.assertIn('staff', role_names)

    def test_manager_can_only_assign_staff(self):
        """Test manager can only assign staff role"""
        roles = get_assignable_roles(self.manager_user)
        role_names = [r.name for r in roles]
        
        self.assertNotIn('owner', role_names)
        self.assertNotIn('manager', role_names)
        self.assertIn('staff', role_names)

    def test_custom_staff_manager_role_gets_assignable_roles(self):
        """Custom role names with can_manage_staff should still get assignable roles"""
        custom_supervisor_role = Role.objects.create(
            name='supervisor_custom',
            display_name='Supervisor',
            is_active=True,
            can_manage_staff=True,
        )

        custom_staff_role = Role.objects.create(
            name='assistant_custom',
            display_name='Assistant',
            is_active=True,
        )

        custom_user = User.objects.create_user(
            username='supervisor_user',
            email='supervisor@test.com',
            password='testpass123'
        )

        AdminUser.objects.create(
            user=custom_user,
            role=custom_supervisor_role,
            center=self.center,
            branch=self.branch,
        )

        roles = get_assignable_roles(custom_user)
        role_names = [r.name for r in roles]

        self.assertIn('assistant_custom', role_names)
        self.assertNotIn('owner', role_names)


class RoleValidationTests(TestCase):
    """Tests for AdminUser.validate_role_assignment"""

    def setUp(self):
        """Set up test data"""
        self.superuser = User.objects.create_superuser(
            username='superadmin',
            email='super@test.com',
            password='testpass123'
        )
        
        self.regular_user = User.objects.create_user(
            username='regular',
            email='regular@test.com',
            password='testpass123'
        )
        
        self.owner_role = Role.objects.create(
            name='owner',
            display_name='Owner',
            is_system_role=True,
        )
        
        self.manager_role = Role.objects.create(
            name='manager',
            display_name='Manager',
            is_system_role=True,
        )
        
        self.center = TranslationCenter.objects.create(
            name='Test Center',
            owner=self.superuser
        )
        self.branch = Branch.objects.filter(center=self.center).first()

    def test_superuser_can_assign_owner(self):
        """Test superuser can assign owner role"""
        is_valid, error = AdminUser.validate_role_assignment(
            self.superuser, self.owner_role, self.center
        )
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_non_superuser_cannot_assign_owner(self):
        """Test non-superuser cannot assign owner role"""
        is_valid, error = AdminUser.validate_role_assignment(
            self.regular_user, self.owner_role, self.center
        )
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)

    def test_superuser_can_replace_owner_for_center(self):
        """A superuser may replace the current owner."""
        # Create first owner
        owner_user = User.objects.create_user(
            username='owner1',
            email='owner1@test.com',
            password='testpass123'
        )
        AdminUser.objects.create(
            user=owner_user,
            role=self.owner_role,
            center=self.center,
            branch=self.branch,
        )
        
        # Validation allows replacement; save() unlinks the previous owner.
        is_valid, error = AdminUser.validate_role_assignment(
            self.superuser, self.owner_role, self.center
        )
        self.assertTrue(is_valid)
        self.assertIsNone(error)

#!/usr/bin/env python
"""
Comprehensive Tariff Feature Testing Script

This script:
1. Creates test tariffs with different feature combinations
2. Creates test organizations with subscriptions to these tariffs
3. Tests feature access for each tariff
4. Verifies that feature-based permissions work correctly

Run with: python manage.py shell < test_tariff_features.py
"""

import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'WowDash.settings')
django.setup()

from django.contrib.auth import get_user_model
from billing.models import Tariff, TariffPricing, Subscription
from organizations.models import TranslationCenter, Branch
from datetime import date, timedelta
from decimal import Decimal

User = get_user_model()

# ANSI color codes
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(80)}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.END}\n")

def print_section(text):
    print(f"\n{Colors.CYAN}{Colors.BOLD}{text}{Colors.END}")
    print(f"{Colors.CYAN}{'-'*80}{Colors.END}")

def print_success(text):
    print(f"{Colors.GREEN}[OK] {text}{Colors.END}")

def print_error(text):
    print(f"{Colors.RED}[ERROR] {text}{Colors.END}")

def print_info(text):
    print(f"{Colors.BLUE}[INFO] {text}{Colors.END}")

def print_warning(text):
    print(f"{Colors.WARNING}[WARNING] {text}{Colors.END}")


def cleanup_test_data():
    """Clean up any existing test data"""
    print_section("Cleaning up existing test data...")
    
    # Delete test organizations
    test_orgs = TranslationCenter.objects.filter(name__startswith='TEST_')
    count = test_orgs.count()
    if count > 0:
        test_orgs.delete()
        print_success(f"Deleted {count} test organizations")
    
    # Delete test tariffs
    test_tariffs = Tariff.objects.filter(slug__startswith='test-')
    count = test_tariffs.count()
    if count > 0:
        test_tariffs.delete()
        print_success(f"Deleted {count} test tariffs")
    
    # Delete test users
    test_users = User.objects.filter(email__startswith='test_')
    count = test_users.count()
    if count > 0:
        test_users.delete()
        print_success(f"Deleted {count} test users")


def create_test_tariffs():
    """Create test tariffs with different feature combinations"""
    print_section("Creating Test Tariffs...")
    
    tariffs = {}
    
    # 1. BASIC Tariff - Minimal features (Orders + Analytics only)
    print_info("Creating BASIC tariff (Orders + Analytics only)...")
    basic = Tariff.objects.create(
        title="TEST Basic Plan",
        slug="test-basic",
        description="Basic plan with minimal features for testing",
        is_active=True,
        is_featured=False,
        is_trial=False,
        max_branches=1,
        max_staff=3,
        max_monthly_orders=100,
        display_order=1,
        # Order features
        feature_orders_basic=True,
        feature_orders_advanced=False,
        feature_order_assignment=False,
        feature_bulk_payments=False,
        # Analytics features
        feature_analytics_basic=True,
        feature_analytics_advanced=False,
        feature_financial_reports=False,
        feature_staff_performance=False,
        feature_custom_reports=False,
        feature_export_reports=False,
        # All other features disabled
        feature_api_access=False,
        feature_webhooks=False,
        feature_integrations=False,
        feature_telegram_bot=False,
        feature_marketing_basic=False,
        feature_broadcast_messages=False,
        feature_multi_branch=False,
        feature_custom_roles=False,
        feature_branch_settings=False,
        feature_archive_access=False,
        feature_payment_management=False,
        feature_invoicing=False,
        feature_expense_tracking=False,
        feature_audit_logs=False,
        feature_products_basic=False,
        feature_products_advanced=False,
        feature_language_pricing=False,
        feature_dynamic_pricing=False,
    )
    TariffPricing.objects.create(
        tariff=basic,
        duration_months=1,
        price=Decimal('100000'),
        currency='UZS',
        is_active=True
    )
    tariffs['basic'] = basic
    print_success(f"Created {basic.title} - {basic.get_feature_count()} features enabled")
    
    # 2. STANDARD Tariff - Orders + Analytics + Integration
    print_info("Creating STANDARD tariff (Orders + Analytics + Integration)...")
    standard = Tariff.objects.create(
        title="TEST Standard Plan",
        slug="test-standard",
        description="Standard plan with orders, analytics, and basic integration",
        is_active=True,
        is_featured=False,
        is_trial=False,
        max_branches=3,
        max_staff=10,
        max_monthly_orders=500,
        display_order=2,
        # Order features
        feature_orders_basic=True,
        feature_orders_advanced=True,
        feature_order_assignment=True,
        feature_bulk_payments=True,
        # Analytics features
        feature_analytics_basic=True,
        feature_analytics_advanced=True,
        feature_financial_reports=True,
        feature_staff_performance=False,
        feature_custom_reports=False,
        feature_export_reports=True,
        # Integration features
        feature_api_access=False,
        feature_webhooks=False,
        feature_integrations=False,
        feature_telegram_bot=True,
        # Marketing features
        feature_marketing_basic=False,
        feature_broadcast_messages=False,
        # Organization features
        feature_multi_branch=True,
        feature_custom_roles=False,
        feature_branch_settings=True,
        # Storage features
        feature_archive_access=True,
        # Financial features
        feature_payment_management=True,
        feature_invoicing=False,
        feature_expense_tracking=False,
        # Support features
        # Advanced features
        feature_audit_logs=False,
        # Product features
        feature_products_basic=True,
        feature_products_advanced=False,
        feature_language_pricing=False,
        feature_dynamic_pricing=False,
    )
    TariffPricing.objects.create(
        tariff=standard,
        duration_months=1,
        price=Decimal('300000'),
        currency='UZS',
        is_active=True
    )
    tariffs['standard'] = standard
    print_success(f"Created {standard.title} - {standard.get_feature_count()} features enabled")
    
    # 3. PROFESSIONAL Tariff - Most features except advanced enterprise features
    print_info("Creating PROFESSIONAL tariff (Almost all features)...")
    professional = Tariff.objects.create(
        title="TEST Professional Plan",
        slug="test-professional",
        description="Professional plan with most features enabled",
        is_active=True,
        is_featured=True,
        is_trial=False,
        max_branches=10,
        max_staff=50,
        max_monthly_orders=2000,
        display_order=3,
        # All Order features
        feature_orders_basic=True,
        feature_orders_advanced=True,
        feature_order_assignment=True,
        feature_bulk_payments=True,
        # All Analytics features
        feature_analytics_basic=True,
        feature_analytics_advanced=True,
        feature_financial_reports=True,
        feature_staff_performance=True,
        feature_custom_reports=True,
        feature_export_reports=True,
        # Most Integration features
        feature_api_access=True,
        feature_webhooks=True,
        feature_integrations=False,  # Reserved for enterprise
        feature_telegram_bot=True,
        # All Marketing features
        feature_marketing_basic=True,
        feature_broadcast_messages=True,
        # All Organization features
        feature_multi_branch=True,
        feature_custom_roles=True,
        feature_branch_settings=True,
        # Most Storage features
        feature_archive_access=True,
        # All Financial features
        feature_payment_management=True,
        feature_invoicing=True,
        feature_expense_tracking=True,
        # All Support features
        # Some Advanced features
        feature_audit_logs=True,
        # All Product features
        feature_products_basic=True,
        feature_products_advanced=True,
        feature_language_pricing=True,
        feature_dynamic_pricing=False,  # Reserved for enterprise
    )
    TariffPricing.objects.create(
        tariff=professional,
        duration_months=1,
        price=Decimal('800000'),
        currency='UZS',
        is_active=True
    )
    tariffs['professional'] = professional
    print_success(f"Created {professional.title} - {professional.get_feature_count()} features enabled")
    
    # 4. ENTERPRISE Tariff - All features enabled
    print_info("Creating ENTERPRISE tariff (All features)...")
    enterprise = Tariff.objects.create(
        title="TEST Enterprise Plan",
        slug="test-enterprise",
        description="Enterprise plan with all features enabled",
        is_active=True,
        is_featured=False,
        is_trial=False,
        max_branches=None,  # Unlimited
        max_staff=None,  # Unlimited
        max_monthly_orders=None,  # Unlimited
        display_order=4,
        # Enable ALL features
        feature_orders_basic=True,
        feature_orders_advanced=True,
        feature_order_assignment=True,
        feature_bulk_payments=True,
        feature_analytics_basic=True,
        feature_analytics_advanced=True,
        feature_financial_reports=True,
        feature_staff_performance=True,
        feature_custom_reports=True,
        feature_export_reports=True,
        feature_api_access=True,
        feature_webhooks=True,
        feature_integrations=True,
        feature_telegram_bot=True,
        feature_marketing_basic=True,
        feature_broadcast_messages=True,
        feature_multi_branch=True,
        feature_custom_roles=True,
        feature_branch_settings=True,
        feature_archive_access=True,
        feature_payment_management=True,
        feature_invoicing=True,
        feature_expense_tracking=True,
        feature_audit_logs=True,
        feature_products_basic=True,
        feature_products_advanced=True,
        feature_language_pricing=True,
        feature_dynamic_pricing=True,
    )
    TariffPricing.objects.create(
        tariff=enterprise,
        duration_months=1,
        price=Decimal('2000000'),
        currency='UZS',
        is_active=True
    )
    tariffs['enterprise'] = enterprise
    print_success(f"Created {enterprise.title} - {enterprise.get_feature_count()} features enabled")
    
    return tariffs


def create_test_organizations(tariffs):
    """Create test organizations with subscriptions to test tariffs"""
    print_section("Creating Test Organizations and Subscriptions...")
    
    organizations = {}
    
    for tariff_key, tariff in tariffs.items():
        # Create user
        user = User.objects.create_user(
            email=f'test_{tariff_key}@example.com',
            username=f'test_{tariff_key}',
            password='testpass123',
            first_name=f'Test {tariff_key.capitalize()}',
            last_name='User'
        )
        
        # Create organization
        org = TranslationCenter.objects.create(
            name=f'TEST_{tariff_key.upper()}_Organization',
            phone=f'+998901234{tariff_key[0:3]}',
            address=f'Test Address for {tariff_key}',
            owner=user
        )
        
        # Create subscription
        pricing = tariff.pricing.first()
        subscription = Subscription.objects.create(
            organization=org,
            tariff=tariff,
            status='active',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            pricing=pricing
        )
        
        organizations[tariff_key] = {
            'user': user,
            'organization': org,
            'subscription': subscription
        }
        
        print_success(f"Created organization '{org.name}' with {tariff.title}")
    
    return organizations


def test_feature_access(organizations):
    """Test feature access for each organization"""
    print_header("TESTING FEATURE ACCESS")
    
    # Define test cases: feature_name -> expected access per tariff
    test_features = {
        'orders_basic': {
            'basic': True,
            'standard': True,
            'professional': True,
            'enterprise': True
        },
        'orders_advanced': {
            'basic': False,
            'standard': True,
            'professional': True,
            'enterprise': True
        },
        'bulk_payments': {
            'basic': False,
            'standard': True,
            'professional': True,
            'enterprise': True
        },
        'analytics_advanced': {
            'basic': False,
            'standard': True,
            'professional': True,
            'enterprise': True
        },
        'financial_reports': {
            'basic': False,
            'standard': True,
            'professional': True,
            'enterprise': True
        },
        'api_access': {
            'basic': False,
            'standard': False,
            'professional': True,
            'enterprise': True
        },
        'webhooks': {
            'basic': False,
            'standard': False,
            'professional': True,
            'enterprise': True
        },
        'marketing_basic': {
            'basic': False,
            'standard': False,
            'professional': True,
            'enterprise': True
        },
        'broadcast_messages': {
            'basic': False,
            'standard': False,
            'professional': True,
            'enterprise': True
        },
        'integrations': {
            'basic': False,
            'standard': False,
            'professional': False,
            'enterprise': True
        },
        'advanced_security': {
            'basic': False,
            'standard': False,
            'professional': False,
            'enterprise': True
        },
        'extended_storage': {
            'basic': False,
            'standard': False,
            'professional': False,
            'enterprise': True
        },
        'dynamic_pricing': {
            'basic': False,
            'standard': False,
            'professional': False,
            'enterprise': True
        },
    }
    
    total_tests = 0
    passed_tests = 0
    failed_tests = 0
    
    for feature_name, expected_access in test_features.items():
        print_section(f"Testing feature: {feature_name}")
        
        for tariff_key, should_have_access in expected_access.items():
            org_data = organizations[tariff_key]
            subscription = org_data['subscription']
            
            has_access = subscription.has_feature(feature_name)
            total_tests += 1
            
            if has_access == should_have_access:
                passed_tests += 1
                status = "[PASS]"
                print_success(f"{status} | {tariff_key.upper():12} | Expected: {should_have_access:5} | Got: {has_access:5}")
            else:
                failed_tests += 1
                status = "[FAIL]"
                print_error(f"{status} | {tariff_key.upper():12} | Expected: {should_have_access:5} | Got: {has_access:5}")
    
    # Print summary
    print_header("TEST SUMMARY")
    print_info(f"Total Tests: {total_tests}")
    print_success(f"Passed: {passed_tests}")
    if failed_tests > 0:
        print_error(f"Failed: {failed_tests}")
    else:
        print_success(f"Failed: {failed_tests}")
    
    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    print_info(f"Success Rate: {success_rate:.2f}%")
    
    return passed_tests == total_tests


def test_feature_counts(organizations):
    """Test that feature counts match expected values"""
    print_header("TESTING FEATURE COUNTS")
    
    expected_counts = {
        'basic': 2,      # Only orders_basic and analytics_basic
        'standard': 16,   # Orders (5) + Analytics (4) + Some integration + Organization + Storage + Financial + Products
        'professional': 31,  # Most features except enterprise-only
        'enterprise': 37   # All features
    }
    
    all_passed = True
    
    for tariff_key, expected_count in expected_counts.items():
        org_data = organizations[tariff_key]
        subscription = org_data['subscription']
        tariff = subscription.tariff
        
        actual_count = tariff.get_feature_count()
        
        if actual_count == expected_count:
            print_success(f"{tariff_key.upper():12} | Expected: {expected_count:2} features | Got: {actual_count:2} | [PASS]")
        else:
            print_error(f"{tariff_key.upper():12} | Expected: {expected_count:2} features | Got: {actual_count:2} | [FAIL]")
            all_passed = False
            
            # Show which features are enabled
            enabled_features = tariff.get_enabled_features()
            print_warning(f"  Enabled features: {', '.join(enabled_features)}")
    
    return all_passed


def test_subscription_status(organizations):
    """Test that subscriptions are active and valid"""
    print_header("TESTING SUBSCRIPTION STATUS")
    
    all_passed = True
    
    for tariff_key, org_data in organizations.items():
        subscription = org_data['subscription']
        
        is_active = subscription.is_active()
        status = subscription.status
        
        if is_active and status == 'active':
            print_success(f"{tariff_key.upper():12} | Status: {status:10} | is_active(): {is_active:5} | [PASS]")
        else:
            print_error(f"{tariff_key.upper():12} | Status: {status:10} | is_active(): {is_active:5} | [FAIL]")
            all_passed = False
    
    return all_passed


def main():
    """Main test runner"""
    print_header("TARIFF FEATURE TESTING SCRIPT")
    print_info("This script creates test tariffs and verifies feature access control")
    
    try:
        # Step 1: Cleanup
        cleanup_test_data()
        
        # Step 2: Create test tariffs
        tariffs = create_test_tariffs()
        
        # Step 3: Create test organizations
        organizations = create_test_organizations(tariffs)
        
        # Step 4: Test subscription status
        status_passed = test_subscription_status(organizations)
        
        # Step 5: Test feature counts
        counts_passed = test_feature_counts(organizations)
        
        # Step 6: Test feature access
        access_passed = test_feature_access(organizations)
        
        # Final summary
        print_header("FINAL RESULTS")
        
        if status_passed and counts_passed and access_passed:
            print_success("ALL TESTS PASSED!")
            print_success("Feature system is working correctly!")
        else:
            print_error("SOME TESTS FAILED!")
            print_warning("Review the errors above for details.")
        
        print_info("\nTest data has been created and can be inspected in Django admin:")
        for tariff_key, org_data in organizations.items():
            print(f"  - {org_data['organization'].name} ({org_data['user'].email})")
        
        print_warning("\nTo clean up test data, run the cleanup function or delete manually from admin.")
        
    except Exception as e:
        print_error(f"Error during testing: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()

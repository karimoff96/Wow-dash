#!/usr/bin/env python
"""
Comprehensive Tariff Permissions Testing Script

This script tests various scenarios to ensure tariff-based permissions
are functioning correctly across different subscription types and limits.

Run with: python manage.py shell < test_tariff_permissions.py
Or: python test_tariff_permissions.py (if Django settings are configured)
"""

import os
import django
import sys
from datetime import date, timedelta
from decimal import Decimal

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'WowDash.settings')
django.setup()

from django.contrib.auth.models import User
from billing.models import Feature, Tariff, TariffPricing, Subscription
from organizations.models import TranslationCenter, Branch, AdminUser
from orders.models import Order

# ANSI color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text):
    """Print section header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(80)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.END}\n")

def print_success(text):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")

def print_error(text):
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.END}")

def print_info(text):
    """Print info message"""
    print(f"{Colors.CYAN}ℹ {text}{Colors.END}")

def print_warning(text):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")

def test_result(condition, success_msg, error_msg):
    """Print test result based on condition"""
    if condition:
        print_success(success_msg)
        return True
    else:
        print_error(error_msg)
        return False

# ============================================================================
# Test Data Setup
# ============================================================================

def cleanup_test_data():
    """Clean up any existing test data"""
    print_info("Cleaning up existing test data...")
    
    # Delete test centers
    TranslationCenter.objects.filter(name__startswith="TEST_").delete()
    
    # Delete test users
    User.objects.filter(username__startswith="test_owner_").delete()
    
    # Delete test tariffs
    Tariff.objects.filter(slug__startswith="test-").delete()
    
    # Delete test features
    Feature.objects.filter(code__startswith="TEST_").delete()
    
    print_success("Cleanup completed")

def create_test_features():
    """Create test features"""
    print_info("Creating test features...")
    
    features = [
        Feature.objects.get_or_create(
            code='TEST_ADVANCED_REPORTS',
            defaults={
                'name': 'Advanced Reports',
                'description': 'Access to advanced reporting and analytics',
                'category': 'reporting',
                'is_active': True
            }
        )[0],
        Feature.objects.get_or_create(
            code='TEST_API_ACCESS',
            defaults={
                'name': 'API Access',
                'description': 'REST API access for integrations',
                'category': 'integration',
                'is_active': True
            }
        )[0],
        Feature.objects.get_or_create(
            code='TEST_PRIORITY_SUPPORT',
            defaults={
                'name': 'Priority Support',
                'description': '24/7 priority customer support',
                'category': 'support',
                'is_active': True
            }
        )[0],
        Feature.objects.get_or_create(
            code='TEST_CUSTOM_BRANDING',
            defaults={
                'name': 'Custom Branding',
                'description': 'Custom logo and branding options',
                'category': 'customization',
                'is_active': True
            }
        )[0],
    ]
    
    print_success(f"Created {len(features)} test features")
    return features

def create_test_tariffs(features):
    """Create test tariffs with different limits"""
    print_info("Creating test tariffs...")
    
    tariffs = {}
    
    # 1. Free Trial Tariff
    tariffs['trial'] = Tariff.objects.create(
        title='TEST Free Trial',
        slug='test-free-trial',
        description='10-day free trial with limited features',
        is_active=True,
        is_trial=True,
        trial_days=10,
        max_branches=2,
        max_staff=3,
        max_monthly_orders=50,
    )
    # Create $0 pricing for trial
    TariffPricing.objects.create(
        tariff=tariffs['trial'],
        duration_months=1,
        price=Decimal('0.00'),
        currency='UZS',
        is_active=True
    )
    print_success(f"Created trial tariff: {tariffs['trial'].title}")
    
    # 2. Starter Tariff (Small Business)
    tariffs['starter'] = Tariff.objects.create(
        title='TEST Starter Plan',
        slug='test-starter',
        description='Perfect for small translation centers',
        is_active=True,
        max_branches=3,
        max_staff=5,
        max_monthly_orders=100,
    )
    tariffs['starter'].features.add(features[0])  # Advanced Reports
    
    # Create pricing
    TariffPricing.objects.create(
        tariff=tariffs['starter'],
        duration_months=1,
        price=Decimal('50000.00'),
        currency='UZS',
        is_active=True
    )
    print_success(f"Created starter tariff: {tariffs['starter'].title}")
    
    # 3. Professional Tariff (Medium Business)
    tariffs['professional'] = Tariff.objects.create(
        title='TEST Professional Plan',
        slug='test-professional',
        description='For growing translation businesses',
        is_active=True,
        max_branches=10,
        max_staff=20,
        max_monthly_orders=500,
    )
    tariffs['professional'].features.add(features[0], features[1], features[2])  # Reports, API, Support
    
    TariffPricing.objects.create(
        tariff=tariffs['professional'],
        duration_months=1,
        price=Decimal('150000.00'),
        currency='UZS',
        is_active=True
    )
    print_success(f"Created professional tariff: {tariffs['professional'].title}")
    
    # 4. Enterprise Tariff (Unlimited)
    tariffs['enterprise'] = Tariff.objects.create(
        title='TEST Enterprise Plan',
        slug='test-enterprise',
        description='Unlimited resources for large enterprises',
        is_active=True,
        is_featured=True,
        max_branches=None,  # Unlimited
        max_staff=None,     # Unlimited
        max_monthly_orders=None,  # Unlimited
    )
    tariffs['enterprise'].features.set(features)  # All features
    
    TariffPricing.objects.create(
        tariff=tariffs['enterprise'],
        duration_months=1,
        price=Decimal('500000.00'),
        currency='UZS',
        is_active=True
    )
    print_success(f"Created enterprise tariff: {tariffs['enterprise'].title}")
    
    # 5. Restricted Tariff (Very Limited)
    tariffs['restricted'] = Tariff.objects.create(
        title='TEST Restricted Plan',
        slug='test-restricted',
        description='Very limited plan for testing',
        is_active=True,
        max_branches=1,
        max_staff=1,
        max_monthly_orders=10,
    )
    
    TariffPricing.objects.create(
        tariff=tariffs['restricted'],
        duration_months=1,
        price=Decimal('20000.00'),
        currency='UZS',
        is_active=True
    )
    print_success(f"Created restricted tariff: {tariffs['restricted'].title}")
    
    return tariffs

def create_test_centers(tariffs):
    """Create test centers with different tariffs"""
    print_info("Creating test centers and subscriptions...")
    
    centers = {}
    
    # Create test owners
    owners = {}
    for plan_name in ['trial', 'starter', 'professional', 'enterprise', 'restricted', 'no_subscription']:
        username = f'test_owner_{plan_name}'
        owners[plan_name] = User.objects.create_user(
            username=username,
            email=f'{username}@test.com',
            password='testpass123'
        )
    
    # 1. Trial Center
    centers['trial'] = TranslationCenter.objects.create(
        name='TEST Trial Center',
        subdomain='test-trial-center',
        owner=owners['trial'],
        is_active=True
    )
    
    # Create active trial subscription (trial needs pricing even if $0)
    trial_pricing = tariffs['trial'].pricing.first()
    Subscription.objects.create(
        organization=centers['trial'],
        tariff=tariffs['trial'],
        pricing=trial_pricing,
        start_date=date.today(),
        status=Subscription.STATUS_ACTIVE,
    )
    print_success(f"Created trial center with active subscription")
    
    # 2. Starter Center (Active)
    centers['starter'] = TranslationCenter.objects.create(
        name='TEST Starter Center',
        subdomain='test-starter-center',
        owner=owners['starter'],
        is_active=True
    )
    
    starter_pricing = tariffs['starter'].pricing.first()
    Subscription.objects.create(
        organization=centers['starter'],
        tariff=tariffs['starter'],
        pricing=starter_pricing,
        start_date=date.today(),
        status=Subscription.STATUS_ACTIVE,
        amount_paid=starter_pricing.price,
        payment_date=date.today(),
    )
    print_success(f"Created starter center with active subscription")
    
    # 3. Professional Center (Active)
    centers['professional'] = TranslationCenter.objects.create(
        name='TEST Professional Center',
        subdomain='test-prof-center',
        owner=owners['professional'],
        is_active=True
    )
    
    prof_pricing = tariffs['professional'].pricing.first()
    Subscription.objects.create(
        organization=centers['professional'],
        tariff=tariffs['professional'],
        pricing=prof_pricing,
        start_date=date.today(),
        status=Subscription.STATUS_ACTIVE,
        amount_paid=prof_pricing.price,
        payment_date=date.today(),
    )
    print_success(f"Created professional center with active subscription")
    
    # 4. Enterprise Center (Active)
    centers['enterprise'] = TranslationCenter.objects.create(
        name='TEST Enterprise Center',
        subdomain='test-enterprise-center',
        owner=owners['enterprise'],
        is_active=True
    )
    
    ent_pricing = tariffs['enterprise'].pricing.first()
    Subscription.objects.create(
        organization=centers['enterprise'],
        tariff=tariffs['enterprise'],
        pricing=ent_pricing,
        start_date=date.today(),
        status=Subscription.STATUS_ACTIVE,
        amount_paid=ent_pricing.price,
        payment_date=date.today(),
    )
    print_success(f"Created enterprise center with active subscription")
    
    # 5. Restricted Center (Active)
    centers['restricted'] = TranslationCenter.objects.create(
        name='TEST Restricted Center',
        subdomain='test-restricted-center',
        owner=owners['restricted'],
        is_active=True
    )
    
    rest_pricing = tariffs['restricted'].pricing.first()
    Subscription.objects.create(
        organization=centers['restricted'],
        tariff=tariffs['restricted'],
        pricing=rest_pricing,
        start_date=date.today(),
        status=Subscription.STATUS_ACTIVE,
        amount_paid=rest_pricing.price,
        payment_date=date.today(),
    )
    print_success(f"Created restricted center with active subscription")
    
    # 6. Expired Subscription Center
    centers['expired'] = TranslationCenter.objects.create(
        name='TEST Expired Center',
        subdomain='test-expired-center',
        owner=owners['starter'],
        is_active=True
    )
    
    Subscription.objects.create(
        organization=centers['expired'],
        tariff=tariffs['starter'],
        pricing=starter_pricing,
        start_date=date.today() - timedelta(days=60),
        end_date=date.today() - timedelta(days=1),
        status=Subscription.STATUS_EXPIRED,
    )
    print_success(f"Created center with expired subscription")
    
    # 7. No Subscription Center
    centers['no_subscription'] = TranslationCenter.objects.create(
        name='TEST No Subscription Center',
        subdomain='test-no-sub-center',
        owner=owners['no_subscription'],
        is_active=True
    )
    print_success(f"Created center with no subscription")
    
    return centers

# ============================================================================
# Test Cases
# ============================================================================

def test_subscription_status(centers):
    """Test 1: Verify subscription status checks"""
    print_header("TEST 1: Subscription Status Verification")
    
    results = []
    
    # Test active subscriptions
    for plan_name in ['trial', 'starter', 'professional', 'enterprise', 'restricted']:
        center = centers[plan_name]
        is_active = center.has_active_subscription()
        results.append(test_result(
            is_active,
            f"{center.name}: Subscription is active ✓",
            f"{center.name}: Subscription should be active but isn't"
        ))
    
    # Test expired subscription
    center = centers['expired']
    is_active = center.has_active_subscription()
    results.append(test_result(
        not is_active,
        f"{center.name}: Correctly identified as expired ✓",
        f"{center.name}: Should be expired but shows as active"
    ))
    
    # Test no subscription
    center = centers['no_subscription']
    has_sub = hasattr(center, 'subscription')
    results.append(test_result(
        not has_sub,
        f"{center.name}: Correctly has no subscription ✓",
        f"{center.name}: Shouldn't have subscription"
    ))
    
    passed = sum(results)
    total = len(results)
    print(f"\n{Colors.BOLD}Test 1 Results: {passed}/{total} passed{Colors.END}")
    return passed, total

def test_branch_limits(centers):
    """Test 2: Branch creation limits"""
    print_header("TEST 2: Branch Limit Enforcement")
    
    results = []
    
    # Test restricted plan (max 1 branch, already has main branch)
    center = centers['restricted']
    sub = center.subscription
    current_branches = center.branches.count()
    can_add = sub.can_add_branch()
    
    results.append(test_result(
        current_branches == 1 and not can_add,
        f"Restricted Plan: Has {current_branches} branch, correctly blocked from adding more ✓",
        f"Restricted Plan: Should block branch creation at limit"
    ))
    
    # Test starter plan (max 3 branches)
    center = centers['starter']
    sub = center.subscription
    current_branches = center.branches.count()
    can_add = sub.can_add_branch()
    
    results.append(test_result(
        current_branches == 1 and can_add,
        f"Starter Plan: Has {current_branches} branch, can add more (limit: 3) ✓",
        f"Starter Plan: Should allow more branches"
    ))
    
    # Add branches to test limit
    for i in range(2):
        Branch.objects.create(
            center=center,
            name=f"Test Branch {i+2}",
            is_main=False
        )
    
    current_branches = center.branches.count()
    can_add = sub.can_add_branch()
    
    results.append(test_result(
        current_branches == 3 and not can_add,
        f"Starter Plan: Now has {current_branches} branches, correctly at limit ✓",
        f"Starter Plan: Should be at branch limit"
    ))
    
    # Test enterprise plan (unlimited branches)
    center = centers['enterprise']
    sub = center.subscription
    can_add = sub.can_add_branch()
    
    results.append(test_result(
        can_add,
        f"Enterprise Plan: Unlimited branches, can add more ✓",
        f"Enterprise Plan: Should allow unlimited branches"
    ))
    
    # Add multiple branches to enterprise
    for i in range(15):
        Branch.objects.create(
            center=center,
            name=f"Enterprise Branch {i+2}",
            is_main=False
        )
    
    current_branches = center.branches.count()
    can_add = sub.can_add_branch()
    
    results.append(test_result(
        current_branches >= 15 and can_add,
        f"Enterprise Plan: Has {current_branches} branches, still can add more (unlimited) ✓",
        f"Enterprise Plan: Should allow unlimited branches"
    ))
    
    passed = sum(results)
    total = len(results)
    print(f"\n{Colors.BOLD}Test 2 Results: {passed}/{total} passed{Colors.END}")
    return passed, total

def test_feature_access(centers, tariffs):
    """Test 3: Feature-based access control"""
    print_header("TEST 3: Feature Access Control")
    
    results = []
    
    # Get test features
    api_feature = Feature.objects.get(code='TEST_API_ACCESS')
    reports_feature = Feature.objects.get(code='TEST_ADVANCED_REPORTS')
    support_feature = Feature.objects.get(code='TEST_PRIORITY_SUPPORT')
    branding_feature = Feature.objects.get(code='TEST_CUSTOM_BRANDING')
    
    # Test trial plan (no features)
    center = centers['trial']
    tariff = center.subscription.tariff
    
    results.append(test_result(
        not tariff.has_feature('TEST_API_ACCESS'),
        f"Trial Plan: Correctly doesn't have API Access ✓",
        f"Trial Plan: Shouldn't have API Access"
    ))
    
    # Test starter plan (only reports feature)
    center = centers['starter']
    tariff = center.subscription.tariff
    
    results.append(test_result(
        tariff.has_feature('TEST_ADVANCED_REPORTS'),
        f"Starter Plan: Has Advanced Reports feature ✓",
        f"Starter Plan: Should have Advanced Reports"
    ))
    
    results.append(test_result(
        not tariff.has_feature('TEST_API_ACCESS'),
        f"Starter Plan: Correctly doesn't have API Access ✓",
        f"Starter Plan: Shouldn't have API Access"
    ))
    
    # Test professional plan (reports, API, support)
    center = centers['professional']
    tariff = center.subscription.tariff
    
    results.append(test_result(
        tariff.has_feature('TEST_ADVANCED_REPORTS'),
        f"Professional Plan: Has Advanced Reports ✓",
        f"Professional Plan: Should have Advanced Reports"
    ))
    
    results.append(test_result(
        tariff.has_feature('TEST_API_ACCESS'),
        f"Professional Plan: Has API Access ✓",
        f"Professional Plan: Should have API Access"
    ))
    
    results.append(test_result(
        tariff.has_feature('TEST_PRIORITY_SUPPORT'),
        f"Professional Plan: Has Priority Support ✓",
        f"Professional Plan: Should have Priority Support"
    ))
    
    results.append(test_result(
        not tariff.has_feature('TEST_CUSTOM_BRANDING'),
        f"Professional Plan: Correctly doesn't have Custom Branding ✓",
        f"Professional Plan: Shouldn't have Custom Branding"
    ))
    
    # Test enterprise plan (all features)
    center = centers['enterprise']
    tariff = center.subscription.tariff
    
    all_features = [
        'TEST_ADVANCED_REPORTS',
        'TEST_API_ACCESS',
        'TEST_PRIORITY_SUPPORT',
        'TEST_CUSTOM_BRANDING'
    ]
    
    for feature_code in all_features:
        has_feature = tariff.has_feature(feature_code)
        results.append(test_result(
            has_feature,
            f"Enterprise Plan: Has {feature_code} ✓",
            f"Enterprise Plan: Should have {feature_code}"
        ))
    
    passed = sum(results)
    total = len(results)
    print(f"\n{Colors.BOLD}Test 3 Results: {passed}/{total} passed{Colors.END}")
    return passed, total

def test_usage_percentage(centers):
    """Test 4: Usage percentage calculations"""
    print_header("TEST 4: Usage Percentage Calculations")
    
    results = []
    
    # Test restricted plan at branch limit
    center = centers['restricted']
    sub = center.subscription
    branch_usage = sub.get_usage_percentage('branches')
    
    results.append(test_result(
        branch_usage == 100,
        f"Restricted Plan: Branch usage at 100% (1/1) ✓",
        f"Restricted Plan: Branch usage should be 100%, got {branch_usage}%"
    ))
    
    # Test starter plan with 3 branches (at limit)
    center = centers['starter']
    sub = center.subscription
    branch_usage = sub.get_usage_percentage('branches')
    
    results.append(test_result(
        branch_usage == 100,
        f"Starter Plan: Branch usage at 100% (3/3) ✓",
        f"Starter Plan: Branch usage should be 100%, got {branch_usage}%"
    ))
    
    # Test professional plan (under limit)
    center = centers['professional']
    sub = center.subscription
    branch_usage = sub.get_usage_percentage('branches')
    
    results.append(test_result(
        branch_usage == 10,  # 1 out of 10
        f"Professional Plan: Branch usage at 10% (1/10) ✓",
        f"Professional Plan: Branch usage should be 10%, got {branch_usage}%"
    ))
    
    # Test enterprise plan (unlimited - should return 0%)
    center = centers['enterprise']
    sub = center.subscription
    branch_usage = sub.get_usage_percentage('branches')
    
    results.append(test_result(
        branch_usage == 0,  # Unlimited
        f"Enterprise Plan: Branch usage 0% (unlimited) ✓",
        f"Enterprise Plan: Unlimited should return 0%, got {branch_usage}%"
    ))
    
    passed = sum(results)
    total = len(results)
    print(f"\n{Colors.BOLD}Test 4 Results: {passed}/{total} passed{Colors.END}")
    return passed, total

def test_trial_conversion(centers, tariffs):
    """Test 5: Trial to paid conversion"""
    print_header("TEST 5: Trial to Paid Conversion")
    
    results = []
    
    # Get trial center
    center = centers['trial']
    trial_sub = center.subscription
    
    # Verify it's a trial
    results.append(test_result(
        trial_sub.is_trial,
        f"Subscription is correctly marked as trial ✓",
        f"Subscription should be trial"
    ))
    
    results.append(test_result(
        trial_sub.is_trial_active(),
        f"Trial is currently active ✓",
        f"Trial should be active"
    ))
    
    trial_days = trial_sub.trial_days_remaining()
    results.append(test_result(
        trial_days > 0,
        f"Trial has {trial_days} days remaining ✓",
        f"Trial should have days remaining"
    ))
    
    # Convert to starter plan
    starter_pricing = tariffs['starter'].pricing.first()
    conversion_success = trial_sub.convert_trial_to_paid(
        tariffs['starter'],
        starter_pricing
    )
    
    # Refresh from database
    trial_sub.refresh_from_db()
    
    results.append(test_result(
        conversion_success,
        f"Trial conversion completed successfully ✓",
        f"Trial conversion should succeed"
    ))
    
    results.append(test_result(
        not trial_sub.is_trial,
        f"After conversion: No longer marked as trial ✓",
        f"Should not be trial after conversion"
    ))
    
    results.append(test_result(
        trial_sub.tariff == tariffs['starter'],
        f"After conversion: Tariff is now Starter ✓",
        f"Tariff should be Starter after conversion"
    ))
    
    results.append(test_result(
        trial_sub.status == Subscription.STATUS_PENDING,
        f"After conversion: Status is Pending (awaiting payment) ✓",
        f"Status should be Pending after conversion"
    ))
    
    # Check history
    history = trial_sub.history.filter(action='trial_converted')
    results.append(test_result(
        history.exists(),
        f"Conversion recorded in subscription history ✓",
        f"Conversion should be in history"
    ))
    
    passed = sum(results)
    total = len(results)
    print(f"\n{Colors.BOLD}Test 5 Results: {passed}/{total} passed{Colors.END}")
    return passed, total

def test_subscription_days_remaining(centers):
    """Test 6: Days remaining calculations"""
    print_header("TEST 6: Days Remaining Calculations")
    
    results = []
    
    # Test active subscriptions
    center = centers['starter']
    sub = center.subscription
    days_remaining = sub.days_remaining()
    
    results.append(test_result(
        days_remaining == 30,  # Created today, 1-month duration
        f"Starter Plan: {days_remaining} days remaining (expected ~30) ✓",
        f"Starter Plan: Should have ~30 days remaining, got {days_remaining}"
    ))
    
    # Test expired subscription
    center = centers['expired']
    sub = center.subscription
    days_remaining = sub.days_remaining()
    
    results.append(test_result(
        days_remaining == 0,
        f"Expired Subscription: 0 days remaining ✓",
        f"Expired Subscription: Should have 0 days, got {days_remaining}"
    ))
    
    # Test trial days remaining
    center = centers['trial']
    sub = center.subscription
    
    # Note: This center was converted in previous test, so let's create new trial
    new_trial_center = TranslationCenter.objects.create(
        name='TEST New Trial Center',
        subdomain='test-new-trial',
        owner=center.owner,
        is_active=True
    )
    
    trial_tariff = Tariff.objects.get(slug='test-free-trial')
    trial_pricing = trial_tariff.pricing.first()
    new_trial_sub = Subscription.objects.create(
        organization=new_trial_center,
        tariff=trial_tariff,
        pricing=trial_pricing,
        start_date=date.today(),
        status=Subscription.STATUS_ACTIVE,
    )
    
    trial_days = new_trial_sub.trial_days_remaining()
    results.append(test_result(
        trial_days == 10,
        f"New Trial: {trial_days} trial days remaining ✓",
        f"New Trial: Should have 10 days, got {trial_days}"
    ))
    
    passed = sum(results)
    total = len(results)
    print(f"\n{Colors.BOLD}Test 6 Results: {passed}/{total} passed{Colors.END}")
    return passed, total

def test_expired_subscription_access(centers):
    """Test 7: Expired subscription should block access"""
    print_header("TEST 7: Expired Subscription Access Control")
    
    results = []
    
    center = centers['expired']
    sub = center.subscription
    
    # Verify subscription is expired
    results.append(test_result(
        not sub.is_active(),
        f"Subscription is correctly inactive/expired ✓",
        f"Subscription should be expired"
    ))
    
    # Try to add branch (should fail)
    can_add_branch = sub.can_add_branch()
    results.append(test_result(
        not can_add_branch,
        f"Expired subscription blocks branch creation ✓",
        f"Should not allow branch creation with expired subscription"
    ))
    
    # Try to add staff (should fail)
    can_add_staff = sub.can_add_staff()
    results.append(test_result(
        not can_add_staff,
        f"Expired subscription blocks staff addition ✓",
        f"Should not allow staff addition with expired subscription"
    ))
    
    # Try to create order (should fail)
    can_create_order = sub.can_create_order()
    results.append(test_result(
        not can_create_order,
        f"Expired subscription blocks order creation ✓",
        f"Should not allow order creation with expired subscription"
    ))
    
    passed = sum(results)
    total = len(results)
    print(f"\n{Colors.BOLD}Test 7 Results: {passed}/{total} passed{Colors.END}")
    return passed, total

# ============================================================================
# Main Test Runner
# ============================================================================

def run_all_tests():
    """Run all test scenarios"""
    print_header("TARIFF PERMISSIONS COMPREHENSIVE TEST SUITE")
    print_info(f"Test started at: {date.today()}")
    
    all_results = []
    
    try:
        # Setup
        cleanup_test_data()
        features = create_test_features()
        tariffs = create_test_tariffs(features)
        centers = create_test_centers(tariffs)
        
        # Run tests
        all_results.append(test_subscription_status(centers))
        all_results.append(test_branch_limits(centers))
        all_results.append(test_feature_access(centers, tariffs))
        all_results.append(test_usage_percentage(centers))
        all_results.append(test_trial_conversion(centers, tariffs))
        all_results.append(test_subscription_days_remaining(centers))
        all_results.append(test_expired_subscription_access(centers))
        
        # Summary
        print_header("TEST SUMMARY")
        
        total_passed = sum(result[0] for result in all_results)
        total_tests = sum(result[1] for result in all_results)
        success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
        
        print(f"\n{Colors.BOLD}Total Tests Run: {total_tests}{Colors.END}")
        print(f"{Colors.BOLD}Tests Passed: {Colors.GREEN}{total_passed}{Colors.END}")
        print(f"{Colors.BOLD}Tests Failed: {Colors.RED}{total_tests - total_passed}{Colors.END}")
        print(f"{Colors.BOLD}Success Rate: {Colors.CYAN}{success_rate:.1f}%{Colors.END}\n")
        
        if total_passed == total_tests:
            print_success("🎉 ALL TESTS PASSED! Tariff permissions are working correctly!")
        else:
            print_warning(f"⚠️  {total_tests - total_passed} test(s) failed. Please review the errors above.")
        
        # Cleanup option
        print(f"\n{Colors.YELLOW}Note: Test data has been created. To clean up, run:{Colors.END}")
        print(f"{Colors.CYAN}python manage.py shell -c \"from test_tariff_permissions import cleanup_test_data; cleanup_test_data()\"{Colors.END}\n")
        
    except Exception as e:
        print_error(f"Test suite failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    return total_passed == total_tests

if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)

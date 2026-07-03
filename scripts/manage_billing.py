#!/usr/bin/env python
"""
WowDash Billing Management Script
==================================

Consolidated script for all billing-related management tasks:
- Create tariff tiers with feature distribution
- Seed initial tariffs
- Create trial tariffs
- Populate usage tracking
- View feature matrix comparison

Usage:
    python scripts/manage_billing.py [command]

Commands:
    setup-tiers       Create all 5 tariff tiers with logical feature distribution
    seed-tariffs      Quick seed with basic tariffs (legacy)
    create-trial      Create trial tariff only
    populate-usage    Populate usage tracking for existing organizations
    view-matrix       Display feature comparison matrix
    setup-all         Run full setup (setup-tiers + populate-usage)
"""

import os
import sys
import django
from pathlib import Path

# Setup Django environment
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'WowDash.settings')
django.setup()

from billing.models import Tariff, TariffPricing, UsageTracking
from organizations.models import TranslationCenter
from decimal import Decimal
from datetime import date


# ============================================================================
# TARIFF TIER CREATION FUNCTIONS
# ============================================================================

def create_trial_tier():
    """Create FREE TRIAL tier - 14 days, basic features"""
    print("\n" + "="*80)
    print("📦 CREATING TRIAL TIER")
    print("="*80)
    
    tariff, created = Tariff.objects.update_or_create(
        slug='trial',
        defaults={
            'title': 'Бесплатный пробный период (Free Trial)',
            'description': 'Test all basic features free for 14 days. Perfect for evaluating the platform.',
            'is_active': True,
            'is_featured': False,
            'is_trial': True,
            'trial_days': 14,
            'display_order': 1,
            'max_branches': 1,
            'max_staff': 2,
            'max_monthly_orders': 50,
            
            # Essential features only (13/37)
            'feature_orders_basic': True,
            'feature_telegram_bot': True,
            'feature_analytics_basic': True,
            'feature_payment_management': True,
            'feature_products_basic': True,
        }
    )
    
    action = "Created" if created else "Updated"
    print(f"✅ {action}: {tariff.title}")
    print(f"   📊 Limits: {tariff.max_branches} branch, {tariff.max_staff} staff, {tariff.max_monthly_orders} orders/month")
    return tariff


def create_starter_tier():
    """Create STARTER tier - $49/month, solo operators"""
    print("\n" + "="*80)
    print("🌱 CREATING STARTER TIER")
    print("="*80)
    
    tariff, created = Tariff.objects.update_or_create(
        slug='starter',
        defaults={
            'title': 'Стартовый (Starter)',
            'description': 'Perfect for solo translators and small offices. Essential features to manage your translation business.',
            'is_active': True,
            'is_featured': False,
            'is_trial': False,
            'display_order': 2,
            'max_branches': 1,
            'max_staff': 3,
            'max_monthly_orders': 200,
            
            # Trial features + Growth tools (20/37)
            'feature_orders_basic': True,
            'feature_order_assignment': True,
            'feature_analytics_basic': True,
            'feature_export_reports': True,
            'feature_telegram_bot': True,
            'feature_webhooks': True,
            'feature_marketing_basic': True,
            'feature_archive_access': True,
            'feature_payment_management': True,
            'feature_invoicing': True,
            'feature_products_basic': True,
            'feature_language_pricing': True,
            'feature_dynamic_pricing': True,
        }
    )
    
    # Pricing
    for duration, price, discount in [(1, 49000, 0), (3, 132300, 10), (6, 252000, 15), (12, 470400, 20)]:
        TariffPricing.objects.update_or_create(
            tariff=tariff, duration_months=duration, currency='UZS',
            defaults={'price': Decimal(str(price)), 'discount_percentage': Decimal(str(discount)), 'is_active': True}
        )
    
    action = "Created" if created else "Updated"
    print(f"✅ {action}: {tariff.title} - 49,000 UZS/month")
    return tariff


def create_professional_tier():
    """Create PROFESSIONAL tier - $149/month, growing agencies (MOST POPULAR)"""
    print("\n" + "="*80)
    print("💼 CREATING PROFESSIONAL TIER (MOST POPULAR)")
    print("="*80)
    
    tariff, created = Tariff.objects.update_or_create(
        slug='professional',
        defaults={
            'title': 'Профессиональный (Professional)',
            'description': 'Advanced features for growing translation agencies. Multi-branch support, advanced analytics, and automation.',
            'is_active': True,
            'is_featured': True,
            'is_trial': False,
            'display_order': 3,
            'max_branches': 5,
            'max_staff': 15,
            'max_monthly_orders': 1000,
            
            # Starter + Scale features (29/37)
            'feature_orders_basic': True,
            'feature_orders_advanced': True,
            'feature_order_assignment': True,
            'feature_bulk_payments': True,
            'feature_extra_fees': True,
            'feature_analytics_basic': True,
            'feature_analytics_advanced': True,
            'feature_financial_reports': True,
            'feature_staff_performance': True,
            'feature_export_reports': True,
            'feature_debt_tracking': True,
            'feature_telegram_bot': True,
            'feature_webhooks': True,
            'feature_marketing_basic': True,
            'feature_broadcast_messages': True,
            'feature_multi_branch': True,
            'feature_custom_roles': True,
            'feature_branch_settings': True,
            'feature_agency_management': True,
            'feature_archive_access': True,
            'feature_payment_management': True,
            'feature_invoicing': True,
            'feature_expense_tracking': True,
            'feature_general_expenses': True,
            'feature_products_basic': True,
            'feature_products_advanced': True,
            'feature_language_pricing': True,
            'feature_dynamic_pricing': True,
        }
    )
    
    # Pricing
    for duration, price, discount in [(1, 149000, 0), (3, 402300, 10), (6, 756000, 15), (12, 1430400, 20)]:
        TariffPricing.objects.update_or_create(
            tariff=tariff, duration_months=duration, currency='UZS',
            defaults={'price': Decimal(str(price)), 'discount_percentage': Decimal(str(discount)), 'is_active': True}
        )
    
    action = "Created" if created else "Updated"
    print(f"✅ {action}: {tariff.title} - 149,000 UZS/month")
    return tariff


def create_business_tier():
    """Create BUSINESS tier - $349/month, established companies"""
    print("\n" + "="*80)
    print("🏢 CREATING BUSINESS TIER")
    print("="*80)
    
    tariff, created = Tariff.objects.update_or_create(
        slug='business',
        defaults={
            'title': 'Бизнес (Business)',
            'description': 'Enterprise-grade features for established translation companies. Advanced security, audit logs, and unlimited capacity.',
            'is_active': True,
            'is_featured': False,
            'is_trial': False,
            'display_order': 4,
            'max_branches': 20,
            'max_staff': 50,
            'max_monthly_orders': 5000,
            
            # Professional + Enterprise-lite (35/37)
            'feature_orders_basic': True,
            'feature_orders_advanced': True,
            'feature_order_assignment': True,
            'feature_bulk_payments': True,
            'feature_extra_fees': True,
            'feature_analytics_basic': True,
            'feature_analytics_advanced': True,
            'feature_financial_reports': True,
            'feature_staff_performance': True,
            'feature_custom_reports': True,
            'feature_export_reports': True,
            'feature_debt_tracking': True,
            'feature_telegram_bot': True,
            'feature_webhooks': True,
            'feature_integrations': True,
            'feature_marketing_basic': True,
            'feature_broadcast_messages': True,
            'feature_multi_branch': True,
            'feature_custom_roles': True,
            'feature_branch_settings': True,
            'feature_agency_management': True,
            'feature_archive_access': True,
            'feature_payment_management': True,
            'feature_invoicing': True,
            'feature_expense_tracking': True,
            'feature_general_expenses': True,
            'feature_audit_logs': True,
            'feature_products_basic': True,
            'feature_products_advanced': True,
            'feature_language_pricing': True,
            'feature_dynamic_pricing': True,
        }
    )
    
    # Pricing
    for duration, price, discount in [(1, 349000, 0), (3, 941100, 10), (6, 1777200, 15), (12, 3348000, 20)]:
        TariffPricing.objects.update_or_create(
            tariff=tariff, duration_months=duration, currency='UZS',
            defaults={'price': Decimal(str(price)), 'discount_percentage': Decimal(str(discount)), 'is_active': True}
        )
    
    action = "Created" if created else "Updated"
    print(f"✅ {action}: {tariff.title} - 349,000 UZS/month")
    return tariff


def create_enterprise_tier():
    """Create ENTERPRISE tier - Custom pricing, unlimited everything"""
    print("\n" + "="*80)
    print("🏛️ CREATING ENTERPRISE TIER")
    print("="*80)
    
    tariff, created = Tariff.objects.update_or_create(
        slug='enterprise',
        defaults={
            'title': 'Корпоративный (Enterprise)',
            'description': 'Unlimited capacity with all premium features. API access, custom integrations, dedicated support, and SLA guarantees.',
            'is_active': True,
            'is_featured': False,
            'is_trial': False,
            'display_order': 5,
            'max_branches': None,
            'max_staff': None,
            'max_monthly_orders': None,
            
            # ALL FEATURES (32/32)
            'feature_orders_basic': True,
            'feature_orders_advanced': True,
            'feature_order_assignment': True,
            'feature_bulk_payments': True,
            'feature_extra_fees': True,
            'feature_analytics_basic': True,
            'feature_analytics_advanced': True,
            'feature_financial_reports': True,
            'feature_staff_performance': True,
            'feature_custom_reports': True,
            'feature_export_reports': True,
            'feature_debt_tracking': True,
            'feature_api_access': True,  # Enterprise exclusive
            'feature_telegram_bot': True,
            'feature_webhooks': True,
            'feature_integrations': True,
            'feature_marketing_basic': True,
            'feature_broadcast_messages': True,
            'feature_multi_branch': True,
            'feature_custom_roles': True,
            'feature_branch_settings': True,
            'feature_agency_management': True,
            'feature_archive_access': True,
            'feature_payment_management': True,
            'feature_invoicing': True,
            'feature_expense_tracking': True,
            'feature_general_expenses': True,
            'feature_audit_logs': True,
            'feature_products_basic': True,
            'feature_products_advanced': True,
            'feature_language_pricing': True,
            'feature_dynamic_pricing': True,
        }
    )
    
    # Pricing (Annual only)
    TariffPricing.objects.update_or_create(
        tariff=tariff, duration_months=12, currency='UZS',
        defaults={'price': Decimal('11880000'), 'discount_percentage': Decimal('0'), 'is_active': True}
    )
    
    action = "Created" if created else "Updated"
    print(f"✅ {action}: {tariff.title} - Contact for custom pricing")
    return tariff


def setup_tiers():
    """Create all tariff tiers"""
    print("\n" + "="*80)
    print("🚀 SETTING UP ALL TARIFF TIERS")
    print("="*80)
    
    create_trial_tier()
    create_starter_tier()
    create_professional_tier()
    create_business_tier()
    create_enterprise_tier()
    
    print("\n" + "="*80)
    print("✅ All tariff tiers created successfully!")
    print("="*80)


# ============================================================================
# USAGE TRACKING FUNCTIONS
# ============================================================================

def populate_usage_tracking():
    """Populate usage tracking for existing organizations"""
    print("\n" + "="*80)
    print("📊 POPULATING USAGE TRACKING")
    print("="*80)
    
    centers = TranslationCenter.objects.all()
    today = date.today()
    created_count = 0
    
    for center in centers:
        tracking, created = UsageTracking.objects.get_or_create(
            organization=center,
            year=today.year,
            month=today.month,
            defaults={
                'branches_count': center.branches.count(),
                'staff_count': center.get_staff_count() if hasattr(center, 'get_staff_count') else 0,
                'orders_created': 0,
                'total_revenue': Decimal('0'),
            }
        )
        
        if created:
            created_count += 1
            print(f"  ✅ Created tracking for: {center.name}")
    
    print(f"\n✅ Created {created_count} new usage tracking records")


# ============================================================================
# FEATURE MATRIX VIEWER
# ============================================================================

def view_matrix():
    """Display feature comparison matrix"""
    from textwrap import wrap
    
    print("\n" + "="*100)
    print("📊 TARIFF FEATURE COMPARISON MATRIX")
    print("="*100)
    
    tiers = ['trial', 'starter', 'professional', 'business', 'enterprise']
    tariffs = {}
    
    for slug in tiers:
        try:
            tariffs[slug] = Tariff.objects.get(slug=slug)
        except Tariff.DoesNotExist:
            print(f"❌ Tariff '{slug}' not found. Run 'setup-tiers' first.")
            return
    
    # Header
    print(f"\n{'TIER':<25} {'Trial':<12} {'Starter':<12} {'Pro':<12} {'Business':<12} {'Enterprise':<12}")
    print("-"*100)
    
    # Pricing
    print(f"{'Monthly Cost':<25} {'FREE':<12} {'$49':<12} {'$149':<12} {'$349':<12} {'Custom':<12}")
    
    # Limits
    print(f"\n{'CAPACITY LIMITS':<25}")
    print("-"*100)
    for attr, label in [('max_branches', 'Max Branches'), ('max_staff', 'Max Staff'), ('max_monthly_orders', 'Monthly Orders')]:
        print(f"{label:<25}", end="")
        for slug in tiers:
            value = getattr(tariffs[slug], attr)
            display = '∞' if value is None else str(value)
            print(f"{display:<12}", end="")
        print()
    
    # Features by category
    feature_categories = {
        'Orders': ['orders_basic', 'orders_advanced', 'order_assignment', 'bulk_payments', 'order_templates'],
        'Analytics': ['analytics_basic', 'analytics_advanced', 'financial_reports', 'staff_performance', 'custom_reports', 'export_reports', 'debt_tracking'],
        'Integration': ['telegram_bot', 'webhooks', 'api_access', 'integrations'],
        'Marketing': ['marketing_basic', 'broadcast_messages'],
        'Organization': ['multi_branch', 'custom_roles', 'staff_scheduling', 'branch_settings'],
        'Storage': ['archive_access', 'cloud_backup', 'extended_storage'],
        'Financial': ['multi_currency', 'payment_management', 'invoicing', 'expense_tracking', 'general_expenses'],
        'Support': ['support_tickets', 'knowledge_base'],
        'Advanced': ['advanced_security', 'audit_logs', 'data_retention'],
        'Services': ['products_basic', 'products_advanced', 'language_pricing', 'dynamic_pricing'],
    }
    
    print(f"\n{'FEATURES':<25}")
    print("="*100)
    
    for category, features in feature_categories.items():
        print(f"\n{category.upper()}")
        for feature in features:
            feature_name = feature.replace('_', ' ').title()[:24]
            print(f"  {feature_name:<23}", end="")
            for slug in tiers:
                has_feature = getattr(tariffs[slug], f'feature_{feature}', False)
                symbol = '✅' if has_feature else '❌'
                print(f"{symbol:<12}", end="")
            print()
    
    # Summary
    print("\n" + "="*100)
    print(f"{'TOTAL FEATURES':<25}", end="")
    for slug in tiers:
        count = sum(1 for f in dir(tariffs[slug]) if f.startswith('feature_') and getattr(tariffs[slug], f))
        print(f"{count}/37{'':<7}", end="")
    print()
    print("="*100)


# ============================================================================
# MAIN COMMAND HANDLER
# ============================================================================

def main():
    """Main command handler"""
    commands = {
        'setup-tiers': setup_tiers,
        'seed-tariffs': setup_tiers,  # Alias
        'create-trial': create_trial_tier,
        'populate-usage': populate_usage_tracking,
        'view-matrix': view_matrix,
        'setup-all': lambda: (setup_tiers(), populate_usage_tracking()),
    }
    
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nAvailable commands:")
        for cmd in commands.keys():
            print(f"  - {cmd}")
        return 1
    
    command = sys.argv[1]
    
    if command not in commands:
        print(f"❌ Unknown command: {command}")
        print(f"\nAvailable commands: {', '.join(commands.keys())}")
        return 1
    
    try:
        commands[command]()
        print("\n✅ Command completed successfully!")
        return 0
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())

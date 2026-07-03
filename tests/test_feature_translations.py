"""Test feature translations"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'WowDash.settings')
django.setup()

from django.utils.translation import activate, gettext
from billing.models import Tariff

# Test features for each language
languages = {
    'ru': 'Russian',
    'uz': 'Uzbek', 
    'en': 'English'
}

# ALL feature slugs from the model
test_features = [
    'Order Assignment',
    'Bulk Payments',
    'Order Templates',
    'Financial Reports',
    'Staff Performance',
    'Export Reports',
    'Basic Marketing',
    'Broadcast Messages',
    'Custom Roles',
    'Staff Scheduling',
    'Branch Settings',
    'Archive Access',
    'Cloud Backup',
    'Extended Storage',
    'Multi-Currency',
    'Payment Management',
    'Expense Tracking',
    'Support Tickets',
    'Knowledge Base',
    'Data Retention',
    'Basic Products',
    'Advanced Products',
    'Language Pricing',
    'Dynamic Pricing',
]

print("=" * 80)
print("TESTING NEW FEATURE TRANSLATIONS")
print("=" * 80)

for lang_code, lang_name in languages.items():
    print(f"\n{lang_name} ({lang_code.upper()}):")
    print("-" * 80)
    activate(lang_code)
    
    for feature in test_features:
        translated = gettext(feature)
        status = "✓" if translated != feature else "✗"
        print(f"  {status} {feature:30} -> {translated}")

print("\n" * 2)
print("=" * 80)
print("Testing with Tariff model method:")
print("=" * 80)

try:
    tariff = Tariff.objects.first()
    if tariff:
        test_slugs = [
            'order_assignment',
            'bulk_payments', 
            'order_templates',
            'financial_reports',
            'staff_performance',
            'export_reports',
            'broadcast_messages',
            'custom_roles',
            'staff_scheduling',
        ]
        
        for lang_code, lang_name in languages.items():
            print(f"\n{lang_name} ({lang_code.upper()}):")
            print("-" * 80)
            activate(lang_code)
            
            for slug in test_slugs:
                display_name = tariff.get_feature_display_name(slug)
                print(f"  {slug:30} -> {display_name}")
    else:
        print("No tariffs found in database")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 80)


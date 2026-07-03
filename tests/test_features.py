import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'WowDash.settings')
django.setup()

from billing.models import Tariff
import json

print("=" * 60)
print("TESTING FEATURE SYSTEM")
print("=" * 60)

for tariff in Tariff.objects.all():
    print(f"\n{tariff.title} ({tariff.slug})")
    print("-" * 60)
    print(f"Has 'marketing_basic': {tariff.has_feature('marketing_basic')}")
    print(f"Has 'api_access': {tariff.has_feature('api_access')}")
    print(f"Total enabled features: {tariff.get_feature_count()}/37")
    
    print("\nFeatures by category:")
    categories = tariff.get_features_by_category()
    for category, features in categories.items():
        enabled = [name for name, is_enabled in features.items() if is_enabled]
        if enabled:
            print(f"  • {category}: {len(enabled)} enabled")
            print(f"    {', '.join(enabled)}")

print("\n" + "=" * 60)
print("Testing Subscription feature access...")
print("=" * 60)

from billing.models import Subscription

# Get an active subscription
sub = Subscription.objects.filter(status='active').first()
if sub:
    print(f"\nOrganization: {sub.organization.name}")
    print(f"Tariff: {sub.tariff.title}")
    print(f"Has 'marketing_basic': {sub.has_feature('marketing_basic')}")
    print(f"Enabled features: {len(sub.get_features())}")
    print("\nFeatures by category:")
    sub_categories = sub.get_features_by_category()
    for category, features in sub_categories.items():
        enabled = [name for name, is_enabled in features.items() if is_enabled]
        if enabled:
            print(f"  • {category}: {len(enabled)} features")
else:
    print("\nNo active subscriptions found.")

print("\n" + "=" * 60)
print("✓ All tests completed!")
print("=" * 60)

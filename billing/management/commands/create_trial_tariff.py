from django.core.management.base import BaseCommand
from billing.models import Tariff, TariffPricing, Feature


class Command(BaseCommand):
    help = 'Create free trial tariff with 10-day trial period'

    def handle(self, *args, **options):
        # Create or get free trial tariff
        tariff, created = Tariff.objects.get_or_create(
            slug='free-trial',
            defaults={
                'title': 'Free Trial',
                'description': '10-day free trial to test all features',
                'is_active': True,
                'is_featured': False,
                'is_trial': True,
                'trial_days': 10,
                'display_order': -1,  # Show first
                'max_branches': 2,
                'max_staff': 5,
                'max_monthly_orders': 50,
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'✓ Created free trial tariff'))
            
            # Create a pricing entry (even though it's free, for consistency)
            pricing = TariffPricing.objects.create(
                tariff=tariff,
                duration_months=0,  # 0 months for trial
                base_price=0.00,
                discount_percentage=100.00,
                final_price=0.00,
                is_active=True
            )
            self.stdout.write(self.style.SUCCESS(f'✓ Created trial pricing entry'))
            
            # Add all basic features to trial
            basic_features = [
                'order_management',
                'staff_management',
                'branch_management',
                'basic_reporting',
                'telegram_bot',
            ]
            
            for feature_code in basic_features:
                try:
                    feature = Feature.objects.get(code=feature_code)
                    tariff.features.add(feature)
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Added feature: {feature.name}'))
                except Feature.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f'  ⚠ Feature not found: {feature_code}'))
            
            self.stdout.write(self.style.SUCCESS('\n✓ Free trial tariff created successfully!'))
            self.stdout.write(self.style.SUCCESS(f'  Trial Duration: {tariff.trial_days} days'))
            self.stdout.write(self.style.SUCCESS(f'  Max Branches: {tariff.max_branches}'))
            self.stdout.write(self.style.SUCCESS(f'  Max Staff: {tariff.max_staff}'))
            self.stdout.write(self.style.SUCCESS(f'  Max Monthly Orders: {tariff.max_monthly_orders}'))
        else:
            self.stdout.write(self.style.WARNING('Free trial tariff already exists'))

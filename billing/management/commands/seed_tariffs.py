from django.core.management.base import BaseCommand
from billing.models import Feature, Tariff, TariffPricing


class Command(BaseCommand):
    help = 'Seed initial tariffs, features, and pricing'

    def handle(self, *args, **options):
        self.stdout.write('Creating features...')
        
        # Define features
        features_data = [
            # Basic features (all plans)
            ('telegram_bot', 'Telegram Bot Integration', 'Integration', 'Telegram bot for order automation'),
            ('basic_reports', 'Basic Reports', 'Reports', 'Basic sales and financial reports'),
            ('excel_export', 'Excel Export', 'Export', 'Export data to Excel format'),
            ('order_management', 'Order Management', 'Core', 'Create and manage orders'),
            ('customer_management', 'Customer Management', 'Core', 'Manage customer database'),
            
            # Professional features
            ('advanced_analytics', 'Advanced Analytics', 'Analytics', 'Detailed analytics and insights'),
            ('marketing_tools', 'Marketing Tools', 'Marketing', 'Bulk messaging and campaigns'),
            ('auto_archiving', 'Automatic Archiving', 'Automation', 'Auto archive old orders to Telegram'),
            ('staff_performance', 'Staff Performance Tracking', 'Analytics', 'Track employee performance'),
            
            # Enterprise features
            ('api_access', 'API Access', 'Integration', 'REST API for custom integrations'),
            ('priority_support', '24/7 Priority Support', 'Support', 'Dedicated support channel'),
            ('custom_integration', 'Custom Integration', 'Integration', 'Custom integrations and development'),
            ('dedicated_manager', 'Dedicated Account Manager', 'Support', 'Personal account manager'),
        ]
        
        created_features = {}
        for code, name, category, description in features_data:
            feature, created = Feature.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'category': category,
                    'description': description,
                }
            )
            created_features[code] = feature
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✓ Created feature: {name}'))
            else:
                self.stdout.write(f'  - Feature already exists: {name}')
        
        # Create Starter Tariff
        self.stdout.write('\nCreating Starter tariff...')
        starter, created = Tariff.objects.get_or_create(
            slug='starter',
            defaults={
                'title': 'Starter',
                'description': 'Perfect for small translation centers just starting out',
                'is_active': True,
                'is_featured': False,
                'display_order': 1,
                'max_branches': 1,
                'max_staff': 3,
                'max_monthly_orders': 150,
            }
        )
        
        if created:
            # Add features to Starter
            starter.features.set([
                created_features['telegram_bot'],
                created_features['basic_reports'],
                created_features['excel_export'],
                created_features['order_management'],
                created_features['customer_management'],
            ])
            self.stdout.write(self.style.SUCCESS('  ✓ Created Starter tariff'))
            
            # Create pricing options for Starter
            TariffPricing.objects.create(
                tariff=starter,
                duration_months=1,
                price=299000,
                currency='UZS',
                discount_percentage=0
            )
            TariffPricing.objects.create(
                tariff=starter,
                duration_months=3,
                price=807300,  # 10% discount
                currency='UZS',
                discount_percentage=10
            )
            TariffPricing.objects.create(
                tariff=starter,
                duration_months=6,
                price=1553400,  # 13% discount
                currency='UZS',
                discount_percentage=13
            )
            TariffPricing.objects.create(
                tariff=starter,
                duration_months=12,
                price=2990000,  # 17% discount
                currency='UZS',
                discount_percentage=17
            )
            self.stdout.write(self.style.SUCCESS('  ✓ Created Starter pricing options'))
        else:
            self.stdout.write('  - Starter tariff already exists')
        
        # Create Professional Tariff
        self.stdout.write('\nCreating Professional tariff...')
        professional, created = Tariff.objects.get_or_create(
            slug='professional',
            defaults={
                'title': 'Professional',
                'description': 'For growing centers with multiple branches',
                'is_active': True,
                'is_featured': True,
                'display_order': 2,
                'max_branches': 3,
                'max_staff': 10,
                'max_monthly_orders': 500,
            }
        )
        
        if created:
            # Add features to Professional
            professional.features.set([
                created_features['telegram_bot'],
                created_features['basic_reports'],
                created_features['excel_export'],
                created_features['order_management'],
                created_features['customer_management'],
                created_features['advanced_analytics'],
                created_features['marketing_tools'],
                created_features['auto_archiving'],
                created_features['staff_performance'],
            ])
            self.stdout.write(self.style.SUCCESS('  ✓ Created Professional tariff'))
            
            # Create pricing options for Professional
            TariffPricing.objects.create(
                tariff=professional,
                duration_months=1,
                price=499000,
                currency='UZS',
                discount_percentage=0
            )
            TariffPricing.objects.create(
                tariff=professional,
                duration_months=3,
                price=1347300,  # 10% discount
                currency='UZS',
                discount_percentage=10
            )
            TariffPricing.objects.create(
                tariff=professional,
                duration_months=6,
                price=2594400,  # 13% discount
                currency='UZS',
                discount_percentage=13
            )
            TariffPricing.objects.create(
                tariff=professional,
                duration_months=12,
                price=4990800,  # 17% discount
                currency='UZS',
                discount_percentage=17
            )
            self.stdout.write(self.style.SUCCESS('  ✓ Created Professional pricing options'))
        else:
            self.stdout.write('  - Professional tariff already exists')
        
        # Create Enterprise Tariff
        self.stdout.write('\nCreating Enterprise tariff...')
        enterprise, created = Tariff.objects.get_or_create(
            slug='enterprise',
            defaults={
                'title': 'Enterprise',
                'description': 'Unlimited everything for large operations',
                'is_active': True,
                'is_featured': False,
                'display_order': 3,
                'max_branches': None,  # Unlimited
                'max_staff': None,  # Unlimited
                'max_monthly_orders': None,  # Unlimited
            }
        )
        
        if created:
            # Add all features to Enterprise
            enterprise.features.set(created_features.values())
            self.stdout.write(self.style.SUCCESS('  ✓ Created Enterprise tariff'))
            
            # Create pricing options for Enterprise
            TariffPricing.objects.create(
                tariff=enterprise,
                duration_months=1,
                price=1999000,
                currency='UZS',
                discount_percentage=0
            )
            TariffPricing.objects.create(
                tariff=enterprise,
                duration_months=3,
                price=5397300,  # 10% discount
                currency='UZS',
                discount_percentage=10
            )
            TariffPricing.objects.create(
                tariff=enterprise,
                duration_months=6,
                price=10394400,  # 13% discount
                currency='UZS',
                discount_percentage=13
            )
            TariffPricing.objects.create(
                tariff=enterprise,
                duration_months=12,
                price=19950200,  # 17% discount
                currency='UZS',
                discount_percentage=17
            )
            self.stdout.write(self.style.SUCCESS('  ✓ Created Enterprise pricing options'))
        else:
            self.stdout.write('  - Enterprise tariff already exists')
        
        self.stdout.write(self.style.SUCCESS('\n✓ Tariff seeding completed successfully!'))

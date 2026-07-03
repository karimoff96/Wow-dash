from django.core.management.base import BaseCommand
from django.db import transaction
from billing.models import Tariff


class Command(BaseCommand):
    help = 'Set default feature flags for all tariff plans'

    def handle(self, *args, **options):
        with transaction.atomic():
            self.stdout.write(self.style.WARNING('Setting default features for tariffs...'))
            
            # Starter - 12 features
            starter = Tariff.objects.filter(slug='starter').first()
            if starter:
                # Basic features
                starter.feature_orders_basic = True
                starter.feature_analytics_basic = True
                starter.feature_telegram_bot = True
                starter.feature_webhooks = True
                starter.feature_products_basic = True
                # Additional features
                starter.feature_order_assignment = True
                starter.feature_multi_branch = True
                starter.feature_payment_management = True
                starter.feature_language_pricing = True
                starter.feature_dynamic_pricing = True
                starter.feature_archive_access = True
                starter.save()
                self.stdout.write(self.style.SUCCESS(f'✓ Starter: {starter.get_feature_count()} features enabled'))
            
            # Professional/Pro - 24 features (Starter + 12 more)
            pro = Tariff.objects.filter(slug__in=['pro', 'professional']).first()
            if pro:
                # Starter features
                pro.feature_orders_basic = True
                pro.feature_analytics_basic = True
                pro.feature_telegram_bot = True
                pro.feature_webhooks = True
                pro.feature_products_basic = True
                pro.feature_order_assignment = True
                pro.feature_multi_branch = True
                pro.feature_payment_management = True
                pro.feature_language_pricing = True
                pro.feature_dynamic_pricing = True
                pro.feature_archive_access = True
                # Additional Pro features
                pro.feature_orders_advanced = True
                pro.feature_bulk_payments = True
                pro.feature_extra_fees = True
                pro.feature_analytics_advanced = True
                pro.feature_financial_reports = True
                pro.feature_staff_performance = True
                pro.feature_export_reports = True
                pro.feature_debt_tracking = True
                pro.feature_marketing_basic = True
                pro.feature_broadcast_messages = True
                pro.feature_custom_roles = True
                pro.feature_branch_settings = True
                pro.feature_agency_management = True
                pro.feature_invoicing = True
                pro.feature_expense_tracking = True
                pro.feature_general_expenses = True
                pro.feature_audit_logs = True
                pro.feature_products_advanced = True
                pro.save()
                self.stdout.write(self.style.SUCCESS(f'✓ {pro.title}: {pro.get_feature_count()} features enabled'))
            
            # Enterprise - All 33 features
            enterprise = Tariff.objects.filter(slug='enterprise').first()
            if enterprise:
                # All Order Management features (5)
                enterprise.feature_orders_basic = True
                enterprise.feature_orders_advanced = True
                enterprise.feature_order_assignment = True
                enterprise.feature_bulk_payments = True
                enterprise.feature_extra_fees = True
                # All Analytics features (7)
                enterprise.feature_analytics_basic = True
                enterprise.feature_analytics_advanced = True
                enterprise.feature_financial_reports = True
                enterprise.feature_staff_performance = True
                enterprise.feature_custom_reports = True
                enterprise.feature_export_reports = True
                enterprise.feature_debt_tracking = True
                # All Integration features (4)
                enterprise.feature_telegram_bot = True
                enterprise.feature_webhooks = True
                enterprise.feature_api_access = True
                enterprise.feature_integrations = True
                # All Marketing features (2)
                enterprise.feature_marketing_basic = True
                enterprise.feature_broadcast_messages = True
                # All Organization features (4)
                enterprise.feature_multi_branch = True
                enterprise.feature_custom_roles = True
                enterprise.feature_branch_settings = True
                enterprise.feature_agency_management = True
                # Storage (1)
                enterprise.feature_archive_access = True
                # All Financial features (4)
                enterprise.feature_payment_management = True
                enterprise.feature_invoicing = True
                enterprise.feature_expense_tracking = True
                enterprise.feature_general_expenses = True
                # Advanced (1)
                enterprise.feature_audit_logs = True
                # All Services features (4)
                enterprise.feature_products_basic = True
                enterprise.feature_products_advanced = True
                enterprise.feature_language_pricing = True
                enterprise.feature_dynamic_pricing = True
                enterprise.save()
                self.stdout.write(self.style.SUCCESS(f'✓ Enterprise: {enterprise.get_feature_count()} features enabled'))
            
            self.stdout.write(self.style.SUCCESS('\nAll tariff features configured successfully! ✓'))
            
            # Summary
            self.stdout.write('\n' + '=' * 50)
            self.stdout.write(self.style.WARNING('Feature Summary:'))
            for tariff in Tariff.objects.all():
                count = tariff.get_feature_count()
                percent = (count / 32) * 100
                self.stdout.write(f'  • {tariff.title}: {count}/32 features ({percent:.0f}%)')

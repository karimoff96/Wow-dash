from django.core.management.base import BaseCommand
from organizations.models import Role


class Command(BaseCommand):
    help = 'Setup initial roles with permissions'

    def handle(self, *args, **options):
        roles_data = [
            {
                'name': Role.OWNER,
                'description': 'Owner of translation center(s). Full access to their centers and branches.',
                'can_manage_centers': True,
                'can_manage_branches': True,
                'can_manage_staff': True,
                'can_view_all_orders': True,
                'can_manage_orders': True,
                'can_manage_financial': True,
                'can_manage_reports': True,
                'can_manage_products': True,
                'can_manage_customers': True,
                'can_manage_marketing': True,
                'can_manage_agencies': True,
            },
            {
                'name': Role.MANAGER,
                'description': 'Branch manager. Can manage orders and staff within their branch.',
                'can_manage_centers': False,
                'can_manage_branches': False,
                'can_manage_staff': False,
                'can_view_staff': True,
                'can_view_all_orders': True,
                'can_manage_orders': True,
                'can_receive_payments': True,
                'can_view_reports': True,
                'can_view_products': True,
                'can_view_customers': True,
            },
            {
                'name': Role.STAFF,
                'description': 'Staff member. Can process assigned orders and receive payments.',
                'can_manage_centers': False,
                'can_manage_branches': False,
                'can_manage_staff': False,
                'can_view_all_orders': False,
                'can_view_own_orders': True,
                'can_manage_orders': False,
                'can_receive_payments': True,
                'can_view_reports': False,
                'can_view_products': True,
                'can_view_customers': True,
            },
        ]

        for role_data in roles_data:
            role, created = Role.objects.update_or_create(
                name=role_data['name'],
                defaults=role_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created role: {role.get_name_display()}'))
            else:
                self.stdout.write(self.style.WARNING(f'Updated role: {role.get_name_display()}'))

        self.stdout.write(self.style.SUCCESS('Successfully setup all roles!'))

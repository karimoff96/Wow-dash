from django.core.management.base import BaseCommand
from organizations.models import Role


class Command(BaseCommand):
    help = 'Setup initial roles with permissions'

    def handle(self, *args, **options):
        roles_data = [
            {
                'name': Role.OWNER,
                **Role.get_default_permissions_for_role(Role.OWNER),
                'description': 'Owner of translation center(s). Full access to their centers and branches.',
            },
            {
                'name': Role.MANAGER,
                **Role.get_default_permissions_for_role(Role.MANAGER),
                'description': 'Branch manager. Can manage orders and staff within their branch.',
            },
            {
                'name': Role.STAFF,
                **Role.get_default_permissions_for_role(Role.STAFF),
                'description': 'Staff member. Can process assigned orders and receive payments.',
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

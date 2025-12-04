from django.core.management.base import BaseCommand
from services.models import Cateogry, Product


class Command(BaseCommand):
    help = "Set up initial data for the translation center with per-page pricing"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing data before creating new data",
        )

    def handle(self, *args, **options):
        if options["reset"]:
            self.stdout.write("Deleting existing data...")
            Product.objects.all().delete()
            Cateogry.objects.all().delete()

        self.stdout.write("Creating basic main services...")

        # Create main services only
        translation_service, created = Cateogry.objects.get_or_create(
            name="Translation",
            defaults={
                "description": "Document translation services",
                "is_active": True,
            },
        )
        if created:
            self.stdout.write(f"Created main service: {translation_service.name}")

        apostille_service, created = Cateogry.objects.get_or_create(
            name="Apostille",
            defaults={"description": "Document apostille services", "is_active": True},
        )
        if created:
            self.stdout.write(f"Created main service: {apostille_service.name}")

        self.stdout.write(
            self.style.SUCCESS(
                "Basic setup completed! You can now create document types through the admin interface."
            )
        )

        # Print summary
        self.stdout.write(f"Total Main Services: {Cateogry.objects.count()}")
        self.stdout.write(f"Total Document Types: {Product.objects.count()}")

        self.stdout.write("\nNext steps:")
        self.stdout.write("1. Go to Django admin (/admin/)")
        self.stdout.write("2. Create Product entries under Services")
        self.stdout.write("3. Set per-page pricing for each document type")
        self.stdout.write("4. Configure minimum pages and estimated days")

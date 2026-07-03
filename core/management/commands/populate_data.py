"""
Management command to populate database with realistic sample data
for translation center dashboard demonstration.
"""

import random
from datetime import timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone

from organizations.models import TranslationCenter, Branch, Role, AdminUser
from accounts.models import BotUser
from services.models import Language, Category, Product
from orders.models import Order


class Command(BaseCommand):
    help = "Populate database with realistic sample data for dashboards"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing data before populating",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            self.stdout.write("Clearing existing data...")
            Order.objects.all().delete()
            BotUser.objects.all().delete()
            Product.objects.all().delete()
            Category.objects.all().delete()
            Language.objects.all().delete()
            AdminUser.objects.filter(user__is_superuser=False).delete()
            Branch.objects.all().delete()
            TranslationCenter.objects.all().delete()
            Role.objects.all().delete()
            User.objects.filter(is_superuser=False).delete()
            self.stdout.write(self.style.SUCCESS("Data cleared!"))

        self.stdout.write("Creating sample data...")

        # Create languages
        languages = self.create_languages()
        self.stdout.write(f"  Created {len(languages)} languages")

        # Create roles
        roles = self.create_roles()
        self.stdout.write(f"  Created {len(roles)} roles")

        # Create translation centers with branches
        centers = self.create_centers()
        self.stdout.write(f"  Created {len(centers)} centers")

        # Create staff for each branch
        staff_count = self.create_staff(roles)
        self.stdout.write(f"  Created {staff_count} staff members")

        # Create categories and products for each branch
        product_count = self.create_products(languages)
        self.stdout.write(f"  Created {product_count} products")

        # Create customers (bot users)
        customers = self.create_customers()
        self.stdout.write(f"  Created {len(customers)} customers")

        # Create orders with realistic distribution
        order_count = self.create_orders()
        self.stdout.write(f"  Created {order_count} orders")

        self.stdout.write(self.style.SUCCESS("\n✓ Database populated successfully!"))
        self.print_summary()

    def create_languages(self):
        """Create common translation languages"""
        language_data = [
            ("Uzbek", "UZ"),
            ("Russian", "RU"),
            ("English", "EN"),
            ("German", "DE"),
            ("French", "FR"),
            ("Arabic", "AR"),
            ("Turkish", "TR"),
            ("Chinese", "ZH"),
            ("Korean", "KO"),
            ("Japanese", "JA"),
        ]
        languages = []
        for name, short in language_data:
            lang, _ = Language.objects.get_or_create(
                name=name, defaults={"short_name": short}
            )
            languages.append(lang)
        return languages

    def create_roles(self):
        """Create staff roles with individual permission fields"""
        role_data = [
            {
                "name": "owner",
                "display_name": "Owner",
                "can_manage_centers": True,
                "can_manage_branches": True,
                "can_manage_staff": True,
                "can_view_all_orders": True,
                "can_manage_orders": True,
                "can_manage_financial": True,
                "can_manage_reports": True,
                "can_manage_products": True,
                "can_manage_customers": True,
                "can_manage_marketing": True,
                "can_manage_agencies": True,
            },
            {
                "name": "manager",
                "display_name": "Manager",
                "can_manage_staff": False,
                "can_view_staff": True,
                "can_view_all_orders": True,
                "can_manage_orders": True,
                "can_receive_payments": True,
                "can_view_reports": True,
                "can_view_products": True,
                "can_view_customers": True,
                "can_edit_customers": True,
            },
            {
                "name": "staff",
                "display_name": "Translator",
                "can_view_own_orders": True,
                "can_update_order_status": True,
                "can_complete_orders": True,
                "can_receive_payments": True,
                "can_view_products": True,
                "can_view_customers": True,
            },
        ]
        roles = {}
        for data in role_data:
            name = data.pop("name")
            role, created = Role.objects.get_or_create(
                name=name,
                defaults={"is_active": True, **data},
            )
            if not created:
                # Update existing role with new permissions
                for key, value in data.items():
                    setattr(role, key, value)
                role.save()
            roles[name] = role
        return roles

    def create_centers(self):
        """Create translation centers with multiple branches"""
        center_data = [
            {
                "name": "GlobalTranslate",
                "branches": [
                    {"name": "Tashkent Main Office", "is_main": True},
                    {"name": "Chilanzar Branch", "is_main": False},
                    {"name": "Sergeli Branch", "is_main": False},
                ],
            },
            {
                "name": "LinguaPro Center",
                "branches": [
                    {"name": "Samarkand Office", "is_main": True},
                    {"name": "Bukhara Branch", "is_main": False},
                ],
            },
            {
                "name": "QuickDocs Translation",
                "branches": [
                    {"name": "Namangan Office", "is_main": True},
                    {"name": "Fergana Branch", "is_main": False},
                    {"name": "Andijan Branch", "is_main": False},
                ],
            },
        ]

        centers = []
        for i, data in enumerate(center_data):
            # Create owner user
            owner_username = f"owner_{data['name'].lower().replace(' ', '_')}"
            owner, _ = User.objects.get_or_create(
                username=owner_username,
                defaults={
                    "email": f"{owner_username}@example.com",
                    "first_name": f"Owner {i+1}",
                    "last_name": data["name"][:10],
                },
            )
            owner.set_password("password123")
            owner.save()

            # Create center
            center, created = TranslationCenter.objects.get_or_create(
                name=data["name"],
                defaults={
                    "owner": owner,
                    "address": f"{data['name']} Address, Uzbekistan",
                    "phone": f"+998 9{random.randint(0,9)} {random.randint(100,999)} {random.randint(10,99)} {random.randint(10,99)}",
                    "email": f"info@{data['name'].lower().replace(' ', '')}.uz",
                },
            )

            # Delete auto-created main branch if we're creating custom ones
            if created:
                Branch.objects.filter(center=center).delete()

            # Create branches
            for branch_data in data["branches"]:
                branch, _ = Branch.objects.get_or_create(
                    center=center,
                    name=branch_data["name"],
                    defaults={
                        "is_main": branch_data["is_main"],
                        "address": f"{branch_data['name']}, Uzbekistan",
                        "phone": f"+998 9{random.randint(0,9)} {random.randint(100,999)} {random.randint(10,99)} {random.randint(10,99)}",
                        "is_active": True,
                    },
                )

            # Create AdminUser profile for owner - get owner role
            owner_role, _ = Role.objects.get_or_create(
                name="owner", defaults={"display_name": "Owner", "is_active": True}
            )
            AdminUser.objects.get_or_create(
                user=owner,
                defaults={
                    "branch": center.branches.filter(is_main=True).first(),
                    "center": center,
                    "role": owner_role,
                    "is_active": True,
                },
            )

            centers.append(center)

        return centers

    def create_staff(self, roles):
        """Create staff members for each branch"""
        first_names = [
            "Aziz",
            "Bobur",
            "Dilshod",
            "Farrukh",
            "Gulnora",
            "Hilola",
            "Jasur",
            "Kamola",
            "Laziz",
            "Malika",
            "Nodira",
            "Oybek",
            "Rustam",
            "Sanjar",
            "Timur",
            "Ulugbek",
            "Yulduz",
            "Zarina",
            "Akmal",
            "Bekzod",
        ]
        last_names = [
            "Karimov",
            "Azimov",
            "Toshmatov",
            "Rahimov",
            "Umarov",
            "Yusupov",
            "Ismoilov",
            "Nazarov",
            "Ergashev",
            "Saidov",
            "Mirzayev",
            "Abdullayev",
            "Olimov",
            "Rajabov",
            "Qodirov",
        ]

        staff_count = 0
        branches = Branch.objects.all()

        for branch in branches:
            # Create 2-4 staff per branch
            num_staff = random.randint(2, 4)

            # First one is always manager
            for i in range(num_staff):
                first_name = random.choice(first_names)
                last_name = random.choice(last_names)
                username = f"{first_name.lower()}_{last_name.lower()}_{branch.id}_{i}"

                user, _ = User.objects.get_or_create(
                    username=username,
                    defaults={
                        "email": f"{username}@example.com",
                        "first_name": first_name,
                        "last_name": last_name,
                    },
                )
                user.set_password("password123")
                user.save()

                if i == 0:
                    # Manager
                    role = roles["manager"]
                else:
                    # Regular staff
                    role = roles["staff"]

                AdminUser.objects.get_or_create(
                    user=user,
                    defaults={
                        "branch": branch,
                        "center": branch.center,
                        "role": role,
                        "is_active": True,
                    },
                )
                staff_count += 1

        return staff_count

    def create_products(self, languages):
        """Create service categories and products for each branch"""
        category_types = [
            {
                "name": "Translation",
                "charging": "dynamic",
                "products": [
                    {"name": "Passport", "first_price": 50000, "other_price": 30000},
                    {
                        "name": "Birth Certificate",
                        "first_price": 45000,
                        "other_price": 25000,
                    },
                    {
                        "name": "Marriage Certificate",
                        "first_price": 55000,
                        "other_price": 35000,
                    },
                    {"name": "Diploma", "first_price": 60000, "other_price": 40000},
                    {
                        "name": "Driver License",
                        "first_price": 40000,
                        "other_price": 25000,
                    },
                    {
                        "name": "Medical Certificate",
                        "first_price": 70000,
                        "other_price": 50000,
                    },
                    {"name": "Contract", "first_price": 80000, "other_price": 60000},
                    {
                        "name": "Power of Attorney",
                        "first_price": 65000,
                        "other_price": 45000,
                    },
                ],
            },
            {
                "name": "Apostille",
                "charging": "static",
                "products": [
                    {
                        "name": "Document Apostille",
                        "first_price": 150000,
                        "other_price": 150000,
                    },
                    {
                        "name": "Legalization",
                        "first_price": 200000,
                        "other_price": 200000,
                    },
                ],
            },
            {
                "name": "Notarization",
                "charging": "dynamic",
                "products": [
                    {
                        "name": "Notarized Copy",
                        "first_price": 35000,
                        "other_price": 20000,
                    },
                    {
                        "name": "Certified Translation",
                        "first_price": 75000,
                        "other_price": 55000,
                    },
                ],
            },
        ]

        product_count = 0
        for branch in Branch.objects.all():
            for cat_data in category_types:
                category, _ = Category.objects.get_or_create(
                    branch=branch,
                    name=cat_data["name"],
                    defaults={
                        "charging": cat_data["charging"],
                        "is_active": True,
                    },
                )
                category.languages.set(languages[:5])  # Add first 5 languages

                for prod_data in cat_data["products"]:
                    Product.objects.get_or_create(
                        category=category,
                        name=prod_data["name"],
                        defaults={
                            "ordinary_first_page_price": Decimal(
                                prod_data["first_price"]
                            ),
                            "ordinary_other_page_price": Decimal(
                                prod_data["other_price"]
                            ),
                            "agency_first_page_price": Decimal(
                                prod_data["first_price"] * 0.85
                            ),
                            "agency_other_page_price": Decimal(
                                prod_data["other_price"] * 0.85
                            ),
                            "is_active": True,
                        },
                    )
                    product_count += 1

        return product_count

    def create_customers(self):
        """Create bot users (customers)"""
        customer_names = [
            "Akbar Aliyev",
            "Bekzod Tursunov",
            "Charos Karimova",
            "Dilnoza Saidova",
            "Eldor Rahimov",
            "Feruza Umarova",
            "Gulshan Nazarova",
            "Hamid Ergashev",
            "Iroda Mirzayeva",
            "Jamshid Abdullayev",
            "Kamila Olimova",
            "Laziz Rajabov",
            "Madina Qodirova",
            "Nodir Yusupov",
            "Ozoda Ismoilova",
            "Pulat Toshmatov",
            "Qobil Azimov",
            "Rano Karimova",
            "Sardor Umarov",
            "Tamara Yuldasheva",
            "Umid Nazarov",
            "Vohid Saidov",
            "Xurshid Mirzayev",
            "Yulduz Rahimova",
            "Zafar Ergashev",
            "Asal Abdullayeva",
            "Bahrom Olimov",
            "Dilbar Rajabova",
            "Elbek Qodirov",
            "Farida Yusupova",
            "Guzal Ismoilova",
            "Husan Toshmatov",
            "Ilhom Azimov",
            "Jasmin Karimova",
            "Komil Umarov",
            "Lola Nazarova",
            "Mansur Saidov",
            "Nargiza Mirzayeva",
            "Otabek Rahimov",
            "Parizod Ergasheva",
        ]

        customers = []
        branches = list(Branch.objects.all())
        now = timezone.now()

        for i, name in enumerate(customer_names):
            branch = random.choice(branches)
            is_agency = random.random() < 0.2  # 20% are agencies

            # Spread customer creation dates over past 90 days for realistic acquisition chart
            days_ago = random.randint(0, 90)
            created_date = now - timedelta(days=days_ago)

            customer, created = BotUser.objects.get_or_create(
                user_id=1000000 + i,
                defaults={
                    "name": name,
                    "phone": f"+998 9{random.randint(0,9)} {random.randint(100,999)} {random.randint(10,99)} {random.randint(10,99)}",
                    "username": name.lower().replace(" ", "_"),
                    "language": random.choice(["uz", "ru", "en"]),
                    "branch": branch,
                    "is_active": True,
                    "is_agency": is_agency,
                },
            )

            # Update created_at to spread customers over time
            if created:
                BotUser.objects.filter(pk=customer.pk).update(created_at=created_date)

            customers.append(customer)

        return customers

    def create_orders(self):
        """Create orders with realistic distribution over the past 90 days"""
        customers = list(BotUser.objects.all())
        # Filter by role name since is_staff_role is a property, not a field
        staff_members = list(AdminUser.objects.filter(role__name="staff"))

        if not customers or not staff_members:
            self.stdout.write(
                self.style.WARNING("  No customers or staff to create orders")
            )
            return 0

        statuses = [
            "pending",
            "payment_pending",
            "payment_received",
            "payment_confirmed",
            "in_progress",
            "ready",
            "completed",
            "cancelled",
        ]
        status_weights = [5, 5, 5, 10, 15, 10, 45, 5]  # Mostly completed

        order_count = 0
        now = timezone.now()

        # Create orders for the past 90 days with varying density
        for days_ago in range(90, -1, -1):
            order_date = now - timedelta(days=days_ago)

            # More orders on weekdays, fewer on weekends
            is_weekend = order_date.weekday() >= 5
            base_orders = 3 if is_weekend else random.randint(8, 15)

            # Increase orders in recent days
            if days_ago < 7:
                base_orders = int(base_orders * 1.3)
            elif days_ago < 30:
                base_orders = int(base_orders * 1.1)

            for _ in range(base_orders):
                customer = random.choice(customers)
                branch = customer.branch or Branch.objects.first()

                # Get products for this branch
                products = list(Product.objects.filter(category__branch=branch))
                if not products:
                    products = list(Product.objects.all()[:5])
                if not products:
                    continue

                product = random.choice(products)

                # Get staff for this branch
                branch_staff = [s for s in staff_members if s.branch == branch]
                assigned_to = (
                    random.choice(branch_staff)
                    if branch_staff
                    else random.choice(staff_members)
                )

                # Determine status based on age
                if days_ago > 7:
                    # Older orders are mostly completed
                    status = random.choices(
                        ["completed", "cancelled"], weights=[95, 5]
                    )[0]
                elif days_ago > 2:
                    # Recent orders have mixed statuses
                    status = random.choices(statuses, weights=status_weights)[0]
                else:
                    # Very recent orders are mostly in early stages
                    status = random.choices(
                        [
                            "pending",
                            "payment_pending",
                            "payment_received",
                            "in_progress",
                        ],
                        weights=[30, 25, 25, 20],
                    )[0]

                pages = random.choices(
                    [1, 2, 3, 4, 5, 6, 7, 8, 10, 15, 20],
                    weights=[30, 25, 15, 10, 7, 5, 3, 2, 1, 1, 1],
                )[0]

                # Calculate price
                if pages == 1:
                    total_price = product.ordinary_first_page_price
                else:
                    total_price = product.ordinary_first_page_price + (
                        product.ordinary_other_page_price * (pages - 1)
                    )

                # Random time during the day
                hour = random.randint(9, 18)
                minute = random.randint(0, 59)
                created_at = order_date.replace(hour=hour, minute=minute)

                # Get language from product's category languages (to pass validation)
                category_languages = list(product.category.languages.all())
                order_language = random.choice(category_languages) if category_languages else None

                order = Order.objects.create(
                    branch=branch,
                    bot_user=customer,
                    product=product,
                    language=order_language,
                    total_pages=pages,
                    status=status,
                    payment_type=random.choice(["cash", "card"]),
                    total_price=total_price,
                    copy_number=random.choices([0, 1, 2, 3], weights=[70, 20, 7, 3])[0],
                    assigned_to=assigned_to,
                    is_active=status not in ["completed", "cancelled"],
                )

                # Update created_at (bypass auto_now_add)
                Order.objects.filter(pk=order.pk).update(created_at=created_at)

                order_count += 1

        return order_count

    def print_summary(self):
        """Print summary of created data"""
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("DATABASE SUMMARY")
        self.stdout.write("=" * 50)
        self.stdout.write(f"Translation Centers: {TranslationCenter.objects.count()}")
        self.stdout.write(f"Branches: {Branch.objects.count()}")
        self.stdout.write(f"Staff Members: {AdminUser.objects.count()}")
        self.stdout.write(f"Roles: {Role.objects.count()}")
        self.stdout.write(f"Languages: {Language.objects.count()}")
        self.stdout.write(f"Categories: {Category.objects.count()}")
        self.stdout.write(f"Products: {Product.objects.count()}")
        self.stdout.write(f"Customers: {BotUser.objects.count()}")
        self.stdout.write(f"Orders: {Order.objects.count()}")
        self.stdout.write("")

        # Order status breakdown
        self.stdout.write("Order Status Breakdown:")
        for status, label in Order.STATUS_CHOICES:
            count = Order.objects.filter(status=status).count()
            self.stdout.write(f"  {label}: {count}")

        self.stdout.write("=" * 50)

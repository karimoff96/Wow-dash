# Generated migration for center-specific order numbering
from django.db import migrations, models


def populate_center_order_numbers(apps, schema_editor):
    """
    Populate center_order_number for existing orders.
    Each center will have sequential numbering starting from 1.
    """
    Order = apps.get_model('orders', 'Order')
    
    # Get all orders grouped by center, ordered by creation date
    orders_by_center = {}
    
    # Group orders by center
    for order in Order.objects.select_related('branch', 'branch__center').order_by('created_at'):
        if order.branch and order.branch.center:
            center_id = order.branch.center.id
            if center_id not in orders_by_center:
                orders_by_center[center_id] = []
            orders_by_center[center_id].append(order)
    
    # Assign sequential numbers per center
    updated_count = 0
    for center_id, orders in orders_by_center.items():
        for index, order in enumerate(orders, start=1):
            order.center_order_number = index
            order.save(update_fields=['center_order_number'])
            updated_count += 1
    
    print(f"✅ Populated center_order_number for {updated_count} orders across {len(orders_by_center)} centers")


def reverse_populate(apps, schema_editor):
    """Reverse operation - set all center_order_numbers to None"""
    Order = apps.get_model('orders', 'Order')
    Order.objects.all().update(center_order_number=None)


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0009_alter_ordermedia_file'),  # Update to your latest migration
    ]

    operations = [
        # Add the field
        migrations.AddField(
            model_name='order',
            name='center_order_number',
            field=models.PositiveIntegerField(
                blank=True,
                db_index=True,
                help_text='Sequential order number within the center (auto-generated)',
                null=True,
                verbose_name='Center Order Number'
            ),
        ),
        # Populate existing orders
        migrations.RunPython(populate_center_order_numbers, reverse_populate),
    ]

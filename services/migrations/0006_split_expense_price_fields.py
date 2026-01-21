# Generated manually for safe data migration
from django.db import migrations, models
from decimal import Decimal


def migrate_price_data_forward(apps, schema_editor):
    """
    Copy existing 'price' data to both new fields.
    This ensures no data is lost during migration.
    """
    Expense = apps.get_model('services', 'Expense')
    for expense in Expense.objects.all():
        # Copy existing price to both fields
        # Assumption: current 'price' represents cost per order (which was for original + all copies)
        # We'll split it: put the price in original, and 0 in copy as a safe default
        # Admins can adjust later based on their business logic
        expense.price_for_original = expense.price
        expense.price_for_copy = Decimal('0.00')
        expense.save(update_fields=['price_for_original', 'price_for_copy'])


def migrate_price_data_backward(apps, schema_editor):
    """
    Restore 'price' from new fields when rolling back.
    """
    Expense = apps.get_model('services', 'Expense')
    for expense in Expense.objects.all():
        # Restore original price field from price_for_original
        expense.price = expense.price_for_original
        expense.save(update_fields=['price'])


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0005_alter_product_agency_copy_price_decimal_and_more'),
    ]

    operations = [
        # Step 1: Add new fields with default values (nullable first to avoid issues)
        migrations.AddField(
            model_name='expense',
            name='price_for_original',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='Cost of this expense for the original document',
                max_digits=12,
                verbose_name='Price for Original'
            ),
        ),
        migrations.AddField(
            model_name='expense',
            name='price_for_copy',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='Cost of this expense per copy document',
                max_digits=12,
                verbose_name='Price for Copy'
            ),
        ),
        
        # Step 2: Migrate existing data
        migrations.RunPython(
            migrate_price_data_forward,
            migrate_price_data_backward
        ),
        
        # Step 3: Remove old 'price' field (only after data is migrated)
        migrations.RemoveField(
            model_name='expense',
            name='price',
        ),
    ]

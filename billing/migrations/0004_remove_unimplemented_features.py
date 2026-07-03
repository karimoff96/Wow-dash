# Generated migration to remove unimplemented features

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0003_add_33_feature_flags'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='tariff',
            name='feature_order_templates',
        ),
        migrations.RemoveField(
            model_name='tariff',
            name='feature_staff_scheduling',
        ),
        migrations.RemoveField(
            model_name='tariff',
            name='feature_invoicing',
        ),
        migrations.RemoveField(
            model_name='tariff',
            name='feature_support_tickets',
        ),
        migrations.RemoveField(
            model_name='tariff',
            name='feature_knowledge_base',
        ),
        migrations.RemoveField(
            model_name='tariff',
            name='feature_data_retention',
        ),
    ]

# Generated manually
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0012_alter_subscription_auto_renew'),
    ]

    operations = [
        migrations.AddField(
            model_name='tariff',
            name='show_prices',
            field=models.BooleanField(default=True, verbose_name='Show Prices', help_text='Display pricing options publicly'),
        ),
    ]

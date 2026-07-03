# Generated manually
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0013_tariff_show_prices'),
    ]

    operations = [
        migrations.AddField(
            model_name='tariff',
            name='is_special',
            field=models.BooleanField(default=False, verbose_name='Private Tariff', help_text='Hide from public landing page'),
        ),
    ]

# Generated manually

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0005_add_granular_permissions'),
    ]

    operations = [
        migrations.AlterField(
            model_name='adminuser',
            name='role',
            field=models.ForeignKey(
                blank=True,
                help_text='Role is optional for superusers',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='users',
                to='organizations.role',
                verbose_name='Role',
            ),
        ),
    ]

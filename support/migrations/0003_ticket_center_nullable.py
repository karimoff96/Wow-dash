from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0001_initial'),
        ('support', '0002_add_telegram_thread_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ticket',
            name='center',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='tickets',
                to='organizations.translationcenter',
                verbose_name='Center',
            ),
        ),
    ]

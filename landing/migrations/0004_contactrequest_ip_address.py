from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('landing', '0003_contactrequest_admin_bot_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='contactrequest',
            name='ip_address',
            field=models.GenericIPAddressField(blank=True, null=True, verbose_name='IP Address'),
        ),
    ]

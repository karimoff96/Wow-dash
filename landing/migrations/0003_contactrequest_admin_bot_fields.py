from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('landing', '0002_contactrequest_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='contactrequest',
            name='admin_telegram_chat_id',
            field=models.BigIntegerField(blank=True, null=True, verbose_name='Admin Telegram Chat ID'),
        ),
        migrations.AddField(
            model_name='contactrequest',
            name='admin_telegram_message_id',
            field=models.BigIntegerField(blank=True, null=True, verbose_name='Admin Telegram Message ID'),
        ),
    ]

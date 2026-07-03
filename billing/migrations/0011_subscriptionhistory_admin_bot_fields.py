from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0010_add_new_tariff_features'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscriptionhistory',
            name='admin_telegram_chat_id',
            field=models.BigIntegerField(blank=True, null=True, verbose_name='Admin Telegram Chat ID'),
        ),
        migrations.AddField(
            model_name='subscriptionhistory',
            name='admin_telegram_message_id',
            field=models.BigIntegerField(blank=True, null=True, verbose_name='Admin Telegram Message ID'),
        ),
    ]

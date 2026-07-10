import secrets
import uuid

import core.fields
import organizations.models
from django.db import migrations, models


def populate_webhook_credentials(apps, schema_editor):
    TranslationCenter = apps.get_model("organizations", "TranslationCenter")
    for center in TranslationCenter.objects.all().iterator():
        center.webhook_identifier = uuid.uuid4()
        center.webhook_secret = secrets.token_urlsafe(32)
        center.save(update_fields=["webhook_identifier", "webhook_secret"])


class Migration(migrations.Migration):
    dependencies = [("organizations", "0027_encrypt_sensitive_fields")]

    operations = [
        migrations.AddField(
            model_name="translationcenter",
            name="bot_delivery_mode",
            field=models.CharField(choices=[("polling", "Polling"), ("webhook", "Webhook")], default="polling", max_length=20, verbose_name="Bot Delivery Mode"),
        ),
        migrations.AddField(
            model_name="translationcenter",
            name="customer_bot_enabled",
            field=models.BooleanField(default=True, verbose_name="Customer Bot Enabled"),
        ),
        migrations.AddField(
            model_name="translationcenter",
            name="maintenance_archive_enabled",
            field=models.BooleanField(default=True, help_text="Allow silent verified archival even when the subscription has ended.", verbose_name="Maintenance Archive Enabled"),
        ),
        migrations.AddField(
            model_name="translationcenter",
            name="webhook_identifier",
            field=models.UUIDField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="translationcenter",
            name="webhook_secret",
            field=core.fields.EncryptedCharField(blank=True, max_length=500, null=True, verbose_name="Webhook Secret"),
        ),
        migrations.RunPython(populate_webhook_credentials, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="translationcenter",
            name="webhook_identifier",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="Webhook Identifier"),
        ),
        migrations.AlterField(
            model_name="translationcenter",
            name="webhook_secret",
            field=core.fields.EncryptedCharField(default=organizations.models.generate_webhook_secret, editable=False, max_length=500, verbose_name="Webhook Secret"),
        ),
    ]

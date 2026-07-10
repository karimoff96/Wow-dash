import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [("organizations", "0028_bot_delivery_controls")]

    operations = [
        migrations.CreateModel(
            name="TelegramUpdateReceipt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("update_id", models.BigIntegerField()),
                ("chat_id", models.BigIntegerField(blank=True, null=True)),
                ("status", models.CharField(choices=[("queued", "Queued"), ("processing", "Processing"), ("completed", "Completed"), ("failed", "Failed"), ("dead", "Dead letter")], default="queued", max_length=20)),
                ("payload", models.JSONField()),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("last_error", models.TextField(blank=True)),
                ("received_at", models.DateTimeField(auto_now_add=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("center", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="telegram_updates", to="organizations.translationcenter")),
            ],
        ),
        migrations.AddConstraint(
            model_name="telegramupdatereceipt",
            constraint=models.UniqueConstraint(fields=("center", "update_id"), name="unique_telegram_update_per_center"),
        ),
        migrations.AddIndex(
            model_name="telegramupdatereceipt",
            index=models.Index(fields=["status", "received_at"], name="bot_telegra_status_21715d_idx"),
        ),
        migrations.AddIndex(
            model_name="telegramupdatereceipt",
            index=models.Index(fields=["center", "chat_id", "received_at"], name="bot_telegra_center__082c0c_idx"),
        ),
    ]

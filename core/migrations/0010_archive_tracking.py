import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0009_notificationread"),
        ("organizations", "0027_encrypt_sensitive_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ArchiveRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("mode", models.CharField(choices=[("inventory", "Inventory only"), ("canary", "Canary without deletion"), ("live", "Live archival")], default="inventory", max_length=20)),
                ("status", models.CharField(choices=[("running", "Running"), ("completed", "Completed"), ("partial", "Partially completed"), ("failed", "Failed")], default="running", max_length=20)),
                ("age_days", models.PositiveIntegerField(default=30)),
                ("delete_after_verified", models.BooleanField(default=False)),
                ("orders_found", models.PositiveIntegerField(default=0)),
                ("orders_archived", models.PositiveIntegerField(default=0)),
                ("source_file_count", models.PositiveIntegerField(default=0)),
                ("source_size_bytes", models.BigIntegerField(default=0)),
                ("deleted_file_count", models.PositiveIntegerField(default=0)),
                ("error", models.TextField(blank=True)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("center", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="archive_runs", to="organizations.translationcenter")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="archive_runs", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-started_at"]},
        ),
        migrations.AddIndex(
            model_name="archiverun",
            index=models.Index(fields=["center", "-started_at"], name="core_archiv_center__a6f0f3_idx"),
        ),
        migrations.AddIndex(
            model_name="archiverun",
            index=models.Index(fields=["status", "-started_at"], name="core_archiv_status_6afe13_idx"),
        ),
        migrations.AddField(model_name="filearchive", name="files_deleted_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="filearchive", name="last_error", field=models.TextField(blank=True)),
        migrations.AddField(model_name="filearchive", name="manifest", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="filearchive", name="run", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="archives", to="core.archiverun")),
        migrations.AddField(model_name="filearchive", name="sha256", field=models.CharField(blank=True, db_index=True, max_length=64)),
        migrations.AddField(model_name="filearchive", name="source_file_count", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="filearchive", name="source_size_bytes", field=models.BigIntegerField(default=0)),
        migrations.AddField(model_name="filearchive", name="telegram_file_id", field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name="filearchive", name="upload_attempts", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="filearchive", name="uploaded_size_bytes", field=models.BigIntegerField(default=0)),
        migrations.AddField(model_name="filearchive", name="verification_status", field=models.CharField(choices=[("legacy", "Legacy archive"), ("pending", "Pending verification"), ("verified", "Verified"), ("failed", "Verification failed"), ("manual_required", "Manual upload required")], db_index=True, default="legacy", max_length=24)),
        migrations.AddField(model_name="filearchive", name="verified_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AlterField(model_name="filearchive", name="telegram_message_id", field=models.BigIntegerField(blank=True, help_text="Message ID in Telegram channel where archive is stored", null=True, verbose_name="Telegram Message ID")),
    ]

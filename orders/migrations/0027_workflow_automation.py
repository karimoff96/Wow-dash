import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0007_add_bot_user_state"),
        ("orders", "0026_add_order_comment"),
        ("organizations", "0028_bot_delivery_controls"),
        ("services", "0015_add_branch_to_language"),
    ]

    operations = [
        migrations.CreateModel(
            name="Quote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference", models.UUIDField(db_index=True, default=uuid.uuid4, editable=False)),
                ("version", models.PositiveIntegerField(default=1)),
                ("customer_name", models.CharField(blank=True, max_length=200)),
                ("customer_phone", models.CharField(blank=True, max_length=30)),
                ("source", models.CharField(choices=[("dashboard", "Dashboard"), ("bot", "Telegram Bot"), ("mini_app", "Telegram Mini App")], default="dashboard", max_length=20)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("submitted", "Submitted"), ("approved", "Approved"), ("rejected", "Rejected"), ("expired", "Expired"), ("converted", "Converted")], db_index=True, default="draft", max_length=20)),
                ("currency", models.CharField(default="UZS", max_length=3)),
                ("subtotal", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("discount", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("total", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("valid_until", models.DateField(blank=True, db_index=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                ("converted_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="approved_quotes", to="organizations.adminuser")),
                ("bot_user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="quotes", to="accounts.botuser")),
                ("branch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="quotes", to="organizations.branch")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_quotes", to="organizations.adminuser")),
                ("files", models.ManyToManyField(blank=True, related_name="quotes", to="orders.ordermedia")),
                ("supersedes", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="revisions", to="orders.quote")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="QuoteLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("pages", models.PositiveIntegerField(default=1)),
                ("copies", models.PositiveIntegerField(default=0)),
                ("urgency", models.CharField(choices=[("normal", "Normal"), ("express", "Express")], default="normal", max_length=20)),
                ("description", models.TextField(blank=True)),
                ("unit_price", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("total_price", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("price_snapshot", models.JSONField(blank=True, default=dict)),
                ("language", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="quote_lines", to="services.language")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="quote_lines", to="services.product")),
                ("quote", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="orders.quote")),
            ],
            options={"ordering": ["pk"]},
        ),
        migrations.CreateModel(
            name="AssignmentRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("priority", models.PositiveSmallIntegerField(default=100)),
                ("turnaround_hours", models.PositiveIntegerField(default=48)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("assignee", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assignment_rules", to="organizations.adminuser")),
                ("branch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="assignment_rules", to="organizations.branch")),
                ("category", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="assignment_rules", to="services.category")),
                ("language", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="assignment_rules", to="services.language")),
                ("product", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="assignment_rules", to="services.product")),
            ],
            options={"ordering": ["priority", "pk"]},
        ),
        migrations.AddConstraint(model_name="quote", constraint=models.UniqueConstraint(fields=("reference", "version"), name="unique_quote_version")),
        migrations.AddIndex(model_name="quote", index=models.Index(fields=["branch", "status", "-created_at"], name="orders_quot_branch__950d3b_idx")),
        migrations.AddIndex(model_name="quote", index=models.Index(fields=["bot_user", "status", "-created_at"], name="orders_quot_bot_use_22fc01_idx")),
        migrations.AddIndex(model_name="assignmentrule", index=models.Index(fields=["branch", "is_active", "priority"], name="orders_assi_branch__42d85f_idx")),
        migrations.AddField(model_name="order", name="quote", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="orders", to="orders.quote", verbose_name="Source Quote")),
        migrations.AddField(model_name="order", name="sla_due_at", field=models.DateTimeField(blank=True, db_index=True, null=True, verbose_name="SLA Due At")),
        migrations.AddField(model_name="order", name="workflow_priority", field=models.PositiveSmallIntegerField(db_index=True, default=100, help_text="Lower values are assigned first.", verbose_name="Workflow Priority")),
        migrations.CreateModel(
            name="OrderEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_type", models.CharField(choices=[("created", "Created"), ("status_changed", "Status changed"), ("assigned", "Assigned"), ("payment", "Payment"), ("deadline_changed", "Deadline changed"), ("comment", "Comment"), ("document_delivered", "Document delivered"), ("quote_converted", "Quote converted")], max_length=30)),
                ("data", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="order_events", to="organizations.adminuser")),
                ("bot_user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="order_events", to="accounts.botuser")),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="timeline", to="orders.order")),
            ],
            options={"ordering": ["created_at", "pk"]},
        ),
        migrations.AddIndex(model_name="orderevent", index=models.Index(fields=["order", "created_at"], name="orders_orde_order_i_4c5f76_idx")),
    ]

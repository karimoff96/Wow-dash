from django.db import models
from django.utils import timezone


class TelegramUpdateReceipt(models.Model):
    """Durable idempotency and processing record for an incoming Telegram update."""

    STATUS_QUEUED = "queued"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_DEAD = "dead"
    STATUS_CHOICES = (
        (STATUS_QUEUED, "Queued"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
        (STATUS_DEAD, "Dead letter"),
    )

    center = models.ForeignKey(
        "organizations.TranslationCenter",
        on_delete=models.CASCADE,
        related_name="telegram_updates",
    )
    update_id = models.BigIntegerField()
    chat_id = models.BigIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    payload = models.JSONField()
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["center", "update_id"],
                name="unique_telegram_update_per_center",
            )
        ]
        indexes = [
            models.Index(fields=["status", "received_at"], name="bot_telegra_status_21715d_idx"),
            models.Index(fields=["center", "chat_id", "received_at"], name="bot_telegra_center__082c0c_idx"),
        ]

    def mark_completed(self):
        self.status = self.STATUS_COMPLETED
        self.completed_at = timezone.now()
        self.last_error = ""
        self.save(update_fields=["status", "completed_at", "last_error", "updated_at"])

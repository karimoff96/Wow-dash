# Generated migration for Marketing app

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('organizations', '0003_role_is_active'),
        ('accounts', '0002_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='MarketingPost',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(help_text='Internal title for identification', max_length=200, verbose_name='Title')),
                ('content', models.TextField(help_text='Message text (supports HTML: <b>, <i>, <a>, <code>)', verbose_name='Message Content')),
                ('content_type', models.CharField(choices=[('text', 'Text Only'), ('photo', 'Photo with Caption'), ('video', 'Video with Caption'), ('document', 'Document with Caption')], default='text', max_length=20, verbose_name='Content Type')),
                ('media_file', models.FileField(blank=True, help_text='Image, video, or document to send with message', null=True, upload_to='marketing/media/%Y/%m/', verbose_name='Media File')),
                ('target_scope', models.CharField(choices=[('all', 'All Users (Platform-wide)'), ('center', 'Center Users'), ('branch', 'Branch Users'), ('custom', 'Custom Segment')], default='branch', max_length=20, verbose_name='Target Scope')),
                ('include_b2c', models.BooleanField(default=True, help_text='Send to individual customers', verbose_name='Include B2C Customers')),
                ('include_b2b', models.BooleanField(default=True, help_text='Send to agency customers', verbose_name='Include B2B Customers')),
                ('scheduled_at', models.DateTimeField(blank=True, help_text='Leave empty to send immediately', null=True, verbose_name='Scheduled Time')),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('scheduled', 'Scheduled'), ('sending', 'Sending'), ('sent', 'Sent'), ('paused', 'Paused'), ('failed', 'Failed'), ('cancelled', 'Cancelled')], default='draft', max_length=20, verbose_name='Status')),
                ('total_recipients', models.PositiveIntegerField(default=0, verbose_name='Total Recipients')),
                ('sent_count', models.PositiveIntegerField(default=0, verbose_name='Sent Count')),
                ('delivered_count', models.PositiveIntegerField(default=0, verbose_name='Delivered Count')),
                ('failed_count', models.PositiveIntegerField(default=0, verbose_name='Failed Count')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('sent_at', models.DateTimeField(blank=True, null=True, verbose_name='Sent At')),
                ('completed_at', models.DateTimeField(blank=True, null=True, verbose_name='Completed At')),
                ('last_error', models.TextField(blank=True, null=True, verbose_name='Last Error')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_posts', to=settings.AUTH_USER_MODEL, verbose_name='Created By')),
                ('target_branch', models.ForeignKey(blank=True, help_text='Required for branch scope', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='marketing_posts', to='organizations.branch', verbose_name='Target Branch')),
                ('target_center', models.ForeignKey(blank=True, help_text='Required for center/branch scope', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='marketing_posts', to='organizations.translationcenter', verbose_name='Target Center')),
            ],
            options={
                'verbose_name': 'Marketing Post',
                'verbose_name_plural': 'Marketing Posts',
                'ordering': ['-created_at'],
                'permissions': [('can_send_platform_wide', 'Can send platform-wide broadcasts'), ('can_send_center_wide', 'Can send center-wide broadcasts'), ('can_send_branch', 'Can send branch broadcasts')],
            },
        ),
        migrations.CreateModel(
            name='UserBroadcastPreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('receive_marketing', models.BooleanField(default=True, help_text='User can opt out of marketing messages', verbose_name='Receive Marketing Messages')),
                ('receive_promotions', models.BooleanField(default=True, verbose_name='Receive Promotions')),
                ('receive_updates', models.BooleanField(default=True, verbose_name='Receive Updates')),
                ('last_broadcast_at', models.DateTimeField(blank=True, null=True, verbose_name='Last Broadcast Received')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('bot_user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='broadcast_preference', to='accounts.botuser', verbose_name='User')),
            ],
            options={
                'verbose_name': 'User Broadcast Preference',
                'verbose_name_plural': 'User Broadcast Preferences',
            },
        ),
        migrations.CreateModel(
            name='BroadcastRecipient',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('sent', 'Sent'), ('delivered', 'Delivered'), ('failed', 'Failed'), ('blocked', 'Blocked by User'), ('skipped', 'Skipped (Opted Out)')], default='pending', max_length=20, verbose_name='Status')),
                ('telegram_message_id', models.BigIntegerField(blank=True, null=True, verbose_name='Telegram Message ID')),
                ('error_message', models.TextField(blank=True, null=True, verbose_name='Error Message')),
                ('retry_count', models.PositiveSmallIntegerField(default=0, verbose_name='Retry Count')),
                ('sent_at', models.DateTimeField(blank=True, null=True, verbose_name='Sent At')),
                ('bot_user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='broadcast_receipts', to='accounts.botuser', verbose_name='Recipient')),
                ('post', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recipients', to='marketing.marketingpost', verbose_name='Marketing Post')),
            ],
            options={
                'verbose_name': 'Broadcast Recipient',
                'verbose_name_plural': 'Broadcast Recipients',
            },
        ),
        migrations.CreateModel(
            name='BroadcastRateLimit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('messages_per_second', models.PositiveSmallIntegerField(default=25, help_text='Max messages per second (Telegram limit: 30)', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(30)], verbose_name='Messages Per Second')),
                ('daily_limit_per_user', models.PositiveSmallIntegerField(default=3, help_text='Max broadcasts per user per day', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(10)], verbose_name='Daily Limit Per User')),
                ('batch_size', models.PositiveSmallIntegerField(default=50, validators=[django.core.validators.MinValueValidator(10), django.core.validators.MaxValueValidator(100)], verbose_name='Batch Size')),
                ('batch_delay', models.PositiveSmallIntegerField(default=3, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(60)], verbose_name='Batch Delay (seconds)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('center', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='broadcast_rate_limit', to='organizations.translationcenter', verbose_name='Center')),
            ],
            options={
                'verbose_name': 'Broadcast Rate Limit',
                'verbose_name_plural': 'Broadcast Rate Limits',
            },
        ),
        migrations.AddIndex(
            model_name='broadcastrecipient',
            index=models.Index(fields=['post', 'status'], name='marketing_b_post_id_8f6c3e_idx'),
        ),
        migrations.AddIndex(
            model_name='broadcastrecipient',
            index=models.Index(fields=['bot_user', 'sent_at'], name='marketing_b_bot_use_3e8e0e_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='broadcastrecipient',
            unique_together={('post', 'bot_user')},
        ),
    ]

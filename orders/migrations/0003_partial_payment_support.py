# Generated migration for partial payment support

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0002_alter_order_language'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='received',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='Total amount received so far',
                max_digits=12,
                verbose_name='Amount Received',
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='extra_fee',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='Additional charges (rush fee, special handling, etc.)',
                max_digits=10,
                verbose_name='Extra Fee',
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='extra_fee_description',
            field=models.CharField(
                blank=True,
                help_text='Reason for the extra fee',
                max_length=255,
                null=True,
                verbose_name='Extra Fee Description',
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='payment_accepted_fully',
            field=models.BooleanField(
                default=False,
                help_text='Mark as True to consider payment complete regardless of received amount',
                verbose_name='Payment Accepted Fully',
            ),
        ),
    ]

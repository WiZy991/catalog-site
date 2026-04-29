from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partners', '0004_partnerrequest_newsletter_consent'),
    ]

    operations = [
        migrations.AddField(
            model_name='partner',
            name='markup_percent',
            field=models.DecimalField(decimal_places=2, default=0, help_text='Индивидуальная наценка партнёра (0-100%)', max_digits=5, verbose_name='Наценка %'),
        ),
        migrations.AddField(
            model_name='partner',
            name='pricing_mode',
            field=models.CharField(choices=[('discount', 'Индивидуальная скидка'), ('markup', 'Индивидуальная наценка')], default='discount', help_text='Скидка: цена ниже оптовой. Наценка: цена выше оптовой.', max_length=20, verbose_name='Режим ценообразования'),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partners', '0005_partner_pricing_mode_markup_percent'),
    ]

    operations = [
        migrations.AddField(
            model_name='partnerrequest',
            name='company_name',
            field=models.CharField(
                default='',
                help_text='С указанием формы: ИП или ООО',
                max_length=255,
                verbose_name='Название компании',
            ),
            preserve_default=False,
        ),
    ]

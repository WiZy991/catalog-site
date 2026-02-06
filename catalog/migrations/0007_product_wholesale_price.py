# Generated migration for wholesale_price field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0006_promotion'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='wholesale_price',
            field=models.DecimalField(
                blank=True, 
                decimal_places=2, 
                help_text='Цена для партнёров. Если не указана, будет равна розничной цене.', 
                max_digits=12, 
                null=True, 
                verbose_name='Оптовая цена'
            ),
        ),
    ]

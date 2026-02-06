# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0007_product_wholesale_price'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='catalog_type',
            field=models.CharField(
                choices=[('retail', 'Основной каталог'), ('wholesale', 'Партнёрский каталог')],
                db_index=True,
                default='retail',
                help_text='retail = основной сайт, wholesale = только для партнёров',
                max_length=20,
                verbose_name='Каталог'
            ),
        ),
    ]

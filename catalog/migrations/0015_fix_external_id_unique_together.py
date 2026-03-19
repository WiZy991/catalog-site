# Generated manually to fix external_id unique constraint

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0013_add_farpost_auto_update_fields'),
    ]

    operations = [
        # Убираем unique=True с external_id
        migrations.AlterField(
            model_name='product',
            name='external_id',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='Уникальный идентификатор товара из 1С (уникален в комбинации с catalog_type)',
                max_length=255,
                null=True,
                verbose_name='ID из 1С'
            ),
        ),
        # Добавляем unique_together для external_id и catalog_type
        migrations.AlterUniqueTogether(
            name='product',
            unique_together={('external_id', 'catalog_type')},
        ),
    ]

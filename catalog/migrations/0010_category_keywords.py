# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0009_alter_category_options_alter_category_image_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='keywords',
            field=models.TextField(
                blank=True, 
                help_text='Слова для автоопределения категории (через запятую). Пример: стартер, генератор, датчик, реле', 
                verbose_name='Ключевые слова'
            ),
        ),
    ]

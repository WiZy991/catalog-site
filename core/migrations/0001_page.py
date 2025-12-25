# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Page',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.CharField(choices=[('about', 'О компании'), ('payment-delivery', 'Оплата и доставка'), ('contacts', 'Контакты'), ('wholesale', 'Оптовые продажи')], max_length=50, unique=True, verbose_name='Тип страницы')),
                ('title', models.CharField(max_length=200, verbose_name='Заголовок')),
                ('content', models.TextField(help_text='HTML разметка разрешена', verbose_name='Содержимое')),
                ('meta_title', models.CharField(blank=True, max_length=200, verbose_name='Meta Title')),
                ('meta_description', models.TextField(blank=True, verbose_name='Meta Description')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активна')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлена')),
            ],
            options={
                'verbose_name': 'Страница',
                'verbose_name_plural': 'Страницы',
                'ordering': ['slug'],
            },
        ),
    ]


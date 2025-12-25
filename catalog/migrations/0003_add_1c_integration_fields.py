# Generated manually for 1C integration

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0002_alter_product_article'),
    ]

    operations = [
        # Добавляем поле external_id в Product
        migrations.AddField(
            model_name='product',
            name='external_id',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='Уникальный идентификатор товара из 1С',
                max_length=255,
                null=True,
                unique=True,
                verbose_name='ID из 1С'
            ),
        ),
        # Добавляем поле properties в Product
        migrations.AddField(
            model_name='product',
            name='properties',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='JSON объект с дополнительными свойствами товара',
                verbose_name='Дополнительные свойства'
            ),
        ),
        # Создаем модель OneCExchangeLog
        migrations.CreateModel(
            name='OneCExchangeLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('request_method', models.CharField(default='POST', max_length=10, verbose_name='Метод')),
                ('request_path', models.CharField(max_length=255, verbose_name='Путь')),
                ('request_ip', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP адрес')),
                ('request_headers', models.JSONField(blank=True, default=dict, verbose_name='Заголовки запроса')),
                ('request_body_size', models.PositiveIntegerField(default=0, verbose_name='Размер тела запроса (байт)')),
                ('request_format', models.CharField(blank=True, help_text='XML или JSON', max_length=20, verbose_name='Формат данных')),
                ('status', models.CharField(choices=[('success', 'Успешно'), ('error', 'Ошибка'), ('unauthorized', 'Не авторизован')], max_length=20, verbose_name='Статус')),
                ('status_code', models.PositiveIntegerField(default=200, verbose_name='HTTP код ответа')),
                ('total_products', models.PositiveIntegerField(default=0, verbose_name='Всего товаров в запросе')),
                ('updated_products', models.PositiveIntegerField(default=0, verbose_name='Обновлено товаров')),
                ('created_products', models.PositiveIntegerField(default=0, verbose_name='Создано товаров')),
                ('hidden_products', models.PositiveIntegerField(default=0, verbose_name='Скрыто товаров')),
                ('errors_count', models.PositiveIntegerField(default=0, verbose_name='Ошибок')),
                ('error_message', models.TextField(blank=True, verbose_name='Сообщение об ошибке')),
                ('response_data', models.JSONField(blank=True, default=dict, verbose_name='Данные ответа')),
                ('processing_time', models.FloatField(default=0.0, verbose_name='Время обработки (сек)')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата обмена')),
            ],
            options={
                'verbose_name': 'Лог обмена с 1С',
                'verbose_name_plural': 'Логи обмена с 1С',
                'ordering': ['-created_at'],
            },
        ),
        # Добавляем индексы для OneCExchangeLog
        migrations.AddIndex(
            model_name='onecexchangelog',
            index=models.Index(fields=['-created_at'], name='catalog_one_created_idx'),
        ),
        migrations.AddIndex(
            model_name='onecexchangelog',
            index=models.Index(fields=['status'], name='catalog_one_status_idx'),
        ),
        migrations.AddIndex(
            model_name='onecexchangelog',
            index=models.Index(fields=['request_ip'], name='catalog_one_request_ip_idx'),
        ),
        # Добавляем индекс для external_id в Product (уже добавлен в AddField, но для явности)
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['external_id'], name='catalog_prod_external_id_idx'),
        ),
    ]


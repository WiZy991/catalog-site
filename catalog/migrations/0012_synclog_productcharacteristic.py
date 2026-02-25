# Generated manually for SyncLog and ProductCharacteristic models

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0011_populate_category_keywords'),
    ]

    operations = [
        migrations.CreateModel(
            name='SyncLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('operation_type', models.CharField(choices=[('file_upload', 'Загрузка файла'), ('api_sync', 'API синхронизация')], default='api_sync', max_length=20, verbose_name='Тип операции')),
                ('status', models.CharField(choices=[('success', 'Успешно'), ('partial', 'Частично'), ('error', 'Ошибка'), ('unauthorized', 'Не авторизован')], max_length=20, verbose_name='Статус')),
                ('message', models.TextField(blank=True, verbose_name='Сообщение')),
                ('processed_count', models.PositiveIntegerField(default=0, verbose_name='Обработано товаров')),
                ('created_count', models.PositiveIntegerField(default=0, verbose_name='Создано товаров')),
                ('updated_count', models.PositiveIntegerField(default=0, verbose_name='Обновлено товаров')),
                ('errors_count', models.PositiveIntegerField(default=0, verbose_name='Ошибок')),
                ('errors', models.JSONField(blank=True, default=list, verbose_name='Список ошибок')),
                ('request_ip', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP адрес')),
                ('request_format', models.CharField(blank=True, help_text='CSV, XML или JSON', max_length=20, verbose_name='Формат данных')),
                ('filename', models.CharField(blank=True, max_length=255, verbose_name='Имя файла')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата синхронизации')),
                ('processing_time', models.FloatField(default=0.0, verbose_name='Время обработки (сек)')),
            ],
            options={
                'verbose_name': 'Лог синхронизации',
                'verbose_name_plural': 'Логи синхронизации',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='synclog',
            index=models.Index(fields=['-created_at'], name='catalog_syn_created_idx'),
        ),
        migrations.AddIndex(
            model_name='synclog',
            index=models.Index(fields=['status'], name='catalog_syn_status_idx'),
        ),
        migrations.AddIndex(
            model_name='synclog',
            index=models.Index(fields=['operation_type'], name='catalog_syn_operati_idx'),
        ),
        migrations.CreateModel(
            name='ProductCharacteristic',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Название характеристики')),
                ('value', models.CharField(max_length=500, verbose_name='Значение')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='Порядок сортировки')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='product_characteristics', to='catalog.product', verbose_name='Товар')),
            ],
            options={
                'verbose_name': 'Характеристика товара',
                'verbose_name_plural': 'Характеристики товаров',
                'ordering': ['order', 'name'],
                'unique_together': {('product', 'name')},
            },
        ),
        migrations.AddIndex(
            model_name='productcharacteristic',
            index=models.Index(fields=['product', 'name'], name='catalog_pro_product_name_idx'),
        ),
    ]

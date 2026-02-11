# Generated manually for SyncLog model

from django.db import migrations, models


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
    ]

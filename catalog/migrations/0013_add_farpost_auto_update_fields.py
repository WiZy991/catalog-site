# Generated manually for FarpostAPISettings auto update fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0012_synclog_productcharacteristic'),
    ]

    operations = [
        migrations.AddField(
            model_name='farpostapisettings',
            name='api_key',
            field=models.CharField(
                blank=True,
                help_text='Ключ для аутентификации в API Farpost. Предоставляется Farpost по запросу. Используется для расчета auth (SHA512 от ключа). Если указан, имеет приоритет над login:password.',
                max_length=255,
                verbose_name='Ключ API'
            ),
        ),
        migrations.AddField(
            model_name='farpostapisettings',
            name='auto_update_enabled',
            field=models.BooleanField(
                default=False,
                help_text='Включить периодическое автоматическое обновление прайс-листа по ссылке',
                verbose_name='Автоматическое обновление'
            ),
        ),
        migrations.AddField(
            model_name='farpostapisettings',
            name='auto_update_interval',
            field=models.PositiveIntegerField(
                default=24,
                help_text='Как часто обновлять прайс-лист (в часах). Минимум: 1 час.',
                verbose_name='Интервал обновления (часы)'
            ),
        ),
        migrations.AddField(
            model_name='farpostapisettings',
            name='auto_update_url',
            field=models.URLField(
                blank=True,
                help_text='URL для автоматического обновления прайс-листа. Например: http://site.ru/import-price/new-price.csv',
                verbose_name='Ссылка на прайс-лист'
            ),
        ),
        migrations.AddField(
            model_name='farpostapisettings',
            name='last_auto_update',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='Последнее автоматическое обновление'
            ),
        ),
        migrations.AlterField(
            model_name='farpostapisettings',
            name='login',
            field=models.CharField(
                blank=True,
                help_text='Логин для входа на Farpost (необязательно, если используется ключ API)',
                max_length=255,
                verbose_name='Логин'
            ),
        ),
        migrations.AlterField(
            model_name='farpostapisettings',
            name='password',
            field=models.CharField(
                blank=True,
                help_text='Пароль (хранится в зашифрованном виде, необязательно если используется ключ API)',
                max_length=255,
                verbose_name='Пароль'
            ),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0015_fix_external_id_unique_together'),
    ]

    operations = [
        migrations.AlterField(
            model_name='farpostapisettings',
            name='packet_id',
            field=models.CharField(
                'ID пакет-объявления',
                max_length=50,
                blank=True,
                default='',
                help_text='ID пакет-объявления на Farpost (необязательно). '
                          'ID можно найти в URL пакета: https://www.farpost.ru/personal/goods/packet/{id}/recurrent-update'
            ),
        ),
    ]

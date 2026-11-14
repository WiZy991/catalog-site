from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('catalog', '0016_make_packet_id_optional'),
    ]

    operations = [
        migrations.AddField(
            model_name='promotion',
            name='video',
            field=models.FileField(
                blank=True,
                null=True,
                upload_to='promotions/videos/',
                verbose_name='Видео-ролик',
                help_text='Необязательно. Если загружено видео — на сайте будет показано видео вместо изображения.',
            ),
        ),
    ]


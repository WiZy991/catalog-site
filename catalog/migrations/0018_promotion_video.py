from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('catalog', '0017_rename_catalog_pro_product_name_idx_catalog_pro_product_e414c9_idx_and_more'),
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


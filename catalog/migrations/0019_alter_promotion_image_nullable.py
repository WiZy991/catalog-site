from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('catalog', '0018_promotion_video'),
    ]

    operations = [
        migrations.AlterField(
            model_name='promotion',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to='promotions/', verbose_name='Изображение'),
        ),
    ]


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0019_alter_promotion_image_nullable'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='supplier_article',
            field=models.CharField(blank=True, db_index=True, max_length=100, verbose_name='Артикул'),
        ),
    ]


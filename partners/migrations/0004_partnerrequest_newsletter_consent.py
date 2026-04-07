from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partners', '0003_partnerorder_comment'),
    ]

    operations = [
        migrations.AddField(
            model_name='partnerrequest',
            name='newsletter_consent',
            field=models.BooleanField(
                default=False,
                help_text='Отмечено в заявке добровольно; на отправку заявки не влияет.',
                verbose_name='Согласие на информационную рассылку',
            ),
        ),
    ]

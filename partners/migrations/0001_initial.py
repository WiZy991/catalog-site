# Generated migration for partners app

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Partner',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('company_name', models.CharField(blank=True, max_length=255, verbose_name='Название компании')),
                ('full_name', models.CharField(max_length=255, verbose_name='ФИО контактного лица')),
                ('phone', models.CharField(max_length=50, verbose_name='Телефон')),
                ('city', models.CharField(max_length=100, verbose_name='Город')),
                ('inn', models.CharField(blank=True, max_length=20, verbose_name='ИНН')),
                ('kpp', models.CharField(blank=True, max_length=20, verbose_name='КПП')),
                ('legal_address', models.TextField(blank=True, verbose_name='Юридический адрес')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активен')),
                ('discount_percent', models.DecimalField(decimal_places=2, default=0, help_text='Индивидуальная скидка партнёра (0-100%)', max_digits=5, verbose_name='Скидка %')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Зарегистрирован')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлён')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='Последний вход')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='partner_profile', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Партнёр',
                'verbose_name_plural': 'Партнёры',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='PartnerSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('manager_email', models.EmailField(help_text='Email для получения уведомлений о новых заявках партнёров', max_length=254, verbose_name='Email менеджера по опту')),
                ('cooperation_conditions', models.TextField(blank=True, help_text='HTML разметка разрешена', verbose_name='Условия сотрудничества')),
                ('advantages', models.TextField(blank=True, help_text='HTML разметка разрешена', verbose_name='Преимущества работы с компанией')),
                ('access_procedure', models.TextField(blank=True, help_text='HTML разметка разрешена', verbose_name='Порядок получения оптового доступа')),
                ('price_hidden_text', models.CharField(default='Цена доступна после регистрации', help_text='Текст, который видят незарегистрированные пользователи вместо цены', max_length=255, verbose_name='Текст вместо цены')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
            ],
            options={
                'verbose_name': 'Настройки партнёрского раздела',
                'verbose_name_plural': 'Настройки партнёрского раздела',
            },
        ),
        migrations.CreateModel(
            name='PartnerRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('full_name', models.CharField(max_length=255, verbose_name='ФИО контактного лица')),
                ('phone', models.CharField(max_length=50, verbose_name='Телефон')),
                ('email', models.EmailField(max_length=254, verbose_name='E-mail')),
                ('city', models.CharField(max_length=100, verbose_name='Город')),
                ('comment', models.TextField(blank=True, verbose_name='Комментарий')),
                ('status', models.CharField(choices=[('pending', 'На рассмотрении'), ('approved', 'Одобрена'), ('rejected', 'Отклонена')], default='pending', max_length=20, verbose_name='Статус')),
                ('admin_comment', models.TextField(blank=True, verbose_name='Комментарий администратора')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата заявки')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлена')),
                ('processed_at', models.DateTimeField(blank=True, null=True, verbose_name='Дата обработки')),
                ('partner', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='request', to='partners.partner', verbose_name='Партнёр')),
                ('processed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='processed_partner_requests', to=settings.AUTH_USER_MODEL, verbose_name='Обработал')),
            ],
            options={
                'verbose_name': 'Заявка партнёра',
                'verbose_name_plural': 'Заявки партнёров',
                'ordering': ['-created_at'],
            },
        ),
    ]

from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, SetPasswordForm
from django.contrib.auth.models import User
from django.contrib.auth import password_validation
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from .models import PartnerRequest, Partner


class PartnerRequestForm(forms.ModelForm):
    """Форма заявки на партнёрство."""
    
    class Meta:
        model = PartnerRequest
        fields = ['full_name', 'phone', 'email', 'city', 'comment']
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Иванов Иван Иванович',
                'required': True,
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': '+7 (999) 123-45-67',
                'type': 'tel',
                'required': True,
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-input',
                'placeholder': 'email@example.com',
                'required': True,
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Владивосток',
                'required': True,
            }),
            'comment': forms.Textarea(attrs={
                'class': 'form-textarea',
                'placeholder': 'Дополнительная информация о вашей компании...',
                'rows': 4,
            }),
        }
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        # Проверяем, нет ли уже активной заявки с таким email
        existing = PartnerRequest.objects.filter(
            email=email, 
            status='pending'
        ).exists()
        if existing:
            raise forms.ValidationError(
                'Заявка с таким email уже существует и находится на рассмотрении.'
            )
        return email


class PartnerLoginForm(AuthenticationForm):
    """Форма авторизации партнёра."""
    username = forms.CharField(
        label='Email',
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Ваш email',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        label='Пароль',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Пароль',
        })
    )
    
    error_messages = {
        'invalid_login': 'Неверный email или пароль. Убедитесь, что ваш партнёрский аккаунт активирован.',
        'inactive': 'Этот аккаунт неактивен. Обратитесь к менеджеру.',
    }


class PartnerProfileForm(forms.ModelForm):
    """Форма редактирования профиля партнёра."""
    
    class Meta:
        model = Partner
        fields = ['company_name', 'full_name', 'phone', 'city', 'inn', 'kpp', 'legal_address']
        widgets = {
            'company_name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'ООО "Компания"',
            }),
            'full_name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Иванов Иван Иванович',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': '+7 (999) 123-45-67',
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Владивосток',
            }),
            'inn': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': '1234567890',
            }),
            'kpp': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': '123456789',
            }),
            'legal_address': forms.Textarea(attrs={
                'class': 'form-textarea',
                'placeholder': 'Юридический адрес компании',
                'rows': 3,
            }),
        }


class PartnerPasswordChangeForm(forms.Form):
    """Форма смены пароля для партнёра."""
    old_password = forms.CharField(
        label='Текущий пароль',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Введите текущий пароль',
        }),
        required=True
    )
    
    new_password1 = forms.CharField(
        label='Новый пароль',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Введите новый пароль',
        }),
        required=True,
        help_text=password_validation.password_validators_help_text_html()
    )
    
    new_password2 = forms.CharField(
        label='Подтвердите новый пароль',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Повторите новый пароль',
        }),
        required=True
    )
    
    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
    
    def clean_old_password(self):
        old_password = self.cleaned_data.get('old_password')
        if not self.user.check_password(old_password):
            raise forms.ValidationError('Неверный текущий пароль.')
        return old_password
    
    def clean_new_password2(self):
        password1 = self.cleaned_data.get('new_password1')
        password2 = self.cleaned_data.get('new_password2')
        if password1 and password2:
            if password1 != password2:
                raise forms.ValidationError('Пароли не совпадают.')
        password_validation.validate_password(password2, self.user)
        return password2
    
    def save(self):
        password = self.cleaned_data['new_password1']
        self.user.set_password(password)
        self.user.save()
        return self.user


class PartnerPasswordResetForm(PasswordResetForm):
    """Форма восстановления пароля для партнёра."""
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'Введите ваш email',
            'autofocus': True,
        })
    )
    
    def get_users(self, email):
        """Получить пользователей с указанным email, у которых есть партнёрский профиль."""
        active_users = User.objects.filter(email__iexact=email, is_active=True)
        # Фильтруем только тех, у кого есть партнёрский профиль
        return [u for u in active_users if hasattr(u, 'partner_profile')]
    
    # save() НЕ переопределяем — используем стандартный Django PasswordResetForm.save(),
    # который корректно генерирует uid и token через urlsafe_base64_encode(force_bytes(user.pk)).
    # Наш get_users() фильтрует только партнёров, а send_mail() отправляет HTML-письмо.
    
    def send_mail(self, subject_template_name, email_template_name, context,
                  from_email, to_email, html_email_template_name=None):
        """
        Отправляем HTML-письмо через EmailMessage + content_subtype="html".
        """
        subject = render_to_string(subject_template_name, context)
        subject = ''.join(subject.splitlines())
        
        # Берём HTML-шаблон (или обычный, если HTML не задан)
        template = html_email_template_name or email_template_name
        html_body = render_to_string(template, context)
        
        # Отправляем как HTML — точно так же, как в send_order_email
        email = EmailMessage(
            subject=subject,
            body=html_body,
            from_email=from_email,
            to=[to_email],
        )
        email.content_subtype = "html"
        email.send()


class PartnerSetPasswordForm(SetPasswordForm):
    """Форма установки нового пароля."""
    new_password1 = forms.CharField(
        label='Новый пароль',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Введите новый пароль',
            'id': 'id_new_password1',
        }),
        help_text=password_validation.password_validators_help_text_html()
    )
    
    new_password2 = forms.CharField(
        label='Подтвердите новый пароль',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Повторите новый пароль',
            'id': 'id_new_password2',
        })
    )

from django import forms


class OrderForm(forms.Form):
    """Форма заказа."""
    customer_name = forms.CharField(
        label='ФИО',
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите ваше полное имя',
            'required': True,
        })
    )
    customer_phone = forms.CharField(
        label='Телефон',
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+7 (XXX) XXX-XX-XX',
            'type': 'tel',
            'required': True,
        })
    )
    customer_email = forms.EmailField(
        label='Email (необязательно)',
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'email@example.com',
        })
    )
    customer_comment = forms.CharField(
        label='Комментарий к заказу',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Дополнительная информация о заказе',
        })
    )


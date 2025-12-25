from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import json

from .models import Order, OrderItem
from .forms import OrderForm
from catalog.models import Product


def get_cart(request):
    """Получить корзину из сессии."""
    cart = request.session.get('cart', {})
    return cart


def set_cart(request, cart):
    """Сохранить корзину в сессию."""
    request.session['cart'] = cart
    request.session.modified = True


def cart_add(request, product_id):
    """Добавить товар в корзину."""
    if request.method == 'POST':
        product = get_object_or_404(Product, id=product_id, is_active=True)
        cart = get_cart(request)
        
        product_id_str = str(product_id)
        if product_id_str in cart:
            cart[product_id_str]['quantity'] += 1
        else:
            cart[product_id_str] = {
                'quantity': 1,
                'price': str(product.price),
            }
        
        set_cart(request, cart)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'cart_count': sum(item['quantity'] for item in cart.values()),
                'message': f'Товар "{product.name}" добавлен в корзину'
            })
        else:
            messages.success(request, f'Товар "{product.name}" добавлен в корзину')
            return redirect('orders:cart_view')
    
    return redirect('catalog:index')


def cart_remove(request, product_id):
    """Удалить товар из корзины."""
    cart = get_cart(request)
    product_id_str = str(product_id)
    
    if product_id_str in cart:
        del cart[product_id_str]
        set_cart(request, cart)
        messages.success(request, 'Товар удалён из корзины')
    
    return redirect('orders:cart_view')


def cart_update(request, product_id):
    """Изменить количество товара в корзине."""
    if request.method == 'POST':
        cart = get_cart(request)
        product_id_str = str(product_id)
        quantity = int(request.POST.get('quantity', 1))
        
        if product_id_str in cart:
            if quantity > 0:
                cart[product_id_str]['quantity'] = quantity
            else:
                del cart[product_id_str]
            
            set_cart(request, cart)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
    
    return redirect('orders:cart_view')


def cart_view(request):
    """Просмотр корзины."""
    cart = get_cart(request)
    cart_items = []
    total = 0
    
    for product_id, item_data in cart.items():
        try:
            product = Product.objects.get(id=int(product_id), is_active=True)
            quantity = item_data['quantity']
            price = float(item_data['price'])
            item_total = quantity * price
            total += item_total
            
            cart_items.append({
                'product': product,
                'quantity': quantity,
                'price': price,
                'total': item_total,
            })
        except Product.DoesNotExist:
            continue
    
    context = {
        'cart_items': cart_items,
        'total': total,
    }
    
    return render(request, 'orders/cart.html', context)


def cart_count(request):
    """Получить количество товаров в корзине (AJAX)."""
    cart = get_cart(request)
    total_quantity = sum(item['quantity'] for item in cart.values())
    return JsonResponse({'count': total_quantity})


def cart_clear(request):
    """Очистить корзину."""
    request.session['cart'] = {}
    request.session.modified = True
    messages.success(request, 'Корзина очищена')
    return redirect('orders:cart_view')


def order_create(request):
    """Создание заказа."""
    cart = get_cart(request)
    
    if not cart:
        messages.warning(request, 'Ваша корзина пуста')
        return redirect('orders:cart_view')
    
    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            # Создаём заказ
            order = Order.objects.create(
                customer_name=form.cleaned_data['customer_name'],
                customer_phone=form.cleaned_data['customer_phone'],
                customer_email=form.cleaned_data.get('customer_email', ''),
                customer_comment=form.cleaned_data.get('customer_comment', ''),
            )
            
            # Добавляем товары
            total = 0
            for product_id, item_data in cart.items():
                try:
                    product = Product.objects.get(id=int(product_id), is_active=True)
                    quantity = item_data['quantity']
                    price = float(item_data['price'])
                    
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        quantity=quantity,
                        price=price,
                    )
                    total += quantity * price
                except Product.DoesNotExist:
                    continue
            
            order.total_price = total
            order.save()
            
            # Отправляем email менеджеру
            send_order_email(order)
            
            # Очищаем корзину
            request.session['cart'] = {}
            request.session.modified = True
            
            messages.success(request, f'Заказ #{order.id} успешно оформлен! Мы свяжемся с вами в ближайшее время.')
            return redirect('orders:order_success', order_id=order.id)
    else:
        form = OrderForm()
    
    # Подготавливаем данные корзины для формы
    cart_items = []
    total = 0
    
    for product_id, item_data in cart.items():
        try:
            product = Product.objects.get(id=int(product_id), is_active=True)
            quantity = item_data['quantity']
            price = float(item_data['price'])
            item_total = quantity * price
            total += item_total
            
            cart_items.append({
                'product': product,
                'quantity': quantity,
                'price': price,
                'total': item_total,
            })
        except Product.DoesNotExist:
            continue
    
    context = {
        'form': form,
        'cart_items': cart_items,
        'total': total,
    }
    
    return render(request, 'orders/order_create.html', context)


def order_success(request, order_id):
    """Страница успешного оформления заказа."""
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'orders/order_success.html', {'order': order})


def send_order_email(order):
    """Отправка email менеджеру о новом заказе."""
    from django.core.mail import EmailMessage
    from django.utils.html import escape
    from django.utils import timezone
    
    # Используем локальное время Приморского края
    local_time = timezone.localtime(order.created_at)
    
    subject = f'[ЗАКАЗ] Новый заказ #{order.id} - {order.customer_name}'
    
    # Формируем список товаров
    items_list = []
    for item in order.items.all():
        items_list.append(
            f"- {item.product.name} (Кросс-номер: {item.product.article or 'не указан'})\n"
            f"  Количество: {item.quantity} шт.\n"
            f"  Цена: {item.price} руб. за шт.\n"
            f"  Сумма: {item.get_total()} руб."
        )
    
    items_text = '\n\n'.join(items_list) if items_list else 'Нет товаров'
    
    # Формируем HTML версию письма для лучшей читаемости
    html_message = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .header {{ background-color: #1a365d; color: white; padding: 20px; }}
            .content {{ padding: 20px; }}
            .order-info {{ background-color: #f7fafc; padding: 15px; margin: 10px 0; border-radius: 5px; }}
            .items {{ margin: 15px 0; }}
            .item {{ background-color: #edf2f7; padding: 10px; margin: 5px 0; border-left: 3px solid #1a365d; }}
            .total {{ font-size: 1.2em; font-weight: bold; color: #1a365d; margin-top: 15px; }}
            .footer {{ margin-top: 20px; padding-top: 20px; border-top: 1px solid #e2e8f0; color: #718096; font-size: 0.9em; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h2>Новый заказ на сайте!</h2>
        </div>
        <div class="content">
            <div class="order-info">
                <h3>Информация о заказе</h3>
                <p><strong>Номер заказа:</strong> #{order.id}</p>
                <p><strong>Дата:</strong> {local_time.strftime('%d.%m.%Y %H:%M')}</p>
            </div>
            
            <div class="order-info">
                <h3>Данные клиента</h3>
                <p><strong>ФИО:</strong> {escape(order.customer_name)}</p>
                <p><strong>Телефон:</strong> <a href="tel:{escape(order.customer_phone)}">{escape(order.customer_phone)}</a></p>
                <p><strong>Email:</strong> {escape(order.customer_email) if order.customer_email else 'не указан'}</p>
            </div>
            
            {f'<div class="order-info"><h3>Комментарий</h3><p>{escape(order.customer_comment)}</p></div>' if order.customer_comment else ''}
            
            <div class="items">
                <h3>Товары в заказе:</h3>
                {''.join([f'''
                <div class="item">
                    <p><strong>{escape(item.product.name)}</strong></p>
                    <p>Кросс-номер: {escape(item.product.article) if item.product.article else 'не указан'}</p>
                    <p>Количество: {item.quantity} шт. × {item.price} руб. = {item.get_total()} руб.</p>
                </div>
                ''' for item in order.items.all()])}
            </div>
            
            <div class="total">
                Итоговая сумма: {order.total_price} руб.
            </div>
        </div>
        <div class="footer">
            <p>Это автоматическое уведомление от сайта {getattr(settings, 'SITE_NAME', 'Onesimus')}</p>
        </div>
    </body>
    </html>
    """
    
    # Текстовая версия для почтовых клиентов без поддержки HTML
    text_message = f"""
Новый заказ на сайте!

Номер заказа: #{order.id}
Дата: {local_time.strftime('%d.%m.%Y %H:%M')}

Данные клиента:
ФИО: {order.customer_name}
Телефон: {order.customer_phone}
Email: {order.customer_email or 'не указан'}

{f'Комментарий: {order.customer_comment}' if order.customer_comment else ''}

Товары в заказе:
{items_text}

Итоговая сумма: {order.total_price} руб.

---
Это автоматическое уведомление от сайта {getattr(settings, 'SITE_NAME', 'Onesimus')}
"""
    
    manager_email = getattr(settings, 'MANAGER_EMAIL', settings.SITE_EMAIL)
    
    try:
        # Используем EmailMessage для отправки HTML письма
        email = EmailMessage(
            subject=subject,
            body=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[manager_email],
        )
        email.content_subtype = "html"
        email.body = html_message
        
        # Добавляем специальные заголовки для автоматической сортировки в папку
        # Mail.ru может использовать эти заголовки для фильтрации
        email.extra_headers = {
            'X-Mail-Category': 'Order',
            'X-Priority': '1',  # Высокий приоритет
            'X-Auto-Response-Suppress': 'All',
            'List-Unsubscribe': f'<mailto:{settings.DEFAULT_FROM_EMAIL}?subject=Unsubscribe>',
        }
        
        # Также добавляем специальный заголовок для фильтрации
        email.extra_headers['X-Order-ID'] = str(order.id)
        email.extra_headers['X-Site-Name'] = getattr(settings, 'SITE_NAME', 'Onesimus')
        
        email.send(fail_silently=False)
    except Exception as e:
        # Логируем ошибку, но не прерываем процесс
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка отправки email для заказа #{order.id}: {e}")
        # Также выводим в консоль для отладки
        print(f"Ошибка отправки email для заказа #{order.id}: {e}")


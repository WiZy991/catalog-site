"""
Тексты политики и согласий из файлов в корне проекта (актуальные редакции для сайта).
"""
import re
from pathlib import Path

from django.conf import settings

# Имена файлов в BASE_DIR (как в репозитории)
POLICY_FILENAME = '1_ПОЛИТИКА САЙТ Перс данные ИП Щербович 16.03.2026(new).txt'
CONSENT_CART_FILENAME = 'СОГЛАСИЕ на обработку персональных данных.txt'
CONSENT_PARTNER_LK_FILENAME = '2_Согласие на обработку ПД сайт ИП Щербович (Регистрация ЛК)(new).txt'
CONSENT_NEWSLETTER_FILENAME = 'Согласие на обработку (рассылки).txt'


def _clean_legal_plain_text(text: str) -> str:
    """Убирает служебные символы Word / PUA, типичные для вставки из .doc."""
    if not text:
        return ''
    bad_chars = {
        '\uf0a7': '',
        '\uf0ad': '',
        '\uf0b7': '',
        '□': '',
        '■': '',
        '☐': '',
        '▢': '',
        '▪': '',
        '▫': '',
    }
    text = text.translate(str.maketrans(bad_chars))
    text = re.sub(r'[\uE000-\uF8FF]', '', text)
    return text.strip()


def load_legal_plain_text(filename: str) -> str:
    """Загрузка UTF-8 текста из корня проекта."""
    path = Path(settings.BASE_DIR) / filename
    if not path.is_file():
        return ''
    try:
        raw = path.read_text(encoding='utf-8')
    except OSError:
        return ''
    return _clean_legal_plain_text(raw)


def load_order_consent_text() -> str:
    """Согласие №1 — корзина / оформление заказа."""
    return load_legal_plain_text(CONSENT_CART_FILENAME)


def load_partner_consent_text() -> str:
    """Согласие №2 — регистрация ЛК партнёра."""
    return load_legal_plain_text(CONSENT_PARTNER_LK_FILENAME)


def load_newsletter_consent_text() -> str:
    """Согласие №3 — информационная рассылка."""
    return load_legal_plain_text(CONSENT_NEWSLETTER_FILENAME)


def load_policy_text() -> str:
    return load_legal_plain_text(POLICY_FILENAME)


def policy_text_as_safe_html(text: str):
    """
    Текст политики для вывода в шаблоне: экранирование + якорь #section8 перед разделом 8.
    """
    from django.utils.html import escape
    from django.utils.safestring import mark_safe

    if not text:
        return mark_safe('')
    marker = '8.Условия использования файлов'
    if marker in text:
        before, rest = text.split(marker, 1)
        inner = escape(before) + '<span id="section8"></span>' + escape(marker + rest)
        return mark_safe(inner)
    return mark_safe(escape(text))

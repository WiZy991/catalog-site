"""
Заполняет поле description у оптовых товаров из данных "Кузов" и "Двигатель" из applicability или других источников.
"""
from django.core.management.base import BaseCommand
from django.db import models
from catalog.models import Product
import re


class Command(BaseCommand):
    help = 'Заполняет поле description у оптовых товаров из данных'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать, что будет изменено, без фактического изменения',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Находим все оптовые товары без description или с пустым description
        wholesale_products = Product.objects.filter(
            catalog_type='wholesale'
        ).filter(
            models.Q(description__isnull=True) | models.Q(description='')
        )
        
        updated_count = 0
        skipped_count = 0
        
        for wholesale_product in wholesale_products:
            description_parts = []
            
            # Вариант 1: Берем из розничного аналога
            if wholesale_product.external_id:
                retail_product = Product.objects.filter(
                    external_id=wholesale_product.external_id,
                    catalog_type='retail'
                ).first()
                
                if retail_product and retail_product.description and retail_product.description.strip():
                    description_parts.append(retail_product.description.strip())
            
            # Вариант 2: Если нет розничного аналога, пытаемся извлечь из applicability
            if not description_parts and wholesale_product.applicability:
                applicability_text = wholesale_product.applicability.strip()
                # Пытаемся найти паттерны "Кузов: ..." или "Двигатель: ..."
                body_match = re.search(r'кузов[:\s]+([^,\n]+)', applicability_text, re.IGNORECASE)
                engine_match = re.search(r'двигатель[:\s]+([^,\n]+)', applicability_text, re.IGNORECASE)
                
                if body_match or engine_match:
                    if body_match:
                        description_parts.append(f"Кузов: {body_match.group(1).strip()}")
                    if engine_match:
                        description_parts.append(f"Двигатель: {engine_match.group(1).strip()}")
            
            # Вариант 3: Извлекаем из названия товара (если есть данные в скобках)
            if not description_parts:
                name = wholesale_product.name
                # Ищем паттерны типа "HZJ70/HZJ80" или "2UZFE/1GRFE" в скобках
                bracket_matches = re.findall(r'\(([^)]+)\)', name)
                for bracket_content in bracket_matches:
                    parts = [p.strip() for p in bracket_content.split(',')]
                    for part in parts:
                        # Пропускаем артикулы
                        if re.match(r'^\d{5}-\d{5}$', part) or re.match(r'^\d{1}-\d{5}-\d{3}-\d{1}$', part):
                            continue
                        # Если это похоже на модель (содержит буквы и цифры, но не только цифры)
                        if re.search(r'[A-Za-z]', part) and not re.match(r'^\d+$', part):
                            if '/' in part:
                                # Это может быть список моделей
                                models_list = [m.strip() for m in part.split('/')]
                                description_parts.append(f"Кузов: {'/'.join(models_list)}")
                            else:
                                description_parts.append(f"Кузов: {part}")
                            break
            
            if description_parts:
                new_description = '\n'.join(description_parts)
                if dry_run:
                    self.stdout.write(
                        f'[DRY RUN] Будет обновлено описание у товара "{wholesale_product.name}" '
                        f'(ID: {wholesale_product.pk}): {new_description}'
                    )
                else:
                    wholesale_product.description = new_description
                    wholesale_product.save(update_fields=['description'])
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✓ Обновлено описание у товара "{wholesale_product.name}" (ID: {wholesale_product.pk})'
                        )
                    )
                updated_count += 1
            else:
                skipped_count += 1
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'\n[DRY RUN] Будет обновлено описаний: {updated_count}, '
                    f'пропущено: {skipped_count}'
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    'Запустите команду без --dry-run для фактического обновления'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✓ Готово! Обновлено описаний: {updated_count}, пропущено: {skipped_count}'
                )
            )

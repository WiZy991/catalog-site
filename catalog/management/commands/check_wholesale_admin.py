"""
Проверяет настройки админки для оптовых товаров.
"""
from django.core.management.base import BaseCommand
from partners.admin import WholesaleProductAdmin
from catalog.models import WholesaleProduct


class Command(BaseCommand):
    help = 'Проверяет настройки админки для оптовых товаров'

    def handle(self, *args, **options):
        admin = WholesaleProductAdmin(WholesaleProduct, None)
        
        self.stdout.write('Проверка настроек WholesaleProductAdmin:')
        self.stdout.write('=' * 60)
        
        # Проверяем exclude
        if hasattr(admin, 'exclude') and admin.exclude:
            self.stdout.write(
                self.style.SUCCESS(f'✓ Поле исключено: {admin.exclude}')
            )
        else:
            self.stdout.write(
                self.style.WARNING('⚠ Поле "applicability" НЕ исключено!')
            )
        
        # Проверяем fieldsets
        if hasattr(admin, 'fieldsets') and admin.fieldsets:
            has_applicability = False
            for name, options in admin.fieldsets:
                if 'applicability' in str(options.get('fields', [])):
                    has_applicability = True
                    self.stdout.write(
                        self.style.ERROR(f'✗ Поле "applicability" найдено в fieldset "{name}"')
                    )
            
            if not has_applicability:
                self.stdout.write(
                    self.style.SUCCESS('✓ Поле "applicability" НЕ найдено в fieldsets')
                )
        
        self.stdout.write('=' * 60)
        self.stdout.write('Если поле всё ещё видно, перезапустите сервер Django!')

"""
Очистка старых ZIP-архивов обмена 1С в media/1c_exchange.

По умолчанию удаляет файлы вида v8_*.zip старше 7 дней.
Подходит для запуска по cron.
"""
import os
from datetime import datetime, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Удаляет старые ZIP архивы 1С (v8_*.zip) из директории обмена"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=7,
            help="Удалять архивы старше N дней (по умолчанию: 7)",
        )
        parser.add_argument(
            "--pattern",
            type=str,
            default="v8_",
            help="Префикс имени архива (по умолчанию: v8_)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только показать, что будет удалено, без удаления",
        )

    def handle(self, *args, **options):
        exchange_dir = getattr(
            settings, "ONE_C_EXCHANGE_DIR", os.path.join(settings.MEDIA_ROOT, "1c_exchange")
        )
        days = max(0, int(options["days"]))
        pattern = str(options["pattern"] or "v8_").strip()
        dry_run = bool(options["dry_run"])

        if not os.path.isdir(exchange_dir):
            self.stdout.write(self.style.ERROR(f"Директория не найдена: {exchange_dir}"))
            return

        cutoff = datetime.now() - timedelta(days=days)
        self.stdout.write(
            f"Папка: {exchange_dir}\n"
            f"Правило: удалить *{pattern}*.zip старше {days} дн. "
            f"(до {cutoff.strftime('%Y-%m-%d %H:%M:%S')})\n"
            f"Режим: {'DRY-RUN' if dry_run else 'DELETE'}"
        )

        deleted_count = 0
        kept_count = 0
        error_count = 0
        total_freed = 0

        try:
            names = os.listdir(exchange_dir)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка чтения директории: {e}"))
            return

        for name in names:
            low = name.lower()
            if not low.endswith(".zip"):
                continue
            if pattern and pattern.lower() not in low:
                continue

            path = os.path.join(exchange_dir, name)
            if not os.path.isfile(path):
                continue

            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(path))
                size = os.path.getsize(path)
            except Exception as e:
                error_count += 1
                self.stdout.write(self.style.WARNING(f"Не удалось прочитать {name}: {e}"))
                continue

            if mtime > cutoff:
                kept_count += 1
                continue

            if dry_run:
                self.stdout.write(
                    f"[DRY] {name} | {size / (1024 * 1024):.2f} MB | "
                    f"{mtime.strftime('%Y-%m-%d %H:%M:%S')}"
                )
                deleted_count += 1
                total_freed += size
                continue

            try:
                os.remove(path)
                self.stdout.write(
                    f"[DEL] {name} | {size / (1024 * 1024):.2f} MB | "
                    f"{mtime.strftime('%Y-%m-%d %H:%M:%S')}"
                )
                deleted_count += 1
                total_freed += size
            except Exception as e:
                error_count += 1
                self.stdout.write(self.style.WARNING(f"Не удалось удалить {name}: {e}"))

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Готово. {'К удалению' if dry_run else 'Удалено'}: {deleted_count}, "
                f"оставлено: {kept_count}, ошибок: {error_count}, "
                f"{'освободится' if dry_run else 'освобождено'}: {total_freed / (1024 * 1024):.2f} MB"
            )
        )


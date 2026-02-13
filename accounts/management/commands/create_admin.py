"""
Создание администратора системы.
Логин: admin1, пароль: 123456
Использование: python manage.py create_admin
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date

from accounts.models import CUsers


class Command(BaseCommand):
    help = 'Создаёт администратора admin1/123456 (если не существует)'

    def handle(self, *args, **options):
        username = 'admin1'
        password = '123456'
        
        admin, created = CUsers.objects.update_or_create(
            username=username,
            defaults={
                'name': 'Администратор',
                'date_of_b': date(1990, 1, 1),
                'role': 'admin',
                'password': password,
                'is_auth': True,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Администратор {username} создан'))
        else:
            admin.password = password
            admin.save()
            self.stdout.write(self.style.SUCCESS(f'Пароль администратора {username} обновлён'))

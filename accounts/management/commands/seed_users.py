"""
Создание тестовых пользователей: 3 врача, 10 родителей, 42 ребёнка.
Распределение: депрессивный ребёнок, повышенный стресс, дефицит внимания,
родители с несколькими детьми, врачи с разным количеством пациентов.
Использование: python manage.py seed_users
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
import random

from accounts.models import CUsers, DoctorLicense, GameResult, GameSession


class Command(BaseCommand):
    help = 'Создаёт 3 врачей, 10 родителей, 42 ребёнка с распределением'

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true', help='Удалить созданных пользователей перед созданием')

    def handle(self, *args, **options):
        if options.get('clear'):
            self._clear_seed_users()
            return

        password = '123456'
        base_year = 2015

        # 3 врача
        doctors_data = [
            ('doc1', 'Петрова Анна Ивановна'),
            ('doc2', 'Сидоров Михаил Петрович'),
            ('doc3', 'Козлова Елена Сергеевна'),
        ]
        doctors = []
        for i, (username, name) in enumerate(doctors_data):
            doc, _ = CUsers.objects.update_or_create(
                username=username,
                defaults={
                    'name': name,
                    'date_of_b': date(1980 + i, 3, 15),
                    'role': 'doctor',
                    'password': password,
                    'is_auth': True,
                }
            )
            doctors.append(doc)
            DoctorLicense.objects.get_or_create(
                user=doc,
                defaults={
                    'license_number': f'LIC-{1000 + i}',
                    'is_verified': True,
                }
            )
            self.stdout.write(self.style.SUCCESS(f'Врач: {name} ({username})'))

        # 10 родителей
        parents_data = [
            ('parent1', 'Иванов Иван Иванович'),
            ('parent2', 'Смирнова Мария Александровна'),
            ('parent3', 'Кузнецов Алексей Владимирович'),
            ('parent4', 'Попова Ольга Николаевна'),
            ('parent5', 'Васильев Дмитрий Сергеевич'),
            ('parent6', 'Соколова Татьяна Петровна'),
            ('parent7', 'Михайлов Андрей Олегович'),
            ('parent8', 'Новикова Екатерина Игоревна'),
            ('parent9', 'Федоров Сергей Дмитриевич'),
            ('parent10', 'Морозова Наталья Викторовна'),
        ]
        parents = []
        for i, (username, name) in enumerate(parents_data):
            p, _ = CUsers.objects.update_or_create(
                username=username,
                defaults={
                    'name': name,
                    'date_of_b': date(1985 + i % 5, 5, 10 + i),
                    'role': 'parent',
                    'password': password,
                    'is_auth': True,
                }
            )
            parents.append(p)
            self.stdout.write(self.style.SUCCESS(f'Родитель: {name} ({username})'))

        # 42 ребёнка: распределение по родителям
        # parent1: 5 детей, parent2: 4, parent3: 4, parent4: 3, parent5: 3, parent6: 4, parent7: 5, parent8: 4, parent9: 5, parent10: 5
        child_per_parent = [5, 4, 4, 3, 3, 4, 5, 4, 5, 5]
        names_pool = [
            'Артём', 'София', 'Максим', 'Анна', 'Иван', 'Мария', 'Александр', 'Виктория',
            'Дмитрий', 'Алиса', 'Кирилл', 'Полина', 'Никита', 'Елизавета', 'Егор', 'Дарья',
            'Арсений', 'Александра', 'Матвей', 'Варвара', 'Тимофей', 'Ксения', 'Роман', 'Ульяна',
            'Владимир', 'Валерия', 'Михаил', 'Арина', 'Даниил', 'Милана', 'Марк', 'Вероника',
            'Лев', 'Алина', 'Степан', 'Кристина', 'Фёдор', 'Ева', 'Глеб', 'Ангелина', 'Илья', 'Диана'
        ]
        random.shuffle(names_pool)

        children = []
        idx = 0
        special_profiles = {
            0: 'depressive',   # первый ребёнок — депрессивный
            5: 'stress',      # 6-й — повышенный стресс
            12: 'attention',   # 13-й — дефицит внимания
        }
        for p_idx, count in enumerate(child_per_parent):
            parent = parents[p_idx]
            for _ in range(count):
                parts = parent.name.split()
                surname = parts[1] if len(parts) > 1 else 'Иванов'
                name = names_pool[idx % len(names_pool)] + ' ' + surname
                username = f'child{idx + 1}'
                profile = special_profiles.get(idx, None)
                child, _ = CUsers.objects.update_or_create(
                    username=username,
                    defaults={
                        'name': name,
                        'date_of_b': date(base_year + idx % 8, (idx % 12) + 1, (idx % 28) + 1),
                        'role': 'child',
                        'password': password,
                        'is_auth': True,
                    }
                )
                parent.children.add(child)
                children.append((child, profile))
                idx += 1

        # Распределение детей по врачам (разное количество)
        # doc1: 20 детей, doc2: 15, doc3: 7
        for i, (child, _) in enumerate(children):
            if i < 20:
                doctors[0].patients.add(child)
            elif i < 35:
                doctors[1].patients.add(child)
            else:
                doctors[2].patients.add(child)

        # Создание игровых результатов для профильных детей
        for child, profile in children:
            if not profile:
                continue
            self._create_profile_results(child, profile)

        self.stdout.write(self.style.SUCCESS(
            f'\nСоздано: 3 врача, 10 родителей, 42 ребёнка.\n'
            f'Пароль для всех: {password}\n'
            f'Специальные профили: child1 (депрессия), child6 (стресс), child13 (внимание)'
        ))

    def _create_profile_results(self, child, profile):
        """Создание игровых результатов для симуляции профиля."""
        session = GameSession.objects.create(user=child, game_type='Painting', completed=True)
        session.end_time = timezone.now()
        session.save()

        if profile == 'depressive':
            GameResult.objects.create(
                user=child, session=session, game_type='Painting',
                sorrow=12, joy=2, happiness=1, love=2, boredom=5, anger=1,
            )
            for gt in ['Choice', 'Dialog', 'EmotionMatch']:
                s = GameSession.objects.create(user=child, game_type=gt, completed=True)
                GameResult.objects.create(
                    user=child, session=s, game_type=gt,
                    sorrow=8, joy=1, happiness=1, love=2, boredom=4, anger=1,
                )
        elif profile == 'stress':
            GameResult.objects.create(
                user=child, session=session, game_type='Painting',
                anger=10, sorrow=3, joy=2, happiness=1, love=1, boredom=2,
            )
            for gt in ['GoNoGo', 'Attention']:
                s = GameSession.objects.create(user=child, game_type=gt, completed=True)
                GameResult.objects.create(
                    user=child, session=s, game_type=gt,
                    mistakes=5, performance_metrics={'correct': 3, 'total': 8},
                )
        elif profile == 'attention':
            for gt in ['Attention', 'GoNoGo', 'Pattern', 'Sequence']:
                s = GameSession.objects.create(user=child, game_type=gt, completed=True)
                GameResult.objects.create(
                    user=child, session=s, game_type=gt,
                    mistakes=8, accuracy=0.4,
                    performance_metrics={'correct': 4, 'total': 10},
                )

    def _clear_seed_users(self):
        """Удаление созданных seed-пользователей."""
        usernames = (
            [f'doc{i}' for i in range(1, 4)] +
            [f'parent{i}' for i in range(1, 11)] +
            [f'child{i}' for i in range(1, 43)]
        )
        deleted = CUsers.objects.filter(username__in=usernames).delete()
        self.stdout.write(self.style.WARNING(f'Удалено пользователей: {deleted[0]}'))

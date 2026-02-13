"""
Команда первоначального заполнения данных нечёткой логики.
Основана на НИР "Сравнительный анализ традиционной и цифровой игровой диагностики детей".

Использование: python manage.py init_fuzzy_data
"""

from django.core.management.base import BaseCommand

from accounts.models import (
    FuzzyLinguisticVariable,
    FuzzyMembershipFunction,
    FuzzyInferenceRule,
    BehaviorPattern,
)
from accounts.fuzzy_logic import init_fuzzy_variables, FuzzyAnalyzer


class Command(BaseCommand):
    help = 'Создание лингвистических переменных, функций принадлежности, правил вывода и поведенческих паттернов из НИР'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Очистить существующие данные перед созданием',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Очистка существующих данных...')
            FuzzyInferenceRule.objects.all().delete()
            BehaviorPattern.objects.all().delete()
            FuzzyMembershipFunction.objects.all().delete()
            FuzzyLinguisticVariable.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Данные очищены'))

        # 1. Лингвистические переменные из НИР (раздел 3.1.1)
        self.stdout.write('Создание лингвистических переменных...')
        init_fuzzy_variables()
        self.stdout.write(self.style.SUCCESS('Лингвистические переменные созданы'))

        # 2. Дополнительные функции принадлежности (раздел 3.1.2)
        self._create_membership_functions()

        # 3. Правила нечёткого вывода
        self._create_inference_rules()

        # 4. Поведенческие паттерны из таблицы 1 НИР
        self._create_behavior_patterns()

        self.stdout.write(self.style.SUCCESS('Инициализация нечёткой логики завершена'))

    def _create_membership_functions(self):
        """Функции принадлежности для классов методов (раздел 3.1.2 НИР)"""
        memberships = [
            ('traditional_test', 'Диагностическая глубина', {
                'низкая': 0.1, 'средняя': 0.8, 'высокая': 0.5
            }, 'Стандартизированные тесты имеют среднюю диагностическую глубину'),
            ('traditional_test', 'Мотивационный потенциал', {
                'низкий': 0.8, 'умеренный': 0.3, 'высокий': 0.1
            }, 'Низкая мотивация у детей при традиционном тестировании'),
            ('traditional_test', 'Объективность и стандартизация', {
                'низкая': 0.1, 'средняя': 0.8, 'высокая': 0.5
            }, 'Высокая стандартизация процедуры'),
            ('digital_game', 'Диагностическая глубина', {
                'низкая': 0.2, 'средняя': 0.5, 'высокая': 0.6
            }, 'Цифровые игры позволяют собирать поведенческие данные'),
            ('digital_game', 'Мотивационный потенциал', {
                'низкий': 0.1, 'умеренный': 0.3, 'высокий': 0.9
            }, 'Высокая вовлечённость детей в игровой процесс'),
            ('digital_game', 'Объективность и стандартизация', {
                'низкая': 0.0, 'средняя': 0.2, 'высокая': 0.9
            }, 'Автоматическая фиксация и объективность данных'),
            ('digital_game', 'Экологическая валидность', {
                'низкая': 0.1, 'средняя': 0.3, 'высокая': 0.8
            }, 'Естественное поведение в игровой среде'),
            ('digital_game', 'Потенциал для динамической оценки', {
                'ограниченный': 0.1, 'умеренный': 0.3, 'широкий': 0.9
            }, 'Возможность многократного тестирования'),
            ('observation', 'Диагностическая глубина', {
                'низкая': 0.2, 'средняя': 0.4, 'высокая': 0.7
            }, 'Наблюдение выявляет глубинные паттерны'),
            ('observation', 'Объективность и стандартизация', {
                'низкая': 0.9, 'средняя': 0.3, 'высокая': 0.0
            }, 'Субъективность наблюдателя'),
            ('projective', 'Мотивационный потенциал', {
                'низкий': 0.2, 'умеренный': 0.5, 'высокий': 0.7
            }, 'Проективные методы привлекательны для детей'),
        ]

        for method_class, var_name, values, rationale in memberships:
            try:
                variable = FuzzyLinguisticVariable.objects.get(name=var_name)
                FuzzyMembershipFunction.objects.update_or_create(
                    method_class=method_class,
                    variable=variable,
                    defaults={
                        'membership_values': values,
                        'rationale': rationale
                    }
                )
            except FuzzyLinguisticVariable.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'Переменная "{var_name}" не найдена, пропуск'))

        self.stdout.write(self.style.SUCCESS('Функции принадлежности созданы'))

    def _create_inference_rules(self):
        """Правила нечёткого вывода для генерации рекомендаций"""
        rules = [
            {
                'name': 'Высокая тревожность',
                'condition': {
                    'emotional_profile.грусть': '>0.5',
                    'motivational_potential.низкий': '>0.4'
                },
                'conclusion': 'Повышенный уровень тревожности',
                'recommendation': 'Рекомендуются успокаивающие игры, консультация психолога',
                'confidence': 0.8
            },
            {
                'name': 'Импульсивный стиль',
                'condition': {
                    'diagnostic_profile.cognitive_style': '== impulsive',
                    'behavioral_patterns.высокий_импульсивность': '>0.6'
                },
                'conclusion': 'Выраженный импульсивный когнитивный стиль',
                'recommendation': 'Упражнения на развитие произвольного внимания и самоконтроля',
                'confidence': 0.9
            },
            {
                'name': 'Высокий диагностический потенциал',
                'condition': {
                    'diagnostic_depth.высокая': '>0.7',
                    'dynamic_assessment.широкий': '>0.6'
                },
                'conclusion': 'Благоприятные условия для диагностики',
                'recommendation': 'Можно проводить углублённую диагностику с использованием всех игровых модулей',
                'confidence': 0.7
            },
            {
                'name': 'Систематическая стратегия',
                'condition': {
                    'classification.систематический': '>0.7',
                    'error_rate': '<0.1'
                },
                'conclusion': 'Систематический подход к решению задач',
                'recommendation': 'Поддерживать текущую стратегию, можно усложнять задания',
                'confidence': 0.85
            },
            {
                'name': 'Случайный паттерн ошибок',
                'condition': {
                    'classification.случайный': '>0.6',
                    'error_rate': '>0.3'
                },
                'conclusion': 'Нестабильность внимания и когнитивного контроля',
                'recommendation': 'Рекомендуются игры на концентрацию, консультация специалиста',
                'confidence': 0.8
            },
        ]

        for rule_data in rules:
            FuzzyInferenceRule.objects.get_or_create(
                name=rule_data['name'],
                defaults=rule_data
            )

        self.stdout.write(self.style.SUCCESS('Правила нечёткого вывода созданы'))

    def _create_behavior_patterns(self):
        """Поведенческие паттерны из таблицы 1 НИР (классификация по доле ошибок)"""
        patterns = [
            {
                'name': 'Систематический',
                'pattern_type': 'strategy',
                'description': 'Доля ошибок < 10%. Последовательный, планомерный подход к решению задач. Низкая импульсивность.',
                'fuzzy_sets': {
                    'error_rate': [0, 0, 0.05, 0.1],
                    'систематический': 1.0,
                    'импульсивный': 0.0,
                    'случайный': 0.0
                },
                'relevant_games': ['Painting', 'Choice', 'Dialog']
            },
            {
                'name': 'Систематический с элементами импульсивности',
                'pattern_type': 'strategy',
                'description': 'Доля ошибок 10-20%. В целом систематичный подход с периодическими импульсивными действиями.',
                'fuzzy_sets': {
                    'error_rate': [0.1, 0.12, 0.18, 0.2],
                    'систематический': 0.7,
                    'импульсивный': 0.3,
                    'случайный': 0.0
                },
                'relevant_games': ['Choice', 'Dialog']
            },
            {
                'name': 'Импульсивный',
                'pattern_type': 'strategy',
                'description': 'Доля ошибок 20-30%. Склонность к быстрым решениям без проверки. Трудности с торможением.',
                'fuzzy_sets': {
                    'error_rate': [0.2, 0.22, 0.28, 0.3],
                    'систематический': 0.2,
                    'импульсивный': 0.7,
                    'случайный': 0.1
                },
                'relevant_games': ['Choice', 'Painting']
            },
            {
                'name': 'Случайный',
                'pattern_type': 'strategy',
                'description': 'Доля ошибок > 30%. Нестабильность, отсутствие чёткой стратегии. Возможные трудности с вниманием.',
                'fuzzy_sets': {
                    'error_rate': [0.3, 0.35, 0.5, 1.0],
                    'систематический': 0.0,
                    'импульсивный': 0.3,
                    'случайный': 0.8
                },
                'relevant_games': ['Painting', 'Choice', 'Dialog']
            },
            {
                'name': 'Ошибки внимания',
                'pattern_type': 'attention',
                'description': 'Ошибки, связанные с отвлечением и потерей фокуса. Часто при длительных заданиях.',
                'fuzzy_sets': {'attention': 0.8, 'inhibition': 0.2},
                'relevant_games': ['Painting', 'Choice']
            },
            {
                'name': 'Ошибки торможения',
                'pattern_type': 'attention',
                'description': 'Ошибки из-за трудностей с подавлением доминантной реакции. Импульсивные ответы.',
                'fuzzy_sets': {'attention': 0.2, 'inhibition': 0.8},
                'relevant_games': ['Choice', 'Dialog']
            },
            {
                'name': 'Эмоциональная вовлечённость',
                'pattern_type': 'emotion',
                'description': 'Высокая эмоциональная реакция на задания. Влияние на точность выполнения.',
                'fuzzy_sets': {'engagement': 0.8},
                'relevant_games': ['Painting', 'Dialog']
            },
        ]

        for p in patterns:
            BehaviorPattern.objects.get_or_create(
                name=p['name'],
                defaults={
                    'pattern_type': p['pattern_type'],
                    'description': p['description'],
                    'fuzzy_sets': p['fuzzy_sets'],
                    'relevant_games': p['relevant_games']
                }
            )

        self.stdout.write(self.style.SUCCESS('Поведенческие паттерны созданы'))

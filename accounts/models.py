from django.db import models
from django.contrib.auth.hashers import make_password, check_password
import datetime
import json
import uuid

# Список базовых эмоций из презентации
EMOTIONS = ['гнев', 'скука', 'радость', 'счастье', 'грусть', 'любовь']

class CUsers(models.Model):
    """Модель пользователя (из вашего кода с улучшениями)"""
    username = models.CharField('логин', max_length=150, unique=True)
    name = models.CharField('фио', max_length=150)
    date_of_b = models.DateField('дата рождения')
    role = models.CharField(max_length=20, choices=[
        ('admin', 'Администратор'),
        ('doctor', 'Врач'),
        ('parent', 'Родитель'),
        ('child', 'Ребёнок'),
    ], default='child')
    password = models.CharField('пароль', max_length=150)
    is_auth = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Связи
    children = models.ManyToManyField(
        'self',
        symmetrical=False,
        related_name='parents',
        blank=True
    )
    # Пациенты врача (дети, добавленные по коду)
    patients = models.ManyToManyField(
        'self',
        symmetrical=False,
        related_name='doctors',
        blank=True,
        limit_choices_to={'role': 'child'}
    )
    
    # Код для присоединения
    connection_code = models.CharField(max_length=10, blank=True, null=True, unique=True)
    code_expires = models.DateTimeField(blank=True, null=True)
    
    def save(self, *args, **kwargs):
        # Хеширование пароля
        if self.password and not self.password.startswith('pbkdf2_'):
            self.password = make_password(self.password)
        # Генерация кода для ребёнка или врача
        if not self.connection_code and self.role in ['child', 'doctor']:
            self.generate_connection_code()
        super().save(*args, **kwargs)
    
    def generate_connection_code(self):
        """Генерация уникального кода для присоединения"""
        import random
        import string
        from django.utils import timezone
        from datetime import timedelta
        
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        while CUsers.objects.filter(connection_code=code).exists():
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        self.connection_code = code
        self.code_expires = timezone.now() + timedelta(days=30)
    
    def check_password(self, raw_password):
        """Проверка пароля"""
        return check_password(raw_password, self.password)
    
    def __str__(self):
        return f'{self.get_role_display()} {self.name}'
    
    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'


class DoctorLicense(models.Model):
    """Лицензия врача (проверка при регистрации)"""
    user = models.OneToOneField(CUsers, on_delete=models.CASCADE, related_name='license')
    license_number = models.CharField('номер лицензии', max_length=50, unique=True)
    license_file = models.FileField('файл лицензии', upload_to='licenses/', blank=True, null=True)
    license_scan = models.TextField('текст лицензии', blank=True)  # Для вставки текста
    is_verified = models.BooleanField('проверено', default=False)
    verified_by = models.ForeignKey(
        CUsers, 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL, 
        related_name='verified_doctors',
        limit_choices_to={'role': 'admin'}
    )
    verified_date = models.DateTimeField('дата проверки', null=True, blank=True)
    rejection_reason = models.TextField('причина отказа', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Лицензия {self.license_number} - {'проверена' if self.is_verified else 'ожидает'}"
    
    class Meta:
        verbose_name = 'Лицензия врача'
        verbose_name_plural = 'Лицензии врачей'


class GameSession(models.Model):
    """Игровая сессия - для сбора поведенческих траекторий"""
    user = models.ForeignKey(CUsers, on_delete=models.CASCADE, related_name='game_sessions')
    game_type = models.CharField(max_length=20, choices=[
        ('Painting', 'Раскраска'),
        ('Dialog', 'Диалог'),
        ('Choice', 'Выбор'),
        ('Puzzle', 'Головоломка'),
        ('Memory', 'Память'),
        ('Adventure', 'Приключение'),
    ])
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    completed = models.BooleanField(default=False)
    
    # Поведенческие траектории (из раздела 2.1.2 НИР)
    behavior_trajectory = models.JSONField(default=list)  # История действий
    
    def add_action(self, action_type, action_data, timestamp=None):
        """Добавление действия в траекторию"""
        from django.utils import timezone
        if timestamp is None:
            timestamp = timezone.now().isoformat()
        
        self.behavior_trajectory.append({
            'type': action_type,
            'data': action_data,
            'timestamp': timestamp
        })
        self.save(update_fields=['behavior_trajectory'])
    
    def __str__(self):
        return f"Сессия {self.game_type} для {self.user.name} от {self.start_time.strftime('%d.%m.%Y')}"
    
    class Meta:
        verbose_name = 'Игровая сессия'
        verbose_name_plural = 'Игровые сессии'


class GameResult(models.Model):
    """Результаты игры (из вашего кода с улучшениями)"""
    user = models.ForeignKey(CUsers, on_delete=models.CASCADE, related_name='game_results')
    session = models.ForeignKey(GameSession, on_delete=models.CASCADE, null=True, blank=True, related_name='results')
    game_type = models.CharField(max_length=20, choices=[
        ('Painting', 'Раскраска'),
        ('Dialog', 'Диалог'),
        ('Choice', 'Выбор'),
    ])
    
    # Эмоциональные показатели
    joy = models.IntegerField(default=0)      # радость
    sorrow = models.IntegerField(default=0)    # грусть
    love = models.IntegerField(default=0)      # любовь
    anger = models.IntegerField(default=0)      # гнев
    boredom = models.IntegerField(default=0)    # скука
    happiness = models.IntegerField(default=0)  # счастье
    
    # Новые поля для нечёткого анализа (из НИР)
    reaction_time = models.FloatField(null=True, blank=True)  # среднее время реакции в мс
    reaction_times = models.JSONField(default=list)  # все времена реакций для анализа вариабельности
    
    mistakes = models.IntegerField(default=0)  # количество ошибок
    mistake_types = models.JSONField(default=dict)  # типы ошибок {'attention': 2, 'inhibition': 1}
    
    hints_used = models.IntegerField(default=0)  # использование подсказок
    hint_timing = models.JSONField(default=list)  # когда запрашивал подсказки
    
    strategy_type = models.CharField(max_length=50, null=True, blank=True)  # систематический/импульсивный/адаптивный
    
    # Метрики производительности (из раздела 2.1.2)
    accuracy = models.FloatField(default=0.0)  # точность (0-1)
    performance_metrics = models.JSONField(default=dict)  # дополнительные метрики
    
    # Результаты нечёткого анализа
    fuzzy_analysis = models.JSONField(default=dict)  # результаты нечёткой классификации
    
    # Для игры "Раскраска" - сохраняем рисунок
    drawing_data = models.JSONField(null=True, blank=True)  # данные о рисунке (цвета, области)
    final_image = models.ImageField(upload_to='drawings/', null=True, blank=True)
    
    # Для игры "Диалог" - сохраняем ответы
    dialog_answers = models.JSONField(null=True, blank=True)
    
    # Для игры "Выбор" - выбор изображений
    choices = models.JSONField(null=True, blank=True)
    
    date = models.DateTimeField(auto_now_add=True)
    
    def calculate_accuracy(self):
        """Расчёт точности выполнения"""
        if self.mistakes == 0:
            self.accuracy = 1.0
        else:
            total_actions = len(self.reaction_times) if self.reaction_times else 1
            self.accuracy = max(0, 1 - (self.mistakes / total_actions))
    
    def analyze_reaction_variability(self):
        """Анализ вариабельности времени реакции (маркер утомления/импульсивности)"""
        if len(self.reaction_times) < 2:
            return 0
        
        import numpy as np
        return float(np.std(self.reaction_times))
    
    def save(self, *args, **kwargs):
        if not self.accuracy:
            self.calculate_accuracy()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Результат {self.game_type} для {self.user.name} от {self.date.strftime('%d.%m.%Y')}"
    
    class Meta:
        verbose_name = "Результат игры"
        verbose_name_plural = "Результаты игр"
        ordering = ['-date']


class Prescription(models.Model):
    """Рецепт/назначение врача"""
    child = models.ForeignKey(CUsers, on_delete=models.CASCADE, related_name='prescriptions')
    doctor = models.ForeignKey(CUsers, on_delete=models.CASCADE, related_name='prescriptions_written', limit_choices_to={'role': 'doctor'})
    text = models.TextField('текст назначения')
    
    # Типы назначений
    prescription_type = models.CharField('тип', max_length=50, choices=[
        ('medication', 'Лекарство'),
        ('therapy', 'Терапия'),
        ('exercise', 'Упражнение'),
        ('recommendation', 'Рекомендация'),
    ], default='recommendation')
    
    # Для лекарств
    medication_name = models.CharField('название препарата', max_length=200, blank=True)
    dosage = models.CharField('дозировка', max_length=100, blank=True)
    duration = models.CharField('длительность', max_length=100, blank=True)
    
    date_created = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField('активно', default=True)
    
    def __str__(self):
        return f"Назначение для {self.child.name} от {self.date_created.strftime('%d.%m.%Y')}"
    
    class Meta:
        verbose_name = "Назначение"
        verbose_name_plural = "Назначения"
        ordering = ['-date_created']


# ==================== МОДЕЛИ ДЛЯ НЕЧЁТКОЙ ЛОГИКИ (ИЗ НИР) ====================

class FuzzyLinguisticVariable(models.Model):
    """Лингвистическая переменная из НИР (раздел 3.1.1)"""
    name = models.CharField('название', max_length=100)
    description = models.TextField('описание', blank=True)
    
    # Термы и их функции принадлежности
    # Формат: {'низкая': [0,0,0.3,0.5], 'средняя': [0.3,0.5,0.7,0.9], 'высокая': [0.7,0.9,1,1]}
    terms = models.JSONField('термы', default=dict)
    
    # Для какой диагностической цели
    purpose = models.CharField('назначение', max_length=200, blank=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'Лингвистическая переменная'
        verbose_name_plural = 'Лингвистические переменные'


class FuzzyMembershipFunction(models.Model):
    """Функции принадлежности для классов методов (из раздела 3.1.2 НИР)"""
    METHOD_CLASSES = [
        ('traditional_test', 'Стандартизированный тест'),
        ('projective', 'Проективный метод'),
        ('observation', 'Наблюдение'),
        ('digital_game', 'Цифровая игра'),
        ('hybrid', 'Гибридный метод'),
    ]
    
    method_class = models.CharField('класс метода', max_length=50, choices=METHOD_CLASSES)
    variable = models.ForeignKey(FuzzyLinguisticVariable, on_delete=models.CASCADE, related_name='memberships')
    
    # Значения принадлежности к каждому терму
    membership_values = models.JSONField('значения принадлежности', default=dict)
    
    # Обоснование из НИР
    rationale = models.TextField('обоснование', blank=True)
    
    def __str__(self):
        return f"{self.get_method_class_display()} - {self.variable.name}"
    
    class Meta:
        verbose_name = 'Функция принадлежности'
        verbose_name_plural = 'Функции принадлежности'
        unique_together = ['method_class', 'variable']


class DiagnosticProfile(models.Model):
    """Диагностический профиль ребёнка из НИР (радарная диаграмма)"""
    child = models.ForeignKey(CUsers, on_delete=models.CASCADE, related_name='diagnostic_profiles')
    date_created = models.DateTimeField(auto_now_add=True)
    
    # 5 лингвистических переменных из НИР (стр. 20-21)
    # Каждая - JSON с принадлежностью к термам
    diagnostic_depth = models.JSONField('диагностическая глубина', default=dict)
    motivational_potential = models.JSONField('мотивационный потенциал', default=dict)
    objectivity = models.JSONField('объективность и стандартизация', default=dict)
    ecological_validity = models.JSONField('экологическая валидность', default=dict)
    dynamic_assessment = models.JSONField('потенциал для динамической оценки', default=dict)
    
    # Интегральные показатели
    cognitive_style = models.CharField('когнитивный стиль', max_length=50, choices=[
        ('systematic', 'Систематический'),
        ('impulsive', 'Импульсивный'),
        ('adaptive', 'Адаптивный'),
        ('chaotic', 'Хаотичный'),
    ], blank=True)
    
    emotional_profile = models.JSONField('эмоциональный профиль', default=dict)
    
    # Рекомендации на основе анализа
    recommendations = models.TextField('рекомендации', blank=True)
    
    # Ссылка на сырые данные
    based_on_sessions = models.ManyToManyField(GameSession, blank=True, related_name='profiles')
    
    def get_radar_data(self):
        """Получение данных для радарной диаграммы (значения для 'высокой' принадлежности)"""
        return {
            'diagnostic_depth': self.diagnostic_depth.get('высокая', 0) * 100,
            'motivational_potential': self.motivational_potential.get('высокий', 0) * 100,
            'objectivity': self.objectivity.get('высокая', 0) * 100,
            'ecological_validity': self.ecological_validity.get('высокая', 0) * 100,
            'dynamic_assessment': self.dynamic_assessment.get('широкий', 0) * 100,
        }
    
    def get_emotional_summary(self):
        """Сводка по эмоциональному профилю"""
        if not self.emotional_profile:
            return "Нет данных"
        
        # Находим доминирующие эмоции
        emotions = self.emotional_profile
        sorted_emotions = sorted(emotions.items(), key=lambda x: x[1], reverse=True)
        
        return {
            'dominant': sorted_emotions[:3] if len(sorted_emotions) >= 3 else sorted_emotions,
            'all': emotions
        }
    
    def __str__(self):
        return f"Диагностический профиль {self.child.name} от {self.date_created.strftime('%d.%m.%Y')}"
    
    class Meta:
        verbose_name = 'Диагностический профиль'
        verbose_name_plural = 'Диагностические профили'
        ordering = ['-date_created']


class FuzzyInferenceRule(models.Model):
    """Правила нечёткого вывода (для генерации рекомендаций)"""
    name = models.CharField('название', max_length=200)
    condition = models.JSONField('условие')  # {'diagnostic_depth.высокая': '>0.7', 'motivational_potential.низкий': '>0.5'}
    conclusion = models.TextField('заключение')
    recommendation = models.TextField('рекомендация')
    confidence = models.FloatField('уверенность', default=1.0)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'Правило нечёткого вывода'
        verbose_name_plural = 'Правила нечёткого вывода'


class BehaviorPattern(models.Model):
    """Поведенческие паттерны из таблицы 1 НИР"""
    name = models.CharField('название', max_length=100)
    pattern_type = models.CharField('тип', max_length=50, choices=[
        ('strategy', 'Стратегия решения'),
        ('attention', 'Внимание'),
        ('emotion', 'Эмоциональная реакция'),
        ('social', 'Социальное поведение'),
    ])
    
    # Описание паттерна
    description = models.TextField('описание')
    
    # Параметры для нечёткой классификации
    fuzzy_sets = models.JSONField('нечёткие множества', default=dict)
    
    # Связанные игры
    relevant_games = models.JSONField('соответствующие игры', default=list)
    
    def __str__(self):
        return f"{self.get_pattern_type_display()}: {self.name}"
    
    class Meta:
        verbose_name = 'Поведенческий паттерн'
        verbose_name_plural = 'Поведенческие паттерны'


class Subscription(models.Model):
    """Подписки из презентации"""
    user = models.OneToOneField(CUsers, on_delete=models.CASCADE, related_name='subscription')
    
    # Тип подписки
    subscription_type = models.CharField(max_length=50, choices=[
        ('parent_individual', 'Родитель (индивидуальная)'),
        ('parent_family', 'Родитель (семейная)'),
        ('psychologist_individual', 'Психолог (индивидуальный)'),
        ('clinic_small', 'Клиника (до 3 врачей)'),
        ('clinic_medium', 'Клиника (4-10 врачей)'),
        ('clinic_large', 'Клиника (11+ врачей)'),
        ('kindergarten', 'Детский сад'),
    ])
    
    # Параметры подписки
    max_children = models.IntegerField(default=1)  # макс. количество детей
    max_doctors = models.IntegerField(default=1)   # для клиник
    
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    
    # Платежи
    price = models.DecimalField(max_digits=10, decimal_places=2)
    payment_id = models.CharField(max_length=100, blank=True)
    
    def __str__(self):
        return f"{self.user.name} - {self.get_subscription_type_display()}"
    
    class Meta:
        verbose_name = 'Подписка'
        verbose_name_plural = 'Подписки'
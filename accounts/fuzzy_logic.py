"""
Модуль нечёткой логики для диагностики детей
Основан на главе 3 НИР "Сравнительный анализ традиционной и цифровой игровой диагностики детей"
"""

import numpy as np
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime, timedelta
import json
from collections import Counter

from .models import (
    CUsers, GameResult, GameSession, DiagnosticProfile,
    FuzzyLinguisticVariable, BehaviorPattern, FuzzyInferenceRule,
    EMOTIONS
)


class FuzzySet:
    """Нечёткое множество с функцией принадлежности"""
    
    def __init__(self, name: str, membership_function: List[float]):
        """
        Инициализация нечёткого множества
        
        Args:
            name: название терма (например, "низкий", "средний", "высокий")
            membership_function: параметры функции принадлежности
                Для трапециевидной: [a, b, c, d]
                Для треугольной: [a, b, c] (интерпретируется как [a, b, b, c])
        """
        self.name = name
        self.mf = membership_function
        
        # Нормализация до трапециевидной функции
        if len(self.mf) == 3:
            self.a, self.b, self.c = self.mf
            self.d = self.c
        elif len(self.mf) == 4:
            self.a, self.b, self.c, self.d = self.mf
        else:
            raise ValueError("Функция принадлежности должна иметь 3 или 4 параметра")
    
    def membership(self, x: float) -> float:
        """
        Вычисление степени принадлежности x к нечёткому множеству
        
        Args:
            x: значение переменной
            
        Returns:
            степень принадлежности [0, 1]
        """
        if x <= self.a or x >= self.d:
            return 0.0
        elif self.a < x < self.b:
            # Левая сторона трапеции
            return (x - self.a) / (self.b - self.a) if self.b != self.a else 1.0
        elif self.b <= x <= self.c:
            # Верх трапеции
            return 1.0
        elif self.c < x < self.d:
            # Правая сторона трапеции
            return (self.d - x) / (self.d - self.c) if self.d != self.c else 1.0
        return 0.0


class FuzzyVariable:
    """Лингвистическая переменная с набором термов"""
    
    def __init__(self, name: str, terms: Dict[str, List[float]]):
        """
        Инициализация лингвистической переменной
        
        Args:
            name: название переменной
            terms: словарь {название_терма: функция_принадлежности}
        """
        self.name = name
        self.terms = {term: FuzzySet(term, mf) for term, mf in terms.items()}
    
    def fuzzify(self, value: float) -> Dict[str, float]:
        """
        Фаззификация значения - определение принадлежности к каждому терму
        
        Args:
            value: чёткое значение переменной
            
        Returns:
            словарь {терм: степень_принадлежности}
        """
        return {term: fuzzy_set.membership(value) for term, fuzzy_set in self.terms.items()}
    
    def defuzzify_centroid(self, memberships: Dict[str, float]) -> float:
        """
        Дефаззификация методом центра тяжести
        
        Args:
            memberships: степени принадлежности к термам
            
        Returns:
            чёткое значение
        """
        total_area = 0
        weighted_sum = 0
        
        for term, membership in memberships.items():
            if membership > 0:
                fuzzy_set = self.terms[term]
                # Центр тяжести трапеции
                center = (fuzzy_set.b + fuzzy_set.c) / 2
                area = membership * (fuzzy_set.d - fuzzy_set.a) / 2
                weighted_sum += center * area
                total_area += area
        
        return weighted_sum / total_area if total_area > 0 else 0


class FuzzyAnalyzer:
    """
    Основной класс для нечёткого анализа диагностических данных
    Реализует методы из разделов 2.2, 3.1 и 3.5 НИР
    """
    
    # Предопределённые лингвистические переменные из НИР (раздел 3.1.1)
    LINGUISTIC_VARIABLES = {
        'diagnostic_depth': {
            'name': 'Диагностическая глубина',
            'terms': {
                'низкая': [0, 0, 0.3, 0.4],
                'средняя': [0.3, 0.5, 0.7, 0.8],
                'высокая': [0.7, 0.8, 1, 1]
            }
        },
        'motivational_potential': {
            'name': 'Мотивационный потенциал',
            'terms': {
                'низкий': [0, 0, 0.2, 0.3],
                'умеренный': [0.2, 0.4, 0.6, 0.7],
                'высокий': [0.6, 0.8, 1, 1]
            }
        },
        'objectivity': {
            'name': 'Объективность и стандартизация',
            'terms': {
                'низкая': [0, 0, 0.2, 0.3],
                'средняя': [0.2, 0.4, 0.6, 0.7],
                'высокая': [0.6, 0.8, 1, 1]
            }
        },
        'ecological_validity': {
            'name': 'Экологическая валидность',
            'terms': {
                'низкая': [0, 0, 0.2, 0.3],
                'средняя': [0.2, 0.4, 0.6, 0.7],
                'высокая': [0.6, 0.8, 1, 1]
            }
        },
        'dynamic_assessment': {
            'name': 'Потенциал для динамической оценки',
            'terms': {
                'ограниченный': [0, 0, 0.2, 0.3],
                'умеренный': [0.2, 0.4, 0.6, 0.7],
                'широкий': [0.6, 0.8, 1, 1]
            }
        },
        'impulsivity': {
            'name': 'Уровень импульсивности',
            'terms': {
                'низкий': [0, 0, 300, 400],
                'средний': [300, 400, 600, 700],
                'высокий': [600, 800, 2000, 2000]
            }
        },
        'cognitive_activity': {
            'name': 'Познавательная активность',
            'terms': {
                'исследующая': [0, 0, 2, 3],
                'направленная': [2, 3, 5, 6],
                'зависимая': [5, 7, 10, 10]
            }
        }
    }
    
    def __init__(self):
        """Инициализация с созданием лингвистических переменных"""
        self.variables = {}
        for var_name, var_data in self.LINGUISTIC_VARIABLES.items():
            self.variables[var_name] = FuzzyVariable(
                var_data['name'],
                var_data['terms']
            )
    
    # ==================== МЕТОДЫ ДЛЯ АНАЛИЗА ПОВЕДЕНЧЕСКИХ ДАННЫХ ====================
    
    def analyze_reaction_times(self, reaction_times: List[float]) -> Dict[str, float]:
        """
        Анализ времени реакции (раздел 2.2.1 НИР)
        
        Args:
            reaction_times: список времени реакции в мс
            
        Returns:
            степени принадлежности к уровням импульсивности
        """
        if not reaction_times:
            return {'низкий': 0, 'средний': 0, 'высокий': 0}
        
        avg_time = np.mean(reaction_times)
        std_time = np.std(reaction_times)
        
        # Коэффициент вариации - маркер стабильности внимания
        cv = std_time / avg_time if avg_time > 0 else 0
        
        # Анализ импульсивности по среднему времени реакции
        impulsivity = self.variables['impulsivity'].fuzzify(avg_time)
        
        # Корректировка на основе вариабельности
        if cv > 0.3:  # Высокая вариабельность - признак нестабильности
            impulsivity['высокий'] = min(1, impulsivity['высокий'] + 0.2)
        
        return impulsivity
    
    def analyze_hint_usage(self, hints_used: int, total_actions: int, 
                          hint_timing: List[float]) -> Dict[str, float]:
        """
        Анализ использования подсказок (частота проверки подсказок из раздела 2.2.1)
        
        Args:
            hints_used: количество использованных подсказок
            total_actions: общее количество действий
            hint_timing: временные метки запроса подсказок (в секундах от начала)
            
        Returns:
            степени принадлежности к типам познавательной активности
        """
        if total_actions == 0:
            return {'исследующая': 0, 'направленная': 0, 'зависимая': 0}
        
        # Нормализованная частота запросов
        hint_frequency = hints_used / total_actions * 10  # масштабируем до 0-10
        
        # Анализ по частоте
        activity = self.variables['cognitive_activity'].fuzzify(hint_frequency)
        
        # Анализ временного паттерна
        if hint_timing and len(hint_timing) > 1:
            # Если подсказки запрашиваются в начале - исследующая
            if np.mean(hint_timing) < total_actions * 0.3:
                activity['исследующая'] = min(1, activity['исследующая'] + 0.2)
            
            # Если подсказки после каждой попытки - зависимая
            if len(hint_timing) > 3 and max(hint_timing) - min(hint_timing) < total_actions * 0.5:
                activity['зависимая'] = min(1, activity['зависимая'] + 0.3)
        
        return activity
    
    def analyze_strategy(self, game_results: List[GameResult]) -> str:
        """
        Определение стратегии решения (раздел 2.4.2 НИР)
        
        Returns:
            тип стратегии: 'systematic', 'impulsive', 'adaptive', 'chaotic'
        """
        if not game_results:
            return 'unknown'
        
        # Собираем данные о стратегиях из всех результатов
        strategies = []
        
        for result in game_results:
            if result.strategy_type:
                strategies.append(result.strategy_type)
            
            # Анализ паттерна ошибок
            if hasattr(result, 'mistake_types') and result.mistake_types:
                mistake_types = result.mistake_types
                
                # Определяем стратегию по типу ошибок
                if mistake_types.get('inhibition', 0) > mistake_types.get('attention', 0):
                    strategies.append('impulsive')
                elif mistake_types.get('attention', 0) > mistake_types.get('inhibition', 0):
                    strategies.append('systematic')
        
        if not strategies:
            return 'unknown'
        
        # Находим наиболее частую стратегию
        counter = Counter(strategies)
        return counter.most_common(1)[0][0]
    
    def analyze_error_patterns(self, game_results: List[GameResult]) -> Dict[str, Any]:
        """
        Анализ паттернов ошибок (из таблицы 1 НИР)
        
        Returns:
            словарь с анализом ошибок
        """
        total_mistakes = sum(r.mistakes for r in game_results)
        total_actions = sum(len(r.reaction_times) for r in game_results if r.reaction_times)
        
        if total_actions == 0:
            return {
                'error_rate': 0,
                'pattern': 'no_data',
                'classification': {'систематический': 0, 'импульсивный': 0, 'случайный': 0}
            }
        
        error_rate = total_mistakes / total_actions
        
        # Нечёткая классификация по таблице 1
        if error_rate < 0.1:
            systematic = 1.0
            impulsive = 0.0
            random = 0.0
            pattern = 'systematic'
        elif error_rate < 0.2:
            systematic = 0.7
            impulsive = 0.3
            random = 0.0
            pattern = 'systematic_light'
        elif error_rate < 0.3:
            systematic = 0.2
            impulsive = 0.7
            random = 0.1
            pattern = 'impulsive'
        else:
            systematic = 0.0
            impulsive = 0.3
            random = 0.8
            pattern = 'random'
        
        # Дополнительный анализ по типам ошибок
        error_types = {}
        for result in game_results:
            if hasattr(result, 'mistake_types') and result.mistake_types:
                for err_type, count in result.mistake_types.items():
                    error_types[err_type] = error_types.get(err_type, 0) + count
        
        return {
            'error_rate': error_rate,
            'total_mistakes': total_mistakes,
            'pattern': pattern,
            'classification': {
                'систематический': systematic,
                'импульсивный': impulsive,
                'случайный': random
            },
            'error_types': error_types
        }
    
    # ==================== МЕТОДЫ ДЛЯ РАСЧЁТА ЛИНГВИСТИЧЕСКИХ ПЕРЕМЕННЫХ ====================
    
    def calculate_diagnostic_depth(self, game_results: List[GameResult]) -> Dict[str, float]:
        """
        Расчёт диагностической глубины (лингвистическая переменная А из НИР)
        
        Args:
            game_results: результаты игр ребёнка
            
        Returns:
            принадлежность к термам 'низкая', 'средняя', 'высокая'
        """
        if not game_results:
            return {'низкая': 0.5, 'средняя': 0.5, 'высокая': 0}
        
        # Факторы, влияющие на диагностическую глубину:
        # 1. Разнообразие игр
        game_types = set(r.game_type for r in game_results)
        diversity = len(game_types) / 3  # максимум 3 типа игр
        
        # 2. Наличие поведенческих траекторий
        has_trajectories = any(r.behavior_trajectory for r in game_results)
        
        # 3. Детализация результатов (наличие дополнительных метрик)
        has_detailed = any(
            r.reaction_times or r.mistake_types or r.performance_metrics
            for r in game_results
        )
        
        # 4. Количество сессий
        sessions_count = min(len(game_results) / 5, 1)  # нормализуем до 1
        
        # Интегральный показатель (0-1)
        depth_score = (
            diversity * 0.3 +
            (1 if has_trajectories else 0) * 0.3 +
            (1 if has_detailed else 0) * 0.25 +
            sessions_count * 0.15
        )
        
        # Фаззификация
        var = FuzzyVariable('diagnostic_depth', self.LINGUISTIC_VARIABLES['diagnostic_depth']['terms'])
        return var.fuzzify(depth_score)
    
    def calculate_motivation(self, game_results: List[GameResult]) -> Dict[str, float]:
        """
        Расчёт мотивационного потенциала (лингвистическая переменная В из НИР)
        
        Args:
            game_results: результаты игр ребёнка
            
        Returns:
            принадлежность к термам 'низкий', 'умеренный', 'высокий'
        """
        if not game_results:
            return {'низкий': 0.5, 'умеренный': 0.5, 'высокий': 0}
        
        # Индикаторы мотивации:
        # 1. Завершённые сессии
        completed_sessions = sum(1 for r in game_results if r.session and r.session.completed)
        completion_rate = completed_sessions / len(game_results) if game_results else 0
        
        # 2. Время, проведённое в игре
        total_time = 0
        for r in game_results:
            if r.session and r.session.end_time and r.session.start_time:
                session_time = (r.session.end_time - r.session.start_time).total_seconds()
                total_time += session_time
        
        avg_time = total_time / len(game_results) if game_results else 0
        time_score = min(avg_time / 300, 1)  # 5 минут = максимум
        
        # 3. Использование дополнительных функций (подсказки - не всегда плохо)
        hint_usage = sum(r.hints_used for r in game_results) / len(game_results) if game_results else 0
        # Нормализованный показатель (умеренное использование = хорошо)
        hint_score = 1 - abs(hint_usage - 2) / 5 if hint_usage else 0.5
        
        # 4. Прогресс в играх (улучшение результатов)
        if len(game_results) >= 2:
            first_joy = game_results[0].joy if hasattr(game_results[0], 'joy') else 0
            last_joy = game_results[-1].joy if hasattr(game_results[-1], 'joy') else 0
            progress = min((last_joy - first_joy) / 10 + 0.5, 1) if last_joy > first_joy else 0.3
        else:
            progress = 0.5
        
        # Интегральный показатель
        motivation_score = (
            completion_rate * 0.3 +
            time_score * 0.3 +
            max(0, hint_score) * 0.2 +
            progress * 0.2
        )
        
        # Фаззификация
        var = FuzzyVariable('motivational_potential', self.LINGUISTIC_VARIABLES['motivational_potential']['terms'])
        return var.fuzzify(motivation_score)
    
    def calculate_objectivity(self, game_results: List[GameResult]) -> Dict[str, float]:
        """
        Расчёт объективности и стандартизации (лингвистическая переменная С из НИР)
        Для цифровых методов всегда высокая, но учитываем качество данных
        """
        if not game_results:
            return {'низкая': 0.1, 'средняя': 0.3, 'высокая': 0.6}
        
        # Для цифровых игр объективность высокая по умолчанию
        base_score = 0.8
        
        # Но может снижаться при проблемах с данными
        data_quality = 1.0
        
        # Проверяем наличие объективных метрик
        has_reaction_times = any(r.reaction_times for r in game_results)
        has_accuracy = any(r.accuracy > 0 for r in game_results)
        
        if not has_reaction_times:
            data_quality -= 0.1
        if not has_accuracy:
            data_quality -= 0.1
        
        objectivity_score = base_score * data_quality
        
        # Фаззификация
        var = FuzzyVariable('objectivity', self.LINGUISTIC_VARIABLES['objectivity']['terms'])
        return var.fuzzify(objectivity_score)
    
    def calculate_ecological_validity(self, game_results: List[GameResult]) -> Dict[str, float]:
        """
        Расчёт экологической валидности (лингвистическая переменная D из НИР)
        """
        if not game_results:
            return {'низкая': 0.2, 'средняя': 0.5, 'высокая': 0.3}
        
        # Факторы экологической валидности:
        # 1. Естественность игрового контекста
        context_score = 0.8  # игры по умолчанию экологичны
        
        # 2. Отсутствие вмешательства взрослых
        has_sessions = any(r.session for r in game_results)
        
        # 3. Свобода действий в игре
        has_choices = any(r.choices for r in game_results)
        
        if has_choices:
            context_score += 0.1
        
        ecological_score = min(context_score, 1.0)
        
        # Фаззификация
        var = FuzzyVariable('ecological_validity', self.LINGUISTIC_VARIABLES['ecological_validity']['terms'])
        return var.fuzzify(ecological_score)
    
    def calculate_dynamic_assessment(self, game_results: List[GameResult]) -> Dict[str, float]:
        """
        Расчёт потенциала для динамической оценки (лингвистическая переменная Е из НИР)
        """
        if not game_results:
            return {'ограниченный': 0.3, 'умеренный': 0.5, 'широкий': 0.2}
        
        # Факторы динамической оценки:
        # 1. Наличие временных рядов
        has_trajectories = any(r.behavior_trajectory for r in game_results)
        
        # 2. Множество точек измерения
        multiple_points = len(game_results) >= 3
        
        # 3. Вариативность заданий
        game_types = len(set(r.game_type for r in game_results))
        
        dynamic_score = (
            (1 if has_trajectories else 0) * 0.4 +
            (1 if multiple_points else 0) * 0.3 +
            (game_types / 3) * 0.3
        )
        
        # Фаззификация
        var = FuzzyVariable('dynamic_assessment', self.LINGUISTIC_VARIABLES['dynamic_assessment']['terms'])
        return var.fuzzify(dynamic_score)
    
    # ==================== МЕТОДЫ ДЛЯ ЭМОЦИОНАЛЬНОГО АНАЛИЗА ====================
    
    def analyze_emotions(self, game_results: List[GameResult]) -> Dict[str, float]:
        """
        Анализ эмоционального профиля ребёнка
        
        Returns:
            нормализованный словарь эмоций
        """
        emotion_sums = {emotion: 0 for emotion in EMOTIONS}
        emotion_sums.update({
            'гнев': sum(r.anger for r in game_results),
            'скука': sum(r.boredom for r in game_results),
            'радость': sum(r.joy for r in game_results),
            'счастье': sum(r.happiness for r in game_results),
            'грусть': sum(r.sorrow for r in game_results),
            'любовь': sum(r.love for r in game_results),
        })
        
        total = sum(emotion_sums.values())
        if total == 0:
            return {emotion: 0 for emotion in EMOTIONS}
        
        # Нормализация
        return {emotion: value / total for emotion, value in emotion_sums.items()}
    
    def detect_emotional_trends(self, game_results: List[GameResult]) -> Dict[str, Any]:
        """
        Выявление трендов в эмоциональном состоянии
        """
        if len(game_results) < 2:
            return {'trend': 'insufficient_data'}
        
        # Сортируем по дате
        sorted_results = sorted(game_results, key=lambda x: x.date)
        
        trends = {}
        for emotion in EMOTIONS:
            values = [getattr(r, emotion, 0) for r in sorted_results]
            if len(values) >= 2:
                # Простой линейный тренд
                first_half = sum(values[:len(values)//2]) / (len(values)//2)
                second_half = sum(values[len(values)//2:]) / (len(values) - len(values)//2)
                
                if second_half > first_half * 1.2:
                    trends[emotion] = 'increasing'
                elif second_half < first_half * 0.8:
                    trends[emotion] = 'decreasing'
                else:
                    trends[emotion] = 'stable'
        
        return trends
    
    # ==================== ОСНОВНОЙ МЕТОД СОЗДАНИЯ ПРОФИЛЯ ====================
    
    def create_diagnostic_profile(self, child_id: int) -> DiagnosticProfile:
        """
        Создание диагностического профиля ребёнка (раздел 3.1.3 НИР)
        
        Args:
            child_id: ID ребёнка
            
        Returns:
            созданный профиль DiagnosticProfile
        """
        child = CUsers.objects.get(id=child_id, role='child')
        game_results = list(GameResult.objects.filter(user=child).select_related('session'))
        
        if not game_results:
            # Создаём пустой профиль, если нет данных
            return DiagnosticProfile.objects.create(
                child=child,
                diagnostic_depth={'низкая': 0.3, 'средняя': 0.5, 'высокая': 0.2},
                motivational_potential={'низкий': 0.3, 'умеренный': 0.5, 'высокий': 0.2},
                objectivity={'низкая': 0.1, 'средняя': 0.3, 'высокая': 0.6},
                ecological_validity={'низкая': 0.2, 'средняя': 0.4, 'высокая': 0.4},
                dynamic_assessment={'ограниченный': 0.2, 'умеренный': 0.4, 'широкий': 0.4},
                emotional_profile=self.analyze_emotions([]),
                recommendations="Недостаточно данных для анализа. Проведите больше игровых сессий."
            )
        
        # Расчёт лингвистических переменных
        diagnostic_depth = self.calculate_diagnostic_depth(game_results)
        motivational_potential = self.calculate_motivation(game_results)
        objectivity = self.calculate_objectivity(game_results)
        ecological_validity = self.calculate_ecological_validity(game_results)
        dynamic_assessment = self.calculate_dynamic_assessment(game_results)
        
        # Анализ стратегии
        cognitive_style = self.analyze_strategy(game_results)
        
        # Эмоциональный анализ
        emotional_profile = self.analyze_emotions(game_results)
        emotional_trends = self.detect_emotional_trends(game_results)
        emotional_profile['trends'] = emotional_trends
        
        # Генерация рекомендаций
        recommendations = self.generate_recommendations(
            diagnostic_depth, motivational_potential,
            objectivity, ecological_validity, dynamic_assessment,
            emotional_profile, cognitive_style
        )
        
        # Создание профиля
        profile = DiagnosticProfile.objects.create(
            child=child,
            diagnostic_depth=diagnostic_depth,
            motivational_potential=motivational_potential,
            objectivity=objectivity,
            ecological_validity=ecological_validity,
            dynamic_assessment=dynamic_assessment,
            cognitive_style=cognitive_style,
            emotional_profile=emotional_profile,
            recommendations=recommendations
        )
        
        # Привязываем сессии
        sessions = GameSession.objects.filter(user=child)
        profile.based_on_sessions.set(sessions)
        
        return profile
    
    # ==================== ГЕНЕРАЦИЯ РЕКОМЕНДАЦИЙ ====================
    
    def generate_recommendations(self, *args, **kwargs) -> str:
        """
        Генерация рекомендаций на основе нечёткого анализа
        """
        recommendations = []
        
        diagnostic_depth = kwargs.get('diagnostic_depth', {})
        motivational = kwargs.get('motivational_potential', {})
        emotional = kwargs.get('emotional_profile', {})
        cognitive_style = kwargs.get('cognitive_style', 'unknown')
        
        # Рекомендации по диагностической глубине
        if diagnostic_depth.get('высокая', 0) < 0.5:
            recommendations.append(
                "✅ Рекомендуется провести дополнительные игровые сессии для углублённой диагностики. "
                "Разнообразьте типы игр для получения более полной картины."
            )
        
        # Рекомендации по мотивации
        if motivational.get('низкий', 0) > 0.6:
            recommendations.append(
                "⚠️ Наблюдается сниженная мотивация к выполнению заданий. "
                "Рекомендуется использовать более короткие игровые сессии и добавлять элементы поощрения."
            )
        elif motivational.get('высокий', 0) > 0.7:
            recommendations.append(
                "🌟 Ребёнок проявляет высокую мотивацию к игровой диагностике. "
                "Это создаёт благоприятные условия для получения достоверных результатов."
            )
        
        # Рекомендации по когнитивному стилю
        if cognitive_style == 'impulsive':
            recommendations.append(
                "🧠 Выявлен импульсивный стиль решения задач. "
                "Рекомендуются упражнения на развитие самоконтроля и внимания: "
                "игры на последовательное выполнение инструкций, задания с отсроченным ответом."
            )
        elif cognitive_style == 'systematic':
            recommendations.append(
                "📊 Ребёнок демонстрирует систематический подход к решению задач. "
                "Это указывает на хорошее развитие планирования и контроля. "
                "Поддерживайте этот стиль, предлагая задачи с возрастающей сложностью."
            )
        elif cognitive_style == 'adaptive':
            recommendations.append(
                "🎯 Отмечается адаптивный стиль - ребёнок успешно меняет стратегии при изменении условий. "
                "Это признак гибкости мышления. Рекомендуются задания, требующие переключения между правилами."
            )
        
        # Эмоциональные рекомендации
        if emotional:
            dominant_emotions = sorted(emotional.items(), key=lambda x: x[1], reverse=True)[:3]
            dominant = [e[0] for e in dominant_emotions if e[0] not in ['trends', 'радость', 'счастье', 'любовь']]
            
            if 'гнев' in dominant and emotional.get('гнев', 0) > 0.3:
                recommendations.append(
                    "😠 Повышенный уровень гнева может указывать на фрустрацию. "
                    "Рекомендуется включать в занятия элементы релаксации и упражнения на выражение эмоций."
                )
            
            if 'грусть' in dominant and emotional.get('грусть', 0) > 0.3:
                recommendations.append(
                    "😔 Преобладание грусти в эмоциональном профиле. "
                    "Рекомендуется консультация психолога для выяснения причин."
                )
            
            if 'скука' in dominant and emotional.get('скука', 0) > 0.3:
                recommendations.append(
                    "😐 Высокий уровень скуки может свидетельствовать о недостаточной сложности заданий. "
                    "Попробуйте увеличить уровень сложности игр или разнообразить их."
                )
        
        # Общая рекомендация
        if not recommendations:
            recommendations.append(
                "👍 Эмоциональный и когнитивный профиль в норме. "
                "Продолжайте регулярные игровые сессии для мониторинга динамики развития."
            )
        
        return "\n\n".join(recommendations)


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def init_fuzzy_variables():
    """
    Инициализация лингвистических переменных в БД
    (для первоначальной настройки)
    """
    for var_name, var_data in FuzzyAnalyzer.LINGUISTIC_VARIABLES.items():
        FuzzyLinguisticVariable.objects.get_or_create(
            name=var_data['name'],
            defaults={
                'description': f'Лингвистическая переменная из НИР: {var_name}',
                'terms': var_data['terms'],
                'purpose': 'Диагностика когнитивных и эмоциональных процессов'
            }
        )
    
    # Функции принадлежности для классов методов (раздел 3.1.2)
    memberships = [
        # Для традиционных стандартизированных тестов
        ('traditional_test', 'Диагностическая глубина', {'низкая': 0.1, 'средняя': 0.8, 'высокая': 0.5}),
        ('traditional_test', 'Мотивационный потенциал', {'низкий': 0.8, 'умеренный': 0.3, 'высокий': 0.1}),
        ('traditional_test', 'Объективность и стандартизация', {'низкая': 0.1, 'средняя': 0.8, 'высокая': 0.5}),
        
        # Для цифровых игр
        ('digital_game', 'Диагностическая глубина', {'низкая': 0.2, 'средняя': 0.5, 'высокая': 0.6}),
        ('digital_game', 'Мотивационный потенциал', {'низкий': 0.1, 'умеренный': 0.3, 'высокий': 0.9}),
        ('digital_game', 'Объективность и стандартизация', {'низкая': 0.0, 'средняя': 0.2, 'высокая': 0.9}),
        
        # Для наблюдения
        ('observation', 'Диагностическая глубина', {'низкая': 0.2, 'средняя': 0.4, 'высокая': 0.7}),
        ('observation', 'Объективность и стандартизация', {'низкая': 0.9, 'средняя': 0.3, 'высокая': 0.0}),
    ]
    
    for method_class, var_name, values in memberships:
        try:
            variable = FuzzyLinguisticVariable.objects.get(name=var_name)
            FuzzyMembershipFunction.objects.update_or_create(
                method_class=method_class,
                variable=variable,
                defaults={'membership_values': values}
            )
        except FuzzyLinguisticVariable.DoesNotExist:
            pass


def create_sample_rules():
    """
    Создание примеров правил нечёткого вывода
    """
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
    ]
    
    for rule_data in rules:
        FuzzyInferenceRule.objects.get_or_create(
            name=rule_data['name'],
            defaults=rule_data
        )
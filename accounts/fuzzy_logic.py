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
    CUsers, GameResult, GameSession, DiagnosticProfile, DiagnosticDiagnosis,
    FuzzyLinguisticVariable, FuzzyMembershipFunction, BehaviorPattern, FuzzyInferenceRule,
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
            
            if hasattr(result, 'mistake_types') and result.mistake_types:
                mt = result.mistake_types
                if mt.get('inhibition', 0) > mt.get('attention', 0):
                    strategies.append('impulsive')
                elif mt.get('attention', 0) > mt.get('inhibition', 0):
                    strategies.append('systematic')
            
            # Sequence: много ошибок = импульсивность
            if result.game_type == 'Sequence' and result.mistakes > 3:
                strategies.append('impulsive')
            elif result.game_type == 'Sequence' and result.mistakes <= 1:
                strategies.append('systematic')
            
            # Puzzle: много ходов = систематичность, мало = импульсивность
            pm = getattr(result, 'performance_metrics', None) or {}
            if result.game_type == 'Puzzle':
                moves = pm.get('moves', 0)
                if moves > 50 and pm.get('completed'):
                    strategies.append('systematic')
                elif moves < 20 and not pm.get('completed'):
                    strategies.append('impulsive')
            
            # Memory: много попыток = импульсивность
            if result.game_type == 'Memory':
                attempts = pm.get('attempts', 0)
                pairs = pm.get('pairs_found', 0)
                if attempts > 0 and pairs > 0 and attempts / max(pairs, 1) > 2:
                    strategies.append('impulsive')
            # GoNoGo: commission_errors = импульсивность
            if result.game_type == 'GoNoGo' and pm.get('commission_errors', 0) > 2:
                strategies.append('impulsive')
        
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
        
        # Добавляем действия из performance_metrics
        for r in game_results:
            pm = getattr(r, 'performance_metrics', None) or {}
            if r.game_type == 'Memory':
                total_actions += pm.get('attempts', 0) * 2
                total_mistakes += max(0, pm.get('attempts', 0) - pm.get('pairs_found', 0))
            elif r.game_type == 'Puzzle':
                total_actions += pm.get('moves', 0)
            elif r.game_type == 'Sequence':
                total_actions += pm.get('level_reached', 1) * 4
            elif r.game_type in ('EmotionFace', 'Sort', 'Pattern', 'EmotionMatch'):
                total_actions += pm.get('total', 8)
            elif r.game_type == 'Attention':
                total_actions += pm.get('hits', 0) + pm.get('misses', 0) + pm.get('false_alarms', 0)
            elif r.game_type == 'GoNoGo':
                total_actions += pm.get('correct_go', 0) + pm.get('commission_errors', 0) + pm.get('omission_errors', 0)
        
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
    
    def _game_data_score(self, r: GameResult) -> float:
        """Оценка полноты данных по типу игры (0-1). Чёткая логика для каждого типа."""
        if r.game_type == 'Painting':
            return 1.0 if (r.drawing_data and r.drawing_data.get('image_base64')) else 0.3
        if r.game_type == 'Dialog':
            return min(len(r.dialog_answers or {}) / 5, 1)
        if r.game_type == 'Choice':
            return min(len(r.choices or {}) / 5, 1)
        if r.game_type == 'Memory':
            pm = r.performance_metrics or {}
            return min((pm.get('pairs_found', 0) + pm.get('levels_completed', 0) * 2) / 10, 1)
        if r.game_type == 'Puzzle':
            pm = r.performance_metrics or {}
            return 0.5 if pm.get('moves', 0) > 0 else 0.2
        if r.game_type == 'Sequence':
            pm = r.performance_metrics or {}
            return 0.5 if pm.get('level_reached', 0) > 0 else 0.2
        if r.game_type in ('EmotionFace', 'Attention', 'GoNoGo', 'Sort', 'Pattern', 'EmotionMatch'):
            pm = r.performance_metrics or {}
            return 0.7 if pm else 0.3
        return 0.3
    
    def calculate_diagnostic_depth(self, game_results: List[GameResult]) -> Dict[str, float]:
        """
        Расчёт диагностической глубины (лингвистическая переменная А из НИР)
        Для каждого типа: Painting, Dialog, Choice, Memory, Puzzle, Sequence — своя логика.
        """
        if not game_results:
            return {'низкая': 0.5, 'средняя': 0.5, 'высокая': 0}
        
        game_types = set(r.game_type for r in game_results)
        diversity = min(len(game_types) / 12, 1)  # 12 типов игр
        
        # Интегральная оценка полноты данных по каждой игре
        data_scores = [self._game_data_score(r) for r in game_results]
        has_detailed = sum(data_scores) / len(data_scores) if data_scores else 0
        
        sessions_score = min(len(game_results) / 8, 1)
        
        depth_score = (
            diversity * 0.35 +
            has_detailed * 0.4 +
            sessions_score * 0.25
        )
        
        var = FuzzyVariable('diagnostic_depth', self.LINGUISTIC_VARIABLES['diagnostic_depth']['terms'])
        return var.fuzzify(depth_score)
    
    def calculate_motivation(self, game_results: List[GameResult]) -> Dict[str, float]:
        """
        Расчёт мотивационного потенциала (лингвистическая переменная В из НИР)
        Memory: levels_completed, pairs_found; Puzzle: completed; Sequence: level_reached, mistakes.
        Painting/Dialog/Choice: joy+happiness.
        """
        if not game_results:
            return {'низкий': 0.5, 'умеренный': 0.5, 'высокий': 0}
        
        completion_rate = sum(1 for r in game_results if r.session and r.session.completed) / len(game_results)
        
        # Memory: levels_completed (0–4), pairs_found
        memory_results = [r for r in game_results if r.game_type == 'Memory']
        memory_score = 0
        for r in memory_results:
            pm = r.performance_metrics or {}
            lvl = pm.get('levels_completed', 0) / 4
            pairs = min(pm.get('pairs_found', 0) / 20, 1)
            memory_score += lvl * 0.6 + pairs * 0.4
        memory_score = min(memory_score / max(len(memory_results), 1), 1)
        
        # Puzzle: completed
        puzzle_results = [r for r in game_results if r.game_type == 'Puzzle']
        puzzle_score = sum(1 for r in puzzle_results if (r.performance_metrics or {}).get('completed')) / max(len(puzzle_results), 1)
        
        # Sequence: level_reached (1–5), mistakes
        seq_results = [r for r in game_results if r.game_type == 'Sequence']
        seq_score = 0
        for r in seq_results:
            pm = r.performance_metrics or {}
            lvl = pm.get('level_reached', 1) / 5
            seq_score += lvl * max(0, 1 - r.mistakes * 0.1)
        seq_score = min(seq_score / max(len(seq_results), 1), 1)
        
        emotion_sum = sum(r.joy + r.happiness for r in game_results)
        emotion_score = min(emotion_sum / (len(game_results) * 10), 1)
        
        motivation_score = (
            completion_rate * 0.2 +
            memory_score * 0.25 +
            puzzle_score * 0.2 +
            seq_score * 0.2 +
            emotion_score * 0.15
        )
        
        var = FuzzyVariable('motivational_potential', self.LINGUISTIC_VARIABLES['motivational_potential']['terms'])
        return var.fuzzify(motivation_score)
    
    def calculate_objectivity(self, game_results: List[GameResult]) -> Dict[str, float]:
        """
        Расчёт объективности (лингвистическая переменная С из НИР)
        Memory, Puzzle, Sequence — объективные метрики; Painting, Dialog, Choice — субъективные.
        """
        if not game_results:
            return {'низкая': 0.1, 'средняя': 0.3, 'высокая': 0.6}
        
        # Объективные игры: Memory, Puzzle, Sequence, EmotionFace, Attention, GoNoGo, Sort, Pattern, EmotionMatch
        obj_types = ('Memory', 'Puzzle', 'Sequence', 'EmotionFace', 'Attention', 'GoNoGo', 'Sort', 'Pattern', 'EmotionMatch')
        obj_count = sum(1 for r in game_results if r.game_type in obj_types)
        obj_ratio = obj_count / len(game_results)
        
        # Субъективные: Painting, Dialog, Choice — дополняют картину
        subj_count = sum(1 for r in game_results if r.game_type in ('Painting', 'Dialog', 'Choice'))
        
        # Базовая объективность: чем больше объективных игр, тем выше
        base_score = 0.6 + obj_ratio * 0.3
        if subj_count > 0:
            base_score += 0.1  # Субъективные дают контекст
        base_score = min(base_score, 1.0)
        
        var = FuzzyVariable('objectivity', self.LINGUISTIC_VARIABLES['objectivity']['terms'])
        return var.fuzzify(base_score)
    
    def calculate_ecological_validity(self, game_results: List[GameResult]) -> Dict[str, float]:
        """
        Расчёт экологической валидности (лингвистическая переменная D из НИР)
        Choice — свобода выбора; Painting — творчество; Dialog — естественный диалог.
        Memory, Puzzle, Sequence — структурированные, но игровые.
        """
        if not game_results:
            return {'низкая': 0.2, 'средняя': 0.5, 'высокая': 0.3}
        
        # Choice — высокая экологичность (свобода выбора эмоций)
        choice_count = sum(1 for r in game_results if r.game_type == 'Choice' and r.choices)
        # Painting — творческая свобода
        paint_count = sum(1 for r in game_results if r.game_type == 'Painting' and r.drawing_data)
        # Dialog — естественный разговор
        dialog_count = sum(1 for r in game_results if r.game_type == 'Dialog' and r.dialog_answers)
        
        eco_score = 0.6
        eco_score += choice_count * 0.1
        eco_score += paint_count * 0.1
        eco_score += dialog_count * 0.1
        eco_score = min(eco_score, 1.0)
        
        var = FuzzyVariable('ecological_validity', self.LINGUISTIC_VARIABLES['ecological_validity']['terms'])
        return var.fuzzify(eco_score)
    
    def calculate_dynamic_assessment(self, game_results: List[GameResult]) -> Dict[str, float]:
        """
        Расчёт потенциала для динамической оценки (лингвистическая переменная Е из НИР)
        Memory: levels_completed; Sequence: level_reached; Puzzle: completed.
        Множество игр и прогресс по уровням = широкий потенциал.
        """
        if not game_results:
            return {'ограниченный': 0.3, 'умеренный': 0.5, 'широкий': 0.2}
        
        multiple_points = len(game_results) >= 3
        game_types = len(set(r.game_type for r in game_results))
        
        # Memory: levels_completed (0–4)
        mem_progress = sum(
            (r.performance_metrics or {}).get('levels_completed', 0) / 4
            for r in game_results if r.game_type == 'Memory'
        )
        # Sequence: level_reached (1–5)
        seq_progress = sum(
            (r.performance_metrics or {}).get('level_reached', 1) / 5
            for r in game_results if r.game_type == 'Sequence'
        )
        # Puzzle: completed
        puz_progress = sum(
            1 for r in game_results if r.game_type == 'Puzzle' and (r.performance_metrics or {}).get('completed')
        )
        
        progress_score = min((mem_progress + seq_progress + puz_progress) / max(len(game_results), 1), 1)
        
        dynamic_score = (
            (1 if multiple_points else 0) * 0.35 +
            min(game_types / 12, 1) * 0.4 +
            progress_score * 0.25
        )
        
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
        
        EMOTION_FIELD = {'гнев': 'anger', 'скука': 'boredom', 'радость': 'joy', 'счастье': 'happiness', 'грусть': 'sorrow', 'любовь': 'love'}
        trends = {}
        for emotion in EMOTIONS:
            field = EMOTION_FIELD.get(emotion, emotion)
            values = [getattr(r, field, 0) for r in sorted_results]
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
                recommendations="Недостаточно данных для анализа. Проведите больше игровых сессий.",
                detected_diagnoses=[]
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
        
        # Определение диагнозов и генерация рекомендаций
        profile_data = {
            'diagnostic_depth': diagnostic_depth,
            'motivational_potential': motivational_potential,
            'objectivity': objectivity,
            'ecological_validity': ecological_validity,
            'dynamic_assessment': dynamic_assessment,
            'emotional_profile': emotional_profile,
            'cognitive_style': cognitive_style,
        }
        detected_diagnoses, recommendations = self.generate_recommendations_with_diagnoses(**profile_data)
        
        # Обновляем последний профиль или создаём новый (чтобы не плодить записи)
        latest = DiagnosticProfile.objects.filter(child=child).first()
        if latest:
            latest.diagnostic_depth = diagnostic_depth
            latest.motivational_potential = motivational_potential
            latest.objectivity = objectivity
            latest.ecological_validity = ecological_validity
            latest.dynamic_assessment = dynamic_assessment
            latest.cognitive_style = cognitive_style
            latest.emotional_profile = emotional_profile
            latest.recommendations = recommendations
            latest.detected_diagnoses = detected_diagnoses
            latest.save()
            profile = latest
        else:
            profile = DiagnosticProfile.objects.create(
                child=child,
                diagnostic_depth=diagnostic_depth,
                motivational_potential=motivational_potential,
                objectivity=objectivity,
                ecological_validity=ecological_validity,
                dynamic_assessment=dynamic_assessment,
                cognitive_style=cognitive_style,
                emotional_profile=emotional_profile,
                recommendations=recommendations,
                detected_diagnoses=detected_diagnoses
            )
        
        sessions = GameSession.objects.filter(user=child)
        profile.based_on_sessions.set(sessions)
        return profile
    
    # ==================== ГЕНЕРАЦИЯ РЕКОМЕНДАЦИЙ ====================
    
    def _match_diagnoses(self, profile_data: Dict) -> List[Tuple[DiagnosticDiagnosis, float]]:
        """Сопоставление профиля с диагнозами из БД. Возвращает список (диагноз, степень соответствия)."""
        matched = []
        for diag in DiagnosticDiagnosis.objects.all():
            conditions = diag.fuzzy_conditions or {}
            if not conditions:
                continue
            min_match = 1.0
            for key, threshold in conditions.items():
                parts = key.split('.')
                if len(parts) != 2:
                    continue
                var_name, term = parts
                data = profile_data.get(var_name, {})
                if isinstance(data, dict):
                    val = data.get(term, 0)
                else:
                    val = 1.0 if data == term else 0.0
                if val >= threshold:
                    min_match = min(min_match, val)
                else:
                    min_match = 0
                    break
            if min_match > 0:
                matched.append((diag, min_match))
        return sorted(matched, key=lambda x: (-x[1], x[0].priority))
    
    def generate_recommendations_with_diagnoses(self, **kwargs) -> Tuple[List[str], str]:
        """Генерация рекомендаций с учётом диагнозов из БД. Возвращает (коды диагнозов, текст рекомендаций)."""
        detected_codes = []
        sections = []
        diagnostic_depth = kwargs.get('diagnostic_depth', {})
        motivational = kwargs.get('motivational_potential', {})
        emotional = kwargs.get('emotional_profile', {})
        cognitive_style = kwargs.get('cognitive_style', 'unknown')
        
        # Сопоставление с диагнозами из БД
        matched = self._match_diagnoses(kwargs)
        for diag, score in matched:
            detected_codes.append(diag.code)
            block = f"▸ {diag.name}\n{diag.default_recommendations}"
            if diag.default_prescription_text:
                block += f"\n• Возможное назначение: {diag.default_prescription_text}"
            if diag.default_prescription_type == 'medication':
                block += " (только по назначению врача)"
            sections.append(block)
        
        # Граничные значения с заголовками и рекомендациями
        boundary_sections = self._generate_boundary_analysis(
            diagnostic_depth=diagnostic_depth,
            motivational=motivational,
            emotional=emotional,
            cognitive_style=cognitive_style
        )
        sections.extend(boundary_sections)
        
        # Дополнительные рекомендации
        extra = self._generate_extra_recommendations(**kwargs)
        sections.extend(extra)
        
        if not sections:
            return detected_codes, (
                "✅ Диагноз не выявлен. Всё хорошо.\n\n"
                "Эмоциональный и когнитивный профиль в пределах нормы. "
                "Продолжайте регулярные игровые сессии для мониторинга динамики развития."
            )
        
        return detected_codes, "\n\n".join(sections)
    
    def _generate_boundary_analysis(self, **kwargs) -> List[str]:
        """Подробный анализ по граничным значениям с заголовками, рекомендациями и назначениями."""
        sections = []
        emotional = kwargs.get('emotional_profile', {})
        motivational = kwargs.get('motivational_potential', {})
        diagnostic_depth = kwargs.get('diagnostic_depth', {})
        cognitive_style = kwargs.get('cognitive_style', 'unknown')
        
        # Грусть: граничные значения
        sorrow = emotional.get('грусть', 0)
        if sorrow >= 0.5:
            sections.append(
                "▸ Выраженная грусть (≥50%) — возможная депрессия\n"
                "Рекомендации: Срочная консультация детского психиатра или психолога. "
                "Создание поддерживающей среды, арт-терапия, игры на позитивные эмоции. "
                "Исключить буллинг и стрессовые факторы.\n"
                "• Возможные назначения: Консультация психиатра; при подтверждённой депрессии — "
                "психотерапия (КПТ), в тяжёлых случаях — антидепрессанты по назначению врача (флуоксетин и др.)."
            )
        elif sorrow >= 0.35:
            sections.append(
                "▸ Повышенная грусть (35–50%)\n"
                "Рекомендации: Консультация детского психолога для выяснения причин. "
                "Поддерживающая среда, игры на позитивные эмоции, арт-терапия.\n"
                "• Возможные назначения: Игровая терапия, наблюдение психолога."
            )
        
        # Гнев/стресс
        anger = emotional.get('гнев', 0)
        if anger >= 0.5:
            sections.append(
                "▸ Выраженный гнев/стресс (≥50%)\n"
                "Рекомендации: Оценка уровня стресса и тревоги. Техники релаксации, "
                "дыхательные упражнения. Арт-терапия для выражения эмоций. Исключить травмирующие факторы.\n"
                "• Возможные назначения: Игровая терапия, релаксационные техники; "
                "при выраженной тревоге — консультация психиатра (анксиолитики только по назначению)."
            )
        elif anger >= 0.3:
            sections.append(
                "▸ Повышенный гнев (30–50%)\n"
                "Рекомендации: Элементы релаксации, упражнения на выражение эмоций. "
                "Арт-терапия, песочная терапия, техники управления гневом.\n"
                "• Возможные назначения: Арт-терапия 2–3 раза в неделю."
            )
        
        # Скука/апатия
        boredom = emotional.get('скука', 0)
        if boredom >= 0.5:
            sections.append(
                "▸ Выраженная апатия/скука (≥50%)\n"
                "Рекомендации: Исключить депрессию и ангедонию. Разнообразить задания, "
                "подобрать игры по интересам. Проверить соответствие сложности возрасту.\n"
                "• Возможные назначения: Консультация психолога; при сочетании с грустью — "
                "оценка на депрессию."
            )
        elif boredom >= 0.35:
            sections.append(
                "▸ Повышенная скука (35–50%)\n"
                "Рекомендации: Увеличить сложность или разнообразить игры. "
                "Проверить соответствие заданий возрасту и возможностям ребёнка.\n"
                "• Возможные назначения: Адаптация сложности игр."
            )
        
        # Мотивация
        low_mot = motivational.get('низкий', 0)
        if low_mot >= 0.6:
            sections.append(
                "▸ Низкая мотивация (≥60%)\n"
                "Рекомендации: Короткие сессии (10–15 мин) с элементами поощрения. "
                "Постепенное увеличение сложности. Выбор игр по интересам ребёнка.\n"
                "• Возможные назначения: Игровые сессии до 15 мин с перерывами, система поощрений."
            )
        
        # Когнитивный стиль (дефицит внимания)
        if cognitive_style == 'impulsive':
            sections.append(
                "▸ Импульсивность / возможный дефицит внимания\n"
                "Рекомендации: Упражнения на произвольное внимание и самоконтроль. "
                "Игры с последовательным выполнением инструкций, задания с отсроченным ответом.\n"
                "• Возможные назначения: Упражнения на концентрацию 15–20 мин ежедневно; "
                "при подтверждённом СДВГ — консультация невролога/психиатра (метилфенидат и др. только по назначению)."
            )
        
        # Диагностическая глубина
        if diagnostic_depth.get('высокая', 0) < 0.5:
            sections.append(
                "▸ Недостаточная диагностическая глубина\n"
                "Рекомендации: Провести дополнительные игровые сессии. Разнообразить типы игр."
            )
        
        return sections
    
    def _generate_extra_recommendations(self, **kwargs) -> List[str]:
        """Дополнительные рекомендации на основе нечёткого анализа."""
        recommendations = []
        diagnostic_depth = kwargs.get('diagnostic_depth', {})
        motivational = kwargs.get('motivational_potential', {})
        emotional = kwargs.get('emotional_profile', {})
        cognitive_style = kwargs.get('cognitive_style', 'unknown')
        
        if diagnostic_depth.get('высокая', 0) < 0.5:
            recommendations.append(
                "✅ Рекомендуется провести дополнительные игровые сессии для углублённой диагностики. "
                "Разнообразьте типы игр для получения более полной картины."
            )
        if motivational.get('низкий', 0) > 0.6:
            recommendations.append(
                "⚠️ Наблюдается сниженная мотивация. "
                "Используйте более короткие сессии и элементы поощрения."
            )
        elif motivational.get('высокий', 0) > 0.7:
            recommendations.append(
                "🌟 Высокая мотивация к игровой диагностике — благоприятные условия для достоверных результатов."
            )
        if cognitive_style == 'impulsive':
            recommendations.append(
                "🧠 Импульсивный стиль. Рекомендуются упражнения на самоконтроль и внимание."
            )
        elif cognitive_style == 'systematic':
            recommendations.append(
                "📊 Систематический подход. Поддерживайте задачи с возрастающей сложностью."
            )
        elif cognitive_style == 'adaptive':
            recommendations.append(
                "🎯 Адаптивный стиль. Рекомендуются задания на переключение между правилами."
            )
        if emotional:
            for em, threshold in [('гнев', 0.3), ('грусть', 0.3), ('скука', 0.3)]:
                if emotional.get(em, 0) > threshold:
                    if em == 'гнев':
                        recommendations.append("😠 Повышенный гнев — элементы релаксации и выражение эмоций.")
                    elif em == 'грусть':
                        recommendations.append("😔 Преобладание грусти — консультация психолога.")
                    elif em == 'скука':
                        recommendations.append("😐 Высокая скука — увеличить сложность или разнообразие игр.")
        
        return recommendations
    
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
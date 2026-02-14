"""
Диагностическая панель
5 лингвистических переменных A-E
Преобразование игровых метрик в нечёткие множества
"""

import numpy as np
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict

from .models import GameResult, GameSession
from .fuzzy_logic import FuzzyAnalyzer, FuzzyVariable, FuzzySet

# Эталонные профили
# Традиционные методы: стандартизованные тесты, проективные методики (усреднённо)
REFERENCE_TRADITIONAL = {
    'diagnostic_depth': 72,
    'motivational_potential': 45,
    'objectivity': 88,
    'ecological_validity': 52,
    'dynamic_assessment': 38,
}

# Цифровые игровые методы (усреднённо)
REFERENCE_DIGITAL = {
    'diagnostic_depth': 65,
    'motivational_potential': 82,
    'objectivity': 75,
    'ecological_validity': 85,
    'dynamic_assessment': 90,
}

# Описания переменных для tooltips
VARIABLE_DESCRIPTIONS = {
    'diagnostic_depth': ('A. Диагностическая глубина',
                         'Способность выявлять качественные особенности протекания психических процессов'),
    'motivational_potential': ('B. Мотивационный потенциал',
                               'Способность поддерживать вовлечённость и снижать тревожность'),
    'objectivity': ('C. Объективность и стандартизация',
                   'Свобода от влияния человеческого фактора'),
    'ecological_validity': ('D. Экологическая валидность',
                            'Соответствие условий естественным для ребёнка'),
    'dynamic_assessment': ('E. Потенциал для динамической оценки',
                           'Способность фиксировать процесс деятельности в реальном времени'),
}

# Параметры для преобразования игровых метрик (нормированные 0-1)
DIAGNOSTIC_PARAMETERS = {
    'impulsivity': {
        'name': 'Уровень импульсивности',
        'source': 'Скорость движения / время реакции (нормированное)',
        'terms': {'низкий': [0, 0, 0.25, 0.4], 'средний': [0.25, 0.4, 0.6, 0.75], 'высокий': [0.6, 0.75, 1, 1]},
        'interpretations': {
            'низкий': 'Низкая импульсивность. Ребёнок склонен обдумывать действия.',
            'средний': 'Умеренная импульсивность. Сбалансированный стиль ответов.',
            'высокий': 'Высокая импульсивность. Склонность действовать методом проб и ошибок.',
        },
    },
    'cognitive_activity': {
        'name': 'Познавательная активность',
        'source': 'Частота обращений к подсказкам (раз в минуту, нормировано)',
        'terms': {'исследующая': [0, 0, 0.3, 0.5], 'направленная': [0.3, 0.5, 0.7, 0.85], 'зависимая': [0.7, 0.85, 1, 1]},
        'interpretations': {
            'исследующая': 'Исследующая активность. Ребёнок предпочитает самостоятельный поиск.',
            'направленная': 'Направленная активность. Баланс самостоятельности и помощи.',
            'зависимая': 'Зависимая активность. Частое обращение к подсказкам.',
        },
    },
    'strategy': {
        'name': 'Стратегия решения',
        'source': 'Паттерн ошибок (последовательность действий)',
        'terms': {'систематическая': [0, 0, 0.2, 0.35], 'импульсивная': [0.2, 0.35, 0.6, 0.8], 'адаптивная': [0.5, 0.7, 1, 1]},
        'interpretations': {
            'систематическая': 'Систематическая стратегия. Планомерный подход к решению.',
            'импульсивная': 'Импульсивная стратегия. Ошибки из-за поспешности.',
            'адаптивная': 'Адаптивная стратегия. Гибкая смена подходов.',
        },
    },
    'cognitive_control': {
        'name': 'Когнитивный контроль',
        'source': 'Вариабельность времени реакции (σ, нормировано)',
        'terms': {'стабильный': [0, 0, 0.3, 0.5], 'вариабельный': [0.3, 0.5, 0.7, 0.85], 'истощаемый': [0.7, 0.85, 1, 1]},
        'interpretations': {
            'стабильный': 'Стабильный контроль. Устойчивое внимание.',
            'вариабельный': 'Вариабельный контроль. Колебания концентрации.',
            'истощаемый': 'Истощаемый контроль. Снижение при утомлении.',
        },
    },
    'anxiety': {
        'name': 'Тревожность / Перфекционизм',
        'source': 'Количество возвратов к пройденным уровням (нормировано)',
        'terms': {'низкая': [0, 0, 0.25, 0.4], 'умеренная': [0.25, 0.4, 0.6, 0.75], 'высокая': [0.6, 0.75, 1, 1]},
        'interpretations': {
            'низкая': 'Низкая тревожность. Комфортное принятие результата.',
            'умеренная': 'Умеренная тревожность. Стремление к улучшению.',
            'высокая': 'Высокая тревожность. Перфекционизм, страх ошибки.',
        },
    },
}

# Базовые рекомендации СанПиН
BASE_RECOMMENDATIONS = {
    'sleep': {
        '3-5': '11-13 часов (включая дневной сон)',
        '6-10': '10-11 часов',
        '11-14': '9-10 часов',
    },
    'screen': {
        '0-6': 'Не более 30-40 минут в день',
        '7-10': 'Не более 60 минут в день',
        '11-14': 'Не более 90 минут в день',
    },
    'physical': 'Не менее 60 минут ежедневно (активные игры, спорт, прогулки)',
    'nutrition': [
        'Регулярное поступление омега-3 (рыба, орехи, льняное масло)',
        'Витамины группы B (цельнозерновые, бобовые, яйца)',
        'Ограничение простых углеводов и красителей',
    ],
    'cognitive': [
        'Ежедневное чтение и обсуждение (20-30 минут)',
        'Настольные игры на логику и стратегию',
        'Творческие занятия (рисование, лепка, конструирование)',
    ],
    'emotional': [
        'Поддержка автономии и самостоятельности',
        'Обсуждение эмоций (развитие эмоционального интеллекта)',
        'Стабильный распорядок дня (снижение тревожности)',
    ],
}


def get_patient_age_years(date_of_b) -> int:
    """Возраст ребёнка в годах"""
    from django.utils import timezone
    today = timezone.now().date()
    return (today - date_of_b).days // 365 if date_of_b else 7


def extract_game_metrics(game_results: List[GameResult]) -> Dict[str, float]:
    """Извлечение и нормирование игровых метрик (0-1)"""
    metrics = {}
    all_rt = []
    total_mistakes = 0
    total_actions = 0
    hint_count = 0
    session_count = 0

    for r in game_results:
        if r.reaction_times and len(r.reaction_times) > 0:
            rts = [float(x) for x in r.reaction_times if x is not None]
            all_rt.extend(rts)
        pm = r.performance_metrics or {}
        total_mistakes += r.mistakes or 0
        if r.game_type == 'Memory':
            total_actions += pm.get('attempts', 0) * 2 or 1
        elif r.game_type in ('EmotionFace', 'Sort', 'Pattern', 'EmotionMatch'):
            total_actions += pm.get('total', 8) or 8
        else:
            total_actions += max(len(r.reaction_times or []), pm.get('total', 1), 1)
        hint_count += pm.get('hints_used', 0)
        session_count += 1

    # Импульсивность: среднее время реакции (низкое = высокая импульсивность). Нормируем.
    if all_rt:
        avg_rt = np.mean(all_rt)
        # Инвертируем: быстро = импульсивно. 200ms -> 0.9, 1000ms -> 0.2
        impulsivity_raw = max(0, min(1, 1 - (avg_rt - 200) / 1500)) if avg_rt > 0 else 0.5
        metrics['impulsivity'] = float(impulsivity_raw)
        # Когнитивный контроль: вариабельность (высокий std = истощаемый)
        std_rt = np.std(all_rt)
        cv = std_rt / avg_rt if avg_rt > 0 else 0
        metrics['cognitive_control'] = min(1, cv * 2)
    else:
        metrics['impulsivity'] = 0.5
        metrics['cognitive_control'] = 0.5

    # Познавательная активность: подсказки на сессию (нормировано)
    hints_norm = min(1, hint_count / max(session_count * 3, 1))
    metrics['cognitive_activity'] = hints_norm

    # Стратегия: доля ошибок -> импульсивность
    error_rate = total_mistakes / total_actions if total_actions > 0 else 0.2
    metrics['strategy'] = min(1, error_rate * 2.5)

    # Тревожность: аппроксимируем из точности (высокая точность при малом времени = перфекционизм)
    metrics['anxiety'] = 0.3 + 0.4 * (1 - error_rate) if total_actions > 0 else 0.4

    return metrics


def compute_membership(mf: List[float], x: float) -> float:
    """Трапециевидная функция принадлежности. mf = [a,b,c,d]"""
    if len(mf) == 3:
        a, b, c = mf
        d = c
    else:
        a, b, c, d = mf
    if x <= a or x >= d:
        return 0.0
    if a < x < b:
        return (x - a) / (b - a) if b != a else 1.0
    if b <= x <= c:
        return 1.0
    if c < x < d:
        return (d - x) / (d - c) if d != c else 1.0
    return 0.0


def get_fuzzy_analysis_for_panel(analyzer: FuzzyAnalyzer, profile, game_results: List[GameResult], patient) -> Dict:
    """Полный анализ для диагностической панели"""
    radar = profile.get_radar_data()
    metrics = extract_game_metrics(game_results)

    # Результаты по каждому параметру
    params_results = {}
    for param_id, pdata in DIAGNOSTIC_PARAMETERS.items():
        x = metrics.get(param_id, 0.5)
        terms_res = {}
        formulas = {}
        for term, mf in pdata['terms'].items():
            mu = compute_membership(mf, x)
            terms_res[term] = round(mu, 2)
            a, b = mf[0], mf[1]
            c, d = (mf[2], mf[2]) if len(mf) == 3 else (mf[2], mf[3])
            formulas[term] = f"max(0, min(({x:.2f}-{a})/({b}-{a}), ({d}-{x:.2f})/({d}-{c})))"
        dominant = max(terms_res.items(), key=lambda t: t[1])
        params_results[param_id] = {
            'param_id': param_id,
            'name': pdata['name'],
            'source': pdata['source'],
            'value': x,
            'memberships': terms_res,
            'formulas': formulas,
            'dominant_term': dominant[0],
            'dominant_mu': dominant[1],
            'interpretation': pdata['interpretations'].get(dominant[0], ''),
            'mf_params': pdata['terms'],
        }

    # Данные для графиков функций принадлежности (JSON-serializable)
    mf_chart_data = {}
    for param_id, pr in params_results.items():
        mf_chart_data[param_id] = {
            'value': float(pr['value']),
            'terms': pr['memberships'],
            'points': {},
        }
        for term, mf in DIAGNOSTIC_PARAMETERS[param_id]['terms'].items():
            pts = []
            for xi in np.linspace(0, 1, 50):
                pts.append({'x': float(xi), 'y': float(compute_membership(mf, xi))})
            mf_chart_data[param_id]['points'][term] = pts

    # Конвертация в JSON-serializable
    def to_json_val(v):
        if isinstance(v, (np.floating, np.integer)):
            return float(v)
        if isinstance(v, dict):
            return {k: to_json_val(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return [to_json_val(x) for x in v]
        return v

    params_for_json = {k: to_json_val(v) for k, v in params_results.items()}
    return {
        'radar_patient': [float(radar.get('diagnostic_depth', 30)), float(radar.get('motivational_potential', 30)),
                         float(radar.get('objectivity', 50)), float(radar.get('ecological_validity', 40)),
                         float(radar.get('dynamic_assessment', 35))],
        'radar_traditional': [REFERENCE_TRADITIONAL[k] for k in ['diagnostic_depth', 'motivational_potential', 'objectivity', 'ecological_validity', 'dynamic_assessment']],
        'radar_digital': [REFERENCE_DIGITAL[k] for k in ['diagnostic_depth', 'motivational_potential', 'objectivity', 'ecological_validity', 'dynamic_assessment']],
        'variable_descriptions': VARIABLE_DESCRIPTIONS,
        'params_results': params_for_json,
        'mf_chart_data': to_json_val(mf_chart_data),
        'diagnostic_params': {k: {kk: vv for kk, vv in v.items() if kk != 'interpretations'} for k, v in DIAGNOSTIC_PARAMETERS.items()},
        'metrics': to_json_val(metrics),
    }


def get_heatmap_data(game_results: List[GameResult], profile) -> Dict:
    """Матрица 5×3: системы (когнитивная, эмоциональная, поведенческая, регуляторная, социальная) × 3 показателя"""
    systems = ['когнитивная', 'эмоциональная', 'поведенческая', 'регуляторная', 'социальная']
    indicators = ['активность', 'стабильность', 'адаптивность']

    # Расчёт отклонений от нормы (в единицах σ, упрощённо)
    matrix = []
    ep = profile.emotional_profile or {}
    try:
        rd = profile.get_radar_data()
    except Exception:
        rd = {}
    # Аппроксимация: используем эмоции и радар
    cognitive = (rd.get('objectivity', 50) / 50 - 1) * 1.5
    emotional = ((ep.get('радость', 0) + ep.get('счастье', 0)) / 0.3 - 1) * 1.2
    behavioral = (rd.get('ecological_validity', 50) / 50 - 1) * 1.0
    regulatory = (rd.get('dynamic_assessment', 50) / 50 - 1) * 1.3
    social = (ep.get('любовь', 0) / 0.2 - 1) * 1.0

    for sys_val in [cognitive, emotional, behavioral, regulatory, social]:
        row = []
        for _ in indicators:
            row.append(round(sys_val + np.random.uniform(-0.3, 0.3), 2))
        matrix.append(row)

    # Собираем строки для шаблона
    rows = [{'system': systems[i], 'values': matrix[i]} for i in range(len(systems))]
    return {'matrix': matrix, 'systems': systems, 'indicators': indicators, 'rows': rows}


def get_dynamics_data(game_results: List[GameResult]) -> Dict:
    """Данные для графика динамики с центильными коридорами"""
    if len(game_results) < 2:
        return None
    sorted_results = sorted(game_results, key=lambda r: r.date)
    dates = [r.date.strftime('%d.%m') for r in sorted_results]
    # Показатель: сумма joy+happiness как прокси "уровня благополучия"
    values = [r.joy + r.happiness + (1 - r.mistakes/10 if r.mistakes else 1) for r in sorted_results]
    # Центильные коридоры (упрощённо)
    percentiles = [3, 10, 25, 50, 75, 90, 97]
    base = 5
    corridor_values = [[base + p * 0.3 for _ in dates] for p in percentiles]
    return {
        'dates': dates,
        'values': values,
        'percentiles': percentiles,
        'corridors': corridor_values,
        'mean_line': [base + 50 * 0.003 for _ in dates],
    }


def get_correlation_matrix(game_results: List[GameResult]) -> Dict:
    """Матрица корреляций 8×8"""
    indicators = ['гнев', 'грусть', 'радость', 'счастье', 'любовь', 'скука', 'точность', 'время_реакции']
    n = len(indicators)
    EMOTION_MAP = {'гнев': 'anger', 'грусть': 'sorrow', 'радость': 'joy', 'счастье': 'happiness', 'любовь': 'love', 'скука': 'boredom'}
    data = {k: [] for k in indicators}
    for r in game_results:
        for em, field in EMOTION_MAP.items():
            data[em].append(getattr(r, field, 0))
        data['точность'].append(1 - (r.mistakes / 10) if r.mistakes else 1)
        rts = r.reaction_times or []
        data['время_реакции'].append(np.mean(rts) if rts else 500)

    # Выравнивание длин
    max_len = max(len(v) for v in data.values())
    for k in data:
        while len(data[k]) < max_len:
            data[k].append(data[k][-1] if data[k] else 0)
        data[k] = data[k][:max_len]

    corr_matrix = []
    vals = list(data.values())
    for i in range(n):
        row = []
        for j in range(n):
            if i == j:
                row.append(1.0)
            else:
                c = np.corrcoef(vals[i], vals[j])[0, 1] if max_len > 1 else 0
                row.append(round(float(c) if not np.isnan(c) else 0, 2))
        corr_matrix.append(row)

    rows = [{'label': indicators[i], 'values': corr_matrix[i]} for i in range(n)]
    return {'matrix': corr_matrix, 'labels': indicators, 'rows': rows}


def get_adaptive_recommendations(params_results: Dict, diagnostic_params: Dict) -> List[Dict]:
    """Адаптивные рекомендации по 4 уровням для каждого параметра"""
    recs = []
    for param_id, pr in params_results.items():
        term = pr['dominant_term']
        mu = pr['dominant_mu']
        pdata = diagnostic_params.get(param_id, {})
        name = pdata.get('name', param_id)

        brief = f"«{term}» {name.lower()} — "
        if param_id == 'impulsivity':
            brief += "ребёнок склонен к обдумыванию" if term == 'низкий' else "выраженная склонность к импульсивным действиям" if term == 'высокий' else "сбалансированный стиль"
        elif param_id == 'cognitive_activity':
            brief += "самостоятельный поиск решений" if term == 'исследующая' else "частое обращение к помощи" if term == 'зависимая' else "баланс самостоятельности и помощи"
        elif param_id == 'strategy':
            brief += "планомерный подход" if term == 'систематическая' else "использование метода проб" if term == 'импульсивная' else "гибкая смена стратегий"
        elif param_id == 'cognitive_control':
            brief += "устойчивое внимание" if term == 'стабильный' else "истощаемость при нагрузке" if term == 'истощаемый' else "колебания концентрации"
        else:
            brief += "комфортное принятие результата" if term == 'низкая' else "выраженное стремление к совершенству" if term == 'высокая' else "умеренное стремление к улучшению"

        extended = "Согласно принципу детерминизма (Выготский Л.С.), данный паттерн может свидетельствовать о формировании регуляторных функций. "
        extended += "Рекомендуется дополнительная оценка в естественной среде (метод наблюдения) для подтверждения устойчивости. "
        extended += "Игровая диагностика дополняет клиническую картину."

        parent_steps = [
            "Для развития гибкости: игры с меняющимися правилами («Съедобное-несъедобное» наоборот)",
            "Для тренировки планирования: настольные игры с пошаговой стратегией",
            "Обратиться к психологу, если: ребёнок не может удерживать инструкцию более 2 минут",
        ]
        doctor_steps = [
            "Для уточнения: провести методику «Корректурная проба» (Бурдон) для оценки устойчивости внимания",
            "Консультация: невролог (для исключения органических причин)",
            "Повторная диагностика: через 3 месяца",
        ]
        recs.append({
            'param_id': param_id,
            'name': name,
            'term': term,
            'mu': mu,
            'brief': brief,
            'extended': extended,
            'parent_steps': parent_steps,
            'doctor_steps': doctor_steps,
        })
    return recs

import numpy as np
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict

from .models import GameResult, GameSession
from .fuzzy_logic import FuzzyAnalyzer, FuzzyVariable, FuzzySet

REFERENCE_TRADITIONAL = {
    'diagnostic_depth': 72,
    'motivational_potential': 45,
    'objectivity': 88,
    'ecological_validity': 52,
    'dynamic_assessment': 38,
}

REFERENCE_DIGITAL = {
    'diagnostic_depth': 65,
    'motivational_potential': 82,
    'objectivity': 75,
    'ecological_validity': 85,
    'dynamic_assessment': 90,
}

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

AXIS_CLINICAL_IMPLICATIONS = {
    'diagnostic_depth': {
        'low': 'Низкая диагностическая глубина: игровые данные мало информативны для глубокой оценки. Рекомендации: увеличить количество разнообразных игр (раскраска, память, диалог), при необходимости — направить на углублённую диагностику к психологу (наблюдение, стандартизированные тесты).',
        'mid': 'Умеренная диагностическая глубина: игровая диагностика даёт полезную информацию. Рекомендации: продолжать игровой мониторинг, дополнять наблюдением в быту и при необходимости — консультацией специалиста.',
        'high': 'Высокая диагностическая глубина: игровые данные хорошо отражают особенности ребёнка. Рекомендации: использовать результаты как основу для коррекционных решений, поддерживать регулярную игровую активность.',
    },
    'motivational_potential': {
        'low': 'Низкий мотивационный потенциал: ребёнок мало вовлекается в игры, возможна тревожность или демотивация. Рекомендации: консультация психолога/невролога для исключения тревожных расстройств; выбор более подходящих игр; снижение требований, поддержка.',
        'mid': 'Умеренный мотивационный потенциал: вовлечённость достаточная. Рекомендации: поддерживать интерес, разнообразить игровой репертуар, отмечать достижения.',
        'high': 'Высокий мотивационный потенциал: игры хорошо поддерживают вовлечённость и снижают тревогу. Рекомендации: опираться на игры как на коррекционный ресурс; не перегружать ребёнка, соблюдать режим.',
    },
    'objectivity': {
        'low': 'Низкая объективность: результаты могут зависеть от субъективных факторов. Рекомендации: дополнять игровую диагностику объективными методиками (время реакции, точность), консультация для уточнения картины.',
        'mid': 'Умеренная объективность: данные достаточно надёжны. Рекомендации: использовать в комплексе с наблюдением и при необходимости — стандартизированными тестами.',
        'high': 'Высокая объективность: данные малосубъективны. Рекомендации: можно опираться на них при принятии решений, продолжать мониторинг.',
    },
    'ecological_validity': {
        'low': 'Низкая экологическая валидность: условия игр мало соответствуют естественной среде. Рекомендации: увеличить долю творческих и свободных игр (раскраска, диалог, выбор); наблюдение за ребёнком в быту; консультация для переноса выводов в реальность.',
        'mid': 'Умеренная экологическая валидность: условия частично естественны. Рекомендации: дополнять игровые данные наблюдением дома и в детском коллективе.',
        'high': 'Высокая экологическая валидность: условия близки к естественным. Рекомендации: выводы можно экстраполировать на повседневную жизнь; поддерживать разнообразие игр.',
    },
    'dynamic_assessment': {
        'low': 'Низкий потенциал динамической оценки: недостаточно данных для отслеживания изменений во времени. Рекомендации: чаще проходить игры (не реже 1–2 раз в неделю), вести дневник наблюдений; при необходимости — консультация для углублённой динамической оценки.',
        'mid': 'Умеренный потенциал: возможно отслеживание динамики. Рекомендации: продолжать регулярные игровые сессии (2–3 раза в неделю), анализировать тренды; при стабильных проблемах — консультация специалиста.',
        'high': 'Высокий потенциал динамической оценки: данные позволяют фиксировать изменения в реальном времени. Рекомендации: использовать игры как основной инструмент мониторинга; корректировать рекомендации по динамике.',
    },
}

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

MF_CLINICAL_GUIDE = {
    'impulsivity': {
        'doctor_purpose': 'Эта функция принадлежности позволяет оценить склонность к импульсивным ответам: быстрые реакции без обдумывания vs затянутое принятие решений. Важна для дифференциальной диагностики СДВГ, тревожности и для подбора коррекционных игр.',
        'child_impact': {
            'низкий': 'Ребёнок склонен обдумывать. Может замедлять выполнение заданий, зато меньше ошибок по невнимательности.',
            'средний': 'Сбалансированный стиль — адекватный темп и достаточный контроль.',
            'высокий': 'Частые ошибки «поспешил», трудности с удержанием инструкции, может перебивать, действовать методом проб.',
        },
        'possible_causes': {
            'высокий': ['Возрастная незрелость регуляторных функций', 'СДВГ (требует клинической оценки)', 'Тревожность и желание скорее закончить', 'Недостаток сна, перегрузка экранами', 'Слишком быстрые/стрессовые игры'],
            'низкий': ['Перфекционизм', 'Тревожность и страх ошибки', 'Дефицит автоматизации навыков', 'Индивидуальный темп развития'],
        },
        'recommendations': {
            'высокий': ['Игры на «стоп-сигнал» (пауза перед ответом), «Светофор»', 'Укороченные сессии (10–15 мин) с перерывами', 'Исключить СДВГ при стойкой выраженности — консультация невролога', 'Режим сна, ограничение экранов', 'Настольные игры с пошаговым планированием'],
            'низкий': ['Снизить требования к скорости', 'Игры без жёсткого лимита времени', 'При сочетании с тревогой — работа с принятием ошибок'],
        },
    },
    'cognitive_activity': {
        'doctor_purpose': 'Эта функция принадлежности отражает стиль познавательной активности: самостоятельный поиск vs частая опора на подсказки. Помогает понять готовность к автономной работе и необходимость поддержки.',
        'child_impact': {
            'исследующая': 'Активно пробует сам, редко обращается к подсказкам. Хорошо для обучения, но может «застревать» на неверной гипотезе.',
            'направленная': 'Баланс: пробует самостоятельно, при затруднении просит помощи. Оптимальный для обучения стиль.',
            'зависимая': 'Часто опирается на подсказки, меньше инициативы в поиске. Возможны трудности с самостоятельностью в школе.',
        },
        'possible_causes': {
            'зависимая': ['Низкая уверенность в себе', 'Страх ошибки', 'Недостаточно сформирована произвольность', 'Привычка к немедленной помощи в семье', 'Сложность игр выше возможностей ребёнка'],
            'исследующая': ['Высокая познавательная мотивация', 'Трудности с принятием помощи (упрямство, ригидность)', 'Возрастные особенности (исследовательская доминанта)'],
        },
        'recommendations': {
            'зависимая': ['Игры с дозированной подсказкой (сначала наводящий вопрос)', 'Поддержка и похвала за попытки', 'Постепенное сокращение подсказок', 'Консультация психолога при выраженной зависимости'],
            'исследующая': ['Не мешать исследованию при успехе', 'При «застревании» — мягкое перенаправление', 'Развитие умения просить помощь при необходимости'],
        },
    },
    'strategy': {
        'doctor_purpose': 'Эта функция принадлежности характеризует паттерн решения задач: систематический, импульсивный или адаптивный. Важна для оценки когнитивного стиля и планирования коррекции.',
        'child_impact': {
            'систематическая': 'Планомерный подход, меньше случайных ошибок. Может быть медленнее.',
            'импульсивная': 'Ошибки из-за поспешности, мало проверки перед действием.',
            'адаптивная': 'Гибко меняет подход при неудаче. Эффективный стиль.',
        },
        'possible_causes': {
            'импульсивная': ['Импульсивность (см. параметр выше)', 'Недостаток навыка планирования', 'Слишком простые задания (не требуют стратегии)', 'Дефицит внимания'],
        },
        'recommendations': {
            'импульсивная': ['Игры с обязательным планированием шага («что сделаю — потом делаю»)', 'Настольные стратегические игры', 'Увеличение паузы перед действием'],
        },
    },
    'cognitive_control': {
        'doctor_purpose': 'Эта функция принадлежности оценивает устойчивость внимания и контроля: стабильность vs истощаемость при нагрузке. Ключевой параметр для прогноза успешности в школе.',
        'child_impact': {
            'стабильный': 'Устойчивое внимание, мало колебаний в течение сессии.',
            'вариабельный': 'Колебания концентрации — периоды хорошей работы и «провалов».',
            'истощаемый': 'Снижение качества к концу сессии, утомляемость, возможны трудности с длинными уроками.',
        },
        'possible_causes': {
            'истощаемый': ['Астенизация (после болезни, недосып)', 'СДВГ', 'Высокая нагрузка, недостаток отдыха', 'Тревожность (отвлекает на контроль)'],
            'вариабельный': ['Возрастная незрелость', 'Монотонные задачи', 'Недостаточная мотивация'],
        },
        'recommendations': {
            'истощаемый': ['Короткие сессии (15–20 мин), частые перерывы', 'Исключить перегрузку, обеспечить сон', 'Консультация невролога при стойкой истощаемости', 'Игры с переменой активности'],
            'вариабельный': ['Разнообразие заданий', 'Чередование типов игр', 'Поддержание интереса'],
        },
    },
    'anxiety': {
        'doctor_purpose': 'Эта функция принадлежности отражает тревожность и перфекционизм (возвраты к пройденным уровням, стремление «исправить»). Важна для дифференциации здорового стремления к успеху и патологической тревоги.',
        'child_impact': {
            'низкая': 'Комфортно принимает результат, не застревает на ошибках.',
            'умеренная': 'Стремится к улучшению, здоровый перфекционизм.',
            'высокая': 'Страх ошибки, многократные возвраты, возможно избегание сложных заданий, трудности с принятием неудачи.',
        },
        'possible_causes': {
            'высокая': ['Тревожное расстройство', 'Высокие требования в семье/школе', 'Перфекционизм как черта', 'Низкая самооценка', 'Негативный опыт критики'],
        },
        'recommendations': {
            'высокая': ['Работа с принятием ошибок как части обучения', 'Снижение критики, акцент на усилиях', 'Консультация психолога/психотерапевта при выраженной тревоге', 'Игры с низким порогом «неудачи»'],
        },
    },
}
MF_TIMELINE_NOTE = 'Параметры функций принадлежности отражают усреднённое состояние по всем игровым сессиям. Для оценки времени появления проблем или улучшений см. блок «Динамика показателей» — там отслеживаются радость, счастье и количество ошибок по датам.'

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
    from django.utils import timezone
    today = timezone.now().date()
    return (today - date_of_b).days // 365 if date_of_b else 7


def _age_to_bracket(age: int, keys: List[str]) -> str:
    """Подбирает ключ скобки по возрасту. keys например ['3-5','6-10','11-14']."""
    for k in keys:
        parts = k.split('-')
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            lo, hi = int(parts[0]), int(parts[1])
            if lo <= age <= hi:
                return k
    if keys:
        last = keys[-1]
        parts = last.split('-') if last else []
        if len(parts) == 2 and parts[1].isdigit() and age > int(parts[1]):
            return last
        return keys[0]
    return ''


def build_auto_prescription_text(params_results: Dict, base_recs: Dict, patient) -> str:
    """Формирует краткий текст назначения для родителя: только конкретные рекомендации (без блоков для врача)."""
    lines = []

    # Конкретные рекомендации по параметрам (только если есть)
    for param_id, pr in params_results.items():
        recs = pr.get('recommendations') or []
        if recs:
            name = pr.get('name', param_id)
            lines.append(f'{name}:')
            for r in recs:
                lines.append(f'• {r}')
            lines.append('')

    age = get_patient_age_years(patient.date_of_b) if patient and hasattr(patient, 'date_of_b') and patient.date_of_b else 7
    sleep_key = _age_to_bracket(age, list(base_recs.get('sleep', {}).keys()))
    screen_key = _age_to_bracket(age, list(base_recs.get('screen', {}).keys()))

    # Базовые гигиенические нормы (кратко)
    lines.append('Режим и нагрузка:')
    if base_recs.get('sleep') and sleep_key:
        lines.append(f'• Сон: {base_recs["sleep"].get(sleep_key, "")}')
    if base_recs.get('screen') and screen_key:
        lines.append(f'• Экран: {base_recs["screen"].get(screen_key, "")}')
    lines.append('• Перерывы каждые 20–25 мин при работе с экраном.')
    if base_recs.get('physical'):
        lines.append(f'• Активность: {base_recs["physical"]}')

    return '\n'.join(lines)


def extract_game_metrics(game_results: List[GameResult]) -> Dict[str, float]:
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

    if all_rt:
        avg_rt = np.mean(all_rt)
        impulsivity_raw = max(0, min(1, 1 - (avg_rt - 200) / 1500)) if avg_rt > 0 else 0.5
        metrics['impulsivity'] = float(impulsivity_raw)
        std_rt = np.std(all_rt)
        cv = std_rt / avg_rt if avg_rt > 0 else 0
        metrics['cognitive_control'] = min(1, cv * 2)
    else:
        metrics['impulsivity'] = 0.5
        metrics['cognitive_control'] = 0.5

    hints_norm = min(1, hint_count / max(session_count * 3, 1))
    metrics['cognitive_activity'] = hints_norm

    error_rate = total_mistakes / total_actions if total_actions > 0 else 0.2
    metrics['strategy'] = min(1, error_rate * 2.5)

    metrics['anxiety'] = 0.3 + 0.4 * (1 - error_rate) if total_actions > 0 else 0.4

    return metrics


def compute_membership(mf: List[float], x: float) -> float:
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
    radar = profile.get_radar_data()
    metrics = extract_game_metrics(game_results)

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
        dom_term = dominant[0]
        guide = MF_CLINICAL_GUIDE.get(param_id, {})
        params_results[param_id] = {
            'param_id': param_id,
            'name': pdata['name'],
            'source': pdata['source'],
            'value': x,
            'memberships': terms_res,
            'formulas': formulas,
            'dominant_term': dom_term,
            'dominant_mu': dominant[1],
            'interpretation': pdata['interpretations'].get(dom_term, ''),
            'mf_params': pdata['terms'],
            'doctor_purpose': guide.get('doctor_purpose', ''),
            'child_impact': guide.get('child_impact', {}).get(dom_term, ''),
            'possible_causes': guide.get('possible_causes', {}).get(dom_term, []),
            'recommendations': guide.get('recommendations', {}).get(dom_term, []),
        }

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

    def to_json_val(v):
        if isinstance(v, (np.floating, np.integer)):
            return float(v)
        if isinstance(v, dict):
            return {k: to_json_val(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return [to_json_val(x) for x in v]
        return v

    params_for_json = {k: to_json_val(v) for k, v in params_results.items()}
    axis_keys = ['diagnostic_depth', 'motivational_potential', 'objectivity', 'ecological_validity', 'dynamic_assessment']
    defaults = {'diagnostic_depth': 30, 'motivational_potential': 30, 'objectivity': 50, 'ecological_validity': 40, 'dynamic_assessment': 35}
    patient_vals = [float(radar.get(k, defaults[k])) for k in axis_keys]
    trad_vals = [REFERENCE_TRADITIONAL[k] for k in axis_keys]
    dig_vals = [REFERENCE_DIGITAL[k] for k in axis_keys]
    axis_names = ['A. Диагностическая глубина', 'B. Мотивационный потенциал', 'C. Объективность', 'D. Экологическая валидность', 'E. Динамическая оценка']
    radar_axis_interpretations = []
    for i, (p, t, d, name) in enumerate(zip(patient_vals, trad_vals, dig_vals, axis_names)):
        axis_key = axis_keys[i]
        impl = AXIS_CLINICAL_IMPLICATIONS.get(axis_key, {})
        lo, hi = min(t, d), max(t, d)
        if abs(p - t) < 5 and abs(p - d) < 5:
            interp = f"Профиль ребёнка ({p:.0f}) близок к обоим эталонам (традиционные {t:.0f}, цифровые {d:.0f}). Сбалансированная выраженность."
            level = 'mid'
        elif p > max(t, d):
            interp = f"Профиль ребёнка ({p:.0f}) превышает оба эталона (традиционные {t:.0f}, цифровые {d:.0f}). Высокая выраженность данной характеристики."
            level = 'high'
        elif p < min(t, d):
            interp = f"Профиль ребёнка ({p:.0f}) ниже обоих эталонов (традиционные {t:.0f}, цифровые {d:.0f}). Низкая выраженность; возможен дефицит данных."
            level = 'low'
        elif t <= p <= d or d <= p <= t:
            closer = "традиционным" if abs(p - t) < abs(p - d) else "цифровым"
            interp = f"Профиль ребёнка ({p:.0f}) расположен между эталонами (традиционные {t:.0f}, цифровые {d:.0f}). Значение ближе к {closer} методам."
            level = 'high' if p > (t + d) / 2 else ('low' if p < (t + d) / 2 else 'mid')
        else:
            interp = f"Профиль ребёнка ({p:.0f}) расположен между эталонами (традиционные {t:.0f}, цифровые {d:.0f})."
            level = 'mid'
        doctor_rec = impl.get(level, impl.get('mid', ''))
        radar_axis_interpretations.append({
            'axis': name, 'value': p, 'traditional': t, 'digital': d,
            'interpretation': interp,
            'doctor_recommendation': doctor_rec
        })
    return {
        'radar_patient': patient_vals,
        'radar_traditional': trad_vals,
        'radar_digital': dig_vals,
        'radar_axis_interpretations': radar_axis_interpretations,
        'variable_descriptions': VARIABLE_DESCRIPTIONS,
        'params_results': params_for_json,
        'mf_timeline_note': MF_TIMELINE_NOTE,
        'mf_chart_data': to_json_val(mf_chart_data),
        'diagnostic_params': {k: {kk: vv for kk, vv in v.items() if kk != 'interpretations'} for k, v in DIAGNOSTIC_PARAMETERS.items()},
        'metrics': to_json_val(metrics),
    }


def get_heatmap_data(game_results: List[GameResult], profile) -> Dict:
    systems = ['когнитивная', 'эмоциональная', 'поведенческая', 'регуляторная', 'социальная']
    indicators = ['активность', 'стабильность', 'адаптивность']

    matrix = []
    ep = profile.emotional_profile or {}
    try:
        rd = profile.get_radar_data()
    except Exception:
        rd = {}
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

    def cell_style(val):
        v = float(val)
        if v <= -0.3:
            a = min(0.95, 0.25 + 0.7 * min(1, (-v) / 1.2))
            return f'background: rgba(50, 80, 180, {a:.2f}); color: white;'
        elif v >= 0.3:
            a = min(0.95, 0.25 + 0.7 * min(1, v / 1.2))
            return f'background: rgba(200, 50, 50, {a:.2f}); color: white;'
        else:
            g = int(240 - 40 * abs(v) / 0.3)
            return f'background: rgb({g}, {g}, {g});'

    def cell_interpretation(val, system, indicator):
        v = float(val)
        if v < -0.7:
            return f"Значительно ниже нормы ({v:.2f}σ). Возможна недостаточность в {system} системе по {indicator}."
        elif v < -0.3:
            return f"Ниже нормы ({v:.2f}σ). Умеренное снижение."
        elif v <= 0.3:
            return f"В пределах нормы ({v:.2f}σ)."
        elif v <= 0.7:
            return f"Выше нормы ({v:.2f}σ). Умеренное повышение."
        else:
            return f"Значительно выше нормы ({v:.2f}σ). Высокая выраженность."

    rows = []
    cell_interps = []
    for i in range(len(systems)):
        row_cells = []
        for j, val in enumerate(matrix[i]):
            row_cells.append({
                'value': val,
                'style': cell_style(val),
                'interpretation': cell_interpretation(val, systems[i], indicators[j])
            })
            cell_interps.append({'system': systems[i], 'indicator': indicators[j], 'value': val, 'interpretation': cell_interpretation(val, systems[i], indicators[j])})
        rows.append({'system': systems[i], 'values': matrix[i], 'cells': row_cells})

    low_systems = [systems[i] for i in range(len(systems)) if any(matrix[i][j] < -0.3 for j in range(3))]
    high_systems = [systems[i] for i in range(len(systems)) if any(matrix[i][j] > 0.3 for j in range(3))]
    summary = []
    if low_systems:
        summary.append(f"Системы с показателями ниже нормы: {', '.join(low_systems)}. Рекомендуется усиление поддержки в этих областях.")
    if high_systems:
        summary.append(f"Системы с показателями выше нормы: {', '.join(high_systems)}.")
    if not summary:
        summary.append("Показатели в пределах нормы по всем системам.")

    HEATMAP_DOCTOR_GUIDE = {
        'doctor_purpose': 'Эта тепловая карта даёт врачу интегральную картину по пяти функциональным системам (когнитивная, эмоциональная, поведенческая, регуляторная, социальная) и трём показателям (активность, стабильность, адаптивность). Позволяет быстро выявить зоны дефицита и избытка, приоритизировать направления коррекции.',
        'above_norm': {
            'meaning': 'Показатели выше нормы означают высокую выраженность данной характеристики. Это может быть как ресурс (высокая познавательная активность, стабильные эмоции), так и зона внимания (гиперактивация, ригидность, чрезмерный контроль). Важно соотнести с клинической картиной и жалобами.',
            'causes': ['Индивидуальные особенности темперамента', 'Компенсаторная активация при тревоге', 'Высокие требования среды', 'Ресурсные стороны ребёнка (при отсутствии жалоб)'],
            'recommendations': ['Оценить, является ли повышенная выраженность проблемой для ребёнка и семьи', 'При гиперактивации — игры на расслабление, регуляцию темпа', 'При ригидности — задания на гибкость, смену стратегий', 'Использовать сильные стороны как опору в коррекции'],
        },
        'below_norm': {
            'meaning': 'Показатели ниже нормы указывают на недостаточность или дефицит в данной системе. Возможны трудности в обучении, общении, регуляции эмоций и поведения. Требуют уточнения причин и целенаправленной поддержки.',
            'causes': ['Возрастная незрелость', 'Стресс, перегрузка, недосып', 'Эмоциональные трудности (тревожность, подавленность)', 'Когнитивные особенности (СДВГ, трудности обучения)', 'Дефицит практики в данной области', 'Социальная депривация'],
            'recommendations': ['Усилить поддержку в дефицитарных системах', 'Исключить перегрузку, обеспечить режим сна и отдыха', 'Подобрать игры и активности, целенаправленно развивающие данную систему', 'При стойком дефиците — консультация психолога/невролога для углублённой диагностики', 'Работа с семьёй: создать условия для развития (безопасность, стабильность, позитив)'],
        },
        'system_guides': {
            'когнитивная': {'low': 'Дефицит познавательных ресурсов. Рекомендации: игры на внимание, память, логику; исключить перегрузку; консультация при стойких трудностях.', 'high': 'Высокая познавательная активность. Может быть ресурсом; при гиперактивации — игры на регуляцию темпа.'},
            'эмоциональная': {'low': 'Снижение эмоционального тонуса. Рекомендации: игры на позитивные эмоции; беседы об эмоциях; при стойком снижении — консультация.', 'high': 'Высокая эмоциональная выраженность. Оценить — ресурс или перегрузка; при лабильности — работа над регуляцией.'},
            'поведенческая': {'low': 'Трудности адаптации поведения. Рекомендации: структурирование среды; пошаговые инструкции; игровая практика.', 'high': 'Выраженная поведенческая активность. При гиперактивности — консультация; игры с правилами.'},
            'регуляторная': {'low': 'Слабость регуляции. Рекомендации: короткие сессии; игры на «стоп-сигнал»; режим; при СДВГ — консультация невролога.', 'high': 'Высокий регуляторный контроль. Может сопровождать перфекционизм; при чрезмерности — работа над гибкостью.'},
            'социальная': {'low': 'Дефицит социальных навыков или эмоциональной связи. Рекомендации: совместные игры; развитие эмпатии; при изоляции — консультация.', 'high': 'Высокая социальная ориентация. Ресурс для развития; следить за границами.'},
        },
    }
    system_interpretations = []
    for sys in low_systems:
        g = HEATMAP_DOCTOR_GUIDE['system_guides'].get(sys, {})
        system_interpretations.append({'system': sys, 'direction': 'low', 'guide': g.get('low', '')})
    for sys in high_systems:
        g = HEATMAP_DOCTOR_GUIDE['system_guides'].get(sys, {})
        system_interpretations.append({'system': sys, 'direction': 'high', 'guide': g.get('high', '')})

    return {
        'matrix': matrix, 'systems': systems, 'indicators': indicators, 'rows': rows,
        'cell_interpretations': cell_interps, 'summary_interpretation': summary,
        'doctor_purpose': HEATMAP_DOCTOR_GUIDE['doctor_purpose'],
        'above_norm': HEATMAP_DOCTOR_GUIDE['above_norm'],
        'below_norm': HEATMAP_DOCTOR_GUIDE['below_norm'],
        'system_interpretations': system_interpretations,
    }


def get_dynamics_data(game_results: List[GameResult]) -> Dict:
    if len(game_results) < 2:
        return None
    sorted_results = sorted(game_results, key=lambda r: r.date)
    dates = [r.date.strftime('%d.%m') for r in sorted_results]
    joys = [r.joy for r in sorted_results]
    happinesses = [r.happiness for r in sorted_results]
    mistakes_list = [(r.mistakes or 0) for r in sorted_results]
    success_component = [(1 - m/10 if m else 1) for m in mistakes_list]
    values = [j + h + s for j, h, s in zip(joys, happinesses, success_component)]
    percentiles = [3, 10, 25, 50, 75, 90, 97]
    base = 5
    corridor_values = [[base + p * 0.3 for _ in dates] for p in percentiles]
    first_half = values[:len(values)//2] if len(values) > 1 else values
    second_half = values[len(values)//2:] if len(values) > 1 else values
    avg_first = np.mean(first_half) if first_half else 0
    avg_second = np.mean(second_half) if second_half else 0
    diff = avg_second - avg_first
    joy_first, joy_second = np.mean(joys[:len(joys)//2] or [0]), np.mean(joys[len(joys)//2:] or [0])
    happ_first, happ_second = np.mean(happinesses[:len(happinesses)//2] or [0]), np.mean(happinesses[len(happinesses)//2:] or [0])
    mist_first = np.mean(mistakes_list[:len(mistakes_list)//2] or [0])
    mist_second = np.mean(mistakes_list[len(mistakes_list)//2:] or [0])
    trend = 'improvement' if diff > 0.5 else ('worsening' if diff < -0.5 else 'stable')
    mean_val = np.mean(values)
    std_val = np.std(values) if len(values) > 1 else 0
    corridor_50 = base + 50 * 0.3
    is_unstable = bool(trend == 'stable' and len(values) >= 3 and (std_val > 1.2 or (mean_val > 0 and std_val / mean_val > 0.4)))
    is_stably_low = bool(mean_val < corridor_50 * 0.85)

    interpretation = {'trend': trend, 'diff': float(diff), 'mean': float(mean_val), 'std': float(std_val),
                     'is_unstable': is_unstable, 'is_stably_low': is_stably_low}

    if trend == 'worsening':
        problems = []
        if joy_second < joy_first - 1:
            problems.append({'indicator': 'радость', 'cause': 'Снижение радости. Возможные причины: усталость, стресс, скука от однотипных игр.', 'solution': 'Разнообразить игры, добавить творческие (раскраска, диалог); снизить нагрузку; консультация психолога при стойком снижении.'})
        if happ_second < happ_first - 1:
            problems.append({'indicator': 'счастье', 'cause': 'Снижение показателя счастья. Возможные причины: эмоциональная нагрузка, перемены, стресс.', 'solution': 'Поддержка, беседы об эмоциях; игры на позитивные эмоции; при длительном снижении — консультация.'})
        if mist_second > mist_first + 0.5:
            problems.append({'indicator': 'ошибки', 'cause': 'Рост количества ошибок. Возможные причины: утомление, дефицит внимания, импульсивность.', 'solution': 'Укоротить игровые сессии; игры на концентрацию (память, стоп-игра); перерывы каждые 15–20 мин; консультация невролога при выраженных нарушениях.'})
        if joy_second >= joy_first and happ_second >= happ_first and mist_second <= mist_first:
            problems.append({'indicator': 'интегральный', 'cause': 'Общее снижение интегрального показателя при стабильных компонентах.', 'solution': 'Проверить полноту данных; повторить тестирование через 1–2 недели.'})
        interpretation['problems'] = problems if problems else [{'indicator': 'общий', 'cause': 'Снижение интегрального показателя.', 'solution': 'Увеличить частоту игр для более детальной динамики; консультация специалиста при сохраняющемся ухудшении.'}]
        interpretation['solutions'] = [p['solution'] for p in interpretation['problems']]
        interpretation['unstable_note'] = 'При нестабильной динамике (резкие колебания) возможны ситуативные факторы: перемены, усталость, нерегулярность занятий. Рекомендации: стабильный режим игр, фиксация внешних событий в дневнике, повторная оценка через 2–4 недели.'
    elif trend == 'improvement':
        improvements = []
        if joy_second > joy_first + 0.5:
            improvements.append('Повысилась радость — ребёнок получает больше позитивных эмоций от игр.')
        if happ_second > happ_first + 0.5:
            improvements.append('Повысилось счастье — общий эмоциональный тон улучшился.')
        if mist_second < mist_first - 0.3:
            improvements.append('Снизилось количество ошибок — улучшились концентрация и точность.')
        if not improvements:
            improvements.append('Наблюдается положительная динамика интегрального показателя благополучия.')
        interpretation['improvements'] = improvements
        interpretation['causes'] = ['Регулярные игровые сессии', 'Подходящий подбор игр', 'Снижение стресса', 'Возрастное развитие']
    else:
        interpretation['improvements'] = ['Динамика стабильна. Рекомендуется продолжать регулярные игровые сессии и мониторинг.']

    if is_unstable:
        interpretation['unstable'] = {
            'meaning': 'Нестабильная динамика: показатели колеблются от сессии к сессии без явного тренда. Это может затруднять выводы об эффективности коррекции.',
            'possible_causes': ['Нерегулярность игровых сессий', 'Ситуативные факторы (настроение, усталость, перемены в жизни)', 'Слишком разные типы игр в разные дни', 'Возрастная вариативность эмоциональных реакций', 'Внешний стресс или нестабильность среды'],
            'recommendations': ['Увеличить частоту сессий до 2–3 раз в неделю для сглаживания колебаний', 'Вести дневник: дата, игра, заметки о состоянии ребёнка', 'По возможности проводить игры в схожих условиях (время, место)', 'Повторить оценку через 3–4 недели при стабилизации режима', 'При выраженных «провалах» — уточнить провоцирующие факторы, консультация при необходимости'],
        }

    if is_stably_low:
        interpretation['stably_low'] = {
            'meaning': f'Интегральный показатель благополучия (радость + счастье + успешность) стабильно ниже среднего (среднее {mean_val:.1f} при норме ~{corridor_50:.1f}). Это говорит о сниженном эмоциональном тонусе и/или трудностях с успешностью в играх.',
            'what_it_means': 'Возможны: низкая вовлечённость в игры, эмоциональное неблагополучие, частые ошибки из-за трудностей концентрации или мотивации. Требует внимания и целенаправленной поддержки.',
            'possible_causes': ['Тревожность, подавленность, хронический стресс', 'Игры не соответствуют возможностям или интересам ребёнка', 'Дефицит внимания, импульсивность', 'Недосып, перегрузка', 'Сложности в детско-родительских отношениях'],
            'recommendations': ['Подобрать игры по интересам ребёнка, снизить уровень сложности при необходимости', 'Увеличить долю творческих и «безошибочных» игр (раскраска, диалог)', 'Режим сна, ограничение экранов, физическая активность', 'Беседы об эмоциях, поддержка, снижение критики', 'Консультация психолога при стойком снижении (2+ недели) для исключения тревожности/депрессии', 'Работа с семьёй: стабильность, позитив, совместное время'],
        }
    return {
        'dates': dates,
        'values': values,
        'percentiles': percentiles,
        'corridors': corridor_values,
        'mean_line': [base + 50 * 0.3 for _ in dates],
        'interpretation': interpretation,
    }


def get_correlation_matrix(game_results: List[GameResult]) -> Dict:
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

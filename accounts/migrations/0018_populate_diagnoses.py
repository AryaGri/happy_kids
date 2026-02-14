# Generated manually - начальные диагнозы/эмоциональные состояния

from django.db import migrations


def create_diagnoses(apps, schema_editor):
    DiagnosticDiagnosis = apps.get_model('accounts', 'DiagnosticDiagnosis')
    diagnoses = [
        {
            'name': 'Повышенная тревожность',
            'code': 'anxiety',
            'fuzzy_conditions': {'emotional_profile.грусть': 0.4, 'motivational_potential.низкий': 0.4},
            'default_recommendations': 'Рекомендуются успокаивающие игры, дыхательные упражнения. Консультация психолога для оценки уровня тревожности.',
            'default_prescription_type': 'therapy',
            'default_prescription_text': 'Игровая терапия, релаксационные техники 2-3 раза в неделю',
            'priority': 1,
        },
        {
            'name': 'Импульсивность',
            'code': 'impulsivity',
            'fuzzy_conditions': {'objectivity.низкая': 0.5},
            'default_recommendations': 'Упражнения на развитие произвольного внимания и самоконтроля. Игры с последовательным выполнением инструкций, задания с отсроченным ответом.',
            'default_prescription_type': 'exercise',
            'default_prescription_text': 'Упражнения на концентрацию внимания 15-20 мин ежедневно',
            'priority': 2,
        },
        {
            'name': 'Сниженная мотивация',
            'code': 'low_motivation',
            'fuzzy_conditions': {'motivational_potential.низкий': 0.6},
            'default_recommendations': 'Короткие игровые сессии с элементами поощрения. Постепенное увеличение сложности. Выбор игр по интересам ребёнка.',
            'default_prescription_type': 'recommendation',
            'default_prescription_text': 'Игровые сессии до 10-15 мин с перерывами, система поощрений',
            'priority': 3,
        },
        {
            'name': 'Эмоциональная нестабильность (гнев)',
            'code': 'anger_elevated',
            'fuzzy_conditions': {'emotional_profile.гнев': 0.35},
            'default_recommendations': 'Элементы релаксации, упражнения на выражение эмоций. Арт-терапия, песочная терапия.',
            'default_prescription_type': 'therapy',
            'default_prescription_text': 'Арт-терапия, техники управления гневом',
            'priority': 4,
        },
        {
            'name': 'Преобладание грусти',
            'code': 'sadness_dominant',
            'fuzzy_conditions': {'emotional_profile.грусть': 0.35},
            'default_recommendations': 'Консультация психолога для выяснения причин. Поддерживающая среда, игры на позитивные эмоции.',
            'default_prescription_type': 'recommendation',
            'default_prescription_text': 'Консультация детского психолога, наблюдение',
            'priority': 5,
        },
        {
            'name': 'Высокая скука / недостаточная вовлечённость',
            'code': 'boredom_high',
            'fuzzy_conditions': {'emotional_profile.скука': 0.35},
            'default_recommendations': 'Увеличить сложность заданий или разнообразить игры. Проверить соответствие заданий возрасту и возможностям.',
            'default_prescription_type': 'recommendation',
            'default_prescription_text': 'Адаптация сложности игр под уровень ребёнка',
            'priority': 6,
        },
        {
            'name': 'Благоприятный профиль',
            'code': 'favorable',
            'fuzzy_conditions': {'diagnostic_depth.высокая': 0.5, 'motivational_potential.высокий': 0.5},
            'default_recommendations': 'Благоприятные условия для диагностики. Можно проводить углублённую диагностику. Продолжать регулярный мониторинг.',
            'default_prescription_type': 'recommendation',
            'default_prescription_text': 'Продолжить игровые сессии для мониторинга',
            'priority': 10,
        },
    ]
    for d in diagnoses:
        DiagnosticDiagnosis.objects.get_or_create(code=d['code'], defaults=d)


def reverse_func(apps, schema_editor):
    DiagnosticDiagnosis = apps.get_model('accounts', 'DiagnosticDiagnosis')
    DiagnosticDiagnosis.objects.filter(
        code__in=['anxiety', 'impulsivity', 'low_motivation', 'anger_elevated', 
                  'sadness_dominant', 'boredom_high', 'favorable']
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0017_add_diagnostic_diagnosis'),
    ]

    operations = [
        migrations.RunPython(create_diagnoses, reverse_func),
    ]

# Generated manually for fuzzy logic models

from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0013_alter_prescription_options_alter_prescription_text'),
    ]

    operations = [
        # Добавляем created_at в CUsers с default для существующих строк
        migrations.AddField(
            model_name='cusers',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='cusers',
            name='connection_code',
            field=models.CharField(blank=True, max_length=10, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='cusers',
            name='code_expires',
            field=models.DateTimeField(blank=True, null=True),
        ),
        # FuzzyLinguisticVariable
        migrations.CreateModel(
            name='FuzzyLinguisticVariable',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='название')),
                ('description', models.TextField(blank=True, verbose_name='описание')),
                ('terms', models.JSONField(default=dict, verbose_name='термы')),
                ('purpose', models.CharField(blank=True, max_length=200, verbose_name='назначение')),
            ],
            options={
                'verbose_name': 'Лингвистическая переменная',
                'verbose_name_plural': 'Лингвистические переменные',
            },
        ),
        # GameSession
        migrations.CreateModel(
            name='GameSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('game_type', models.CharField(choices=[('Painting', 'Раскраска'), ('Dialog', 'Диалог'), ('Choice', 'Выбор'), ('Puzzle', 'Головоломка'), ('Memory', 'Память'), ('Adventure', 'Приключение')], max_length=20)),
                ('start_time', models.DateTimeField(auto_now_add=True)),
                ('end_time', models.DateTimeField(blank=True, null=True)),
                ('completed', models.BooleanField(default=False)),
                ('behavior_trajectory', models.JSONField(default=list)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='game_sessions', to='accounts.cusers')),
            ],
            options={
                'verbose_name': 'Игровая сессия',
                'verbose_name_plural': 'Игровые сессии',
            },
        ),
        # DoctorLicense
        migrations.CreateModel(
            name='DoctorLicense',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('license_number', models.CharField(max_length=50, unique=True, verbose_name='номер лицензии')),
                ('license_file', models.FileField(blank=True, null=True, upload_to='licenses/', verbose_name='файл лицензии')),
                ('license_scan', models.TextField(blank=True, verbose_name='текст лицензии')),
                ('is_verified', models.BooleanField(default=False, verbose_name='проверено')),
                ('verified_date', models.DateTimeField(blank=True, null=True, verbose_name='дата проверки')),
                ('rejection_reason', models.TextField(blank=True, verbose_name='причина отказа')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='license', to='accounts.cusers')),
                ('verified_by', models.ForeignKey(blank=True, limit_choices_to={'role': 'admin'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='verified_doctors', to='accounts.cusers')),
            ],
            options={
                'verbose_name': 'Лицензия врача',
                'verbose_name_plural': 'Лицензии врачей',
            },
        ),
        # FuzzyMembershipFunction
        migrations.CreateModel(
            name='FuzzyMembershipFunction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('method_class', models.CharField(choices=[('traditional_test', 'Стандартизированный тест'), ('projective', 'Проективный метод'), ('observation', 'Наблюдение'), ('digital_game', 'Цифровая игра'), ('hybrid', 'Гибридный метод')], max_length=50)),
                ('membership_values', models.JSONField(default=dict, verbose_name='значения принадлежности')),
                ('rationale', models.TextField(blank=True, verbose_name='обоснование')),
                ('variable', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='memberships', to='accounts.fuzzylinguisticvariable')),
            ],
            options={
                'verbose_name': 'Функция принадлежности',
                'verbose_name_plural': 'Функции принадлежности',
                'unique_together': {('method_class', 'variable')},
            },
        ),
        # DiagnosticProfile
        migrations.CreateModel(
            name='DiagnosticProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('diagnostic_depth', models.JSONField(default=dict, verbose_name='диагностическая глубина')),
                ('motivational_potential', models.JSONField(default=dict, verbose_name='мотивационный потенциал')),
                ('objectivity', models.JSONField(default=dict, verbose_name='объективность и стандартизация')),
                ('ecological_validity', models.JSONField(default=dict, verbose_name='экологическая валидность')),
                ('dynamic_assessment', models.JSONField(default=dict, verbose_name='потенциал для динамической оценки')),
                ('cognitive_style', models.CharField(blank=True, choices=[('systematic', 'Систематический'), ('impulsive', 'Импульсивный'), ('adaptive', 'Адаптивный'), ('chaotic', 'Хаотичный')], max_length=50)),
                ('emotional_profile', models.JSONField(default=dict)),
                ('recommendations', models.TextField(blank=True)),
                ('child', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='diagnostic_profiles', to='accounts.cusers')),
                ('based_on_sessions', models.ManyToManyField(blank=True, related_name='profiles', to='accounts.gamesession')),
            ],
            options={
                'verbose_name': 'Диагностический профиль',
                'verbose_name_plural': 'Диагностические профили',
                'ordering': ['-date_created'],
            },
        ),
        # FuzzyInferenceRule
        migrations.CreateModel(
            name='FuzzyInferenceRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('condition', models.JSONField()),
                ('conclusion', models.TextField()),
                ('recommendation', models.TextField()),
                ('confidence', models.FloatField(default=1.0)),
            ],
            options={
                'verbose_name': 'Правило нечёткого вывода',
                'verbose_name_plural': 'Правила нечёткого вывода',
            },
        ),
        # BehaviorPattern
        migrations.CreateModel(
            name='BehaviorPattern',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('pattern_type', models.CharField(choices=[('strategy', 'Стратегия решения'), ('attention', 'Внимание'), ('emotion', 'Эмоциональная реакция'), ('social', 'Социальное поведение')], max_length=50)),
                ('description', models.TextField()),
                ('fuzzy_sets', models.JSONField(default=dict)),
                ('relevant_games', models.JSONField(default=list)),
            ],
            options={
                'verbose_name': 'Поведенческий паттерн',
                'verbose_name_plural': 'Поведенческие паттерны',
            },
        ),
        # Subscription
        migrations.CreateModel(
            name='Subscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('subscription_type', models.CharField(choices=[('parent_individual', 'Родитель (индивидуальная)'), ('parent_family', 'Родитель (семейная)'), ('psychologist_individual', 'Психолог (индивидуальный)'), ('clinic_small', 'Клиника (до 3 врачей)'), ('clinic_medium', 'Клиника (4-10 врачей)'), ('clinic_large', 'Клиника (11+ врачей)'), ('kindergarten', 'Детский сад')], max_length=50)),
                ('max_children', models.IntegerField(default=1)),
                ('max_doctors', models.IntegerField(default=1)),
                ('start_date', models.DateTimeField(auto_now_add=True)),
                ('end_date', models.DateTimeField()),
                ('is_active', models.BooleanField(default=True)),
                ('price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('payment_id', models.CharField(blank=True, max_length=100)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='subscription', to='accounts.cusers')),
            ],
            options={
                'verbose_name': 'Подписка',
                'verbose_name_plural': 'Подписки',
            },
        ),
        # Add session FK to GameResult, alter GameResult fields
        migrations.AddField(
            model_name='gameresult',
            name='session',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='results', to='accounts.gamesession'),
        ),
        migrations.AddField(
            model_name='gameresult',
            name='reaction_time',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='gameresult',
            name='reaction_times',
            field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name='gameresult',
            name='mistakes',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='gameresult',
            name='mistake_types',
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name='gameresult',
            name='hints_used',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='gameresult',
            name='hint_timing',
            field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name='gameresult',
            name='strategy_type',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='gameresult',
            name='accuracy',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='gameresult',
            name='performance_metrics',
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name='gameresult',
            name='fuzzy_analysis',
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name='gameresult',
            name='drawing_data',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='gameresult',
            name='final_image',
            field=models.ImageField(blank=True, null=True, upload_to='drawings/'),
        ),
        migrations.AddField(
            model_name='gameresult',
            name='dialog_answers',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='gameresult',
            name='choices',
            field=models.JSONField(blank=True, null=True),
        ),
        # Prescription additional fields (doctor nullable for existing rows)
        migrations.AddField(
            model_name='prescription',
            name='doctor',
            field=models.ForeignKey(blank=True, limit_choices_to={'role': 'doctor'}, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='prescriptions_written', to='accounts.cusers'),
        ),
        migrations.AddField(
            model_name='prescription',
            name='prescription_type',
            field=models.CharField(choices=[('medication', 'Лекарство'), ('therapy', 'Терапия'), ('exercise', 'Упражнение'), ('recommendation', 'Рекомендация')], default='recommendation', max_length=50),
        ),
        migrations.AddField(
            model_name='prescription',
            name='medication_name',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='prescription',
            name='dosage',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='prescription',
            name='duration',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='prescription',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
    ]

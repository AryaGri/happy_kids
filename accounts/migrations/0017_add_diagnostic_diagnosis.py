# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0016_create_admin_user'),
    ]

    operations = [
        migrations.CreateModel(
            name='DiagnosticDiagnosis',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150, verbose_name='название')),
                ('code', models.CharField(help_text='Уникальный код для сопоставления', max_length=50, unique=True, verbose_name='код')),
                ('fuzzy_conditions', models.JSONField(default=dict, verbose_name='условия')),
                ('default_recommendations', models.TextField(verbose_name='рекомендации по умолчанию')),
                ('default_prescription_type', models.CharField(choices=[('medication', 'Лекарство'), ('therapy', 'Терапия'), ('exercise', 'Упражнение'), ('recommendation', 'Рекомендация')], default='recommendation', max_length=50, verbose_name='тип назначения')),
                ('default_prescription_text', models.TextField(blank=True, verbose_name='текст назначения по умолчанию')),
                ('priority', models.IntegerField(default=0, verbose_name='приоритет')),
            ],
            options={
                'verbose_name': 'Диагностический диагноз',
                'verbose_name_plural': 'Диагностические диагнозы',
                'ordering': ['priority', 'name'],
            },
        ),
        migrations.AddField(
            model_name='diagnosticprofile',
            name='detected_diagnoses',
            field=models.JSONField(default=list, verbose_name='выявленные диагнозы'),
        ),
    ]

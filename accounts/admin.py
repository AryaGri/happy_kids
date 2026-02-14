from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import CUsers, GameResult, Prescription, DiagnosticDiagnosis

# Регистрация модели CUsers в админке
@admin.register(CUsers)
class CUsersAdmin(admin.ModelAdmin):
    list_display = ['username', 'name', 'role', 'is_auth', 'date_of_b', 'linked_parents', 'linked_doctors']
    list_filter = ['role', 'is_auth']
    search_fields = ['username', 'name']
    filter_horizontal = ('children', 'patients')
    readonly_fields = ['parents_display', 'doctors_display']

    def linked_parents(self, obj):
        if obj.role != 'child':
            return '—'
        parents = obj.parents.all()
        if not parents:
            return 'Не привязан'
        return ', '.join(f'{p.name} ({p.username})' for p in parents[:3])
    linked_parents.short_description = 'Родители'

    def linked_doctors(self, obj):
        if obj.role != 'child':
            return '—'
        doctors = obj.doctors.all()
        if not doctors:
            return 'Не привязан'
        return ', '.join(f'{d.name} ({d.username})' for d in doctors[:3])
    linked_doctors.short_description = 'Врачи'

    def parents_display(self, obj):
        if obj.role != 'child':
            return '—'
        parents = obj.parents.all()
        if not parents:
            return 'Не привязан ни к одному родителю'
        items = []
        for p in parents:
            url = reverse('admin:accounts_cusers_change', args=[p.id])
            items.append(format_html('<li>{} ({}) — <a href="{}">открыть</a></li>', p.name, p.username, url))
        return format_html('<ul>{}</ul>', mark_safe(''.join(str(i) for i in items)))
    parents_display.short_description = 'Привязанные родители'

    def doctors_display(self, obj):
        if obj.role != 'child':
            return '—'
        doctors = obj.doctors.all()
        if not doctors:
            return 'Не привязан ни к одному врачу'
        items = []
        for d in doctors:
            url = reverse('admin:accounts_cusers_change', args=[d.id])
            items.append(format_html('<li>{} ({}) — <a href="{}">открыть</a></li>', d.name, d.username, url))
        return format_html('<ul>{}</ul>', mark_safe(''.join(str(i) for i in items)))
    doctors_display.short_description = 'Привязанные врачи'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related('parents', 'doctors')

    def get_fieldsets(self, request, obj=None):
        fieldsets = [
            (None, {'fields': ['username', 'name', 'date_of_b', 'role', 'password', 'is_auth']}),
            ('Связи', {'fields': ['children', 'patients']}),
            ('Код подключения', {'fields': ['connection_code', 'code_expires'], 'classes': ['collapse']}),
        ]
        if obj and getattr(obj, 'pk', None) and obj.role == 'child':
            fieldsets.insert(1, ('Привязки', {
                'fields': ['parents_display', 'doctors_display'],
                'description': 'К кому привязан ребёнок (только для просмотра)',
            }))
        return fieldsets

# Регистрация модели GameResult в админке
@admin.register(GameResult)
class GameResultAdmin(admin.ModelAdmin):
    list_display = ['user', 'game_type', 'date', 'joy', 'sorrow', 'love', 'anger', 'boredom', 'happiness']
    list_filter = ['game_type', 'date']
    search_fields = ['user__username', 'game_type']
    raw_id_fields = ['user']
    autocomplete_fields = ['user']

@admin.register(DiagnosticDiagnosis)
class DiagnosticDiagnosisAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'priority', 'default_prescription_type']
    list_editable = ['priority']
    search_fields = ['name', 'code']

@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ['child', 'text', 'date_created']
    list_filter = ['date_created', 'child']
    search_fields = ['child__username', 'text']
    ordering = ['-date_created']
    fields = ['child', 'text', 'date_created']
    readonly_fields = ['date_created',]  # Сделать поле date_created только для чтения

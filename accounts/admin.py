from django.contrib import admin
from .models import CUsers, GameResult, Prescription

# Регистрация модели CUsers в админке
@admin.register(CUsers)
class CUsersAdmin(admin.ModelAdmin):
    list_display = ['username', 'name', 'role', 'is_auth', 'date_of_b']
    list_filter = ['role', 'is_auth']
    search_fields = ['username', 'name']
    filter_horizontal = ('children',)

# Регистрация модели GameResult в админке
@admin.register(GameResult)
class GameResultAdmin(admin.ModelAdmin):
    list_display = ['user', 'game_type', 'date', 'joy', 'sorrow', 'love', 'anger', 'boredom', 'happiness']
    list_filter = ['game_type', 'date']
    search_fields = ['user__username', 'game_type']
    raw_id_fields = ['user']
    autocomplete_fields = ['user']

@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ['child', 'text', 'date_created']
    list_filter = ['date_created', 'child']
    search_fields = ['child__username', 'text']
    ordering = ['-date_created']
    fields = ['child', 'text', 'date_created']
    readonly_fields = ['date_created',]  # Сделать поле date_created только для чтения

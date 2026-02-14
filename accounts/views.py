from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Avg, Count
from django.db.models.functions import TruncDate
from django.contrib.auth import logout
import json
import os
import base64
import uuid
from datetime import datetime, timedelta, date
from collections import defaultdict
from django.core.files.base import ContentFile

from .forms import (
    LoginForm, UserCreateForm, PrescriptionForm, DoctorRegistrationForm,
    ParentRegistrationForm, ChildRegistrationForm, ConnectionCodeForm,
    DoctorVerificationForm, DoctorLicenseEditForm, UserEditForm, ProfileSelfEditForm,
    ChildAssignForm, DateRangeFilterForm, SubscriptionForm, FeedbackForm,
    PasswordChangeForm, BulkChildAssignForm, BulkDoctorAssignForm
)
from .models import (
    CUsers, GameResult, Prescription, DoctorLicense, GameSession,
    DiagnosticProfile, Subscription, FuzzyLinguisticVariable,
    BehaviorPattern, EMOTIONS
)
from .fuzzy_logic import FuzzyAnalyzer, init_fuzzy_variables
from django.conf import settings


# ==================== БАЗОВЫЕ ПРЕДСТАВЛЕНИЯ ====================

def base_view(request):
    """Главная страница"""
    return render(request, 'main.html')


def login_view(request):
    """Авторизация пользователя"""
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            
            try:
                user = CUsers.objects.get(username=username)
                if user.check_password(password):
                    # Сохраняем пользователя в сессии
                    request.session['user_id'] = user.id
                    request.session['user_role'] = user.role
                    request.session['user_name'] = user.name
                    
                    messages.success(request, f'Добро пожаловать, {user.name}!')
                    
                    # Перенаправление в зависимости от роли
                    if user.role == 'admin':
                        return redirect('admin_dashboard')
                    elif user.role == 'doctor':
                        # Проверяем статус лицензии
                        try:
                            license = user.license
                            if not license.is_verified:
                                messages.warning(request, 'Ваша лицензия ещё не проверена администратором')
                        except DoctorLicense.DoesNotExist:
                            messages.warning(request, 'Пожалуйста, заполните информацию о лицензии')
                        return redirect('doctor_dashboard')
                    elif user.role == 'parent':
                        return redirect('parent_dashboard', user_id=user.id)
                    elif user.role == 'child':
                        return redirect('game_dashboard', user_id=user.id)
                else:
                    messages.error(request, 'Неверный пароль!')
            except CUsers.DoesNotExist:
                messages.error(request, 'Пользователь не найден!')
    else:
        form = LoginForm()
    
    return render(request, 'login.html', {'form': form})


def logout_view(request):
    """Выход из системы"""
    request.session.flush()
    logout(request)
    messages.success(request, 'Вы успешно вышли из системы')
    return redirect('home')


def register_view(request, user_id=None):
    """Регистрация нового пользователя (выбор роли)"""
    return render(request, 'register_choice.html')


def register_doctor_view(request):
    """Регистрация врача"""
    if request.method == 'POST':
        form = DoctorRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            messages.success(
                request, 
                'Регистрация успешна! Ваша лицензия будет проверена администратором. '
                'Вы получите уведомление после проверки.'
            )
            return redirect('login')
    else:
        form = DoctorRegistrationForm()
    
    return render(request, 'register_doctor.html', {'form': form, 'today': date.today().isoformat()})


def register_parent_view(request):
    """Регистрация родителя"""
    if request.method == 'POST':
        form = ParentRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, 'Регистрация успешна! Теперь вы можете войти.')
            return redirect('login')
    else:
        form = ParentRegistrationForm()
    
    return render(request, 'register_parent.html', {'form': form, 'today': date.today().isoformat()})


def register_child_view(request):
    """Регистрация ребёнка"""
    if request.method == 'POST':
        form = ChildRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, 'Регистрация успешна! Запомните ваш код для подключения к родителю.')
            return redirect('login')
    else:
        form = ChildRegistrationForm()
    
    return render(request, 'register_child.html', {'form': form, 'today': date.today().isoformat()})


# ==================== ПРЕДСТАВЛЕНИЯ ДЛЯ АДМИНИСТРАТОРА ====================

def admin_dashboard_view(request):
    """Панель администратора"""
    # Проверка прав доступа
    if request.session.get('user_role') != 'admin':
        return HttpResponseForbidden('Доступ запрещён')
    
    # Фильтрация по роли (администраторов не показываем в списке — их нельзя редактировать/создавать)
    role_filter = request.GET.get('role')
    search_query = request.GET.get('search', '').strip()
    sort = request.GET.get('sort', '')
    users = CUsers.objects.exclude(role='admin')
    if role_filter:
        users = users.filter(role=role_filter)
    if search_query:
        users = users.filter(Q(name__icontains=search_query) | Q(username__icontains=search_query))
    if sort == 'name':
        users = users.order_by('name', '-created_at')
    elif sort == '-name':
        users = users.order_by('-name', '-created_at')
    elif sort == 'age':
        users = users.order_by('date_of_b', 'name')  # старше первыми
    elif sort == '-age':
        users = users.order_by('-date_of_b', 'name')  # младше первыми
    else:
        users = users.order_by('-created_at', 'name')
    
    # Статистика
    total_users = CUsers.objects.count()
    doctors_count = CUsers.objects.filter(role='doctor').count()
    parents_count = CUsers.objects.filter(role='parent').count()
    children_count = CUsers.objects.filter(role='child').count()
    
    # Непроверенные лицензии
    pending_licenses = DoctorLicense.objects.filter(is_verified=False).select_related('user')
    
    # Последние регистрации
    recent_users = CUsers.objects.order_by('-created_at')[:10]
    
    context = {
        'users': users,
        'total_users': total_users,
        'doctors_count': doctors_count,
        'parents_count': parents_count,
        'children_count': children_count,
        'pending_licenses': pending_licenses,
        'recent_users': recent_users,
        'role_filter': role_filter,
        'search_query': search_query,
        'sort': sort,
    }
    
    return render(request, 'admin_dashboard.html', context)


def admin_verify_licenses_view(request):
    """Просмотр и проверка лицензий врачей"""
    if request.session.get('user_role') != 'admin':
        return HttpResponseForbidden('Доступ запрещён')
    
    licenses = DoctorLicense.objects.all().select_related('user').order_by('-created_at')
    
    # Фильтр по статусу
    status = request.GET.get('status')
    if status == 'pending':
        licenses = licenses.filter(is_verified=False)
    elif status == 'verified':
        licenses = licenses.filter(is_verified=True)
    
    # Поиск по ФИО или номеру лицензии
    search = request.GET.get('search', '').strip()
    if search:
        licenses = licenses.filter(
            Q(user__name__icontains=search) | Q(license_number__icontains=search)
        )
    
    # Пагинация
    paginator = Paginator(licenses, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'licenses': page_obj,
        'page_obj': page_obj,
        'status': status,
        'search': search,
    }
    
    return render(request, 'admin_verify_licenses.html', context)


def admin_verify_license_detail_view(request, license_id):
    """Детальный просмотр и проверка лицензии"""
    if request.session.get('user_role') != 'admin':
        return HttpResponseForbidden('Доступ запрещён')
    
    license_obj = get_object_or_404(DoctorLicense, id=license_id)
    admin_id = request.session.get('user_id')
    admin = get_object_or_404(CUsers, id=admin_id, role='admin')
    
    if request.method == 'POST':
        form = DoctorVerificationForm(request.POST, instance=license_obj, admin=admin)
        if form.is_valid():
            form.save()
            # Перезагружаем объект после save
            license_obj.refresh_from_db()
            if license_obj.is_verified:
                messages.success(request, f'Лицензия {license_obj.license_number} подтверждена')
            else:
                messages.info(request, f'Лицензия {license_obj.license_number} отклонена')
            return redirect('admin_verify_licenses')
    else:
        form = DoctorVerificationForm(instance=license_obj)
    
    # Текущее решение для отображения в форме (при ошибках — из POST)
    decision = form.data.get('is_verified') if form.is_bound else str(license_obj.is_verified)
    
    context = {
        'license': license_obj,
        'form': form,
        'decision': decision,
    }
    
    return render(request, 'admin_verify_license_detail.html', context)


def admin_delete_user_view(request, id):
    """Удаление пользователя (только не-администраторы)"""
    if request.session.get('user_role') != 'admin':
        return HttpResponseForbidden('Доступ запрещён')
    
    user = get_object_or_404(CUsers, pk=id)
    if user.role == 'admin':
        messages.error(request, 'Нельзя удалить администратора')
        return redirect('admin_dashboard')
    
    if request.method == 'POST':
        name = user.name
        user.delete()
        messages.success(request, f'Пользователь {name} удалён')
        return redirect('admin_dashboard')
    
    return render(request, 'admin_delete_user_confirm.html', {'user': user})


def admin_bulk_assign_view(request):
    """Массовое назначение: дети родителям, пациенты врачу"""
    if request.session.get('user_role') != 'admin':
        return HttpResponseForbidden('Доступ запрещён')
    
    if request.method == 'POST':
        if 'patients' in request.POST:
            doctor_form = BulkDoctorAssignForm(request.POST)
            if doctor_form.is_valid():
                doctor = doctor_form.cleaned_data['doctor']
                patients = doctor_form.cleaned_data['patients']
                for patient in patients:
                    doctor.patients.add(patient)
                messages.success(request, f'{patients.count()} пациентов назначено врачу {doctor.name}')
                return redirect('admin_dashboard')
            parent_form = BulkChildAssignForm()
        else:
            parent_form = BulkChildAssignForm(request.POST)
            if parent_form.is_valid():
                parent = parent_form.cleaned_data['parent']
                children = parent_form.cleaned_data['children']
                for child in children:
                    parent.children.add(child)
                messages.success(request, f'{children.count()} детей привязаны к родителю {parent.name}')
                return redirect('admin_dashboard')
            doctor_form = BulkDoctorAssignForm()
    else:
        parent_form = BulkChildAssignForm()
        doctor_form = BulkDoctorAssignForm()
    
    context = {
        'parent_form': parent_form,
        'doctor_form': doctor_form,
    }
    
    return render(request, 'admin_bulk_assign.html', context)


def admin_statistics_view(request):
    """Статистика использования системы"""
    if request.session.get('user_role') != 'admin':
        return HttpResponseForbidden('Доступ запрещён')
    
    # Общая статистика
    total_games = GameResult.objects.count()
    total_sessions = GameSession.objects.count()
    active_doctors = CUsers.objects.filter(role='doctor', is_auth=True).count()
    active_parents = CUsers.objects.filter(role='parent', is_auth=True).count()
    
    # Статистика по играм
    games_by_type = GameResult.objects.values('game_type').annotate(count=Count('id'))
    
    # Эмоциональная статистика
    emotion_totals = GameResult.objects.aggregate(
        total_joy=Sum('joy'),
        total_sorrow=Sum('sorrow'),
        total_anger=Sum('anger'),
        total_love=Sum('love'),
        total_boredom=Sum('boredom'),
        total_happiness=Sum('happiness'),
    )
    
    # Активность по дням (последние 30 дней)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    daily_activity = list(
        GameResult.objects.filter(date__gte=thirty_days_ago)
        .annotate(day=TruncDate('date'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    # Приводим к формату {date, count} для шаблона
    daily_activity = [{'date': str(d['day']), 'count': d['count']} for d in daily_activity]
    
    context = {
        'total_games': total_games,
        'total_sessions': total_sessions,
        'active_doctors': active_doctors,
        'active_parents': active_parents,
        'games_by_type': games_by_type,
        'emotion_totals': emotion_totals,
        'daily_activity': daily_activity,
    }
    
    return render(request, 'admin_statistics.html', context)


# ==================== ПРЕДСТАВЛЕНИЯ ДЛЯ ВРАЧА ====================

def doctor_license_edit_view(request):
    """Редактирование лицензии врачом (после отклонения или обновление данных)"""
    if request.session.get('user_role') != 'doctor':
        return HttpResponseForbidden('Доступ запрещён')
    
    doctor_id = request.session.get('user_id')
    doctor = get_object_or_404(CUsers, id=doctor_id, role='doctor')
    
    try:
        license_obj = doctor.license
    except DoctorLicense.DoesNotExist:
        license_obj = DoctorLicense(user=doctor, license_number='', license_scan='', is_verified=False)
    
    if request.method == 'POST':
        form = DoctorLicenseEditForm(request.POST, request.FILES, instance=license_obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Данные лицензии обновлены. Заявка отправлена на повторную проверку администратору.')
            return redirect('doctor_dashboard')
    else:
        form = DoctorLicenseEditForm(instance=license_obj)
    
    context = {'form': form, 'license': license_obj}
    return render(request, 'doctor_license_edit.html', context)


def doctor_dashboard_view(request):
    """Панель врача"""
    if request.session.get('user_role') != 'doctor':
        return HttpResponseForbidden('Доступ запрещён')
    
    doctor_id = request.session.get('user_id')
    doctor = CUsers.objects.get(id=doctor_id)
    
    # Проверка лицензии
    try:
        license_obj = doctor.license
        if not license_obj.is_verified:
            messages.warning(request, 'Ваша лицензия ещё не проверена администратором. Доступ ограничен.')
            return render(request, 'doctor_pending.html', {'license': license_obj})
    except DoctorLicense.DoesNotExist:
        messages.warning(request, 'Пожалуйста, заполните информацию о лицензии в профиле.')
        return redirect('profile')
    
    # Присоединение пациента по коду
    if request.method == 'POST' and 'connect_code' in request.POST:
        code_form = ConnectionCodeForm(data=request.POST, user_role='doctor')
        if code_form.is_valid():
            child = code_form.connected_user
            doctor.patients.add(child)
            messages.success(request, f'Пациент {child.name} успешно добавлен')
            return redirect('doctor_dashboard')
        else:
            pass  # code_form с ошибками передадим в контекст
    else:
        code_form = ConnectionCodeForm(user_role='doctor')
    
    # Получаем пациентов врача (добавленных по коду)
    sort = request.GET.get('sort', 'name')
    if sort == 'name':
        patients = doctor.patients.all().order_by('name')
    elif sort == '-name':
        patients = doctor.patients.all().order_by('-name')
    elif sort == 'age':
        patients = doctor.patients.all().order_by('date_of_b')  # старше первыми
    elif sort == '-age':
        patients = doctor.patients.all().order_by('-date_of_b')  # младше первыми
    else:
        patients = doctor.patients.all().order_by('name')
    
    # Поиск
    search_query = request.GET.get('search')
    if search_query:
        patients = patients.filter(
            Q(name__icontains=search_query) | 
            Q(username__icontains=search_query)
        )
    
    # Пагинация
    paginator = Paginator(patients, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Последние результаты
    recent_results = GameResult.objects.select_related('user').order_by('-date')[:10]
    
    # Статистика
    total_patients = patients.count()
    total_prescriptions = Prescription.objects.filter(doctor=doctor).count()
    
    context = {
        'doctor': doctor,
        'patients': page_obj,
        'recent_results': recent_results,
        'total_patients': total_patients,
        'total_prescriptions': total_prescriptions,
        'search_query': search_query,
        'sort': sort,
        'code_form': code_form,
    }
    
    return render(request, 'doctor_dashboard.html', context)


def patient_detail_view(request, patient_id):
    """Детальная информация о пациенте для врача"""
    if request.session.get('user_role') != 'doctor':
        return HttpResponseForbidden('Доступ запрещён')
    
    doctor_id = request.session.get('user_id')
    doctor = CUsers.objects.get(id=doctor_id)
    patient = get_object_or_404(CUsers, id=patient_id, role='child')
    
    # Фильтр по дате
    form = DateRangeFilterForm(request.GET or None)
    game_results = GameResult.objects.filter(user=patient)
    
    if form.is_valid():
        date_from = form.cleaned_data.get('date_from')
        date_to = form.cleaned_data.get('date_to')
        game_type = form.cleaned_data.get('game_type')
        
        if date_from:
            game_results = game_results.filter(date__date__gte=date_from)
        if date_to:
            game_results = game_results.filter(date__date__lte=date_to)
        if game_type:
            game_results = game_results.filter(game_type=game_type)
    
    game_results = game_results.order_by('-date')
    
    # Суммарные эмоциональные показатели
    emotion_scores = {
        'гнев': sum(r.anger for r in game_results),
        'скука': sum(r.boredom for r in game_results),
        'радость': sum(r.joy for r in game_results),
        'счастье': sum(r.happiness for r in game_results),
        'грусть': sum(r.sorrow for r in game_results),
        'любовь': sum(r.love for r in game_results),
    }
    
    # Назначения
    prescriptions = Prescription.objects.filter(child=patient).order_by('-date_created')
    
    # Всегда пересчитываем профиль по актуальным результатам игр
    analyzer = FuzzyAnalyzer()
    profile = analyzer.create_diagnostic_profile(patient.id)
    
    # Данные для радарной диаграммы
    radar_data = profile.get_radar_data()
    
    # Поведенческие паттерны
    behavior_analysis = analyzer.analyze_error_patterns(game_results)
    
    # Обработка формы назначения
    if request.method == 'POST' and 'prescription' in request.POST:
        prescription_form = PrescriptionForm(request.POST, doctor=doctor)
        if prescription_form.is_valid():
            prescription = prescription_form.save(commit=False)
            prescription.child = patient
            prescription.doctor = doctor
            prescription.save()
            messages.success(request, 'Назначение добавлено')
            return redirect('patient_detail', patient_id=patient.id)
    else:
        prescription_form = PrescriptionForm()
    
    # Для графика эмоций (labels + data)
    emotion_labels = list(emotion_scores.keys())
    emotion_values = list(emotion_scores.values())
    
    # Выявленные диагнозы (только для врача)
    from .models import DiagnosticDiagnosis
    detected_diagnoses = DiagnosticDiagnosis.objects.filter(code__in=profile.detected_diagnoses) if profile.detected_diagnoses else []
    
    # Диагностическая панель
    from .diagnostic_panel import (
        get_fuzzy_analysis_for_panel,
        get_heatmap_data,
        get_dynamics_data,
        get_correlation_matrix,
        get_adaptive_recommendations,
        BASE_RECOMMENDATIONS,
        VARIABLE_DESCRIPTIONS,
    )
    panel_data = None
    adaptive_recs = []
    heatmap_data = {'matrix': [], 'systems': [], 'indicators': [], 'rows': []}
    dynamics_data = None
    corr_data = {'matrix': [], 'labels': [], 'rows': []}
    if game_results:
        try:
            gr_list = list(game_results)
            panel_data = get_fuzzy_analysis_for_panel(analyzer, profile, gr_list, patient)
            adaptive_recs = get_adaptive_recommendations(
                panel_data['params_results'],
                panel_data['diagnostic_params']
            )
            heatmap_data = get_heatmap_data(gr_list, profile)
            dynamics_data = get_dynamics_data(gr_list)
            corr_data = get_correlation_matrix(gr_list)
        except Exception:
            pass
    
    context = {
        'doctor': doctor,
        'patient': patient,
        'game_results': game_results,
        'detected_diagnoses': detected_diagnoses,
        'emotion_scores': emotion_scores,
        'emotion_chart_data': json.dumps({'labels': emotion_labels, 'data': emotion_values}),
        'prescriptions': prescriptions,
        'prescription_form': prescription_form,
        'filter_form': form,
        'profile': profile,
        'radar_data': json.dumps(radar_data),
        'behavior_analysis': behavior_analysis,
        'panel_data': panel_data,
        'panel_data_json': json.dumps(panel_data) if panel_data else 'null',
        'heatmap_data': heatmap_data,
        'heatmap_data_json': json.dumps(heatmap_data),
        'dynamics_data': dynamics_data,
        'dynamics_data_json': json.dumps(dynamics_data) if dynamics_data else 'null',
        'corr_data': corr_data,
        'corr_data_json': json.dumps(corr_data),
        'adaptive_recommendations': adaptive_recs,
        'base_recommendations': BASE_RECOMMENDATIONS,
        'variable_descriptions': VARIABLE_DESCRIPTIONS,
    }
    
    return render(request, 'patient_detail.html', context)


def patient_game_session_view(request, patient_id, session_id):
    """Просмотр детальной игровой сессии пациента"""
    if request.session.get('user_role') != 'doctor':
        return HttpResponseForbidden('Доступ запрещён')
    
    patient = get_object_or_404(CUsers, id=patient_id, role='child')
    session = get_object_or_404(GameSession, id=session_id, user=patient)
    results = GameResult.objects.filter(session=session)
    
    context = {
        'patient': patient,
        'session': session,
        'results': results,
    }
    
    return render(request, 'patient_game_session.html', context)


def doctor_analysis_view(request, patient_id):
    """Углублённый анализ с нечёткой логикой"""
    if request.session.get('user_role') != 'doctor':
        return HttpResponseForbidden('Доступ запрещён')
    
    patient = get_object_or_404(CUsers, id=patient_id, role='child')
    
    # Всегда пересчитываем профиль по актуальным результатам игр
    from .models import DiagnosticDiagnosis
    analyzer = FuzzyAnalyzer()
    profile = analyzer.create_diagnostic_profile(patient.id)
    detected_diagnoses = list(DiagnosticDiagnosis.objects.filter(code__in=profile.detected_diagnoses)) if profile.detected_diagnoses else []
    
    # Получаем все результаты
    game_results = GameResult.objects.filter(user=patient).select_related('session').order_by('date')
    
    # Анализ по времени (маппинг: русское название -> поле модели)
    EMOTION_TO_FIELD = {
        'гнев': 'anger', 'скука': 'boredom', 'радость': 'joy',
        'счастье': 'happiness', 'грусть': 'sorrow', 'любовь': 'love'
    }
    if len(game_results) >= 2:
        first_result = game_results.first()
        last_result = game_results.last()
        
        # Динамика эмоций
        emotion_dynamics = {}
        for emotion in EMOTIONS:
            field = EMOTION_TO_FIELD.get(emotion, emotion)
            first_val = getattr(first_result, field, 0)
            last_val = getattr(last_result, field, 0)
            emotion_dynamics[emotion] = {
                'first': first_val,
                'last': last_val,
                'change': last_val - first_val
            }
    else:
        emotion_dynamics = {}
    
    # Поведенческие траектории (из сессий)
    behavior_trajectories = []
    seen_sessions = set()
    for result in game_results:
        if result.session_id and result.session_id not in seen_sessions:
            session = result.session
            if session and session.behavior_trajectory:
                seen_sessions.add(result.session_id)
                behavior_trajectories.append({
                    'date': result.date.isoformat(),
                    'game_type': result.game_type,
                    'trajectory': session.behavior_trajectory
                })
    
    # Данные для графика динамики эмоций (по датам)
    emotion_chart_data = {
        'dates': [r.date.strftime('%d.%m.%Y') for r in game_results],
        'гнев': [r.anger for r in game_results],
        'скука': [r.boredom for r in game_results],
        'радость': [r.joy for r in game_results],
        'счастье': [r.happiness for r in game_results],
        'грусть': [r.sorrow for r in game_results],
        'любовь': [r.love for r in game_results],
    }
    
    context = {
        'patient': patient,
        'profile': profile,
        'game_results': game_results,
        'emotion_dynamics': emotion_dynamics,
        'emotion_chart_data': json.dumps(emotion_chart_data),
        'behavior_trajectories': behavior_trajectories,
        'radar_data': json.dumps(profile.get_radar_data()),
        'detected_diagnoses': detected_diagnoses,
    }
    
    return render(request, 'doctor_analysis.html', context)


# ==================== ПРЕДСТАВЛЕНИЯ ДЛЯ РОДИТЕЛЯ ====================

def parent_dashboard_view(request, user_id):
    """Панель родителя"""
    if request.session.get('user_role') != 'parent' or request.session.get('user_id') != user_id:
        return HttpResponseForbidden('Доступ запрещён')
    
    parent = get_object_or_404(CUsers, id=user_id, role='parent')
    sort = request.GET.get('sort', 'name')
    if sort == 'name':
        children = parent.children.all().order_by('name')
    elif sort == '-name':
        children = parent.children.all().order_by('-name')
    elif sort == 'age':
        children = parent.children.all().order_by('date_of_b')  # старше первыми
    elif sort == '-age':
        children = parent.children.all().order_by('-date_of_b')  # младше первыми
    else:
        children = parent.children.all().order_by('name')
    
    # Присоединение по коду
    if request.method == 'POST' and 'connect_code' in request.POST:
        code_form = ConnectionCodeForm(data=request.POST, user_role='parent')
        if code_form.is_valid():
            child = code_form.connected_user
            parent.children.add(child)
            messages.success(request, f'Ребёнок {child.name} успешно добавлен')
            return redirect('parent_dashboard', user_id=parent.id)
    else:
        code_form = ConnectionCodeForm(user_role='parent')
    
    # Статистика по детям
    children_stats = []
    for child in children:
        game_results = GameResult.objects.filter(user=child)
        total_games = game_results.count()
        last_game = game_results.order_by('-date').first()
        
        # Эмоциональный профиль
        emotion_profile = {}
        if game_results.exists():
            for emotion in EMOTIONS:
                emotion_profile[emotion] = sum(getattr(r, emotion, 0) for r in game_results)
        
        children_stats.append({
            'child': child,
            'total_games': total_games,
            'last_game': last_game,
            'emotion_profile': emotion_profile
        })
    
    context = {
        'parent': parent,
        'children_stats': children_stats,
        'sort': sort,
        'code_form': code_form,
    }
    
    return render(request, 'parent_dashboard.html', context)


def parent_child_detail_view(request, user_id, child_id):
    """Детальная информация о ребёнке для родителя (URL с user_id)"""
    if request.session.get('user_id') != user_id:
        return HttpResponseForbidden('Доступ запрещён')
    return child_detail_for_parent_view(request, child_id)


def child_detail_for_parent_view(request, child_id):
    """Детальная информация о ребёнке для родителя (упрощённая)"""
    parent_id = request.session.get('user_id')
    parent = get_object_or_404(CUsers, id=parent_id, role='parent')
    child = get_object_or_404(CUsers, id=child_id, role='child')
    
    # Проверяем, что это ребёнок данного родителя
    if not parent.children.filter(id=child.id).exists():
        return HttpResponseForbidden('Это не ваш ребёнок')
    
    # Родитель видит только агрегированную статистику, не конкретные результаты
    game_results = GameResult.objects.filter(user=child)
    games_count = game_results.count()
    
    # Упрощённые эмоциональные показатели (агрегированные)
    emotion_scores = {
        'радость': sum(r.joy + r.happiness for r in game_results),
        'грусть': sum(r.sorrow for r in game_results),
        'гнев': sum(r.anger for r in game_results),
        'спокойствие': sum(r.love for r in game_results) - sum(r.boredom for r in game_results),
    }
    
    # Нормализация (спокойствие может быть отрицательным — ограничиваем снизу)
    total = sum(max(0, v) for v in emotion_scores.values()) or 1
    emotion_percentages = {
        k: max(0, int(v / total * 100)) if total > 0 else 0
        for k, v in emotion_scores.items()
    }
    
    # Получаем назначения врача
    prescriptions = Prescription.objects.filter(child=child, is_active=True).order_by('-date_created')
    
    # Получаем диагностический профиль (если есть)
    profile = DiagnosticProfile.objects.filter(child=child).first()
    
    context = {
        'parent': parent,
        'child': child,
        'games_count': games_count,
        'emotion_percentages': emotion_percentages,
        'emotion_percentages_json': json.dumps(emotion_percentages),
        'prescriptions': prescriptions,
        'profile': profile,
    }
    
    return render(request, 'child_detail_parent.html', context)


def parent_download_prescriptions_view(request, child_id):
    """Скачивание назначений врача для ребёнка (PDF) — только для родителя"""
    parent_id = request.session.get('user_id')
    if request.session.get('user_role') != 'parent' or not parent_id:
        return HttpResponseForbidden('Доступ запрещён')
    
    parent = get_object_or_404(CUsers, id=parent_id, role='parent')
    child = get_object_or_404(CUsers, id=child_id, role='child')
    
    if not parent.children.filter(id=child.id).exists():
        return HttpResponseForbidden('Это не ваш ребёнок')
    
    prescriptions = Prescription.objects.filter(child=child, is_active=True).order_by('-date_created')
    
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from io import BytesIO
    except ImportError:
        # Fallback: простой текстовый файл без reportlab
        from io import BytesIO
        lines = [
            f'Назначения врача для {child.name}',
            f'Дата рождения: {child.date_of_b.strftime("%d.%m.%Y")}',
            '',
            '=' * 50,
        ]
        for p in prescriptions:
            type_display = dict(Prescription._meta.get_field('prescription_type').choices).get(p.prescription_type, p.prescription_type)
            lines.append(f'\n{type_display} — {p.date_created.strftime("%d.%m.%Y")}')
            lines.append(p.text)
            if p.medication_name:
                lines.append(f'Препарат: {p.medication_name}')
            if p.dosage:
                lines.append(f'Дозировка: {p.dosage}')
            if p.duration:
                lines.append(f'Длительность: {p.duration}')
            lines.append('')
        
        content = '\n'.join(lines).encode('utf-8')
        response = HttpResponse(content, content_type='text/plain; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="naznacheniya_{child.name.replace(" ", "_")}.txt"'
        return response
    
    # Шрифт с поддержкой кириллицы (без «закрытых» букв)
    cyrillic_font = None
    font_paths = [
        os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts', 'arial.ttf'),
        os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts', 'times.ttf'),
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
        '/usr/share/fonts/TTF/DejaVuSans.ttf',
    ]
    if hasattr(settings, 'BASE_DIR'):
        base = str(settings.BASE_DIR)
        font_paths.insert(0, os.path.join(base, 'static', 'fonts', 'DejaVuSans.ttf'))
    for fp in font_paths:
        if fp and os.path.exists(fp):
            try:
                pdfmetrics.registerFont(TTFont('CyrillicFont', fp))
                cyrillic_font = 'CyrillicFont'
                break
            except Exception:
                continue
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    base_styles = getSampleStyleSheet()
    
    if cyrillic_font:
        styles = {
            'Title': ParagraphStyle('Title', parent=base_styles['Title'], fontName=cyrillic_font, fontSize=16),
            'Normal': ParagraphStyle('Normal', parent=base_styles['Normal'], fontName=cyrillic_font, fontSize=11),
            'Heading2': ParagraphStyle('Heading2', parent=base_styles['Heading2'], fontName=cyrillic_font, fontSize=12),
        }
    else:
        styles = {'Title': base_styles['Title'], 'Normal': base_styles['Normal'], 'Heading2': base_styles['Heading2']}
    
    story = []
    
    story.append(Paragraph(f'Назначения врача для {child.name}', styles['Title']))
    story.append(Paragraph(f'Дата рождения: {child.date_of_b.strftime("%d.%m.%Y")}', styles['Normal']))
    story.append(Spacer(1, 0.5*cm))
    
    type_map = dict(Prescription._meta.get_field('prescription_type').choices)
    
    for p in prescriptions:
        type_display = type_map.get(p.prescription_type, p.prescription_type)
        story.append(Paragraph(f'<b>{type_display}</b> — {p.date_created.strftime("%d.%m.%Y")}', styles['Heading2']))
        story.append(Paragraph(p.text.replace('\n', '<br/>'), styles['Normal']))
        if p.medication_name or p.dosage or p.duration:
            extra = []
            if p.medication_name:
                extra.append(f'Препарат: {p.medication_name}')
            if p.dosage:
                extra.append(f'Дозировка: {p.dosage}')
            if p.duration:
                extra.append(f'Длительность: {p.duration}')
            story.append(Paragraph('<br/>'.join(extra), styles['Normal']))
        story.append(Spacer(1, 0.4*cm))
    
    doc.build(story)
    buffer.seek(0)
    
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    safe_name = ''.join(c if c.isalnum() or c in ' _-' else '_' for c in child.name)
    response['Content-Disposition'] = f'attachment; filename="naznacheniya_{safe_name}.pdf"'
    return response


# ==================== ПРЕДСТАВЛЕНИЯ ДЛЯ РЕБЁНКА ====================

def game_dashboard_view(request, user_id):
    """Панель ребёнка с выбором игр"""
    session_user_id = request.session.get('user_id')
    session_user_role = request.session.get('user_role')
    # Явное приведение к int — сессия может хранить значение в другом типе
    if session_user_role != 'child' or session_user_id is None or int(session_user_id) != int(user_id):
        return HttpResponseForbidden('Доступ запрещён')
    
    child = get_object_or_404(CUsers, id=user_id, role='child')
    # Генерируем код подключения, если его ещё нет
    if not child.connection_code:
        child.generate_connection_code()
        child.save()
    
    # Статистика игр
    game_results = GameResult.objects.filter(user=child).order_by('-date')[:10]
    
    # Количество сыгранных игр
    games_played = GameResult.objects.filter(user=child).count()
    
    # Последняя игра
    last_game = game_results.first()
    
    # Достижения (упрощённо)
    achievements = []
    if games_played >= 10:
        achievements.append('🏆 Сыграно 10 игр')
    if games_played >= 25:
        achievements.append('🏆 Сыграно 25 игр')
    
    # Уровни эмоций (для мотивации)
    emotion_levels = {}
    if game_results:
        for emotion in ['радость', 'счастье']:
            total = sum(getattr(r, emotion, 0) for r in game_results)
            emotion_levels[emotion] = min(total, 100)
    
    context = {
        'child': child,
        'game_results': game_results,
        'games_played': games_played,
        'last_game': last_game,
        'achievements': achievements,
        'emotion_levels': emotion_levels,
    }
    
    return render(request, 'game_dashboard.html', context)


def game_painting_view(request, user_id):
    """Игра 'Раскраска'"""
    session_user_id = request.session.get('user_id')
    if request.session.get('user_role') != 'child' or session_user_id is None or int(session_user_id) != int(user_id):
        return redirect('login')
    child = get_object_or_404(CUsers, id=user_id, role='child')
    
    if request.method == 'POST':
        session_id = request.POST.get('session_id')
        session = None
        if session_id:
            try:
                session = GameSession.objects.get(id=session_id, user=child)
                session.end_time = timezone.now()
                session.completed = True
                session.save()
            except GameSession.DoesNotExist:
                pass
        
        # Эмоции из скрытых полей (агрегат по всем 3 рисункам)
        anger = int(request.POST.get('anger', 0) or 0)
        joy = int(request.POST.get('joy', 0) or 0)
        sorrow = int(request.POST.get('sorrow', 0) or 0)
        love = int(request.POST.get('love', 0) or 0)
        boredom = int(request.POST.get('boredom', 0) or 0)
        happiness = int(request.POST.get('happiness', 0) or 0)
        
        drawing_data = {'color_counts': {}}
        raw_drawing = request.POST.get('drawing_data', '')
        drawing_base64 = ''
        if raw_drawing.strip().startswith('{'):
            try:
                parsed = json.loads(raw_drawing)
                drawing_data = parsed
                drawing_base64 = parsed.get('image_base64', '')
            except (json.JSONDecodeError, TypeError):
                drawing_base64 = raw_drawing
        else:
            drawing_base64 = raw_drawing
        if drawing_base64 and drawing_base64.startswith('data:image'):
            drawing_data['image_base64'] = drawing_base64
        
        result = GameResult(
            user=child,
            session=session,
            game_type='Painting',
            anger=anger,
            joy=joy,
            sorrow=sorrow,
            love=love,
            boredom=boredom,
            happiness=happiness,
            drawing_data=drawing_data,
        )
        result.save()
        
        # Сохраняем рисунок как файл для просмотра врачом
        if drawing_base64 and drawing_base64.startswith('data:image'):
            try:
                format_str, img_str = drawing_base64.split(';base64,')
                ext = 'png' if 'png' in format_str else 'jpeg'
                data = base64.b64decode(img_str)
                if len(data) > 100:  # не пустой рисунок
                    result.final_image.save(
                        f'drawing_{result.id}_{uuid.uuid4().hex[:8]}.{ext}',
                        ContentFile(data),
                        save=True
                    )
            except Exception:
                pass
        
        messages.success(request, 'Рисунок сохранён!')
        return redirect('game_dashboard', user_id=child.id)
    
    # Создаём игровую сессию
    session = GameSession.objects.create(
        user=child,
        game_type='Painting'
    )
    
    context = {
        'child': child,
        'session': session,
        'csrf_token': request.COOKIES.get('csrftoken'),
    }
    
    return render(request, 'game_painting.html', context)


def game_painting_save_view(request, user_id):
    """Сохранение результатов игры 'Раскраска'"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Метод не поддерживается'}, status=405)
    
    child = get_object_or_404(CUsers, id=user_id, role='child')
    
    try:
        data = json.loads(request.body)
        
        # Получаем или создаём сессию
        session_id = data.get('session_id')
        if session_id:
            session = get_object_or_404(GameSession, id=session_id, user=child)
            session.end_time = timezone.now()
            session.completed = True
            session.save()
        else:
            session = None
        
        # Анализ цветов (из вашей логики)
        colors = data.get('colors', [])
        color_analysis = {
            'красная': 0,
            'оранжевая': 0,
            'жёлтая': 0,
            'зелёная': 0,
            'синяя': 0,
            'фиолетовая': 0,
        }
        
        for color in colors:
            if color in color_analysis:
                color_analysis[color] += 1
        
        # Расчёт эмоций
        result = GameResult(
            user=child,
            session=session,
            game_type='Painting',
            anger=color_analysis.get('красная', 0) + color_analysis.get('оранжевая', 0),
            joy=color_analysis.get('жёлтая', 0),
            happiness=color_analysis.get('зелёная', 0),
            sorrow=color_analysis.get('синяя', 0),
            love=color_analysis.get('фиолетовая', 0),
            drawing_data={
                'colors': colors,
                'color_counts': color_analysis,
                'timestamp': timezone.now().isoformat()
            }
        )
        
        # Добавляем поведенческие данные
        if data.get('reaction_times'):
            result.reaction_times = data.get('reaction_times')
            result.reaction_time = sum(data['reaction_times']) / len(data['reaction_times'])
        
        result.save()
        
        # Добавляем действия в сессию
        if session and data.get('actions'):
            for action in data['actions']:
                session.add_action(action['type'], action['data'])
        
        return JsonResponse({
            'success': True,
            'result_id': result.id,
            'message': 'Результаты сохранены'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


def game_choice_view(request, user_id):
    """Игра 'Выбор'"""
    # Проверка: доступ только для ребёнка, играющего под своим аккаунтом
    session_user_id = request.session.get('user_id')
    session_user_role = request.session.get('user_role')
    if session_user_role != 'child' or session_user_id is None or int(session_user_id) != int(user_id):
        return redirect('login')
    
    child = get_object_or_404(CUsers, id=user_id, role='child')
    
    if request.method == 'POST':
        session_id = request.POST.get('session_id')
        session = None
        if session_id:
            try:
                session = GameSession.objects.get(id=session_id, user=child)
                session.end_time = timezone.now()
                session.completed = True
                session.save()
            except GameSession.DoesNotExist:
                pass
        
        choices_raw = request.POST.get('choices_json')
        if choices_raw:
            try:
                choices = json.loads(choices_raw)
            except (json.JSONDecodeError, TypeError):
                choices = {f'round_{i}': request.POST.get(f'round_{i}', '') for i in range(1, 6)}
        else:
            choices = {
                'round_1': request.POST.get('round_1', ''),
                'round_2': request.POST.get('round_2', ''),
                'round_3': request.POST.get('round_3', ''),
                'round_4': request.POST.get('round_4', ''),
                'round_5': request.POST.get('round_5', ''),
            }
        emotion_counts = {'joy': 0, 'sorrow': 0, 'love': 0, 'anger': 0, 'boredom': 0, 'happiness': 0}
        for k, v in choices.items():
            val = v.get('value', v) if isinstance(v, dict) else v
            if val in emotion_counts:
                emotion_counts[val] += 1
        
        rt_raw = request.POST.get('reaction_times', '[]')
        try:
            reaction_times = json.loads(rt_raw) if isinstance(rt_raw, str) else rt_raw
        except (json.JSONDecodeError, TypeError):
            reaction_times = []
        
        result = GameResult(
            user=child,
            session=session,
            game_type='Choice',
            anger=emotion_counts.get('anger', 0),
            boredom=emotion_counts.get('boredom', 0),
            joy=emotion_counts.get('joy', 0),
            sorrow=emotion_counts.get('sorrow', 0),
            love=emotion_counts.get('love', 0),
            happiness=emotion_counts.get('happiness', 0),
            choices=choices,
            reaction_times=reaction_times,
            reaction_time=sum(reaction_times) / len(reaction_times) if reaction_times else None,
        )
        result.save()
        
        messages.success(request, 'Результаты сохранены!')
        return redirect('game_dashboard', user_id=child.id)
    
    # Создаём игровую сессию
    session = GameSession.objects.create(
        user=child,
        game_type='Choice'
    )
    
    # Изображения для раундов (из вашего кода)
    context = {
        'child': child,
        'session': session,
        'round_1_images': ['anger_1.jpg', 'anger_2.jpg', 'anger_3.jpg', 'anger_4.png', 'anger_5.png', 'anger_6.png'],
        'round_2_images': ['boredom_1.jpg', 'boredom_2.jpg', 'boredom_3.jpg', 'boredom_4.png', 'boredom_5.jpg', 'boredom_6.jpg'],
        'round_3_images': ['joy_1.jpg', 'joy_2.jpg', 'joy_3.jpg', 'joy_4.jpg', 'joy_5.jpg', 'joy_6.jpg'],
        'csrf_token': request.COOKIES.get('csrftoken'),
    }
    
    return render(request, 'game_choice.html', context)


def game_choice_save_view(request, user_id):
    """Сохранение результатов игры 'Выбор'"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Метод не поддерживается'}, status=405)
    
    child = get_object_or_404(CUsers, id=user_id, role='child')
    
    try:
        data = json.loads(request.body)
        
        # Получаем сессию
        session_id = data.get('session_id')
        if session_id:
            session = get_object_or_404(GameSession, id=session_id, user=child)
            session.end_time = timezone.now()
            session.completed = True
            session.save()
        else:
            session = None
        
        choices = data.get('choices', {})
        
        # Анализ выборов
        result = GameResult(
            user=child,
            session=session,
            game_type='Choice',
            anger=choices.get('round_1', 0),
            boredom=choices.get('round_2', 0),
            joy=choices.get('round_3', 0),
            choices=choices,
        )
        
        # Поведенческие данные
        if data.get('reaction_times'):
            result.reaction_times = data.get('reaction_times')
            result.reaction_time = sum(data['reaction_times']) / len(data['reaction_times'])
        
        if data.get('mistakes'):
            result.mistakes = data['mistakes']
        
        result.save()
        
        return JsonResponse({
            'success': True,
            'result_id': result.id,
            'message': 'Результаты сохранены'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


def game_dialog_view(request, user_id):
    """Игра 'Диалог'"""
    # Проверка: доступ только для ребёнка
    session_user_id = request.session.get('user_id')
    session_user_role = request.session.get('user_role')
    if session_user_role != 'child' or session_user_id is None or int(session_user_id) != int(user_id):
        return redirect('login')
    
    child = get_object_or_404(CUsers, id=user_id, role='child')
    
    if request.method == 'POST':
        session_id = request.POST.get('session_id')
        session_obj = None
        if session_id:
            try:
                session_obj = GameSession.objects.get(id=session_id, user=child)
                session_obj.end_time = timezone.now()
                session_obj.completed = True
                session_obj.save()
            except GameSession.DoesNotExist:
                pass
        
        # Собираем ответы (q1–q5 с эмоциями: joy, sorrow, love, anger, boredom, happiness)
        # Поддержка dialog_answers JSON (множественный выбор на этапе)
        dialog_raw = request.POST.get('dialog_answers')
        if dialog_raw:
            try:
                answers = json.loads(dialog_raw)
            except (json.JSONDecodeError, TypeError):
                answers = {f'q{i}': request.POST.get(f'q{i}', '') for i in range(1, 6)}
        else:
            answers = {f'q{i}': request.POST.get(f'q{i}', '') for i in range(1, 6)}
        emotion_counts = {'joy': 0, 'sorrow': 0, 'love': 0, 'anger': 0, 'boredom': 0, 'happiness': 0}
        for v in answers.values():
            vals = v if isinstance(v, list) else [v] if v else []
            for x in vals:
                if x in emotion_counts:
                    emotion_counts[x] += 1
        
        joy = emotion_counts.get('joy', 0)
        sorrow = emotion_counts.get('sorrow', 0)
        love = emotion_counts.get('love', 0)
        anger = emotion_counts.get('anger', 0)
        boredom = emotion_counts.get('boredom', 0)
        happiness = emotion_counts.get('happiness', 0)
        
        # Время реакции
        rt_raw = request.POST.get('reaction_times', '[]')
        try:
            reaction_times = json.loads(rt_raw) if isinstance(rt_raw, str) else rt_raw
        except (json.JSONDecodeError, TypeError):
            reaction_times = []
        
        result = GameResult(
            user=child,
            session=session_obj,
            game_type='Dialog',
            joy=joy,
            sorrow=sorrow,
            love=love,
            anger=anger,
            boredom=boredom,
            happiness=happiness,
            dialog_answers=answers,
            reaction_times=reaction_times,
            reaction_time=sum(reaction_times) / len(reaction_times) if reaction_times else None,
        )
        result.save()
        
        messages.success(request, 'Результаты сохранены!')
        return redirect('game_dashboard', user_id=child.id)
    
    # Создаём игровую сессию
    session = GameSession.objects.create(
        user=child,
        game_type='Dialog'
    )
    
    context = {
        'child': child,
        'session': session,
        'csrf_token': request.COOKIES.get('csrftoken'),
    }
    
    return render(request, 'game_dialog.html', context)


def game_dialog_save_view(request, user_id):
    """Сохранение результатов игры 'Диалог'"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Метод не поддерживается'}, status=405)
    
    child = get_object_or_404(CUsers, id=user_id, role='child')
    
    try:
        data = json.loads(request.body)
        
        # Получаем сессию
        session_id = data.get('session_id')
        if session_id:
            session = get_object_or_404(GameSession, id=session_id, user=child)
            session.end_time = timezone.now()
            session.completed = True
            session.save()
        else:
            session = None
        
        answers = data.get('answers', {})
        
        # Расчёт эмоций (из вашей логики)
        joy = int(answers.get('question_1', 0)) + int(answers.get('question_3', 0)) + int(answers.get('question_5', 0))
        sorrow = int(answers.get('question_2', 0)) + int(answers.get('question_4', 0)) + int(answers.get('question_6', 0))
        love = int(answers.get('question_4a', 0))
        anger = int(answers.get('question_2b', 0))
        boredom = int(answers.get('question_3c', 0))
        happiness = int(answers.get('question_5a', 0))
        
        result = GameResult(
            user=child,
            session=session,
            game_type='Dialog',
            joy=joy,
            sorrow=sorrow,
            love=love,
            anger=anger,
            boredom=boredom,
            happiness=happiness,
            dialog_answers=answers,
        )
        
        # Поведенческие данные
        if data.get('reaction_times'):
            result.reaction_times = data.get('reaction_times')
            result.reaction_time = sum(data['reaction_times']) / len(data['reaction_times'])
        
        if data.get('mistakes'):
            result.mistakes = data['mistakes']
        
        result.save()
        
        return JsonResponse({
            'success': True,
            'result_id': result.id,
            'message': 'Результаты сохранены'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


def game_memory_view(request, user_id):
    """Игра 'Память' — найди пары"""
    session_user_id = request.session.get('user_id')
    if request.session.get('user_role') != 'child' or session_user_id is None or int(session_user_id) != int(user_id):
        return redirect('login')
    child = get_object_or_404(CUsers, id=user_id, role='child')
    if request.method == 'POST':
        session_id = request.POST.get('session_id')
        session = None
        if session_id:
            try:
                session = GameSession.objects.get(id=session_id, user=child)
                session.end_time = timezone.now()
                session.completed = True
                session.save()
            except GameSession.DoesNotExist:
                pass
        result = GameResult(
            user=child, session=session, game_type='Memory',
            performance_metrics={
                'pairs_found': int(request.POST.get('pairs_found', 0)),
                'attempts': int(request.POST.get('attempts', 0)),
                'time_seconds': int(request.POST.get('time_seconds', 0)),
                'levels_completed': int(request.POST.get('levels_completed', 0)),
            }
        )
        result.save()
        messages.success(request, 'Результат сохранён!')
        return redirect('game_dashboard', user_id=child.id)
    session = GameSession.objects.create(user=child, game_type='Memory')
    return render(request, 'game_memory.html', {'child': child, 'session': session})


def game_puzzle_view(request, user_id):
    """Игра 'Головоломка' — собери по порядку"""
    session_user_id = request.session.get('user_id')
    if request.session.get('user_role') != 'child' or session_user_id is None or int(session_user_id) != int(user_id):
        return redirect('login')
    child = get_object_or_404(CUsers, id=user_id, role='child')
    if request.method == 'POST':
        session_id = request.POST.get('session_id')
        session = None
        if session_id:
            try:
                session = GameSession.objects.get(id=session_id, user=child)
                session.end_time = timezone.now()
                session.completed = True
                session.save()
            except GameSession.DoesNotExist:
                pass
        result = GameResult(
            user=child, session=session, game_type='Puzzle',
            performance_metrics={
                'moves': int(request.POST.get('moves', 0)),
                'completed': int(request.POST.get('completed', 0)),
            }
        )
        result.save()
        messages.success(request, 'Результат сохранён!')
        return redirect('game_dashboard', user_id=child.id)
    session = GameSession.objects.create(user=child, game_type='Puzzle')
    return render(request, 'game_puzzle.html', {'child': child, 'session': session})


def game_sequence_view(request, user_id):
    """Игра 'Последовательность' — повтори паттерн"""
    session_user_id = request.session.get('user_id')
    if request.session.get('user_role') != 'child' or session_user_id is None or int(session_user_id) != int(user_id):
        return redirect('login')
    child = get_object_or_404(CUsers, id=user_id, role='child')
    if request.method == 'POST':
        session_id = request.POST.get('session_id')
        session = None
        if session_id:
            try:
                session = GameSession.objects.get(id=session_id, user=child)
                session.end_time = timezone.now()
                session.completed = True
                session.save()
            except GameSession.DoesNotExist:
                pass
        result = GameResult(
            user=child, session=session, game_type='Sequence',
            mistakes=int(request.POST.get('mistakes', 0)),
            performance_metrics={
                'level_reached': int(request.POST.get('level_reached', 1)),
            }
        )
        result.save()
        messages.success(request, 'Результат сохранён!')
        return redirect('game_dashboard', user_id=child.id)
    session = GameSession.objects.create(user=child, game_type='Sequence')
    return render(request, 'game_sequence.html', {'child': child, 'session': session})


# ==================== 6 НОВЫХ ИГР (ЭМОЦИИ + КОГНИЦИЯ) ====================

def _child_game_check(request, user_id):
    """Проверка доступа ребёнка к игре. Возвращает child или None."""
    if request.session.get('user_role') != 'child' or not request.session.get('user_id'):
        return None
    if int(request.session.get('user_id')) != int(user_id):
        return None
    return get_object_or_404(CUsers, id=user_id, role='child')


def game_emotion_face_view(request, user_id):
    """Узнай эмоцию — распознавание эмоций по лицу (эмодзи)"""
    child = _child_game_check(request, user_id)
    if not child:
        return redirect('login')
    if request.method == 'POST':
        session_id = request.POST.get('session_id')
        session = None
        if session_id:
            try:
                session = GameSession.objects.get(id=session_id, user=child)
            except (GameSession.DoesNotExist, ValueError):
                pass
        if session:
            session.end_time = timezone.now()
            session.completed = True
            session.save()
        data = json.loads(request.POST.get('data', '{}'))
        correct = data.get('correct', 0)
        total = data.get('total', 8)
        reaction_times = data.get('reaction_times', [])
        result = GameResult(
            user=child, session=session, game_type='EmotionFace',
            performance_metrics={'correct': correct, 'total': total, 'accuracy': correct / total if total else 0},
            reaction_times=reaction_times,
            reaction_time=sum(reaction_times) / len(reaction_times) if reaction_times else None,
            mistakes=total - correct,
            accuracy=correct / total if total else 0,
        )
        result.save()
        messages.success(request, 'Результат сохранён!')
        return redirect('game_dashboard', user_id=child.id)
    session = GameSession.objects.create(user=child, game_type='EmotionFace')
    return render(request, 'game_emotion_face.html', {'child': child, 'session': session})


def game_attention_view(request, user_id):
    """Внимание — нажми когда увидишь цель (устойчивое внимание)"""
    child = _child_game_check(request, user_id)
    if not child:
        return redirect('login')
    if request.method == 'POST':
        session_id = request.POST.get('session_id')
        session = None
        if session_id:
            try:
                session = GameSession.objects.get(id=session_id, user=child)
            except (GameSession.DoesNotExist, ValueError):
                pass
        if session:
            session.end_time = timezone.now()
            session.completed = True
            session.save()
        data = json.loads(request.POST.get('data', '{}'))
        hits = data.get('hits', 0)
        misses = data.get('misses', 0)
        false_alarms = data.get('false_alarms', 0)
        reaction_times = data.get('reaction_times', [])
        result = GameResult(
            user=child, session=session, game_type='Attention',
            performance_metrics={'hits': hits, 'misses': misses, 'false_alarms': false_alarms},
            reaction_times=reaction_times,
            reaction_time=sum(reaction_times) / len(reaction_times) if reaction_times else None,
            mistakes=misses + false_alarms,
        )
        result.save()
        messages.success(request, 'Результат сохранён!')
        return redirect('game_dashboard', user_id=child.id)
    session = GameSession.objects.create(user=child, game_type='Attention')
    return render(request, 'game_attention.html', {'child': child, 'session': session})


def game_gonogo_view(request, user_id):
    """Стоп-игра — Go/No-Go (торможение, импульсивность)"""
    child = _child_game_check(request, user_id)
    if not child:
        return redirect('login')
    if request.method == 'POST':
        session_id = request.POST.get('session_id')
        session = None
        if session_id:
            try:
                session = GameSession.objects.get(id=session_id, user=child)
            except (GameSession.DoesNotExist, ValueError):
                pass
        if session:
            session.end_time = timezone.now()
            session.completed = True
            session.save()
        data = json.loads(request.POST.get('data', '{}'))
        correct_go = data.get('correct_go', 0)
        correct_nogo = data.get('correct_nogo', 0)
        commission_errors = data.get('commission_errors', 0)  # нажал на No-Go
        omission_errors = data.get('omission_errors', 0)  # не нажал на Go
        reaction_times = data.get('reaction_times', [])
        result = GameResult(
            user=child, session=session, game_type='GoNoGo',
            performance_metrics={
                'correct_go': correct_go, 'correct_nogo': correct_nogo,
                'commission_errors': commission_errors, 'omission_errors': omission_errors,
            },
            mistake_types={'inhibition': commission_errors, 'attention': omission_errors},
            reaction_times=reaction_times,
            reaction_time=sum(reaction_times) / len(reaction_times) if reaction_times else None,
            mistakes=commission_errors + omission_errors,
        )
        result.save()
        messages.success(request, 'Результат сохранён!')
        return redirect('game_dashboard', user_id=child.id)
    session = GameSession.objects.create(user=child, game_type='GoNoGo')
    return render(request, 'game_gonogo.html', {'child': child, 'session': session})


def game_sort_view(request, user_id):
    """Сортировка — категоризация (исполнительные функции)"""
    child = _child_game_check(request, user_id)
    if not child:
        return redirect('login')
    if request.method == 'POST':
        session_id = request.POST.get('session_id')
        session = None
        if session_id:
            try:
                session = GameSession.objects.get(id=session_id, user=child)
            except (GameSession.DoesNotExist, ValueError):
                pass
        if session:
            session.end_time = timezone.now()
            session.completed = True
            session.save()
        data = json.loads(request.POST.get('data', '{}'))
        correct = data.get('correct', 0)
        total = data.get('total', 8)
        reaction_times = data.get('reaction_times', [])
        result = GameResult(
            user=child, session=session, game_type='Sort',
            performance_metrics={'correct': correct, 'total': total},
            reaction_times=reaction_times,
            reaction_time=sum(reaction_times) / len(reaction_times) if reaction_times else None,
            mistakes=total - correct,
            accuracy=correct / total if total else 0,
        )
        result.save()
        messages.success(request, 'Результат сохранён!')
        return redirect('game_dashboard', user_id=child.id)
    session = GameSession.objects.create(user=child, game_type='Sort')
    return render(request, 'game_sort.html', {'child': child, 'session': session})


def game_pattern_view(request, user_id):
    """Паттерн — заверши последовательность (логическое мышление)"""
    child = _child_game_check(request, user_id)
    if not child:
        return redirect('login')
    if request.method == 'POST':
        session_id = request.POST.get('session_id')
        session = None
        if session_id:
            try:
                session = GameSession.objects.get(id=session_id, user=child)
            except (GameSession.DoesNotExist, ValueError):
                pass
        if session:
            session.end_time = timezone.now()
            session.completed = True
            session.save()
        data = json.loads(request.POST.get('data', '{}'))
        correct = data.get('correct', 0)
        total = data.get('total', 6)
        reaction_times = data.get('reaction_times', [])
        result = GameResult(
            user=child, session=session, game_type='Pattern',
            performance_metrics={'correct': correct, 'total': total},
            reaction_times=reaction_times,
            reaction_time=sum(reaction_times) / len(reaction_times) if reaction_times else None,
            mistakes=total - correct,
            accuracy=correct / total if total else 0,
        )
        result.save()
        messages.success(request, 'Результат сохранён!')
        return redirect('game_dashboard', user_id=child.id)
    session = GameSession.objects.create(user=child, game_type='Pattern')
    return render(request, 'game_pattern.html', {'child': child, 'session': session})


def game_emotion_match_view(request, user_id):
    """Эмоция и ситуация — сопоставление (эмоциональный интеллект)"""
    child = _child_game_check(request, user_id)
    if not child:
        return redirect('login')
    if request.method == 'POST':
        session_id = request.POST.get('session_id')
        session = None
        if session_id:
            try:
                session = GameSession.objects.get(id=session_id, user=child)
            except (GameSession.DoesNotExist, ValueError):
                pass
        if session:
            session.end_time = timezone.now()
            session.completed = True
            session.save()
        data = json.loads(request.POST.get('data', '{}'))
        correct = data.get('correct', 0)
        total = data.get('total', 6)
        choices = data.get('choices', {})
        emotion_counts = {'joy': 0, 'sorrow': 0, 'love': 0, 'anger': 0, 'boredom': 0, 'happiness': 0}
        for k, v in choices.items():
            val = v.get('value', v) if isinstance(v, dict) else v
            if val in emotion_counts:
                emotion_counts[val] += 1
        reaction_times = data.get('reaction_times', [])
        result = GameResult(
            user=child, session=session, game_type='EmotionMatch',
            performance_metrics={'correct': correct, 'total': total},
            choices=choices,
            joy=emotion_counts.get('joy', 0),
            sorrow=emotion_counts.get('sorrow', 0),
            love=emotion_counts.get('love', 0),
            anger=emotion_counts.get('anger', 0),
            boredom=emotion_counts.get('boredom', 0),
            happiness=emotion_counts.get('happiness', 0),
            reaction_times=reaction_times,
            reaction_time=sum(reaction_times) / len(reaction_times) if reaction_times else None,
            mistakes=total - correct,
            accuracy=correct / total if total else 0,
        )
        result.save()
        messages.success(request, 'Результат сохранён!')
        return redirect('game_dashboard', user_id=child.id)
    session = GameSession.objects.create(user=child, game_type='EmotionMatch')
    return render(request, 'game_emotion_match.html', {'child': child, 'session': session})


# ==================== ПРЕДСТАВЛЕНИЯ ДЛЯ ПРОФИЛЯ ====================

def profile_view(request):
    """Просмотр профиля пользователя"""
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')
    
    user = get_object_or_404(CUsers, id=user_id)
    
    # Дополнительная информация в зависимости от роли
    context = {'user': user}
    
    if user.role == 'doctor':
        try:
            context['license'] = user.license
        except DoctorLicense.DoesNotExist:
            context['license'] = None
    
    elif user.role == 'parent':
        context['children'] = user.children.all()
    
    elif user.role == 'child':
        context['game_results'] = GameResult.objects.filter(user=user)[:10]
        context['parents'] = user.parents.all()
    
    return render(request, 'profile.html', context)


def profile_edit_view(request):
    """Редактирование профиля"""
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')
    
    user = get_object_or_404(CUsers, id=user_id)
    form_class = ProfileSelfEditForm
    
    if request.method == 'POST':
        form = form_class(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Профиль обновлён')
            return redirect('profile')
    else:
        form = form_class(instance=user)
    
    context = {
        'form': form,
        'user': user,
    }
    
    return render(request, 'profile_edit.html', context)


def change_password_view(request):
    """Смена пароля"""
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')
    
    user = get_object_or_404(CUsers, id=user_id)
    
    if request.method == 'POST':
        form = PasswordChangeForm(request.POST, user=user)
        if form.is_valid():
            user.password = form.cleaned_data['new_password']
            user.save()
            messages.success(request, 'Пароль успешно изменён')
            return redirect('profile')
    else:
        form = PasswordChangeForm()
    
    context = {
        'form': form,
        'user': user,
    }
    
    return render(request, 'change_password.html', context)


# ==================== ВСПОМОГАТЕЛЬНЫЕ ПРЕДСТАВЛЕНИЯ ====================

def _get_redirect_url(request, default='admin_dashboard'):
    """Возвращает безопасный URL для редиректа (next или referer), иначе — дашборд."""
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return next_url
    ref = request.META.get('HTTP_REFERER')
    if ref and url_has_allowed_host_and_scheme(ref, allowed_hosts={request.get_host()}):
        return ref
    return reverse(default)


def edit_user_view(request, id):
    """Редактирование пользователя (для администратора)"""
    if request.session.get('user_role') != 'admin':
        return HttpResponseForbidden('Доступ запрещён')
    
    user = get_object_or_404(CUsers.objects.prefetch_related('parents', 'doctors'), pk=id)
    
    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, f'Пользователь {user.name} обновлён')
            return redirect(_get_redirect_url(request))
    else:
        form = UserEditForm(instance=user)
    
    context = {
        'form': form,
        'user': user,
    }
    
    return render(request, 'edit_user.html', context)


def edit_parent_view(request, id):
    """Редактирование родителя и его детей"""
    if request.session.get('user_role') != 'admin':
        return HttpResponseForbidden('Доступ запрещён')
    
    user = get_object_or_404(CUsers, pk=id, role='parent')
    assigned_children = user.children.all().order_by('name')
    available_children = CUsers.objects.filter(role='child').exclude(parents=user).order_by('name')
    
    if request.method == 'POST':
        # Отвязка ребёнка
        if request.POST.get('remove_child'):
            child_id = request.POST.get('remove_child')
            child = get_object_or_404(CUsers, id=child_id, role='child')
            user.children.remove(child)
            messages.success(request, f'Ребёнок {child.name} отвязан')
            return redirect('edit_parent', id=id)
        
        # Привязка ребёнка (обрабатываем отдельно, до валидации формы)
        if request.POST.get('add_child') and request.POST.get('child_id'):
            child_id = request.POST.get('child_id')
            child = get_object_or_404(CUsers, id=child_id, role='child')
            if not user.children.filter(id=child.id).exists():
                user.children.add(child)
                messages.success(request, f'Ребёнок {child.name} добавлен')
            return redirect('edit_parent', id=id)
        
        form = UserEditForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Данные сохранены')
            return redirect(_get_redirect_url(request))
    else:
        form = UserEditForm(instance=user)
    
    context = {
        'form': form,
        'user': user,
        'children': available_children,
        'assigned_children': assigned_children,
    }
    
    return render(request, 'edit_parent.html', context)


def edit_doctor_view(request, id):
    """Редактирование врача и привязка пациентов"""
    if request.session.get('user_role') != 'admin':
        return HttpResponseForbidden('Доступ запрещён')
    
    user = get_object_or_404(CUsers, pk=id, role='doctor')
    assigned_patients = user.patients.all().order_by('name')
    available_patients = CUsers.objects.filter(role='child').exclude(doctors=user).order_by('name')
    
    if request.method == 'POST':
        # Добавление пациента
        if request.POST.get('assign_patient'):
            patient_id = request.POST.get('patient_id')
            if patient_id:
                child = get_object_or_404(CUsers, id=patient_id, role='child')
                if not user.patients.filter(id=child.id).exists():
                    user.patients.add(child)
                    messages.success(request, f'Пациент {child.name} добавлен')
            return redirect('edit_doctor', id=id)
        # Удаление пациента
        if request.POST.get('remove_patient'):
            patient_id = request.POST.get('remove_patient')
            child = get_object_or_404(CUsers, id=patient_id, role='child')
            user.patients.remove(child)
            messages.success(request, f'Пациент {child.name} отвязан')
            return redirect('edit_doctor', id=id)
        
        form = UserEditForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, f'Врач {user.name} обновлён')
            return redirect(_get_redirect_url(request))
    else:
        form = UserEditForm(instance=user)
    
    context = {
        'form': form,
        'user': user,
        'doctor': user,
        'assigned_patients': assigned_patients,
        'available_patients': available_patients,
    }
    
    return render(request, 'edit_doctor.html', context)


def generate_connection_code_view(request):
    """Генерация нового кода подключения"""
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'error': 'Не авторизован'}, status=401)
    
    user = get_object_or_404(CUsers, id=user_id)
    
    if user.role not in ['child', 'doctor']:
        return JsonResponse({'error': 'Эта роль не может генерировать код'}, status=400)
    
    user.generate_connection_code()
    user.save()
    
    return JsonResponse({
        'success': True,
        'code': user.connection_code,
        'expires': user.code_expires.isoformat()
    })


def api_get_game_statistics(request, child_id):
    """API для получения статистики игр (для графиков)"""
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'error': 'Не авторизован'}, status=401)
    
    child = get_object_or_404(CUsers, id=child_id, role='child')
    
    # Проверка прав
    current_user = CUsers.objects.get(id=user_id)
    if current_user.role == 'parent' and not current_user.children.filter(id=child.id).exists():
        return JsonResponse({'error': 'Нет доступа'}, status=403)
    
    game_results = GameResult.objects.filter(user=child).order_by('date')
    
    data = {
        'dates': [r.date.strftime('%d.%m.%Y') for r in game_results],
        'joy': [r.joy for r in game_results],
        'sorrow': [r.sorrow for r in game_results],
        'anger': [r.anger for r in game_results],
        'love': [r.love for r in game_results],
        'boredom': [r.boredom for r in game_results],
        'happiness': [r.happiness for r in game_results],
    }
    
    return JsonResponse(data)


def init_fuzzy_system_view(request):
    """Инициализация системы нечёткой логики (только для администратора)"""
    if request.session.get('user_role') != 'admin':
        return HttpResponseForbidden('Доступ запрещён')
    
    try:
        init_fuzzy_variables()
        messages.success(request, 'Система нечёткой логики успешно инициализирована')
    except Exception as e:
        messages.error(request, f'Ошибка инициализации: {str(e)}')
    
    return redirect('admin_dashboard')


def export_patient_data_view(request, patient_id):
    """Экспорт данных пациента в JSON"""
    if request.session.get('user_role') not in ['admin', 'doctor']:
        return HttpResponseForbidden('Доступ запрещён')
    
    patient = get_object_or_404(CUsers, id=patient_id, role='child')
    
    data = {
        'patient': {
            'id': patient.id,
            'name': patient.name,
            'username': patient.username,
            'date_of_b': patient.date_of_b.isoformat(),
        },
        'game_results': list(GameResult.objects.filter(user=patient).values()),
        'prescriptions': list(Prescription.objects.filter(child=patient).values()),
        'profiles': list(DiagnosticProfile.objects.filter(child=patient).values()),
    }
    
    response = JsonResponse(data, json_dumps_params={'indent': 2, 'ensure_ascii': False})
    response['Content-Disposition'] = f'attachment; filename="patient_{patient.id}_data.json"'
    
    return response


def feedback_view(request):
    """Обратная связь"""
    if request.method == 'POST':
        form = FeedbackForm(request.POST)
        if form.is_valid():
            # Здесь можно отправить email или сохранить в БД
            messages.success(request, 'Спасибо за обратную связь! Мы ответим вам в ближайшее время.')
            return redirect('home')
    else:
        form = FeedbackForm()
    
    return render(request, 'feedback.html', {'form': form})
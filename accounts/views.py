from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Avg, Count
from django.contrib.auth import logout
import json
import os
from datetime import datetime, timedelta
from collections import defaultdict

from .forms import (
    LoginForm, UserCreateForm, PrescriptionForm, DoctorRegistrationForm,
    ParentRegistrationForm, ChildRegistrationForm, ConnectionCodeForm,
    DoctorVerificationForm, UserEditForm, ChildAssignForm, DateRangeFilterForm,
    SubscriptionForm, FeedbackForm, PasswordChangeForm, BulkChildAssignForm
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
    
    return render(request, 'register_doctor.html', {'form': form})


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
    
    return render(request, 'register_parent.html', {'form': form})


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
    
    return render(request, 'register_child.html', {'form': form})


# ==================== ПРЕДСТАВЛЕНИЯ ДЛЯ АДМИНИСТРАТОРА ====================

def admin_dashboard_view(request):
    """Панель администратора"""
    # Проверка прав доступа
    if request.session.get('user_role') != 'admin':
        return HttpResponseForbidden('Доступ запрещён')
    
    # Фильтрация по роли
    role_filter = request.GET.get('role')
    if role_filter:
        users = CUsers.objects.filter(role=role_filter).order_by('name')
    else:
        users = CUsers.objects.all().order_by('role', 'name')
    
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
    }
    
    return render(request, 'admin_dashboard.html', context)


def admin_verify_licenses_view(request):
    """Просмотр и проверка лицензий врачей"""
    if request.session.get('user_role') != 'admin':
        return HttpResponseForbidden('Доступ запрещён')
    
    licenses = DoctorLicense.objects.all().select_related('user').order_by('-created_at')
    
    # Фильтры
    status = request.GET.get('status')
    if status == 'pending':
        licenses = licenses.filter(is_verified=False)
    elif status == 'verified':
        licenses = licenses.filter(is_verified=True)
    
    context = {
        'licenses': licenses,
    }
    
    return render(request, 'admin_verify_licenses.html', context)


def admin_verify_license_detail_view(request, license_id):
    """Детальный просмотр и проверка лицензии"""
    if request.session.get('user_role') != 'admin':
        return HttpResponseForbidden('Доступ запрещён')
    
    license = get_object_or_404(DoctorLicense, id=license_id)
    admin_id = request.session.get('user_id')
    admin = CUsers.objects.get(id=admin_id)
    
    if request.method == 'POST':
        form = DoctorVerificationForm(request.POST, instance=license, admin=admin)
        if form.is_valid():
            form.save()
            
            if license.is_verified:
                messages.success(request, f'Лицензия {license.license_number} подтверждена')
            else:
                messages.info(request, f'Лицензия {license.license_number} отклонена: {license.rejection_reason}')
            
            return redirect('admin_verify_licenses')
    else:
        form = DoctorVerificationForm(instance=license)
    
    context = {
        'license': license,
        'form': form,
    }
    
    return render(request, 'admin_verify_license_detail.html', context)


def admin_bulk_assign_view(request):
    """Массовое назначение детей родителям"""
    if request.session.get('user_role') != 'admin':
        return HttpResponseForbidden('Доступ запрещён')
    
    if request.method == 'POST':
        form = BulkChildAssignForm(request.POST)
        if form.is_valid():
            parent = form.cleaned_data['parent']
            children = form.cleaned_data['children']
            
            for child in children:
                parent.children.add(child)
            
            messages.success(request, f'{children.count()} детей успешно привязаны к родителю {parent.name}')
            return redirect('admin_dashboard')
    else:
        form = BulkChildAssignForm()
    
    context = {
        'form': form,
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
    daily_activity = GameResult.objects.filter(
        date__gte=thirty_days_ago
    ).extra({'date': "date(date)"}).values('date').annotate(count=Count('id')).order_by('date')
    
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

def doctor_dashboard_view(request):
    """Панель врача"""
    if request.session.get('user_role') != 'doctor':
        return HttpResponseForbidden('Доступ запрещён')
    
    doctor_id = request.session.get('user_id')
    doctor = CUsers.objects.get(id=doctor_id)
    
    # Проверка лицензии
    try:
        license = doctor.license
        if not license.is_verified:
            messages.warning(request, 'Ваша лицензия ещё не проверена администратором. Доступ ограничен.')
            return render(request, 'doctor_pending.html')
    except DoctorLicense.DoesNotExist:
        messages.warning(request, 'Пожалуйста, заполните информацию о лицензии в профиле.')
        return redirect('doctor_profile')
    
    # Получаем всех детей (пациентов)
    # Врач может видеть всех детей или только назначенных?
    # Пока сделаем всех детей
    patients = CUsers.objects.filter(role='child').order_by('name')
    
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
    
    # Получаем или создаём диагностический профиль с нечёткой логикой
    analyzer = FuzzyAnalyzer()
    
    # Проверяем, есть ли свежий профиль (не старше 7 дней)
    recent_profile = DiagnosticProfile.objects.filter(
        child=patient,
        date_created__gte=timezone.now() - timedelta(days=7)
    ).first()
    
    if recent_profile:
        profile = recent_profile
    else:
        # Создаём новый профиль
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
    
    context = {
        'doctor': doctor,
        'patient': patient,
        'game_results': game_results,
        'emotion_scores': emotion_scores,
        'prescriptions': prescriptions,
        'prescription_form': prescription_form,
        'filter_form': form,
        'profile': profile,
        'radar_data': json.dumps(radar_data),
        'behavior_analysis': behavior_analysis,
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
    
    # Получаем диагностический профиль
    profile = DiagnosticProfile.objects.filter(child=patient).first()
    
    if not profile:
        analyzer = FuzzyAnalyzer()
        profile = analyzer.create_diagnostic_profile(patient.id)
    
    # Получаем все результаты
    game_results = GameResult.objects.filter(user=patient).order_by('date')
    
    # Анализ по времени
    if len(game_results) >= 2:
        first_result = game_results.first()
        last_result = game_results.last()
        
        # Динамика эмоций
        emotion_dynamics = {}
        for emotion in EMOTIONS:
            first_val = getattr(first_result, emotion, 0)
            last_val = getattr(last_result, emotion, 0)
            emotion_dynamics[emotion] = {
                'first': first_val,
                'last': last_val,
                'change': last_val - first_val
            }
    else:
        emotion_dynamics = {}
    
    # Поведенческие траектории
    behavior_trajectories = []
    for result in game_results:
        if result.behavior_trajectory:
            behavior_trajectories.append({
                'date': result.date.isoformat(),
                'game_type': result.game_type,
                'trajectory': result.behavior_trajectory
            })
    
    context = {
        'patient': patient,
        'profile': profile,
        'game_results': game_results,
        'emotion_dynamics': emotion_dynamics,
        'behavior_trajectories': behavior_trajectories,
        'radar_data': json.dumps(profile.get_radar_data()),
    }
    
    return render(request, 'doctor_analysis.html', context)


# ==================== ПРЕДСТАВЛЕНИЯ ДЛЯ РОДИТЕЛЯ ====================

def parent_dashboard_view(request, user_id):
    """Панель родителя"""
    if request.session.get('user_role') != 'parent' or request.session.get('user_id') != user_id:
        return HttpResponseForbidden('Доступ запрещён')
    
    parent = get_object_or_404(CUsers, id=user_id, role='parent')
    children = parent.children.all()
    
    # Присоединение по коду
    if request.method == 'POST' and 'connect_code' in request.POST:
        code_form = ConnectionCodeForm(request.POST, user_role='parent')
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
        'code_form': code_form,
    }
    
    return render(request, 'parent_dashboard.html', context)


def child_detail_for_parent_view(request, child_id):
    """Детальная информация о ребёнке для родителя (упрощённая)"""
    parent_id = request.session.get('user_id')
    parent = get_object_or_404(CUsers, id=parent_id, role='parent')
    child = get_object_or_404(CUsers, id=child_id, role='child')
    
    # Проверяем, что это ребёнок данного родителя
    if not parent.children.filter(id=child.id).exists():
        return HttpResponseForbidden('Это не ваш ребёнок')
    
    game_results = GameResult.objects.filter(user=child).order_by('-date')[:20]
    
    # Упрощённые эмоциональные показатели
    emotion_scores = {
        'радость': sum(r.joy + r.happiness for r in game_results),
        'грусть': sum(r.sorrow for r in game_results),
        'гнев': sum(r.anger for r in game_results),
        'спокойствие': sum(r.love for r in game_results) - sum(r.boredom for r in game_results),
    }
    
    # Нормализация
    total = sum(emotion_scores.values()) or 1
    emotion_percentages = {k: int(v / total * 100) for k, v in emotion_scores.items()}
    
    # Получаем назначения врача
    prescriptions = Prescription.objects.filter(child=child, is_active=True).order_by('-date_created')
    
    # Получаем диагностический профиль (если есть)
    profile = DiagnosticProfile.objects.filter(child=child).first()
    
    context = {
        'parent': parent,
        'child': child,
        'game_results': game_results,
        'emotion_percentages': emotion_percentages,
        'prescriptions': prescriptions,
        'profile': profile,
    }
    
    return render(request, 'child_detail_parent.html', context)


# ==================== ПРЕДСТАВЛЕНИЯ ДЛЯ РЕБЁНКА ====================

def game_dashboard_view(request, user_id):
    """Панель ребёнка с выбором игр"""
    if request.session.get('user_role') != 'child' or request.session.get('user_id') != user_id:
        return HttpResponseForbidden('Доступ запрещён')
    
    child = get_object_or_404(CUsers, id=user_id, role='child')
    
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
    child = get_object_or_404(CUsers, id=user_id, role='child')
    
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
    child = get_object_or_404(CUsers, id=user_id, role='child')
    
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
    child = get_object_or_404(CUsers, id=user_id, role='child')
    
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
    
    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Профиль обновлён')
            return redirect('profile')
    else:
        form = UserEditForm(instance=user)
    
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

def edit_user_view(request, id):
    """Редактирование пользователя (для администратора)"""
    if request.session.get('user_role') != 'admin':
        return HttpResponseForbidden('Доступ запрещён')
    
    user = get_object_or_404(CUsers, pk=id)
    
    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, f'Пользователь {user.name} обновлён')
            return redirect('admin_dashboard')
    else:
        form = UserEditForm(instance=user)
    
    context = {
        'form': form,
        'edit_user': user,
    }
    
    return render(request, 'edit_user.html', context)


def edit_parent_view(request, id):
    """Редактирование родителя и его детей"""
    if request.session.get('user_role') != 'admin':
        return HttpResponseForbidden('Доступ запрещён')
    
    user = get_object_or_404(CUsers, pk=id, role='parent')
    assigned_children = user.children.filter(parents=user)
    available_children = CUsers.objects.filter(role='child').exclude(parents=user)
    
    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            
            # Привязка ребёнка
            child_id = request.POST.get('child_id')
            if child_id:
                child = get_object_or_404(CUsers, id=child_id, role='child')
                if not user.children.filter(id=child.id).exists():
                    user.children.add(child)
                    messages.success(request, f'Ребёнок {child.name} добавлен')
            
            return redirect('admin_dashboard')
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
    """Редактирование врача"""
    if request.session.get('user_role') != 'admin':
        return HttpResponseForbidden('Доступ запрещён')
    
    user = get_object_or_404(CUsers, pk=id, role='doctor')
    
    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, f'Врач {user.name} обновлён')
            return redirect('admin_dashboard')
    else:
        form = UserEditForm(instance=user)
    
    context = {
        'form': form,
        'user': user,
    }
    
    return render(request, 'edit_user.html', context)


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
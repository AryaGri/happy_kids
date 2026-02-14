"""
REST API для десктопного клиента.
Веб-приложение НЕ использует этот модуль — всё через views.py и сессии.
"""
import json
import secrets
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404

from .models import CUsers, GameResult, Prescription, GameSession, ApiToken


def _get_doctor_from_request(request):
    """Проверяет X-Auth-Token, возвращает врача или None."""
    token = request.headers.get('X-Auth-Token') or request.GET.get('token')
    if not token:
        return None, 'Токен не указан'
    try:
        api_token = ApiToken.objects.select_related('user').get(token=token)
        user = api_token.user
        if user.role != 'doctor':
            return None, 'Доступ только для врачей'
        return user, None
    except ApiToken.DoesNotExist:
        return None, 'Неверный токен'


def _safe_get_display(obj, field_name):
    """Безопасно получает display для choice-поля."""
    if not obj:
        return None
    val = getattr(obj, field_name, None)
    if not val:
        return None
    try:
        return getattr(obj, f'get_{field_name}_display')()
    except Exception:
        return str(val)


def _to_json_serializable(obj):
    """Конвертирует объект в JSON-сериализуемый вид (numpy -> float и т.д.)."""
    import numpy as np
    if isinstance(obj, (np.floating, np.integer)):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _to_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_json_serializable(x) for x in obj]
    if isinstance(obj, bool) and type(obj).__module__ == 'numpy':
        return bool(obj)
    return obj


@csrf_exempt
@require_http_methods(["POST"])
def api_login(request):
    """POST: username, password → {token, user_name} или {error}"""
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Неверный JSON'}, status=400)
    username = data.get('username', '').strip()
    password = data.get('password', '')
    if not username or not password:
        return JsonResponse({'error': 'Укажите логин и пароль'}, status=400)
    try:
        user = CUsers.objects.get(username=username)
        if not user.check_password(password):
            return JsonResponse({'error': 'Неверный логин или пароль'}, status=401)
        if user.role != 'doctor':
            return JsonResponse({'error': 'API доступен только для врачей'}, status=403)
        token = secrets.token_urlsafe(32)
        ApiToken.objects.create(user=user, token=token)
        return JsonResponse({
            'token': token,
            'user_id': user.id,
            'user_name': user.name,
        })
    except CUsers.DoesNotExist:
        return JsonResponse({'error': 'Неверный логин или пароль'}, status=401)


@require_http_methods(["GET"])
def api_doctor_patients(request):
    """GET + X-Auth-Token → список пациентов врача."""
    doctor, err = _get_doctor_from_request(request)
    if err:
        return JsonResponse({'error': err}, status=401)
    search = request.GET.get('search', '').strip()
    sort = request.GET.get('sort', 'name')
    patients = doctor.patients.all()
    if sort == 'name':
        patients = patients.order_by('name')
    elif sort == '-name':
        patients = patients.order_by('-name')
    elif sort == 'age':
        patients = patients.order_by('date_of_b')
    elif sort == '-age':
        patients = patients.order_by('-date_of_b')
    else:
        patients = patients.order_by('name')
    if search:
        from django.db.models import Q
        patients = patients.filter(Q(name__icontains=search) | Q(username__icontains=search))
    items = []
    for p in patients:
        items.append({
            'id': p.id,
            'name': p.name,
            'username': p.username,
            'date_of_b': p.date_of_b.strftime('%Y-%m-%d'),
        })
    return JsonResponse({'patients': items})


@csrf_exempt
@require_http_methods(["POST"])
def api_doctor_add_patient(request):
    """POST + X-Auth-Token + {code: "XXXX"} → добавить пациента по коду."""
    doctor, err = _get_doctor_from_request(request)
    if err:
        return JsonResponse({'error': err}, status=401)
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Неверный JSON'}, status=400)
    code = (data.get('code') or '').strip().upper()
    if not code:
        return JsonResponse({'error': 'Укажите код ребёнка'}, status=400)
    from django.utils import timezone
    try:
        child = CUsers.objects.get(connection_code=code, role='child')
    except CUsers.DoesNotExist:
        return JsonResponse({'error': 'Неверный код'}, status=400)
    if child.code_expires and child.code_expires < timezone.now():
        return JsonResponse({'error': 'Срок действия кода истёк'}, status=400)
    if doctor.patients.filter(id=child.id).exists():
        return JsonResponse({'error': 'Пациент уже добавлен', 'patient': {'id': child.id, 'name': child.name}}, status=200)
    doctor.patients.add(child)
    return JsonResponse({
        'success': True,
        'patient': {'id': child.id, 'name': child.name, 'username': child.username, 'date_of_b': child.date_of_b.strftime('%Y-%m-%d')},
    })


@require_http_methods(["GET"])
def api_doctor_patient_detail(request, patient_id):
    """GET + X-Auth-Token → полные данные пациента для десктопа."""
    doctor, err = _get_doctor_from_request(request)
    if err:
        return JsonResponse({'error': err}, status=401)
    patient = get_object_or_404(CUsers, id=patient_id, role='child')
    if not doctor.patients.filter(id=patient.id).exists():
        return JsonResponse({'error': 'Нет доступа к этому пациенту'}, status=403)

    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    game_type = request.GET.get('game_type')

    game_results = GameResult.objects.filter(user=patient)
    if date_from:
        game_results = game_results.filter(date__date__gte=date_from)
    if date_to:
        game_results = game_results.filter(date__date__lte=date_to)
    if game_type:
        game_results = game_results.filter(game_type=game_type)
    game_results = list(game_results.order_by('-date')[:100])

    emotion_scores = {
        'гнев': sum(r.anger for r in game_results),
        'скука': sum(r.boredom for r in game_results),
        'радость': sum(r.joy for r in game_results),
        'счастье': sum(r.happiness for r in game_results),
        'грусть': sum(r.sorrow for r in game_results),
        'любовь': sum(r.love for r in game_results),
    }
    emotion_labels = list(emotion_scores.keys())
    emotion_values = list(emotion_scores.values())

    prescriptions = list(Prescription.objects.filter(child=patient).select_related('doctor').order_by('-date_created')[:50])

    from .fuzzy_logic import FuzzyAnalyzer
    analyzer = FuzzyAnalyzer()
    profile = analyzer.create_diagnostic_profile(patient.id)
    radar_data = profile.get_radar_data()

    from .diagnostic_panel import (
        get_fuzzy_analysis_for_panel,
        get_heatmap_data,
        get_dynamics_data,
        get_adaptive_recommendations,
        build_auto_prescription_text,
        BASE_RECOMMENDATIONS,
    )

    panel_data = None
    heatmap_data = {}
    dynamics_data = None
    adaptive_recs = []
    auto_prescription = ''
    detected_diagnoses = []

    gr_list = list(game_results)
    if gr_list:
        try:
            panel_data = get_fuzzy_analysis_for_panel(analyzer, profile, gr_list, patient)
            adaptive_recs = get_adaptive_recommendations(
                panel_data['params_results'],
                panel_data['diagnostic_params']
            )
            heatmap_data = get_heatmap_data(gr_list, profile)
            dynamics_data = get_dynamics_data(gr_list)
            auto_prescription = build_auto_prescription_text(
                panel_data['params_results'], BASE_RECOMMENDATIONS, patient
            )
        except Exception:
            pass

    if profile and hasattr(profile, 'detected_diagnoses') and profile.detected_diagnoses:
        from .models import DiagnosticDiagnosis
        detected_diagnoses = list(
            DiagnosticDiagnosis.objects.filter(code__in=profile.detected_diagnoses).values(
                'code', 'name', 'default_recommendations'
            )
        )

    result = {
        'patient': {
            'id': patient.id,
            'name': patient.name,
            'username': patient.username,
            'date_of_b': patient.date_of_b.strftime('%Y-%m-%d'),
        },
        'profile': {
            'cognitive_style': getattr(profile, 'cognitive_style', None),
            'cognitive_style_display': _safe_get_display(profile, 'cognitive_style'),
            'recommendations': getattr(profile, 'recommendations', None) or '',
            'detected_diagnoses': detected_diagnoses,
        },
        'emotion_scores': emotion_scores,
        'emotion_chart_data': {'labels': emotion_labels, 'data': emotion_values},
        'radar_data': _to_json_serializable(radar_data),
        'prescriptions': [
            {
                'id': p.id,
                'text': p.text,
                'prescription_type': p.prescription_type,
                'prescription_type_display': _safe_get_display(p, 'prescription_type'),
                'date_created': p.date_created.strftime('%d.%m.%Y %H:%M'),
                'doctor_name': p.doctor.name if p.doctor else None,
                'medication_name': getattr(p, 'medication_name', '') or '',
                'dosage': getattr(p, 'dosage', '') or '',
                'duration': getattr(p, 'duration', '') or '',
            }
            for p in prescriptions
        ],
        'game_results_count': len(game_results),
        'game_results': [
            {
                'id': r.id,
                'game_type': r.game_type,
                'game_type_display': r.get_game_type_display(),
                'date': r.date.strftime('%d.%m.%Y %H:%M'),
                'joy': r.joy, 'happiness': r.happiness, 'sorrow': r.sorrow,
                'anger': r.anger, 'love': r.love, 'boredom': r.boredom,
                'mistakes': r.mistakes or 0,
                'performance_metrics': r.performance_metrics or {},
                'dialog_answers': r.dialog_answers or {},
                'choices': r.choices or {},
                'final_image_url': request.build_absolute_uri(r.final_image.url) if getattr(r, 'final_image', None) and r.final_image else None,
                'drawing_data': r.drawing_data or {},
            }
            for r in game_results[:50]
        ],
        'panel_data': _to_json_serializable(panel_data) if panel_data else None,
        'heatmap_data': _to_json_serializable(heatmap_data) if isinstance(heatmap_data, dict) else {},
        'dynamics_data': _to_json_serializable(dynamics_data) if dynamics_data else None,
        'adaptive_recommendations': [
            {
                'name': r['name'],
                'brief': r['brief'],
                'parent_steps': r.get('parent_steps', []),
                'doctor_steps': r.get('doctor_steps', []),
            }
            for r in adaptive_recs
        ],
        'base_recommendations': BASE_RECOMMENDATIONS,
        'auto_prescription_text': auto_prescription,
    }
    return JsonResponse(result, json_dumps_params={'ensure_ascii': False})


@csrf_exempt
@require_http_methods(["POST"])
def api_doctor_create_prescription(request, patient_id):
    """POST + X-Auth-Token + {text, prescription_type, ...} → создать назначение."""
    doctor, err = _get_doctor_from_request(request)
    if err:
        return JsonResponse({'error': err}, status=401)
    patient = get_object_or_404(CUsers, id=patient_id, role='child')
    if not doctor.patients.filter(id=patient.id).exists():
        return JsonResponse({'error': 'Нет доступа к этому пациенту'}, status=403)
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Неверный JSON'}, status=400)
    text = (data.get('text') or '').strip()
    if not text:
        return JsonResponse({'error': 'Укажите текст назначения'}, status=400)
    ptype = data.get('prescription_type', 'recommendation')
    if ptype not in ['medication', 'therapy', 'exercise', 'recommendation']:
        ptype = 'recommendation'
    p = Prescription.objects.create(
        child=patient,
        doctor=doctor,
        text=text,
        prescription_type=ptype,
        medication_name=(data.get('medication_name') or '')[:200],
        dosage=(data.get('dosage') or '')[:100],
        duration=(data.get('duration') or '')[:100],
        is_active=data.get('is_active', True),
    )
    return JsonResponse({
        'success': True,
        'prescription': {
            'id': p.id,
            'text': p.text,
            'prescription_type': p.prescription_type,
            'prescription_type_display': _safe_get_display(p, 'prescription_type'),
            'date_created': p.date_created.strftime('%d.%m.%Y %H:%M'),
            'doctor_name': doctor.name,
        },
    })


@require_http_methods(["GET"])
def api_doctor_profile(request):
    """GET + X-Auth-Token → профиль текущего врача."""
    doctor, err = _get_doctor_from_request(request)
    if err:
        return JsonResponse({'error': err}, status=401)
    return JsonResponse({
        'id': doctor.id,
        'username': doctor.username,
        'name': doctor.name,
        'date_of_b': doctor.date_of_b.strftime('%Y-%m-%d'),
        'connection_code': doctor.connection_code or '',
    })


@csrf_exempt
@require_http_methods(["POST", "PUT", "PATCH"])
def api_doctor_profile_update(request):
    """POST/PUT/PATCH + X-Auth-Token + {name, ...} → обновить профиль врача."""
    doctor, err = _get_doctor_from_request(request)
    if err:
        return JsonResponse({'error': err}, status=401)
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Неверный JSON'}, status=400)
    if data.get('name'):
        doctor.name = (data['name'] or '').strip()[:150] or doctor.name
    doctor.save()
    return JsonResponse({
        'success': True,
        'profile': {
            'id': doctor.id,
            'username': doctor.username,
            'name': doctor.name,
            'date_of_b': doctor.date_of_b.strftime('%Y-%m-%d'),
        },
    })

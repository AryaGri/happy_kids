from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .forms import LoginForm, PrescriptionForm
from .models import CUsers, Game, GameResult, Prescription
from django.contrib.auth import logout
from .forms import UserCreateForm
from django.http import HttpResponseForbidden
import os
from django.conf import settings

def base_view(request):
    return render(request, 'main.html')

def admin_dashboard_view(request):
    role_filter = request.GET.get('role')   
    if role_filter:
        users = CUsers.objects.filter(role=role_filter).order_by('name')
    else:
        users = CUsers.objects.all().order_by('role', 'name')
    return render(request, 'admin_dashboard.html', {'users':users})

def edit_user_view(request, id):
    user = get_object_or_404(CUsers, pk=id)
    if request.method == 'POST':
        username = request.POST.get('username')
        name = request.POST.get('name')
        date_of_b = request.POST.get('date_of_b') 
        role = request.POST.get('role')
        from datetime import datetime
        date_of_b = datetime.strptime(date_of_b, '%Y-%m-%d').date()
        user.username = username
        user.name = name
        user.date_of_b = date_of_b
        user.role = role
        user.save()
    return render(request, 'edit_user.html', {'user': user})

def edit_parent_view(request, id):
    user = get_object_or_404(CUsers, pk=id)
    assigned_children = user.children.filter(parents=user)
    available_children = CUsers.objects.filter(role='child').exclude(parents=user)
    if request.method == 'POST':
        user.username = request.POST.get('username')
        user.name = request.POST.get('name')
        user.date_of_b = request.POST.get('date_of_b')
        user.password = request.POST.get('password')
        user.role = request.POST.get('role')
        user.save()
        child_id = request.POST.get('child_id')
        if child_id:
            child = get_object_or_404(CUsers, id=child_id, role='child')
            if not user.children.filter(id=child.id).exists():
                user.children.add(child)
        return redirect('admin_dashboard')
    return render(request, 'edit_parent.html', {
        'user': user,
        'children': available_children,
        'assigned_children': assigned_children,
    })

def edit_doctor_view(request, id):
    user = get_object_or_404(CUsers, pk=id)
    if request.method == 'POST':
        username = request.POST.get('username')
        name = request.POST.get('name')
        date_of_b = request.POST.get('date_of_b')
        role = request.POST.get('role')
        from datetime import datetime
        date_of_b = datetime.strptime(date_of_b, '%Y-%m-%d').date()
        user.username = username
        user.name = name
        user.date_of_b = date_of_b
        user.role = role
        user.save()
    return render(request, 'edit_user.html', {'user': user})

def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            try:
                user = CUsers.objects.get(username=username)
                if user.password == password:  
                    if user.role == 'admin':
                        return redirect('admin_dashboard')
                    elif user.role == 'doctor':
                        return redirect('doctor_dashboard')
                    elif user.role == 'parent':
                        return redirect(f'/parent_dashboard/{user.id}/')
                    elif user.role == 'child':
                        return redirect(f'/game_dashboard/{user.id}/')
                else:
                    messages.error(request, 'Неверный пароль!')
            except CUsers.DoesNotExist:
                messages.error(request, 'Пользователь не найден!')
    else:
        form = LoginForm()
    return render(request, 'login.html', {'form': form})

def logout_view(request):
    logout(request) 
    return redirect('home') 

def register_view(request, user_id=None):
    if request.method == 'POST':
        form = UserCreateForm(request.POST)
        if form.is_valid():
            new_user = form.save(commit=False)
            new_user.save()
            messages.success(request, 'Пользователь успешно создан!')
            return redirect('admin_dashboard')  
        else:
            messages.error(request, 'Ошибка при создании пользователя. Пожалуйста, проверьте форму.')
    else:
        form = UserCreateForm()
    return render(request, 'register.html', {'form': form})

def parent_dashboard_view(request, user_id):
    user = get_object_or_404(CUsers, pk=user_id)
    children = user.children.all()
    return render(request, 'parent_dashboard.html', {'children': children})

def doctor_dashboard_view(request):
    patients = CUsers.objects.filter(role='child')    
    return render(request, 'doctor_dashboard.html', {'patients': patients})

def game_dashboard_view(request, user_id):
    user = get_object_or_404(CUsers, pk=user_id)
    return render(request, 'game_dashboard.html', {'user': user})

def game_painting_view(request, user_id):
    user = get_object_or_404(CUsers, pk=user_id)
    return render(request, 'game_painting.html', {'user': user})

def game_choice_view(request, user_id):
    user = get_object_or_404(CUsers, id=user_id)
    return render(request, 'game_choice.html', {'user': user})

def game_dialog_view(request, user_id):
    user = get_object_or_404(CUsers, id=user_id)
    return render(request, 'game_dialog.html', {'user': user})
 
def game_results(request):
    return render(request, 'child_detail.html')

def game_painting(request, user_id):
    user = get_object_or_404(CUsers, id=user_id)
    if request.method == 'POST':
        color = request.POST.get('color', None)
        if color:
            result, created = GameResult.objects.get_or_create(user=user)
            if color == 'красная' or color == 'оранжевая':
                result.anger += 1
            elif color == 'жёлтая':
                result.joy += 1
            elif color == 'зелёная':
                result.happiness += 1
            elif color == 'синяя':
                result.sorrow += 1
            elif color == 'фиолетовая':
                result.love += 1
            result.save()
            return redirect('game_dashboard')
    return render(request, 'game_painting.html', {'user': user})

def game_choice(request, user_id):
    if request.method == 'POST':
        round_1_choice = request.POST.get('round_1')
        round_2_choice = request.POST.get('round_2')
        round_3_choice = request.POST.get('round_3')
        return redirect('game_dashboard', user_id=user_id)
    context = {
        'round_1_images': ['anger_1.jpg', 'anger_2.jpg', 'anger_3.jpg', 'anger_4.png', 'anger_5.png', 'anger_6.png'],
        'round_2_images': ['boredom_1.jpg', 'boredom_2.jpg', 'boredom_3.jpg', 'boredom_4.png', 'boredom_5.jpg', 'boredom_6.jpg'],
        'round_3_images': ['joy_1.jpg', 'joy_2.jpg', 'joy_3.jpg', 'joy_4.jpg', 'joy_5.jpg', 'joy_6.jpg'],
    }
    return render(request, 'game_choice.html', context)

def game_dialog(request, user_id):
    user = get_object_or_404(CUsers, id=user_id)
    if request.method == 'POST':
        joy = int(request.POST.get('question_1', 0)) + int(request.POST.get('question_3', 0)) + int(request.POST.get('question_5', 0))
        sorrow = int(request.POST.get('question_2', 0)) + int(request.POST.get('question_4', 0)) + int(request.POST.get('question_6', 0))
        love = int(request.POST.get('question_4a', 0))
        anger = int(request.POST.get('question_2b', 0))
        boredom = int(request.POST.get('question_3c', 0))
        happiness = int(request.POST.get('question_5a', 0))
        total_score = joy + sorrow + love + anger + boredom + happiness
        game = Game.objects.create(
            user=request.user,
            game_type="Dialog",
            joy=joy,
            sorrow=sorrow,
            love=love,
            anger=anger,
            boredom=boredom,
            happiness=happiness,
            total_score=total_score
        )
        return redirect('game_dashboard', {'user': user})
    return render(request, 'game_dialog.html', {'user': user})

def patient_detail(request, patient_id):
    patient = get_object_or_404(CUsers, id=patient_id)
    game_results = GameResult.objects.filter(user=patient)
    emotion_scores = {
        'радость': sum(result.joy for result in game_results),
        'грусть': sum(result.sorrow for result in game_results),
        'гнев': sum(result.anger for result in game_results),
        'любовь': sum(result.love for result in game_results),
        'скука': sum(result.boredom for result in game_results),
        'счастье': sum(result.happiness for result in game_results)
    }
    prescriptions = Prescription.objects.filter(child=patient)
    if request.method == 'POST':
        form = PrescriptionForm(request.POST)
        if form.is_valid():
            prescription = form.save(commit=False)
            prescription.child = patient
            prescription.save()
            return redirect('patient_detail', patient_id=patient.id)
    else:
        form = PrescriptionForm()
    return render(request, 'patient_detail.html', {
        'patient': patient,
        'prescriptions': prescriptions,
        'game_results': game_results,
        'emotion_scores': emotion_scores,
        'form': form,
    })

def child_detail(request, child_id):
    child = get_object_or_404(CUsers, id=child_id)
    prescriptions = Prescription.objects.filter(child=child)
    game_results = GameResult.objects.filter(user=child)
    emotion_scores = {
        'гнев': sum([result.anger for result in game_results]),
        'скука': sum([result.boredom for result in game_results]),
        'радость': sum([result.joy for result in game_results]),
        'счастье': sum([result.happiness for result in game_results]),
        'грусть': sum([result.sorrow for result in game_results]),
        'любовь': sum([result.love for result in game_results]),
    }
    return render(request, 'child_detail.html', {
        'child': child,
        'prescriptions': prescriptions,
        'game_results': game_results,
        'emotion_scores': emotion_scores
    })

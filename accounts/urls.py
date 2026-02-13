from django.urls import path
from . import views


urlpatterns = [
    path('', views.base_view, name='home'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    path('adm/dashboard/', views.admin_dashboard_view, name='admin_dashboard'),  # Панель администратора
    path('adm/dashboard/edit_user/<int:id>/', views.edit_user_view, name='edit_user'), # Редактирование пользователя

    path('doctor_dashboard/', views.doctor_dashboard_view, name='doctor_dashboard'),

    path('parent_dashboard/<int:user_id>/', views.parent_dashboard_view, name='parent_dashboard'),  # Панель родителя
    
    path('game_dashboard/<int:user_id>/game_painting', views.game_painting, name='painting_game'),  
    path('game_dashboard/<int:user_id>/game_dialog/', views.game_dialog, name='game_dialog'), 
    path('game_dashboard/<int:user_id>/game_choice/', views.game_choice, name='game_choice'),  
    path('game_dashboard/<int:user_id>/', views.game_dashboard_view, name='game_dashboard'),
    
    path('adm/dashboard/edit_parent/<int:id>/', views.edit_parent_view, name='edit_parent'), 
    path('adm/dashboard/edit_doc/<int:id>/', views.edit_doctor_view, name='edit_doctor'), 

    path('game/painting/<int:user_id>/', views.game_painting, name='game_painting'),
    path('game/choice/<int:user_id>/', views.game_choice, name='game_choice'),

    path('patient/<int:patient_id>/', views.patient_detail, name='patient_detail'),

    path('child/<int:child_id>/', views.child_detail, name='child_detail'),

]


from django.urls import path
from . import views


urlpatterns = [
    path('', views.base_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Регистрация
    path('register/', views.register_view, name='register'),
    path('register/choice/', views.register_view, name='register_choice'),
    path('register/doctor/', views.register_doctor_view, name='register_doctor'),
    path('register/parent/', views.register_parent_view, name='register_parent'),
    path('register/child/', views.register_child_view, name='register_child'),

    # Администратор
    path('adm/dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    path('adm/dashboard/edit_user/<int:id>/', views.edit_user_view, name='edit_user'),
    path('adm/dashboard/edit_parent/<int:id>/', views.edit_parent_view, name='edit_parent'),
    path('adm/dashboard/edit_doc/<int:id>/', views.edit_doctor_view, name='edit_doctor'),
    path('adm/verify-licenses/', views.admin_verify_licenses_view, name='admin_verify_licenses'),
    path('adm/verify-license/<int:license_id>/', views.admin_verify_license_detail_view, name='admin_verify_license'),
    path('adm/dashboard/delete_user/<int:id>/', views.admin_delete_user_view, name='admin_delete_user'),
    path('adm/bulk-assign/', views.admin_bulk_assign_view, name='admin_bulk_assign'),
    path('adm/statistics/', views.admin_statistics_view, name='admin_statistics'),
    path('adm/init-fuzzy/', views.init_fuzzy_system_view, name='admin_init_fuzzy'),

    # Врач
    path('doctor_dashboard/', views.doctor_dashboard_view, name='doctor_dashboard'),
    path('doctor/license/edit/', views.doctor_license_edit_view, name='doctor_license_edit'),
    path('doctor/patient/<int:patient_id>/analysis/', views.doctor_analysis_view, name='doctor_analysis'),
    path('doctor/patient/<int:patient_id>/session/<int:session_id>/', views.patient_game_session_view, name='doctor_patient_session'),
    path('doctor/export-patient/<int:patient_id>/', views.export_patient_data_view, name='doctor_export_patient'),
    path('patient/<int:patient_id>/', views.patient_detail_view, name='patient_detail'),

    # Родитель
    path('parent_dashboard/<int:user_id>/', views.parent_dashboard_view, name='parent_dashboard'),
    path('parent/<int:user_id>/child/<int:child_id>/', views.parent_child_detail_view, name='parent_child_detail'),
    path('child/<int:child_id>/', views.child_detail_for_parent_view, name='child_detail'),
    path('child/<int:child_id>/prescriptions/download/', views.parent_download_prescriptions_view, name='parent_download_prescriptions'),

    # Ребёнок / Игры
    path('game_dashboard/<int:user_id>/', views.game_dashboard_view, name='game_dashboard'),
    path('game_dashboard/<int:user_id>/game_painting', views.game_painting_view, name='painting_game'),
    path('game_dashboard/<int:user_id>/game_dialog/', views.game_dialog_view, name='game_dialog'),
    path('game_dashboard/<int:user_id>/game_choice/', views.game_choice_view, name='game_choice'),
    path('game_dashboard/<int:user_id>/game_memory/', views.game_memory_view, name='game_memory'),
    path('game_dashboard/<int:user_id>/game_puzzle/', views.game_puzzle_view, name='game_puzzle'),
    path('game_dashboard/<int:user_id>/game_sequence/', views.game_sequence_view, name='game_sequence'),
    path('game_dashboard/<int:user_id>/game_emotion_face/', views.game_emotion_face_view, name='game_emotion_face'),
    path('game_dashboard/<int:user_id>/game_attention/', views.game_attention_view, name='game_attention'),
    path('game_dashboard/<int:user_id>/game_gonogo/', views.game_gonogo_view, name='game_gonogo'),
    path('game_dashboard/<int:user_id>/game_sort/', views.game_sort_view, name='game_sort'),
    path('game_dashboard/<int:user_id>/game_pattern/', views.game_pattern_view, name='game_pattern'),
    path('game_dashboard/<int:user_id>/game_emotion_match/', views.game_emotion_match_view, name='game_emotion_match'),
    path('game/painting/<int:user_id>/', views.game_painting_view, name='game_painting'),

    # API для игр (POST)
    path('api/game/painting/<int:user_id>/save/', views.game_painting_save_view, name='api_game_painting_save'),
    path('api/game/choice/<int:user_id>/save/', views.game_choice_save_view, name='api_game_choice_save'),
    path('api/game/dialog/<int:user_id>/save/', views.game_dialog_save_view, name='api_game_dialog_save'),
    path('api/game/statistics/<int:child_id>/', views.api_get_game_statistics, name='api_game_statistics'),

    # Профиль
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.profile_edit_view, name='profile_edit'),
    path('change-password/', views.change_password_view, name='change_password'),
    path('generate-code/', views.generate_connection_code_view, name='generate_code'),

    # Прочее
    path('feedback/', views.feedback_view, name='feedback'),
]

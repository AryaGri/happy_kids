from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime, date
import re

from .models import CUsers, DoctorLicense, Prescription, GameResult, Subscription


class LoginForm(forms.Form):
    """Форма входа"""
    username = forms.CharField(
        label='Логин',
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Введите логин'})
    )
    password = forms.CharField(
        label='Пароль',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Введите пароль'})
    )


class UserCreateForm(forms.ModelForm):
    """Форма создания пользователя (из вашего кода с улучшениями)"""
    password_confirm = forms.CharField(
        label='Подтверждение пароля',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = CUsers
        fields = ['username', 'name', 'date_of_b', 'role', 'password']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'date_of_b': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'role': forms.Select(attrs={'class': 'form-control'}),
            'password': forms.PasswordInput(attrs={'class': 'form-control'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        
        if password and password_confirm and password != password_confirm:
            raise ValidationError('Пароли не совпадают')
        
        return cleaned_data
    
    def clean_username(self):
        username = self.cleaned_data['username']
        if CUsers.objects.filter(username=username).exists():
            raise ValidationError('Пользователь с таким логином уже существует')
        return username
    
    def clean_date_of_b(self):
        date_of_b = self.cleaned_data['date_of_b']
        if date_of_b > date.today():
            raise ValidationError('Дата рождения не может быть в будущем')
        return date_of_b


class DoctorRegistrationForm(UserCreateForm):
    """Форма регистрации врача с проверкой лицензии"""
    license_number = forms.CharField(
        label='Номер лицензии',
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    license_scan = forms.CharField(
        label='Текст лицензии',
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5})
    )
    license_file = forms.FileField(
        label='Файл лицензии',
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )
    
    class Meta(UserCreateForm.Meta):
        fields = ['username', 'name', 'date_of_b', 'password', 'license_number']
    
    def clean_license_number(self):
        license_number = self.cleaned_data['license_number'].strip().upper()
        if not re.match(r'^[A-Z0-9]{5,20}$', license_number):
            raise ValidationError('Неверный формат номера лицензии (латиница и цифры, 5–20 символов)')
        return license_number
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'doctor'
        
        if commit:
            user.save()
            # Создаём запись о лицензии
            license_obj = DoctorLicense(
                user=user,
                license_number=self.cleaned_data['license_number'],
                license_scan=self.cleaned_data.get('license_scan', ''),
                is_verified=False
            )
            if self.cleaned_data.get('license_file'):
                license_obj.license_file = self.cleaned_data['license_file']
            license_obj.save()
        return user


class ParentRegistrationForm(UserCreateForm):
    """Форма регистрации родителя"""
    
    class Meta(UserCreateForm.Meta):
        fields = ['username', 'name', 'date_of_b', 'password']
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'parent'
        if commit:
            user.save()
        return user


class ChildRegistrationForm(UserCreateForm):
    """Форма регистрации ребёнка"""
    
    class Meta(UserCreateForm.Meta):
        fields = ['username', 'name', 'date_of_b', 'password']
    
    def clean_date_of_b(self):
        date_of_b = self.cleaned_data['date_of_b']
        # Для детей проверяем возраст (не старше 18 лет)
        age = (date.today() - date_of_b).days / 365.25
        if age > 18:
            raise ValidationError('Ребёнок должен быть младше 18 лет')
        return date_of_b
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'child'
        if commit:
            user.save()
        return user


class ConnectionCodeForm(forms.Form):
    """Форма для ввода кода присоединения"""
    code = forms.CharField(
        label='Код',
        max_length=10,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Введите код'})
    )
    
    def __init__(self, *args, user_role=None, **kwargs):
        self.user_role = user_role
        super().__init__(*args, **kwargs)
    
    def clean_code(self):
        code = self.cleaned_data['code']
        try:
            user = CUsers.objects.get(connection_code=code)
            
            # Проверка срока действия кода
            if user.code_expires and user.code_expires < timezone.now():
                raise ValidationError('Срок действия кода истёк')
            
            # Проверка соответствия ролей
            if self.user_role == 'parent' and user.role != 'child':
                raise ValidationError('Этот код не является кодом ребёнка')
            elif self.user_role == 'doctor' and user.role != 'child':
                raise ValidationError('Этот код не является кодом пациента')
            elif self.user_role == 'child' and user.role not in ['parent', 'doctor']:
                raise ValidationError('Неверный код')
            
            self.connected_user = user
            return code
        except CUsers.DoesNotExist:
            raise ValidationError('Неверный код')


class PrescriptionForm(forms.ModelForm):
    """Форма для создания назначений/рецептов"""
    
    class Meta:
        model = Prescription
        fields = ['text', 'prescription_type', 'medication_name', 'dosage', 'duration', 'is_active']
        widgets = {
            'text': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'prescription_type': forms.Select(attrs={'class': 'form-control'}),
            'medication_name': forms.TextInput(attrs={'class': 'form-control'}),
            'dosage': forms.TextInput(attrs={'class': 'form-control'}),
            'duration': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.doctor = kwargs.pop('doctor', None)
        super().__init__(*args, **kwargs)
        
        # Если это не лекарство, скрываем поля для лекарств
        self.fields['medication_name'].required = False
        self.fields['dosage'].required = False
        self.fields['duration'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        prescription_type = cleaned_data.get('prescription_type')
        
        if prescription_type == 'medication':
            if not cleaned_data.get('medication_name'):
                raise ValidationError('Для назначения лекарства укажите название препарата')
            if not cleaned_data.get('dosage'):
                raise ValidationError('Укажите дозировку')
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.doctor:
            instance.doctor = self.doctor
        if commit:
            instance.save()
        return instance


class GameResultForm(forms.ModelForm):
    """Форма для сохранения результатов игры"""
    
    class Meta:
        model = GameResult
        fields = [
            'game_type', 'joy', 'sorrow', 'love', 'anger', 'boredom', 'happiness',
            'reaction_time', 'mistakes', 'hints_used', 'strategy_type',
            'drawing_data', 'dialog_answers', 'choices'
        ]
        widgets = {
            'drawing_data': forms.HiddenInput(),
            'dialog_answers': forms.HiddenInput(),
            'choices': forms.HiddenInput(),
            'reaction_times': forms.HiddenInput(),
            'mistake_types': forms.HiddenInput(),
        }


class DoctorVerificationForm(forms.ModelForm):
    """Форма для проверки лицензии врача администратором"""
    
    class Meta:
        model = DoctorLicense
        fields = ['is_verified', 'rejection_reason']
        widgets = {
            'is_verified': forms.RadioSelect(choices=[(True, 'Подтвердить'), (False, 'Отклонить')]),
            'rejection_reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Укажите причину отказа...'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.admin = kwargs.pop('admin', None)
        super().__init__(*args, **kwargs)
        self.fields['is_verified'].label = 'Решение'
        self.fields['rejection_reason'].label = 'Причина отказа'
        self.fields['rejection_reason'].required = False
        if self.instance.is_verified:
            self.fields['is_verified'].widget.attrs['disabled'] = True
    
    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('is_verified') is False and not cleaned_data.get('rejection_reason', '').strip():
            raise ValidationError('При отклонении необходимо указать причину отказа')
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        if instance.is_verified and self.admin:
            instance.verified_by = self.admin
            instance.verified_date = timezone.now()
            instance.rejection_reason = ''
        elif not instance.is_verified:
            instance.verified_by = None
            instance.verified_date = None
        
        if commit:
            instance.save()
        return instance


class ProfileSelfEditForm(forms.ModelForm):
    """Форма для самостоятельного редактирования профиля (без role, is_auth)"""
    
    class Meta:
        model = CUsers
        fields = ['username', 'name', 'date_of_b']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'date_of_b': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }
    
    def clean_username(self):
        username = self.cleaned_data['username']
        if CUsers.objects.filter(username=username).exclude(pk=self.instance.pk).exists():
            raise ValidationError('Пользователь с таким логином уже существует')
        return username


class UserEditForm(forms.ModelForm):
    """Форма для редактирования пользователя администратором. Роль admin нельзя назначить (защита от создания новых админов)."""
    
    class Meta:
        model = CUsers
        fields = ['username', 'name', 'date_of_b', 'role', 'is_auth']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'date_of_b': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'role': forms.Select(attrs={'class': 'form-control'}),
            'is_auth': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Роль "Администратор" доступна только при редактировании существующего админа
        if self.instance and self.instance.pk and self.instance.role != 'admin':
            self.fields['role'].choices = [
                (r, l) for r, l in CUsers._meta.get_field('role').choices if r != 'admin'
            ]
    
    def clean_role(self):
        role = self.cleaned_data.get('role')
        if role == 'admin' and self.instance and self.instance.pk and self.instance.role != 'admin':
            raise ValidationError('Нельзя назначить роль администратора')
        return role
    
    def clean_username(self):
        username = self.cleaned_data['username']
        # Проверяем, что username уникален, исключая текущего пользователя
        if CUsers.objects.filter(username=username).exclude(pk=self.instance.pk).exists():
            raise ValidationError('Пользователь с таким логином уже существует')
        return username


class ChildAssignForm(forms.Form):
    """Форма для привязки ребёнка к родителю/врачу"""
    child_id = forms.ModelChoiceField(
        label='Ребёнок',
        queryset=CUsers.objects.filter(role='child'),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        self.parent_user = kwargs.pop('parent_user', None)
        super().__init__(*args, **kwargs)
        
        # Исключаем уже привязанных детей
        if self.parent_user:
            assigned_ids = self.parent_user.children.values_list('id', flat=True)
            self.fields['child_id'].queryset = self.fields['child_id'].queryset.exclude(id__in=assigned_ids)


class DateRangeFilterForm(forms.Form):
    """Форма для фильтрации результатов по дате"""
    date_from = forms.DateField(
        label='С',
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    date_to = forms.DateField(
        label='По',
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    game_type = forms.ChoiceField(
        label='Тип игры',
        required=False,
        choices=[('', 'Все')] + GameResult._meta.get_field('game_type').choices,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        
        if date_from and date_to and date_from > date_to:
            raise ValidationError('Дата "С" не может быть позже даты "По"')
        
        return cleaned_data


class SubscriptionForm(forms.ModelForm):
    """Форма для управления подписками"""
    
    class Meta:
        model = Subscription
        fields = ['subscription_type', 'max_children', 'max_doctors', 'end_date', 'price', 'is_active']
        widgets = {
            'subscription_type': forms.Select(attrs={'class': 'form-control'}),
            'max_children': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'max_doctors': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'end_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean_end_date(self):
        end_date = self.cleaned_data['end_date']
        if end_date < timezone.now():
            raise ValidationError('Дата окончания не может быть в прошлом')
        return end_date


class FeedbackForm(forms.Form):
    """Форма обратной связи"""
    name = forms.CharField(
        label='Ваше имя',
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    subject = forms.CharField(
        label='Тема',
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    message = forms.CharField(
        label='Сообщение',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5})
    )
    
    def clean_message(self):
        message = self.cleaned_data['message']
        if len(message) < 10:
            raise ValidationError('Сообщение должно содержать не менее 10 символов')
        return message


class PasswordChangeForm(forms.Form):
    """Форма смены пароля"""
    old_password = forms.CharField(
        label='Старый пароль',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    new_password = forms.CharField(
        label='Новый пароль',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    new_password_confirm = forms.CharField(
        label='Подтверждение нового пароля',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
    
    def clean_old_password(self):
        old_password = self.cleaned_data['old_password']
        if self.user and not self.user.check_password(old_password):
            raise ValidationError('Неверный старый пароль')
        return old_password
    
    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        new_password_confirm = cleaned_data.get('new_password_confirm')
        
        if new_password and new_password_confirm and new_password != new_password_confirm:
            raise ValidationError('Новые пароли не совпадают')
        
        if new_password and len(new_password) < 6:
            raise ValidationError('Пароль должен содержать не менее 6 символов')
        
        return cleaned_data


class BulkChildAssignForm(forms.Form):
    """Форма для массовой привязки детей (для администратора)"""
    parent = forms.ModelChoiceField(
        label='Родитель',
        queryset=CUsers.objects.filter(role='parent'),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    children = forms.ModelMultipleChoiceField(
        label='Дети',
        queryset=CUsers.objects.filter(role='child'),
        widget=forms.SelectMultiple(attrs={'class': 'form-control', 'size': 10})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Исключаем уже привязанных детей
        if 'parent' in self.data:
            try:
                parent_id = int(self.data.get('parent'))
                parent = CUsers.objects.get(id=parent_id)
                assigned_ids = parent.children.values_list('id', flat=True)
                self.fields['children'].queryset = self.fields['children'].queryset.exclude(id__in=assigned_ids)
            except (ValueError, CUsers.DoesNotExist):
                pass
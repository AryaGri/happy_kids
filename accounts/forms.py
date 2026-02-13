# accounts/forms.py
from django import forms
from .models import CUsers
from .models import Prescription


class LoginForm(forms.Form):
    username = forms.CharField(label='Логин', max_length=150)
    password = forms.CharField(label='Пароль', widget=forms.PasswordInput)

class UserCreateForm(forms.ModelForm):
    class Meta:
        model = CUsers
        fields = ['username', 'name', 'date_of_b', 'password', 'role']

    def clean_password(self):
        password = self.cleaned_data.get('password')
        # Если это новый пользователь, проверяем, что пароль заполнен
        if not password:
            raise forms.ValidationError('Пароль обязателен для нового пользователя.')
        return password

class GameForm(forms.Form):
    color = forms.ChoiceField(choices=[('красная', 'Красная'), ('оранжевая', 'Оранжевая'), ('жёлтая', 'Жёлтая'), ('зелёная', 'Зелёная'), ('синяя', 'Синяя'), ('фиолетовая', 'Фиолетовая')])


class PrescriptionForm(forms.ModelForm):
    class Meta:
        model = Prescription
        fields = ['text']  # Поле для ввода текста рецепта

    text = forms.CharField(widget=forms.Textarea(attrs={'rows': 4, 'cols': 50}), label='Рецепт', required=True)
    
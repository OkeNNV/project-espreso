from django import forms
from django.contrib.auth import password_validation

from coffee_ordering.models import User


class cartForm():
    ...


class RegisterForm(forms.Form):
    username = forms.CharField(label="Ім'я користувача", max_length=150)
    email = forms.EmailField(label='Email')
    password1 = forms.CharField(label='Пароль', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Повторіть пароль', widget=forms.PasswordInput)

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Користувач з таким ім'ям вже існує.")
        return username

    def clean_email(self):
        email = self.cleaned_data['email'].lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Користувач з таким email вже існує.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        if password1 and password2 and password1 != password2:
            self.add_error('password2', 'Паролі не співпадають.')
        elif password1:
            try:
                password_validation.validate_password(password1)
            except forms.ValidationError as e:
                self.add_error('password1', e)

        return cleaned_data

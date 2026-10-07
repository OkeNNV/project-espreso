from django import forms
from django.contrib.auth import password_validation
from django.db.models import Q

from coffee_ordering.models import User


class RegisterForm(forms.Form):
    """Форма реэстрації"""
    username = forms.CharField(label="Ім'я користувача", max_length=150)
    email = forms.EmailField(label='Email')
    password1 = forms.CharField(label='Пароль', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Повторіть пароль', widget=forms.PasswordInput)

    def clean_username(self):
        """Перевірка чи немає юзера з подібним юзернеймом"""
        username = self.cleaned_data['username'].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Користувач з таким ім'ям вже існує.")
        return username

    def clean_email(self):
        """Перевірка чи немає юзера з подібним емейл"""
        email = self.cleaned_data['email'].lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Користувач з таким email вже існує.')
        return email

    def clean(self):
        """Валідація паролів"""
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


class UserSearchForm(forms.Form):
    """Пошук і фільтрація списку користувачів через GET-параметри."""

    q = forms.CharField(
        required=False,
        max_length=100,
        strip=True,
        widget=forms.TextInput(attrs={'placeholder': 'Логін або email'}),
    )
    role = forms.ChoiceField(
        required=False,
        choices=[('', 'Усі ролі'), *User.Role.choices],
    )
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'Усі статуси'), *User.Status.choices],
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            css = 'form-select' if isinstance(field, forms.ChoiceField) else 'form-control'
            field.widget.attrs['class'] = css

    def filter(self, queryset):
        """
            Пошук за заповненими полями.
            --Q() емейл чи юзернейм.
            --роль
            --статус
        """
        self.is_valid()
        data = self.cleaned_data

        if data.get('q'):
            queryset = queryset.filter(
                Q(username__icontains=data['q']) | Q(email__icontains=data['q'])
            )
        if data.get('role'):
            queryset = queryset.filter(role=data['role'])
        if data.get('status'):
            queryset = queryset.filter(status=data['status'])
        return queryset

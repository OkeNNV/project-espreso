from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from coffee_ordering.services.user_activation_token_service import UserActivationTokenService

User = get_user_model()


class UserService:
    def __init__(self, token_service: UserActivationTokenService) -> None:
        self.token_service = token_service

    @staticmethod
    def get_uid(pk: int) -> str:
        """
            Закодовує первинний ключ (pk) у формат base64 (безпечний для URL).
        """
        return urlsafe_base64_encode(force_bytes(pk))

    def get_activation_link(self, url: str, user: User) -> str:
        """
            Генерує токен через token_service та повертає повне посилання для активації.
        """
        uid = self.get_uid(user.pk)
        token = self.token_service.make_token(user)

        separator = "&" if "?" in url else "?"
        return f"{url}{separator}uid={uid}&token={token}"

    @staticmethod
    def decode_uid(uidb64: str) -> int:
        """
            Декодує base64 UID назад в integer PK.
        """
        return int(urlsafe_base64_decode(uidb64).decode('utf-8'))

    @staticmethod
    def create_pending_user(username: str, email: str, password: str, **extra_fields) -> User:
        """
            Створює нового користувача, очікує на підтвердження email адреси
        """
        with transaction.atomic():
            user = User(
                username=username,
                email=email,
                is_active=False,
                status=User.Status.PENDING,
                **extra_fields
            )
            user.set_password(password)
            user.save()
            return user

    @staticmethod
    def confirm_user_email(user: User) -> User:
        """
            Активовує користувача дозволяючи йому користуватися додатком після підтвердження email
        """
        with transaction.atomic():
            user.is_active = True
            user.status = User.Status.ACTIVE
            user.save(update_fields=['is_active', 'status'])
            return user

    @staticmethod
    def change_role(user: User, new_role: str) -> User:
        """
            Змінює роль користувача та автоматично оновлює is_staff і is_superuser.
        """
        if new_role not in User.Role.values:
            raise ValueError(f"Некоректна роль: {new_role}")

        with transaction.atomic():
            user.role = new_role

            if new_role in [User.Role.MODERATOR, User.Role.ADMIN]:
                user.is_staff = True
            else:
                user.is_staff = False

            user.is_superuser = (new_role == User.Role.ADMIN)

            user.save(update_fields=['role', 'is_staff', 'is_superuser'])
            return user

    @staticmethod
    def change_status(user: User, new_status: str) -> User:
        """
            Змінює статус користувача та синхронізує is_active:
            - BLOCKED / BLACKLISTED -> is_active = False
            - ACTIVE -> is_active = True
        """
        if new_status not in User.Status.values:
            raise ValueError(f"Некоректний статус: {new_status}")

        with transaction.atomic():
            user.status = new_status

            if new_status in [User.Status.BLOCKED, User.Status.PENDING]:
                user.is_active = False
            elif new_status == User.Status.ACTIVE:
                user.is_active = True

            user.save(update_fields=['status', 'is_active'])
            return user

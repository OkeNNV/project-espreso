from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import PasswordResetTokenGenerator

User = get_user_model()


class UserActivationTokenService(PasswordResetTokenGenerator):
    def _make_hash_value(self, user: User, timestamp: int) -> str:
        """
            Генерує хеш на основі даних користувача.
        """
        return f"{user.pk}{timestamp}{user.is_active}{getattr(user, 'status', '')}"

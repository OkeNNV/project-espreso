from django.contrib.auth import get_user_model
from django.db import transaction

User = get_user_model()


class UserService:
    @staticmethod
    def create_pending_user(email: str, password: str, **extra_fields) -> User:
        with transaction.atomic():
            user = User(
                username=email,
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
        with transaction.atomic():
            user.is_active = True
            user.status = User.Status.ACTIVE
            user.save(update_fields=['is_active', 'status'])
            return user


class OrderService:
    ...


class ProductService:
    ...


class CartService:
    ...

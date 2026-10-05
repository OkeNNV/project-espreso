from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.templatetags.static import static


def conver_to_uah(value: int) -> Decimal:
    return (Decimal(value) / 100).quantize(Decimal('0.00'))


class User(AbstractUser):
    """
        Кастомна модель користувача, яка розширює базовий `AbstractUser` з Django.

        Використовується для автентифікації, розмежування прав доступу через ролі,
        управління статусом акаунта та підтвердження пошти за допомогою токена
    """

    class Role(models.TextChoices):
        CUSTOMER = 'CUSTOMER', 'Customer'
        MODERATOR = 'MODERATOR', 'Mod'
        ADMIN = 'ADMIN', 'Admin'

    class Status(models.TextChoices):
        PENDING = 'PENDING'
        ACTIVE = 'ACTIVE'
        BLOCKED = 'BLOCKED'

    email = models.EmailField(unique=True)
    role = models.CharField(choices=Role, max_length=20, default=Role.CUSTOMER)
    status = models.CharField(choices=Status, max_length=20, default=Status.PENDING)

    @property
    def is_moderator(self) -> bool:
        """Перевірка прав редагування контенту на сторінці доступній для модераторів і вище"""
        return self.role in (self.Role.MODERATOR, self.Role.ADMIN)

    @property
    def is_admin(self) -> bool:
        """Перевірка прав редагування на сторінці доступній лише адміністраторам"""
        return self.role == self.Role.ADMIN

    def __str__(self):
        return f'{self.username} : {self.get_role_display()}'


class Category(models.Model):
    """
        Категорія товарів (наприклад: "Кава", "Десерти", "Сезонне меню").
    """
    name = models.CharField(max_length=50)
    slug = models.CharField(max_length=20)

    def __str__(self):
        return self.name


class Product(models.Model):
    """
        Товар кав'ярні із зазначенням ціни в копійках, опису та прив'язкою до категорії.
    """
    name = models.CharField(max_length=50)
    price = models.PositiveIntegerField(default=0)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    description = models.CharField(max_length=255, null=True, blank=True)
    details = models.CharField(max_length=255, null=True, blank=True)
    is_available = models.BooleanField(default=False)
    quantity = models.PositiveSmallIntegerField(default=0)

    # image = models.CharField(max_length=500, blank=True, default='')
    #
    # @property
    # def image_url(self) -> str | None:
    #     """Готове посилання для <img>: зовнішнє як є, статичний шлях через static()."""
    #     if not self.image:
    #         return None
    #     if self.image.startswith(('http://', 'https://')):
    #         return self.image
    #     return static(self.image)

    @property
    def price_uah(self) -> Decimal:
        return conver_to_uah(self.price)

    class Meta:
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['category', 'is_available']),
        ]

    def __str__(self):
        return self.name


class Order(models.Model):
    """
        Замовлення клієнта з фіксацією статусу, дати створення та підсумкової суми.
    """

    class Status(models.TextChoices):
        NEW = 'NEW'
        IN_PROGRESS = 'IN_PROGRESS'
        READY = 'READY'
        COMPLETED = 'COMPLETED'
        CANCELED = 'CANCELED'

    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name='orders')
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(choices=Status, default=Status.NEW, max_length=20)
    total_price = models.PositiveIntegerField(default=0)
    handler = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True, related_name='handled_orders'
    )

    @property
    def total_price_uah(self) -> Decimal:
        return conver_to_uah(self.total_price)

    def __str__(self):
        return f"Order #{self.id} by {self.user.username} [{self.get_status_display()}]"


class OrderItem(models.Model):
    """
        Окрема позиція в замовленні з фіксацією ціни товару на момент купівлі.
    """
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='order_items')
    quantity = models.PositiveSmallIntegerField(default=1)
    price = models.PositiveIntegerField()

    @property
    def price_uah(self) -> Decimal:
        return conver_to_uah(self.price)

    def __str__(self):
        return f"{self.quantity} x {self.product.name} (Order #{self.order.id})"


class Cart(models.Model):
    """
        Тимчасовий кошик користувача для накопичення товарів перед оформленням замовлення.
    """
    user = models.OneToOneField(
        'User',
        on_delete=models.CASCADE,
        related_name='cart',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Cart of {self.user.username}'

    @property
    def total_price(self) -> int:
        """Сума кошика в копійках."""
        return sum(item.get_cost for item in self.items.select_related('product'))

    @property
    def total_price_uah(self) -> Decimal:
        return conver_to_uah(self.total_price)


class CartItem(models.Model):
    """
        Позиція в кошику із зазначенням обраної кількості товару.
    """
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='cart_items'
    )
    quantity = models.PositiveSmallIntegerField(default=1)

    class Meta:
        unique_together = ('cart', 'product')

    @property
    def get_cost(self) -> int:
        """Вартість позиції на основі ціни товару в копійках."""
        return self.product.price * self.quantity

    @property
    def get_cost_uah(self) -> Decimal:
        """Вартість позиції на основі ціни товару."""
        return conver_to_uah(self.product.price * self.quantity)

    def __str__(self):
        return f'{self.quantity} x {self.product.name} in Cart #{self.cart.id}'

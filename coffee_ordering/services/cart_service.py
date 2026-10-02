from django.db import transaction
from django.db.models import F

from coffee_ordering.models import (
    Product,
    User,
    Cart,
    CartItem,
    Order,
    OrderItem
)


class CartException(Exception):
    """Базовий виняток для всіх помилок Cart."""
    pass


class EmptyCartError(CartException):
    """Виникає при спробі виконати операцію з порожнім кошиком (наприклад, checkout)."""
    pass


class ProductUnavailableError(CartException):
    """Виникає, якщо товар недоступний для замовлення (`is_available=False`)."""

    def __init__(self, product_name: str):
        self.product_name = product_name
        super().__init__(f"Товар '{product_name}' наразі недоступний для замовлення.")


class InsufficientStockError(CartException):
    """Виникає, якщо запитувана кількість перевищує наявний залишок на складі."""

    def __init__(self, product_name: str, available_quantity: int):
        self.product_name = product_name
        self.available_quantity = available_quantity
        super().__init__(
            f"Недостатньо товару '{product_name}' на складі. Доступно: {available_quantity} шт."
        )


class CartItemNotFoundError(CartException):
    """Виникає, якщо позицію не знайдено в кошику."""
    pass


class CartService:
    """
        Сервіс для управління кошиком покупок користувача.

        Забезпечує бізнес-логіку додавання, видалення, оновлення товарів у кошику,
        перевірку їх доступності та наявності на складі, а також відповідає за
        процес "оформлення замовлення" (checkout) із зафіксованими цінами.

        Основні задачі:
            - Отримання або створення об'єкта кошика для користувача.
            - Валідація залишків товарів на складі перед зміною вмісту кошика.
            - Перетворення вмісту кошика на замовлення (Order)
              зі списанням залишків товару та очищенням кошика.
    """
    @staticmethod
    def get_or_create_cart(user: User) -> Cart:
        """Отримує кошик користувача, або створює його у разі відсутності"""
        try:
            return user.cart
        except Cart.DoesNotExist:
            return Cart.objects.create(user=user)
        # cart, _ = Cart.objects.prefetch_related('items__product').get_or_create(user=user)
        # return cart

    @classmethod
    def add_item(cls, user: User, product: Product, quantity: int = 1) -> CartItem:
        """Додає товар або збільшує його кількість із перевіркою доступності та залишків."""
        if not product.is_available:
            raise ProductUnavailableError(product.name)

        cart = cls.get_or_create_cart(user)
        existing_item = CartItem.object.filter(cart=cart, product=product).first()
        current_quantity_in_cart = existing_item.quantity if existing_item else 0
        new_quantity = current_quantity_in_cart + quantity

        if new_quantity > product.quantity:
            raise InsufficientStockError(product.name, product.quantity)

        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={'quantity': quantity}
        )

        if not created:
            cart_item.quantity = F('quantity') + quantity
            cart_item.save(update_fields=['quantity'])
            cart_item.refresh_from_db()

        return cart_item

    @classmethod
    def remove_item(cls, user: User, product: Product) -> None:
        """Видаляє конкретний продукт з кошика."""
        cart = cls.get_or_create_cart(user)
        deleted_count, _ = CartItem.objects.filter(cart=cart, product=product).delete()
        if deleted_count == 0:
            raise CartItemNotFoundError(f"'{product}' не знайдено у кошику.")

    @classmethod
    def clear_cart(cls, user: User) -> None:
        """Повністю спустошує кошик."""
        cart = cls.get_or_create_cart(user)
        cart.items.all().delete()

    @classmethod
    def update_quantity(cls, user: User, product: Product, quantity: int) -> None | CartItem:
        """Оновлює кількість продуктів наявних у кошику, або викликає видалення продукту з кошика."""
        if quantity <= 0:
            cls.remove_item(user=user, product=product)
            return None

        if not product.is_available:
            raise ProductUnavailableError

        if quantity > product.quantity:
            raise InsufficientStockError

        cart = cls.get_or_create_cart(user)

        try:
            cart_item = CartItem.objects.get(cart=cart, product=product)
        except CartItem.DoesNotExist:
            raise CartItemNotFoundError(f"'{product}' не знайдено у кошику.")

        cart_item.quantity = quantity
        cart_item.save(update_fields="quantity")

        return cart_item

    @classmethod
    @transaction.atomic
    def checkout(cls, user: User) -> Order:
        """
            Перетворює кошик на Order:
            - Перевіряє доступність товару
            - Фіксує ціну товару на момент створення замовлення
            - Зменшує кількість товарів у БД
            - Очищує кошик
        """
        cart = cls.get_or_create_cart(user)
        items = cart.items.select_related('product').select_for_update()

        if not items.exists():
            raise EmptyCartError("Неможливо створити замовлення з порожнім кошиком.")

        for item in items:
            if not item.product.is_available:
                raise ProductUnavailableError(item.product.name)
            if item.quantity > item.product.quantity:
                raise InsufficientStockError(item.product.name, item.product.quantity)

        order = Order.objects.create(
            user=user,
            total_price=cart.total_price,
            status=Order.Status.NEW
        )
        order_items = []

        for item in items:
            order_items.append(
                OrderItem(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price=item.product.price
                )
            )
            item.product.quantity -= item.quantity
            item.product.save(update_fields=['quantity'])

        OrderItem.objects.bulk_create(order_items)

        cls.clear_cart(user)

        return order

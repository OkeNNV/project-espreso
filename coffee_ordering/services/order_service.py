from django.db import transaction
from django.db.models import QuerySet

from coffee_ordering.models import (
    User,
    Order
)
from coffee_ordering.services.cart_service import (
    CartService,
    EmptyCartError,
    ProductUnavailableError,
    InsufficientStockError,
    CartException
)


class OrderException(Exception):
    """Базовий виняток для всіх помилок Order."""
    pass


class OrderCreationError(OrderException):
    """Виникає при помилках під час створення замовлення."""
    pass


class OrderNotFoundError(OrderException):
    """Виникає коли Order відсутній або не знайдено в БД"""
    pass


class OrderCannotBeCanceledError(OrderException):
    """Виникає при спробі скасувати замовлення, яке вже не можна скасувати."""
    pass


class OrderCannotBeCompletedError(OrderException):
    """Виникає при спробі завершити замовлення, яке не готове або вже скасоване."""
    pass


class OrderService:
    """
        Сервіс для управління життєвим циклом замовлень кав'ярні.

        Містить бізнес-логіку створення замовлень (через кошик або оператора),
        зміни їх статусів (прийняття в роботу, готовність, завершення, скасування),
        а також формування списків замовлень для каси/кухні та клієнта.

        Основні задачі:
            - Створення замовлень клієнтом або працівником по телефону.
            - Призначення відповідального працівника за замовлення.
            - Скасування замовлення з автоматичним поверненням товарів на склад.
            - Вибірка активних замовлень для табло/екрана.
    """

    @classmethod
    def get_order_by_id(cls, order_id: int) -> Order:
        try:
            return Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            raise OrderNotFoundError(f"Замовлення #{order_id} не знайдено.")

    @classmethod
    def create_order_from_cart(cls, user: User) -> Order:
        try:
            order = CartService.checkout(user)
            return order
        except (EmptyCartError, ProductUnavailableError, InsufficientStockError) as e:
            raise OrderCreationError(str(e)) from e
        except CartException as e:
            raise OrderCreationError(f"Помилка при обробці кошика: {str(e)}") from e

    @classmethod
    @transaction.atomic
    def accept_order(cls, order_id: int, handler: User) -> Order:

        order = cls.get_order_by_id(order_id)

        order.handler = handler
        order.status = Order.Status.IN_PROGRESS
        order.save(update_fields=['handler', 'status'])

        return order

    @classmethod
    @transaction.atomic
    def cancel_order(cls, order_id: int, handler: User) -> Order:
        """

        """
        order = cls.get_order_by_id(order_id)

        if order.status in (Order.Status.COMPLETED, Order.Status.CANCELED):
            raise OrderCannotBeCanceledError(
                f"Неможливо скасувати замовлення #{order.id}"
                f" Статус: '{order.get_status_display()}'."
            )

        order_items = order.items.select_related('product').all()

        for item in order_items:
            item.product.quantity += item.quantity
            item.product.save(update_fields=['quantity'])

        order.status = Order.Status.CANCELED

        if handler and not order.handler:
            order.handler = handler

        order.save(update_fields=['status', 'handler'])

        return order

    @classmethod
    def complete_order(cls, order_id: int) -> Order:
        """

        """
        order = cls.get_order_by_id(order_id)

        if order.status in (Order.Status.COMPLETED, Order.Status.CANCELED):
            raise OrderCannotBeCompletedError(
                f"Замовлення #{order.id} вже опрацьовано. Статус: '{order.get_status_display()}'."
            )

        order.status = Order.Status.COMPLETED

        order.save(update_fields=['status', 'handler'])

        return order

    @classmethod
    def mark_as_ready(cls, order_id: int) -> Order:
        """Переводить замовлення у статус READY"""
        order = cls.get_order_by_id(order_id)

        if order.status != Order.Status.IN_PROGRESS:
            raise OrderException(
                'Тільки замовлення в процесі приготування можна позначити як готові.'
            )

        order.status = Order.Status.READY
        order.save(update_fields=['status'])

        return order

    @classmethod
    def get_active_orders(cls) -> QuerySet[Order]:
        """Повертає список активних замовлень для працівників закладу."""
        return (
            Order.objects.filter(
                status__in=[Order.Status.NEW, Order.Status.IN_PROGRESS, Order.Status.READY]
            )
            .select_related('user', 'handler')
            .prefetch_related('items__product')
            .order_by('created_at')
        )
    # --------------------------------
    #Переробити логіку створеня замовлення від адміна
    # @classmethod
    # @transaction.atomic
    # def create_order_by_staff(cls, customer: User, staff_user: User) -> Order:
    #     """Оформлення замовлення працівником кав'ярні."""
    #     order = CartService.checkout(customer)
    #     order.handler = staff_user
    #     order.status = Order.Status.IN_PROGRESS
    #     order.save(update_fields=['handler', 'status'])
    #     return order

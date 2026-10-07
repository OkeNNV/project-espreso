from django.core import mail
from django.test import TestCase

from coffee_ordering.models import Order, User
from coffee_ordering.services.cart_service import (
    CartItemNotFoundError,
    CartService,
    EmptyCartError,
    InsufficientStockError,
    ProductUnavailableError,
)
from coffee_ordering.services.catalog_service import (
    CatalogException,
    CatalogService,
    ProductNotFoundError,
)
from coffee_ordering.services.order_service import (
    OrderCannotBeCanceledError,
    OrderCreationError,
    OrderException,
    OrderNotFoundError,
    OrderService,
)
from coffee_ordering.services.user_activation_token_service import UserActivationTokenService
from coffee_ordering.services.user_service import UserService, UserServiceError
from coffee_ordering.tests._helpers import (
    make_product,
    make_user,
    make_order
)


class CatalogServiceTests(TestCase):
    def test_available_products_hide_unavailable_and_out_of_stock(self):
        ok = make_product('Ok')
        make_product('Disabled', is_available=False)
        make_product('Empty', quantity=0)

        self.assertEqual(list(CatalogService.get_available_products()), [ok])

    def test_filter_by_category_slug(self):
        coffee = make_product('Latte')
        from coffee_ordering.models import Category
        dessert_cat = Category.objects.create(name='Dessert', slug='dessert')
        cake = make_product('Cake', category=dessert_cat)

        self.assertEqual(list(CatalogService.get_available_products('dessert')), [cake])
        self.assertNotIn(coffee, CatalogService.get_available_products('dessert'))

    def test_get_product_by_id_not_found(self):
        with self.assertRaises(ProductNotFoundError):
            CatalogService.get_product_by_id(999999)

    def test_update_availability(self):
        product = make_product()
        CatalogService.update_product_availability(product.id, False)
        product.refresh_from_db()
        self.assertFalse(product.is_available)

    def test_zero_stock_disables_product(self):
        product = make_product()
        CatalogService.update_stock_quantity(product.id, 0)
        product.refresh_from_db()
        self.assertEqual(product.quantity, 0)
        self.assertFalse(product.is_available)

    def test_negative_stock_rejected(self):
        product = make_product()
        with self.assertRaises(CatalogException):
            CatalogService.update_stock_quantity(product.id, -1)


class CartServiceTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.product = make_product(price=5000, quantity=5)

    def test_add_item_creates_and_accumulates(self):
        CartService.add_item(self.user, self.product, 2)
        item = CartService.add_item(self.user, self.product, 1)
        self.assertEqual(item.quantity, 3)

    def test_add_unavailable_product(self):
        self.product.is_available = False
        self.product.save()
        with self.assertRaises(ProductUnavailableError):
            CartService.add_item(self.user, self.product)

    def test_add_more_than_stock(self):
        CartService.add_item(self.user, self.product, 3)
        with self.assertRaises(InsufficientStockError):
            CartService.add_item(self.user, self.product, 3)

    def test_update_quantity(self):
        CartService.add_item(self.user, self.product, 1)
        item = CartService.update_quantity(self.user, self.product, 4)
        self.assertEqual(item.quantity, 4)

    def test_update_quantity_over_stock(self):
        CartService.add_item(self.user, self.product, 1)
        with self.assertRaises(InsufficientStockError):
            CartService.update_quantity(self.user, self.product, 99)

    def test_update_quantity_zero_removes_item(self):
        CartService.add_item(self.user, self.product, 1)
        self.assertIsNone(CartService.update_quantity(self.user, self.product, 0))
        self.assertEqual(CartService.get_or_create_cart(self.user).items.count(), 0)

    def test_remove_missing_item(self):
        with self.assertRaises(CartItemNotFoundError):
            CartService.remove_item(self.user, self.product)

    def test_clear_cart(self):
        CartService.add_item(self.user, self.product, 2)
        CartService.clear_cart(self.user)
        self.assertEqual(CartService.get_or_create_cart(self.user).items.count(), 0)

    def test_checkout_creates_order_and_updates_stock(self):
        CartService.add_item(self.user, self.product, 2)
        order = CartService.checkout(self.user)

        self.assertEqual(order.status, Order.Status.NEW)
        self.assertEqual(order.total_price, 10000)
        item = order.items.get()
        self.assertEqual((item.quantity, item.price), (2, 5000))
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 3)
        self.assertEqual(CartService.get_or_create_cart(self.user).items.count(), 0)

    def test_checkout_empty_cart(self):
        with self.assertRaises(EmptyCartError):
            CartService.checkout(self.user)

    def test_checkout_fails_atomically_when_stock_dropped(self):
        CartService.add_item(self.user, self.product, 2)
        self.product.quantity = 1
        self.product.save()

        with self.assertRaises(InsufficientStockError):
            CartService.checkout(self.user)
        self.assertEqual(Order.objects.count(), 0)


class OrderServiceTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.staff = make_user('staff', role=User.Role.MODERATOR)
        self.product = make_product(price=5000, quantity=10)

    def test_create_from_empty_cart(self):
        with self.assertRaises(OrderCreationError):
            OrderService.create_order_from_cart(self.user)

    def test_get_order_not_found(self):
        with self.assertRaises(OrderNotFoundError):
            OrderService.get_order_by_id(999999)

    def test_accept_sets_handler_and_status(self):
        order = make_order(self.user, self.product)
        order = OrderService.accept_order(order.id, self.staff)
        self.assertEqual(order.status, Order.Status.IN_PROGRESS)
        self.assertEqual(order.handler, self.staff)

    def test_full_lifecycle(self):
        order = make_order(self.user, self.product)
        OrderService.accept_order(order.id, self.staff)
        OrderService.mark_as_ready(order.id)
        order = OrderService.complete_order(order.id)
        self.assertEqual(order.status, Order.Status.COMPLETED)

    def test_mark_ready_requires_in_progress(self):
        order = make_order(self.user, self.product)
        with self.assertRaises(OrderException):
            OrderService.mark_as_ready(order.id)

    def test_cancel_returns_stock(self):
        order = make_order(self.user, self.product, quantity=2)
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 8)

        order = OrderService.cancel_order(order.id, self.staff)

        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 10)
        self.assertEqual(order.status, Order.Status.CANCELED)
        self.assertEqual(order.handler, self.staff)

    def test_cannot_cancel_completed(self):
        order = make_order(self.user, self.product)
        Order.objects.filter(pk=order.pk).update(status=Order.Status.COMPLETED)
        with self.assertRaises(OrderCannotBeCanceledError):
            OrderService.cancel_order(order.id, self.staff)

    def test_active_orders_exclude_finished(self):
        active = make_order(self.user, self.product, 1)
        done = make_order(self.user, self.product, 1)
        Order.objects.filter(pk=done.pk).update(status=Order.Status.COMPLETED)

        self.assertEqual(list(OrderService.get_active_orders()), [active])


class UserServiceTests(TestCase):
    def setUp(self):
        self.token_service = UserActivationTokenService()
        self.service = UserService(self.token_service)
        self.user = UserService.create_pending_user('newbie', 'newbie@example.com', 'pass12345')

    def test_create_pending_user(self):
        self.assertFalse(self.user.is_active)
        self.assertEqual(self.user.status, User.Status.PENDING)
        self.assertTrue(self.user.check_password('pass12345'))

    def test_uid_roundtrip(self):
        self.assertEqual(UserService.decode_uid(UserService.get_uid(self.user.pk)), self.user.pk)

    def test_activation_link_contains_uid_and_token(self):
        link = self.service.get_activation_link('http://testserver/activate/', self.user)
        self.assertIn('?uid=', link)
        self.assertIn('&token=', link)

    def test_confirm_email_activates_user(self):
        UserService.confirm_user_email(self.user)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertEqual(self.user.status, User.Status.ACTIVE)

    def test_token_is_invalidated_after_confirmation(self):
        token = self.token_service.make_token(self.user)
        self.assertTrue(self.token_service.check_token(self.user, token))
        UserService.confirm_user_email(self.user)
        self.assertFalse(self.token_service.check_token(self.user, token))

    def test_change_status_blocked_deactivates(self):
        UserService.confirm_user_email(self.user)
        UserService.change_status(self.user, User.Status.BLOCKED)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_change_status_invalid(self):
        with self.assertRaises(ValueError):
            UserService.change_status(self.user, 'NOPE')

    def test_change_status_active_activates_user(self):
        user = UserService.change_status(self.user, User.Status.ACTIVE)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertEqual(self.user.status, User.Status.ACTIVE)
        self.assertEqual(user, self.user)

    def test_change_status_pending_deactivates_user(self):
        active_user = make_user(username='active_guy', status=User.Status.ACTIVE)
        UserService.change_status(active_user, User.Status.PENDING)
        active_user.refresh_from_db()
        self.assertFalse(active_user.is_active)
        self.assertEqual(active_user.status, User.Status.PENDING)

    def test_change_role_success(self):
        UserService.change_role(self.user, User.Role.MODERATOR)
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, User.Role.MODERATOR)

    def test_change_role_invalid_raises_error(self):
        with self.assertRaises(UserServiceError):
            UserService.change_role(self.user, 'INVALID_ROLE')

    def test_block_user_success(self):
        admin = make_user(username='admin', role=User.Role.ADMIN)
        active_user = make_user(username='active_user', status=User.Status.ACTIVE)
        product = make_product()

        order_new = make_order(active_user, product)
        order_in_progress = make_order(active_user, product)
        order_in_progress.status = Order.Status.IN_PROGRESS
        order_in_progress.save()

        order_completed = make_order(active_user, product)
        order_completed.status = Order.Status.COMPLETED
        order_completed.save()

        make_order(active_user, product)

        blocked_user = UserService.block_user(active_user, handler=admin)

        self.assertEqual(blocked_user.status, User.Status.BLOCKED)
        self.assertFalse(blocked_user.is_active)

        order_new.refresh_from_db()
        order_in_progress.refresh_from_db()
        order_completed.refresh_from_db()

        self.assertEqual(order_new.status, Order.Status.CANCELED)
        self.assertEqual(order_in_progress.status, Order.Status.CANCELED)
        self.assertEqual(order_completed.status, Order.Status.COMPLETED)

        self.assertEqual(active_user.cart.items.count(), 0)

    def test_block_non_active_user_raises_error(self):
        admin = make_user(username='admin', role=User.Role.ADMIN)
        with self.assertRaises(UserServiceError):
            UserService.block_user(self.user, handler=admin)

    def test_unblock_user_success(self):
        blocked_user = make_user(username='blocked_guy', status=User.Status.BLOCKED)
        blocked_user.is_active = False
        blocked_user.save()

        unblocked_user = UserService.unblock_user(blocked_user)
        unblocked_user.refresh_from_db()

        self.assertEqual(unblocked_user.status, User.Status.ACTIVE)
        self.assertTrue(unblocked_user.is_active)

    def test_unblock_non_blocked_user_raises_error(self):
        active_user = make_user(username='active_guy', status=User.Status.ACTIVE)
        with self.assertRaises(UserServiceError):
            UserService.unblock_user(active_user)

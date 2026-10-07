from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from coffee_ordering.models import (
    Cart,
    CartItem,
    User,
    conver_to_uah
)
from coffee_ordering.tests._helpers import (
    make_user,
    make_product
)


class ConvertToUahTests(SimpleTestCase):
    def test_to_uah(self):
        self.assertEqual(conver_to_uah(1250), Decimal('12.50'))
        self.assertEqual(conver_to_uah(5), Decimal('0.05'))
        self.assertEqual(conver_to_uah(0), Decimal('0.00'))


class UserModelTests(TestCase):
    def test_roles(self):
        customer = make_user('c')
        moderator = make_user('m', role=User.Role.MODERATOR)
        admin = make_user('a', role=User.Role.ADMIN)

        self.assertFalse(customer.is_moderator)
        self.assertFalse(customer.is_admin)
        self.assertTrue(moderator.is_moderator)
        self.assertFalse(moderator.is_admin)
        self.assertTrue(admin.is_moderator)
        self.assertTrue(admin.is_admin)

    def test_new_user_defaults_to_pending_customer(self):
        user = User.objects.create_user('x', 'x@example.com', 'pass12345')
        self.assertEqual(user.role, User.Role.CUSTOMER)
        self.assertEqual(user.status, User.Status.PENDING)


class ProductModelTests(TestCase):
    def test_price_uah(self):
        product = make_product(price=12345)
        self.assertEqual(product.price_uah, Decimal('123.45'))


class CartModelTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.cart = Cart.objects.create(user=self.user)
        self.a = make_product('A', price=8000)
        self.b = make_product('B', price=13000)
        CartItem.objects.create(cart=self.cart, product=self.a, quantity=3)
        CartItem.objects.create(cart=self.cart, product=self.b, quantity=1)

    def test_item_cost_is_in_kopecks(self):
        item = self.cart.items.get(product=self.a)
        self.assertEqual(item.get_cost, 24000)
        self.assertEqual(item.get_cost_uah, Decimal('240.00'))

    def test_cart_total_is_in_kopecks(self):
        self.assertEqual(self.cart.total_price, 37000)
        self.assertEqual(self.cart.total_price_uah, Decimal('370.00'))

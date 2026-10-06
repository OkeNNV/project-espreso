from coffee_ordering.models import Category, Product, User
from coffee_ordering.services.cart_service import CartService
from coffee_ordering.services.order_service import OrderService

PASSWORD = 'pass12345'


def make_user(username='customer', role=User.Role.CUSTOMER, status=User.Status.ACTIVE):
    return User.objects.create_user(
        username=username,
        email=f'{username}@example.com',
        password=PASSWORD,
        role=role,
        status=status,
    )


def make_product(name='Latte', price=5000, quantity=10, is_available=True, category=None):
    if category is None:
        category, _ = Category.objects.get_or_create(name='Coffee', defaults={'slug': 'coffee'})
    return Product.objects.create(
        name=name, price=price, quantity=quantity,
        is_available=is_available, category=category,
    )


def make_order(user, product, quantity=2):
    CartService.add_item(user, product, quantity)
    return OrderService.create_order_from_cart(user)

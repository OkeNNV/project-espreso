from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from coffee_ordering.forms import RegisterForm
from coffee_ordering.models import Order, Product, User
from coffee_ordering.services.cart_service import (
    CartException,
    CartService,
)
from coffee_ordering.services.catalog_service import (
    CatalogException,
    CatalogService,
    ProductNotFoundError,
)
from coffee_ordering.services.order_service import (
    OrderException,
    OrderCreationError,
    OrderNotFoundError,
    OrderService,
)
from coffee_ordering.services.user_activation_token_service import UserActivationTokenService
from coffee_ordering.services.user_service import UserService

user_service = UserService(UserActivationTokenService())

PAGE_SIZE = 12


def _paginate(request, queryset, per_page=PAGE_SIZE):
    """Кастомна пагінація"""
    if hasattr(queryset, 'ordered') and not queryset.ordered:
        queryset = queryset.order_by('pk')

    paginator = Paginator(queryset, per_page)
    page = paginator.get_page(request.GET.get('page'))
    page.elided_range = paginator.get_elided_page_range(
        page.number, on_each_side=2, on_ends=1
    )
    return page


def active_required(view):
    """Доступ лише для авторизованих користувачів зі статусом ACTIVE."""

    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.status != User.Status.ACTIVE:
            raise PermissionDenied('Акаунт не активовано або заблоковано.')
        return view(request, *args, **kwargs)

    return wrapper


def moderator_required(view):
    """Доступ для модераторів та адміністраторів (з активним акаунтом)."""

    @wraps(view)
    @active_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_moderator:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper


def _parse_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _redirect_back(request, default):
    """Редірект на ?next=/POST next, якщо він безпечний, інакше на default."""
    target = request.POST.get('next') or request.GET.get('next')
    if target and url_has_allowed_host_and_scheme(
            target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(target)
    return redirect(default)


def _get_product_or_404(product_id: int) -> Product:
    try:
        return CatalogService.get_product_by_id(product_id)
    except ProductNotFoundError as e:
        raise Http404(str(e)) from e


def _get_order_or_404(order_id: int) -> Order:
    try:
        return OrderService.get_order_by_id(order_id)
    except OrderNotFoundError as e:
        raise Http404(str(e)) from e


@require_http_methods(['GET', 'POST'])
def register(request):
    if request.user.is_authenticated:
        return redirect('coffee_ordering:menu')

    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = UserService.create_pending_user(
            username=form.cleaned_data['username'],
            email=form.cleaned_data['email'],
            password=form.cleaned_data['password1'],
        )
        user_service.send_activation_email(
            user, request.build_absolute_uri(reverse('coffee_ordering:activate'))
        )
        return render(request, 'registration/register_done.html', {'email': user.email})

    return render(request, 'registration/register.html', {'form': form})


@require_GET
def activate(request):
    """Підтвердження email за посиланням ?uid=<uidb64>&token=<token>."""
    try:
        user = User.objects.get(pk=UserService.decode_uid(request.GET.get('uid', '')))
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is None or not user_service.token_service.check_token(
            user, request.GET.get('token', '')
    ):
        messages.error(request, 'Посилання для активації недійсне або застаріле.')
        return redirect('login')

    if user.status == User.Status.PENDING:
        UserService.confirm_user_email(user)
    messages.success(request, 'Акаунт активовано. Тепер ви можете увійти.')
    return redirect('login')


@require_GET
def menu(request):
    """Меню для клієнтів, з опційним фільтром ?category=<slug>."""
    category_slug = request.GET.get('category') or None
    categories = CatalogService.get_all_categories()

    if category_slug and not categories.filter(slug=category_slug).exists():
        raise Http404(f"Категорію '{category_slug}' не знайдено.")

    products = _paginate(request, CatalogService.get_available_products(category_slug))
    return render(
        request, 'coffee_ordering/public/menu.html', {
            'categories': categories,
            'products': products,
            'active_category': category_slug,
        }
    )


@require_GET
def product_detail(request, product_id: int):
    product = _get_product_or_404(product_id)

    hidden = not product.is_available or product.quantity <= 0
    if hidden and not (request.user.is_authenticated and request.user.is_moderator):
        raise Http404('Товар недоступний.')

    return render(request, 'coffee_ordering/public/product_detail.html', {'product': product})


@active_required
@require_GET
def cart_detail(request):
    cart = CartService.get_or_create_cart(request.user)
    items = cart.items.select_related('product')
    return render(
        request, 'coffee_ordering/public/cart.html', {
            'cart': cart,
            'items': items,
            'total_price': cart.total_price_uah,
        }
    )


@active_required
@require_POST
def cart_add(request, product_id: int):
    product = _get_product_or_404(product_id)
    quantity = _parse_int(request.POST.get('quantity'), default=1)

    if quantity is None or quantity <= 0:
        messages.error(request, 'Некоректна кількість.')
        return _redirect_back(request, 'coffee_ordering:menu')

    try:
        CartService.add_item(request.user, product, quantity)
        messages.success(request, f"'{product.name}' додано до кошика.")
    except CartException as e:
        messages.error(request, str(e))

    return _redirect_back(request, 'coffee_ordering:cart')


@active_required
@require_POST
def cart_update(request, product_id: int):
    product = _get_product_or_404(product_id)
    quantity = _parse_int(request.POST.get('quantity'))

    if quantity is None:
        messages.error(request, 'Некоректна кількість.')
        return redirect('coffee_ordering:cart')

    try:
        CartService.update_quantity(request.user, product, quantity)
    except CartException as e:
        messages.error(request, str(e))

    return redirect('coffee_ordering:cart')


@active_required
@require_POST
def cart_remove(request, product_id: int):
    product = _get_product_or_404(product_id)
    try:
        CartService.remove_item(request.user, product)
        messages.success(request, f"'{product.name}' видалено з кошика.")
    except CartException as e:
        messages.error(request, str(e))
    return redirect('coffee_ordering:cart')


@active_required
@require_POST
def cart_clear(request):
    CartService.clear_cart(request.user)
    messages.success(request, 'Кошик очищено.')
    return redirect('coffee_ordering:cart')


@active_required
@require_POST
def checkout(request):
    try:
        order = OrderService.create_order_from_cart(request.user)
    except OrderCreationError as e:
        messages.error(request, str(e))
        return redirect('coffee_ordering:cart')

    messages.success(request, f'Замовлення #{order.id} оформлено.')
    return redirect('coffee_ordering:order_detail', order_id=order.id)


@active_required
@require_GET
def my_orders(request):
    orders = (
        Order.objects.filter(user=request.user)
        .prefetch_related('items__product')
        .order_by('-created_at')
    )
    return render(request, 'coffee_ordering/public/my_orders.html', {'orders': orders})


@active_required
@require_GET
def order_detail(request, order_id: int):
    order = _get_order_or_404(order_id)

    if order.user_id != request.user.id and not request.user.is_moderator:
        raise Http404

    items = order.items.select_related('product')
    return render(
        request, 'coffee_ordering/public/order_detail.html', {
            'order': order,
            'items': items,
        }
    )


@active_required
@require_POST
def order_cancel(request, order_id: int):
    order = _get_order_or_404(order_id)
    is_staff = request.user.is_moderator

    if order.user_id != request.user.id and not is_staff:
        raise Http404

    if not is_staff and order.status != Order.Status.NEW:
        messages.error(request, 'Замовлення вже в роботі. Зверніться до працівника.')
        return redirect('coffee_ordering:order_detail', order_id=order.id)

    try:
        OrderService.cancel_order(order_id, handler=request.user if is_staff else None)
        messages.success(request, f'Замовлення #{order_id} скасовано.')
    except OrderException as e:
        messages.error(request, str(e))

    return redirect('coffee_ordering:order_detail', order_id=order_id)


@moderator_required
@require_GET
def active_orders(request):
    """Табло активних замовлень для каси/кухні."""
    return render(
        request, 'coffee_ordering/staff/active_orders.html', {
            'orders': OrderService.get_active_orders(),
        }
    )


def _staff_order_action(request, order_id, action, success_msg):
    try:
        action()
        messages.success(request, success_msg.format(id=order_id))
    except OrderException as e:
        messages.error(request, str(e))
    return redirect('coffee_ordering:staff_active_orders')


@moderator_required
@require_POST
def staff_order_accept(request, order_id: int):
    return _staff_order_action(
        request, order_id,
        lambda: OrderService.accept_order(order_id, handler=request.user),
        'Замовлення #{id} прийнято в роботу.',
    )


@moderator_required
@require_POST
def staff_order_ready(request, order_id: int):
    return _staff_order_action(
        request, order_id,
        lambda: OrderService.mark_as_ready(order_id),
        'Замовлення #{id} готове.',
    )


@moderator_required
@require_POST
def staff_order_complete(request, order_id: int):
    return _staff_order_action(
        request, order_id,
        lambda: OrderService.complete_order(order_id),
        'Замовлення #{id} завершено.',
    )


@moderator_required
@require_POST
def staff_order_cancel(request, order_id: int):
    return _staff_order_action(
        request, order_id,
        lambda: OrderService.cancel_order(order_id, handler=request.user),
        'Замовлення #{id} скасовано.',
    )


@moderator_required
@require_GET
def staff_products(request):
    products = Product.objects.select_related('category').order_by('category__name', 'name')
    return render(
        request, 'coffee_ordering/staff/products.html', {'products': _paginate(request, products, 20)}
    )

@moderator_required
@require_POST
def staff_product_availability(request, product_id: int):
    is_available = request.POST.get('is_available') in ('1', 'true', 'on', 'True')
    try:
        product = CatalogService.update_product_availability(product_id, is_available)
        state = 'доступний' if product.is_available else 'прихований'
        messages.success(request, f"'{product.name}' тепер {state}.")
    except CatalogException as e:
        messages.error(request, str(e))
    return redirect('coffee_ordering:staff_products')


@moderator_required
@require_POST
def staff_product_stock(request, product_id: int):
    quantity = _parse_int(request.POST.get('quantity'))
    if quantity is None:
        messages.error(request, 'Некоректна кількість.')
        return redirect('coffee_ordering:staff_products')

    try:
        product = CatalogService.update_stock_quantity(product_id, quantity)
        messages.success(request, f"Залишок '{product.name}': {product.quantity} шт.")
    except CatalogException as e:
        messages.error(request, str(e))
    return redirect('coffee_ordering:staff_products')

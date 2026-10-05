from coffee_ordering.models import Category, Product

from django.db.models import QuerySet


class CatalogException(Exception):
    """Базовий виняток для сервісу каталогу."""
    pass


class ProductNotFoundError(CatalogException):
    """Виникає, коли товар не знайдено."""
    pass


class CategoryNotFoundError(CatalogException):
    """Виникає, коли категорію не знайдено."""
    pass


class CatalogService:
    """
        Сервіс для управління вітриною товарів та категорій кав'ярні.

        Відповідає за відображення активного меню для клієнтів, пошук товарів,
        а також швидке управління наявністю та залишками товарів працівниками.
    """

    @classmethod
    def get_product_by_id(cls, product_id: int) -> Product:
        """Отримує товар за ID або викидає ProductNotFoundError."""
        try:
            return Product.objects.select_related('category').get(id=product_id)
        except Product.DoesNotExist:
            raise ProductNotFoundError(f'Товар з ID #{product_id} не знайдено.')

    @classmethod
    def get_available_products(cls, category_slug: str = None) -> 'QuerySet[Product]':
        """
            Повертає список доступних товарів (is_available=True та quantity > 0).

            Опціонально фільтрує за слагом категорії для швидкої навігації в меню.
        """
        queryset = (
            Product.objects.filter(is_available=True, quantity__gt=0)
            .select_related('category')
            .order_by('category__name', 'name')
        )
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)

        return queryset

    @classmethod
    def get_all_categories(cls) -> 'QuerySet[Category]':
        """Повертає всі категорії для побудови навігації меню."""
        return Category.objects.all().order_by('name')

    @classmethod
    def update_product_availability(cls, product_id: int, is_available: bool) -> Product:
        """Швидке включення/виключення товару для відображення в додатку"""
        product = cls.get_product_by_id(product_id)
        product.is_available = is_available
        product.save(update_fields=['is_available'])
        return product

    @classmethod
    def update_stock_quantity(cls, product_id: int, quantity: int) -> Product:
        """Оновлення залишків товару на складі працівником."""
        if quantity < 0:
            raise CatalogException('Кількість товару не може бути від`ємною.')

        product = cls.get_product_by_id(product_id)
        product.quantity = quantity

        if quantity == 0:
            product.is_available = False
            product.save(update_fields=['quantity', 'is_available'])
        else:
            product.save(update_fields=['quantity'])

        return product

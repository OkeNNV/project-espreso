from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Cart, CartItem, Category, Order, OrderItem, Product, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        'username',
        'email',
        'role',
        'status',
        'is_staff',
        'is_active',
    )
    list_filter = ('role', 'status', 'is_staff', 'is_active')
    search_fields = ('username', 'email')
    ordering = ('username',)

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Додаткові поля', {'fields': ('role', 'status')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Додаткові поля', {'fields': ('email', 'role', 'status')}),
    )


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'slug')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'name',
        'category',
        'display_price_uah',
        'is_available',
        'quantity',
    )
    list_filter = ('category', 'is_available')
    search_fields = ('name', 'description')
    list_editable = ('is_available', 'quantity')

    @admin.display(description='Ціна (грн)', ordering='price')
    def display_price_uah(self, obj):
        return f'{obj.price_uah} грн'


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('display_price_uah',)

    @admin.display(description='Ціна (грн)')
    def display_price_uah(self, obj):
        return f'{obj.price_uah} грн' if obj.pk else '-'


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'status',
        'display_total_price_uah',
        'created_at',
        'handler',
    )
    list_filter = ('status', 'created_at')
    search_fields = ('id', 'user__username', 'user__email')
    inlines = [OrderItemInline]
    readonly_fields = ('created_at', 'display_total_price_uah')

    @admin.display(description='Сума (грн)', ordering='total_price')
    def display_total_price_uah(self, obj):
        return f'{obj.total_price_uah} грн'


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ('display_cost_uah',)

    @admin.display(description='Вартість (грн)')
    def display_cost_uah(self, obj):
        return f'{obj.get_cost_uah} грн' if obj.pk else '-'


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'display_total_price_uah', 'updated_at')
    search_fields = ('user__username', 'user__email')
    inlines = [CartItemInline]
    readonly_fields = ('created_at', 'updated_at', 'display_total_price_uah')

    @admin.display(description='Сума (грн)')
    def display_total_price_uah(self, obj):
        return f'{obj.total_price_uah} грн'


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'product', 'quantity', 'display_price_uah')
    search_fields = ('order__id', 'product__name')

    @admin.display(description='Ціна (грн)', ordering='price')
    def display_price_uah(self, obj):
        return f'{obj.price_uah} грн'


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'cart', 'product', 'quantity', 'display_cost_uah')

    @admin.display(description='Вартість (грн)')
    def display_cost_uah(self, obj):
        return f'{obj.get_cost_uah} грн'

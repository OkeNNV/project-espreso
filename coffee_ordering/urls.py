from django.urls import path

from coffee_ordering import views

app_name = 'coffee_ordering'

urlpatterns = [
    # Auth
    path('register/', views.register, name='register'),
    path('activate/', views.activate, name='activate'),


    path('', views.menu, name='menu'),
    path('products/<int:product_id>/', views.product_detail, name='product_detail'),


    path('cart/', views.cart_detail, name='cart'),
    path('cart/add/<int:product_id>/', views.cart_add, name='cart_add'),
    path('cart/update/<int:product_id>/', views.cart_update, name='cart_update'),
    path('cart/remove/<int:product_id>/', views.cart_remove, name='cart_remove'),
    path('cart/clear/', views.cart_clear, name='cart_clear'),
    path('checkout/', views.checkout, name='checkout'),

    path('orders/', views.my_orders, name='my_orders'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
    path('orders/<int:order_id>/cancel/', views.order_cancel, name='order_cancel'),

    path('staff/orders/', views.active_orders, name='staff_active_orders'),
    path('staff/orders/create/', views.staff_order_create, name='staff_order_create'),
    path('staff/orders/<int:order_id>/accept/', views.staff_order_accept, name='staff_order_accept'),
    path('staff/orders/<int:order_id>/ready/', views.staff_order_ready, name='staff_order_ready'),
    path('staff/orders/<int:order_id>/complete/', views.staff_order_complete, name='staff_order_complete'),
    path('staff/orders/<int:order_id>/cancel/', views.staff_order_cancel, name='staff_order_cancel'),

    # Staff: catalog
    path('staff/products/', views.staff_products, name='staff_products'),
    path('staff/products/<int:product_id>/availability/', views.staff_product_availability,
         name='staff_product_availability'),
    path('staff/products/<int:product_id>/stock/', views.staff_product_stock, name='staff_product_stock'),
]

# project-espreso
# Espreso

A Django web application for a coffee shop: customers browse the menu, fill a cart and place orders, while staff (moderators and admins) process orders and manage the product catalog.

## Features

- User registration with email activation (account stays `PENDING` until the link from the email is opened)
- Login / logout
- Public menu with category filter and pagination
- Product detail page (unavailable or out-of-stock products are hidden from customers) w/ pagination
- Shopping cart: add, change quantity, remove, clear
- Checkout: create an order from the cart
- My orders page with current users orders
- Cancel an order while it is still `NEW`
- Roles and statuses: customer, moderator, admin; `PENDING`, `ACTIVE`, `BLOCKED`
- Staff board with active orders: accept, mark as ready, complete, cancel
- Staff product management: toggle availability, update stock quantity

## Tech Stack

- Python 3.14
- Django 6.1
- Bootstrap 5

## Getting Started

### 1. Clone the repository and activate a virtual environment

```bash
git clone <repository-url>
cd <project-folder>
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file next to `manage.py`:

```env
EMAIL_HOST_USER="your_address@gmail.com"
EMAIL_HOST_PASSWORD="your_16_char_app_password"
```

Email is configured through the `MAILERS` setting (Django 6.1) and sent via Gmail SMTP.

### 4. Apply migrations

```bash
python manage.py migrate
```

### 5. Load data

```bash
python manage.py loaddata fixtures/populate      
```

### 6. Run the development server

```bash
python manage.py runserver
```

Open http://127.0.0.1:8000/coffee_ordering/

# Superuser credentials

| Login | Password |
|-------|----------|
| admin | 123 |

## How Email Activation Works

1. A user registers and gets the status `PENDING` (`is_active = False`).
2. The app sends an email with a link: `/activate/?uid=<base64 user id>&token=<token>`.
3. Opening the link activates the account (`ACTIVE`, `is_active = True`).

## Roles and Access

| Role | Access |
|------|--------|
| Anonymous | Menu, product pages, registration, login |
| Customer (`ACTIVE`) | Cart, checkout, own orders |
| Moderator | Everything above + active orders board, product management |
| Admin | Everything above + Django admin |

Users with the status `PENDING` or `BLOCKED` cannot use the cart or orders.

## Main Pages

| Page | Route name | Access |
|------|------------|--------|
| Menu (`?category=<slug>`, `?page=<n>`) | `coffee_ordering:menu` | Public |
| Product detail | `coffee_ordering/product_detail` | Public |
| Registration | `coffee_ordering/register` | Anonymous |
| Email activation | `coffee_ordering/activate` | Public |
| Cart | `coffee_ordering/cart` | Active user |
| My orders | `coffee_ordering/my_orders` | Active user |
| Order detail | `coffee_ordering/order_detail` | Owner / staff |
| Active orders board | `coffee_ordering/staff_active_orders` | Staff |
| Product management | `coffee_ordering/staff_products` | Staff |


Business logic lives in service classes (`CartService`, `CatalogService`, `OrderService`, `UserService`),
so views stay thin and only handle HTTP.

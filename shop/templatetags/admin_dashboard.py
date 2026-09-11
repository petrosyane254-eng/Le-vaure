from datetime import timedelta

from django import template
from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.utils import timezone

from shop.models import (
    Product,
    Order,
    Wishlist,
)

register = template.Library()

User = get_user_model()


@register.simple_tag
def southward_admin_stats():

    today = timezone.localdate()

    today_orders = Order.objects.filter(
        created_at__date=today,
    )

    total_revenue = (
        Order.objects.exclude(
            status="cancelled",
        ).aggregate(
            total=Sum("total"),
        )["total"]
        or 0
    )

    today_revenue = (
        today_orders.exclude(
            status="cancelled",
        ).aggregate(
            total=Sum("total"),
        )["total"]
        or 0
    )

    return {

        "orders_today":
            today_orders.count(),

        "today_revenue":
            today_revenue,

        "total_revenue":
            total_revenue,

        "pending_orders":
            Order.objects.filter(
                status__in=[
                    "new",
                    "paid",
                    "processing",
                ]
            ).count(),

        "low_stock":
            Product.objects.filter(
                active=True,
                stock__gt=0,
                stock__lte=5,
            ).count(),

        "out_of_stock":
            Product.objects.filter(
                active=True,
                stock=0,
            ).count(),

        "products":
            Product.objects.count(),

        "active_products":
            Product.objects.filter(
                active=True,
            ).count(),

        "customers":
            User.objects.filter(
                is_staff=False,
            ).count(),

        "wishlist_items":
            Wishlist.objects.count(),
    }


@register.simple_tag
def southward_recent_orders():

    return (
        Order.objects
        .select_related("user")
        .order_by("-created_at")[:7]
    )


@register.simple_tag
def southward_low_stock_products():

    return (
        Product.objects
        .filter(
            active=True,
            stock__lte=5,
        )
        .select_related("category")
        .order_by("stock", "name")[:7]
    )
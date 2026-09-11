import stripe
import resend

from decimal import Decimal
import logging
import secrets
import requests

from datetime import datetime, timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from .forms import RegistrationForm
from .models import (
    Category,
    Product,
    Order,
    OrderItem,
    Wishlist,
    SiteAccessSettings,
    PrintifyProduct,
    PrintifyProductImage,
    PrintifyVariant,
    PrintifyOrderItem,
)


logger = logging.getLogger(__name__)


def _new_verification_code():
    return f"{secrets.randbelow(1_000_000):06d}"


def _safe_int(value, default=0, minimum=None):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default

    if minimum is not None:
        return max(minimum, parsed)

    return parsed


# =========================================================
# CART HELPERS
# =========================================================

def _printify_cart_data(request):
    cart_data = request.session.get("printify_cart", {})
    return cart_data if isinstance(cart_data, dict) else {}


def _build_cart_items(request):
    items = []
    total = Decimal("0.00")

    # -----------------------------------------------------
    # LOCAL PRODUCTS
    # -----------------------------------------------------

    cart_data = request.session.get(
        "cart",
        {},
    )

    local_products = (
        Product.objects
        .filter(
            pk__in=cart_data.keys(),
            active=True,
        )
        .select_related("category")
    )

    for product_item in local_products:
        quantity = _safe_int(
            cart_data.get(
                str(product_item.pk),
                0,
            ),
            default=0,
            minimum=0,
        )

        quantity = min(
            quantity,
            product_item.stock,
        )

        if quantity <= 0:
            continue

        subtotal = (
            product_item.price
            * quantity
        )

        items.append(
            {
                "source": "local",
                "product": product_item,
                "variant": None,
                "title": product_item.name,
                "variant_title": "",
                "image": (
                    product_item.image.url
                    if product_item.image
                    else ""
                ),
                "url": reverse(
                    "product",
                    args=[product_item.slug],
                ),
                "quantity": quantity,
                "max_quantity": product_item.stock,
                "unit_price": product_item.price,
                "subtotal": subtotal,
                "update_url": reverse(
                    "update_cart",
                    args=[product_item.pk],
                ),
            }
        )

        total += subtotal

    return items, total


def _cart_json_payload(
    request,
    product_item=None,
):
    items, cart_total = _build_cart_items(
        request
    )

    cart_count = sum(
        item["quantity"]
        for item in items
    )

    payload = {
        "ok": True,
        "cart_count": cart_count,
        "cart_total": f"{cart_total:.2f}",
    }

    if product_item is not None:
        cart_data = request.session.get(
            "cart",
            {},
        )

        quantity = cart_data.get(
            str(product_item.pk),
            0,
        )

        payload["product"] = {
            "id": product_item.pk,
            "name": product_item.name,
            "price": f"{product_item.price:.2f}",
            "quantity": quantity,
            "stock": product_item.stock,
            "image": (
                product_item.image.url
                if product_item.image
                else ""
            ),
            "category": (
                product_item.category.name
                if product_item.category
                else "LE VAURÉ"
            ),
            "update_url": reverse(
                "update_cart",
                args=[product_item.pk],
            ),
            "product_url": reverse(
                "product",
                args=[product_item.slug],
            ),
        }

    return payload


# =========================================================
# VERIFICATION HELPERS
# =========================================================

def _verification_minutes():
    return getattr(
        settings,
        "SOUTHWARD_VERIFICATION_MINUTES",
        getattr(
            settings,
            "SCORPION_VERIFICATION_MINUTES",
            10
        ),
    )


def _pending_registration_key():
    return "pending_registration"


def _send_verification_email(
    recipient_email,
    code,
    username=""
):
    """
    Send account verification email through Django's configured email backend.

    With the project's SMTP settings, this sends from the Gmail account configured
    by EMAIL_HOST_USER / DEFAULT_FROM_EMAIL instead of using Resend.
    """
    recipient_email = (recipient_email or "").strip().lower()
    username = (username or "").strip()

    if not recipient_email:
        raise ValueError("User has no email address.")

    minutes = _verification_minutes()

    html_message = render_to_string(
        "emails/verification_email.html",
        {
            "username": username,
            "email": recipient_email,
            "code": code,
            "minutes": minutes,
            "logo_cid": "",
        },
    )

    text_message = (
        "LE VAURÉ\n\n"
        f"Welcome, {username or 'LE VAURÉ member'}.\n\n"
        f"Your email verification code is: {code}\n\n"
        f"This code expires in {minutes} minutes.\n\n"
        "If you did not create a LE VAURÉ account, "
        "you can safely ignore this email."
    )

    from_email = (
        getattr(settings, "DEFAULT_FROM_EMAIL", "")
        or getattr(settings, "EMAIL_HOST_USER", "")
    ).strip()

    if not from_email:
        raise RuntimeError(
            "DEFAULT_FROM_EMAIL / EMAIL_HOST_USER is not configured."
        )

    email_message = EmailMultiAlternatives(
        subject="Your LE VAURÉ verification code",
        body=text_message,
        from_email=from_email,
        to=[recipient_email],
    )
    email_message.attach_alternative(html_message, "text/html")

    sent_count = email_message.send(fail_silently=False)

    if sent_count != 1:
        raise RuntimeError(
            f"Verification email was not sent. Django returned {sent_count}."
        )

    logger.info(
        "LE VAURÉ verification email sent via Django email backend. recipient=%s",
        recipient_email,
    )

    return sent_count

def _send_order_confirmation_email(order):
    if not settings.RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY is not configured.")

    order_number = f"LV-{order.pk:06d}"
    order_items = order.items.select_related("product").all()

    html_message = render_to_string(
        "emails/order_confirmation_email.html",
        {
            "order": order,
            "order_number": order_number,
            "items": order_items,
            "logo_cid": "",
        },
    )

    item_lines = [
        f"- {item.product.name} x {item.quantity} ({item.subtotal})"
        for item in order_items
    ]

    text_message = (
        "LE VAURÉ\n\n"
        f"Thank you for your order, {order.full_name}.\n\n"
        f"Order number: {order_number}\n"
        f"Total: {order.total}\n\n"
        "Items:\n"
        + "\n".join(item_lines)
        + "\n\n"
        "We received your order successfully and we are preparing it now.\n\n"
        "LE VAURÉ\n"
        "MOVE YOUR OWN WAY."
    )

    resend.api_key = settings.RESEND_API_KEY

    response = resend.Emails.send(
        {
            "from": settings.RESEND_FROM_EMAIL,
            "to": [order.email],
            "subject": f"LE VAURÉ Order Confirmation - {order_number}",
            "html": html_message,
            "text": text_message,
        }
    )

    if not response:
        raise RuntimeError("Resend did not return a response.")

    return response


def _send_order_notification_email(order):
    notification_email = getattr(
        settings,
        "CEO_ORDER_NOTIFICATION_EMAIL",
        "",
    ).strip()

    if not notification_email:
        return 0

    if not settings.RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY is not configured.")

    order_number = f"LV-{order.pk:06d}"
    order_items = order.items.select_related("product").all()

    html_message = render_to_string(
        "emails/order_notification_email.html",
        {
            "order": order,
            "order_number": order_number,
            "items": order_items,
            "logo_cid": "",
        },
    )

    text_lines = [
        "LE VAURÉ NEW ORDER ALERT",
        "",
        f"Customer: {order.full_name}",
        f"Order number: {order_number}",
        f"Total: {order.total}",
        "",
        "Items:",
    ]
    text_lines.extend(
        f"- {item.product.name} x {item.quantity}"
        for item in order_items
    )

    resend.api_key = settings.RESEND_API_KEY

    response = resend.Emails.send(
        {
            "from": settings.RESEND_FROM_EMAIL,
            "to": [notification_email],
            "subject": f"New Order Received - {order_number}",
            "html": html_message,
            "text": "\n".join(text_lines),
        }
    )

    if not response:
        raise RuntimeError("Resend did not return a response.")

    return response


def _store_pending_registration(
    request,
    form
):
    code = _new_verification_code()

    minutes = _verification_minutes()

    now = timezone.now()

    pending = {
        "username": (
            form.cleaned_data["username"]
            .strip()
        ),
        "email": (
            form.cleaned_data["email"]
            .strip()
            .lower()
        ),
        "password": (
            form.cleaned_data["password1"]
        ),
        "code_hash": make_password(code),
        "expires_at": (
            now
            + timedelta(minutes=minutes)
        ).isoformat(),
        "attempts": 0,
        "last_sent_at": now.isoformat(),
    }

    request.session[
        _pending_registration_key()
    ] = pending

    request.session.modified = True

    _send_verification_email(
        pending["email"],
        code,
        pending["username"],
    )


def _get_pending_registration(request):
    return request.session.get(
        _pending_registration_key()
    )


def _parse_iso_datetime(value):
    parsed = datetime.fromisoformat(value)

    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(
            parsed,
            timezone.get_current_timezone()
        )

    return parsed


def _store_pending_verification(
    request,
    pending,
    code
):
    now = timezone.now()

    pending["code_hash"] = (
        make_password(code)
    )

    pending["expires_at"] = (
        now
        + timedelta(
            minutes=_verification_minutes()
        )
    ).isoformat()

    pending["attempts"] = 0

    pending["last_sent_at"] = (
        now.isoformat()
    )

    request.session[
        _pending_registration_key()
    ] = pending

    request.session.modified = True


# =========================================================
# SITE ACCESS / PRIVATE SHOP
# =========================================================

def site_access(request):
    site_settings = SiteAccessSettings.objects.first()

    # If no settings row exists, do not accidentally lock the site.
    if site_settings is None:
        return redirect("home")

    # If private mode has been disabled from Admin, go to the shop.
    if not site_settings.maintenance_mode:
        return redirect("home")

    # The session is valid only for the currently configured password hash.
    # Changing the password in Admin automatically invalidates old sessions.
    if (
        request.session.get("southward_site_access_granted_for")
        == site_settings.access_password
    ):
        return redirect("home")

    error = ""

    if request.method == "POST":
        entered_password = request.POST.get(
            "password",
            "",
        )

        if site_settings.check_access_password(entered_password):
            request.session["southward_site_access_granted_for"] = (
                site_settings.access_password
            )

            # Remove the old boolean-style session key if it exists.
            request.session.pop(
                "southward_site_access_granted",
                None,
            )

            request.session.modified = True
            return redirect("home")

        error = "Incorrect password."

    response = render(
        request,
        "shop/site_access.html",
        {
            "error": error,
        },
    )

    # Keep the private-development gate out of search-engine indexes
    # and prevent the password page from being cached.
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response["Cache-Control"] = "no-store"
    return response


# =========================================================
# HOME
# =========================================================

def home(request):
    products = []

    # =====================================================
    # LOCAL PRODUCTS
    # =====================================================

    local_products = (
        Product.objects
        .filter(
            active=True,
            featured=True,
        )
        .select_related("category")
        .order_by("-created_at")
    )

    for item in local_products:
        products.append(
            {
                "source": "local",
                "id": item.pk,
                "pk": item.pk,
                "name": item.name,
                "title": item.name,
                "price": item.price,
                "image": (
                    item.image.url
                    if item.image
                    else ""
                ),
                "url": reverse(
                    "product",
                    args=[item.slug],
                ),
                "stock": item.stock,
                "category": (
                    item.category.name
                    if item.category
                    else "LE VAURÉ"
                ),
                "featured": item.featured,
                "created_at": item.created_at,
            }
        )

    # =====================================================
    # PRINTIFY API — OPTIONAL IMAGE FALLBACK
    # =====================================================
    # Important:
    # Printify products are NOT dependent on a live API response.
    # They are always loaded from the local database first.
    # API data is used only as a fallback for image URLs.

    api_products_by_id = {}

    # =====================================================
    # PRINTIFY PRODUCTS — DATABASE IS SOURCE OF DISPLAY
    # =====================================================

    # =====================================================
    # SORT + LIMIT
    # =====================================================

    products.sort(
        key=lambda item: item["created_at"],
        reverse=True,
    )

    products = products[:8]

    # =====================================================
    # WISHLIST
    # =====================================================

    wishlist_product_ids = set()

    if request.user.is_authenticated:
        wishlist_product_ids = set(
            Wishlist.objects.filter(
                user=request.user
            ).values_list(
                "product_id",
                flat=True,
            )
        )

    return render(
        request,
        "shop/home.html",
        {
            "products": products,
            "wishlist_product_ids":
                wishlist_product_ids,
        },
    )


# =========================================================
# SHOP
# =========================================================

def shop(request):
    """
    Main LE VAURÉ shop page.

    Local and Printify products are normalized into one plain Python list.
    This keeps the original shop template/design while avoiding QuerySet.sort()
    errors and lets both product sources appear together.
    """
    products = []

    q = request.GET.get("q", "").strip()
    sort = request.GET.get("sort", "featured").strip()
    selected_category = request.GET.get("category", "").strip()

    # =====================================================
    # LOCAL PRODUCTS
    # =====================================================
    local_products = (
        Product.objects
        .filter(active=True)
        .select_related("category")
        .order_by("-featured", "-created_at")
    )

    if selected_category:
        local_products = local_products.filter(
            category__slug=selected_category
        )

    for item in local_products:
        products.append(
            {
                "source": "local",
                "id": item.pk,
                "pk": item.pk,
                "title": item.name,
                "name": item.name,
                "slug": item.slug,
                "description": item.description or "",
                "price": item.price,
                "image": item.image.url if item.image else "",
                "stock": item.stock,
                "featured": item.featured,
                "category": (
                    item.category.name
                    if item.category
                    else "LE VAURÉ"
                ),
                "category_slug": (
                    item.category.slug
                    if item.category
                    else ""
                ),
                "url": reverse(
                    "product",
                    args=[item.slug],
                ),
                "variants": [],
            }
        )

    # =====================================================
    # PRINTIFY PRODUCTS
    # =====================================================
    # Printify products do not currently have a Category FK in the model.
    # Therefore they are included in the main/all-products view, but not
    # injected into a specific local category filter where they could be
    # incorrectly categorized.
    # =====================================================
    # SEARCH
    # =====================================================
    if q:
        query = q.casefold()

        products = [
            item
            for item in products
            if (
                query in item["title"].casefold()
                or query in (
                    item.get("description")
                    or ""
                ).casefold()
                or query in (
                    item.get("category")
                    or ""
                ).casefold()
            )
        ]

    # =====================================================
    # SORT
    # =====================================================
    # Be explicit: products MUST be a normal list before using .sort().
    products = list(products)

    if sort == "price_low":
        products.sort(
            key=lambda item: item["price"]
        )

    elif sort == "price_high":
        products.sort(
            key=lambda item: item["price"],
            reverse=True,
        )

    elif sort == "name":
        products.sort(
            key=lambda item: item["title"].casefold()
        )

    else:
        products.sort(
            key=lambda item: bool(
                item.get("featured")
            ),
            reverse=True,
        )

    # =====================================================
    # WISHLIST IDS
    # =====================================================
    wishlist_product_ids = set()

    if request.user.is_authenticated:
        wishlist_product_ids = set(
            Wishlist.objects.filter(
                user=request.user
            ).values_list(
                "product_id",
                flat=True,
            )
        )

    # =====================================================
    # CATEGORIES
    # =====================================================
    categories = Category.objects.all().order_by("name")

    # =====================================================
    # RENDER ORIGINAL SHOP DESIGN
    # =====================================================
    return render(
        request,
        "shop/shop.html",
        {
            "products": products,
            "categories": categories,
            "selected_category": selected_category,
            "wishlist_product_ids": wishlist_product_ids,
            "q": q,
            "sort": sort,
        },
    )


# =========================================================
# PRODUCT
# =========================================================

def product(request, slug):
    item = get_object_or_404(
        Product,
        slug=slug,
        active=True
    )

    is_wishlisted = False

    if request.user.is_authenticated:
        is_wishlisted = (
            Wishlist.objects.filter(
                user=request.user,
                product=item,
            ).exists()
        )

    return render(
        request,
        "shop/product.html",
        {
            "product": item,
            "is_wishlisted": is_wishlisted,
        },
    )


# =========================================================
# PRINTIFY PRODUCT DETAIL
# =========================================================



# =========================================================
# PRINTIFY PRODUCT DETAIL
# =========================================================

def printify_product(
    request,
    printify_id,
):
    item = get_object_or_404(
        PrintifyProduct,
        printify_id=printify_id,
        active=True,
    )

    images = (
        item.images
        .order_by(
            "-is_primary",
            "sort_order",
            "id",
        )
    )

    variants = (
        item.variants
        .filter(enabled=True)
        .order_by(
            "price",
            "title",
        )
    )

    available_variants = (
        variants
        .filter(available=True)
        .count()
    )

    is_wishlisted = False

    if request.user.is_authenticated:
        is_wishlisted = (
            Wishlist.objects.filter(
                user=request.user,
                printify_product=item,
            ).exists()
        )

    return render(
        request,
        "shop/printify_product.html",
        {
            "product": item,
            "images": images,
            "variants": variants,
            "available_variants": available_variants,
            "is_wishlisted": is_wishlisted,
        },
    )


# =========================================================
# ADD TO CART
# =========================================================

@require_POST
def add_cart(request, pk):
    product_item = get_object_or_404(
        Product,
        pk=pk,
        active=True
    )

    if product_item.stock <= 0:
        if (
            request.headers.get(
                "x-requested-with"
            )
            == "XMLHttpRequest"
        ):
            return JsonResponse(
                {
                    "ok": False,
                    "message":
                        "Product is out of stock."
                },
                status=400
            )

        messages.warning(
            request,
            "Product is out of stock."
        )

        return redirect(
            request.META.get(
                "HTTP_REFERER",
                "/shop/"
            )
        )

    cart_data = request.session.get(
        "cart",
        {}
    )

    key = str(pk)

    quantity = _safe_int(
        request.POST.get(
            "quantity",
            1
        ),
        default=1,
        minimum=1
    )

    current_quantity = (
        cart_data.get(key, 0)
    )

    cart_data[key] = min(
        current_quantity + quantity,
        product_item.stock
    )

    request.session["cart"] = (
        cart_data
    )

    request.session.modified = True

    if (
        request.headers.get(
            "x-requested-with"
        )
        == "XMLHttpRequest"
    ):
        return JsonResponse(
            _cart_json_payload(
                request,
                product_item
            )
        )

    messages.success(
        request,
        f"{product_item.name} added to cart."
    )

    return redirect(
        request.META.get(
            "HTTP_REFERER",
            "/shop/"
        )
    )


# =========================================================
# ADD PRINTIFY PRODUCT TO CART
# =========================================================

@require_POST
def add_printify_cart(
    request,
    printify_id,
):
    product_item = get_object_or_404(
        PrintifyProduct,
        printify_id=printify_id,
        active=True,
    )

    variant_id = _safe_int(
        request.POST.get(
            "variant_id",
            0,
        ),
        default=0,
        minimum=0,
    )

    quantity = _safe_int(
        request.POST.get(
            "quantity",
            1,
        ),
        default=1,
        minimum=1,
    )

    quantity = min(
        quantity,
        99,
    )

    variant = (
        product_item.variants
        .filter(
            printify_variant_id=variant_id,
            enabled=True,
            available=True,
        )
        .first()
    )

    if variant is None:
        messages.error(
            request,
            "Please select an available size / color.",
        )

        return redirect(
            "printify_product",
            printify_id=printify_id,
        )

    cart_data = _printify_cart_data(
        request
    )

    key = str(
        variant.printify_variant_id
    )

    current_quantity = _safe_int(
        cart_data.get(
            key,
            0,
        ),
        default=0,
        minimum=0,
    )

    cart_data[key] = min(
        current_quantity + quantity,
        99,
    )

    request.session["printify_cart"] = (
        cart_data
    )

    request.session.modified = True

    if request.POST.get("buy_now"):
        return redirect("checkout")

    messages.success(
        request,
        (
            f"{product_item.title} / "
            f"{variant.title} added to cart."
        ),
    )

    return redirect("cart")


# =========================================================
# CART
# =========================================================

def cart(request):
    items, total = _build_cart_items(
        request
    )

    return render(
        request,
        "shop/cart.html",
        {
            "items": items,
            "total": total,
        },
    )


# =========================================================
# UPDATE CART
# =========================================================

@require_POST
def update_cart(request, pk):
    product_item = get_object_or_404(
        Product,
        pk=pk,
        active=True
    )

    cart_data = request.session.get(
        "cart",
        {}
    )

    quantity = _safe_int(
        request.POST.get(
            "quantity",
            0
        ),
        default=0,
        minimum=0
    )

    key = str(pk)

    if quantity <= 0:
        cart_data.pop(
            key,
            None
        )

    elif product_item.stock <= 0:
        cart_data.pop(
            key,
            None
        )

        if (
            request.headers.get(
                "x-requested-with"
            )
            != "XMLHttpRequest"
        ):
            messages.warning(
                request,
                (
                    f"{product_item.name} "
                    "is out of stock."
                )
            )

    else:
        cart_data[key] = min(
            quantity,
            product_item.stock
        )

    request.session["cart"] = (
        cart_data
    )

    request.session.modified = True

    if (
        request.headers.get(
            "x-requested-with"
        )
        == "XMLHttpRequest"
    ):
        return JsonResponse(
            _cart_json_payload(
                request,
                product_item
            )
        )

    return redirect("cart")


# =========================================================
# UPDATE PRINTIFY CART
# =========================================================

@require_POST
def update_printify_cart(
    request,
    variant_id,
):
    variant = get_object_or_404(
        PrintifyVariant,
        printify_variant_id=variant_id,
        product__active=True,
        enabled=True,
    )

    cart_data = _printify_cart_data(
        request
    )

    key = str(
        variant.printify_variant_id
    )

    quantity = _safe_int(
        request.POST.get(
            "quantity",
            0,
        ),
        default=0,
        minimum=0,
    )

    if (
        quantity <= 0
        or not variant.available
    ):
        cart_data.pop(
            key,
            None,
        )
    else:
        cart_data[key] = min(
            quantity,
            99,
        )

    request.session["printify_cart"] = (
        cart_data
    )

    request.session.modified = True

    return redirect("cart")


# =========================================================
# STRIPE PAYMENT HELPERS
# =========================================================

def _send_paid_order_emails(order):
    customer_sent = False
    ceo_sent = False

    try:
        response = _send_order_confirmation_email(order)
        customer_sent = bool(response)
        logger.info(
            "LE VAURÉ customer order confirmation sent. order=%s email=%s",
            order.pk,
            order.email,
        )
    except Exception:
        logger.exception(
            "LE VAURÉ customer order confirmation could not be sent. order=%s",
            order.pk,
        )

    try:
        response = _send_order_notification_email(order)
        ceo_sent = bool(response)

        if response:
            logger.info(
                "LE VAURÉ CEO order notification sent. order=%s",
                order.pk,
            )
        else:
            logger.warning(
                "LE VAURÉ CEO order notification skipped because "
                "CEO_ORDER_NOTIFICATION_EMAIL is empty. order=%s",
                order.pk,
            )
    except Exception:
        logger.exception(
            "LE VAURÉ CEO order notification could not be sent. order=%s",
            order.pk,
        )

    return customer_sent, ceo_sent


def _finalize_stripe_payment(
    order,
    checkout_session,
):
    """
    Mark an order as paid exactly once.

    This function is intentionally idempotent so both the Stripe webhook
    and the success-page verification can safely call it without reducing
    stock twice or sending duplicate emails.
    """
    payment_status = getattr(
        checkout_session,
        "payment_status",
        "",
    )

    if payment_status != "paid":
        return order, False

    payment_intent_id = (
        getattr(
            checkout_session,
            "payment_intent",
            "",
        )
        or ""
    )

    order_was_paid_now = False

    with transaction.atomic():
        locked_order = (
            Order.objects
            .select_for_update()
            .get(pk=order.pk)
        )

        if locked_order.status == "paid":
            return locked_order, False

        order_items = list(
            locked_order.items
            .select_related("product")
            .all()
        )

        for order_item in order_items:
            product_item = (
                Product.objects
                .select_for_update()
                .get(pk=order_item.product_id)
            )

            if product_item.stock < order_item.quantity:
                logger.warning(
                    "Insufficient stock while finalizing "
                    "Stripe payment for order %s, product %s. "
                    "Available=%s, ordered=%s",
                    locked_order.pk,
                    product_item.pk,
                    product_item.stock,
                    order_item.quantity,
                )

            product_item.stock = max(
                0,
                product_item.stock
                - order_item.quantity
            )

            product_item.save(
                update_fields=["stock"]
            )

        locked_order.status = "paid"
        locked_order.payment_method = "stripe"
        locked_order.stripe_payment_intent_id = (
            str(payment_intent_id)
        )
        locked_order.paid_at = timezone.now()

        locked_order.save(
            update_fields=[
                "status",
                "payment_method",
                "stripe_payment_intent_id",
                "paid_at",
            ]
        )

        order_was_paid_now = True

    if order_was_paid_now:
        _send_paid_order_emails(locked_order)

    return locked_order, order_was_paid_now


def _split_customer_name(full_name):
    parts = (
        full_name
        or ""
    ).strip().split()

    if not parts:
        return "", ""

    first_name = parts[0]

    last_name = (
        " ".join(parts[1:])
        if len(parts) > 1
        else "-"
    )

    return first_name, last_name


def _printify_headers():
    api_token = getattr(
        settings,
        "PRINTIFY_API_TOKEN",
        "",
    ).strip()

    if not api_token:
        raise RuntimeError(
            "PRINTIFY_API_TOKEN is not configured."
        )

    return {
        "Authorization":
            f"Bearer {api_token}",
        "Content-Type":
            "application/json;charset=utf-8",
    }


def _printify_address_payload(
    full_name,
    email,
    phone,
    country,
    region,
    street,
    apartment,
    city,
    postal_code,
):
    first_name, last_name = (
        _split_customer_name(
            full_name
        )
    )

    return {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone": phone or "",
        "country": country,
        "region": region or "",
        "address1": street,
        "address2": apartment or "",
        "city": city,
        "zip": postal_code,
    }


def _printify_shipping_quote(
    printify_items,
    address_to,
):
    if not printify_items:
        return Decimal("0.00")

    line_items = []

    for item in printify_items:
        line_items.append(
            {
                "product_id":
                    item["product"].printify_id,
                "variant_id":
                    item["variant"].printify_variant_id,
                "quantity":
                    item["quantity"],
            }
        )

    url = (
        "https://api.printify.com/v1/shops/"
        f"{PRINTIFY_SHOP_ID}/orders/shipping.json"
    )

    response = requests.post(
        url,
        headers=_printify_headers(),
        json={
            "line_items": line_items,
            "address_to": address_to,
        },
        timeout=20,
    )

    response.raise_for_status()

    data = response.json()

    standard_cents = data.get(
        "standard"
    )

    if standard_cents is None:
        raise RuntimeError(
            "Printify did not return a standard shipping rate."
        )

    return (
        Decimal(
            str(standard_cents)
        )
        / Decimal("100")
    )


def _ensure_printify_order(order):
    """
    Submit paid Printify items exactly once.

    Safe to call from both Stripe success verification and the webhook.
    """
    order = (
        Order.objects
        .prefetch_related(
            "printify_items__product",
            "printify_items__variant",
        )
        .get(pk=order.pk)
    )

    printify_items = list(
        order.printify_items.all()
    )

    if not printify_items:
        return True

    if order.printify_order_id:
        return True

    if order.status != "paid":
        return False

    address_to = (
        _printify_address_payload(
            order.full_name,
            order.email,
            order.phone,
            order.country,
            order.region,
            order.street,
            order.apartment,
            order.city,
            order.postal_code,
        )
    )

    line_items = []

    for index, item in enumerate(
        printify_items,
        start=1,
    ):
        line_items.append(
            {
                "product_id":
                    item.product.printify_id,
                "variant_id":
                    item.variant.printify_variant_id,
                "quantity":
                    item.quantity,
                "external_id":
                    (
                        f"SW-{order.pk:06d}-"
                        f"P{index}"
                    ),
            }
        )

    payload = {
        "external_id":
            f"LV-{order.pk:06d}",
        "label":
            f"LV-{order.pk:06d}",
        "line_items": line_items,
        "shipping_method": 1,
        "is_printify_express": False,
        "is_economy_shipping": False,
        "send_shipping_notification": False,
        "address_to": address_to,
    }

    url = (
        "https://api.printify.com/v1/shops/"
        f"{PRINTIFY_SHOP_ID}/orders.json"
    )

    try:
        response = requests.post(
            url,
            headers=_printify_headers(),
            json=payload,
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        printify_order_id = str(
            data.get(
                "id",
                "",
            )
        ).strip()

        if not printify_order_id:
            raise RuntimeError(
                "Printify order response has no order id."
            )

        order.printify_order_id = (
            printify_order_id
        )

        order.printify_status = str(
            data.get(
                "status",
                "created",
            )
        )

        order.printify_submitted_at = (
            timezone.now()
        )

        order.printify_error = ""

        order.save(
            update_fields=[
                "printify_order_id",
                "printify_status",
                "printify_submitted_at",
                "printify_error",
            ]
        )

        auto_send = bool(
            getattr(
                settings,
                "PRINTIFY_AUTO_SEND_TO_PRODUCTION",
                False,
            )
        )

        if auto_send:
            production_url = (
                "https://api.printify.com/v1/shops/"
                f"{PRINTIFY_SHOP_ID}/orders/"
                f"{printify_order_id}/"
                "send_to_production.json"
            )

            production_response = requests.post(
                production_url,
                headers=_printify_headers(),
                json={},
                timeout=20,
            )

            production_response.raise_for_status()

            order.printify_status = (
                "sent_to_production"
            )

            order.save(
                update_fields=[
                    "printify_status"
                ]
            )

        return True

    except Exception as exc:
        logger.exception(
            "Printify order submission failed for LE VAURÉ order %s.",
            order.pk,
        )

        order.printify_error = str(
            exc
        )[:2000]

        order.save(
            update_fields=[
                "printify_error"
            ]
        )

        return False


# =========================================================
# CHECKOUT
# =========================================================

def checkout(request):
    items, subtotal = _build_cart_items(
        request
    )

    if not items:
        messages.warning(
            request,
            "Your cart is empty.",
        )

        return redirect("shop")

    if request.method == "POST":
        full_name = request.POST.get(
            "full_name",
            "",
        ).strip()

        email = request.POST.get(
            "email",
            "",
        ).strip()

        phone = request.POST.get(
            "phone",
            "",
        ).strip()

        country = request.POST.get(
            "country",
            "",
        ).strip().upper()

        region = request.POST.get(
            "region",
            "",
        ).strip()

        street = request.POST.get(
            "street",
            "",
        ).strip()

        apartment = request.POST.get(
            "apartment",
            "",
        ).strip()

        city = request.POST.get(
            "city",
            "",
        ).strip()

        postal_code = request.POST.get(
            "postal_code",
            "",
        ).strip()

        delivery_notes = request.POST.get(
            "delivery_notes",
            "",
        ).strip()

        if (
            not full_name
            or not email
            or not country
            or not street
            or not city
            or not postal_code
        ):
            messages.error(
                request,
                "Please fill all required shipping fields.",
            )

            return render(
                request,
                "shop/checkout.html",
                {
                    "items": items,
                    "subtotal": subtotal,
                    "shipping_total":
                        Decimal("0.00"),
                    "total": subtotal,
                },
            )

        if len(country) != 2:
            messages.error(
                request,
                "Please select a valid country.",
            )

            return redirect("checkout")

        address_to = (
            _printify_address_payload(
                full_name,
                email,
                phone,
                country,
                region,
                street,
                apartment,
                city,
                postal_code,
            )
        )

        printify_items = [
            item
            for item in items
            if item["source"] == "printify"
        ]

        shipping_total = Decimal(
            "0.00"
        )

        if printify_items:
            try:
                shipping_total = (
                    _printify_shipping_quote(
                        printify_items,
                        address_to,
                    )
                )

            except Exception as exc:
                logger.exception(
                    "Printify shipping quote failed."
                )

                messages.error(
                    request,
                    (
                        "Could not calculate Printify shipping "
                        "for this address. "
                        f"{exc if settings.DEBUG else ''}"
                    ).strip(),
                )

                return render(
                    request,
                    "shop/checkout.html",
                    {
                        "items": items,
                        "subtotal": subtotal,
                        "shipping_total":
                            Decimal("0.00"),
                        "total": subtotal,
                    },
                )

        total = (
            subtotal
            + shipping_total
        )

        stripe_secret_key = getattr(
            settings,
            "STRIPE_SECRET_KEY",
            "",
        ).strip()

        if not stripe_secret_key:
            logger.error(
                "STRIPE_SECRET_KEY is not configured."
            )

            messages.error(
                request,
                "Payment service is not configured.",
            )

            return redirect("checkout")

        stripe.api_key = (
            stripe_secret_key
        )

        address_text_parts = [
            street,
            apartment,
            city,
            postal_code,
            country,
        ]

        address = ", ".join(
            part
            for part in address_text_parts
            if part
        )

        with transaction.atomic():
            order = Order.objects.create(
                user=(
                    request.user
                    if request.user.is_authenticated
                    else None
                ),
                full_name=full_name,
                email=email,
                phone=phone,
                country=country,
                region=region,
                street=street,
                apartment=apartment,
                city=city,
                postal_code=postal_code,
                delivery_notes=delivery_notes,
                address=address,
                shipping_total=shipping_total,
                total=total,
                status="new",
                payment_method="stripe",
            )

            for item in items:
                if item["source"] == "local":
                    OrderItem.objects.create(
                        order=order,
                        product=item["product"],
                        quantity=item["quantity"],
                        price=item["unit_price"],
                    )
                else:
                    PrintifyOrderItem.objects.create(
                        order=order,
                        product=item["product"],
                        variant=item["variant"],
                        quantity=item["quantity"],
                        price=item["unit_price"],
                    )

        stripe_line_items = []

        for item in items:
            product_name = item["title"]

            if item["variant_title"]:
                product_name += (
                    " / "
                    + item["variant_title"]
                )

            unit_amount = int(
                (
                    item["unit_price"]
                    * Decimal("100")
                ).quantize(
                    Decimal("1")
                )
            )

            stripe_line_items.append(
                {
                    "price_data": {
                        "currency": "eur",
                        "product_data": {
                            "name": product_name,
                        },
                        "unit_amount":
                            unit_amount,
                    },
                    "quantity":
                        item["quantity"],
                }
            )

        if shipping_total > 0:
            shipping_amount = int(
                (
                    shipping_total
                    * Decimal("100")
                ).quantize(
                    Decimal("1")
                )
            )

            stripe_line_items.append(
                {
                    "price_data": {
                        "currency": "eur",
                        "product_data": {
                            "name":
                                "Printify standard shipping",
                        },
                        "unit_amount":
                            shipping_amount,
                    },
                    "quantity": 1,
                }
            )

        try:
            checkout_session = (
                stripe.checkout.Session.create(
                    mode="payment",
                    line_items=stripe_line_items,
                    customer_email=email,
                    client_reference_id=str(
                        order.pk
                    ),
                    metadata={
                        "order_id":
                            str(order.pk),
                    },
                    success_url=(
                        request.build_absolute_uri(
                            reverse(
                                "stripe_success"
                            )
                        )
                        + "?session_id="
                        "{CHECKOUT_SESSION_ID}"
                    ),
                    cancel_url=(
                        request.build_absolute_uri(
                            reverse(
                                "stripe_cancel"
                            )
                        )
                        + f"?order_id={order.pk}"
                    ),
                )
            )

        except Exception as exc:
            logger.exception(
                "Stripe Checkout Session could not be created."
            )

            order.delete()

            if settings.DEBUG:
                messages.error(
                    request,
                    f"Stripe error: {exc}",
                )
            else:
                messages.error(
                    request,
                    "Payment service is temporarily unavailable.",
                )

            return redirect("checkout")

        order.stripe_checkout_session_id = (
            checkout_session.id
        )

        order.save(
            update_fields=[
                "stripe_checkout_session_id"
            ]
        )

        return redirect(
            checkout_session.url,
            code=303,
        )

    return render(
        request,
        "shop/checkout.html",
        {
            "items": items,
            "subtotal": subtotal,
            "shipping_total":
                Decimal("0.00"),
            "total": subtotal,
        },
    )


# =========================================================
# STRIPE SUCCESS
# =========================================================

def stripe_success(request):
    session_id = request.GET.get(
        "session_id",
        ""
    ).strip()

    if not session_id:
        messages.error(
            request,
            "Missing Stripe session."
        )

        return redirect("shop")

    stripe_secret_key = getattr(
        settings,
        "STRIPE_SECRET_KEY",
        "",
    ).strip()

    if not stripe_secret_key:
        messages.error(
            request,
            "Payment service is not configured."
        )

        return redirect("shop")

    stripe.api_key = stripe_secret_key

    try:
        checkout_session = (
            stripe.checkout.Session.retrieve(
                session_id
            )
        )

    except Exception:
        logger.exception(
            "Stripe session verification failed."
        )

        messages.error(
            request,
            "Could not verify payment."
        )

        return redirect("shop")

    order = (
        Order.objects
        .filter(
            stripe_checkout_session_id=session_id,
            payment_method="stripe",
        )
        .first()
    )

    if order is None:
        logger.error(
            "No LE VAURÉ order found for Stripe session %s.",
            session_id,
        )

        messages.error(
            request,
            "Order could not be found."
        )

        return redirect("shop")

    metadata = getattr(
        checkout_session,
        "metadata",
        None,
    )

    session_order_id = ""

    if metadata:
        session_order_id = str(
            getattr(
                metadata,
                "order_id",
                "",
            )
        )

    if (
        session_order_id
        and session_order_id != str(order.pk)
    ):
        logger.error(
            "Stripe session/order mismatch. "
            "Session=%s order=%s metadata_order=%s",
            session_id,
            order.pk,
            session_order_id,
        )

        messages.error(
            request,
            "Payment verification failed."
        )

        return redirect("shop")

    if checkout_session.payment_status != "paid":
        messages.warning(
            request,
            "Payment has not been completed."
        )

        return redirect("checkout")

    order, _ = _finalize_stripe_payment(
        order,
        checkout_session,
    )

    printify_ok = _ensure_printify_order(
        order
    )

    if not printify_ok:
        messages.warning(
            request,
            (
                "Payment was successful, but Printify fulfillment "
                "needs attention. The order is saved safely."
            ),
        )

    request.session["cart"] = {}
    request.session["printify_cart"] = {}
    request.session.modified = True

    return render(
        request,
        "shop/success.html",
        {
            "order": order
        }
    )


# =========================================================
# STRIPE CANCEL
# =========================================================

def stripe_cancel(request):
    order_id = request.GET.get(
        "order_id",
        ""
    ).strip()

    if order_id:
        order = (
            Order.objects
            .filter(
                pk=order_id,
                payment_method="stripe",
            )
            .first()
        )

        if (
            order is not None
            and order.status == "new"
        ):
            order.status = "cancelled"

            order.save(
                update_fields=["status"]
            )

    messages.warning(
        request,
        "Payment was cancelled. Your cart is still available."
    )

    return redirect("checkout")


# =========================================================
# STRIPE WEBHOOK
# =========================================================

@csrf_exempt
@require_POST
def stripe_webhook(request):
    webhook_secret = getattr(
        settings,
        "STRIPE_WEBHOOK_SECRET",
        "",
    ).strip()

    if not webhook_secret:
        logger.error(
            "STRIPE_WEBHOOK_SECRET is not configured."
        )

        return HttpResponse(
            "Webhook secret is not configured.",
            status=400,
        )

    payload = request.body

    signature = request.META.get(
        "HTTP_STRIPE_SIGNATURE",
        ""
    )

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=signature,
            secret=webhook_secret,
        )

    except Exception:
        logger.exception(
            "Invalid Stripe webhook."
        )

        return HttpResponse(
            "Invalid webhook.",
            status=400,
        )

    event_type = event.get(
        "type",
        ""
    )

    if event_type in {
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
    }:
        checkout_session = event["data"]["object"]

        session_id = str(
            getattr(
                checkout_session,
                "id",
                "",
            )
        )

        metadata = getattr(
            checkout_session,
            "metadata",
            None,
        )

        order_id = ""

        if metadata:
            order_id = str(
                getattr(
                    metadata,
                    "order_id",
                    "",
                )
            )

        order = None

        if session_id:
            order = (
                Order.objects
                .filter(
                    stripe_checkout_session_id=session_id,
                    payment_method="stripe",
                )
                .first()
            )

        if (
            order is None
            and order_id
        ):
            order = (
                Order.objects
                .filter(
                    pk=order_id,
                    payment_method="stripe",
                )
                .first()
            )

        if order is None:
            logger.error(
                "Stripe webhook order not found. "
                "Session=%s order_id=%s",
                session_id,
                order_id,
            )

            return HttpResponse(
                "Order not found.",
                status=404,
            )

        if (
            session_id
            and order.stripe_checkout_session_id
            and session_id
            != order.stripe_checkout_session_id
        ):
            logger.error(
                "Stripe webhook session/order mismatch. "
                "Session=%s order=%s",
                session_id,
                order.pk,
            )

            return HttpResponse(
                "Session mismatch.",
                status=400,
            )

        order, _ = _finalize_stripe_payment(
            order,
            checkout_session,
        )

        printify_ok = _ensure_printify_order(
            order
        )

        if not printify_ok:
            return HttpResponse(
                "Printify fulfillment failed.",
                status=500,
            )

    return HttpResponse(
        "ok",
        status=200,
    )


# =========================================================
# REGISTER
# =========================================================

def register(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = RegistrationForm(
        request.POST or None
    )

    if (
        request.method == "POST"
        and form.is_valid()
    ):
        email = (
            form.cleaned_data["email"]
            .strip()
            .lower()
        )

        username = (
            form.cleaned_data["username"]
            .strip()
        )

        if User.objects.filter(
            email__iexact=email
        ).exists():
            form.add_error(
                "email",
                (
                    "An account with this email "
                    "already exists."
                )
            )

            return render(
                request,
                "registration/register.html",
                {
                    "form": form
                }
            )

        if User.objects.filter(
            username__iexact=username
        ).exists():
            form.add_error(
                "username",
                (
                    "This username is "
                    "already taken."
                )
            )

            return render(
                request,
                "registration/register.html",
                {
                    "form": form
                }
            )

        try:
            _store_pending_registration(
                request,
                form
            )

        except Exception as exc:
            request.session.pop(
                _pending_registration_key(),
                None
            )

            request.session.modified = True

            logger.exception(
                "LE VAURÉ verification "
                "email could not be sent."
            )

            if settings.DEBUG:
                messages.error(
                    request,
                    (
                        "Verification email "
                        f"error: {exc}"
                    )
                )
            else:
                messages.error(
                    request,
                    (
                        "We could not send the "
                        "verification email. "
                        "Your account was not "
                        "created yet."
                    )
                )

            return render(
                request,
                "registration/register.html",
                {
                    "form": form
                }
            )

        messages.success(
            request,
            (
                "We sent a 6-digit verification "
                "code to your email."
            )
        )

        return redirect(
            "verify_email"
        )

    return render(
        request,
        "registration/register.html",
        {
            "form": form
        }
    )


# =========================================================
# VERIFY EMAIL
# =========================================================

def verify_email(request):
    pending = (
        _get_pending_registration(
            request
        )
    )

    if not pending:
        messages.warning(
            request,
            (
                "Register first to verify "
                "your email."
            )
        )

        return redirect(
            "register"
        )

    try:
        expires_at = (
            _parse_iso_datetime(
                pending["expires_at"]
            )
        )

    except (
        KeyError,
        TypeError,
        ValueError
    ):
        request.session.pop(
            _pending_registration_key(),
            None
        )

        request.session.modified = True

        messages.error(
            request,
            (
                "Your verification session "
                "is invalid. "
                "Please register again."
            )
        )

        return redirect(
            "register"
        )

    if request.method == "POST":
        code = request.POST.get(
            "code",
            ""
        ).strip()

        if timezone.now() > expires_at:
            messages.error(
                request,
                (
                    "That code has expired. "
                    "Request a new one."
                )
            )

        elif (
            pending.get(
                "attempts",
                0
            )
            >= 8
        ):
            messages.error(
                request,
                (
                    "Too many incorrect attempts. "
                    "Request a new code."
                )
            )

        elif check_password(
            code,
            pending["code_hash"]
        ):
            username = (
                pending["username"]
            )

            email = (
                pending["email"]
            )

            password = (
                pending["password"]
            )

            if User.objects.filter(
                username__iexact=username
            ).exists():
                request.session.pop(
                    _pending_registration_key(),
                    None
                )

                request.session.modified = True

                messages.error(
                    request,
                    (
                        "That username is already "
                        "in use. "
                        "Please register again."
                    )
                )

                return redirect(
                    "register"
                )

            if User.objects.filter(
                email__iexact=email
            ).exists():
                request.session.pop(
                    _pending_registration_key(),
                    None
                )

                request.session.modified = True

                messages.error(
                    request,
                    (
                        "That email is already "
                        "registered. Please log in."
                    )
                )

                return redirect(
                    "login"
                )

            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
            )

            request.session.pop(
                _pending_registration_key(),
                None
            )

            request.session.modified = True

            login(
                request,
                user
            )

            messages.success(
                request,
                (
                    "Email verified. "
                    "Welcome to LE VAURÉ."
                )
            )

            return redirect(
                "home"
            )

        else:
            pending["attempts"] = (
                pending.get(
                    "attempts",
                    0
                )
                + 1
            )

            request.session[
                _pending_registration_key()
            ] = pending

            request.session.modified = True

            messages.error(
                request,
                (
                    "Incorrect verification "
                    "code."
                )
            )

    return render(
        request,
        "registration/verify_email.html",
        {
            "email": pending["email"],
            "expires_at": expires_at
        },
    )


# =========================================================
# RESEND VERIFICATION
# =========================================================

@require_POST
def resend_verification(request):
    pending = (
        _get_pending_registration(
            request
        )
    )

    if not pending:
        messages.warning(
            request,
            "Register first."
        )

        return redirect(
            "register"
        )

    try:
        last_sent_at = (
            _parse_iso_datetime(
                pending["last_sent_at"]
            )
        )

    except (
        KeyError,
        TypeError,
        ValueError
    ):
        request.session.pop(
            _pending_registration_key(),
            None
        )

        request.session.modified = True

        messages.error(
            request,
            (
                "Your verification session "
                "is invalid. "
                "Please register again."
            )
        )

        return redirect(
            "register"
        )

    seconds_since_last_send = (
        timezone.now()
        - last_sent_at
    ).total_seconds()

    if seconds_since_last_send < 45:
        wait_seconds = max(
            1,
            45 - int(
                seconds_since_last_send
            )
        )

        messages.warning(
            request,
            (
                f"Please wait {wait_seconds} "
                "seconds before requesting "
                "another code."
            )
        )

        return redirect(
            "verify_email"
        )

    try:
        code = (
            _new_verification_code()
        )

        _send_verification_email(
            pending["email"],
            code,
            pending.get(
                "username",
                ""
            ),
        )

        _store_pending_verification(
            request,
            pending,
            code
        )

    except Exception as exc:
        logger.exception(
            "LE VAURÉ verification "
            "email resend failed."
        )

        if settings.DEBUG:
            messages.error(
                request,
                (
                    "Verification email "
                    f"resend error: {exc}"
                )
            )
        else:
            messages.error(
                request,
                (
                    "Could not send the "
                    "verification email. "
                    "Please try again."
                )
            )

        return redirect(
            "verify_email"
        )

    messages.success(
        request,
        (
            "A new verification code "
            "was sent to your email."
        )
    )

    return redirect(
        "verify_email"
    )


# =========================================================
# LOGIN
# =========================================================

def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = AuthenticationForm(
        request,
        data=request.POST or None
    )

    if request.method == "GET":
        next_url = request.GET.get(
            "next",
            ""
        )

        if next_url:
            request.session[
                "login_next"
            ] = next_url

    if (
        request.method == "POST"
        and form.is_valid()
    ):
        login(
            request,
            form.get_user()
        )

        next_url = request.session.pop(
            "login_next",
            None,
        )

        request.session.modified = True

        return redirect(
            next_url or "home"
        )

    return render(
        request,
        "registration/login.html",
        {
            "form": form
        },
    )


# =========================================================
# WISHLIST
# =========================================================

@login_required
def wishlist(request):
    wishlist_items = (
        Wishlist.objects
        .filter(user=request.user)
        .select_related(
            "product",
            "product__category",
        )
    )

    return render(
        request,
        "shop/wishlist.html",
        {
            "wishlist_items":
                wishlist_items
        },
    )


@login_required
@require_POST
def toggle_wishlist(request, pk):
    product_item = get_object_or_404(
        Product,
        pk=pk,
        active=True,
    )

    wishlist_item = (
        Wishlist.objects.filter(
            user=request.user,
            product=product_item,
        ).first()
    )

    if wishlist_item:
        wishlist_item.delete()

        messages.success(
            request,
            (
                f"{product_item.name} "
                "removed from wishlist."
            )
        )

    else:
        Wishlist.objects.create(
            user=request.user,
            product=product_item,
        )

        messages.success(
            request,
            (
                f"{product_item.name} "
                "added to wishlist."
            )
        )

    next_url = (
        request.POST.get("next")
        or request.META.get(
            "HTTP_REFERER"
        )
        or reverse("wishlist")
    )

    return redirect(
        next_url
    )
@login_required
@require_POST
def toggle_printify_wishlist(
    request,
    printify_id,
):
    product_item = get_object_or_404(
        PrintifyProduct,
        printify_id=printify_id,
        active=True,
    )

    wishlist_item = (
        Wishlist.objects.filter(
            user=request.user,
            printify_product=product_item,
        ).first()
    )

    if wishlist_item:
        wishlist_item.delete()

        messages.success(
            request,
            (
                f"{product_item.title} "
                "removed from wishlist."
            )
        )

    else:
        Wishlist.objects.create(
            user=request.user,
            printify_product=product_item,
        )

        messages.success(
            request,
            (
                f"{product_item.title} "
                "added to wishlist."
            )
        )

    next_url = (
        request.POST.get("next")
        or request.META.get(
            "HTTP_REFERER"
        )
        or reverse("shop")
    )

    return redirect(next_url)

# =========================================================
# ACCOUNT
# =========================================================

@login_required
def account(request):
    orders = Order.objects.filter(
        user=request.user
    )

    return render(
        request,
        "shop/account.html",
        {
            "orders": orders
        }
    )


# =========================================================
# LEGAL PAGES
# =========================================================

def privacy_policy(request):
    return render(
        request,
        "shop/legal/privacy.html"
    )


def terms(request):
    return render(
        request,
        "shop/legal/terms.html"
    )


def cookie_policy(request):
    return render(
        request,
        "shop/legal/cookies.html"
    )


def returns_policy(request):
    return render(
        request,
        "shop/legal/returns.html"
    )


def impressum(request):
    return render(
        request,
        "shop/legal/impressum.html"
    )


# =========================================================
# PRINTIFY PRODUCTS
# =========================================================

PRINTIFY_SHOP_ID = "28774925"


def _load_printify_products():
    """
    Fetch products from Printify, normalize them for the shop template,
    and synchronize them into the local PrintifyProduct tables so they
    are also visible in Django admin.

    Printify prices are stored in cents, so 3075 becomes Decimal("30.75").
    """
    api_token = getattr(
        settings,
        "PRINTIFY_API_TOKEN",
        ""
    ).strip()

    if not api_token:
        return [], "PRINTIFY_API_TOKEN is not configured."

    url = (
        "https://api.printify.com/v1/shops/"
        f"{PRINTIFY_SHOP_ID}/products.json"
    )

    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=15
        )
        response.raise_for_status()
        data = response.json()

    except (requests.RequestException, ValueError) as exc:
        logger.exception(
            "Printify API request failed."
        )
        return [], str(exc)

    normalized_products = []

    for raw_product in data.get("data", []):
        printify_id = str(
            raw_product.get("id", "")
        ).strip()

        if not printify_id:
            continue

        title = raw_product.get(
            "title",
            "Untitled product"
        )

        description = raw_product.get(
            "description",
            ""
        )

        # ---------------------------------------------
        # OPTION VALUE NAMES
        # ---------------------------------------------
        option_value_names = {}

        for option in raw_product.get("options", []):
            for value in option.get("values", []):
                value_id = value.get("id")

                option_value_names[value_id] = value.get(
                    "title",
                    str(value_id or "")
                )

        # ---------------------------------------------
        # VARIANTS
        # ---------------------------------------------
        raw_variants = raw_product.get(
            "variants",
            []
        )

        enabled_variants = []

        for variant in raw_variants:
            if not variant.get("is_enabled", False):
                continue

            option_titles = [
                option_value_names.get(
                    option_id,
                    str(option_id)
                )
                for option_id in variant.get("options", [])
            ]

            variant_title = (
                " / ".join(option_titles)
                or variant.get("title", "Variant")
            )

            variant_price = (
                Decimal(
                    str(variant.get("price", 0))
                )
                / Decimal("100")
            )

            enabled_variants.append(
                {
                    "id": variant.get("id"),
                    "title": variant_title,
                    "price": variant_price,
                    "is_available": variant.get(
                        "is_available",
                        True
                    ),
                }
            )

        prices = [
            variant["price"]
            for variant in enabled_variants
        ]

        product_price = (
            min(prices)
            if prices
            else Decimal("0.00")
        )

        # ---------------------------------------------
        # LOCAL PRINTIFY PRODUCT
        # ---------------------------------------------
        db_product, created = PrintifyProduct.objects.get_or_create(
            printify_id=printify_id,
            defaults={
                "title": title,
                "description": description,
                "price": product_price,
                "active": True,
                "featured": True,
                "sync_enabled": True,
            },
        )

        # Respect the admin Sync Enabled switch.
        # New records are synchronized immediately.
        if created or db_product.sync_enabled:
            changed_fields = []

            if db_product.title != title:
                db_product.title = title
                changed_fields.append("title")

            if db_product.description != description:
                db_product.description = description
                changed_fields.append("description")

            if db_product.price != product_price:
                db_product.price = product_price
                changed_fields.append("price")

            if changed_fields:
                db_product.save(
                    update_fields=changed_fields + ["updated_at"]
                )

            # -----------------------------------------
            # PRINTIFY IMAGES
            # -----------------------------------------
            raw_images = raw_product.get(
                "images",
                []
            )

            # Printify can return multiple mockups. The first item is not
            # always the storefront/default mockup, so prefer is_default.
            default_image_index = 0

            for index, image in enumerate(raw_images):
                if image.get("is_default", False):
                    default_image_index = index
                    break

            remote_image_urls = []

            for index, image in enumerate(raw_images):
                image_url = (
                    image.get("src", "")
                    or ""
                ).strip()

                if not image_url:
                    continue

                remote_image_urls.append(image_url)

                PrintifyProductImage.objects.update_or_create(
                    product=db_product,
                    printify_url=image_url,
                    defaults={
                        "is_primary": index == default_image_index,
                        "sort_order": index,
                    },
                )

            # Make sure an old image cannot remain marked as primary.
            if remote_image_urls:
                primary_url = (
                    raw_images[default_image_index].get("src", "")
                    or ""
                ).strip()

                if primary_url:
                    PrintifyProductImage.objects.filter(
                        product=db_product
                    ).exclude(
                        printify_url=primary_url
                    ).update(
                        is_primary=False
                    )

            # Remove only old API images.
            # Manually uploaded custom images are preserved.
            api_images = PrintifyProductImage.objects.filter(
                product=db_product,
                custom_image__isnull=True,
            )

            if remote_image_urls:
                api_images.exclude(
                    printify_url__in=remote_image_urls
                ).delete()
            else:
                api_images.exclude(
                    printify_url=""
                ).delete()

            # -----------------------------------------
            # PRINTIFY VARIANTS
            # -----------------------------------------
            current_variant_ids = []

            for variant in raw_variants:
                variant_id = variant.get("id")

                if variant_id is None:
                    continue

                current_variant_ids.append(variant_id)

                option_titles = [
                    option_value_names.get(
                        option_id,
                        str(option_id)
                    )
                    for option_id in variant.get("options", [])
                ]

                variant_title = (
                    " / ".join(option_titles)
                    or variant.get("title", "Variant")
                )

                variant_price = (
                    Decimal(
                        str(variant.get("price", 0))
                    )
                    / Decimal("100")
                )

                PrintifyVariant.objects.update_or_create(
                    printify_variant_id=variant_id,
                    defaults={
                        "product": db_product,
                        "title": variant_title,
                        "price": variant_price,
                        "available": variant.get(
                            "is_available",
                            True
                        ),
                        "enabled": variant.get(
                            "is_enabled",
                            True
                        ),
                    },
                )

            stale_variants = PrintifyVariant.objects.filter(
                product=db_product
            )

            if current_variant_ids:
                stale_variants.exclude(
                    printify_variant_id__in=current_variant_ids
                ).delete()
            else:
                stale_variants.delete()

        # ---------------------------------------------
        # TEMPLATE-FRIENDLY DATA
        # ---------------------------------------------
        raw_images = raw_product.get("images", [])
        image_url = ""

        if raw_images:
            default_image = next(
                (
                    image
                    for image in raw_images
                    if image.get("is_default", False)
                ),
                raw_images[0],
            )

            image_url = (
                default_image.get("src", "")
                or ""
            ).strip()

        normalized_products.append(
            {
                "id": printify_id,
                "title": title,
                "image": image_url,
                "variants": enabled_variants,
                "price": product_price,
            }
        )

    return normalized_products, None


def printify_products(request):
    products, error = _load_printify_products()

    if error:
        return JsonResponse(
            {
                "ok": False,
                "error": error,
            },
            status=502
        )

    return render(
        request,
        "shop/printify_products.html",
        {
            "products": products,
        },
    )

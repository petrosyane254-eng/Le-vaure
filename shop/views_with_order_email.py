from decimal import Decimal
import logging
import secrets
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import RegistrationForm
from .models import Category, Product, Order, OrderItem

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


def _verification_minutes():
    return getattr(
        settings,
        "SOUTHWARD_VERIFICATION_MINUTES",
        getattr(settings, "SCORPION_VERIFICATION_MINUTES", 10),
    )


def _pending_registration_key():
    return "pending_registration"


def _send_verification_email(recipient_email, code, username=""):
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
        },
    )

    text_message = (
        "SOUTHWARD\n\n"
        f"Welcome, {username or 'LE VAURÉ member'}.\n\n"
        f"Your email verification code is: {code}\n\n"
        f"This code expires in {minutes} minutes.\n\n"
        "If you did not create a LE VAURÉ account, "
        "you can safely ignore this email."
    )

    email = EmailMultiAlternatives(
        subject="Your LE VAURÉ verification code",
        body=text_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient_email],
    )
    email.attach_alternative(html_message, "text/html")
    email.send(fail_silently=False)



def _send_order_confirmation_email(order):
    order_number = f"SW-{order.pk:06d}"

    html_message = render_to_string(
        "emails/order_confirmation_email.html",
        {
            "order": order,
            "order_number": order_number,
        },
    )

    text_message = (
        "SOUTHWARD\n\n"
        f"Thank you for your order, {order.full_name}.\n\n"
        f"Order number: {order_number}\n"
        f"Total: {order.total}\n\n"
        "We received your order successfully and we are preparing it now.\n\n"
        "SOUTHWARD\n"
        "MOVE YOUR OWN WAY."
    )

    email = EmailMultiAlternatives(
        subject=f"LE VAURÉ Order Confirmation — {order_number}",
        body=text_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[order.email],
    )

    email.attach_alternative(html_message, "text/html")
    return email.send(fail_silently=False)


def _store_pending_registration(request, form):
    code = _new_verification_code()
    minutes = _verification_minutes()
    now = timezone.now()

    pending = {
        "username": form.cleaned_data["username"].strip(),
        "email": form.cleaned_data["email"].strip().lower(),
        "password": form.cleaned_data["password1"],
        "code_hash": make_password(code),
        "expires_at": (now + timedelta(minutes=minutes)).isoformat(),
        "attempts": 0,
        "last_sent_at": now.isoformat(),
    }

    request.session[_pending_registration_key()] = pending
    request.session.modified = True

    _send_verification_email(
        pending["email"],
        code,
        pending["username"],
    )


def _get_pending_registration(request):
    return request.session.get(_pending_registration_key())


def _parse_iso_datetime(value):
    parsed = datetime.fromisoformat(value)
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _store_pending_verification(request, pending, code):
    now = timezone.now()
    pending["code_hash"] = make_password(code)
    pending["expires_at"] = (now + timedelta(minutes=_verification_minutes())).isoformat()
    pending["attempts"] = 0
    pending["last_sent_at"] = now.isoformat()
    request.session[_pending_registration_key()] = pending
    request.session.modified = True


def home(request):
    products = Product.objects.filter(active=True, featured=True)[:8]
    return render(request, "shop/home.html", {"products": products})


def shop(request):
    products = Product.objects.filter(active=True).select_related("category")
    category = request.GET.get("category", "all")
    q = request.GET.get("q", "").strip()
    sort = request.GET.get("sort", "featured")

    if category != "all":
        products = products.filter(category__slug=category)
    if q:
        products = products.filter(name__icontains=q)
    if sort == "price_low":
        products = products.order_by("price")
    elif sort == "price_high":
        products = products.order_by("-price")
    elif sort == "name":
        products = products.order_by("name")

    return render(
        request,
        "shop/shop.html",
        {
            "products": products,
            "categories": Category.objects.all(),
            "active_category": category,
            "q": q,
            "sort": sort,
        },
    )


def product(request, slug):
    item = get_object_or_404(Product, slug=slug, active=True)
    return render(request, "shop/product.html", {"product": item})


@require_POST
def add_cart(request, pk):
    product_item = get_object_or_404(Product, pk=pk, active=True)

    if product_item.stock <= 0:
        messages.warning(request, "Product is out of stock.")
        return redirect(request.META.get("HTTP_REFERER", "/shop/"))

    cart_data = request.session.get("cart", {})
    key = str(pk)
    quantity = _safe_int(request.POST.get("quantity", 1), default=1, minimum=1)
    current_quantity = cart_data.get(key, 0)
    cart_data[key] = min(current_quantity + quantity, product_item.stock)
    request.session["cart"] = cart_data
    request.session.modified = True
    messages.success(request, f"{product_item.name} added to cart.")
    return redirect(request.META.get("HTTP_REFERER", "/shop/"))


def cart(request):
    cart_data = request.session.get("cart", {})
    products = Product.objects.filter(pk__in=cart_data.keys())
    items = []
    total = Decimal("0.00")

    for product_item in products:
        quantity = cart_data.get(str(product_item.pk), 0)
        subtotal = product_item.price * quantity
        items.append({"product": product_item, "quantity": quantity, "subtotal": subtotal})
        total += subtotal

    return render(request, "shop/cart.html", {"items": items, "total": total})


@require_POST
def update_cart(request, pk):
    product_item = get_object_or_404(Product, pk=pk, active=True)
    cart_data = request.session.get("cart", {})
    quantity = _safe_int(request.POST.get("quantity", 0), default=0, minimum=0)
    key = str(pk)

    if quantity <= 0:
        cart_data.pop(key, None)
    elif product_item.stock <= 0:
        cart_data.pop(key, None)
        messages.warning(request, f"{product_item.name} is out of stock.")
    else:
        cart_data[key] = min(quantity, product_item.stock)

    request.session["cart"] = cart_data
    request.session.modified = True
    return redirect("cart")


def checkout(request):
    cart_data = request.session.get("cart", {})
    products = Product.objects.filter(pk__in=cart_data.keys(), active=True)
    items = []
    total = Decimal("0.00")

    for product_item in products:
        requested_quantity = cart_data.get(str(product_item.pk), 0)
        quantity = min(requested_quantity, product_item.stock)
        if quantity <= 0:
            continue
        subtotal = product_item.price * quantity
        items.append({"product": product_item, "quantity": quantity, "subtotal": subtotal})
        total += subtotal

    if not items:
        messages.warning(request, "Your cart is empty.")
        return redirect("shop")

    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        email = request.POST.get("email", "").strip()
        address = request.POST.get("address", "").strip()

        if not full_name or not email or not address:
            messages.error(request, "Please fill all fields.")
            return render(request, "shop/checkout.html", {"items": items, "total": total})

        order = Order.objects.create(
            user=request.user if request.user.is_authenticated else None,
            full_name=full_name,
            email=email,
            address=address,
            total=total,
        )

        for item in items:
            product_item = item["product"]
            quantity = item["quantity"]
            OrderItem.objects.create(
                order=order,
                product=product_item,
                quantity=quantity,
                price=product_item.price,
            )
            product_item.stock = max(0, product_item.stock - quantity)
            product_item.save(update_fields=["stock"])

        try:
            _send_order_confirmation_email(order)
        except Exception:
            logger.exception(
                "LE VAURÉ order confirmation email could not be sent."
            )

        request.session["cart"] = {}
        request.session.modified = True
        return render(request, "shop/success.html", {"order": order})

    return render(request, "shop/checkout.html", {"items": items, "total": total})


def register(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = RegistrationForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].strip().lower()
        username = form.cleaned_data["username"].strip()

        if User.objects.filter(email__iexact=email).exists():
            form.add_error("email", "An account with this email already exists.")
            return render(request, "registration/register.html", {"form": form})

        if User.objects.filter(username__iexact=username).exists():
            form.add_error("username", "This username is already taken.")
            return render(request, "registration/register.html", {"form": form})

        try:
            _store_pending_registration(request, form)
        except Exception as exc:
            request.session.pop(_pending_registration_key(), None)
            request.session.modified = True
            logger.exception("LE VAURÉ verification email could not be sent.")

            if settings.DEBUG:
                messages.error(request, f"Verification email error: {exc}")
            else:
                messages.error(
                    request,
                    "We could not send the verification email. Your account was not created yet.",
                )

            return render(request, "registration/register.html", {"form": form})

        messages.success(request, "We sent a 6-digit verification code to your email.")
        return redirect("verify_email")

    return render(request, "registration/register.html", {"form": form})


def verify_email(request):
    pending = _get_pending_registration(request)

    if not pending:
        messages.warning(request, "Register first to verify your email.")
        return redirect("register")

    try:
        expires_at = _parse_iso_datetime(pending["expires_at"])
    except (KeyError, TypeError, ValueError):
        request.session.pop(_pending_registration_key(), None)
        request.session.modified = True
        messages.error(request, "Your verification session is invalid. Please register again.")
        return redirect("register")

    if request.method == "POST":
        code = request.POST.get("code", "").strip()

        if timezone.now() > expires_at:
            messages.error(request, "That code has expired. Request a new one.")
        elif pending.get("attempts", 0) >= 8:
            messages.error(request, "Too many incorrect attempts. Request a new code.")
        elif check_password(code, pending["code_hash"]):
            username = pending["username"]
            email = pending["email"]
            password = pending["password"]

            if User.objects.filter(username__iexact=username).exists():
                request.session.pop(_pending_registration_key(), None)
                request.session.modified = True
                messages.error(request, "That username is already in use. Please register again.")
                return redirect("register")

            if User.objects.filter(email__iexact=email).exists():
                request.session.pop(_pending_registration_key(), None)
                request.session.modified = True
                messages.error(request, "That email is already registered. Please log in.")
                return redirect("login")

            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
            )

            request.session.pop(_pending_registration_key(), None)
            request.session.modified = True
            login(request, user)
            messages.success(request, "Email verified. Welcome to LE VAURÉ.")
            return redirect("home")
        else:
            pending["attempts"] = pending.get("attempts", 0) + 1
            request.session[_pending_registration_key()] = pending
            request.session.modified = True
            messages.error(request, "Incorrect verification code.")

    return render(
        request,
        "registration/verify_email.html",
        {"email": pending["email"], "expires_at": expires_at},
    )


@require_POST
def resend_verification(request):
    pending = _get_pending_registration(request)

    if not pending:
        messages.warning(request, "Register first.")
        return redirect("register")

    try:
        last_sent_at = _parse_iso_datetime(pending["last_sent_at"])
    except (KeyError, TypeError, ValueError):
        request.session.pop(_pending_registration_key(), None)
        request.session.modified = True
        messages.error(request, "Your verification session is invalid. Please register again.")
        return redirect("register")

    seconds_since_last_send = (timezone.now() - last_sent_at).total_seconds()

    if seconds_since_last_send < 45:
        wait_seconds = max(1, 45 - int(seconds_since_last_send))
        messages.warning(
            request,
            f"Please wait {wait_seconds} seconds before requesting another code.",
        )
        return redirect("verify_email")

    try:
        code = _new_verification_code()

        _send_verification_email(
            pending["email"],
            code,
            pending.get("username", ""),
        )

        _store_pending_verification(request, pending, code)

    except Exception as exc:
        logger.exception("LE VAURÉ verification email resend failed.")

        if settings.DEBUG:
            messages.error(request, f"Verification email resend error: {exc}")
        else:
            messages.error(request, "Could not send the verification email. Please try again.")

        return redirect("verify_email")

    messages.success(request, "A new verification code was sent to your email.")
    return redirect("verify_email")


def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = AuthenticationForm(request, data=request.POST or None)

    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        return redirect("home")

    return render(request, "registration/login.html", {"form": form})


@login_required
def account(request):
    orders = Order.objects.filter(user=request.user)
    return render(request, "shop/account.html", {"orders": orders})


def privacy_policy(request):
    return render(request, "shop/legal/privacy.html")


def terms(request):
    return render(request, "shop/legal/terms.html")


def cookie_policy(request):
    return render(request, "shop/legal/cookies.html")


def returns_policy(request):
    return render(request, "shop/legal/returns.html")


def impressum(request):
    return render(request, "shop/legal/impressum.html")

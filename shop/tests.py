from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from . import views
from .models import Category, Order, OrderItem, Product, SiteAccessSettings


class OrderItemSubtotalTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name="Test",
            slug="test",
        )

        self.product = Product.objects.create(
            name="Widget",
            slug="widget",
            category=self.category,
            description="Test product",
            price=Decimal("19.99"),
            stock=10,
        )

        self.order = Order.objects.create(
            full_name="Test Customer",
            email="test@example.com",
            address="123 Test Street",
            total=Decimal("19.99"),
        )

    def test_subtotal_returns_zero_when_inline_fields_are_empty(self):
        item = OrderItem(
            order=self.order,
            product=self.product,
        )

        self.assertEqual(
            item.subtotal,
            0,
        )

    def test_subtotal_multiplies_quantity_and_price(self):
        item = OrderItem(
            order=self.order,
            product=self.product,
            quantity=3,
            price=Decimal("19.99"),
        )

        self.assertEqual(
            item.subtotal,
            Decimal("59.97"),
        )


class ViewUtilityTests(TestCase):
    def test_safe_int_handles_invalid_input(self):
        self.assertEqual(
            views._safe_int(
                "oops",
                default=7,
                minimum=1,
            ),
            7,
        )

    def test_safe_int_respects_minimum(self):
        self.assertEqual(
            views._safe_int(
                "-4",
                default=7,
                minimum=1,
            ),
            1,
        )

    def test_views_module_imports_user(self):
        self.assertIsNotNone(
            views.User
        )


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class RegistrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        SiteAccessSettings.objects.update(maintenance_mode=False)

    @patch("shop.views._send_verification_email")
    def test_register_does_not_create_user_until_verified(
        self,
        mocked_send,
    ):
        response = self.client.post(
            reverse("register"),
            {
                "username": "newuser",
                "email": "newuser@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.assertEqual(
            response.url,
            reverse("verify_email"),
        )

        self.assertFalse(
            User.objects.filter(
                username="newuser",
                email="newuser@example.com",
            ).exists()
        )

        self.assertTrue(
            response.wsgi_request.session.get(
                "pending_registration"
            )
        )

        mocked_send.assert_called_once()

    def test_register_rejects_duplicate_email(self):
        User.objects.create_user(
            username="existing",
            email="dup@example.com",
            password="StrongPass123!",
        )

        response = self.client.post(
            reverse("register"),
            {
                "username": "newuser2",
                "email": "dup@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            "This email is already registered.",
        )

        self.assertFalse(
            User.objects.filter(
                username="newuser2"
            ).exists()
        )

    @patch(
        "shop.views.check_password",
        return_value=True,
    )
    @patch(
        "shop.views._send_verification_email"
    )
    def test_verify_email_creates_user(
        self,
        mocked_send,
        mocked_check_password,
    ):
        self.client.post(
            reverse("register"),
            {
                "username": "verifieduser",
                "email": "verified@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        session = self.client.session

        pending = session[
            "pending_registration"
        ]

        pending["code_hash"] = "fake-hash"
        pending["attempts"] = 0
        pending["expires_at"] = (
            "2099-01-01T00:00:00+00:00"
        )

        session[
            "pending_registration"
        ] = pending

        session.save()

        response = self.client.post(
            reverse("verify_email"),
            {
                "code": "123456",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.assertEqual(
            response.url,
            reverse("home"),
        )

        self.assertTrue(
            User.objects.filter(
                username="verifieduser",
                email="verified@example.com",
            ).exists()
        )


@override_settings(
    STRIPE_SECRET_KEY="sk_test_fake"
)
class CheckoutStripeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        SiteAccessSettings.objects.update(maintenance_mode=False)

    def setUp(self):
        self.category = Category.objects.create(
            name="Test",
            slug="test",
        )

        self.product = Product.objects.create(
            name="Widget",
            slug="widget",
            category=self.category,
            description="Test product",
            price=Decimal("19.99"),
            stock=10,
        )

    def _add_product_to_cart(self, quantity=1):
        session = self.client.session

        session["cart"] = {
            str(self.product.pk): quantity
        }

        session.save()

    def _checkout_data(self):
        return {
            "full_name": "Test Customer",
            "email": "test@example.com",
            "phone": "",
            "country": "DE",
            "region": "",
            "street": "123 Test Street",
            "apartment": "",
            "city": "Berlin",
            "postal_code": "10115",
            "delivery_notes": "",
        }

    @patch(
        "shop.views.stripe.checkout.Session.create"
    )
    def test_checkout_creates_order_and_stripe_session(
        self,
        mocked_stripe_create,
    ):
        mocked_stripe_create.return_value = (
            SimpleNamespace(
                id="cs_test_123",
                url=(
                    "https://checkout.stripe.com/"
                    "test-session"
                ),
            )
        )

        self._add_product_to_cart(
            quantity=2
        )

        response = self.client.post(
            reverse("checkout"),
            self._checkout_data(),
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.assertEqual(
            response.url,
            (
                "https://checkout.stripe.com/"
                "test-session"
            ),
        )

        order = Order.objects.get(
            email="test@example.com",
        )

        self.assertEqual(
            order.full_name,
            "Test Customer",
        )

        self.assertEqual(
            order.payment_method,
            "stripe",
        )

        self.assertEqual(
            order.stripe_checkout_session_id,
            "cs_test_123",
        )

        self.assertEqual(
            order.total,
            Decimal("39.98"),
        )

        self.assertEqual(
            order.items.count(),
            1,
        )

        order_item = order.items.get()

        self.assertEqual(
            order_item.product,
            self.product,
        )

        self.assertEqual(
            order_item.quantity,
            2,
        )

        mocked_stripe_create.assert_called_once()

        stripe_kwargs = (
            mocked_stripe_create.call_args.kwargs
        )

        self.assertEqual(
            stripe_kwargs["mode"],
            "payment",
        )

        self.assertEqual(
            stripe_kwargs["customer_email"],
            "test@example.com",
        )

        self.assertEqual(
            stripe_kwargs["metadata"]["order_id"],
            str(order.pk),
        )

    @patch(
        "shop.views.stripe.checkout.Session.create",
        side_effect=Exception(
            "Stripe unavailable"
        ),
    )
    def test_checkout_deletes_order_when_stripe_session_fails(
        self,
        mocked_stripe_create,
    ):
        self._add_product_to_cart(
            quantity=1
        )

        response = self.client.post(
            reverse("checkout"),
            self._checkout_data(),
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.assertEqual(
            response.url,
            reverse("checkout"),
        )

        self.assertFalse(
            Order.objects.filter(
                email="test@example.com",
            ).exists()
        )

        mocked_stripe_create.assert_called_once()

from django.conf import settings
from django.contrib.auth.models import User
from django.template.loader import get_template
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import resolve, reverse

from .models import Category, Product, SiteAccessSettings


class TemplateCompilationTests(SimpleTestCase):
    def test_all_project_templates_compile(self):
        template_root = settings.BASE_DIR / "templates"
        for path in template_root.rglob("*.html"):
            with self.subTest(template=path.name):
                get_template(path.relative_to(template_root).as_posix())


@override_settings(
    SECURE_SSL_REDIRECT=False,
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class AdminNavigationTests(TestCase):
    def test_sidebar_links_resolve_and_render_for_superuser(self):
        user = User.objects.create_superuser(
            username="navigation-admin", email="admin@example.com", password=None
        )
        self.client.force_login(user)
        expected_names = {
            "Dashboard": "admin:index",
            "My Products": "admin:shop_product_changelist",
            "Categories": "admin:shop_category_changelist",
            "Orders": "admin:shop_order_changelist",
            "Order Items": "admin:shop_orderitem_changelist",
            "Users": "admin:auth_user_changelist",
            "Wishlists": "admin:shop_wishlist_changelist",
            "Email Verifications": "admin:shop_emailverification_changelist",
        }
        items = [
            item for group in settings.UNFOLD["SIDEBAR"]["navigation"]
            for item in group["items"]
        ]
        self.assertEqual({item["title"] for item in items}, set(expected_names))
        for item in items:
            with self.subTest(page=item["title"]):
                url = str(item["link"])
                name = expected_names[item["title"]]
                self.assertEqual(url, reverse(name))
                self.assertEqual(resolve(url).view_name, name)
                self.assertEqual(self.client.get(url).status_code, 200)


@override_settings(
    SECURE_SSL_REDIRECT=False,
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class StorefrontPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        SiteAccessSettings.objects.update(maintenance_mode=False)
        category = Category.objects.create(name="Smoke test", slug="smoke-test")
        cls.product = Product.objects.create(
            name="Test product", slug="test-product", category=category,
            description="Test", price="10.00", stock=3,
        )
        cls.user = User.objects.create_user(username="page-test")

    def test_public_pages_render(self):
        for name in (
            "home", "shop", "cart", "login", "register", "privacy",
            "terms", "cookies", "returns", "impressum", "robots_txt", "sitemap",
        ):
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        self.assertEqual(self.client.get(self.product.get_absolute_url()).status_code, 200)

    def test_account_wishlist_and_populated_checkout_render(self):
        self.client.force_login(self.user)
        for name in ("account", "wishlist"):
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        session = self.client.session
        session["cart"] = {str(self.product.pk): 1}
        session.save()
        self.assertEqual(self.client.get(reverse("checkout")).status_code, 200)

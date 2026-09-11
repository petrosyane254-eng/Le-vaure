from django.urls import path
from django.contrib.auth.views import LogoutView
from django.contrib.sitemaps.views import sitemap
from django.views.generic import TemplateView

from . import views
from .sitemaps import StaticViewSitemap, ProductSitemap


# =========================================================
# SITEMAPS
# =========================================================

sitemaps = {
    "static": StaticViewSitemap,
    "products": ProductSitemap,
}


# =========================================================
# URL PATTERNS
# =========================================================

urlpatterns = [

    # =====================================================
    # SEO
    # =====================================================

    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="sitemap",
    ),

    path(
        "robots.txt",
        TemplateView.as_view(
            template_name="robots.txt",
            content_type="text/plain",
        ),
        name="robots_txt",
    ),

    # =====================================================
    # HOME / SHOP
    # =====================================================

    path(
        "",
        views.home,
        name="home",
    ),

    path(
        "shop/",
        views.shop,
        name="shop",
    ),

    # =====================================================
    # PRIVATE SHOP
    # =====================================================

    path(
        "site-access/",
        views.site_access,
        name="site_access",
    ),

    # =====================================================
    # PRODUCT
    # =====================================================

    path(
        "product/<slug:slug>/",
        views.product,
        name="product",
    ),

    # =====================================================
    # CART
    # =====================================================

    path(
        "cart/",
        views.cart,
        name="cart",
    ),

    path(
        "cart/add/<int:pk>/",
        views.add_cart,
        name="add_cart",
    ),

    path(
        "cart/update/<int:pk>/",
        views.update_cart,
        name="update_cart",
    ),

    # =====================================================
    # CHECKOUT
    # =====================================================

    path(
        "checkout/",
        views.checkout,
        name="checkout",
    ),

    # =====================================================
    # STRIPE
    # =====================================================

    path(
        "stripe/success/",
        views.stripe_success,
        name="stripe_success",
    ),

    path(
        "stripe/cancel/",
        views.stripe_cancel,
        name="stripe_cancel",
    ),

    path(
        "stripe/webhook/",
        views.stripe_webhook,
        name="stripe_webhook",
    ),

    # =====================================================
    # AUTH
    # =====================================================

    path(
        "register/",
        views.register,
        name="register",
    ),

    path(
        "verify-email/",
        views.verify_email,
        name="verify_email",
    ),

    path(
        "resend-verification/",
        views.resend_verification,
        name="resend_verification",
    ),

    path(
        "login/",
        views.login_view,
        name="login",
    ),

    path(
        "logout/",
        LogoutView.as_view(
            next_page="home",
        ),
        name="logout",
    ),

    # =====================================================
    # ACCOUNT
    # =====================================================

    path(
        "account/",
        views.account,
        name="account",
    ),

    # =====================================================
    # WISHLIST
    # =====================================================

    path(
        "wishlist/",
        views.wishlist,
        name="wishlist",
    ),

    path(
        "wishlist/toggle/<int:pk>/",
        views.toggle_wishlist,
        name="toggle_wishlist",
    ),

    # =====================================================
    # LEGAL / HELP
    # =====================================================

    path(
        "privacy/",
        views.privacy_policy,
        name="privacy",
    ),

    path(
        "terms/",
        views.terms,
        name="terms",
    ),

    path(
        "cookies/",
        views.cookie_policy,
        name="cookies",
    ),

    path(
        "returns/",
        views.returns_policy,
        name="returns",
    ),

    path(
        "impressum/",
        views.impressum,
        name="impressum",
    ),
]
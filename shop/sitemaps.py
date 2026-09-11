from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Product


# =========================================================
# STATIC PAGES
# =========================================================

class StaticViewSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7
    protocol = "https"

    def items(self):
        return [
            "home",
            "shop",
            "returns",
            "privacy",
            "terms",
            "cookies",
            "impressum",
        ]

    def location(self, item):
        return reverse(item)


# =========================================================
# PRODUCTS
# =========================================================

class ProductSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.9
    protocol = "https"

    def items(self):
        return (
            Product.objects
            .filter(active=True)
            .select_related("category")
        )

    def location(self, obj):
        return obj.get_absolute_url()
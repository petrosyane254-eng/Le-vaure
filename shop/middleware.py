from django.shortcuts import redirect
from django.urls import reverse

from .models import SiteAccessSettings


class SiteAccessMiddleware:
    """
    Blocks the public shop while private mode is enabled.

    Always accessible:
    - Django admin
    - site access page
    - robots.txt
    - sitemap.xml
    - static files
    - media files
    - Stripe webhook
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        allowed_prefixes = (
            "/southward-control-7x9/",
            "/site-access/",
            "/static/",
            "/media/",
        )

        allowed_exact_paths = (
            reverse("set_language"),
            "/robots.txt",
            "/sitemap.xml",
            "/stripe/webhook/",
        )

        if (
            path in allowed_exact_paths
            or path.startswith(allowed_prefixes)
        ):
            return self.get_response(request)

        try:
            site_access = SiteAccessSettings.objects.first()
        except Exception:
            return self.get_response(request)

        if not site_access:
            return self.get_response(request)

        if not site_access.maintenance_mode:
            return self.get_response(request)

        if (
            request.session.get(
                "southward_site_access_granted_for"
            )
            == site_access.access_password
        ):
            return self.get_response(request)

        return redirect(reverse("site_access"))

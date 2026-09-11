from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path(
        "southward-control-7x9/",
        admin.site.urls,
    ),

    path(
        "i18n/",
        include("django.conf.urls.i18n"),
    ),

    path(
        "",
        include("shop.urls"),
    ),
]


if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )
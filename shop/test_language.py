from html.parser import HTMLParser

from django.conf import settings
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import SiteAccessSettings


class NavbarParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_nav = False
        self.in_link = False
        self.labels = []

    def handle_starttag(self, tag, attrs):
        if tag == "nav" and "sw-main-menu" in dict(attrs).get("class", "").split():
            self.in_nav = True
        if self.in_nav and tag == "a":
            self.in_link = True
            self.labels.append("")

    def handle_endtag(self, tag):
        if tag == "a":
            self.in_link = False
        if tag == "nav":
            self.in_nav = False

    def handle_data(self, data):
        if self.in_nav and self.in_link:
            self.labels[-1] += data


@override_settings(
    SECURE_SSL_REDIRECT=False,
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class LanguageSelectionTests(TestCase):
    labels = {
        "en": ["Shop", "Collections", "About", "Journal"],
        "hy": ["Խանութ", "Հավաքածուներ", "Մեր մասին", "Ամսագիր"],
        "de": ["Shop", "Kollektionen", "Über uns", "Journal"],
        "ru": ["Магазин", "Коллекции", "О нас", "Журнал"],
        "fr": ["Boutique", "Collections", "À propos", "Journal"],
    }

    def setUp(self):
        SiteAccessSettings.objects.update_or_create(
            pk=1, defaults={"maintenance_mode": False}
        )

    def assert_navbar(self, response, language):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Language"], language)
        self.assertContains(response, f'<html lang="{language}">')
        parser = NavbarParser()
        parser.feed(response.content.decode())
        self.assertEqual(parser.labels, self.labels[language])

    def test_default_language_is_english(self):
        self.assert_navbar(self.client.get(reverse("home")), "en")

    def test_all_languages_persist_after_switch_refresh_and_navigation(self):
        for language in ("hy", "en", "de", "ru", "fr"):
            with self.subTest(language=language):
                response = self.client.post(
                    reverse("set_language"),
                    {"language": language, "next": reverse("home")},
                    follow=True,
                )
                self.assertEqual(
                    self.client.cookies[settings.LANGUAGE_COOKIE_NAME].value,
                    language,
                )
                self.assert_navbar(response, language)
                self.assert_navbar(self.client.get(reverse("home")), language)
                self.assert_navbar(self.client.get(reverse("shop")), language)

    def test_selected_language_overrides_browser_preference(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "de"
        response = self.client.get(reverse("home"), HTTP_ACCEPT_LANGUAGE="hy")
        self.assert_navbar(response, "de")

    def test_language_switch_is_available_while_shop_is_private(self):
        SiteAccessSettings.objects.update(maintenance_mode=True)
        self.assertRedirects(
            self.client.get(reverse("home")), reverse("site_access")
        )
        response = self.client.post(
            reverse("set_language"),
            {"language": "fr", "next": reverse("site_access")},
        )
        self.assertRedirects(response, reverse("site_access"))
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value, "fr")
        self.assertRedirects(
            self.client.get(reverse("home")), reverse("site_access")
        )

    def test_language_switch_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(reverse("set_language"), {"language": "fr"})
        self.assertEqual(response.status_code, 403)

    def test_invalid_language_does_not_replace_selection(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"
        response = self.client.post(
            reverse("set_language"),
            {"language": "invalid", "next": reverse("home")},
            follow=True,
        )
        self.assert_navbar(response, "en")

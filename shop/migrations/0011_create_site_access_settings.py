from django.db import migrations


def create_site_access_settings(apps, schema_editor):
    SiteAccessSettings = apps.get_model(
        "shop",
        "SiteAccessSettings",
    )

    SiteAccessSettings.objects.get_or_create(
        pk=1,
        defaults={
            "maintenance_mode": True,
            "access_password": "",
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0010_siteaccesssettings"),
    ]

    operations = [
        migrations.RunPython(
            create_site_access_settings,
            migrations.RunPython.noop,
        ),
    ]
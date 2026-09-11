from decimal import Decimal

import requests
from django.conf import settings


def _get_printify_auth():
    api_token = getattr(settings, "PRINTIFY_API_TOKEN", "").strip()
    shop_id = getattr(settings, "PRINTIFY_SHOP_ID", "").strip()

    if not api_token:
        raise ValueError("PRINTIFY_API_TOKEN is not configured.")
    if not shop_id:
        raise ValueError("PRINTIFY_SHOP_ID is not configured.")

    return api_token, shop_id


def load_printify_products():
    api_token, shop_id = _get_printify_auth()

    url = f"https://api.printify.com/v1/shops/{shop_id}/products.json"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }

    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    data = response.json()

    normalized_products = []

    for raw_product in data.get("data", []):
        option_value_names = {}

        for option in raw_product.get("options", []):
            for value in option.get("values", []):
                option_value_names[value.get("id")] = value.get("title", str(value.get("id", "")))

        enabled_variants = []

        for variant in raw_product.get("variants", []):
            if not variant.get("is_enabled", False):
                continue

            option_titles = [
                option_value_names.get(option_id, str(option_id))
                for option_id in variant.get("options", [])
            ]

            enabled_variants.append(
                {
                    "id": variant.get("id"),
                    "title": " / ".join(option_titles) if option_titles else variant.get("title", ""),
                    "price": Decimal(str(variant.get("price", 0))) / Decimal("100"),
                    "production_cost": (
                        Decimal(str(variant.get("cost", 0))) / Decimal("100")
                        if variant.get("cost") is not None
                        else None
                    ),
                    "is_available": variant.get("is_available", True),
                }
            )

        prices = [variant["price"] for variant in enabled_variants]
        image_url = ""
        images = raw_product.get("images", [])
        if images:
            image_url = images[0].get("src", "")

        normalized_products.append(
            {
                "id": raw_product.get("id", ""),
                "title": raw_product.get("title", "Untitled product"),
                "description": raw_product.get("description", "") or "",
                "image": image_url,
                "variants": enabled_variants,
                "price": min(prices) if prices else Decimal("0.00"),
            }
        )

    return normalized_products

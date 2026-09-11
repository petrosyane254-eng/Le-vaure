from django.conf import settings
from django.utils.translation import get_language


def shop_context(request):
    cart = request.session.get("cart", {})

    return {
        "cart_count": sum(cart.values()),
        "available_languages": settings.LANGUAGES,
        "current_language": get_language(),
    }

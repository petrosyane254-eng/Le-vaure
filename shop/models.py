from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password, check_password
from django.urls import reverse


# =========================================================
# CATEGORY
# =========================================================

class Category(models.Model):
    name = models.CharField(
        max_length=80,
        unique=True,
    )

    slug = models.SlugField(
        max_length=80,
        unique=True,
    )

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


# =========================================================
# MY PRODUCTS / CUSTOM PRODUCTS
# =========================================================

class Product(models.Model):
    name = models.CharField(
        max_length=160,
    )

    slug = models.SlugField(
        max_length=180,
        unique=True,
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
    )

    description = models.TextField()

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    image = models.ImageField(
        upload_to="products/",
        blank=True,
        null=True,
    )

    stock = models.PositiveIntegerField(
        default=0,
    )

    featured = models.BooleanField(
        default=True,
    )

    active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "My Product"
        verbose_name_plural = "My Products"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse(
            "product",
            kwargs={"slug": self.slug},
        )


# =========================================================
# MY PRODUCT GALLERY IMAGES
# =========================================================

class ProductImage(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images",
    )

    image = models.ImageField(
        upload_to="products/gallery/",
    )

    is_primary = models.BooleanField(
        default=False,
    )

    sort_order = models.PositiveIntegerField(
        default=0,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = [
            "-is_primary",
            "sort_order",
            "id",
        ]

        verbose_name = "Product Image"
        verbose_name_plural = "Product Images"

    def __str__(self):
        return f"{self.product.name} - Image {self.pk}"


# =========================================================
# ORDERS
# =========================================================

class PrintifyProduct(models.Model):
    printify_id = models.CharField(max_length=100, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    active = models.BooleanField(default=True)
    featured = models.BooleanField(default=True)
    sync_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Printify Product"
        verbose_name_plural = "Printify Products"
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title


class PrintifyProductImage(models.Model):
    product = models.ForeignKey(
        PrintifyProduct, on_delete=models.CASCADE, related_name="images"
    )
    printify_url = models.URLField(blank=True)
    custom_image = models.ImageField(upload_to="printify_products/", blank=True, null=True)
    is_primary = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Printify Product Image"
        verbose_name_plural = "Printify Product Images"
        ordering = ["sort_order", "id"]


class PrintifyVariant(models.Model):
    product = models.ForeignKey(
        PrintifyProduct, on_delete=models.CASCADE, related_name="variants"
    )
    printify_variant_id = models.PositiveBigIntegerField(unique=True)
    title = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    production_cost = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    available = models.BooleanField(default=True)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Printify Variant"
        verbose_name_plural = "Printify Variants"
        ordering = ["id"]

    def __str__(self):
        return self.title


class Order(models.Model):
    STATUS = [
        ("new", "New"),
        ("paid", "Paid"),
        ("processing", "Processing"),
        ("shipped", "Shipped"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    full_name = models.CharField(
        max_length=160,
    )

    email = models.EmailField()

    address = models.TextField()

    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS,
        default="new",
    )

    # PAYMENT

    payment_method = models.CharField(
        max_length=30,
        blank=True,
        default="",
    )

    stripe_checkout_session_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
    )

    stripe_payment_intent_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    paid_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    # SHIPPING

    phone = models.CharField(
        max_length=50,
        blank=True,
        default="",
    )

    country = models.CharField(
        max_length=2,
        blank=True,
        default="",
    )

    region = models.CharField(
        max_length=120,
        blank=True,
        default="",
    )

    street = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    apartment = models.CharField(
        max_length=120,
        blank=True,
        default="",
    )

    city = models.CharField(
        max_length=120,
        blank=True,
        default="",
    )

    postal_code = models.CharField(
        max_length=40,
        blank=True,
        default="",
    )

    delivery_notes = models.TextField(
        blank=True,
        default="",
    )

    shipping_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    printify_order_id = models.CharField(
        max_length=120, blank=True, default="", db_index=True
    )
    printify_status = models.CharField(max_length=80, blank=True, default="")
    printify_submitted_at = models.DateTimeField(blank=True, null=True)
    printify_error = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Order"
        verbose_name_plural = "Orders"

    def __str__(self):
        if self.pk:
            return f"SW-{self.pk:06d} — {self.full_name}"

        return self.full_name


# =========================================================
# ORDER ITEMS
# =========================================================

class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
    )

    quantity = models.PositiveIntegerField()

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    @property
    def subtotal(self):
        if self.quantity is None or self.price is None:
            return 0

        return self.quantity * self.price

    def __str__(self):
        return f"{self.product} x {self.quantity}"


# =========================================================
# EMAIL VERIFICATION
# =========================================================

class PrintifyOrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="printify_items")
    product = models.ForeignKey(
        PrintifyProduct, on_delete=models.PROTECT, related_name="order_items"
    )
    variant = models.ForeignKey(
        PrintifyVariant, on_delete=models.PROTECT, related_name="order_items"
    )
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def subtotal(self):
        if self.quantity is None or self.price is None:
            return 0
        return self.quantity * self.price


class EmailVerification(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="email_verification",
    )

    code_hash = models.CharField(
        max_length=200,
    )

    expires_at = models.DateTimeField()

    attempts = models.PositiveIntegerField(
        default=0,
    )

    last_sent_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return f"Email verification for {self.user.username}"


# =========================================================
# WISHLIST
# =========================================================

class Wishlist(models.Model):
    printify_product = models.ForeignKey(
        PrintifyProduct,
        on_delete=models.CASCADE,
        related_name="wishlisted_by",
        blank=True,
        null=True,
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="wishlist_items",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="wishlisted_by",
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-created_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["user", "printify_product"],
                name="unique_user_wishlist_printify_product",
            ),
            models.UniqueConstraint(
                fields=[
                    "user",
                    "product",
                ],
                name="unique_user_wishlist_product",
            ),
        ]

    def __str__(self):
        if self.product:
            return (
                f"{self.user.username} — "
                f"{self.product.name}"
            )

        return (
            f"{self.user.username} — "
            "Wishlist item"
        )


# =========================================================
# SITE ACCESS / PRIVATE SHOP
# =========================================================

class SiteAccessSettings(models.Model):
    maintenance_mode = models.BooleanField(
        default=True,
        verbose_name="Private shop enabled",
    )

    access_password = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Access password",
        help_text=(
            "Visitors must enter this password while "
            "private shop mode is enabled."
        ),
    )

    class Meta:
        verbose_name = "Site Access"
        verbose_name_plural = "Site Access"

    def __str__(self):
        return "LE VAURÉ Site Access"

    def set_access_password(self, raw_password):
        if raw_password:
            self.access_password = make_password(raw_password)
        else:
            self.access_password = ""

    def check_access_password(self, raw_password):
        if not self.access_password:
            return False

        return check_password(
            raw_password,
            self.access_password,
        )

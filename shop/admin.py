from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import User
from django.db.models import Sum
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from unfold.admin import ModelAdmin, TabularInline
from unfold.sites import UnfoldAdminSite

from .models import (
    Category,
    Product,
    ProductImage,
    Order,
    OrderItem,
    EmailVerification,
    Wishlist,
    SiteAccessSettings,
)


# =========================================================
# ADMIN BRANDING
# =========================================================

class SouthwardAdminSite(UnfoldAdminSite):

    # Disabled so Unfold can render its own dashboard.


    def each_context(self, request):

        context = super().each_context(request)

        today = timezone.localdate()
        today_orders = Order.objects.filter(created_at__date=today)

        context.update(
            stats={
                "orders_today": today_orders.count(),
                "today_revenue": (
                    today_orders.exclude(status="cancelled").aggregate(
                        total=Sum("total")
                    )["total"]
                    or 0
                ),
                "total_revenue": (
                    Order.objects.exclude(status="cancelled").aggregate(
                        total=Sum("total")
                    )["total"]
                    or 0
                ),
                "pending_orders": Order.objects.filter(
                    status__in=["new", "paid", "processing"]
                ).count(),
                "low_stock": Product.objects.filter(
                    active=True,
                    stock__gt=0,
                    stock__lte=5,
                ).count(),
                "out_of_stock": Product.objects.filter(
                    active=True,
                    stock=0,
                ).count(),
                "products": Product.objects.count(),
                "active_products": Product.objects.filter(active=True).count(),
                "customers": get_user_model().objects.filter(is_staff=False).count(),
                "wishlist_items": Wishlist.objects.count(),
            },
            product_sections=[
                {
                    "title": _("My Products"),
                    "description": _("Products created and managed inside this shop."),
                    "count": Product.objects.count(),
                    "url": "admin:shop_product_changelist",
                },
            ],
            recent_orders=Order.objects.select_related("user").order_by("-created_at")[:7],
            low_stock_products=(
                Product.objects.filter(
                    active=True,
                    stock__lte=5,
                )
                .select_related("category")
                .order_by("stock", "name")[:7]
            ),
        )

        return context


admin.site = SouthwardAdminSite()
admin.site.site_header = _("LE VAURÉ ADMIN")
admin.site.site_title = _("LE VAURÉ Control Center")
admin.site.index_title = _("Store Control Center")
admin.site.register(User, DjangoUserAdmin)

admin.site.site_header = _("LE VAURÉ ADMIN")
admin.site.site_title = _("LE VAURÉ Control Center")
admin.site.index_title = _("Store Control Center")


# =========================================================
# SITE ACCESS / PRIVATE SHOP
# =========================================================

class SiteAccessSettingsForm(forms.ModelForm):
    password = forms.CharField(
        required=False,
        label=_("Access password"),
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "new-password",
                "placeholder": _("Enter a new access password"),
            }
        ),
        help_text=(
            _("Enter a new password to set or change it. ")
            + _("Leave blank to keep the current password.")
        ),
    )

    class Meta:
        model = SiteAccessSettings
        fields = (
            "maintenance_mode",
            "password",
        )

    def save(self, commit=True):
        obj = super().save(commit=False)

        raw_password = self.cleaned_data.get("password", "")
        if raw_password:
            obj.set_access_password(raw_password)

        if commit:
            obj.save()

        return obj


@admin.register(SiteAccessSettings, site=admin.site)
class SiteAccessSettingsAdmin(ModelAdmin):
    form = SiteAccessSettingsForm

    list_display = (
        "maintenance_mode",
        "password_configured",
    )

    fields = (
        "maintenance_mode",
        "password",
    )

    def has_add_permission(self, request):
        # Only one SiteAccessSettings row is needed.
        if SiteAccessSettings.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        # Keep the singleton settings row available.
        return False

    @admin.display(
        description=_("Password"),
        boolean=True,
    )
    def password_configured(self, obj):
        return bool(obj.access_password)


# =========================================================
# CATEGORY
# =========================================================

@admin.register(Category, site=admin.site)
class CategoryAdmin(ModelAdmin):

    list_display = (
        "name",
        "slug",
        "product_count",
    )

    search_fields = (
        "name",
        "slug",
    )

    prepopulated_fields = {
        "slug": ("name",),
    }

    ordering = (
        "name",
    )

    @admin.display(description=_("Products"))
    def product_count(self, obj):
        return obj.products.count()


# =========================================================
# MY PRODUCT IMAGE INLINE
# =========================================================

class ProductImageInline(TabularInline):
    model = ProductImage
    extra = 1

    fields = (
        "image_preview",
        "image",
        "is_primary",
        "sort_order",
    )

    readonly_fields = (
        "image_preview",
    )

    @admin.display(description="Preview")
    def image_preview(self, obj):
        if not obj or not obj.image:
            return _("No image")

        return format_html(
            '<img src="{}" style="'
            'width:80px;'
            'height:80px;'
            'object-fit:cover;'
            'background:#f4f4f2;'
            'border:1px solid #ddd;'
            'border-radius:10px;'
            'padding:4px;'
            '" />',
            obj.image.url,
        )


# =========================================================
# MY PRODUCTS
# =========================================================

@admin.register(Product, site=admin.site)
class ProductAdmin(ModelAdmin):

    class Media:
        css = {
            "all": (
                "css/admin.css",
            )
        }

    list_display = (
        "image_preview",
        "name",
        "category",
        "price_display",
        "stock_display",
        "featured",
        "active",
        "created_at",
    )

    list_display_links = (
        "image_preview",
        "name",
    )

    list_editable = (
        "featured",
        "active",
    )

    list_filter = (
        "active",
        "featured",
        "category",
        "created_at",
    )

    search_fields = (
        "name",
        "slug",
        "description",
        "category__name",
    )

    prepopulated_fields = {
        "slug": ("name",),
    }

    ordering = (
        "-created_at",
    )

    list_per_page = 25

    list_select_related = (
        "category",
    )

    readonly_fields = (
        "large_image_preview",
        "created_at",
    )

    inlines = (
        ProductImageInline,
    )

    fieldsets = (
        (
            "PRODUCT",
            {
                "fields": (
                    "name",
                    "slug",
                    "category",
                    "description",
                )
            },
        ),
        (
            "PRICE & STOCK",
            {
                "fields": (
                    "price",
                    "stock",
                )
            },
        ),
        (
            "MEDIA",
            {
                "fields": (
                    "image",
                    "large_image_preview",
                )
            },
        ),
        (
            "STORE VISIBILITY",
            {
                "fields": (
                    "active",
                    "featured",
                )
            },
        ),
        (
            "SYSTEM",
            {
                "fields": (
                    "created_at",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )

    actions = (
        "make_active",
        "make_inactive",
        "make_featured",
        "remove_featured",
        "set_out_of_stock",
    )

    @admin.display(description="Image")
    def image_preview(self, obj):

        if obj.image:
            return format_html(
                '<img src="{}" style="'
                'width:54px;'
                'height:54px;'
                'object-fit:contain;'
                'background:#f1f1ef;'
                'border:1px solid #ddd;'
                'border-radius:8px;'
                'padding:4px;'
                '" />',
                obj.image.url,
            )

        return format_html(
            '<div style="'
            'width:54px;'
            'height:54px;'
            'display:flex;'
            'align-items:center;'
            'justify-content:center;'
            'background:#eee;'
            'border-radius:8px;'
            'font-size:9px;'
            'color:#777;'
            '">NO IMAGE</div>'
        )

    @admin.display(description=_("Preview"))
    def large_image_preview(self, obj):

        if not obj or not obj.image:
            return "No image uploaded."

        return format_html(
            '<img src="{}" style="'
            'max-width:320px;'
            'max-height:320px;'
            'object-fit:contain;'
            'background:#f4f4f2;'
            'padding:20px;'
            'border:1px solid #ddd;'
            'border-radius:12px;'
            '" />',
            obj.image.url,
        )

    @admin.display(description="Price", ordering="price")
    def price_display(self, obj):
        return format_html(
            "<strong>${}</strong>",
            obj.price,
        )

    @admin.display(description="Stock", ordering="stock")
    def stock_display(self, obj):

        if obj.stock == 0:
            return format_html(
                '<span class="sw-stock sw-stock-out">'
                'OUT OF STOCK'
                '</span>'
            )

        if obj.stock <= 5:
            return format_html(
                '<span class="sw-stock sw-stock-low">'
                '{} LOW'
                '</span>',
                obj.stock,
            )

        return format_html(
            '<span class="sw-stock sw-stock-good">'
            '{}'
            '</span>',
            obj.stock,
        )

    @admin.action(description="Activate selected products")
    def make_active(self, request, queryset):

        updated = queryset.update(active=True)

        self.message_user(
            request,
            f"{updated} product(s) activated.",
        )

    @admin.action(description="Deactivate selected products")
    def make_inactive(self, request, queryset):

        updated = queryset.update(active=False)

        self.message_user(
            request,
            f"{updated} product(s) deactivated.",
        )

    @admin.action(description="Mark selected as featured")
    def make_featured(self, request, queryset):

        updated = queryset.update(featured=True)

        self.message_user(
            request,
            f"{updated} product(s) featured.",
        )

    @admin.action(description="Remove selected from featured")
    def remove_featured(self, request, queryset):

        updated = queryset.update(featured=False)

        self.message_user(
            request,
            f"{updated} product(s) removed from featured.",
        )

    @admin.action(description="Set selected products stock to 0")
    def set_out_of_stock(self, request, queryset):

        updated = queryset.update(stock=0)

        self.message_user(
            request,
            f"{updated} product(s) marked out of stock.",
        )


# =========================================================
# ORDER ITEM INLINE
# =========================================================

class OrderItemInline(TabularInline):

    model = OrderItem

    extra = 0

    readonly_fields = (
        "product",
        "quantity",
        "price",
        "subtotal_display",
    )

    can_delete = False

    @admin.display(description=_("Subtotal"))
    def subtotal_display(self, obj):

        if not obj.pk:
            return "-"

        return f"${obj.subtotal}"


# =========================================================
# ORDERS
# =========================================================

@admin.register(Order, site=admin.site)
class OrderAdmin(ModelAdmin):

    class Media:
        css = {
            "all": (
                "css/admin.css",
            )
        }

    list_display = (
        "order_number",
        "full_name",
        "email",
        "total_display",
        "status_badge",
        "created_at",
    )

    list_display_links = (
        "order_number",
        "full_name",
    )

    list_filter = (
        "status",
        "created_at",
    )

    search_fields = (
        "full_name",
        "email",
        "address",
        "user__username",
        "user__email",
    )

    ordering = (
        "-created_at",
    )

    date_hierarchy = "created_at"

    list_per_page = 30

    list_select_related = (
        "user",
    )

    readonly_fields = (
        "order_number_detail",
        "created_at",
        "total",
    )

    inlines = (
        OrderItemInline,
    )

    fieldsets = (
        (
            _("ORDER"),
            {
                "fields": (
                    "order_number_detail",
                    "status",
                    "created_at",
                )
            },
        ),
        (
            _("CUSTOMER"),
            {
                "fields": (
                    "user",
                    "full_name",
                    "email",
                )
            },
        ),
        (
            _("DELIVERY"),
            {
                "fields": (
                    "address",
                )
            },
        ),
        (
            _("PAYMENT"),
            {
                "fields": (
                    "total",
                )
            },
        ),
    )

    actions = (
        "mark_new",
        "mark_paid",
        "mark_processing",
        "mark_shipped",
        "mark_completed",
        "mark_cancelled",
    )

    @admin.display(description=_("Order"), ordering="id")
    def order_number(self, obj):

        return f"SW-{obj.pk:06d}"

    @admin.display(description=_("Order Number"))
    def order_number_detail(self, obj):

        if not obj or not obj.pk:
            return _("Created after saving.")

        return format_html(
            '<strong class="sw-order-number-detail">'
            'SW-{}'
            '</strong>',
            f"{obj.pk:06d}",
        )

    @admin.display(description=_("Total"), ordering="total")
    def total_display(self, obj):

        return format_html(
            '<strong class="sw-order-total">${}</strong>',
            obj.total,
        )

    @admin.display(description=_("Status"), ordering="status")
    def status_badge(self, obj):

        css_class = f"sw-order-{obj.status}"

        return format_html(
            '<span class="sw-order-status {}">'
            '{}'
            '</span>',
            css_class,
            obj.get_status_display().upper(),
        )

    def get_search_results(
        self,
        request,
        queryset,
        search_term,
    ):

        queryset, use_distinct = super().get_search_results(
            request,
            queryset,
            search_term,
        )

        clean_term = (
            search_term
            .strip()
            .upper()
            .replace("SW-", "")
            .replace("SW", "")
        )

        if clean_term.isdigit():

            order_id = int(clean_term)

            queryset |= self.model.objects.filter(
                pk=order_id
            )

        return queryset, use_distinct

    def _change_status(
        self,
        request,
        queryset,
        status,
        label,
    ):

        updated = queryset.update(
            status=status,
        )

        self.message_user(
            request,
            _("%(count)s order(s) marked %(label)s.") % {"count": updated, "label": label},
        )

    @admin.action(description=_("Mark selected orders as NEW"))
    def mark_new(self, request, queryset):
        self._change_status(
            request,
            queryset,
            "new",
            "NEW",
        )

    @admin.action(description=_("Mark selected orders as PAID"))
    def mark_paid(self, request, queryset):
        self._change_status(
            request,
            queryset,
            "paid",
            "PAID",
        )

    @admin.action(description=_("Mark selected orders as PROCESSING"))
    def mark_processing(self, request, queryset):
        self._change_status(
            request,
            queryset,
            "processing",
            "PROCESSING",
        )

    @admin.action(description=_("Mark selected orders as SHIPPED"))
    def mark_shipped(self, request, queryset):
        self._change_status(
            request,
            queryset,
            "shipped",
            "SHIPPED",
        )

    @admin.action(description=_("Mark selected orders as COMPLETED"))
    def mark_completed(self, request, queryset):
        self._change_status(
            request,
            queryset,
            "completed",
            "COMPLETED",
        )

    @admin.action(description=_("Mark selected orders as CANCELLED"))
    def mark_cancelled(self, request, queryset):
        self._change_status(
            request,
            queryset,
            "cancelled",
            "CANCELLED",
        )


# =========================================================
# EMAIL VERIFICATION
# =========================================================

@admin.register(EmailVerification, site=admin.site)
class EmailVerificationAdmin(ModelAdmin):

    list_display = (
        "user",
        "expires_at",
        "attempts",
        "last_sent_at",
    )

    search_fields = (
        "user__username",
        "user__email",
    )

    readonly_fields = (
        "code_hash",
        "last_sent_at",
    )

    list_filter = (
        "last_sent_at",
        "expires_at",
    )

    ordering = (
        "-last_sent_at",
    )


# =========================================================
# WISHLIST
# =========================================================

@admin.register(Wishlist, site=admin.site)
class WishlistAdmin(ModelAdmin):

    list_display = (
        "user",
        "product",
        "created_at",
    )

    search_fields = (
        "user__username",
        "user__email",
        "product__name",
    )

    list_filter = (
        "created_at",
        "product__category",
    )

    ordering = (
        "-created_at",
    )

    readonly_fields = (
        "created_at",
    )

    list_select_related = (
        "user",
        "product",
    )


# =========================================================
# ORDER ITEM DIRECT ADMIN
# =========================================================

@admin.register(OrderItem, site=admin.site)
class OrderItemAdmin(ModelAdmin):

    list_display = (
        "order",
        "product",
        "quantity",
        "price",
        "subtotal_display",
    )

    search_fields = (
        "order__id",
        "product__name",
    )

    list_filter = (
        "product__category",
    )

    list_select_related = (
        "order",
        "product",
    )

    @admin.display(description="Subtotal")
    def subtotal_display(self, obj):
        return f"${obj.subtotal}"

from django.contrib import admin

from .models import Tip


@admin.register(Tip)
class TipAdmin(admin.ModelAdmin):
    list_display = ("creator", "sender", "amount_rupees", "status", "created_at", "paid_at")
    list_filter = ("status",)
    search_fields = ("creator__username", "sender__username", "razorpay_order_id", "razorpay_payment_id")
    readonly_fields = [field.name for field in Tip._meta.fields]

    @admin.display(description="Amount (₹)")
    def amount_rupees(self, tip):
        return tip.amount_paise / 100

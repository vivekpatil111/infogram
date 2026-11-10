from django.conf import settings
from django.db import models


class Tip(models.Model):
    """"Tipping for Utility" (Infogram_Pivot.md): pay a creator whose post helped.

    Money is collected through Razorpay into the platform account; `paid` tips
    are what creators are owed. Paying creators out (Razorpay Route / bank
    transfer) is a separate, later step.
    """

    class Status(models.TextChoices):
        CREATED = "created", "Created"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"

    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="tips_sent")
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tips_received")
    post = models.ForeignKey("posts.Post", on_delete=models.SET_NULL, null=True, blank=True, related_name="tips")
    amount_paise = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, default="INR")
    message = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.CREATED, db_index=True)
    razorpay_order_id = models.CharField(max_length=64, unique=True)
    razorpay_payment_id = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["creator", "status", "-created_at"])]

    def __str__(self):
        return f"₹{self.amount_paise / 100:.0f} to {self.creator} ({self.status})"

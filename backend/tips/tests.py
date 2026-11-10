import hashlib
import hmac
import json
from unittest import mock

from django.test import override_settings

from config.testutils import InfogramAPITestCase
from notifications.models import Notification
from tips.models import Tip

KEYS = {"RAZORPAY_KEY_ID": "rzp_test_abc", "RAZORPAY_KEY_SECRET": "secret123", "RAZORPAY_WEBHOOK_SECRET": "hook456"}


def sign(message, secret):
    return hmac.new(secret.encode(), message.encode() if isinstance(message, str) else message, hashlib.sha256).hexdigest()


@override_settings(**KEYS)
class TipTests(InfogramAPITestCase):
    def setUp(self):
        super().setUp()
        self.creator, self.fan = self.make_user("helpful"), self.make_user("grateful")
        self.post = self.make_post(self.creator)

    def order(self, amount=50, **extra):
        with mock.patch("tips.razorpay.create_order", return_value={"id": f"order_{amount}_{len(extra)}"}) as create:
            response = self.as_user(self.fan).post("/api/v1/tips/", {"creator": "helpful", "amount": amount, "post_id": self.post.id, "message": " Thanks!! ", **extra}, format="json")
        return response, create

    def test_config_and_validation(self):
        config = self.as_user(self.fan).get("/api/v1/tips/config/").data
        self.assertEqual((config["enabled"], config["key_id"]), (True, "rzp_test_abc"))
        self.assertEqual(self.order(amount=5)[0].status_code, 400)
        self.assertEqual(self.order(amount=9000)[0].status_code, 400)
        with mock.patch("tips.razorpay.create_order") as create:
            own = self.as_user(self.creator).post("/api/v1/tips/", {"creator": "helpful", "amount": 50}, format="json")
        self.assertEqual(own.status_code, 400)
        create.assert_not_called()
        with override_settings(RAZORPAY_KEY_ID="", RAZORPAY_KEY_SECRET=""):
            self.assertFalse(self.as_user(self.fan).get("/api/v1/tips/config/").data["enabled"])
            self.assertEqual(self.order()[0].status_code, 503)

    def test_checkout_signature_marks_paid_once_and_notifies(self):
        response, create = self.order(amount=100)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(create.call_args.kwargs["amount_paise"], 10000)
        order_id = response.data["order_id"]
        bad = self.as_user(self.fan).post("/api/v1/tips/verify/", {"razorpay_order_id": order_id, "razorpay_payment_id": "pay_1", "razorpay_signature": "nope"}, format="json")
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(Tip.objects.get().status, "failed")

        response, _ = self.order(amount=100, extra_field=1)
        order_id = response.data["order_id"]
        body = {"razorpay_order_id": order_id, "razorpay_payment_id": "pay_2", "razorpay_signature": sign(f"{order_id}|pay_2", "secret123")}
        ok = self.as_user(self.fan).post("/api/v1/tips/verify/", body, format="json")
        self.assertEqual(ok.data, {"status": "paid", "amount": 100.0, "creator": "helpful"})
        self.as_user(self.fan).post("/api/v1/tips/verify/", body, format="json")  # repeat is harmless
        self.assertEqual(Notification.objects.filter(recipient=self.creator, notification_type="tip").count(), 1)
        received = self.as_user(self.creator).get("/api/v1/tips/received/").data
        self.assertEqual((received["total"], received["count"], received["results"][0]["message"]), (100.0, 1, "Thanks!!"))
        self.assertEqual(self.as_user(self.fan).get("/api/v1/tips/sent/").data["count"], 1)

    def test_webhook_requires_signature_and_is_idempotent(self):
        response, _ = self.order()
        order_id = response.data["order_id"]
        event = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {"id": "pay_9", "order_id": order_id}}}}).encode()
        self.client.force_authenticate(None)
        forged = self.client.post("/api/v1/tips/webhook/", event, content_type="application/json", HTTP_X_RAZORPAY_SIGNATURE="bad")
        self.assertEqual(forged.status_code, 400)
        for _ in range(2):
            ok = self.client.post("/api/v1/tips/webhook/", event, content_type="application/json", HTTP_X_RAZORPAY_SIGNATURE=sign(event, "hook456"))
            self.assertEqual(ok.status_code, 200)
        tip = Tip.objects.get()
        self.assertEqual((tip.status, tip.razorpay_payment_id), ("paid", "pay_9"))

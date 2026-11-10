from config.testutils import InfogramAPITestCase
from messaging.models import Conversation


class MessagingTests(InfogramAPITestCase):
    def setUp(self):
        super().setUp()
        self.me = self.make_user("me.user")
        self.friend = self.make_user("friend")
        self.third = self.make_user("third")
        self.client = self.as_user(self.me)

    def test_direct_thread_is_reused(self):
        first = self.client.post("/api/v1/conversations/", {"participant_ids": [self.friend.id]}, format="json")
        self.assertEqual(first.status_code, 201, first.data)
        again = self.client.post("/api/v1/conversations/", {"participant_ids": [str(self.friend.id)]}, format="json")
        self.assertEqual(again.status_code, 200)
        self.assertEqual(again.data["id"], first.data["id"])
        # The other side opening a DM lands in the same thread too.
        reverse = self.as_user(self.friend).post("/api/v1/conversations/", {"participant_ids": [self.me.id]}, format="json")
        self.assertEqual(reverse.data["id"], first.data["id"])

        group = self.client.post(
            "/api/v1/conversations/", {"participant_ids": [self.friend.id, self.third.id]}, format="json"
        )
        self.assertEqual(group.status_code, 201)
        self.assertEqual(Conversation.objects.count(), 2)

    def test_invalid_participants(self):
        for ids in ([], [self.me.id], ["abc"], [999999]):
            response = self.client.post("/api/v1/conversations/", {"participant_ids": ids}, format="json")
            self.assertEqual(response.status_code, 400, ids)

    def test_send_read_unread_counts(self):
        conversation_id = self.client.post(
            "/api/v1/conversations/", {"participant_ids": [self.friend.id]}, format="json"
        ).data["id"]
        friend_client = self.as_user(self.friend)
        sent = friend_client.post(f"/api/v1/conversations/{conversation_id}/messages/", {"body": "Hi!"}, format="json")
        self.assertEqual(sent.status_code, 201)
        self.assertEqual(friend_client.post(f"/api/v1/conversations/{conversation_id}/messages/", {"body": "  "}, format="json").status_code, 400)

        me_client = self.as_user(self.me)
        listing = me_client.get("/api/v1/conversations/").data
        self.assertEqual(listing[0]["unread_count"], 1)
        self.assertEqual(listing[0]["last_message"]["body"], "Hi!")
        self.assertEqual({p["username"] for p in listing[0]["participants"]}, {"me.user", "friend"})
        self.assertEqual(me_client.get("/api/v1/notifications/unread-count/").data["messages"], 1)

        self.assertEqual(me_client.post(f"/api/v1/conversations/{conversation_id}/read/").data["updated"], 1)
        self.assertEqual(me_client.get("/api/v1/conversations/").data[0]["unread_count"], 0)

        messages = me_client.get(f"/api/v1/conversations/{conversation_id}/messages/").data
        self.assertEqual([m["body"] for m in messages["results"]], ["Hi!"])

    def test_non_members_cannot_read(self):
        conversation_id = self.client.post(
            "/api/v1/conversations/", {"participant_ids": [self.friend.id]}, format="json"
        ).data["id"]
        outsider = self.as_user(self.third)
        self.assertEqual(outsider.get(f"/api/v1/conversations/{conversation_id}/messages/").status_code, 404)

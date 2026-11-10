from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

from .models import Conversation, ConversationMember, Message
from .serializers import MAX_MESSAGE_LENGTH, MessageSerializer


class ConversationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.group_name = f"conversation_{self.conversation_id}"
        user = self.scope.get("user")
        if isinstance(user, AnonymousUser) or not await self.is_member(user.id):
            await self.close(code=4403)
            return
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        body = str(content.get("body", "")).strip()
        if not body:
            await self.send_json({"error": "Message body is required."})
            return
        if len(body) > MAX_MESSAGE_LENGTH:
            await self.send_json({"error": f"Messages are limited to {MAX_MESSAGE_LENGTH} characters."})
            return
        if await self.is_blocked():
            await self.send_json({"error": "You can't message this account."})
            return
        message = await self.create_message(body)
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "chat.message", "message": message},
        )

    async def chat_message(self, event):
        await self.send_json(event["message"])

    @database_sync_to_async
    def is_member(self, user_id):
        return ConversationMember.objects.filter(conversation_id=self.conversation_id, user_id=user_id).exists()

    @database_sync_to_async
    def is_blocked(self):
        from .views import conversation_blocked

        return conversation_blocked(Conversation.objects.get(pk=self.conversation_id), self.scope["user"])

    @database_sync_to_async
    def create_message(self, body):
        message = Message.objects.create(
            conversation_id=self.conversation_id,
            sender=self.scope["user"],
            body=body,
        )
        Conversation.objects.filter(id=self.conversation_id).update(updated_at=timezone.now())
        from .views import push_new_message

        push_new_message(message)
        return MessageSerializer(message).data

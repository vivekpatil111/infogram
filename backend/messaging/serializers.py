from rest_framework import serializers

from .models import Conversation, Message


MAX_MESSAGE_LENGTH = 5000


class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ["id", "conversation", "sender", "body", "created_at", "read_at"]
        read_only_fields = ["id", "conversation", "sender", "created_at", "read_at"]
        extra_kwargs = {"body": {"max_length": MAX_MESSAGE_LENGTH}}

    def get_sender(self, message):
        return {
            "id": message.sender_id,
            "username": message.sender.username,
            "avatar_url": message.sender.avatar_url,
        }

    def validate_body(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Message body is required.")
        return value


class ConversationSerializer(serializers.ModelSerializer):
    participants = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Conversation
        fields = ["id", "participants", "last_message", "unread_count", "created_at", "updated_at"]
        read_only_fields = fields

    def get_participants(self, conversation):
        return [
            {
                "id": member.user_id,
                "username": member.user.username,
                "avatar_url": member.user.avatar_url,
            }
            for member in conversation.members.all()
        ]

    def get_last_message(self, conversation):
        message = conversation.messages.select_related("sender").order_by("-created_at", "-id").first()
        return MessageSerializer(message).data if message else None

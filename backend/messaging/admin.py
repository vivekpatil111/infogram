from django.contrib import admin

from .models import Conversation, ConversationMember, Message


admin.site.register([Conversation, ConversationMember, Message])

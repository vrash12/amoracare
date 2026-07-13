# django-ai-service/apps/legal_guidance/serializers.py

from rest_framework import serializers


class LegalGuidanceRequestSerializer(serializers.Serializer):
    question = serializers.CharField(
        required=True,
        allow_blank=False,
        max_length=2000,
        trim_whitespace=True,
        error_messages={
            "required": "Please enter a question.",
            "blank": "Question cannot be empty.",
            "max_length": "Question is too long. Please keep it under 2000 characters.",
        },
    )

    parent_context = serializers.DictField(
        required=False,
        default=dict,
        allow_empty=True,
    )

    conversation_history = serializers.ListField(
        required=False,
        default=list,
        allow_empty=True,
        child=serializers.DictField(),
    )

    def validate_parent_context(self, value):
        if value is None:
            return {}

        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "Parent context must be a valid object."
            )

        return value

    def validate_conversation_history(self, value):
        if value is None:
            return []

        if not isinstance(value, list):
            raise serializers.ValidationError(
                "Conversation history must be a list."
            )

        cleaned_history = []

        for item in value[-10:]:
            if not isinstance(item, dict):
                continue

            role = item.get("role")
            content = item.get("content")

            if not role or not content:
                continue

            cleaned_history.append({
                "role": str(role)[:50],
                "content": str(content)[:2000],
            })

        return cleaned_history
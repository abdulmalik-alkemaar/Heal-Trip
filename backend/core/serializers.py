from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "avatar_url",
            "date_joined",
        ]
        read_only_fields = [
            "id",
            "username",
            "email",
            "date_joined",
        ]

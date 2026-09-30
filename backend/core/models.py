from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom User model with social auth fields."""

    avatar_url = models.URLField(max_length=500, blank=True, default="")

    def __str__(self):
        return self.email or self.username

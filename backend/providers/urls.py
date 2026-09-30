from django.urls import path

from . import views

urlpatterns = [
    path("providers/", views.ProviderListView.as_view(), name="provider-list"),
    path("specialties/", views.SpecialtyListView.as_view(), name="specialty-list"),
]

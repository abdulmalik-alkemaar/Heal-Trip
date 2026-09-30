"""Public, read-only directory endpoints (transparency: reviewers can see exactly the
data the agent is allowed to recommend from)."""

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny

from .choices import City, LanguageCode, SpecialtyCode
from .models import Doctor, Specialty
from .serializers import DoctorCardSerializer, SpecialtySerializer


@extend_schema(
    tags=["directory"],
    parameters=[
        OpenApiParameter("specialty", enum=SpecialtyCode.values),
        OpenApiParameter("city", enum=City.values),
        OpenApiParameter("language", enum=LanguageCode.values),
    ],
)
class ProviderListView(generics.ListAPIView):
    """Active doctors, filterable by specialty, city and spoken language."""

    serializer_class = DoctorCardSerializer
    permission_classes = [AllowAny]
    throttle_scope = "public"

    def get_queryset(self):
        params = self.request.query_params
        qs = (
            Doctor.objects.filter(is_active=True, hospital__is_active=True)
            .select_related("hospital")
            .prefetch_related("specialties")
            .order_by("hospital__city", "name_en")
        )
        filters = {
            "specialty": (SpecialtyCode.values, "specialties__code"),
            "city": (City.values, "hospital__city"),
        }
        for param, (allowed, lookup) in filters.items():
            value = params.get(param)
            if value:
                if value not in allowed:
                    raise ValidationError({param: [f"Must be one of {allowed}."]})
                qs = qs.filter(**{lookup: value})
        language = params.get("language")
        if language:
            if language not in LanguageCode.values:
                raise ValidationError({"language": [f"Must be one of {LanguageCode.values}."]})
            qs = qs.filter(languages__contains=[language])
        return qs.distinct()


@extend_schema(tags=["directory"])
class SpecialtyListView(generics.ListAPIView):
    queryset = Specialty.objects.all()
    serializer_class = SpecialtySerializer
    permission_classes = [AllowAny]
    pagination_class = None
    throttle_scope = "public"

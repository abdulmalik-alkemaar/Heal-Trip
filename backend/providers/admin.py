from django.contrib import admin

from .models import AvailabilitySlot, Doctor, Hospital, Specialty


@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    list_display = ("code", "name_en", "name_ar")
    search_fields = ("code", "name_en", "name_ar")


@admin.register(Hospital)
class HospitalAdmin(admin.ModelAdmin):
    list_display = (
        "name_en",
        "city",
        "has_emergency",
        "emergency_phone",
        "accreditation",
        "is_active",
    )
    list_filter = ("city", "has_emergency", "is_active", "accreditation")
    search_fields = ("name_en", "name_ar", "address_en", "address_ar")


class AvailabilitySlotInline(admin.TabularInline):
    model = AvailabilitySlot
    extra = 0
    fields = ("start_time", "duration_minutes", "is_booked")


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = (
        "name_en",
        "hospital",
        "specialty_codes",
        "languages",
        "offers_second_opinion",
        "offers_telemedicine",
        "consultation_fee_sar",
        "is_active",
    )
    list_filter = (
        "specialties",
        "hospital__city",
        "offers_second_opinion",
        "offers_telemedicine",
        "is_active",
    )
    search_fields = ("name_en", "name_ar", "hospital__name_en")
    filter_horizontal = ("specialties",)
    list_select_related = ("hospital",)
    inlines = [AvailabilitySlotInline]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("specialties")

    @admin.display(description="Specialties")
    def specialty_codes(self, obj: Doctor) -> str:
        return ", ".join(s.code for s in obj.specialties.all())


@admin.register(AvailabilitySlot)
class AvailabilitySlotAdmin(admin.ModelAdmin):
    list_display = ("doctor", "start_time", "duration_minutes", "is_booked")
    list_filter = ("is_booked", "doctor__hospital__city")
    search_fields = ("doctor__name_en",)
    date_hierarchy = "start_time"
    list_select_related = ("doctor",)

from django.contrib import admin
from .models import Magnolia


@admin.register(Magnolia)
class MagnoliaAdmin(admin.ModelAdmin):
    list_display = ['species', 'location_description', 'date_observed', 'blooming_status', 'logged_by', 'date_logged']
    list_filter = ['species', 'blooming_status', 'date_observed']
    search_fields = ['location_description', 'notes', 'logged_by']
    date_hierarchy = 'date_observed'

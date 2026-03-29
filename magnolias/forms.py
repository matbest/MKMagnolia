from django import forms
from .models import Magnolia


class MagnoliaForm(forms.ModelForm):
    class Meta:
        model = Magnolia
        fields = [
            'species',
            'location_description',
            'latitude',
            'longitude',
            'date_observed',
            'blooming_status',
            'notes',
            'image',
            'logged_by',
        ]
        widgets = {
            'date_observed': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 4}),
        }

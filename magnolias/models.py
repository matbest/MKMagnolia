from django.db import models
from django.urls import reverse


class Magnolia(models.Model):
    SPECIES_CHOICES = [
        ('stellata', 'Magnolia stellata (Star Magnolia)'),
        ('soulangeana', 'Magnolia × soulangeana (Saucer Magnolia)'),
        ('grandiflora', 'Magnolia grandiflora (Southern Magnolia)'),
        ('liliiflora', 'Magnolia liliiflora (Lily Magnolia)'),
        ('kobus', 'Magnolia kobus'),
        ('other', 'Other / Unknown'),
    ]

    BLOOMING_STATUS_CHOICES = [
        ('budding', 'Budding'),
        ('blooming', 'Blooming'),
        ('past_bloom', 'Past Bloom'),
        ('dormant', 'Dormant'),
    ]

    species = models.CharField(max_length=50, choices=SPECIES_CHOICES, default='other')
    location_description = models.CharField(
        max_length=255,
        help_text='e.g. Campbell Park, Central Milton Keynes',
    )
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        help_text='Decimal latitude (e.g. 52.041)',
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        help_text='Decimal longitude (e.g. -0.759)',
    )
    date_observed = models.DateField(help_text='Date the magnolia was observed')
    blooming_status = models.CharField(
        max_length=20, choices=BLOOMING_STATUS_CHOICES, default='dormant',
    )
    notes = models.TextField(blank=True)
    image = models.ImageField(upload_to='magnolias/', blank=True, null=True)
    logged_by = models.CharField(max_length=100, blank=True)
    date_logged = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_observed', '-date_logged']
        verbose_name = 'Magnolia'
        verbose_name_plural = 'Magnolias'

    def __str__(self):
        return f'{self.get_species_display()} at {self.location_description} ({self.date_observed})'

    def get_absolute_url(self):
        return reverse('magnolias:detail', kwargs={'pk': self.pk})

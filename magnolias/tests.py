import datetime
from django.test import TestCase, Client
from django.urls import reverse
from .models import Magnolia


class MagnoliaModelTest(TestCase):
    def setUp(self):
        self.magnolia = Magnolia.objects.create(
            species='stellata',
            location_description='Campbell Park, Central Milton Keynes',
            date_observed=datetime.date(2024, 3, 15),
            blooming_status='blooming',
            notes='Beautiful white flowers',
            logged_by='Alice',
        )

    def test_str_representation(self):
        expected = 'Magnolia stellata (Star Magnolia) at Campbell Park, Central Milton Keynes (2024-03-15)'
        self.assertEqual(str(self.magnolia), expected)

    def test_get_absolute_url(self):
        url = self.magnolia.get_absolute_url()
        self.assertEqual(url, f'/{self.magnolia.pk}/')

    def test_default_ordering(self):
        second = Magnolia.objects.create(
            species='kobus',
            location_description='Willen Lake',
            date_observed=datetime.date(2024, 4, 1),
            blooming_status='budding',
        )
        magnolias = list(Magnolia.objects.all())
        self.assertEqual(magnolias[0], second)
        self.assertEqual(magnolias[1], self.magnolia)

    def test_optional_fields_blank(self):
        m = Magnolia.objects.create(
            species='other',
            location_description='Test Location',
            date_observed=datetime.date(2024, 1, 1),
        )
        self.assertEqual(m.notes, '')
        self.assertEqual(m.logged_by, '')
        self.assertIsNone(m.latitude)
        self.assertIsNone(m.longitude)


class MagnoliaListViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('magnolias:list')

    def test_list_view_empty(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No magnolias logged yet')

    def test_list_view_with_entries(self):
        Magnolia.objects.create(
            species='stellata',
            location_description='Campbell Park',
            date_observed=datetime.date(2024, 3, 15),
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Campbell Park')
        self.assertContains(response, '1 sighting logged')


class MagnoliaDetailViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.magnolia = Magnolia.objects.create(
            species='soulangeana',
            location_description='Willen Lake',
            date_observed=datetime.date(2024, 3, 20),
            blooming_status='blooming',
            notes='Pink and white flowers',
            logged_by='Bob',
        )

    def test_detail_view(self):
        url = reverse('magnolias:detail', kwargs={'pk': self.magnolia.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Willen Lake')
        self.assertContains(response, 'Pink and white flowers')
        self.assertContains(response, 'Bob')

    def test_detail_view_404(self):
        url = reverse('magnolias:detail', kwargs={'pk': 9999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class MagnoliaCreateViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('magnolias:create')

    def test_create_view_get(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Log a Magnolia')

    def test_create_view_post_valid(self):
        data = {
            'species': 'stellata',
            'location_description': 'Bradwell Abbey, MK',
            'date_observed': '2024-03-10',
            'blooming_status': 'blooming',
            'notes': 'Lovely tree',
            'logged_by': 'Charlie',
        }
        response = self.client.post(self.url, data)
        self.assertEqual(Magnolia.objects.count(), 1)
        magnolia = Magnolia.objects.first()
        self.assertEqual(magnolia.location_description, 'Bradwell Abbey, MK')
        self.assertRedirects(response, magnolia.get_absolute_url())

    def test_create_view_post_invalid(self):
        data = {'species': 'stellata'}  # missing required fields
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Magnolia.objects.count(), 0)


class MagnoliaUpdateViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.magnolia = Magnolia.objects.create(
            species='stellata',
            location_description='Old Location',
            date_observed=datetime.date(2024, 3, 1),
        )
        self.url = reverse('magnolias:update', kwargs={'pk': self.magnolia.pk})

    def test_update_view_get(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Edit Magnolia')

    def test_update_view_post_valid(self):
        data = {
            'species': 'kobus',
            'location_description': 'New Location',
            'date_observed': '2024-04-01',
            'blooming_status': 'budding',
        }
        response = self.client.post(self.url, data)
        self.magnolia.refresh_from_db()
        self.assertEqual(self.magnolia.location_description, 'New Location')
        self.assertEqual(self.magnolia.species, 'kobus')
        self.assertRedirects(response, self.magnolia.get_absolute_url())


class MagnoliaDeleteViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.magnolia = Magnolia.objects.create(
            species='stellata',
            location_description='To Be Deleted',
            date_observed=datetime.date(2024, 3, 1),
        )
        self.url = reverse('magnolias:delete', kwargs={'pk': self.magnolia.pk})

    def test_delete_view_get(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Confirm Delete')

    def test_delete_view_post(self):
        response = self.client.post(self.url)
        self.assertEqual(Magnolia.objects.count(), 0)
        self.assertRedirects(response, reverse('magnolias:list'))

from django.urls import path
from . import views

app_name = 'magnolias'

urlpatterns = [
    path('', views.magnolia_list, name='list'),
    path('add/', views.magnolia_create, name='create'),
    path('<int:pk>/', views.magnolia_detail, name='detail'),
    path('<int:pk>/edit/', views.magnolia_update, name='update'),
    path('<int:pk>/delete/', views.magnolia_delete, name='delete'),
]

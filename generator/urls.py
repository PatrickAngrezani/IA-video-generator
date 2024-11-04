from django.urls import path
from . import views

urlpatterns = [
    path('api/generate-video/', views.home, name='home'),
]

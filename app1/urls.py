from django.urls import path
from . import views

urlpatterns = [
    path('', views.tasa_cambio_flujo_view, name='tasa_flujo'),
]
from django.urls import path
from . import views

urlpatterns = [
    path('', views.tasa_cambio_flujo_view, name='tasa_flujo'),
    path('api/dashboard/', views.api_dashboard_data, name='api_dashboard_data'),
    path('api/turno/crear/', views.api_crear_turno, name='api_crear_turno'),
    path('api/turno/atender/', views.api_atender_turno, name='api_atender_turno'),
    path('api/turno/derivar/', views.api_derivar_turno, name='api_derivar_turno'),
    path('api/turno/finalizar/', views.api_finalizar_turno, name='api_finalizar_turno'),
    path('api/turno/reiniciar/', views.api_reiniciar_simulacion, name='api_reiniciar_simulacion'),
]
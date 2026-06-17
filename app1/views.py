from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta
from .models import Turno

def tasa_cambio_flujo_view(request):
    """
    Vista que calcula la derivada discreta (ΔN / Δt) 
    para la tasa de llegadas en la última hora.
    """
    tiempo_fin = timezone.now()
    tiempo_inicio = tiempo_fin - timedelta(hours=1)
    
    # Δt: Diferencia de tiempo en minutos
    delta_t = (tiempo_fin - tiempo_inicio).total_seconds() / 60.0
    
    # ΔN: Cantidad de turnos registrados en ese intervalo
    delta_n = Turno.objects.filter(
        tiempo_llegada__gte=tiempo_inicio,
        tiempo_llegada__lte=tiempo_fin
    ).count()
    
    # Derivada discreta de flujo (clientes por minuto)
    tasa = delta_n / delta_t if delta_t > 0 else 0.0
    
    context = {
        'tasa_flujo': tasa,
        'intervalo_minutos': delta_t,
        'cantidad_llegadas': delta_n
    }
    
    # Retornamos los datos al template para visualizarlos
    return render(request, 'tasa_flujo.html', context)

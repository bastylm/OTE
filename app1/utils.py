from django.utils import timezone
from .models import Turno

def calcular_tasa_llegadas(tiempo_inicio, tiempo_fin):
    """
    Calcula la derivada discreta (ΔN / Δt) de llegadas 
    en un intervalo de tiempo dado.
    ΔN = Número de nuevos turnos en el intervalo.
    Δt = Diferencia de tiempo en minutos.
    """
    # Δt: Diferencia de tiempo en minutos
    delta_t = (tiempo_fin - tiempo_inicio).total_seconds() / 60.0
    
    if delta_t <= 0:
        return 0.0  # Evitar división por cero si los tiempos son iguales
        
    # ΔN: Cantidad de turnos registrados en ese intervalo
    delta_n = Turno.objects.filter(
        tiempo_llegada__gte=tiempo_inicio,
        tiempo_llegada__lte=tiempo_fin
    ).count()
    
    # Derivada discreta (clientes por minuto)
    return delta_n / delta_t
from django.utils import timezone
from datetime import timedelta
from django.db.models import Avg, Count
from .models import Turno

def obtener_metricas_cola(ventana_llegada_minutos=15, ventana_atencion_minutos=30):
    ahora = timezone.now()
    
    # 1. Tasa de llegada (lambda)
    inicio_llegada = ahora - timedelta(minutes=ventana_llegada_minutos)
    num_llegadas = Turno.objects.filter(
        tiempo_llegada__gte=inicio_llegada,
        tiempo_llegada__lte=ahora
    ).count()
    
    lam = num_llegadas / ventana_llegada_minutos if ventana_llegada_minutos > 0 else 0.0
    
    # 2. Aceleración de llegada (d_lambda / dt)
    # Comparamos la tasa de llegada de los últimos W minutos con los W minutos anteriores
    w = 5  # Ventana de 5 minutos
    t1_inicio = ahora - timedelta(minutes=w)
    num_llegadas_t1 = Turno.objects.filter(
        tiempo_llegada__gte=t1_inicio,
        tiempo_llegada__lte=ahora
    ).count()
    lam_t1 = num_llegadas_t1 / w
    
    t2_inicio = ahora - timedelta(minutes=2*w)
    num_llegadas_t2 = Turno.objects.filter(
        tiempo_llegada__gte=t2_inicio,
        tiempo_llegada__lt=t1_inicio
    ).count()
    lam_t2 = num_llegadas_t2 / w
    
    aceleracion = (lam_t1 - lam_t2) / w
    
    # 3. Tasa de atención (mu)
    # Turnos que salieron de Atención en la ventana de atención
    inicio_atencion = ahora - timedelta(minutes=ventana_atencion_minutos)
    turnos_atendidos_ventana = Turno.objects.filter(
        tiempo_salida__gte=inicio_atencion,
        tiempo_salida__lte=ahora,
        tiempo_atencion__isnull=False
    )
    num_atendidos = turnos_atendidos_ventana.count()
    
    # Cantidad de módulos de atención activos
    # Módulos que atendieron en la ventana o están atendiendo actualmente
    modulos_activos_ids = set()
    for t in turnos_atendidos_ventana:
        if t.modulo_atencion is not None:
            modulos_activos_ids.add(t.modulo_atencion)
            
    modulos_actuales = Turno.objects.filter(estado='Atencion', modulo_atencion__isnull=False)
    for t in modulos_actuales:
        if t.modulo_atencion is not None:
            modulos_activos_ids.add(t.modulo_atencion)
            
    c = len(modulos_activos_ids)
    if c == 0:
        c = 1  # Por lo menos 1 módulo teórico
        
    # Calcular mu
    if num_atendidos > 0:
        # mu es atenciones por módulo por minuto en esa ventana
        mu = num_atendidos / (c * ventana_atencion_minutos)
    else:
        # Fallback a histórico general para estimar mu (1 / tiempo promedio de atención)
        turnos_historicos = Turno.objects.filter(
            tiempo_atencion__isnull=False,
            tiempo_salida__isnull=False
        )
        total_duracion = 0
        for t in turnos_historicos:
            total_duracion += (t.tiempo_salida - t.tiempo_atencion).total_seconds() / 60.0
            
        if turnos_historicos.count() > 0 and total_duracion > 0:
            avg_duration = total_duracion / turnos_historicos.count()
            mu = 1.0 / avg_duration if avg_duration > 0 else 0.2
        else:
            mu = 0.2  # Valor por defecto: 5 minutos por cliente (0.2 clientes/minuto)
            
    # 4. Factor de utilización (rho)
    rho = lam / (c * mu) if (c * mu) > 0 else 0.0
    
    # 5. Métricas de colas (Aproximación de Teoría de Colas)
    lq = 0.0
    wq = 0.0
    if rho < 1.0 and rho > 0.0:
        # Para c=1 (M/M/1):
        if c == 1:
            lq = (rho ** 2) / (1 - rho)
            wq = lq / lam if lam > 0 else 0.0
        else:
            # Aproximación general para M/M/c
            lq = (rho ** (c + 1)) / (1 - rho)
            wq = lq / lam if lam > 0 else 0.0
    else:
        # Si está saturado, estimamos de forma determinista basado en la cola real de espera
        lq = Turno.objects.filter(estado='Espera').count()
        wq = lq * (1.0 / mu) / c if mu > 0 else 0.0
        
    # Criterio de alerta de colapso
    # Alerta si la aceleración de llegada supera la tasa de servicio (criterio del prompt)
    # o si el factor de utilización es crítico (rho >= 1.0)
    alerta_colapso = (aceleracion > mu) or (rho >= 1.0)
    
    return {
        'lambda': round(lam, 3),
        'mu': round(mu, 3),
        'aceleracion': round(aceleracion, 4),
        'rho': round(rho, 3),
        'modulos_activos': c,
        'lq': round(lq, 1),
        'wq_minutos': round(wq, 2),
        'alerta_colapso': alerta_colapso,
        'num_llegadas': num_llegadas,
        'num_atendidos': num_atendidos
    }

def calcular_matriz_transicion():
    # Inicialización de la matriz con valores lógicos base (para que nunca quede vacía)
    matrix = {
        'Espera': {'Espera': 1.0, 'Atencion': 0.0, 'Derivado': 0.0, 'Finalizado': 0.0},
        'Atencion': {'Espera': 0.0, 'Atencion': 1.0, 'Derivado': 0.0, 'Finalizado': 0.0},
        'Derivado': {'Espera': 0.0, 'Atencion': 0.0, 'Derivado': 1.0, 'Finalizado': 0.0},
        'Finalizado': {'Espera': 0.0, 'Atencion': 0.0, 'Derivado': 0.0, 'Finalizado': 1.0}
    }
    
    total = Turno.objects.count()
    if total == 0:
        # Valores de ejemplo representativos para simulación vacía
        matrix['Espera'] = {'Espera': 0.7, 'Atencion': 0.3, 'Derivado': 0.0, 'Finalizado': 0.0}
        matrix['Atencion'] = {'Espera': 0.0, 'Atencion': 0.6, 'Derivado': 0.1, 'Finalizado': 0.3}
        matrix['Derivado'] = {'Espera': 0.0, 'Atencion': 0.2, 'Derivado': 0.5, 'Finalizado': 0.3}
        matrix['Finalizado'] = {'Espera': 0.0, 'Atencion': 0.0, 'Derivado': 0.0, 'Finalizado': 1.0}
        return matrix
        
    # Transiciones desde Espera
    # E -> A: turnos que pasaron a atención (tienen tiempo_atencion no nulo)
    # E -> E: turnos que siguen en Espera (estado == 'Espera')
    e_a = Turno.objects.filter(tiempo_atencion__isnull=False).count()
    e_e = Turno.objects.filter(estado='Espera').count()
    sum_e = e_e + e_a
    if sum_e > 0:
        matrix['Espera']['Espera'] = round(e_e / sum_e, 3)
        matrix['Espera']['Atencion'] = round(e_a / sum_e, 3)
        matrix['Espera']['Derivado'] = 0.0
        matrix['Espera']['Finalizado'] = 0.0
        
    # Transiciones desde Atencion
    # A -> D: turnos que se derivaron (estado == 'Derivado' o fue_derivado == True)
    # A -> F: turnos que finalizaron sin ser derivados (estado == 'Finalizado' y fue_derivado == False)
    # A -> A: turnos que siguen en Atencion (estado == 'Atencion')
    a_a = Turno.objects.filter(estado='Atencion').count()
    a_d = Turno.objects.filter(estado='Derivado').count() + Turno.objects.filter(estado='Finalizado', fue_derivado=True).count()
    a_f = Turno.objects.filter(estado='Finalizado', fue_derivado=False).count()
    
    sum_a = a_a + a_d + a_f
    if sum_a > 0:
        matrix['Atencion']['Espera'] = 0.0
        matrix['Atencion']['Atencion'] = round(a_a / sum_a, 3)
        matrix['Atencion']['Derivado'] = round(a_d / sum_a, 3)
        matrix['Atencion']['Finalizado'] = round(a_f / sum_a, 3)
        
    # Transiciones desde Derivado
    # D -> F: turnos derivados y ahora finalizados (estado == 'Finalizado' y fue_derivado == True)
    # D -> A: turnos derivados que volvieron a atención (estado == 'Atencion' y fue_derivado == True)
    # D -> D: turnos que siguen en Derivado (estado == 'Derivado')
    d_d = Turno.objects.filter(estado='Derivado').count()
    d_f = Turno.objects.filter(estado='Finalizado', fue_derivado=True).count()
    d_a = Turno.objects.filter(estado='Atencion', fue_derivado=True).count()
    
    sum_d = d_d + d_f + d_a
    if sum_d > 0:
        matrix['Derivado']['Espera'] = 0.0
        matrix['Derivado']['Atencion'] = round(d_a / sum_d, 3)
        matrix['Derivado']['Derivado'] = round(d_d / sum_d, 3)
        matrix['Derivado']['Finalizado'] = round(d_f / sum_d, 3)
        
    # Finalizado es un estado absorbente
    matrix['Finalizado']['Espera'] = 0.0
    matrix['Finalizado']['Atencion'] = 0.0
    matrix['Finalizado']['Derivado'] = 0.0
    matrix['Finalizado']['Finalizado'] = 1.0
    
    return matrix

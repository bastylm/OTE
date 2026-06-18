import json
import random
from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.db.models import F

from .models import Turno
from .analytics import obtener_metricas_cola, calcular_matriz_transicion

# Nombres aleatorios para la simulación
NOMBRES_SIMULADOS = [
    "Juan Pérez", "María González", "Carlos Muñoz", "Ana Silva", "Diego Rojas",
    "Laura Díaz", "Luis Herrera", "Sofía Castro", "Pedro Valenzuela", "Elena Soto",
    "Andrés Contreras", "Camila Tapia", "Gabriel Carrasco", "Valentina Sepúlveda",
    "José Morales", "Antonia Fuentes", "Manuel Mendoza", "Francisca Araya",
    "Christian Castillo", "Catalina Reyes"
]

def tasa_cambio_flujo_view(request):
    """Retorna la interfaz del dashboard principal."""
    return render(request, 'tasa_flujo.html')

def api_dashboard_data(request):
    """API que retorna todas las métricas, matriz de transición y estados de cola."""
    metricas = obtener_metricas_cola()
    matriz = calcular_matriz_transicion()
    
    # Listas de turnos según su estado actual
    turnos_espera = Turno.objects.filter(estado='Espera').order_by('tiempo_llegada')
    turnos_atencion = Turno.objects.filter(estado='Atencion').order_by('tiempo_atencion')
    turnos_derivados = Turno.objects.filter(estado='Derivado').order_by('tiempo_salida')
    
    # Serialización simple
    espera_list = [{
        'id': t.id,
        'nombre': t.nombre_cliente,
        'tiempo_espera': t.tiempo_espera_minutos(),
        'tiempo_llegada': t.tiempo_llegada.strftime("%H:%M:%S")
    } for t in turnos_espera]

    atencion_list = [{
        'id': t.id,
        'nombre': t.nombre_cliente,
        'modulo': t.modulo_atencion,
        'tiempo_atencion': t.tiempo_atencion_minutos(),
        'tiempo_inicio_atencion': t.tiempo_atencion.strftime("%H:%M:%S") if t.tiempo_atencion else ""
    } for t in turnos_atencion]

    derivado_list = [{
        'id': t.id,
        'nombre': t.nombre_cliente,
        'tiempo_espera_total': t.tiempo_espera_minutos() + t.tiempo_atencion_minutos(),
        'tiempo_salida': t.tiempo_salida.strftime("%H:%M:%S") if t.tiempo_salida else ""
    } for t in turnos_derivados]

    # Últimos 10 finalizados
    ultimos_finalizados = Turno.objects.filter(estado='Finalizado').order_by('-tiempo_salida')[:10]
    finalizados_list = [{
        'id': t.id,
        'nombre': t.nombre_cliente,
        'tiempo_espera': t.tiempo_espera_minutos(),
        'tiempo_atencion': t.tiempo_atencion_minutos(),
        'fue_derivado': t.fue_derivado,
        'tiempo_salida': t.tiempo_salida.strftime("%H:%M:%S") if t.tiempo_salida else ""
    } for t in ultimos_finalizados]

    # Datos históricos simulados para el gráfico de tasa de llegada (últimas 10 muestras en minutos)
    # Mostramos los últimos minutos en el gráfico para que la simulación se vea activa.
    ahora = timezone.now()
    muestras_chart = []
    for i in range(9, -1, -1):
        t_target = ahora - timezone.timedelta(minutes=i)
        llegadas_min = Turno.objects.filter(
            tiempo_llegada__minute=t_target.minute,
            tiempo_llegada__hour=t_target.hour,
            tiempo_llegada__day=t_target.day
        ).count()
        atendidos_min = Turno.objects.filter(
            tiempo_salida__minute=t_target.minute,
            tiempo_salida__hour=t_target.hour,
            tiempo_salida__day=t_target.day,
            estado='Finalizado'
        ).count()
        muestras_chart.append({
            'minuto': t_target.strftime("%H:%M"),
            'llegadas': llegadas_min,
            'atenciones': atendidos_min
        })

    response_data = {
        'metricas': metricas,
        'matriz_transicion': matriz,
        'colas': {
            'espera': espera_list,
            'atencion': atencion_list,
            'derivado': derivado_list,
            'finalizado': finalizados_list,
            'totales': {
                'espera': len(espera_list),
                'atencion': len(atencion_list),
                'derivado': len(derivado_list),
                'finalizado': Turno.objects.filter(estado='Finalizado').count()
            }
        },
        'muestras_grafico': muestras_chart
    }
    
    return JsonResponse(response_data)

@csrf_exempt
def api_crear_turno(request):
    """Crea un turno en estado Espera (simula ticketera IoT)."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body) if request.body else {}
        except ValueError:
            data = {}
            
        nombre = data.get('nombre_cliente')
        if not nombre:
            nombre = random.choice(NOMBRES_SIMULADOS) + f" ({random.randint(100, 999)})"
            
        nuevo_turno = Turno.objects.create(
            nombre_cliente=nombre,
            estado='Espera'
        )
        return JsonResponse({
            'status': 'success',
            'turno': {
                'id': nuevo_turno.id,
                'nombre': nuevo_turno.nombre_cliente,
                'estado': nuevo_turno.estado,
                'tiempo_llegada': nuevo_turno.tiempo_llegada.strftime("%H:%M:%S")
            }
        })
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

@csrf_exempt
def api_atender_turno(request):
    """Atiende al siguiente cliente en fila (simula llamado de módulo)."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body) if request.body else {}
        except ValueError:
            data = {}
            
        modulo = data.get('modulo_atencion', random.randint(1, 3))
        
        # Buscamos el turno más antiguo que esté en Espera o Derivado
        # Priorizamos Espera y luego Derivado si no hay en espera.
        siguiente_turno = Turno.objects.filter(estado='Espera').order_by('tiempo_llegada').first()
        if not siguiente_turno:
            siguiente_turno = Turno.objects.filter(estado='Derivado').order_by('tiempo_salida').first()
            
        if siguiente_turno:
            siguiente_turno.estado = 'Atencion'
            siguiente_turno.tiempo_atencion = timezone.now()
            siguiente_turno.modulo_atencion = modulo
            siguiente_turno.save()
            return JsonResponse({
                'status': 'success',
                'turno': {
                    'id': siguiente_turno.id,
                    'nombre': siguiente_turno.nombre_cliente,
                    'estado': siguiente_turno.estado,
                    'modulo': siguiente_turno.modulo_atencion,
                    'tiempo_atencion': siguiente_turno.tiempo_atencion.strftime("%H:%M:%S")
                }
            })
        return JsonResponse({'status': 'empty', 'message': 'No hay clientes en cola de espera o derivados'}, status=200)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

@csrf_exempt
def api_derivar_turno(request):
    """Deriva a un cliente en atención (simula derivación médica o comercial)."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body) if request.body else {}
        except ValueError:
            data = {}
            
        turno_id = data.get('turno_id')
        if turno_id:
            turno = Turno.objects.filter(id=turno_id, estado='Atencion').first()
        else:
            # Si no se envía ID, tomamos el más antiguo en atención
            turno = Turno.objects.filter(estado='Atencion').order_by('tiempo_atencion').first()
            
        if turno:
            turno.estado = 'Derivado'
            turno.tiempo_salida = timezone.now()
            turno.fue_derivado = True
            turno.save()
            return JsonResponse({
                'status': 'success',
                'turno': {
                    'id': turno.id,
                    'nombre': turno.nombre_cliente,
                    'estado': turno.estado,
                    'tiempo_salida': turno.tiempo_salida.strftime("%H:%M:%S")
                }
            })
        return JsonResponse({'status': 'empty', 'message': 'No se encontró un turno activo en atención para derivar'}, status=200)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

@csrf_exempt
def api_finalizar_turno(request):
    """Finaliza el trámite de un cliente (simula salida del sistema)."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body) if request.body else {}
        except ValueError:
            data = {}
            
        turno_id = data.get('turno_id')
        if turno_id:
            turno = Turno.objects.filter(id=turno_id).exclude(estado__in=['Finalizado', 'Espera']).first()
        else:
            # Tomamos el primero en atención
            turno = Turno.objects.filter(estado='Atencion').order_by('tiempo_atencion').first()
            if not turno:
                turno = Turno.objects.filter(estado='Derivado').order_by('tiempo_salida').first()
                
        if turno:
            turno.estado = 'Finalizado'
            if not turno.tiempo_salida or not turno.fue_derivado:
                turno.tiempo_salida = timezone.now()
            turno.save()
            return JsonResponse({
                'status': 'success',
                'turno': {
                    'id': turno.id,
                    'nombre': turno.nombre_cliente,
                    'estado': turno.estado,
                    'tiempo_salida': turno.tiempo_salida.strftime("%H:%M:%S")
                }
            })
        return JsonResponse({'status': 'empty', 'message': 'No hay turnos activos para finalizar'}, status=200)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

@csrf_exempt
def api_reiniciar_simulacion(request):
    """Elimina todos los registros de turnos para reiniciar la simulación."""
    if request.method == 'POST':
        Turno.objects.all().delete()
        return JsonResponse({'status': 'success', 'message': 'Simulación reiniciada con éxito'})
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

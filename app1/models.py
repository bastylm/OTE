from django.db import models
from django.utils import timezone

class Turno(models.Model):
    ESTADOS_TURNO = [
        ('Espera', 'En Espera'),
        ('Atencion', 'En Atención'),
        ('Derivado', 'Derivado'),
        ('Finalizado', 'Finalizado'),
    ]

    nombre_cliente = models.CharField(max_length=100)
    estado = models.CharField(max_length=20, choices=ESTADOS_TURNO, default='Espera')
    modulo_atencion = models.IntegerField(null=True, blank=True, verbose_name="Módulo de Atención")
    fue_derivado = models.BooleanField(default=False, verbose_name="¿Fue Derivado?")
    
    tiempo_llegada = models.DateTimeField(auto_now_add=True)
    tiempo_atencion = models.DateTimeField(null=True, blank=True)
    tiempo_salida = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.nombre_cliente} - {self.estado}"

    def tiempo_espera_minutos(self):
        """Calcula el tiempo que el cliente esperó (o lleva esperando) en minutos."""
        fin = self.tiempo_atencion if self.tiempo_atencion else timezone.now()
        return round((fin - self.tiempo_llegada).total_seconds() / 60.0, 2)

    def tiempo_atencion_minutos(self):
        """Calcula el tiempo que duró (o lleva durando) la atención en minutos."""
        if not self.tiempo_atencion:
            return 0.0
        fin = self.tiempo_salida if self.tiempo_salida else timezone.now()
        return round((fin - self.tiempo_atencion).total_seconds() / 60.0, 2)


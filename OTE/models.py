from django.db import models

class Turno(models.Model):
    ESTADOS_TURNO = [
        ('Espera', 'En Espera'),
        ('Atencion', 'En Atención'),
        ('Derivado', 'Derivado'),
    ]

    nombre_cliente = models.CharField(max_length=100)
    estado = models.CharField(max_length=20, choices=ESTADOS_TURNO, default='Espera')
    
    tiempo_llegada = models.DateTimeField(auto_now_add=True)
    tiempo_atencion = models.DateTimeField(null=True, blank=True)
    tiempo_salida = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.nombre_cliente} - {self.estado}"
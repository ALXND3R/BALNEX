import uuid
from django.db import models
from django.contrib.auth.models import User


def generar_codigo_unico():
    return uuid.uuid4().hex[:8].upper()


class Evento(models.Model):
    organizador = models.ForeignKey(User, on_delete=models.CASCADE)
    nombre_evento = models.CharField(max_length=100)
    lugar = models.CharField(max_length=150)
    fecha_evento = models.DateField()
    cupo_maximo = models.PositiveIntegerField()
    servicios = models.TextField(blank=True, null=True)
    descripcion = models.TextField(blank=True, null=True)
    codigo_invitacion = models.CharField(
        max_length=20, unique=True, default=generar_codigo_unico
    )

    def __str__(self):
        return self.nombre_evento


class Reservacion(models.Model):
    evento = models.ForeignKey(
        Evento, on_delete=models.CASCADE, related_name="reservaciones"
    )
    usuario = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="reservaciones"
    )
    nombre_cliente = models.CharField(max_length=100)
    hora_reserva = models.TimeField()
    numero_personas = models.PositiveIntegerField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre_cliente} - {self.evento.nombre_evento}"

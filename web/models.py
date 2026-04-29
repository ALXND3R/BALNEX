import uuid
from django.db import models

# Create your models here.

from django.db import models
from django.contrib.auth.models import User

def generar_codigo_unico():
    return uuid.uuid4().hex[:8].upper()

class Evento(models.Model):
    # 🔹 2. Añadimos el campo que guardará el código automáticamente
    codigo_invitacion = models.CharField(max_length=10, unique=True, default=generar_codigo_unico)
    
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mis_eventos', null=True, blank=True)
    nombre_evento = models.CharField(max_length=200)
    fecha_evento = models.DateField(null=True, blank=True)
    cupo_maximo = models.IntegerField(default=0)
    lugar = models.CharField(max_length=100, null=True, blank=True)
    descripcion = models.TextField(max_length=500, null=True, blank=True)
    servicios = models.CharField(max_length=255, blank=True, null=True)
    
    def __str__(self):
        return f"{self.nombre_evento} ({self.codigo_invitacion})"
    

class Reservacion(models.Model):
    id_reservacion = models.AutoField(primary_key=True)  # (cite: 38)
    nombre_cliente = models.CharField(max_length=100)  # (cite: 38)
    numero_personas = models.PositiveIntegerField()  # (cite: 39)
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE)  # (cite: 40)ç
    hora = models.TimeField(null=True, blank=True)

    class Meta:
        unique_together = ("evento", "nombre_cliente")  # Evita duplicados (cite: 18)

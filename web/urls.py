from django.urls import path
from .views import (
    VistaPaginaInicio,
    VistaPaginaAcercaDe,
    login_view,
    register_view,
    logout_view,
    detalle_y_reserva,
    crear_evento,# 🔹 1. Importamos la nueva vista aquí
)

urlpatterns = [
    path("", VistaPaginaInicio.as_view(), name="pagina_de_inicio"),
    path("nosotros/", VistaPaginaAcercaDe.as_view(), name="acerca_de"),
    # RUTAS para el sistema Balnex (Cita: 4, 18)
    path("evento/<int:id_evento>/", detalle_y_reserva, name="detalle_y_reserva"),
    # 🔹 2. Añadimos la ruta para crear un nuevo evento
    path("crear-evento/", crear_evento, name="crear_evento"),
    # Autenticación
    path("login/", login_view, name="login"),
    path("registro/", register_view, name="register"),
    path("logout/", logout_view, name="logout"),
    
]

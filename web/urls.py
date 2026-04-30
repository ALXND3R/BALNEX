from django.urls import path
from .views import (
    VistaPaginaInicio,
    VistaPaginaAcercaDe,
    login_view,
    register_view,
    logout_view,
    detalle_y_reserva,
    crear_evento,
)

urlpatterns = [
    path("", VistaPaginaInicio.as_view(), name="pagina_de_inicio"),
    path("nosotros/", VistaPaginaAcercaDe.as_view(), name="acerca_de"),
    path("evento/<int:id_evento>/", detalle_y_reserva, name="detalle_y_reserva"),
    path("crear-evento/", crear_evento, name="crear_evento"),

    path("login/", login_view, name="login"),
    path("registro/", register_view, name="register"),
    path("logout/", logout_view, name="logout"),
    
]

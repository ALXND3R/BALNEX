from django.urls import path
from .views import (
    VistaPaginaInicio,
    VistaPaginaAcercaDe,
    cambiar_password,
    login_view,
    recuperar_password,
    register_view,
    logout_view,
    detalle_y_reserva,
    crear_evento,
    buscar_evento,
    eliminar_evento,
    editar_evento,
    editar_reservacion,
    cancelar_reservacion,
)

urlpatterns = [
    path("", VistaPaginaInicio.as_view(), name="pagina_de_inicio"),
    path("nosotros/", VistaPaginaAcercaDe.as_view(), name="acerca_de"),
    path("evento/<int:evento_id>/", detalle_y_reserva, name="detalle_y_reserva"),
    path("crear-evento/", crear_evento, name="crear_evento"),
    path("buscar-evento/", buscar_evento, name="buscar_evento"),
    path("evento/<int:evento_id>/eliminar/", eliminar_evento, name="eliminar_evento"),
    path("login/", login_view, name="login"),
    path("registro/", register_view, name="register"),
    path("logout/", logout_view, name="logout"),
    path("evento/<int:evento_id>/editar/", editar_evento, name="editar_evento"),
    path(
        "reservacion/<int:reservacion_id>/editar/",
        editar_reservacion,
        name="editar_reservacion",
    ),
    path(
        "reservacion/<int:reservacion_id>/cancelar/",
        cancelar_reservacion,
        name="cancelar_reservacion",
    ),
    path("recuperar-password/", recuperar_password, name="recuperar_password"),
    path("cambiar-password/<uidb64>/<token>/", cambiar_password, name="cambiar_password"),
]

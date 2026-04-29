from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.cache import never_cache
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.db.models import Sum
from .models import Evento, Reservacion
from django.contrib.auth.mixins import LoginRequiredMixin

# Agrega estas importaciones al inicio de tu views.py
from django.contrib.auth.decorators import login_required
from django.contrib import messages


@method_decorator(never_cache, name="dispatch")
class VistaPaginaInicio(LoginRequiredMixin, TemplateView):
    template_name = "pagina_de_inicio.html"
    login_url = "/login/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # 🔹 Filtramos para que solo traiga los eventos del usuario logueado
        # Usamos self.request.user porque estamos dentro de una Clase (TemplateView)
        context["eventos"] = Evento.objects.filter(usuario=self.request.user).order_by(
            "-id"
        )

        return context


class VistaPaginaAcercaDe(TemplateView):
    template_name = "acerca_de.html"


@never_cache
def login_view(request):
    correo = request.GET.get("correo", "")

    if request.method == "POST":
        correo = request.POST.get("correo")
        password = request.POST.get("password")

        try:
            user_obj = User.objects.get(email=correo)
            user = authenticate(request, username=user_obj.username, password=password)
        except User.DoesNotExist:
            user = None

        if user:
            login(request, user)
            return redirect("pagina_de_inicio")
        else:
            return render(
                request, "login.html", {"error": "Datos incorrectos", "correo": correo}
            )

    return render(request, "login.html", {"correo": correo})


@never_cache
def register_view(request):
    if request.method == "POST":
        correo = request.POST.get("correo")
        password = request.POST.get("password")

        # 🔹 Validar formato real de email
        try:
            validate_email(correo)
        except ValidationError:
            return render(request, "register.html", {"error": "Correo no válido"})

        if not correo.endswith((".com", ".mx", ".edu", ".org")):
            return render(request, "register.html", {"error": "Dominio no permitido"})

        # 🔹 Evitar duplicados
        if User.objects.filter(email=correo).exists():
            return render(
                request, "register.html", {"error": "El correo ya está registrado"}
            )

        # 🔹 Crear usuario
        User.objects.create_user(username=correo, email=correo, password=password)

        # 🔹 Redirigir al login pasando el correo en la URL
        url_login = reverse("login")
        return redirect(f"{url_login}?correo={correo}")

    return render(request, "register.html")


def logout_view(request):
    logout(request)  # Esto destruye la sesión actual
    return redirect("login")  #


def gestion_eventos(request):
    # READ: Ver eventos disponibles [cite: 28, 58]
    eventos = Evento.objects.all()
    return render(request, "inicio.html", {"eventos": eventos})


# Función para manejar la lógica de Balnex
from django.utils import timezone  # Por si necesitas validar horas reales


def detalle_y_reserva(request, id_evento):
    evento = get_object_or_404(Evento, pk=id_evento)

    # Cálculos de disponibilidad
    asistentes = (
        Reservacion.objects.filter(evento=evento).aggregate(Sum("numero_personas"))[
            "numero_personas__sum"
        ]
        or 0
    )
    disponible = evento.cupo_maximo - asistentes
    ganancias = asistentes * 1500
    esta_lleno = disponible <= 0

    if request.method == "POST":
        nombre = request.POST.get("nombre_cliente")
        personas = int(request.POST.get("numero_personas", 0))
        # CAPTURAMOS LA HORA DEL FORMULARIO
        hora_seleccionada = request.POST.get("hora_reserva")

        # Validación: Cupo suficiente y que hayan enviado una hora
        if 0 < personas <= disponible and hora_seleccionada:
            try:
                Reservacion.objects.create(
                    evento=evento,
                    nombre_cliente=nombre,
                    numero_personas=personas,
                    hora=hora_seleccionada,  # Asegúrate que tu modelo Reservacion tenga este campo
                )
                messages.success(
                    request, f"¡Reserva confirmada para las {hora_seleccionada}!"
                )
            except Exception as e:
                messages.error(request, "Hubo un error al procesar tu reserva.")
        else:
            messages.error(request, "Datos inválidos o cupo insuficiente.")

        return redirect("detalle_y_reserva", id_evento=evento.id_evento)

    return render(
        request,
        "inicio.html",  # Cambia a "detalle.html" si creas uno nuevo
        {
            "evento": evento,
            "disponible": disponible,
            "ganancias": ganancias,
            "esta_lleno": esta_lleno,
        },
    )


@login_required(login_url="/login/")
def crear_evento(request):
    if request.method == "POST":
        # 1. Obtener los datos del formulario (los atributos 'name' del HTML)
        nombre = request.POST.get("nombre_evento")
        fecha = request.POST.get("fecha_evento")
        invitados = request.POST.get("cantidad_invitados")

        # 2. Los checkboxes devuelven una lista, la convertimos a texto separado por comas
        servicios_lista = request.POST.getlist("servicios")
        servicios_str = ", ".join(servicios_lista)  # Ej: "catering, fotografia"

        # 3. Guardar en la base de datos vinculado al usuario logueado
        Evento.objects.create(
            usuario=request.user,  # ¡Aquí es donde se vincula al usuario actual!
            nombre_evento=nombre,
            fecha_evento=fecha,
            cupo_maximo=invitados,  # Mapeamos los invitados al cupo máximo
            servicios=servicios_str,
        )

        # 4. Mensaje de éxito y redirección al inicio (dashboard)
        messages.success(
            request, "¡Tu evento se ha configurado y guardado exitosamente!"
        )
        return redirect("pagina_de_inicio")

    # Si la petición es GET, simplemente mostramos la página con el formulario
    return render(request, "crear_evento.html")

from decimal import Decimal
from datetime import timedelta

from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.test import Client, TestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils import timezone

from .models import ActividadEvento, Evento, NotificacionInterna, Reservacion, ServicioExtra


class BaseBalNexTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.organizador = User.objects.create_user(
            username="organizador",
            email="organizador@gmail.com",
            password="Password12345",
        )
        self.asistente = User.objects.create_user(
            username="asistente",
            email="asistente@gmail.com",
            password="Password12345",
        )
        self.otro = User.objects.create_user(
            username="otro",
            email="otro@gmail.com",
            password="Password12345",
        )
        self.evento = Evento.objects.create(
            organizador=self.organizador,
            nombre_evento="Evento principal",
            lugar="Salón Diamante",
            fecha_evento=timezone.localdate() + timedelta(days=10),
            cupo_maximo=20,
            precio_persona=Decimal("100.00"),
            categoria=Evento.CATEGORIA_GENERAL,
            descripcion="Evento de prueba",
        )

    def permitir_evento_en_sesion(self, evento=None):
        evento = evento or self.evento
        session = self.client.session
        session["eventos_permitidos"] = [evento.id]
        session.save()

    def datos_evento(self, **overrides):
        data = {
            "nombre_evento": "Evento nuevo",
            "fecha_evento": (timezone.localdate() + timedelta(days=20)).isoformat(),
            "cantidad_invitados": "30",
            "cupo_maximo": "30",
            "lugar": "Salón Diamante",
            "categoria": Evento.CATEGORIA_GENERAL,
            "precio_persona": "150.00",
            "descripcion": "Descripción",
        }
        data.update(overrides)
        return data

    def datos_reservacion(self, **overrides):
        data = {
            "nombre_cliente": "Cliente Uno",
            "numero_personas": "2",
            "hora_reserva": "18:30",
        }
        data.update(overrides)
        return data


class AuthTests(TestCase):
    def test_usuario_puede_registrarse(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "nuevo",
                "correo": "nuevo@gmail.com",
                "password": "Password12345",
                "confirmar_password": "Password12345",
            },
        )
        self.assertRedirects(response, reverse("login"))
        self.assertTrue(User.objects.filter(username="nuevo", email="nuevo@gmail.com").exists())

    def test_no_puede_registrar_username_repetido(self):
        User.objects.create_user(username="repetido", email="uno@gmail.com", password="x")
        response = self.client.post(
            reverse("register"),
            {
                "username": "repetido",
                "correo": "dos@gmail.com",
                "password": "Password12345",
                "confirmar_password": "Password12345",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "El usuario ya está registrado.")

    def test_no_puede_registrar_correo_repetido(self):
        User.objects.create_user(username="uno", email="dupe@gmail.com", password="x")
        response = self.client.post(
            reverse("register"),
            {
                "username": "dos",
                "correo": "dupe@gmail.com",
                "password": "Password12345",
                "confirmar_password": "Password12345",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "El correo ya está registrado.")

    def test_registro_rechaza_entradas_excesivamente_largas(self):
        texto_enorme = "a" * 10000
        response = self.client.post(
            reverse("register"),
            {
                "username": texto_enorme,
                "correo": f"{texto_enorme}@gmail.com",
                "password": texto_enorme,
                "confirmar_password": texto_enorme,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "no puede superar")
        self.assertFalse(User.objects.filter(username=texto_enorme).exists())

    def test_cambio_password_rechaza_password_excesiva(self):
        usuario = User.objects.create_user(
            username="recupera",
            email="recupera@gmail.com",
            password="Password12345",
        )
        uid = urlsafe_base64_encode(force_bytes(usuario.pk))
        token = default_token_generator.make_token(usuario)
        response = self.client.post(
            reverse("cambiar_password", args=[uid, token]),
            {
                "nueva_password": "a" * 10000,
                "confirmar_password": "a" * 10000,
            },
            follow=True,
        )
        self.assertContains(response, "no puede superar")

    def test_usuario_puede_iniciar_sesion_con_username_y_password(self):
        User.objects.create_user(username="usuario", email="usuario@gmail.com", password="Password12345")
        response = self.client.post(
            reverse("login"),
            {"username": "usuario", "password": "Password12345"},
        )
        self.assertRedirects(response, reverse("pagina_de_inicio"))

    def test_login_no_pide_correo(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password"')
        self.assertNotContains(response, 'name="correo"')

    def test_login_no_acepta_correo_como_identificador_principal(self):
        User.objects.create_user(username="usuario", email="usuario@gmail.com", password="Password12345")
        response = self.client.post(
            reverse("login"),
            {"username": "usuario@gmail.com", "password": "Password12345"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_funciona_correctamente(self):
        User.objects.create_user(username="usuario", email="usuario@gmail.com", password="Password12345")
        self.client.login(username="usuario", password="Password12345")
        response = self.client.get(reverse("logout"))
        self.assertRedirects(response, reverse("login"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_paginas_protegidas_redirigen_al_login(self):
        response = self.client.get(reverse("pagina_de_inicio"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])


class PaginasTests(BaseBalNexTestCase):
    def test_paginas_principales_responden(self):
        self.assertEqual(self.client.get(reverse("login")).status_code, 200)
        self.assertEqual(self.client.get(reverse("register")).status_code, 200)
        self.assertEqual(self.client.get(reverse("acerca_de")).status_code, 200)

    def test_panel_sin_login_redirige_y_con_login_responde(self):
        self.assertEqual(self.client.get(reverse("pagina_de_inicio")).status_code, 302)
        self.client.login(username="organizador", password="Password12345")
        self.assertEqual(self.client.get(reverse("pagina_de_inicio")).status_code, 200)

    def test_paginas_privadas_con_login_responden(self):
        self.client.login(username="organizador", password="Password12345")
        self.assertEqual(self.client.get(reverse("crear_evento")).status_code, 200)
        self.assertEqual(self.client.get(reverse("notificaciones")).status_code, 200)
        self.assertEqual(self.client.get(reverse("detalle_y_reserva", args=[self.evento.id])).status_code, 200)
        self.assertEqual(self.client.get(reverse("estadisticas_evento", args=[self.evento.id])).status_code, 200)
        self.assertEqual(self.client.get(reverse("editar_evento", args=[self.evento.id])).status_code, 200)

    def test_detalle_evento_ajeno_requiere_codigo_o_reserva(self):
        self.client.login(username="asistente", password="Password12345")
        response = self.client.get(reverse("detalle_y_reserva", args=[self.evento.id]))
        self.assertRedirects(response, reverse("pagina_de_inicio"))
        self.client.get(reverse("buscar_evento"), {"codigo": self.evento.codigo_invitacion})
        self.assertEqual(self.client.get(reverse("detalle_y_reserva", args=[self.evento.id])).status_code, 200)

    def test_estadisticas_y_edicion_solo_organizador(self):
        self.client.login(username="asistente", password="Password12345")
        self.assertEqual(self.client.get(reverse("estadisticas_evento", args=[self.evento.id])).status_code, 404)
        self.assertEqual(self.client.get(reverse("editar_evento", args=[self.evento.id])).status_code, 404)


class EventosTests(BaseBalNexTestCase):
    def test_usuario_autenticado_puede_crear_evento(self):
        self.client.login(username="organizador", password="Password12345")
        response = self.client.post(reverse("crear_evento"), self.datos_evento())
        self.assertRedirects(response, reverse("pagina_de_inicio"))
        self.assertTrue(Evento.objects.filter(nombre_evento="Evento nuevo", organizador=self.organizador).exists())
        self.assertTrue(ActividadEvento.objects.filter(mensaje="Evento creado.").exists())

    def test_crear_evento_rechaza_campos_excesivos(self):
        self.client.login(username="organizador", password="Password12345")
        response = self.client.post(
            reverse("crear_evento"),
            self.datos_evento(nombre_evento="E" * 10000),
        )
        self.assertRedirects(response, reverse("crear_evento"))
        self.assertFalse(Evento.objects.filter(nombre_evento="E" * 10000).exists())

    def test_usuario_solo_ve_sus_eventos_en_panel(self):
        Evento.objects.create(
            organizador=self.asistente,
            nombre_evento="Evento ajeno",
            lugar="Salón Diamante",
            fecha_evento=timezone.localdate() + timedelta(days=12),
            cupo_maximo=10,
        )
        self.client.login(username="organizador", password="Password12345")
        response = self.client.get(reverse("pagina_de_inicio"))
        eventos = response.context["eventos"]
        self.assertEqual([evento.organizador for evento in eventos], [self.organizador])

    def test_usuario_no_puede_editar_evento_ajeno(self):
        self.client.login(username="asistente", password="Password12345")
        response = self.client.post(reverse("editar_evento", args=[self.evento.id]), self.datos_evento())
        self.assertEqual(response.status_code, 404)

    def test_usuario_no_puede_eliminar_evento_ajeno(self):
        self.client.login(username="asistente", password="Password12345")
        response = self.client.post(reverse("eliminar_evento", args=[self.evento.id]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Evento.objects.filter(id=self.evento.id).exists())

    def test_cancelar_evento_no_borra_historial_ni_reservaciones(self):
        reservacion = Reservacion.objects.create(
            evento=self.evento,
            usuario=self.asistente,
            nombre_cliente="Cliente",
            hora_reserva="18:00",
            numero_personas=2,
        )
        ActividadEvento.objects.create(
            evento=self.evento,
            usuario=self.organizador,
            mensaje="Actividad previa.",
        )
        self.client.login(username="organizador", password="Password12345")

        response = self.client.post(reverse("eliminar_evento", args=[self.evento.id]))

        self.assertRedirects(response, reverse("pagina_de_inicio"))
        self.evento.refresh_from_db()
        self.assertFalse(self.evento.activo)
        self.assertTrue(Reservacion.objects.filter(id=reservacion.id).exists())
        self.assertTrue(self.evento.historial.filter(mensaje="Evento cancelado.").exists())

    def test_panel_solo_lista_eventos_activos(self):
        self.evento.activo = False
        self.evento.save(update_fields=["activo"])
        Evento.objects.create(
            organizador=self.organizador,
            nombre_evento="Evento activo",
            lugar="Salón Diamante",
            fecha_evento=timezone.localdate() + timedelta(days=12),
            cupo_maximo=10,
        )
        self.client.login(username="organizador", password="Password12345")

        response = self.client.get(reverse("pagina_de_inicio"))

        self.assertEqual(
            list(response.context["eventos"]),
            list(Evento.objects.filter(nombre_evento="Evento activo")),
        )

    def test_detalle_evento_inexistente_redirige_sin_404(self):
        self.client.login(username="organizador", password="Password12345")

        response = self.client.get(reverse("detalle_y_reserva", args=[999999]))

        self.assertRedirects(response, reverse("pagina_de_inicio"))

    def test_evento_cancelado_muestra_mensaje_y_rechaza_nuevas_reservaciones(self):
        self.evento.activo = False
        self.evento.save(update_fields=["activo"])
        self.client.login(username="asistente", password="Password12345")
        self.permitir_evento_en_sesion()

        response_get = self.client.get(reverse("detalle_y_reserva", args=[self.evento.id]))
        response_post = self.client.post(
            reverse("detalle_y_reserva", args=[self.evento.id]),
            self.datos_reservacion(),
        )

        self.assertEqual(response_get.status_code, 200)
        self.assertContains(response_get, "Este evento fue cancelado")
        self.assertRedirects(response_post, reverse("detalle_y_reserva", args=[self.evento.id]))
        self.assertFalse(Reservacion.objects.filter(evento=self.evento, usuario=self.asistente).exists())

    def test_usuario_con_reservacion_ve_evento_cancelado_sin_404(self):
        Reservacion.objects.create(
            evento=self.evento,
            usuario=self.asistente,
            nombre_cliente="Cliente",
            hora_reserva="18:00",
            numero_personas=2,
        )
        self.evento.activo = False
        self.evento.save(update_fields=["activo"])
        self.client.login(username="asistente", password="Password12345")

        response = self.client.get(reverse("detalle_y_reserva", args=[self.evento.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tu reservación queda guardada")

    def test_usuario_no_puede_ver_informacion_privada_de_evento_ajeno_sin_permiso(self):
        self.client.login(username="asistente", password="Password12345")
        response = self.client.get(reverse("detalle_y_reserva", args=[self.evento.id]))
        self.assertRedirects(response, reverse("pagina_de_inicio"))


class ReservacionesTests(BaseBalNexTestCase):
    def reservar(self, usuario=None, evento=None, **overrides):
        usuario = usuario or self.asistente
        evento = evento or self.evento
        self.client.login(username=usuario.username, password="Password12345")
        self.permitir_evento_en_sesion(evento)
        return self.client.post(reverse("detalle_y_reserva", args=[evento.id]), self.datos_reservacion(**overrides))

    def test_usuario_puede_reservar_evento_permitido(self):
        response = self.reservar()
        self.assertRedirects(response, reverse("pagina_de_inicio"))
        self.assertTrue(Reservacion.objects.filter(evento=self.evento, usuario=self.asistente).exists())

    def test_organizador_no_puede_reservar_su_propio_evento(self):
        response = self.reservar(usuario=self.organizador)
        self.assertRedirects(response, reverse("detalle_y_reserva", args=[self.evento.id]))
        self.assertFalse(Reservacion.objects.filter(evento=self.evento, usuario=self.organizador).exists())

    def test_usuario_no_puede_reservar_dos_veces_mismo_evento(self):
        self.reservar()
        response = self.reservar()
        self.assertRedirects(response, reverse("detalle_y_reserva", args=[self.evento.id]))
        self.assertEqual(Reservacion.objects.filter(evento=self.evento, usuario=self.asistente).count(), 1)

    def test_no_puede_reservar_mas_lugares_que_disponibles(self):
        self.evento.cupo_maximo = 1
        self.evento.save()
        response = self.reservar(numero_personas="2")
        self.assertRedirects(response, reverse("detalle_y_reserva", args=[self.evento.id]))
        self.assertFalse(Reservacion.objects.filter(evento=self.evento, usuario=self.asistente).exists())

    def test_no_puede_reservar_mas_del_limite_maximo(self):
        response = self.reservar(numero_personas=str(Reservacion.MAX_PERSONAS_POR_RESERVACION + 1))
        self.assertRedirects(response, reverse("detalle_y_reserva", args=[self.evento.id]))
        self.assertFalse(Reservacion.objects.filter(evento=self.evento, usuario=self.asistente).exists())

    def test_reservacion_rechaza_numeros_excesivamente_largos(self):
        response = self.reservar(numero_personas="9" * 10000)
        self.assertRedirects(response, reverse("detalle_y_reserva", args=[self.evento.id]))
        self.assertFalse(Reservacion.objects.filter(evento=self.evento, usuario=self.asistente).exists())

    def test_reservacion_cancelada_libera_cupo(self):
        self.reservar(numero_personas="5")
        reservacion = Reservacion.objects.get(usuario=self.asistente, evento=self.evento)
        self.assertEqual(self.evento.lugares_disponibles(), 15)
        response = self.client.post(reverse("cancelar_reservacion", args=[reservacion.id]))
        self.assertRedirects(response, reverse("pagina_de_inicio"))
        self.evento.refresh_from_db()
        self.assertEqual(self.evento.lugares_disponibles(), 20)

    def test_usuario_solo_ve_sus_reservaciones(self):
        self.reservar()
        Reservacion.objects.create(
            evento=self.evento,
            usuario=self.otro,
            nombre_cliente="Otro",
            hora_reserva="19:00",
            numero_personas=1,
        )
        response = self.client.get(reverse("pagina_de_inicio"))
        reservaciones = response.context["mis_reservaciones"]
        self.assertEqual(list(reservaciones.values_list("usuario", flat=True)), [self.asistente.id])

    def test_usuario_no_puede_editar_reservacion_de_otro(self):
        reservacion = Reservacion.objects.create(
            evento=self.evento,
            usuario=self.otro,
            nombre_cliente="Otro",
            hora_reserva="19:00",
            numero_personas=1,
        )
        self.client.login(username="asistente", password="Password12345")
        response = self.client.get(reverse("editar_reservacion", args=[reservacion.id]))
        self.assertEqual(response.status_code, 404)

    def test_usuario_no_puede_cancelar_reservacion_de_otro(self):
        reservacion = Reservacion.objects.create(
            evento=self.evento,
            usuario=self.otro,
            nombre_cliente="Otro",
            hora_reserva="19:00",
            numero_personas=1,
        )
        self.client.login(username="asistente", password="Password12345")
        response = self.client.post(reverse("cancelar_reservacion", args=[reservacion.id]))
        self.assertEqual(response.status_code, 404)
        reservacion.refresh_from_db()
        self.assertNotEqual(reservacion.estado, Reservacion.ESTADO_CANCELADA)


class FinanzasTests(BaseBalNexTestCase):
    def setUp(self):
        super().setUp()
        self.servicio = ServicioExtra.objects.create(
            evento=self.evento,
            nombre="Zona VIP",
            precio=Decimal("50.00"),
        )

    def test_totales_financieros_se_calculan_correctamente(self):
        pagada = Reservacion.objects.create(
            evento=self.evento,
            usuario=self.asistente,
            nombre_cliente="Pagada",
            hora_reserva="18:00",
            numero_personas=2,
            estado=Reservacion.ESTADO_PAGADA,
        )
        pagada.servicios_extra.add(self.servicio)
        Reservacion.objects.create(
            evento=self.evento,
            usuario=self.otro,
            nombre_cliente="Pendiente",
            hora_reserva="19:00",
            numero_personas=1,
            estado=Reservacion.ESTADO_PENDIENTE,
        )
        cancelada = Reservacion.objects.create(
            evento=self.evento,
            usuario=User.objects.create_user("cancelado", "cancelado@gmail.com", "x"),
            nombre_cliente="Cancelada",
            hora_reserva="20:00",
            numero_personas=5,
            estado=Reservacion.ESTADO_CANCELADA,
        )
        self.assertEqual(pagada.total_reservacion(), Decimal("250.00"))
        self.assertEqual(cancelada.total_reservacion(), Decimal("0.00"))
        self.assertEqual(self.evento.total_ingresos_esperados(), Decimal("350.00"))
        self.assertEqual(self.evento.total_ingresos_confirmados(), Decimal("250.00"))
        self.assertEqual(self.evento.total_pendiente_cobrar(), Decimal("100.00"))
        self.assertEqual(self.evento.total_asistentes(), 0)

    def test_reservaciones_canceladas_no_cuentan_como_pagadas_ni_asistencia(self):
        Reservacion.objects.create(
            evento=self.evento,
            usuario=self.asistente,
            nombre_cliente="Cancelada",
            hora_reserva="18:00",
            numero_personas=2,
            estado=Reservacion.ESTADO_CANCELADA,
        )
        self.assertEqual(self.evento.reservaciones_pagadas(), 0)
        self.assertEqual(self.evento.total_asistentes(), 0)


class NotificacionesTests(BaseBalNexTestCase):
    def test_se_crea_notificacion_cuando_alguien_reserva(self):
        self.client.login(username="asistente", password="Password12345")
        self.permitir_evento_en_sesion()
        self.client.post(reverse("detalle_y_reserva", args=[self.evento.id]), self.datos_reservacion())
        self.assertTrue(NotificacionInterna.objects.filter(usuario=self.organizador, mensaje__contains="reservó").exists())

    def test_se_crea_notificacion_cuando_reservacion_se_cancela(self):
        reservacion = Reservacion.objects.create(
            evento=self.evento,
            usuario=self.asistente,
            nombre_cliente="Cliente",
            hora_reserva="18:00",
            numero_personas=2,
        )
        self.client.login(username="asistente", password="Password12345")
        self.client.post(reverse("cancelar_reservacion", args=[reservacion.id]))
        self.assertTrue(NotificacionInterna.objects.filter(usuario=self.organizador, mensaje__contains="canceló").exists())

    def test_se_crea_notificacion_cuando_pago_se_confirma(self):
        reservacion = Reservacion.objects.create(
            evento=self.evento,
            usuario=self.asistente,
            nombre_cliente="Cliente",
            hora_reserva="18:00",
            numero_personas=2,
        )
        self.client.login(username="organizador", password="Password12345")
        self.client.post(
            reverse("actualizar_estado_reservacion", args=[reservacion.id]),
            {"estado": Reservacion.ESTADO_PAGADA},
        )
        self.assertTrue(NotificacionInterna.objects.filter(usuario=self.asistente, mensaje__contains="pago").exists())

    def test_usuario_solo_ve_sus_notificaciones(self):
        NotificacionInterna.objects.create(usuario=self.asistente, mensaje="Propia")
        NotificacionInterna.objects.create(usuario=self.organizador, mensaje="Ajena")
        self.client.login(username="asistente", password="Password12345")
        response = self.client.get(reverse("notificaciones"))
        self.assertContains(response, "Propia")
        self.assertNotContains(response, "Ajena")

    def test_usuario_no_puede_marcar_notificacion_de_otro(self):
        notificacion = NotificacionInterna.objects.create(usuario=self.organizador, mensaje="Ajena")
        self.client.login(username="asistente", password="Password12345")
        response = self.client.post(reverse("marcar_notificacion_leida", args=[notificacion.id]))
        self.assertEqual(response.status_code, 404)
        notificacion.refresh_from_db()
        self.assertFalse(notificacion.leida)


class HistorialTests(BaseBalNexTestCase):
    def test_historial_evento_creacion_edicion_reserva_cancelacion_y_pago(self):
        self.client.login(username="organizador", password="Password12345")
        self.client.post(reverse("crear_evento"), self.datos_evento(nombre_evento="Con historial"))
        evento = Evento.objects.get(nombre_evento="Con historial")
        self.assertTrue(evento.historial.filter(mensaje="Evento creado.").exists())

        self.client.post(
            reverse("editar_evento", args=[evento.id]),
            self.datos_evento(nombre_evento="Con historial editado"),
        )
        evento.refresh_from_db()
        self.assertTrue(evento.historial.filter(mensaje="Evento editado.").exists())

        self.client.logout()
        self.client.login(username="asistente", password="Password12345")
        self.permitir_evento_en_sesion(evento)
        self.client.post(reverse("detalle_y_reserva", args=[evento.id]), self.datos_reservacion())
        reservacion = Reservacion.objects.get(evento=evento, usuario=self.asistente)
        self.assertTrue(evento.historial.filter(mensaje__contains="Reservación creada").exists())

        self.client.post(reverse("cancelar_reservacion", args=[reservacion.id]))
        self.assertTrue(evento.historial.filter(mensaje__contains="Reservación cancelada").exists())

        reservacion.estado = Reservacion.ESTADO_PENDIENTE
        reservacion.save(update_fields=["estado"])
        self.client.logout()
        self.client.login(username="organizador", password="Password12345")
        self.client.post(
            reverse("actualizar_estado_reservacion", args=[reservacion.id]),
            {"estado": Reservacion.ESTADO_PAGADA},
        )
        self.assertTrue(evento.historial.filter(mensaje__contains="marcada como pagada").exists())
        self.assertEqual(ActividadEvento.objects.filter(evento=evento).count(), evento.historial.count())

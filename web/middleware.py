from django.contrib import messages
from django.core.exceptions import RequestDataTooBig, TooManyFieldsSent
from django.shortcuts import redirect


class SafeRequestSizeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if not isinstance(exception, (RequestDataTooBig, TooManyFieldsSent)):
            return None

        messages.error(
            request,
            "La información enviada es demasiado grande. Revisa los campos e inténtalo otra vez.",
        )

        if request.path.startswith("/registro"):
            return redirect("register")

        if request.path.startswith("/login"):
            return redirect("login")

        if request.path.startswith("/recuperar-password"):
            return redirect("recuperar_password")

        return redirect("pagina_de_inicio")

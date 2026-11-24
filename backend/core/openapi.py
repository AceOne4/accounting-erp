from drf_spectacular.extensions import OpenApiAuthenticationExtension


class Session401Scheme(OpenApiAuthenticationExtension):
    target_class = "core.authentication.Session401Authentication"
    name = "cookieAuth"

    def get_security_definition(self, auto_schema):
        return {"type": "apiKey", "in": "cookie", "name": "sessionid"}

from rest_framework.authentication import SessionAuthentication


class Session401Authentication(SessionAuthentication):
    """Session login that answers 401 (not 403) when nobody is signed in, so clients can tell
    "sign in first" apart from "you are not allowed". A bad CSRF token still answers 403."""

    def authenticate_header(self, request):
        return 'Session realm="api"'

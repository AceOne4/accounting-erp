"""drf-spectacular hook: document the X-Company-Id header on company-scoped endpoints."""

PUBLIC_PATHS = ("/api/v1/health/", "/api/v1/me/")


def add_company_header(result, generator, request, public):
    header = {
        "name": "X-Company-Id",
        "in": "header",
        "required": False,
        "schema": {"type": "integer"},
        "description": "Company to act in. Optional when the user belongs to exactly one.",
    }
    for path, methods in result.get("paths", {}).items():
        if path in PUBLIC_PATHS or not path.startswith("/api/v1/"):
            continue
        for method, operation in methods.items():
            if isinstance(operation, dict) and "operationId" in operation:
                operation.setdefault("parameters", []).append(header)
    return result

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; base-uri 'none'; object-src 'none'; "
    "frame-ancestors 'none'; form-action 'self'; script-src 'none'; "
    "style-src 'self'; img-src 'self'; font-src 'self'; "
    "frame-src 'none'; worker-src 'none'"
)
PERMISSIONS_POLICY = (
    "camera=(), geolocation=(), microphone=(), payment=(), usb=()"
)
HSTS_POLICY = "max-age=31536000"


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, *, production: bool) -> None:
        self.app = app
        self.production = production

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path", ""))

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                headers["X-Frame-Options"] = "DENY"
                headers["Permissions-Policy"] = PERMISSIONS_POLICY

                content_type = headers.get("content-type", "")
                is_html = content_type.lower().startswith("text/html")
                is_interactive_docs = path == "/docs" or path.startswith("/docs/")
                if is_html and not is_interactive_docs:
                    headers["Content-Security-Policy"] = (
                        CONTENT_SECURITY_POLICY
                    )

                if path == "/admin" or path.startswith("/admin/"):
                    headers["Cache-Control"] = "no-store"

                if self.production and scope.get("scheme") == "https":
                    headers["Strict-Transport-Security"] = HSTS_POLICY

            await send(message)

        await self.app(scope, receive, send_with_security_headers)

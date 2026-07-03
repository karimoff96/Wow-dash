from django.conf import settings


class ProxyPrefixMiddleware:
    """
    Help Django run behind path-based development proxies such as code-server.

    APP_URL_PREFIX=/proxy/8003 makes reversed URLs include the proxy mount. Some
    older templates still contain absolute /static/ or /media/ paths, so HTML
    responses are patched only when a prefix is configured.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.prefix = getattr(settings, "APP_URL_PREFIX", "").rstrip("/")

    def __call__(self, request):
        if self.prefix:
            request.META["SCRIPT_NAME"] = self.prefix
            if request.path_info == self.prefix:
                request.path_info = "/"
                request.META["PATH_INFO"] = "/"
            elif request.path_info.startswith(f"{self.prefix}/"):
                request.path_info = request.path_info[len(self.prefix):] or "/"
                request.META["PATH_INFO"] = request.path_info

        response = self.get_response(request)

        if not self.prefix or getattr(response, "streaming", False):
            return response

        content_type = response.get("Content-Type", "")
        if not content_type.startswith("text/html"):
            return response

        encoding = response.charset or "utf-8"
        try:
            body = response.content.decode(encoding)
        except UnicodeDecodeError:
            return response

        for asset_root in ("static", "media"):
            body = body.replace(f'="/{asset_root}/', f'="{self.prefix}/{asset_root}/')
            body = body.replace(f"='/{asset_root}/", f"='{self.prefix}/{asset_root}/")
            body = body.replace(f'("/{asset_root}/', f'("{self.prefix}/{asset_root}/')
            body = body.replace(f"('/{asset_root}/", f"('{self.prefix}/{asset_root}/")

        response.content = body.encode(encoding)
        response["Content-Length"] = str(len(response.content))
        return response

"""
Subdomain middleware for multi-tenant translation centers.

This middleware extracts the subdomain from the request and attaches
the corresponding TranslationCenter to the request object.

Best Practice: Subdomain is for branding/routing only.
Security is handled by RBAC (user sees only their center's data).

Usage in views:
    center = request.center  # TranslationCenter from URL (for branding)
    user_center = request.current_center  # User's actual center (for data access)
"""

import re
from django.conf import settings


class SubdomainMiddleware:
    """
    Middleware that identifies the translation center based on subdomain.
    
    Example:
        center1.alltranslation.uz → request.center = TranslationCenter(subdomain='center1')
        alltranslation.uz → request.center = None (main site)
    
    Note: This is for branding only. Actual data access is controlled by
    request.current_center (set by RBACMiddleware from user's profile).
    """
    
    # Subdomains to ignore (not tenant subdomains)
    # Note: 'admin' is now a valid subdomain for superuser admin panel
    IGNORED_SUBDOMAINS = {'www', 'api', 'static', 'media'}
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.main_domain = getattr(settings, 'MAIN_DOMAIN', 'alltranslation.uz')
        # Support .local and lvh.me for development
        self.dev_domains = ['multilang.local', 'lvh.me']
    
    def __call__(self, request):
        host = request.get_host().split(':')[0]
        subdomain = self._extract_subdomain(host)
        
        request.subdomain = subdomain
        request.center = None
        
        if subdomain and subdomain not in self.IGNORED_SUBDOMAINS:
            from organizations.models import TranslationCenter
            
            try:
                request.center = TranslationCenter.objects.get(
                    subdomain=subdomain,
                    is_active=True
                )
            except TranslationCenter.DoesNotExist:
                pass
        
        return self.get_response(request)
    
    def _extract_subdomain(self, host):
        """Extract subdomain from host."""
        if re.match(r'^(\d{1,3}\.){3}\d{1,3}$', host) or host in ('localhost', '127.0.0.1'):
            return None
        
        # Check main production domain
        if host.endswith('.' + self.main_domain):
            subdomain = host[:-len('.' + self.main_domain)]
            if '.' not in subdomain:
                return subdomain
        
        # Check development domains
        for dev_domain in self.dev_domains:
            if host.endswith('.' + dev_domain):
                subdomain = host[:-len('.' + dev_domain)]
                if '.' not in subdomain:
                    return subdomain
        
        return None

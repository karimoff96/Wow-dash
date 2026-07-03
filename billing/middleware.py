from datetime import date, timedelta

from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

# Grace period after subscription.end_date before the hard redirect kicks in.
# During this window the user sees a warning banner but can still work.
GRACE_PERIOD_DAYS = getattr(settings, "SUBSCRIPTION_GRACE_DAYS", 3)


class SubscriptionEnforcementMiddleware:
    """Block non-superusers from the app when their center subscription is missing or expired.

    Superusers are exempt.  Subscriptions get a configurable grace period
    (SUBSCRIPTION_GRACE_DAYS, default 3) after expiry before the hard
    redirect kicks in — this prevents locking out users mid-task due to
    clock skew or a missed renewal.  During the grace period the request
    attribute `request.subscription_grace` is set to the number of days
    remaining so templates can show a warning banner.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        media_url = getattr(settings, "MEDIA_URL", "/media/") or "/media/"
        self.exempt_prefixes = (
            settings.STATIC_URL,
            media_url,
            "/admin",
        )
        self.exempt_names = {
            "admin_login",
            "login",
            "logout",
            "password_reset",
            "password_reset_done",
            "password_reset_confirm",
            "password_reset_complete",
            "billing:subscription_expired",
            "billing:request_renewal",
        }

    def __call__(self, request):
        # Always clear the grace attribute so templates can rely on its presence
        request.subscription_grace = None

        if self._is_exempt(request):
            return self.get_response(request)

        user = request.user
        if not user.is_authenticated or user.is_superuser:
            return self.get_response(request)

        profile = getattr(user, "admin_profile", None)
        if not profile or not profile.center:
            return self.get_response(request)

        center = profile.center
        subscription = getattr(center, "subscription", None)

        if subscription and subscription.is_active():
            return self.get_response(request)

        # If dates have passed but DB status is stale, sync it now.
        if subscription and subscription.status == "active":
            if subscription.end_date and subscription.end_date < date.today():
                from billing.models import Subscription as _Sub
                _Sub.objects.filter(pk=subscription.pk).update(status="expired")
                subscription.status = "expired"

        # ── Grace period check ────────────────────────────────────────────
        # Allow access for GRACE_PERIOD_DAYS days after the end_date so that
        # users can still work while renewing.
        if subscription and subscription.end_date:
            grace_deadline = subscription.end_date + timedelta(days=GRACE_PERIOD_DAYS)
            days_remaining = (grace_deadline - date.today()).days
            if days_remaining >= 0:
                # Within grace period: attach warning info and allow access
                request.subscription_grace = max(days_remaining, 0)
                return self.get_response(request)
        # ─────────────────────────────────────────────────────────────────

        # Grace period exhausted or subscription missing: hard redirect.
        expired_url = reverse("billing:subscription_expired")
        if request.path != expired_url:
            return redirect(expired_url)

        return self.get_response(request)

    def _is_exempt(self, request):
        path = request.path

        for prefix in self.exempt_prefixes:
            if prefix and path.startswith(prefix):
                return True

        match = getattr(request, "resolver_match", None)
        if match:
            url_name = match.view_name or match.url_name
            if url_name in self.exempt_names:
                return True

        return False

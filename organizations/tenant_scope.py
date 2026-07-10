"""Fail-closed queryset helpers for tenant-owned records."""


def get_profile_center(user):
    """Return the user's center without raising for users that have no profile."""
    profile = getattr(user, "admin_profile", None)
    return getattr(profile, "center", None)


def center_queryset(queryset, center, *, lookup="branch__center", allow_global=False):
    """Scope a queryset to one center, denying access when center is absent."""
    if center is None:
        return queryset if allow_global else queryset.none()
    return queryset.filter(**{lookup: center})


def customer_queryset(
    queryset,
    center,
    customer,
    *,
    center_lookup="branch__center",
    customer_lookup="bot_user",
):
    """Scope customer-owned data by both customer and center."""
    scoped = center_queryset(queryset, center, lookup=center_lookup)
    if customer is None:
        return scoped.none()
    return scoped.filter(**{customer_lookup: customer})

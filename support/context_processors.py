from .models import Ticket


def unread_support_replies(request):
    """
    Injects `unread_support_count` into every template context.
    Counts open tickets that belong to the current user and have an
    unread reply from the support team.
    """
    if not request.user.is_authenticated or request.user.is_superuser:
        return {"unread_support_count": 0}

    count = Ticket.objects.filter(
        created_by=request.user,
        has_unread_reply=True,
    ).count()

    return {"unread_support_count": count}

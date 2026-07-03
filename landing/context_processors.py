from .models import ContactRequest


def contact_requests_count(request):
    """Add new contact requests count to template context"""
    if request.user.is_authenticated and request.user.is_superuser:
        new_requests_count = ContactRequest.objects.filter(status=ContactRequest.STATUS_NEW).count()
        return {
            'new_contact_requests_count': new_requests_count
        }
    return {
        'new_contact_requests_count': 0
    }

"""
Views for storage archive management
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils.translation import gettext as _
from core.models import FileArchive
from core.storage_service import StorageArchiveService
from organizations.rbac import permission_required


@login_required
@permission_required('can_view_orders')
def archive_list(request):
    """List all archives for current center"""
    user_center = getattr(request.user.admin_profile, 'center', None)
    
    if not user_center:
        messages.error(request, _("You don't have access to any center"))
        return redirect('index')
    
    archives = FileArchive.objects.filter(center=user_center).order_by('-archive_date')
    
    context = {
        'archives': archives,
        'page_title': _('File Archives'),
    }
    return render(request, 'archive_list.html', context)


@login_required
@permission_required('can_view_orders')
def archive_detail(request, archive_id):
    """View details of a specific archive"""
    user_center = getattr(request.user.admin_profile, 'center', None)
    
    archive = get_object_or_404(
        FileArchive,
        id=archive_id,
        center=user_center
    )
    
    orders = archive.orders.all().order_by('branch', '-created_at')
    
    context = {
        'archive': archive,
        'orders': orders,
        'page_title': _('Archive Details'),
    }
    return render(request, 'archive_detail.html', context)


@login_required
def trigger_archive(request):
    """Manually trigger archiving process - superuser only"""
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': _('Superuser access required')}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    
    user_center = getattr(request.user.admin_profile, 'center', None)
    
    if not user_center:
        return JsonResponse({'success': False, 'error': _('No center access')}, status=403)
    
    # Get options
    force = request.POST.get('force', 'false').lower() == 'true'
    age_days = int(request.POST.get('age_days', 30))
    
    # Run archiving
    service = StorageArchiveService()
    result = service.archive_orders(
        center=user_center,
        age_days=age_days,
        force=force
    )
    
    if result['success']:
        messages.success(
            request,
            _('Successfully archived %(count)d orders (%(size).2f MB)') % {
                'count': result['orders_count'],
                'size': result['archive_size'] / (1024 * 1024)
            }
        )
        return JsonResponse({'success': True, 'result': result})
    else:
        messages.error(request, _('Archive failed: %(error)s') % {'error': result['error']})
        return JsonResponse({'success': False, 'error': result['error']}, status=400)


@login_required
@permission_required('can_view_orders')
def archive_stats(request):
    """Get archive statistics for dashboard"""
    user_center = getattr(request.user.admin_profile, 'center', None)
    
    if not user_center:
        return JsonResponse({'error': _('No center access')}, status=403)
    
    archives = FileArchive.objects.filter(center=user_center)
    
    stats = {
        'total_archives': archives.count(),
        'total_orders_archived': sum(a.total_orders for a in archives),
        'total_size_mb': sum(a.size_mb for a in archives),
        'latest_archive': None
    }
    
    latest = archives.first()
    if latest:
        stats['latest_archive'] = {
            'id': latest.id,
            'name': latest.archive_name,
            'date': latest.archive_date.isoformat(),
            'orders': latest.total_orders,
            'size_mb': latest.size_mb
        }
    
    return JsonResponse(stats)

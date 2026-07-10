"""
Views for storage archive management
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils.translation import gettext as _
from django.db.models import Q, Sum
from django.core.paginator import Paginator
from core.models import FileArchive
from core.storage_service import StorageArchiveService
from organizations.rbac import permission_required
from billing.decorators import require_feature, require_active_subscription


@login_required
@require_active_subscription
@require_feature('archive_access')
@permission_required('can_view_orders')
def archive_list(request):
    """List all archives for current center"""
    user_center = getattr(request.user.admin_profile, 'center', None)
    
    if not user_center:
        messages.error(request, _("You don't have access to any center"))
        return redirect('index')
    
    archives = FileArchive.objects.filter(center=user_center).order_by('-archive_date')

    query = request.GET.get('q', '').strip()
    branch_id = request.GET.get('branch', '').strip()
    verification = request.GET.get('verification', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()

    if query:
        query_filter = Q(archive_name__icontains=query) | Q(sha256__icontains=query)
        if query.isdigit():
            query_filter |= Q(orders__center_order_number=int(query)) | Q(orders__id=int(query))
        archives = archives.filter(query_filter)
    if branch_id.isdigit():
        archives = archives.filter(orders__branch_id=int(branch_id))
    if verification:
        archives = archives.filter(verification_status=verification)
    if date_from:
        archives = archives.filter(archive_date__date__gte=date_from)
    if date_to:
        archives = archives.filter(archive_date__date__lte=date_to)

    archives = archives.distinct()
    page = Paginator(archives, 30).get_page(request.GET.get('page'))
    
    context = {
        'archives': page,
        'branches': user_center.branches.filter(is_active=True).order_by('name'),
        'verification_choices': FileArchive.VERIFICATION_CHOICES,
        'filters': {
            'q': query,
            'branch': branch_id,
            'verification': verification,
            'date_from': date_from,
            'date_to': date_to,
        },
        'page_title': _('File Archives'),
    }
    return render(request, 'archive_list.html', context)


@login_required
@require_active_subscription
@require_feature('archive_access')
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
    
    from organizations.models import TranslationCenter
    center_id = request.POST.get('center_id')
    user_center = TranslationCenter.objects.filter(pk=center_id).first() if center_id else None
    if not user_center:
        return JsonResponse({'success': False, 'error': _('center_id is required')}, status=400)
    
    # Get options
    force = request.POST.get('force', 'false').lower() == 'true'
    age_days = int(request.POST.get('age_days', 30))
    mode = request.POST.get('mode', 'inventory')
    if mode not in {'inventory', 'canary', 'live'}:
        return JsonResponse({'success': False, 'error': _('Invalid archive mode')}, status=400)
    if mode == 'live' and request.POST.get('confirm_delete') != 'true':
        return JsonResponse({'success': False, 'error': _('Live mode requires confirm_delete=true')}, status=400)
    
    # Run archiving
    service = StorageArchiveService()
    result = service.archive_orders(
        center=user_center,
        age_days=age_days,
        force=force,
        mode=mode,
        created_by=request.user,
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
    aggregates = archives.aggregate(
        total_orders=Sum('total_orders'),
        total_bytes=Sum('source_size_bytes'),
    )
    
    stats = {
        'total_archives': archives.count(),
        'total_orders_archived': aggregates['total_orders'] or 0,
        'total_size_mb': (aggregates['total_bytes'] or 0) / (1024 * 1024),
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

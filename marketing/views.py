"""
Marketing Views for Dashboard

Handles CRUD operations for marketing posts and broadcast management.
"""
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.utils.translation import gettext_lazy as _
from django.db.models import Q

from organizations.models import TranslationCenter, Branch, AdminUser
from organizations.rbac import get_user_branches, permission_required, any_permission_required
from core.audit import log_action
from .models import MarketingPost, BroadcastRecipient
from .broadcast_service import send_broadcast, get_recipient_count, BroadcastService

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger('audit')


def get_user_scope_permissions(request):
    """
    Determine what scopes the user can access for marketing.
    Returns dict with allowed scopes and available centers/branches.
    
    Uses role-based permissions from the Role model:
    - can_create_marketing_posts: Can create/edit marketing posts
    - can_send_branch_broadcasts: Can send broadcasts to their branch
    - can_send_center_broadcasts: Can send center-wide broadcasts
    - can_view_broadcast_stats: Can view broadcast delivery statistics
    """
    user = request.user
    permissions = {
        'can_platform_wide': user.is_superuser,
        'can_center_wide': False,
        'can_branch': False,
        'can_create': False,
        'can_view_stats': False,
        'centers': [],
        'branches': [],
    }
    
    if user.is_superuser:
        # Superuser can access everything
        permissions['can_center_wide'] = True
        permissions['can_branch'] = True
        permissions['can_create'] = True
        permissions['can_view_stats'] = True
        permissions['centers'] = list(TranslationCenter.objects.filter(is_active=True))
        permissions['branches'] = list(Branch.objects.filter(is_active=True))
        return permissions
    
    # Get admin profile
    admin_profile = getattr(request, 'admin_profile', None)
    if not admin_profile:
        try:
            admin_profile = AdminUser.objects.get(user=user)
        except AdminUser.DoesNotExist:
            return permissions
    
    # Get role-based permissions using has_permission to support master permissions
    role = admin_profile.role
    if role:
        permissions['can_create'] = admin_profile.has_permission('can_create_marketing_posts')
        permissions['can_view_stats'] = admin_profile.has_permission('can_view_broadcast_stats')
        can_send_branch = admin_profile.has_permission('can_send_branch_broadcasts')
        can_send_center = admin_profile.has_permission('can_send_center_broadcasts')
    else:
        # No role, no marketing permissions
        return permissions
    
    # Owner can access their center and all its branches (if permissions allow)
    if admin_profile.is_owner and admin_profile.center:
        if can_send_center:
            permissions['can_center_wide'] = True
        if can_send_branch or can_send_center:
            permissions['can_branch'] = True
        permissions['centers'] = [admin_profile.center]
        permissions['branches'] = list(admin_profile.center.branches.filter(is_active=True))
    
    # Manager/Staff can only access their branch (if permissions allow)
    elif admin_profile.branch:
        if can_send_branch:
            permissions['can_branch'] = True
        permissions['branches'] = [admin_profile.branch] if admin_profile.branch.is_active else []
        # Add center for that branch
        if admin_profile.branch.center:
            permissions['centers'] = [admin_profile.branch.center]
    
    return permissions


@login_required
@any_permission_required('can_manage_marketing', 'can_create_marketing_posts', 'can_send_branch_broadcasts', 'can_send_center_broadcasts', 'can_view_broadcast_stats')
def marketing_list(request):
    """List marketing posts based on user permissions"""
    marketing_permissions = get_user_scope_permissions(request)
    
    # Build query based on permissions
    if request.user.is_superuser:
        posts = MarketingPost.objects.all()
    else:
        # Filter to posts created by user or targeting their scope
        q = Q(created_by=request.user)
        
        if marketing_permissions['centers']:
            q |= Q(target_center__in=marketing_permissions['centers'])
        if marketing_permissions['branches']:
            q |= Q(target_branch__in=marketing_permissions['branches'])
        
        posts = MarketingPost.objects.filter(q).distinct()
    
    # Filters
    status = request.GET.get('status')
    if status:
        posts = posts.filter(status=status)
    
    scope = request.GET.get('scope')
    if scope:
        posts = posts.filter(target_scope=scope)
    
    # Ordering
    posts = posts.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(posts, 20)
    page = request.GET.get('page', 1)
    posts_page = paginator.get_page(page)
    
    context = {
        'title': _('Marketing Posts'),
        'subTitle': _('Broadcast & Promotions'),
        'posts': posts_page,
        'marketing_permissions': marketing_permissions,
        'status_choices': MarketingPost.STATUS_CHOICES,
        'scope_choices': MarketingPost.TARGET_SCOPE_CHOICES,
        'current_status': status,
        'current_scope': scope,
    }
    
    return render(request, 'marketing/list.html', context)


@login_required
@any_permission_required('can_create_marketing_posts', 'can_manage_marketing')
def marketing_create(request):
    """Create a new marketing post"""
    permissions = get_user_scope_permissions(request)
    
    # Check if user has permission to create marketing posts
    if not permissions['can_create']:
        messages.error(request, _("You don't have permission to create marketing posts."))
        return redirect('marketing_list')
    
    # Check if user has any scope permissions
    if not (permissions['can_platform_wide'] or permissions['can_center_wide'] or permissions['can_branch']):
        messages.error(request, _("You don't have permission to send broadcasts to any scope."))
        return redirect('marketing_list')
    
    if request.method == 'POST':
        # Get form data
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        content_type = request.POST.get('content_type', 'text')
        target_scope = request.POST.get('target_scope', 'branch')
        target_center_id = request.POST.get('target_center')
        target_branch_id = request.POST.get('target_branch')
        include_b2c = request.POST.get('include_b2c') == 'on'
        include_b2b = request.POST.get('include_b2b') == 'on'
        scheduled_at = request.POST.get('scheduled_at')
        
        # Validation
        errors = []
        
        if not title:
            errors.append(_("Title is required"))
        if not content:
            errors.append(_("Content is required"))
        
        # Validate scope permissions
        if target_scope == 'all' and not permissions['can_platform_wide']:
            errors.append(_("You don't have permission for platform-wide broadcasts"))
        elif target_scope == 'center' and not permissions['can_center_wide']:
            errors.append(_("You don't have permission for center-wide broadcasts"))
        
        # Validate center/branch access
        target_center = None
        target_branch = None
        
        if target_scope in ['center', 'branch'] and target_center_id:
            try:
                target_center = TranslationCenter.objects.get(id=target_center_id)
                if target_center not in permissions['centers'] and not request.user.is_superuser:
                    errors.append(_("You don't have access to this center"))
            except TranslationCenter.DoesNotExist:
                errors.append(_("Invalid center selected"))
        
        if target_scope == 'branch' and target_branch_id:
            try:
                target_branch = Branch.objects.get(id=target_branch_id)
                if target_branch not in permissions['branches'] and not request.user.is_superuser:
                    errors.append(_("You don't have access to this branch"))
            except Branch.DoesNotExist:
                errors.append(_("Invalid branch selected"))
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            # Create post
            post = MarketingPost.objects.create(
                title=title,
                content=content,
                content_type=content_type,
                target_scope=target_scope,
                target_center=target_center,
                target_branch=target_branch,
                include_b2c=include_b2c,
                include_b2b=include_b2b,
                created_by=request.user,
                status=MarketingPost.STATUS_DRAFT
            )
            
            # Handle media file
            if 'media_file' in request.FILES:
                post.media_file = request.FILES['media_file']
                post.save()
            
            # Handle scheduling
            if scheduled_at:
                try:
                    from django.utils.dateparse import parse_datetime
                    scheduled_dt = parse_datetime(scheduled_at)
                    if scheduled_dt:
                        post.scheduled_at = scheduled_dt
                        post.status = MarketingPost.STATUS_SCHEDULED
                        post.save()
                except Exception:
                    pass
            
            log_action(
                user=request.user,
                action='create',
                target=post,
                details=f"Created marketing post: {title}",
                request=request
            )
            
            messages.success(request, _("Marketing post created successfully."))
            return redirect('marketing_detail', post_id=post.id)
    
    context = {
        'title': _('Create Marketing Post'),
        'subTitle': _('New Broadcast'),
        'permissions': permissions,
        'content_type_choices': MarketingPost.CONTENT_TYPE_CHOICES,
        'scope_choices': [
            (MarketingPost.SCOPE_BRANCH, _('Branch Users')),
        ],
    }
    
    # Add scope choices based on permissions
    if permissions['can_center_wide']:
        context['scope_choices'].insert(0, (MarketingPost.SCOPE_CENTER, _('Center Users')))
    if permissions['can_platform_wide']:
        context['scope_choices'].insert(0, (MarketingPost.SCOPE_ALL, _('All Platform Users')))
    
    return render(request, 'marketing/create.html', context)


@login_required
@any_permission_required('can_view_broadcast_stats', 'can_manage_marketing')
def marketing_detail(request, post_id):
    """View marketing post details"""
    post = get_object_or_404(MarketingPost, id=post_id)
    permissions = get_user_scope_permissions(request)
    
    # Check access
    if not request.user.is_superuser:
        if post.created_by != request.user:
            if post.target_center and post.target_center not in permissions['centers']:
                messages.error(request, _("You don't have access to this post."))
                return redirect('marketing_list')
            if post.target_branch and post.target_branch not in permissions['branches']:
                messages.error(request, _("You don't have access to this post."))
                return redirect('marketing_list')
    
    # Compute if user can send this specific post
    can_send_this_post = False
    if permissions['can_platform_wide']:
        can_send_this_post = True
    elif post.target_scope == 'center' and permissions['can_center_wide']:
        can_send_this_post = True
    elif post.target_scope == 'branch' and permissions['can_branch']:
        can_send_this_post = True
    
    # Get recipient stats
    recipient_stats = {
        'pending': BroadcastRecipient.objects.filter(post=post, status='pending').count(),
        'sent': BroadcastRecipient.objects.filter(post=post, status='sent').count(),
        'delivered': BroadcastRecipient.objects.filter(post=post, status='delivered').count(),
        'failed': BroadcastRecipient.objects.filter(post=post, status='failed').count(),
        'blocked': BroadcastRecipient.objects.filter(post=post, status='blocked').count(),
        'skipped': BroadcastRecipient.objects.filter(post=post, status='skipped').count(),
    }
    # Total from actual recipients for accuracy
    recipient_stats['total'] = sum([
        recipient_stats['pending'],
        recipient_stats['sent'],
        recipient_stats['delivered'],
        recipient_stats['failed'],
        recipient_stats['blocked'],
        recipient_stats['skipped'],
    ])
    
    # Get recent recipients (for display)
    recent_recipients = BroadcastRecipient.objects.filter(
        post=post
    ).select_related('bot_user').order_by('-sent_at')[:20]
    
    context = {
        'title': post.title,
        'subTitle': _('Marketing Post Details'),
        'post': post,
        'recipient_stats': recipient_stats,
        'recent_recipients': recent_recipients,
        'permissions': permissions,
        'can_send_this_post': can_send_this_post,
    }
    
    return render(request, 'marketing/detail.html', context)


@login_required
@any_permission_required('can_create_marketing_posts', 'can_manage_marketing')
def marketing_edit(request, post_id):
    """Edit a marketing post (draft or scheduled status)"""
    post = get_object_or_404(MarketingPost, id=post_id)
    permissions = get_user_scope_permissions(request)
    
    # Check if user has permission to create/edit marketing posts
    if not permissions['can_create']:
        messages.error(request, _("You don't have permission to edit marketing posts."))
        return redirect('marketing_detail', post_id=post_id)
    
    # Check if editable (allow draft and scheduled)
    if post.status not in [MarketingPost.STATUS_DRAFT, MarketingPost.STATUS_SCHEDULED]:
        messages.error(request, _("Cannot edit post that has been sent or is currently sending."))
        return redirect('marketing_detail', post_id=post_id)
    
    # Check access - allow if created by user OR if post is within user's scope
    if not request.user.is_superuser:
        has_access = False
        
        # Check if user created this post
        if post.created_by == request.user:
            has_access = True
        # Check if post is within user's scope (branch or center)
        elif post.target_branch and post.target_branch in permissions['branches']:
            has_access = True
        elif post.target_center and post.target_center in permissions['centers']:
            has_access = True
        
        if not has_access:
            messages.error(request, _("You don't have access to edit this post."))
            return redirect('marketing_detail', post_id=post_id)
    
    # Get centers and branches for target scope editing (always editable for draft/scheduled)
    from organizations.models import TranslationCenter, Branch
    centers = []
    branches = []
    
    # Always provide centers/branches for editable posts
    if request.user.is_superuser:
        centers = TranslationCenter.objects.filter(is_active=True)
        branches = Branch.objects.filter(is_active=True)
    else:
        admin_profile = getattr(request, 'admin_profile', None)
        if not admin_profile:
            try:
                admin_profile = AdminUser.objects.get(user=request.user)
            except AdminUser.DoesNotExist:
                pass
        
        if admin_profile:
            if admin_profile.is_owner and admin_profile.center:
                centers = [admin_profile.center]
                branches = Branch.objects.filter(center=admin_profile.center, is_active=True)
            elif admin_profile.branch:
                centers = [admin_profile.branch.center] if admin_profile.branch.center else []
                branches = Branch.objects.filter(center=admin_profile.branch.center, is_active=True) if admin_profile.branch.center else []
    
    if request.method == 'POST':
        post.title = request.POST.get('title', post.title).strip()
        post.content = request.POST.get('content', post.content).strip()
        post.content_type = request.POST.get('content_type', post.content_type)
        post.include_b2c = request.POST.get('include_b2c') == 'on'
        post.include_b2b = request.POST.get('include_b2b') == 'on'
        
        # Handle target scope changes (allowed for draft and scheduled posts)
        target_scope = request.POST.get('target_scope', post.target_scope)
        
        # Validate scope permissions before allowing change
        scope_allowed = True
        if target_scope == 'all' and not permissions['can_platform_wide']:
            scope_allowed = False
            messages.error(request, _("You don't have permission for platform-wide scope."))
        elif target_scope == 'center' and not permissions['can_center_wide']:
            scope_allowed = False
            messages.error(request, _("You don't have permission for center-wide scope."))
        
        if scope_allowed:
            post.target_scope = target_scope
            
            if target_scope == 'all':
                post.target_center = None
                post.target_branch = None
            elif target_scope == 'center':
                center_id = request.POST.get('target_center')
                if center_id:
                    try:
                        center = TranslationCenter.objects.get(id=center_id)
                        if center in permissions['centers'] or request.user.is_superuser:
                            post.target_center = center
                        else:
                            messages.error(request, _("You don't have access to this center."))
                    except TranslationCenter.DoesNotExist:
                        pass
                post.target_branch = None
            elif target_scope == 'branch':
                center_id = request.POST.get('target_center')
                branch_id = request.POST.get('target_branch')
                if center_id:
                    try:
                        center = TranslationCenter.objects.get(id=center_id)
                        if center in permissions['centers'] or request.user.is_superuser:
                            post.target_center = center
                    except TranslationCenter.DoesNotExist:
                        pass
                if branch_id:
                    try:
                        branch = Branch.objects.get(id=branch_id)
                        if branch in permissions['branches'] or request.user.is_superuser:
                            post.target_branch = branch
                        else:
                            messages.error(request, _("You don't have access to this branch."))
                    except Branch.DoesNotExist:
                        pass
        
        # Handle media file
        if 'media_file' in request.FILES:
            post.media_file = request.FILES['media_file']
        
        # Handle scheduling
        scheduled_at = request.POST.get('scheduled_at')
        if scheduled_at:
            try:
                from django.utils.dateparse import parse_datetime
                scheduled_dt = parse_datetime(scheduled_at)
                if scheduled_dt:
                    post.scheduled_at = scheduled_dt
                    post.status = MarketingPost.STATUS_SCHEDULED
            except Exception:
                pass
        
        post.save()
        
        log_action(
            user=request.user,
            action='update',
            target=post,
            details=f"Updated marketing post: {post.title}",
            request=request
        )
        
        messages.success(request, _("Marketing post updated successfully."))
        return redirect('marketing_detail', post_id=post_id)
    
    # Build scope choices based on permissions
    scope_choices = [(MarketingPost.SCOPE_BRANCH, _('Branch Users'))]
    if permissions['can_center_wide']:
        scope_choices.insert(0, (MarketingPost.SCOPE_CENTER, _('Center Users')))
    if permissions['can_platform_wide']:
        scope_choices.insert(0, (MarketingPost.SCOPE_ALL, _('All Platform Users')))
    
    context = {
        'title': _('Edit Marketing Post'),
        'subTitle': post.title,
        'post': post,
        'permissions': permissions,
        'content_type_choices': MarketingPost.CONTENT_TYPE_CHOICES,
        'scope_choices': scope_choices,
        'centers': centers,
        'branches': branches,
        'can_edit_target': True,  # Always true for draft/scheduled
    }
    
    return render(request, 'marketing/edit.html', context)


@login_required
@any_permission_required('can_create_marketing_posts', 'can_manage_marketing')
@require_POST
def marketing_delete(request, post_id):
    """Delete a marketing post"""
    post = get_object_or_404(MarketingPost, id=post_id)
    permissions = get_user_scope_permissions(request)
    
    # Check access - allow if created by user OR if post is within user's scope
    if not request.user.is_superuser:
        has_access = False
        
        # Check if user created this post
        if post.created_by == request.user:
            has_access = True
        # Check if post is within user's scope (branch or center)
        elif post.target_branch and post.target_branch in permissions['branches']:
            has_access = True
        elif post.target_center and post.target_center in permissions['centers']:
            has_access = True
        
        if not has_access:
            messages.error(request, _("You don't have access to delete this post."))
            return redirect('marketing_detail', post_id=post_id)
    
    title = post.title
    post.delete()
    
    log_action(
        user=request.user,
        action='delete',
        target=None,
        details=f"Deleted marketing post: {title}",
        request=request
    )
    
    messages.success(request, _("Marketing post deleted."))
    return redirect('marketing_list')


@login_required
@any_permission_required('can_send_branch_broadcasts', 'can_send_center_broadcasts', 'can_manage_marketing')
def marketing_preview(request, post_id):
    """Preview broadcast before sending"""
    post = get_object_or_404(MarketingPost, id=post_id)
    
    try:
        service = BroadcastService(post)
        recipients = service.get_recipients()[:10]  # Preview first 10
        total_count = len(service.get_recipients())
        
        # Estimate duration
        from .models import BroadcastRateLimit
        rate_limit = None
        if post.target_center:
            rate_limit = BroadcastRateLimit.get_or_create_for_center(post.target_center)
        
        estimated_duration = BroadcastService.estimate_duration(total_count, rate_limit)
        
        context = {
            'title': _('Preview Broadcast'),
            'subTitle': post.title,
            'post': post,
            'preview_recipients': recipients,
            'total_recipients': total_count,
            'estimated_duration': estimated_duration,
        }
        
        return render(request, 'marketing/preview.html', context)
        
    except Exception as e:
        messages.error(request, f"Preview error: {str(e)}")
        return redirect('marketing_detail', post_id=post_id)


@login_required
@any_permission_required('can_send_branch_broadcasts', 'can_send_center_broadcasts', 'can_manage_marketing')
@require_POST
def marketing_send(request, post_id):
    """Start sending a broadcast"""
    post = get_object_or_404(MarketingPost, id=post_id)
    permissions = get_user_scope_permissions(request)
    
    # Check scope-based permissions
    if post.target_scope == MarketingPost.SCOPE_ALL and not permissions['can_platform_wide']:
        messages.error(request, _("You don't have permission to send platform-wide broadcasts."))
        return redirect('marketing_detail', post_id=post_id)
    elif post.target_scope == MarketingPost.SCOPE_CENTER and not permissions['can_center_wide']:
        messages.error(request, _("You don't have permission to send center-wide broadcasts."))
        return redirect('marketing_detail', post_id=post_id)
    elif post.target_scope == MarketingPost.SCOPE_BRANCH and not permissions['can_branch']:
        messages.error(request, _("You don't have permission to send branch broadcasts."))
        return redirect('marketing_detail', post_id=post_id)
    
    if not post.is_sendable:
        messages.error(request, _("This post cannot be sent."))
        return redirect('marketing_detail', post_id=post_id)
    
    try:
        # Prepare recipients
        service = BroadcastService(post)
        recipient_count = service.prepare_recipients()
        
        if recipient_count == 0:
            messages.warning(request, _("No recipients found for this broadcast."))
            return redirect('marketing_detail', post_id=post_id)
        
        # Start sending (synchronous for now, can be made async with Celery)
        result = service.execute()
        
        if result.success:
            messages.success(
                request, 
                _("Broadcast completed: {} sent, {} failed in {} seconds.").format(
                    result.sent_count, result.failed_count, result.duration_seconds
                )
            )
        else:
            messages.warning(
                request,
                _("Broadcast completed with issues: {} sent, {} failed.").format(
                    result.sent_count, result.failed_count
                )
            )
        
        log_action(
            user=request.user,
            action='broadcast',
            target=post,
            details=f"Broadcast sent: {result.sent_count} delivered, {result.failed_count} failed",
            request=request
        )
        
    except Exception as e:
        messages.error(request, f"Broadcast failed: {str(e)}")
    
    return redirect('marketing_detail', post_id=post_id)


@login_required
@any_permission_required('can_send_branch_broadcasts', 'can_send_center_broadcasts', 'can_manage_marketing')
@require_POST
def marketing_pause(request, post_id):
    """Pause an ongoing broadcast"""
    post = get_object_or_404(MarketingPost, id=post_id)
    
    if post.status != MarketingPost.STATUS_SENDING:
        messages.error(request, _("Can only pause active broadcasts."))
        return redirect('marketing_detail', post_id=post_id)
    
    post.status = MarketingPost.STATUS_PAUSED
    post.save(update_fields=['status', 'updated_at'])
    
    messages.info(request, _("Broadcast paused."))
    return redirect('marketing_detail', post_id=post_id)


@login_required
@any_permission_required('can_send_branch_broadcasts', 'can_send_center_broadcasts', 'can_manage_marketing')
@require_POST
def marketing_cancel(request, post_id):
    """Cancel a broadcast"""
    post = get_object_or_404(MarketingPost, id=post_id)
    
    if post.status not in [MarketingPost.STATUS_SENDING, MarketingPost.STATUS_PAUSED, MarketingPost.STATUS_SCHEDULED]:
        messages.error(request, _("Cannot cancel this broadcast."))
        return redirect('marketing_detail', post_id=post_id)
    
    post.status = MarketingPost.STATUS_CANCELLED
    post.save(update_fields=['status', 'updated_at'])
    
    messages.info(request, _("Broadcast cancelled."))
    return redirect('marketing_detail', post_id=post_id)


@login_required
@any_permission_required('can_create_marketing_posts', 'can_manage_marketing')
@require_GET
def api_recipient_count(request):
    """API to get recipient count for given scope"""
    scope = request.GET.get('scope', 'branch')
    center_id = request.GET.get('center_id')
    branch_id = request.GET.get('branch_id')
    include_b2c = request.GET.get('include_b2c', 'true') == 'true'
    include_b2b = request.GET.get('include_b2b', 'true') == 'true'
    
    # Create temporary post object for counting
    temp_post = MarketingPost(
        target_scope=scope,
        include_b2c=include_b2c,
        include_b2b=include_b2b
    )
    
    if center_id:
        try:
            temp_post.target_center = TranslationCenter.objects.get(id=center_id)
        except TranslationCenter.DoesNotExist:
            pass
    
    if branch_id:
        try:
            temp_post.target_branch = Branch.objects.get(id=branch_id)
        except Branch.DoesNotExist:
            pass
    
    try:
        count = get_recipient_count(temp_post)
        return JsonResponse({'success': True, 'count': count})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@any_permission_required('can_create_marketing_posts', 'can_manage_marketing')
@require_GET
def api_center_branches(request, center_id):
    """API to get branches for a center"""
    permissions = get_user_scope_permissions(request)
    
    try:
        center = TranslationCenter.objects.get(id=center_id)
        
        # Check access
        if not request.user.is_superuser and center not in permissions['centers']:
            return JsonResponse({'success': False, 'error': 'Access denied'})
        
        branches = center.branches.filter(is_active=True).values('id', 'name')
        
        # Filter to allowed branches if not superuser
        if not request.user.is_superuser:
            allowed_ids = [b.id for b in permissions['branches']]
            branches = [b for b in branches if b['id'] in allowed_ids]
        
        return JsonResponse({'success': True, 'branches': list(branches)})
    
    except TranslationCenter.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Center not found'})

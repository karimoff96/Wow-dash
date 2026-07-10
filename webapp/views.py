"""
Telegram Web App — Django views and JSON API.

All endpoints use POST with a JSON body (except file-upload endpoints which
use multipart/form-data). Every request must supply either:
  - an `init_data` field (the raw initData string provided by Telegram)
  - a `center_id` field (the TranslationCenter primary key)

The backend validates initData's HMAC signature against the center's
bot_token before processing any user-specific data.
"""

import logging
import os
import time
import json
from datetime import timedelta
from urllib.parse import quote as urlquote

from django.http import FileResponse, JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.http import require_GET
from django.core.files.base import ContentFile
from django.utils import timezone

from .auth import get_validated_telegram_user
from organizations.tenant_scope import customer_queryset

logger = logging.getLogger(__name__)


def _json_body(request):
    try:
        return json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return request.POST.dict()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _err(msg: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"ok": False, "error": msg}, status=status)


def _ok(data: dict) -> JsonResponse:
    return JsonResponse({"ok": True, **data})


def _gtf(obj, field: str, lang: str) -> str:
    """Return the translated field value for lang, falling back to the base field."""
    lang = lang if lang in ("uz", "ru", "en") else "uz"
    value = getattr(obj, f"{field}_{lang}", None)
    if not value:
        value = getattr(obj, field, "") or ""
    return value


def _get_center(center_id):
    """Return TranslationCenter or None."""
    from organizations.models import TranslationCenter
    from bot.access import center_can_run_bot
    try:
        center = TranslationCenter.objects.select_related("subscription").get(
            pk=center_id,
            is_active=True,
        )
        return center if center_can_run_bot(center) else None
    except TranslationCenter.DoesNotExist:
        return None


def _auth(request_data: dict):
    """
    Validate initData from request data dict.
    Returns (telegram_user_id, user_dict, center) or (None, None, None).
    """
    init_data = request_data.get("init_data", "")
    center_id = request_data.get("center_id")
    if not init_data or not center_id:
        return None, None, None

    center = _get_center(center_id)
    if not center:
        return None, None, None

    tg_id, user_dict = get_validated_telegram_user(init_data, center)
    return tg_id, user_dict, center


def _count_file_pages(file_content: bytes, file_name: str) -> int:
    """Count pages for a document (PDF) or return 1 for images."""
    _, ext = os.path.splitext(file_name.lower())
    if ext in {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".heic", ".heif"}:
        return 1
    if ext == ".pdf":
        try:
            from io import BytesIO
            import PyPDF2
            reader = PyPDF2.PdfReader(BytesIO(file_content))
            return max(1, len(reader.pages))
        except Exception:
            pass
    return 1


ALLOWED_EXTENSIONS = {
    ".doc", ".docx", ".pdf",
    ".jpg", ".jpeg", ".png", ".gif",
    ".bmp", ".tiff", ".tif", ".webp", ".heic", ".heif",
}


# ---------------------------------------------------------------------------
# HTML entry-point
# ---------------------------------------------------------------------------

@xframe_options_exempt
def webapp_index(request, center_id: int):
    """Serve the single-page Web App HTML (center_id-based URL)."""
    from organizations.models import TranslationCenter
    center = get_object_or_404(TranslationCenter, pk=center_id, is_active=True)
    return render(request, "webapp/index.html", {
        "center": center,
        "center_id": center_id,
    })


@xframe_options_exempt
def webapp_index_subdomain(request):
    """
    Serve the Web App HTML when accessed via a center's own subdomain.

    BotFather Mini App URL format:  https://{subdomain}.multilang.uz/webapp/
    The SubdomainMiddleware already populates request.center from the host.
    """
    center = getattr(request, 'center', None)
    if center is None or not center.is_active:
        from django.http import HttpResponseNotFound
        return HttpResponseNotFound("No active center found for this subdomain.")
    return render(request, "webapp/index.html", {
        "center": center,
        "center_id": center.pk,
    })


@require_GET
@xframe_options_exempt
def payment_return(request):
    """
    Landing page Payme redirects the user to after checkout.
    URL: /webapp/payment-return/?order_id=<id>

    Shows the current order status and a link back to the Telegram bot.
    No authentication required — order details are intentionally minimal.
    """
    from orders.models import Order

    order_id = request.GET.get("order_id")
    order = None
    status = None

    if order_id and order_id.isdigit():
        try:
            order = Order.objects.select_related("branch__center", "bot_user").get(pk=int(order_id))
            status = order.status
        except Order.DoesNotExist:
            pass

    return render(request, "webapp/payment_return.html", {
        "order": order,
        "status": status,
    })


# ---------------------------------------------------------------------------
# API: /webapp/api/init/
# ---------------------------------------------------------------------------

@csrf_exempt
def api_init(request):
    """
    POST {init_data, center_id}

    Validates Telegram initData, looks up or creates the BotUser,
    and returns everything the front-end needs for the order flow:
    user info, center details, categories+products, and payment card info.
    """
    if request.method != "POST":
        return _err("Method not allowed", 405)

    import json as json_module
    try:
        body = json_module.loads(request.body)
    except Exception:
        body = request.POST.dict()

    tg_id, user_dict, center = _auth(body)
    if tg_id is None:
        logger.warning(
            "api_init: auth failed — center_id=%s init_data_preview=%r",
            body.get("center_id"), str(body.get("init_data", ""))[:80],
        )
        return _err("Invalid or expired initData", 401)

    from accounts.models import BotUser, AdditionalInfo
    from services.models import Category, Language

    # ------------------------------------------------------------------
    # Find existing BotUser for this (tg_id, center) pair
    # ------------------------------------------------------------------
    bot_user = BotUser.objects.filter(user_id=tg_id, center=center).first()

    user_payload = None
    if bot_user and bot_user.is_active:
        user_payload = {
            "id": bot_user.id,
            "name": bot_user.name,
            "phone": bot_user.phone,
            "language": bot_user.language,
            "is_agency": bot_user.is_agency,
            "branch_id": bot_user.branch_id,
            "branch_name": bot_user.branch.name if bot_user.branch else None,
            "registered": True,
        }
    elif bot_user:
        # Exists but not yet fully registered
        user_payload = {
            "id": bot_user.id,
            "name": bot_user.name or "",
            "phone": bot_user.phone or "",
            "language": bot_user.language,
            "registered": False,
            "tg_username": user_dict.get("username", ""),
            "tg_first_name": user_dict.get("first_name", ""),
        }
    else:
        user_payload = {
            "id": None,
            "registered": False,
            "tg_username": user_dict.get("username", ""),
            "tg_first_name": user_dict.get("first_name", ""),
        }

    # ------------------------------------------------------------------
    # Branches for this center
    # ------------------------------------------------------------------
    from organizations.models import Branch
    branches = list(
        Branch.objects.filter(center=center, is_active=True)
        .values("id", "name", "address", "phone", "is_main", "show_pricelist")
    )

    # ------------------------------------------------------------------
    # Categories + products (per branch)
    # ------------------------------------------------------------------
    # If user has a branch, only load that branch's categories.
    # Otherwise load all center branches' categories.
    branch_ids = (
        [bot_user.branch_id]
        if (bot_user and bot_user.branch_id)
        else [b["id"] for b in branches]
    )

    categories_qs = Category.objects.filter(
        branch_id__in=branch_ids, is_active=True
    ).prefetch_related("product_set", "languages")

    lang = (bot_user.language or "uz") if bot_user else "uz"

    categories = []
    for cat in categories_qs:
        products = []
        for prod in cat.product_set.filter(is_active=True):
            products.append({
                "id": prod.id,
                "name": _gtf(prod, "name", lang),
                "min_pages": prod.min_pages,
                "estimated_days": prod.estimated_days,
                "charging": cat.charging,
                "ordinary_first_page_price": float(prod.ordinary_first_page_price),
                "ordinary_other_page_price": float(prod.ordinary_other_page_price),
                "agency_first_page_price": float(prod.agency_first_page_price),
                "agency_other_page_price": float(prod.agency_other_page_price),
                "user_copy_price": float(
                    prod.user_copy_price_decimal
                    if prod.user_copy_price_decimal is not None
                    else 0
                ),
                "agency_copy_price": float(
                    prod.agency_copy_price_decimal
                    if prod.agency_copy_price_decimal is not None
                    else 0
                ),
            })

        languages = [
            {
                "id": lang.id,
                "name": lang.name,
                "short_name": lang.short_name,
                "agency_page_price": float(lang.agency_page_price),
                "agency_other_page_price": float(lang.agency_other_page_price),
                "agency_copy_price": float(lang.agency_copy_price),
                "ordinary_page_price": float(lang.ordinary_page_price),
                "ordinary_other_page_price": float(lang.ordinary_other_page_price),
                "ordinary_copy_price": float(lang.ordinary_copy_price),
            }
            for lang in cat.languages.all()
        ]

        categories.append({
            "id": cat.id,
            "name": _gtf(cat, "name", lang),
            "description": _gtf(cat, "description", lang),
            "charging": cat.charging,
            "written_verification_required": cat.written_verification_required,
            "branch_id": cat.branch_id,
            "languages": languages,
            "products": products,
        })

    # ------------------------------------------------------------------
    # Payment card info (for card payment screen)
    # Resolve branch: registered user's branch → center's main branch → None
    # ------------------------------------------------------------------
    card_info = None
    try:
        _card_branch = (
            bot_user.branch
            if (bot_user and bot_user.branch_id)
            else None
        )
        ai = AdditionalInfo.get_for_branch(_card_branch)
        if ai and ai.bank_card:
            card_info = {
                "bank_card": ai.bank_card,
                "holder_name": ai.holder_name or "",
            }
    except Exception as e:
        logger.warning("card_info lookup failed: %s", e)

    return _ok({
        "user": user_payload,
        "center": {
            "id": center.id,
            "name": center.name,
            "phone": center.phone or "",
            "logo": center.logo.url if center.logo else None,
            "payme_enabled": center.payme_enabled and not center.payme_sandbox,
        },
        "branches": branches,
        "categories": categories,
        "card_info": card_info,
    })


# ---------------------------------------------------------------------------
# API: /webapp/api/register/
# ---------------------------------------------------------------------------

@csrf_exempt
def api_register(request):
    """
    POST {init_data, center_id, name, phone, language, branch_id}

    Creates or updates the BotUser and marks them as active (registered).
    """
    if request.method != "POST":
        return _err("Method not allowed", 405)

    import json as json_module
    try:
        body = json_module.loads(request.body)
    except Exception:
        body = request.POST.dict()

    tg_id, user_dict, center = _auth(body)
    if tg_id is None:
        return _err("Invalid or expired initData", 401)

    name = (body.get("name") or "").strip()
    phone = (body.get("phone") or "").strip()
    language = body.get("language", "uz")
    branch_id = body.get("branch_id")

    if not name:
        return _err("Name is required")
    if not phone:
        return _err("Phone is required")
    if language not in ("uz", "ru", "en"):
        language = "uz"

    from accounts.models import BotUser
    from organizations.models import Branch

    branch = None
    if branch_id:
        branch = Branch.objects.filter(pk=branch_id, center=center, is_active=True).first()

    # Auto-select the is_main branch (or first active branch) when no valid branch_id given
    if not branch:
        branches = list(Branch.objects.filter(center=center, is_active=True).order_by('-is_main', 'name'))
        if branches:
            branch = next((b for b in branches if b.is_main), branches[0])

    bot_user, created = BotUser.objects.get_or_create(
        user_id=tg_id,
        center=center,
        defaults={
            "name": name,
            "phone": phone,
            "language": language,
            "username": user_dict.get("username", ""),
            "branch": branch,
            "is_active": True,
        },
    )
    if not created:
        bot_user.name = name
        bot_user.phone = phone
        bot_user.language = language
        bot_user.username = user_dict.get("username", "")
        if branch:
            bot_user.branch = branch
        bot_user.is_active = True
        bot_user.save()

    return _ok({
        "user": {
            "id": bot_user.id,
            "name": bot_user.name,
            "phone": bot_user.phone,
            "language": bot_user.language,
            "registered": True,
            "branch_id": bot_user.branch_id,
            "branch_name": bot_user.branch.name if bot_user.branch else None,
        }
    })


# ---------------------------------------------------------------------------
# API: /webapp/api/order/create/
# ---------------------------------------------------------------------------

@csrf_exempt
def api_create_order(request):
    """
    POST multipart/form-data:
      init_data, center_id, product_id, language_id (opt),
      copy_number (default 0), payment_type (cash|card),
      description (opt), name_clarifications (opt),
      files[] — one or more document files

    Creates the Order + OrderMedia records, computes total_price,
    then triggers the channel notification (same as the bot does).
    """
    if request.method != "POST":
        return _err("Method not allowed", 405)

    # POST fields (multipart)
    data = request.POST
    tg_id, user_dict, center = _auth(data)
    if tg_id is None:
        return _err("Invalid or expired initData", 401)

    from accounts.models import BotUser
    from services.models import Product, Language
    from orders.models import Order, OrderMedia

    # ------------------------------------------------------------------
    # Resolve bot_user
    # ------------------------------------------------------------------
    bot_user = BotUser.objects.filter(user_id=tg_id, center=center, is_active=True).first()
    if not bot_user:
        return _err("User not registered", 403)
    if not bot_user.branch:
        return _err("No branch assigned to user", 400)

    # ------------------------------------------------------------------
    # Resolve product
    # ------------------------------------------------------------------
    product_id = data.get("product_id")
    if not product_id:
        return _err("product_id required")
    try:
        product = Product.objects.get(pk=product_id, is_active=True,
                                      category__branch=bot_user.branch)
    except Product.DoesNotExist:
        return _err("Product not found")

    # ------------------------------------------------------------------
    # Language (optional)
    # ------------------------------------------------------------------
    language_obj = None
    lang_id = data.get("language_id")
    if lang_id:
        try:
            language_obj = Language.objects.get(pk=lang_id)
        except Language.DoesNotExist:
            pass

    # ------------------------------------------------------------------
    # Other fields
    # ------------------------------------------------------------------
    try:
        copy_number = max(0, int(data.get("copy_number", 0)))
    except (ValueError, TypeError):
        copy_number = 0

    payment_type = data.get("payment_type", "cash")
    if payment_type not in ("cash", "card"):
        payment_type = "cash"

    description = (data.get("description") or "").strip()
    name_clarifications = (data.get("name_clarifications") or "").strip()

    # ------------------------------------------------------------------
    # Validate uploaded files
    # ------------------------------------------------------------------
    uploaded_files = request.FILES.getlist("files[]")
    if not uploaded_files:
        return _err("At least one file is required")

    for f in uploaded_files:
        _, ext = os.path.splitext(f.name.lower())
        if ext not in ALLOWED_EXTENSIONS:
            return _err(f"File type not allowed: {f.name}")

    # ------------------------------------------------------------------
    # Create Order (price=0 initially, updated after pages are counted)
    # ------------------------------------------------------------------
    initial_status = "payment_pending" if payment_type == "card" else "pending"
    payment_source = "payme" if (payment_type == "card" and center.payme_enabled and not center.payme_sandbox) else "manual"

    order = Order(
        branch=bot_user.branch,
        bot_user=bot_user,
        product=product,
        language=language_obj,
        copy_number=copy_number,
        payment_type=payment_type,
        payment_source=payment_source,
        description=description or None,
        name_clarifications=name_clarifications or None,
        status=initial_status,
        is_active=True,
        total_price=0,
        total_pages=0,
    )
    order.save()

    # ------------------------------------------------------------------
    # Create OrderMedia records and tally total pages
    # ------------------------------------------------------------------
    total_pages = 0
    for f in uploaded_files:
        content = f.read()
        pages = _count_file_pages(content, f.name)
        total_pages += pages

        media = OrderMedia()
        media.pages = pages
        media.file.save(f.name, ContentFile(content), save=True)
        order.files.add(media)

    order.total_pages = max(1, total_pages)
    order.save(update_fields=["total_pages"])

    # ------------------------------------------------------------------
    # Calculate price using the Order model's own method
    # ------------------------------------------------------------------
    try:
        breakdown = order.get_price_breakdown()
        order.total_price = breakdown.get("total_price", 0)
    except Exception as e:
        logger.warning(f"WebApp: price breakdown failed for order {order.pk}: {e}")
        # Fallback: simple manual calculation
        is_agency = bot_user.is_agency
        if product.category.charging == "dynamic":
            fp = float(product.agency_first_page_price if is_agency else product.ordinary_first_page_price)
            op = float(product.agency_other_page_price if is_agency else product.ordinary_other_page_price)
            base = fp if order.total_pages == 1 else fp + op * (order.total_pages - 1)
        else:
            base = float(product.agency_first_page_price if is_agency else product.ordinary_first_page_price)

        copy_price_dec = (
            product.agency_copy_price_decimal if is_agency else product.user_copy_price_decimal
        )
        copy_charge = float(copy_price_dec or 0) * copy_number
        order.total_price = base + copy_charge

    order.save(update_fields=["total_price"])

    # ------------------------------------------------------------------
    # Trigger Telegram channel notification (same function the bot uses)
    # ------------------------------------------------------------------
    try:
        from bot.notification_service import send_order_notification
        send_order_notification(order.id)
    except Exception as e:
        logger.warning(f"WebApp: channel notification failed for order {order.pk}: {e}")

    # ------------------------------------------------------------------
    # Payme checkout URL (when center has Payme enabled and payment is card)
    # ------------------------------------------------------------------
    payme_checkout_url = None
    if payment_type == "card" and center.payme_enabled and not center.payme_sandbox:
        try:
            from orders.payme_gateway import build_payme_checkout_url, PaymeIntegrationError, check_payme_config
            from django.conf import settings as django_settings
            ok, reason = check_payme_config(center)
            if not ok:
                logger.warning(f"WebApp: Payme config not ready for center {center.id}: {reason}")
            else:
                main_domain = getattr(django_settings, "MAIN_DOMAIN", "multilang.uz")
                sub = center.subdomain if center.subdomain else None
                if sub:
                    return_url = f"https://{sub}.{main_domain}/webapp/payment-return/?order_id={order.id}"
                else:
                    return_url = f"https://{main_domain}/webapp/payment-return/?order_id={order.id}"
                lang = bot_user.language or "uz"
                payme_checkout_url, _, _ = build_payme_checkout_url(
                    order, lang, callback_url=return_url, center=center
                )
        except Exception as exc:
            logger.error(f"WebApp: Payme checkout URL build failed for order {order.pk}: {exc}")

    return _ok({
        "order_id": order.id,
        "order_number": order.get_order_number(),
        "total_price": float(order.total_price),
        "total_pages": order.total_pages,
        "status": order.status,
        "payme_checkout_url": payme_checkout_url,
    })


# ---------------------------------------------------------------------------
# API: /webapp/api/orders/
# ---------------------------------------------------------------------------

@csrf_exempt
def api_my_orders(request):
    """
    POST {init_data, center_id}

    Returns the user's last 20 orders for this center, newest first.
    """
    if request.method != "POST":
        return _err("Method not allowed", 405)

    import json as json_module
    try:
        body = json_module.loads(request.body)
    except Exception:
        body = request.POST.dict()

    tg_id, _, center = _auth(body)
    if tg_id is None:
        return _err("Invalid or expired initData", 401)

    from accounts.models import BotUser
    from orders.models import Order

    bot_user = BotUser.objects.filter(user_id=tg_id, center=center).first()
    if not bot_user:
        return _ok({"orders": []})

    orders_qs = (
        Order.objects.filter(bot_user=bot_user)
        .select_related("product", "product__category", "branch")
        .order_by("-created_at")[:20]
    )

    STATUS_LABELS = {
        "pending": {"uz": "🕐 Kutilmoqda", "ru": "🕐 Ожидание", "en": "🕐 Pending"},
        "payment_pending": {"uz": "💳 To'lov kutilmoqda", "ru": "💳 Ожидает оплаты", "en": "💳 Awaiting Payment"},
        "payment_received": {"uz": "📨 Chek qabul qilindi", "ru": "📨 Чек получен", "en": "📨 Receipt Received"},
        "payment_confirmed": {"uz": "✅ To'lov tasdiqlandi", "ru": "✅ Оплата подтверждена", "en": "✅ Payment Confirmed"},
        "in_progress": {"uz": "🔄 Jarayonda", "ru": "🔄 В процессе", "en": "🔄 In Progress"},
        "ready": {"uz": "✅ Tayyor", "ru": "✅ Готов", "en": "✅ Ready"},
        "completed": {"uz": "🎉 Yakunlandi", "ru": "🎉 Завершён", "en": "🎉 Completed"},
        "cancelled": {"uz": "❌ Bekor qilindi", "ru": "❌ Отменён", "en": "❌ Cancelled"},
    }

    lang = bot_user.language or "uz"
    orders = []
    for o in orders_qs:
        status_labels = STATUS_LABELS.get(o.status, {})
        orders.append({
            "id": o.id,
            "order_number": o.get_order_number(),
            "product": _gtf(o.product, "name", lang),
            "category": _gtf(o.product.category, "name", lang),
            "total_price": float(o.total_price),
            "total_pages": o.total_pages,
            "copy_number": o.copy_number,
            "status": o.status,
            "status_label": status_labels.get(lang, o.get_status_display()),
            "payment_type": o.payment_type,
            "created_at": o.created_at.strftime("%d.%m.%Y %H:%M"),
        })

    return _ok({"orders": orders, "language": lang})


# ---------------------------------------------------------------------------
# API: /webapp/api/orders/<order_id>/
# ---------------------------------------------------------------------------

@csrf_exempt
def api_order_detail(request, order_id: int):
    """
    POST {init_data, center_id}

    Returns full detail of a single order including status, files, and receipt info.
    """
    if request.method != "POST":
        return _err("Method not allowed", 405)

    import json as json_module
    try:
        body = json_module.loads(request.body)
    except Exception:
        body = request.POST.dict()

    tg_id, _, center = _auth(body)
    if tg_id is None:
        return _err("Invalid or expired initData", 401)

    from accounts.models import BotUser, AdditionalInfo
    from orders.models import Order

    bot_user = BotUser.objects.filter(user_id=tg_id, center=center).first()
    if not bot_user:
        return _err("User not found", 403)

    try:
        order = Order.objects.select_related(
            "product", "product__category", "branch", "language"
        ).prefetch_related("files", "timeline").get(pk=order_id, bot_user=bot_user)
    except Order.DoesNotExist:
        return _err("Order not found", 404)

    lang = bot_user.language or "uz"

    STATUS_LABELS = {
        "pending": {"uz": "🕐 Kutilmoqda", "ru": "🕐 Ожидание", "en": "🕐 Pending"},
        "payment_pending": {"uz": "💳 To'lov kutilmoqda", "ru": "💳 Ожидает оплаты", "en": "💳 Awaiting Payment"},
        "payment_received": {"uz": "📨 Chek qabul qilindi", "ru": "📨 Чек получен", "en": "📨 Receipt Received"},
        "payment_confirmed": {"uz": "✅ To'lov tasdiqlandi", "ru": "✅ Оплата подтверждена", "en": "✅ Payment Confirmed"},
        "in_progress": {"uz": "🔄 Jarayonda", "ru": "🔄 В процессе", "en": "🔄 In Progress"},
        "ready": {"uz": "✅ Tayyor", "ru": "✅ Готов", "en": "✅ Ready"},
        "completed": {"uz": "🎉 Yakunlandi", "ru": "🎉 Завершён", "en": "🎉 Completed"},
        "cancelled": {"uz": "❌ Bekor qilindi", "ru": "❌ Отменён", "en": "❌ Cancelled"},
    }

    # Card info for payment_pending orders
    payme_enabled = center.payme_enabled and not center.payme_sandbox
    is_payment_pending = order.status == "payment_pending"

    card_info = None
    if is_payment_pending and not payme_enabled:
        try:
            ai = AdditionalInfo.get_for_branch(order.branch)
            if ai and ai.bank_card:
                card_info = {
                    "bank_card": ai.bank_card,
                    "holder_name": ai.holder_name or "",
                }
        except Exception:
            pass

    status_labels = STATUS_LABELS.get(order.status, {})
    return _ok({
        "order": {
            "id": order.id,
            "order_number": order.get_order_number(),
            "product": _gtf(order.product, "name", lang) if order.product else "",
            "category": _gtf(order.product.category, "name", lang) if order.product and order.product.category else "",
            "language": order.language.name if order.language else "",
            "total_price": float(order.total_price),
            "total_pages": order.total_pages,
            "copy_number": order.copy_number,
            "status": order.status,
            "status_label": status_labels.get(lang, order.get_status_display()),
            "payment_type": order.payment_type,
            "description": order.description or "",
            "name_clarifications": order.name_clarifications or "",
            "created_at": order.created_at.strftime("%d.%m.%Y %H:%M"),
            "branch_name": order.branch.name if order.branch else "",
            "branch_address": order.branch.address if order.branch else "",
            "files_count": order.files.count(),
            "files": [
                {
                    "id": media.pk,
                    "name": media.file_name,
                    "pages": media.pages,
                }
                for media in order.files.all()
            ],
            "timeline": [
                {
                    "type": event.event_type,
                    "data": event.data,
                    "created_at": event.created_at.isoformat(),
                }
                for event in order.timeline.exclude(
                    event_type="comment",
                    actor__isnull=False,
                )
            ],
            "has_receipt": bool(order.recipt),
            "can_upload_receipt": is_payment_pending and not payme_enabled,
            "can_pay_with_payme": is_payment_pending and payme_enabled,
        },
        "card_info": card_info,
        "language": lang,
    })


# ---------------------------------------------------------------------------
# API: /webapp/api/orders/<order_id>/payme-checkout/
# ---------------------------------------------------------------------------

@csrf_exempt
def api_order_payme_checkout(request, order_id: int):
    """
    POST {init_data, center_id}

    Generates a fresh Payme checkout URL for an existing payment_pending order
    whose center has Payme integration enabled. Used when the user leaves the
    Payme page without paying and wants to retry from "My Orders".
    """
    if request.method != "POST":
        return _err("Method not allowed", 405)

    import json as json_module
    try:
        body = json_module.loads(request.body)
    except Exception:
        body = request.POST.dict()

    tg_id, _, center = _auth(body)
    if tg_id is None:
        return _err("Invalid or expired initData", 401)

    from accounts.models import BotUser
    from orders.models import Order

    bot_user = BotUser.objects.filter(user_id=tg_id, center=center, is_active=True).first()
    if not bot_user:
        return _err("User not found", 403)

    try:
        order = Order.objects.get(pk=order_id, bot_user=bot_user)
    except Order.DoesNotExist:
        return _err("Order not found", 404)

    if order.status != "payment_pending":
        return _err("Order is not awaiting payment", 400)

    if not (center.payme_enabled and not center.payme_sandbox):
        return _err("Payme is not enabled for this center", 400)

    try:
        from orders.payme_gateway import build_payme_checkout_url, PaymeIntegrationError, check_payme_config
        from django.conf import settings as django_settings

        ok, reason = check_payme_config(center)
        if not ok:
            return _err(f"Payme configuration error: {reason}", 400)

        main_domain = getattr(django_settings, "MAIN_DOMAIN", "multilang.uz")
        sub = center.subdomain if center.subdomain else None
        if sub:
            return_url = f"https://{sub}.{main_domain}/webapp/payment-return/?order_id={order.id}"
        else:
            return_url = f"https://{main_domain}/webapp/payment-return/?order_id={order.id}"

        lang = bot_user.language or "uz"
        checkout_url, _, _ = build_payme_checkout_url(
            order, lang, callback_url=return_url, center=center
        )
    except Exception as exc:
        logger.error(f"WebApp: Payme retry checkout URL build failed for order {order.pk}: {exc}")
        return _err("Could not generate payment link", 500)

    return _ok({"checkout_url": checkout_url})


# ---------------------------------------------------------------------------
# API: /webapp/api/orders/<order_id>/receipt/
# ---------------------------------------------------------------------------

@csrf_exempt
def api_upload_receipt(request, order_id: int):
    """
    POST multipart: init_data, center_id, receipt (file)

    Uploads a payment receipt image for an existing card-payment order.
    Updates status to payment_received and triggers bot notification.
    """
    if request.method != "POST":
        return _err("Method not allowed", 405)

    tg_id, _, center = _auth(request.POST)
    if tg_id is None:
        return _err("Invalid or expired initData", 401)

    from accounts.models import BotUser
    from orders.models import Order

    bot_user = BotUser.objects.filter(user_id=tg_id, center=center, is_active=True).first()
    if not bot_user:
        return _err("User not found", 403)

    try:
        order = Order.objects.get(pk=order_id, bot_user=bot_user)
    except Order.DoesNotExist:
        return _err("Order not found", 404)

    receipt_file = request.FILES.get("receipt")
    if not receipt_file:
        return _err("receipt file required")

    content = receipt_file.read()
    order.recipt.save(receipt_file.name, ContentFile(content), save=False)
    order.status = "payment_received"
    order.save(update_fields=["recipt", "status", "updated_at"])

    # Notify via bot
    try:
        from bot.main import send_order_status_notification
        send_order_status_notification(order, "payment_pending", "payment_received")
    except Exception as e:
        logger.warning(f"WebApp: receipt notification failed for order {order.pk}: {e}")

    return _ok({"status": "payment_received"})


# ---------------------------------------------------------------------------
# API: /webapp/api/profile/
# ---------------------------------------------------------------------------

@csrf_exempt
def api_profile(request):
    """
    GET or POST  — view / update the current user's profile.

    GET  {init_data, center_id}  → returns full profile info.
    POST {init_data, center_id, name?, phone?, language?, branch_id?}
         → updates any supplied fields and returns the updated profile.
    """
    if request.method not in ("GET", "POST"):
        return _err("Method not allowed", 405)

    import json as json_module

    # Support both query params (GET) and JSON body (POST)
    if request.method == "GET":
        body = request.GET.dict()
    else:
        try:
            body = json_module.loads(request.body)
        except Exception:
            body = request.POST.dict()

    tg_id, _, center = _auth(body)
    if tg_id is None:
        return _err("Invalid or expired initData", 401)

    from accounts.models import BotUser
    from organizations.models import Branch

    bot_user = BotUser.objects.filter(user_id=tg_id, center=center, is_active=True).first()
    if not bot_user:
        return _err("User not found", 403)

    if request.method == "POST":
        # Update allowed fields
        name = body.get("name", "").strip()
        phone = body.get("phone", "").strip()
        language = body.get("language", "").strip()
        branch_id = body.get("branch_id")

        update_fields = []
        if name:
            bot_user.name = name
            update_fields.append("name")
        if phone:
            bot_user.phone = phone
            update_fields.append("phone")
        if language in ("uz", "ru", "en"):
            bot_user.language = language
            update_fields.append("language")
        if branch_id:
            try:
                branch = Branch.objects.get(pk=int(branch_id), center=center, is_active=True)
                bot_user.branch = branch
                update_fields.append("branch")
            except (Branch.DoesNotExist, ValueError):
                return _err("Branch not found", 404)
        if update_fields:
            bot_user.save(update_fields=update_fields)

    # Build branches list for front-end
    branches = list(
        Branch.objects.filter(center=center, is_active=True)
        .values("id", "name", "address", "phone", "is_main")
    )

    return _ok({
        "profile": {
            "id": bot_user.id,
            "name": bot_user.name,
            "phone": bot_user.phone,
            "language": bot_user.language,
            "is_agency": bot_user.is_agency,
            "branch_id": bot_user.branch_id,
            "branch_name": bot_user.branch.name if bot_user.branch else None,
            "branch_address": bot_user.branch.address if bot_user.branch else None,
            "joined": bot_user.created_at.strftime("%d.%m.%Y") if bot_user.created_at else "",
        },
        "branches": branches,
    })


# ---------------------------------------------------------------------------
# API: /webapp/api/center-info/
# ---------------------------------------------------------------------------

@csrf_exempt
def api_center_info(request):
    """
    POST {init_data, center_id}

    Returns about_us, help_text, other_services (description), support
    phone and branch info from AdditionalInfo for the user's branch.
    """
    if request.method != "POST":
        return _err("Method not allowed", 405)

    import json as json_module
    try:
        body = json_module.loads(request.body)
    except Exception:
        body = request.POST.dict()

    tg_id, _, center = _auth(body)
    if tg_id is None:
        return _err("Invalid or expired initData", 401)

    from accounts.models import BotUser, AdditionalInfo

    bot_user = BotUser.objects.filter(user_id=tg_id, center=center, is_active=True).first()
    if not bot_user:
        return _err("User not found", 403)

    info = AdditionalInfo.get_for_user(bot_user) if bot_user else AdditionalInfo.get_for_branch(None)

    def _translated(obj, field, lang):
        """Return lang-specific field, fallback to uz then any non-empty."""
        if not obj:
            return ""
        for suffix in (lang, "uz", "ru", "en"):
            val = getattr(obj, f"{field}_{suffix}", None)
            if val:
                return val
        return ""

    lang = (bot_user.language or "uz") if bot_user else "uz"

    return _ok({
        "about_us": _translated(info, "about_us", lang),
        "help_text": _translated(info, "help_text", lang),
        "description": _translated(info, "description", lang),
        "support_phone": info.support_phone if info else "",
        "support_telegram": info.support_telegram if info else "",
        "branch": {
            "name": bot_user.branch.name if bot_user and bot_user.branch else "",
            "address": bot_user.branch.address if bot_user and bot_user.branch else "",
            "phone": bot_user.branch.phone if bot_user and bot_user.branch else "",
        } if bot_user else {},
    })


# ---------------------------------------------------------------------------
# API: /webapp/api/pricelist/
# ---------------------------------------------------------------------------

@csrf_exempt
def api_pricelist(request):
    """
    POST {init_data, center_id}

    Returns the price list for the user's branch (if show_pricelist=True).
    Structure: [{category, charging, products: [{name, prices}]}]
    """
    if request.method != "POST":
        return _err("Method not allowed", 405)

    import json as json_module
    try:
        body = json_module.loads(request.body)
    except Exception:
        body = request.POST.dict()

    tg_id, _, center = _auth(body)
    if tg_id is None:
        return _err("Invalid or expired initData", 401)

    from accounts.models import BotUser
    from services.models import Category

    bot_user = BotUser.objects.filter(user_id=tg_id, center=center, is_active=True).first()
    if not bot_user:
        return _err("User not found", 403)

    lang = bot_user.language or "uz"
    is_agency = bot_user.is_agency

    # Pricelist requires branch with show_pricelist flag
    if not bot_user.branch:
        return _ok({"available": False, "categories": []})
    if not bot_user.branch.show_pricelist:
        return _ok({"available": False, "categories": []})

    categories_qs = Category.objects.filter(
        branch=bot_user.branch, is_active=True
    ).prefetch_related("product_set").order_by("name_uz")

    def _name(obj, l):
        for suffix in (l, "uz", "ru", "en"):
            v = getattr(obj, f"name_{suffix}", None)
            if v:
                return v
        return str(obj)

    result = []
    for cat in categories_qs:
        products_qs = cat.product_set.filter(is_active=True).order_by("name_uz")
        products = []
        for p in products_qs:
            if is_agency:
                first_price = float(p.agency_first_page_price or 0)
                other_price = float(p.agency_other_page_price or 0)
                copy_price_dec = float(p.agency_copy_price_decimal or 0)
                copy_price_pct = float(p.agency_copy_price_percentage or 0)
            else:
                first_price = float(p.ordinary_first_page_price or 0)
                other_price = float(p.ordinary_other_page_price or 0)
                copy_price_dec = float(p.user_copy_price_decimal or 0)
                copy_price_pct = float(p.user_copy_price_percentage or 0)

            products.append({
                "id": p.id,
                "name": _name(p, lang),
                "estimated_days": p.estimated_days,
                "first_price": first_price,
                "other_price": other_price,
                "copy_price_decimal": copy_price_dec,
                "copy_price_percentage": copy_price_pct,
            })
        if products:
            result.append({
                "id": cat.id,
                "name": _name(cat, lang),
                "charging": cat.charging,
                "products": products,
            })

    return _ok({
        "available": True,
        "branch_name": bot_user.branch.name,
        "is_agency": is_agency,
        "categories": result,
    })


@csrf_exempt
def api_quote_create(request):
    """Create a customer quote request with a deterministic price snapshot."""
    if request.method != "POST":
        return _err("Method not allowed", 405)

    data = request.POST if request.content_type and request.content_type.startswith("multipart/") else _json_body(request)
    tg_id, _, center = _auth(data)
    if tg_id is None:
        return _err("Invalid or expired initData", 401)
    if not center.workflow_automation_enabled:
        return _err("Quote workflow is not enabled for this center", 404)

    from accounts.models import BotUser
    from orders.models import OrderMedia, Quote, QuoteLine
    from services.models import Language, Product

    bot_user = BotUser.objects.filter(user_id=tg_id, center=center, is_active=True).select_related("branch").first()
    if not bot_user or not bot_user.branch:
        return _err("Registered user with a branch is required", 403)

    product = Product.objects.filter(
        pk=data.get("product_id"),
        category__branch=bot_user.branch,
        is_active=True,
    ).select_related("category").first()
    if not product:
        return _err("Product not found", 404)

    language = None
    if data.get("language_id"):
        language = product.category.languages.filter(
            pk=data.get("language_id"),
            branch=bot_user.branch,
        ).first()
        if language is None:
            return _err("Language not available for this product", 404)
    try:
        pages = max(1, int(data.get("pages", 1)))
        copies = max(0, int(data.get("copies", 0)))
    except (TypeError, ValueError):
        return _err("Invalid page or copy count")

    urgency = data.get("urgency", QuoteLine.URGENCY_NORMAL)
    if urgency not in {QuoteLine.URGENCY_NORMAL, QuoteLine.URGENCY_EXPRESS}:
        return _err("Invalid urgency")

    quoted_total = product.get_combined_total_price(
        language=language,
        is_agency=bot_user.is_agency,
        pages=pages,
        copies=copies,
    )
    quote = Quote.objects.create(
        branch=bot_user.branch,
        bot_user=bot_user,
        customer_name=bot_user.display_name,
        customer_phone=bot_user.phone or "",
        source=Quote.SOURCE_MINI_APP,
        status=Quote.STATUS_SUBMITTED,
        valid_until=timezone.localdate() + timedelta(days=7),
        notes=(data.get("notes") or "").strip(),
    )
    line = QuoteLine.objects.create(
        quote=quote,
        product=product,
        language=language,
        pages=pages,
        copies=copies,
        urgency=urgency,
        description=(data.get("description") or "").strip(),
        unit_price=quoted_total / pages,
        total_price=quoted_total,
        price_snapshot={
            "product_id": product.pk,
            "language_id": language.pk if language else None,
            "pages": pages,
            "copies": copies,
            "is_agency": bot_user.is_agency,
            "urgency": urgency,
            "product_first_page": str(product.get_first_page_price(bot_user.is_agency)),
            "product_other_page": str(product.get_other_page_price(bot_user.is_agency)),
            "product_copy": str(
                (product.agency_copy_price_decimal if bot_user.is_agency else product.user_copy_price_decimal)
                or 0
            ),
            "language_first_page": str(
                (language.agency_page_price if bot_user.is_agency else language.ordinary_page_price)
                if language else 0
            ),
            "language_other_page": str(
                (language.agency_other_page_price if bot_user.is_agency else language.ordinary_other_page_price)
                if language else 0
            ),
            "language_copy": str(
                (language.agency_copy_price if bot_user.is_agency else language.ordinary_copy_price)
                if language else 0
            ),
            "total": str(quoted_total),
            "calculated_at": timezone.now().isoformat(),
        },
    )
    quote.recalculate()

    for uploaded_file in request.FILES.getlist("files[]"):
        _, extension = os.path.splitext(uploaded_file.name.lower())
        if extension not in ALLOWED_EXTENSIONS:
            quote.delete()
            return _err(f"File type not allowed: {uploaded_file.name}")
        content = uploaded_file.read()
        media = OrderMedia(pages=_count_file_pages(content, uploaded_file.name))
        media.file.save(uploaded_file.name, ContentFile(content), save=True)
        quote.files.add(media)

    return _ok({
        "quote": {
            "id": quote.pk,
            "reference": str(quote.reference),
            "version": quote.version,
            "status": quote.status,
            "total": float(quote.total),
            "valid_until": quote.valid_until.isoformat(),
        }
    })


@csrf_exempt
def api_my_quotes(request):
    if request.method != "POST":
        return _err("Method not allowed", 405)
    data = _json_body(request)
    tg_id, _, center = _auth(data)
    if tg_id is None:
        return _err("Invalid or expired initData", 401)
    if not center.workflow_automation_enabled:
        return _err("Quote workflow is not enabled for this center", 404)
    from accounts.models import BotUser
    from orders.models import Quote
    bot_user = BotUser.objects.filter(user_id=tg_id, center=center).first()
    if not bot_user:
        return _err("User not registered", 403)
    quotes = customer_queryset(
        Quote.objects.prefetch_related("lines"), center, bot_user
    ).order_by("-created_at")
    return _ok({"quotes": [{
        "id": quote.pk,
        "reference": str(quote.reference),
        "version": quote.version,
        "status": quote.status,
        "total": float(quote.total),
        "valid_until": quote.valid_until.isoformat() if quote.valid_until else None,
        "order_ids": list(quote.orders.values_list("id", flat=True)),
        "created_at": quote.created_at.isoformat(),
    } for quote in quotes[:100]]})


@csrf_exempt
def api_accept_quote(request, quote_id):
    if request.method != "POST":
        return _err("Method not allowed", 405)
    data = _json_body(request)
    tg_id, _, center = _auth(data)
    if tg_id is None:
        return _err("Invalid or expired initData", 401)
    if not center.workflow_automation_enabled:
        return _err("Quote workflow is not enabled for this center", 404)
    from accounts.models import BotUser
    from orders.models import Quote
    from orders.workflow_service import accept_quote
    bot_user = BotUser.objects.filter(user_id=tg_id, center=center, is_active=True).first()
    quote = customer_queryset(Quote.objects.filter(pk=quote_id), center, bot_user).first()
    if not bot_user or not quote:
        return _err("Quote not found", 404)
    try:
        orders = accept_quote(quote, bot_user)
    except (ValueError, PermissionError) as exc:
        return _err(str(exc), 409)
    return _ok({"quote_id": quote.pk, "order_ids": [order.pk for order in orders]})


@csrf_exempt
def api_reject_quote(request, quote_id):
    if request.method != "POST":
        return _err("Method not allowed", 405)
    data = _json_body(request)
    tg_id, _, center = _auth(data)
    if tg_id is None:
        return _err("Invalid or expired initData", 401)
    if not center.workflow_automation_enabled:
        return _err("Quote workflow is not enabled for this center", 404)
    from accounts.models import BotUser
    from orders.models import Quote
    bot_user = BotUser.objects.filter(user_id=tg_id, center=center).first()
    quote = customer_queryset(Quote.objects.filter(pk=quote_id), center, bot_user).first()
    if not quote or quote.status not in {Quote.STATUS_SUBMITTED, Quote.STATUS_APPROVED}:
        return _err("Quote cannot be rejected", 409)
    quote.status = Quote.STATUS_REJECTED
    quote.save(update_fields=["status", "updated_at"])
    return _ok({"quote_id": quote.pk, "status": quote.status})


@csrf_exempt
def api_add_order_comment(request, order_id):
    """Add a customer-visible comment to the immutable order timeline."""
    if request.method != "POST":
        return _err("Method not allowed", 405)
    data = _json_body(request)
    tg_id, _, center = _auth(data)
    if tg_id is None:
        return _err("Invalid or expired initData", 401)
    from accounts.models import BotUser
    from orders.models import Order, OrderEvent
    bot_user = BotUser.objects.filter(user_id=tg_id, center=center, is_active=True).first()
    order = customer_queryset(Order.objects.filter(pk=order_id), center, bot_user).first()
    if not order:
        return _err("Order not found", 404)
    body = (data.get("comment") or "").strip()
    if not body or len(body) > 2000:
        return _err("Comment must contain 1–2000 characters")
    event = OrderEvent.objects.create(
        order=order,
        event_type=OrderEvent.TYPE_COMMENT,
        bot_user=bot_user,
        data={"body": body, "visibility": "customer"},
    )
    return _ok({"event_id": event.pk, "created_at": event.created_at.isoformat()})


@csrf_exempt
def api_notification_preferences(request):
    """Read or update customer notification preferences."""
    if request.method not in {"GET", "POST"}:
        return _err("Method not allowed", 405)
    data = request.GET.dict() if request.method == "GET" else _json_body(request)
    tg_id, _, center = _auth(data)
    if tg_id is None:
        return _err("Invalid or expired initData", 401)
    from accounts.models import BotUser
    from marketing.models import UserBroadcastPreference
    bot_user = BotUser.objects.filter(user_id=tg_id, center=center, is_active=True).first()
    if not bot_user:
        return _err("User not registered", 403)
    preference, _ = UserBroadcastPreference.objects.get_or_create(bot_user=bot_user)
    fields = ("receive_marketing", "receive_promotions", "receive_updates")
    if request.method == "POST":
        update_fields = []
        for field in fields:
            if field in data and isinstance(data[field], bool):
                setattr(preference, field, data[field])
                update_fields.append(field)
        if update_fields:
            preference.save(update_fields=[*update_fields, "updated_at"])
    return _ok({"preferences": {field: getattr(preference, field) for field in fields}})


@csrf_exempt
def api_secure_media(request, media_id):
    """Authorize a customer before delegating local file transfer to Nginx."""
    if request.method != "POST":
        return _err("Method not allowed", 405)
    data = _json_body(request)
    tg_id, _, center = _auth(data)
    if tg_id is None:
        return _err("Invalid or expired initData", 401)

    from django.conf import settings
    from django.db.models import Q
    from django.core.files.storage import default_storage
    from accounts.models import BotUser
    from orders.models import OrderMedia

    bot_user = BotUser.objects.filter(user_id=tg_id, center=center, is_active=True).first()
    if not bot_user:
        return _err("User not registered", 403)
    media = OrderMedia.objects.filter(pk=media_id).filter(
        Q(order__bot_user=bot_user, order__branch__center=center)
        | Q(additional_for_orders__bot_user=bot_user, additional_for_orders__branch__center=center)
        | Q(quotes__bot_user=bot_user, quotes__branch__center=center)
    ).distinct().first()
    if not media or not media.file or not default_storage.exists(media.file.name):
        return _err("File is archived or unavailable", 410)

    if settings.DEBUG:
        return FileResponse(
            default_storage.open(media.file.name, "rb"),
            as_attachment=True,
            filename=media.file_name,
        )

    response = HttpResponse(content_type="application/octet-stream")
    response["Content-Disposition"] = f'attachment; filename="{media.file_name}"'
    response["X-Accel-Redirect"] = f"/protected-media/{urlquote(media.file.name)}"
    return response

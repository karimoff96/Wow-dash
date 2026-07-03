import time
from typing import Optional

from django.core.cache import cache
from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin

from bot.admin_bot_service import send_security_alert


class RateLimitMiddleware(MiddlewareMixin):
    """Rate limit public contact form by IP with escalating cooldowns."""

    CONTACT_PATHS = {"/contact/"}
    WINDOW_SECONDS = 30          # Sliding-ish window for small bursts
    BURST_LIMIT = 3              # Allow this many requests per window
    BASE_COOLDOWN = 60           # Start with 1 minute cooldown when limit exceeded
    MAX_COOLDOWN = 3600          # Cap cooldown at 1 hour after repeated abuse
    PENALTY_TTL = 24 * 3600      # Track penalty counts for a day

    def process_request(self, request):
        if request.method != "POST" or request.path not in self.CONTACT_PATHS:
            return None

        ip = self._get_client_ip(request)
        if not ip:
            return None

        block_key = f"rl:contact:block:{ip}"
        block_until = cache.get(block_key)
        if block_until:
            retry_after = max(1, int(block_until - time.time()))
            self._notify(ip, request.path, retry_after, from_block=True)
            return self._too_many_requests(retry_after)

        count_key = f"rl:contact:count:{ip}"
        count = self._increment_counter(count_key, self.WINDOW_SECONDS)

        if count > self.BURST_LIMIT:
            penalty_key = f"rl:contact:penalty:{ip}"
            penalty = self._increment_counter(penalty_key, self.PENALTY_TTL)
            cooldown = min(self.BASE_COOLDOWN * penalty, self.MAX_COOLDOWN)
            block_until = time.time() + cooldown
            cache.set(block_key, block_until, cooldown)
            self._notify(ip, request.path, int(cooldown), penalty=penalty)
            return self._too_many_requests(int(cooldown))

        return None

    def _increment_counter(self, key: str, ttl: int) -> int:
        """Increment a cache counter with TTL; initialize if missing."""
        added = cache.add(key, 1, ttl)
        if added:
            return 1
        try:
            return cache.incr(key)
        except Exception:
            cache.set(key, 1, ttl)
            return 1

    def _get_client_ip(self, request) -> Optional[str]:
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            # Take the left-most IP (original client) and strip spaces
            return xff.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")

    def _too_many_requests(self, retry_after: int) -> HttpResponse:
        resp = HttpResponse(
            "Too many contact requests. Please try again later.",
            status=429,
            content_type="text/plain",
        )
        resp["Retry-After"] = str(retry_after)
        return resp

    def _notify(self, ip: str, path: str, retry_after: int, penalty: int = 0, from_block: bool = False):
        """Send admin alert for suspicious rate limit hits."""
        reason = "blocked cooldown" if from_block else "limit exceeded"
        message = (
            "🚨 <b>Rate Limit Triggered</b>\n"
            f"📍 <b>Path:</b> {path}\n"
            f"🌐 <b>IP:</b> {ip}\n"
            f"⏱️ <b>Retry-After:</b> {retry_after}s\n"
            f"⚖️ <b>Penalty level:</b> {penalty}\n"
            f"ℹ️ <b>Reason:</b> {reason}"
        )
        try:
            send_security_alert(message)
        except Exception:
            # Avoid breaking the request on alert failures
            pass

"""Test runner that replaces external Telegram transport with deterministic fakes."""

import ipaddress
import socket
from types import SimpleNamespace
from unittest.mock import patch

from django.test.runner import DiscoverRunner


def _telegram_message(*args, **kwargs):
    return SimpleNamespace(
        message_id=1,
        document=SimpleNamespace(file_id="test-file-id", file_size=0),
    )


_socket_connect = socket.socket.connect
_getaddrinfo = socket.getaddrinfo


def _is_local_host(host):
    if host in {None, "", "localhost"}:
        return True
    try:
        return ipaddress.ip_address(str(host)).is_loopback
    except ValueError:
        return False


def _local_only_connect(sock, address):
    # Unix sockets are local. TCP services used by CI (PostgreSQL/Redis) must
    # resolve to loopback; everything else is rejected before transport.
    if isinstance(address, str) or _is_local_host(address[0]):
        return _socket_connect(sock, address)
    raise RuntimeError(f"Outbound network is disabled during tests: {address[0]}")


def _local_only_getaddrinfo(host, *args, **kwargs):
    if not _is_local_host(host):
        raise RuntimeError(f"Outbound DNS is disabled during tests: {host}")
    return _getaddrinfo(host, *args, **kwargs)


class HermeticDiscoverRunner(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._transport_patches = [
            patch("socket.socket.connect", new=_local_only_connect),
            patch("socket.getaddrinfo", new=_local_only_getaddrinfo),
            # Test fixtures deliberately use obvious non-secret tokens. Bypass
            # PyTelegramBotAPI's shape validation while keeping all transport
            # methods replaced below.
            patch("telebot.util.validate_token", return_value=None),
            patch("telebot.util.extract_bot_id", return_value=123456),
            patch("telebot.TeleBot.send_message", autospec=True, side_effect=_telegram_message),
            patch("telebot.TeleBot.send_document", autospec=True, side_effect=_telegram_message),
            patch("telebot.TeleBot.send_photo", autospec=True, side_effect=_telegram_message),
            patch("telebot.TeleBot.remove_webhook", autospec=True, return_value=True),
            patch("telebot.TeleBot.set_webhook", autospec=True, return_value=True),
            patch(
                "telebot.TeleBot.get_me",
                autospec=True,
                return_value=SimpleNamespace(username="test_bot", first_name="Test"),
            ),
        ]
        for transport_patch in self._transport_patches:
            transport_patch.start()

    def teardown_test_environment(self, **kwargs):
        for transport_patch in reversed(getattr(self, "_transport_patches", [])):
            transport_patch.stop()
        super().teardown_test_environment(**kwargs)

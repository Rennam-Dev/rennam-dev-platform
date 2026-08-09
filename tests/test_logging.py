import logging
from io import StringIO

import pytest

from app.core.logging import (
    AUTH_HANDLER_NAME,
    AUTH_LOGGER_NAME,
    configure_auth_logging,
)

pytestmark = pytest.mark.no_database


def test_default_auth_logger_emits_info_to_stdout_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = configure_auth_logging()
    configure_auth_logging()
    configured_handlers = [
        handler
        for handler in logger.handlers
        if handler.get_name() == AUTH_HANDLER_NAME
    ]

    output_stream = StringIO()
    monkeypatch.setattr(configured_handlers[0], "stream", output_stream)
    logger.info(
        "admin_login_failure",
        extra={
            "event": "admin_login_failure",
            "client_ip": "192.0.2.1",
            "path": "/admin/login",
            "result": "failure",
        },
    )
    lines = [
        line
        for line in output_stream.getvalue().splitlines()
        if f"logger={AUTH_LOGGER_NAME}" in line
    ]

    assert logger.level == logging.INFO
    assert logger.getEffectiveLevel() == logging.INFO
    assert logger.isEnabledFor(logging.INFO) is True
    assert logger.propagate is False
    assert len(configured_handlers) == 1
    assert configured_handlers[0].level == logging.INFO
    assert len(lines) == 1
    assert "level=INFO" in lines[0]
    assert "event=admin_login_failure" in lines[0]

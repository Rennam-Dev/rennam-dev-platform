import logging
import sys

AUTH_LOGGER_NAME = "rennam.admin_auth"
AUTH_HANDLER_NAME = "rennam.admin_auth.stdout"
AUTH_LOG_FORMAT = (
    "timestamp=%(asctime)s level=%(levelname)s logger=%(name)s "
    "event=%(event)s client_ip=%(client_ip)s path=%(path)s result=%(result)s"
)
AUTH_LOG_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


def configure_auth_logging() -> logging.Logger:
    logger = logging.getLogger(AUTH_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    handler = next(
        (
            configured_handler
            for configured_handler in logger.handlers
            if configured_handler.get_name() == AUTH_HANDLER_NAME
        ),
        None,
    )
    if handler is None:
        handler = logging.StreamHandler(sys.stdout)
        handler.set_name(AUTH_HANDLER_NAME)
        logger.addHandler(handler)

    handler.setLevel(logging.INFO)
    handler.setFormatter(
        logging.Formatter(
            AUTH_LOG_FORMAT,
            datefmt=AUTH_LOG_DATE_FORMAT,
        )
    )
    return logger

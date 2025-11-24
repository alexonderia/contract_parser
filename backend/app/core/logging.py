from __future__ import annotations

import logging

_LOG_FORMAT = "%(levelname)s %(name)s %(message)s"


def configure_logging(level: int | str = logging.INFO) -> logging.Logger:
    logging.basicConfig(level=level, format=_LOG_FORMAT)
    return logging.getLogger("contract_parser.backend")
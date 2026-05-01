"""Structured logging helpers with print-compatible formatting."""

from __future__ import annotations

import logging
import sys
from contextlib import contextmanager
from typing import Iterator


TRACE_LEVEL = 15
logging.addLevelName(TRACE_LEVEL, "PIPELINE")


class SceneForgeLogger(logging.Logger):
    """Logger with a small pipeline-trace helper."""

    def pipeline(self, message: str, *args, **kwargs) -> None:
        if self.isEnabledFor(TRACE_LEVEL):
            self._log(TRACE_LEVEL, message, args, **kwargs)


logging.setLoggerClass(SceneForgeLogger)


def configure_logging(level: int = logging.INFO) -> None:
    """Configure root logging once, preserving legacy `[LEVEL] msg` output."""

    root = logging.getLogger()
    if root.handlers:
        root.setLevel(level)
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> SceneForgeLogger:
    """Return a configured logger."""

    configure_logging()
    return logging.getLogger(name)  # type: ignore[return-value]


@contextmanager
def pipeline_span(logger: SceneForgeLogger, label: str) -> Iterator[None]:
    """Emit span-style trace logs around a pipeline step."""

    logger.pipeline("%s start", label)
    try:
        yield
    except Exception:
        logger.error("%s failed", label, exc_info=True)
        raise
    logger.pipeline("%s done", label)


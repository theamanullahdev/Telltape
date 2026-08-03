"""One place that decides what shows up in the terminal.

Default (VERBOSE unset): quiet. No per-request "200 OK" spam from uvicorn, no
reload-watcher chatter. Just our own pipeline milestones ("part 1/3: voice
done") and anything that actually went wrong.

Set VERBOSE=1 to get everything back (uvicorn access log, debug-level detail)
for troubleshooting.
"""
import logging
import os

_CONFIGURED = False


def verbose_enabled() -> bool:
    return os.environ.get("VERBOSE", "").strip().lower() in ("1", "true", "yes")


def configure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    verbose = verbose_enabled()
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    if not verbose:
        for name in (
            "uvicorn", "uvicorn.error", "uvicorn.access", "watchfiles.main",
            "httpx", "httpcore", "huggingface_hub", "filelock", "urllib3",
        ):
            logging.getLogger(name).setLevel(logging.WARNING)

        import warnings
        warnings.filterwarnings("ignore", category=UserWarning, module="torch")
        warnings.filterwarnings("ignore", category=FutureWarning, module="torch")


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)

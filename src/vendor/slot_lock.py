"""Serialise GPU access so a concurrent caller cannot swap the resident model
out from under a running trial.

Why this exists at all: Ollama holds one model resident and evicts it when a
different one is requested. If anything else on the machine asks for another
model mid-experiment — a second run, a chat client, a background daemon — the
in-flight request either degrades or hangs until it times out. Trials scored
under those conditions are noise, and the failure is silent.

The original implementation used byte-range locks on a shared file so that
several unrelated OS processes could coordinate. This vendored version keeps
that cross-process property with a lock directory, which is atomic on every
platform and needs no dependencies.

Holding the lock for a whole model BATCH rather than per request is the point:
a multi-turn trial must not be interruptible between the tool call and the
follow-up turn.
"""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path

_LOCK_DIR = Path(os.environ.get("INJECTION_LOCK_DIR", Path.home() / ".injection-study"))
_LOCK = _LOCK_DIR / "gpu.lock"
_POLL_S = 0.5
_STALE_S = float(os.environ.get("INJECTION_LOCK_STALE_S", "7200"))


@contextmanager
def hold_model(model: str, note: str = "", timeout_s: float = 3600.0):
    """Hold exclusive GPU access for `model` until the block exits.

    Set INJECTION_LOCK_DISABLE=1 to make this a no-op — correct when nothing
    else on the machine touches the GPU, and it removes the only piece of
    machinery here that can deadlock.
    """
    if os.environ.get("INJECTION_LOCK_DISABLE"):
        yield
        return

    _LOCK_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    acquired = False
    while not acquired:
        try:
            os.mkdir(_LOCK)
            (_LOCK / "owner").write_text(f"{os.getpid()}\n{model}\n{note}\n", encoding="utf-8")
            acquired = True
        except FileExistsError:
            # A crashed run would otherwise block every later run forever.
            try:
                age = time.time() - _LOCK.stat().st_mtime
                if age > _STALE_S:
                    _release()
                    continue
            except FileNotFoundError:
                continue
            if time.monotonic() - t0 > timeout_s:
                raise TimeoutError(
                    f"GPU lock held by another process for {timeout_s:.0f}s "
                    f"(waiting to run {model!r}). Stale lock: {_LOCK}")
            time.sleep(_POLL_S)
    try:
        yield
    finally:
        _release()


def _release() -> None:
    try:
        (_LOCK / "owner").unlink(missing_ok=True)
        _LOCK.rmdir()
    except OSError:
        pass

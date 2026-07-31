"""Desktop launcher: runs the existing FastAPI app inside a native window (pywebview)
instead of a browser tab.

Why this exists: a browser-hosted page can never tell Windows to launch Excel/Word
directly with a specific local file — that's a hard browser security boundary, not a
limitation of this app's code. Running the same app inside pywebview keeps every
existing route/template/service untouched, but adds one thing a browser tab can't
have: a JS-to-Python bridge running in the same trusted local process, where
``os.startfile()`` actually works.

Run this instead of ``uvicorn main:app`` for the desktop experience:

    python desktop.py

The web routes (including the browser-tab "View" links) keep working exactly as
before — this is a second way to run the same app, not a replacement.
"""
import logging
import os
import socket
import threading
import time

import uvicorn
import webview

import main as main_module
from app.database import SessionLocal
from app.services import contract_service, document_service

HOST = "127.0.0.1"
PORT = 8000

# Configured here (not just relied on from main.py) so Api's logging works even if
# a bridge call somehow lands before main's own basicConfig has run; harmless no-op
# if it already has, since logging.basicConfig only takes effect on its first call.
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("desktop")


class Api:
    """Bridge exposed to page JavaScript as ``window.pywebview.api``."""

    def open_document(self, contract_id: int, doc_type: str) -> dict:
        """Open a contract's permanent Excel/Word document with the OS default app.

        Resolves/creates the file via the exact same ``ensure_canonical_document``
        used by the browser-facing View route, then hands the path to Windows via
        ``os.startfile`` — no download, no temp file, no new copy, no regeneration
        of a file that already exists.

        Logs each step: if this doesn't open Excel/Word, the terminal running
        ``python desktop.py`` will show exactly which step failed (bad contract_id
        type from JS, contract not found, file resolution error, or os.startfile
        itself rejecting the file/association).
        """
        logger.info("open_document called: contract_id=%r doc_type=%r", contract_id, doc_type)

        if doc_type not in ("excel", "word"):
            logger.warning("Rejected: unsupported doc_type %r", doc_type)
            return {"ok": False, "error": "Unsupported document type"}

        db = SessionLocal()
        try:
            contract = contract_service.get_active_contract(db, contract_id)
            if contract is None:
                logger.warning("Rejected: contract_id %r not found or inactive", contract_id)
                return {"ok": False, "error": "Contract not found"}
            file_path = document_service.ensure_canonical_document(db, contract, doc_type)
            db.commit()
        finally:
            db.close()

        logger.info("Resolved document path: %s (exists=%s)", file_path, file_path.exists())

        try:
            os.startfile(str(file_path))  # launches this app's own permanent document with its default app
        except OSError as exc:
            logger.error("os.startfile failed for %s: %s", file_path, exc)
            return {"ok": False, "error": str(exc)}

        logger.info("os.startfile succeeded for %s", file_path)
        return {"ok": True}


def _run_server() -> None:
    # Passing the app object directly (rather than the "main:app" import-string form)
    # is behaviorally identical for uvicorn, but lets PyInstaller's static import
    # analysis actually see and bundle main.py and everything it imports — a string
    # reference is invisible to it and would silently produce a broken exe.
    uvicorn.run(main_module.app, host=HOST, port=PORT, log_level="warning")


def _wait_until_listening(host: str, port: int, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError(f"Server did not start listening on {host}:{port} within {timeout}s")


def main() -> None:
    # pywebview blocks ALL browser-style downloads by default (ALLOW_DOWNLOADS=False
    # out of the box, across every one of its backends) -- it treats itself as an app
    # shell, not a browser. Every Export button (CSV/PDF/Excel/Word, every module) is a
    # plain link relying on normal Content-Disposition: attachment download behavior,
    # so without this, WebView2 silently cancels each one before it reaches disk. This
    # is unrelated to View -> Excel/Word, which never goes through the browser download
    # path at all -- it's intercepted client-side and opened via os.startfile() instead.
    webview.settings["ALLOW_DOWNLOADS"] = True

    server_thread = threading.Thread(target=_run_server, daemon=True)
    server_thread.start()
    _wait_until_listening(HOST, PORT)

    webview.create_window("Offline ERP HAL", f"http://{HOST}:{PORT}", js_api=Api(), width=1280, height=800)
    # debug=True enables right-click > Inspect in the window, so the [HAL] console
    # logs from app.js's desktop-bridge handler are visible for troubleshooting.
    webview.start(debug=True)


if __name__ == "__main__":
    main()

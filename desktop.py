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
import base64
import binascii
import logging
import os
import socket
import tempfile
import threading
import time
import uuid
from pathlib import Path

import uvicorn
import webview

import main as main_module
from app.config import settings
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

    def save_and_open_document(self, doc_type: str, base64_data: str) -> dict:
        """Open a document fetched by JS from a remote backend, via a local temp copy.

        Only used when settings.desktop_backend_url is set (see main() below): in that
        mode this window shows pages served by a hosted backend, so the canonical
        file lives on that server's disk, not this machine's -- open_document() above
        (which calls ensure_canonical_document() directly against local disk) cannot
        resolve it. app.js instead fetches the exact same /contracts/{id}/view/{fmt}
        route a plain browser tab already uses (unchanged, same auth/business logic),
        and hands the bytes here purely so this trusted local process can save a temp
        copy for os.startfile() -- no backend/database/storage code is touched.
        """
        logger.info("save_and_open_document called: doc_type=%r", doc_type)

        if doc_type not in ("excel", "word"):
            logger.warning("Rejected: unsupported doc_type %r", doc_type)
            return {"ok": False, "error": "Unsupported document type"}

        try:
            raw_bytes = base64.b64decode(base64_data)
        except (ValueError, binascii.Error) as exc:
            logger.error("Failed to decode fetched document bytes: %s", exc)
            return {"ok": False, "error": "Could not decode document data"}

        extension = "xlsx" if doc_type == "excel" else "docx"
        temp_dir = Path(tempfile.gettempdir()) / "hal_erp_desktop_view"
        temp_dir.mkdir(exist_ok=True)
        temp_path = temp_dir / f"{uuid.uuid4().hex}.{extension}"
        temp_path.write_bytes(raw_bytes)

        try:
            os.startfile(str(temp_path))  # local temp copy of the remote backend's canonical document
        except OSError as exc:
            logger.error("os.startfile failed for %s: %s", temp_path, exc)
            return {"ok": False, "error": str(exc)}

        logger.info("os.startfile succeeded for %s (fetched from remote backend)", temp_path)
        return {"ok": True}


def _run_server() -> None:
    # Passing the app object directly (rather than the "main:app" import-string form)
    # is behaviorally identical for uvicorn, but lets PyInstaller's static import
    # analysis actually see and bundle main.py and everything it imports — a string
    # reference is invisible to it and would silently produce a broken exe.
    uvicorn.run(main_module.app, host=HOST, port=PORT, log_level="warning")


def _wait_until_listening(host: str, port: int, timeout: float = 15.0) -> None:
    # Poll interval is short (not e.g. 0.2s) purely to reduce detection lag: the
    # window should open within milliseconds of uvicorn actually being ready, not
    # up to an extra poll-interval's worth of time after it already is. Same
    # overall timeout, same retry-on-OSError behavior -- only checks more often.
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.05)
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

    # pywebview's default (OPEN_EXTERNAL_LINKS_IN_BROWSER=True) hands any
    # target="_blank" link to the OS's default external browser via
    # webbrowser.open() instead of keeping it inside this window -- see
    # on_new_window_request() in pywebview's edgechromium.py backend. That
    # external browser has no session cookie for 127.0.0.1:8000 (cookies are
    # scoped to this WebView2 instance, not shared with the system browser),
    # so any such link hits a protected route unauthenticated and bounces to
    # /login. The contract detail page's "Saved Documents" View link (a plain
    # target="_blank" <a>, distinct from the JS-bridge-driven View -> Excel/
    # Word tiles mentioned above) hit exactly this. Disabling it makes
    # target="_blank" navigate in-place in this same authenticated window
    # instead (pywebview's own fallback for this setting), with no effect on
    # a plain browser tab running the same app, where this setting doesn't
    # exist at all.
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = False

    # settings.desktop_backend_url (DESKTOP_BACKEND_URL env var) unset -- the original,
    # fully offline behavior: spawn our own local FastAPI/uvicorn server and point the
    # window at it. Set it (e.g. to a Render URL) to instead point this window directly
    # at a hosted backend sharing one Postgres database with the website -- no local
    # server needed, since the real one is already running there.
    if settings.desktop_backend_url:
        window_url = settings.desktop_backend_url
        logger.info("Using hosted backend: %s", window_url)
    else:
        server_thread = threading.Thread(target=_run_server, daemon=True)
        server_thread.start()
        _wait_until_listening(HOST, PORT)
        window_url = f"http://{HOST}:{PORT}"

    webview.create_window("Offline ERP HAL", window_url, js_api=Api(), width=1280, height=800)
    # debug=True enables right-click > Inspect in the window, so the [HAL] console
    # logs from app.js's desktop-bridge handler are visible for troubleshooting.
    webview.start(debug=True)


if __name__ == "__main__":
    main()

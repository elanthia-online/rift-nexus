"""Entry point for the rift-login console script."""

from __future__ import annotations

import argparse
import logging
import os
import sys

from PySide6.QtWidgets import QApplication

from rift.login.eas_client import EASClient
from rift.login.tls_transport import TLSTransport
from rift.login.ui import LoginWindow
from rift.login.worker import LoginWorker


def main() -> None:
    parser = argparse.ArgumentParser(description="rift-nexus EAS login launcher")
    parser.add_argument(
        "--debug", action="store_true", help="Enable verbose protocol-level debug logging"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug or os.environ.get("RIFT_DEBUG") else logging.INFO,
        format="%(message)s",
    )

    eas_client = EASClient(TLSTransport())
    worker = LoginWorker(eas_client)

    app = QApplication(sys.argv)
    window = LoginWindow(worker)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

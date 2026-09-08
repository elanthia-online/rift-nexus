"""Entry point for the rift-client console script.

client is a standalone, independently launchable front-end - one of
several possible launch targets for the launcher in login, not tied to
it. It only needs a SAL file with the connection handoff data.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from rift.client.game_socket import GameSocket
from rift.client.sal_reader import read_sal_file
from rift.client.stream_worker import StreamWorker
from rift.client.window import ClientWindow


def main() -> None:
    parser = argparse.ArgumentParser(description="rift-nexus raw-stream game client")
    parser.add_argument("--sal", required=True, type=Path, help="Path to the SAL handoff file")
    parser.add_argument(
        "--debug", action="store_true", help="Enable verbose protocol-level debug logging"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug or os.environ.get("RIFT_DEBUG") else logging.INFO,
        format="%(message)s",
    )

    handoff = read_sal_file(args.sal)
    game_socket = GameSocket(handoff["gamehost"], int(handoff["gameport"]))
    worker = StreamWorker(game_socket, handoff["key"])

    app = QApplication(sys.argv)
    window = ClientWindow(worker)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

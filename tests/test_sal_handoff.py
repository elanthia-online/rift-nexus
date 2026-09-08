"""Cross-package integration check: login writes SAL files, client reads them.

login/sal.py and client/sal_reader.py are deliberately independent
implementations (client must work as a front-end launched from any
SAL-writing source, not just this project's login package - see
sal_reader.py's own docstring), so neither package's own test suite
verifies that the two actually agree on the wire format. This is the one
place that checks it.
"""

from pathlib import Path

from rift.client.sal_reader import read_sal_file
from rift.login.models import HandoffInfo
from rift.login.sal import write_sal_file


def test_sal_file_written_by_login_is_readable_by_client(tmp_path: Path):
    handoff = HandoffInfo(
        gamehost="storm.gs4.game.play.net",
        gameport="10024",
        key="abc123",
        game="STORM",
        gamefile="WRAYTH.EXE",
        fullgamename="Wrayth",
        extra={"upport": "5535", "gamecode": "GS"},
    )
    path = write_sal_file(handoff, directory=tmp_path)

    fields = read_sal_file(path, delete_after=False)

    assert fields == {
        "gamehost": "storm.gs4.game.play.net",
        "gameport": "10024",
        "key": "abc123",
        "game": "STORM",
        "gamefile": "WRAYTH.EXE",
        "fullgamename": "Wrayth",
        "upport": "5535",
        "gamecode": "GS",
    }


def test_sal_file_written_by_login_supplies_everything_client_app_needs(tmp_path: Path):
    # client/app.py only ever reads these three fields directly
    # (handoff["gamehost"], handoff["gameport"], handoff["key"]) - the
    # minimal real-world case, with none of the optional fields set.
    handoff = HandoffInfo(gamehost="game.example.com", gameport="1234", key="sessionkey", game="STORM")
    path = write_sal_file(handoff, directory=tmp_path)

    fields = read_sal_file(path, delete_after=False)

    assert fields["gamehost"] == "game.example.com"
    assert int(fields["gameport"]) == 1234
    assert fields["key"] == "sessionkey"

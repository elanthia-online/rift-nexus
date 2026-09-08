import stat
import tempfile
from pathlib import Path

from rift.login import sal
from rift.login.models import HandoffInfo


def test_sal_dir_uses_xdg_runtime_dir_when_set(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    assert sal.sal_dir() == tmp_path


def test_sal_dir_falls_back_to_tempdir_when_unset(monkeypatch):
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    assert sal.sal_dir() == Path(tempfile.gettempdir())


def test_write_sal_file_uppercases_known_fields(tmp_path):
    handoff = HandoffInfo(
        gamehost="game.example.com",
        gameport="1234",
        key="sessionkey",
        game="STORM",
        gamefile="WIZARD.EXE",
        fullgamename="GemStone IV",
    )
    path = sal.write_sal_file(handoff, directory=tmp_path)

    lines = path.read_text().splitlines()
    assert "GAMEHOST=game.example.com" in lines
    assert "GAMEPORT=1234" in lines
    assert "KEY=sessionkey" in lines
    assert "GAME=STORM" in lines
    assert "GAMEFILE=WIZARD.EXE" in lines
    assert "FULLGAMENAME=GemStone IV" in lines


def test_write_sal_file_includes_extra_fields_uppercased(tmp_path):
    handoff = HandoffInfo(
        gamehost="h", gameport="1", key="k", game="STORM", extra={"somenewfield": "value"}
    )
    path = sal.write_sal_file(handoff, directory=tmp_path)
    assert "SOMENEWFIELD=value" in path.read_text().splitlines()


def test_write_sal_file_omits_empty_optional_fields(tmp_path):
    handoff = HandoffInfo(gamehost="h", gameport="1", key="k", game="STORM")
    path = sal.write_sal_file(handoff, directory=tmp_path)
    text = path.read_text()
    assert "GAMEFILE=" not in text
    assert "FULLGAMENAME=" not in text


def test_write_sal_file_hardens_permissions(tmp_path):
    handoff = HandoffInfo(gamehost="h", gameport="1", key="k", game="STORM")
    path = sal.write_sal_file(handoff, directory=tmp_path)
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600


def test_write_sal_file_lands_in_requested_directory(tmp_path):
    handoff = HandoffInfo(gamehost="h", gameport="1", key="k", game="STORM")
    path = sal.write_sal_file(handoff, directory=tmp_path)
    assert path.parent == tmp_path
    assert path.suffix == ".sal"

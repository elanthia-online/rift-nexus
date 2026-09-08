import stat
from pathlib import Path

from rift.login import config


def test_config_dir_respects_xdg_config_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert config.config_dir() == tmp_path / "rift-nexus"


def test_config_dir_falls_back_to_home_config(monkeypatch):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    assert config.config_dir() == Path.home() / ".config" / "rift-nexus"


def test_load_returns_defaults_when_missing(tmp_path):
    path = tmp_path / "config.json"
    assert config.load(path) == config.LoginConfig()


def test_save_then_load_round_trips(tmp_path):
    path = tmp_path / "nested" / "config.json"
    original = config.LoginConfig(
        account_name="acct",
        last_game_code="GS3",
        last_char_code="ABC",
        launch_command_template="wrayth --sal %sal%",
    )
    config.save(original, path)
    assert config.load(path) == original


def test_save_hardens_permissions(tmp_path):
    path = tmp_path / "nested" / "config.json"
    config.save(config.LoginConfig(), path)

    file_mode = stat.S_IMODE(path.stat().st_mode)
    assert file_mode == 0o600

    dir_mode = stat.S_IMODE(path.parent.stat().st_mode)
    assert dir_mode == 0o700

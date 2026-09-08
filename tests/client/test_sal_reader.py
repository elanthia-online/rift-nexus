from rift.client import sal_reader


def _write(tmp_path, text):
    path = tmp_path / "session.sal"
    path.write_text(text)
    return path


def test_read_sal_file_lowercases_keys(tmp_path):
    path = _write(tmp_path, "GAMEHOST=game.example.com\nGAMEPORT=1234\nKEY=sessionkey\n")
    fields = sal_reader.read_sal_file(path)
    assert fields == {"gamehost": "game.example.com", "gameport": "1234", "key": "sessionkey"}


def test_read_sal_file_skips_blank_and_malformed_lines(tmp_path):
    path = _write(tmp_path, "GAMEHOST=h\n\n   \nNOEQUALSIGN\nKEY=k\n")
    fields = sal_reader.read_sal_file(path)
    assert fields == {"gamehost": "h", "key": "k"}


def test_read_sal_file_deletes_by_default(tmp_path):
    path = _write(tmp_path, "KEY=k\n")
    sal_reader.read_sal_file(path)
    assert not path.exists()


def test_read_sal_file_can_keep_file(tmp_path):
    path = _write(tmp_path, "KEY=k\n")
    sal_reader.read_sal_file(path, delete_after=False)
    assert path.exists()

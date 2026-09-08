from rift.login.models import CharacterListing, GameListing, HandoffInfo


def test_game_listing():
    listing = GameListing(code="GS3", name="GS Prime")
    assert listing.code == "GS3"
    assert listing.name == "GS Prime"


def test_character_listing():
    listing = CharacterListing(
        game_code="GS3", game_name="GS Prime", char_code="ABC", char_name="Warrior"
    )
    assert listing.char_name == "Warrior"


def test_handoff_info_from_kv_splits_known_and_extra_fields():
    kv = {
        "gamehost": "game.example.com",
        "gameport": "1234",
        "key": "sessionkey",
        "game": "STORM",
        "gamefile": "WIZARD.EXE",
        "fullgamename": "GemStone IV",
        "somethingnew": "future-field",
    }
    info = HandoffInfo.from_kv(kv)
    assert info.gamehost == "game.example.com"
    assert info.gameport == "1234"
    assert info.key == "sessionkey"
    assert info.game == "STORM"
    assert info.gamefile == "WIZARD.EXE"
    assert info.fullgamename == "GemStone IV"
    assert info.extra == {"somethingnew": "future-field"}


def test_handoff_info_from_kv_defaults_missing_optional_fields():
    kv = {"gamehost": "game.example.com", "gameport": "1234", "key": "sessionkey", "game": "STORM"}
    info = HandoffInfo.from_kv(kv)
    assert info.gamefile == ""
    assert info.fullgamename == ""
    assert info.extra == {}

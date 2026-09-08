import pytest

from rift.login import eas_wire


def test_obscure_password_matches_hand_computed_vector():
    # "a" = 97; shifted = 97-32 = 65; key byte "A" = 65; xor = 0;
    # result = (0 + 32) & 0xFF = 32 = " "
    assert eas_wire.obscure_password("a", "A") == " "


def test_obscure_password_cycles_short_hash_key():
    once = eas_wire.obscure_password("a", "AB")
    twice = eas_wire.obscure_password("aa", "A")
    assert once[0] == twice[0] == twice[1]


def test_obscure_password_rejects_empty_hash_key():
    with pytest.raises(ValueError):
        eas_wire.obscure_password("secret", "")


def test_build_lines_carry_no_trailing_newline():
    # Messages are TLS-record-framed, not newline-delimited - see
    # docs/eas-protocol.md.
    assert eas_wire.build_k_line() == "K"
    assert eas_wire.build_a_line("acct", "pw") == "A\tacct\tpw"
    assert eas_wire.build_m_line() == "M"
    assert eas_wire.build_f_line("GS3") == "F\tGS3"
    assert eas_wire.build_g_line("GS3") == "G\tGS3"
    assert eas_wire.build_p_line("GS3") == "P\tGS3"
    assert eas_wire.build_c_line() == "C"
    assert eas_wire.build_n_line("GS3") == "N\tGS3"
    assert eas_wire.build_l_line("ABC123") == "L\tABC123\tSTORM"
    assert eas_wire.build_l_line("ABC123", "WIZARD") == "L\tABC123\tWIZARD"


def test_parse_hash_key():
    assert eas_wire.parse_hash_key("K\tSOMEHASHKEY") == "SOMEHASHKEY"


def test_parse_functions_tolerate_a_stray_trailing_newline():
    # Defensive: parse_* still works if a trailing newline ever shows up.
    assert eas_wire.parse_hash_key("K\tSOMEHASHKEY\n") == "SOMEHASHKEY"


def test_parse_key_response_success():
    assert eas_wire.parse_key_response("A\tKEY\tabc123\tOTHER\tstuff") == "abc123"


def test_parse_key_response_failure_raises_authentication_error_with_code():
    with pytest.raises(eas_wire.EASAuthenticationError) as excinfo:
        eas_wire.parse_key_response("A\tERROR\tBADPASSWORD")
    assert excinfo.value.error_code == "BADPASSWORD"


def test_parse_key_response_failure_uses_known_friendly_message():
    with pytest.raises(eas_wire.EASAuthenticationError, match="Incorrect account password"):
        eas_wire.parse_key_response("A\tERROR\tPASSWORD")


def test_describe_error_code_falls_back_for_unknown_codes():
    assert eas_wire.describe_error_code("SOMETHINGNEW") == "EAS returned error code: SOMETHINGNEW"


def test_parse_game_list():
    response = "M\tGS3\tGS Prime\tGSF\tGS Shattered"
    assert eas_wire.parse_game_list(response) == [
        ("GS3", "GS Prime"),
        ("GSF", "GS Shattered"),
    ]


def test_parse_game_list_rejects_wrong_prefix():
    with pytest.raises(eas_wire.EASProtocolError):
        eas_wire.parse_game_list("X\tGS3\tGS Prime")


@pytest.mark.parametrize(
    "tier",
    # PREMIUM/TRIAL/FREE plus EXPIRED/NEW_TO_GAME/UNKNOWN, all observed on
    # a live account 2026-09-07 - open-ended, not an exhaustive enum.
    ["PREMIUM", "TRIAL", "FREE", "EXPIRED", "NEW_TO_GAME", "UNKNOWN", "SOME_FUTURE_VALUE"],
)
def test_parse_subscription_passes_through_any_value(tier):
    assert eas_wire.parse_subscription(f"F\t{tier}") == tier


def test_parse_char_list_skips_leading_numeric_fields():
    response = "C\t1\t2\t3\t4\tABC\tWarrior\tDEF\tRogue"
    assert eas_wire.parse_char_list(response) == [
        ("ABC", "Warrior"),
        ("DEF", "Rogue"),
    ]


def test_parse_char_list_rejects_wrong_prefix():
    with pytest.raises(eas_wire.EASProtocolError):
        eas_wire.parse_char_list("X\t1\t2\t3\t4\tABC\tWarrior")


def test_parse_n_response():
    # Real server responses are pipe-delimited flags in one tab field,
    # e.g. "N\tPRODUCTION|STORM|TRIAL" - confirmed via live smoke test.
    assert eas_wire.parse_n_response("N\tPRODUCTION|STORM|TRIAL") is True
    assert eas_wire.parse_n_response("N\tDEVELOPMENT|STORM") is True
    assert eas_wire.parse_n_response("N\tPRODUCTION|WIZARD") is False


def test_parse_handoff_kv_lowercases_keys_and_builds_open_dict():
    response = "L\tOK\tGAMEHOST=game.example.com\tGAMEPORT=1234\tKEY=sessionkey"
    assert eas_wire.parse_handoff_kv(response) == {
        "gamehost": "game.example.com",
        "gameport": "1234",
        "key": "sessionkey",
    }


def test_parse_handoff_kv_failure_raises_character_selection_error_with_code():
    with pytest.raises(eas_wire.EASCharacterSelectionError) as excinfo:
        eas_wire.parse_handoff_kv("L\tERROR\tNOSUCHCHARACTER")
    assert excinfo.value.error_code == "NOSUCHCHARACTER"

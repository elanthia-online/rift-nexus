from rift.login.eas_client import EASClient
from rift.login.models import CharacterListing, GameListing, HandoffInfo


class FakeTransport:
    """Scripted transport double: each entry maps an expected outgoing line
    to the canned response returned for the recv_packet() that follows it."""

    def __init__(self, script: list[tuple[str, str]]):
        self._script = list(script)
        self.sent_lines: list[str] = []
        self.connected = False
        self.closed = False

    def connect(self) -> None:
        self.connected = True

    def send_line(self, line: str) -> None:
        self.sent_lines.append(line)

    def recv_packet(self) -> str:
        expected_line, response = self._script.pop(0)
        assert self.sent_lines[-1] == expected_line, (
            f"expected transport to have just sent {expected_line!r}, "
            f"but last sent line was {self.sent_lines[-1]!r}"
        )
        return response

    def close(self) -> None:
        self.closed = True


def test_connect_delegates_to_transport():
    transport = FakeTransport([])
    client = EASClient(transport)
    client.connect()
    assert transport.connected is True


def test_authenticate_success():
    transport = FakeTransport(
        [
            ("K", "K\tHASHKEY"),
            ("A\tacct\t" + _expected_scrambled_password(), "A\tKEY\teassessionkey"),
        ]
    )
    client = EASClient(transport)
    client.authenticate("acct", "a")


def _expected_scrambled_password() -> str:
    from rift.login.eas_wire import obscure_password

    return obscure_password("a", "HASHKEY")


def test_list_games():
    transport = FakeTransport([("M", "M\tGS3\tGS Prime\tGST\tGS Test")])
    client = EASClient(transport)
    assert client.list_games() == [
        GameListing("GS3", "GS Prime"),
        GameListing("GST", "GS Test"),
    ]


def test_enumerate_all_walks_every_game_and_character():
    transport = FakeTransport(
        [
            ("M", "M\tGS3\tGS Prime\tGSF\tGS Shattered"),
            ("N\tGS3", "N\tPRODUCTION|STORM|TRIAL"),
            ("F\tGS3", "F\tNORMAL"),
            ("G\tGS3", "G\tOK"),
            ("P\tGS3", "P\tOK"),
            ("C", "C\t1\t2\t3\t4\tABC\tWarrior"),
            ("N\tGSF", "N\tDEVELOPMENT"),  # not STORM - skipped entirely
        ]
    )
    client = EASClient(transport)
    assert client.enumerate_all() == [
        CharacterListing(game_code="GS3", game_name="GS Prime", char_code="ABC", char_name="Warrior"),
    ]


def test_select_character_reruns_f_g_p_c_for_the_game_code_before_l():
    # Regression test: select_character() must re-establish the
    # server-side "current game" context of the EAS session for the
    # requested game_code immediately before L, matching the targeted
    # (non-legacy) path of eaccess.rb. Confirmed live 2026-09-07 that
    # skipping this silently returns the connection info of the
    # *previously enumerated* game instead of the requested one, with no
    # error at the EAS layer - the game server rejects the resulting KEY
    # afterward instead.
    transport = FakeTransport(
        [
            ("F\tGS3", "F\tNORMAL"),
            ("G\tGS3", "G\tOK"),
            ("P\tGS3", "P\tOK"),
            ("C", "C\t1\t2\t3\t4\tABC\tWarrior"),
            (
                "L\tABC\tSTORM",
                "L\tOK\tGAMEHOST=game.example.com\tGAMEPORT=1234\tKEY=sessionkey\tGAME=STORM",
            ),
        ]
    )
    client = EASClient(transport)
    handoff = client.select_character("GS3", "ABC")
    assert handoff == HandoffInfo(
        gamehost="game.example.com", gameport="1234", key="sessionkey", game="STORM"
    )


def test_select_character_accepts_alternate_game_type():
    transport = FakeTransport(
        [
            ("F\tGS3", "F\tNORMAL"),
            ("G\tGS3", "G\tOK"),
            ("P\tGS3", "P\tOK"),
            ("C", "C\t1\t2\t3\t4\tABC\tWarrior"),
            (
                "L\tABC\tWIZARD",
                "L\tOK\tGAMEHOST=game.example.com\tGAMEPORT=1234\tKEY=sessionkey\tGAME=WIZARD",
            ),
        ]
    )
    client = EASClient(transport)
    handoff = client.select_character("GS3", "ABC", game_type="WIZARD")
    assert handoff.game == "WIZARD"


def test_close_delegates_to_transport():
    transport = FakeTransport([])
    client = EASClient(transport)
    client.close()
    assert transport.closed is True

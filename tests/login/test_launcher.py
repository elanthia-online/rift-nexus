from pathlib import Path

from rift.login import launcher


def test_build_command_uses_default_template_when_none_given():
    command = launcher.build_command("", Path("/run/user/1000/rift-nexus-abc123.sal"))
    assert command == ["rift-client", "--sal", "/run/user/1000/rift-nexus-abc123.sal"]


def test_build_command_substitutes_sal_path_into_custom_template():
    command = launcher.build_command(
        "/opt/Wrayth/wrayth.exe --login {sal_path} --other-flag",
        Path("/tmp/session.sal"),
    )
    assert command == ["/opt/Wrayth/wrayth.exe", "--login", "/tmp/session.sal", "--other-flag"]


def test_build_command_quotes_a_sal_path_containing_spaces():
    command = launcher.build_command(
        launcher.DEFAULT_LAUNCH_COMMAND_TEMPLATE, Path("/tmp/has space/session.sal")
    )
    assert command == ["rift-client", "--sal", "/tmp/has space/session.sal"]


def test_launch_spawns_the_built_command(monkeypatch):
    captured_commands = []

    class FakePopen:
        def __init__(self, command):
            captured_commands.append(command)

    monkeypatch.setattr(launcher.subprocess, "Popen", FakePopen)

    result = launcher.launch(Path("/tmp/session.sal"))

    assert captured_commands == [["rift-client", "--sal", "/tmp/session.sal"]]
    assert isinstance(result, FakePopen)


def test_launch_uses_the_configured_template(monkeypatch):
    captured_commands = []
    monkeypatch.setattr(
        launcher.subprocess, "Popen", lambda command: captured_commands.append(command)
    )

    launcher.launch(Path("/tmp/session.sal"), launch_command_template="/opt/Wizard/wizard {sal_path}")

    assert captured_commands == [["/opt/Wizard/wizard", "/tmp/session.sal"]]

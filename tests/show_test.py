import pytest
import show.main as show
from click.testing import CliRunner
from unittest.mock import MagicMock, patch

EXPECTED_BASE_COMMAND = 'sudo '

@patch('show.main.run_command')
@pytest.mark.parametrize(
        "cli_arguments,expected",
        [
            ([], 'cat /var/log/syslog'),
            (['xcvrd'], "cat /var/log/syslog | grep 'xcvrd'"),
            (['-l', '10'], 'cat /var/log/syslog | tail -10'),
            (['-f'], 'tail -F /var/log/syslog'),
        ]
)
def test_show_logging_default(run_command, cli_arguments, expected):
    runner = CliRunner()
    result = runner.invoke(show.cli.commands["logging"], cli_arguments)
    run_command.assert_called_with(EXPECTED_BASE_COMMAND + expected, display_cmd=False)

@patch('show.main.run_command')
@patch('os.path.isfile', MagicMock(return_value=True))
@pytest.mark.parametrize(
        "cli_arguments,expected",
        [
            ([], 'cat /var/log/syslog.1 /var/log/syslog'),
            (['xcvrd'], "cat /var/log/syslog.1 /var/log/syslog | grep 'xcvrd'"),
            (['-l', '10'], 'cat /var/log/syslog.1 /var/log/syslog | tail -10'),
            (['-f'], 'tail -F /var/log/syslog'),
        ]
)
def test_show_logging_syslog_1(run_command, cli_arguments, expected):
    runner = CliRunner()
    result = runner.invoke(show.cli.commands["logging"], cli_arguments)
    run_command.assert_called_with(EXPECTED_BASE_COMMAND + expected, display_cmd=False)

@patch('show.main.run_command')
@patch('os.path.exists', MagicMock(return_value=True))
@pytest.mark.parametrize(
        "cli_arguments,expected",
        [
            ([], 'cat /var/log.tmpfs/syslog'),
            (['xcvrd'], "cat /var/log.tmpfs/syslog | grep 'xcvrd'"),
            (['-l', '10'], 'cat /var/log.tmpfs/syslog | tail -10'),
            (['-f'], 'tail -F /var/log.tmpfs/syslog'),
        ]
)
def test_show_logging_tmpfs(run_command, cli_arguments, expected):
    runner = CliRunner()
    result = runner.invoke(show.cli.commands["logging"], cli_arguments)
    run_command.assert_called_with(EXPECTED_BASE_COMMAND + expected, display_cmd=False)

@patch('show.main.run_command')
@patch('os.path.isfile', MagicMock(return_value=True))
@patch('os.path.exists', MagicMock(return_value=True))
@pytest.mark.parametrize(
        "cli_arguments,expected",
        [
            ([], 'cat /var/log.tmpfs/syslog.1 /var/log.tmpfs/syslog'),
            (['xcvrd'], "cat /var/log.tmpfs/syslog.1 /var/log.tmpfs/syslog | grep 'xcvrd'"),
            (['-l', '10'], 'cat /var/log.tmpfs/syslog.1 /var/log.tmpfs/syslog | tail -10'),
            (['-f'], 'tail -F /var/log.tmpfs/syslog'),
        ]
)
def test_show_logging_tmpfs_syslog_1(run_command, cli_arguments, expected):
    runner = CliRunner()
    result = runner.invoke(show.cli.commands["logging"], cli_arguments)
    run_command.assert_called_with(EXPECTED_BASE_COMMAND + expected, display_cmd=False)

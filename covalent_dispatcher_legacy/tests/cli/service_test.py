# Copyright 2021 Agnostiq Inc.
#
# This file is part of Covalent.
#
# Licensed under the GNU Affero General Public License 3.0 (the "License").
# A copy of the License may be obtained with this software package or at
#
#      https://www.gnu.org/licenses/agpl-3.0.en.html
#
# Use of this file is prohibited except in compliance with the License. Any
# modifications or derivative works of this file must retain this copyright
# notice, and modified files must contain a notice indicating that they have
# been altered from the originals.
#
# Covalent is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the License for more details.
#
# Relief from the License may be granted by purchasing a commercial license.

"""Tests for Covalent command line interface (CLI) Tool."""

import tempfile

import mock
import pytest
from click.exceptions import ClickException
from click.testing import CliRunner
from psutil import pid_exists

from covalent_dispatcher_legacy._cli.service import (
    _ensure_supervisord_running,
    _graceful_shutdown,
    _graceful_start,
    _is_server_running,
    _next_available_port,
    _port_from_pid,
    _read_pid,
    _rm_pid_file,
    config,
    logs,
    purge,
    restart,
    start,
    status,
    stop,
)

STOPPED_SERVER_STATUS_ECHO = "Covalent server is stopped.\n"
RUNNING_SERVER_STATUS_ECHO = "Covalent server is running at http://0.0.0.0:42.\n"

STARTED_SUPERVISORD_ECHO = "Started Supervisord process {}."
NO_SERVICE_PROVIDED_TO_LOGS_ECHO = (
    "No service name provided, please use '-s <service_name>' or '--service <service_name>"
)
RUNNING_SUPERVISORD_ECHO = "Supervisord already running in process {}."
SUPEVISORD_PROGRAM_GROUP_NAME = "covalent"


def test_read_pid_nonexistent_file():
    """Test the process id read function when the pid file does not exist."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        assert _read_pid(f"{tmp_dir}/nonexistent.pid") == -1


def test_read_valid_pid_file():
    """Test the process id read function when the pid file exists."""

    with mock.patch(
        "covalent_dispatcher_legacy._cli.service.open", mock.mock_open(read_data="1984")
    ):
        res = _read_pid(filename="mock.pid")
    assert res == 1984


@pytest.mark.parametrize("file_exists,remove_call_status", [(False, False), (True, True)])
def test_rm_pid_file(mocker, file_exists, remove_call_status):
    """Test the process id file removal function."""

    mocker.patch("os.path.isfile", return_value=file_exists)
    os_remove_mock = mocker.patch("os.remove")
    _rm_pid_file("nonexistent.pid")

    assert os_remove_mock.called is remove_call_status


def test_port_from_invalid_pid(mocker):
    """Test port retrieval method from invalid pid."""

    mocker.patch("psutil.pid_exists", return_value=False)
    res = _port_from_pid(-1)
    assert res is None


def test_port_from_valid_pid(mocker):
    """Test port retrieval method from invalid pid."""

    process_mock = mocker.patch("psutil.Process")
    mocker.patch("psutil.pid_exists", return_value=True)
    _port_from_pid(12)
    process_mock.assert_called_once()


def test_next_available_port(mocker):
    """Test function to generate the next available port that is not in use."""

    # Case 1 - Port is available.
    mocker.patch("socket.socket.bind")
    res = _next_available_port(requested_port=12)
    assert res == 12

    # Case 2 - Next two ports are not available.
    click_echo_mock = mocker.patch("click.echo")
    mocker.patch(
        "socket.socket.bind", side_effect=[Exception("OSERROR"), Exception("OSERROR"), None]
    )

    res = _next_available_port(requested_port=12)
    assert res == 14
    click_echo_mock.assert_called_once()


def test_graceful_start_when_pid_exists(mocker):
    """Test the graceful server start function."""

    read_pid_mock = mocker.patch("covalent_dispatcher_legacy._cli.service._read_pid")
    pid_exists_mock = mocker.patch("psutil.pid_exists", return_value=True)
    port_from_pid_mock = mocker.patch(
        "covalent_dispatcher_legacy._cli.service.get_config", return_value=1984
    )
    click_echo_mock = mocker.patch("click.echo")
    res = _graceful_start("", "", "", 15, False)
    assert res == 1984

    click_echo_mock.assert_called_once()
    read_pid_mock.assert_called_once()
    pid_exists_mock.assert_called_once()
    port_from_pid_mock.assert_called_once()


def test_graceful_start_when_pid_absent(mocker):
    """Test the graceful server start function."""

    read_pid_mock = mocker.patch("covalent_dispatcher_legacy._cli.service._read_pid")
    pid_exists_mock = mocker.patch("psutil.pid_exists", return_value=False)
    rm_pid_file_mock = mocker.patch("covalent_dispatcher_legacy._cli.service._rm_pid_file")
    next_available_port_mock = mocker.patch(
        "covalent_dispatcher_legacy._cli.service._next_available_port", return_value=1984
    )
    popen_mock = mocker.patch("covalent_dispatcher_legacy._cli.service.Popen")
    click_echo_mock = mocker.patch("click.echo")

    with mock.patch("covalent_dispatcher_legacy._cli.service.open", mock.mock_open()):
        res = _graceful_start("", "", "output.log", 15, False)
        assert res == 1984

    rm_pid_file_mock.assert_called_once()
    next_available_port_mock.assert_called_once()
    pid_exists_mock.assert_called_once()
    popen_mock.assert_called_once()
    click_echo_mock.assert_called_once()
    read_pid_mock.assert_called_once()


def test_graceful_shutdown_running_server(mocker):
    """Test the graceful shutdown functionality."""

    read_pid_mock = mocker.patch(
        "covalent_dispatcher_legacy._cli.service._read_pid", return_value=12
    )
    mocker.patch("psutil.pid_exists", return_value=True)
    process_mock = mocker.patch("psutil.Process")
    rm_pid_file_mock = mocker.patch("covalent_dispatcher_legacy._cli.service._rm_pid_file")
    click_echo_mock = mocker.patch("click.echo")

    _graceful_shutdown(pidfile="mock")

    click_echo_mock.assert_called_once_with("Covalent server has stopped.")
    rm_pid_file_mock.assert_called_once_with("mock")
    read_pid_mock.assert_called_once()
    assert process_mock.called


def test_graceful_shutdown_stopped_server(mocker):
    """Test the graceful shutdown functionality."""

    mocker.patch("covalent_dispatcher_legacy._cli.service._read_pid", return_value=12)
    mocker.patch("psutil.pid_exists", return_value=False)
    process_mock = mocker.patch("psutil.Process")
    rm_pid_file_mock = mocker.patch("covalent_dispatcher_legacy._cli.service._rm_pid_file")
    click_echo_mock = mocker.patch("click.echo")

    _graceful_shutdown(pidfile="mock")

    click_echo_mock.assert_called_once_with("Covalent server was not running.")
    rm_pid_file_mock.assert_called_once_with("mock")
    assert not process_mock.called


def test_start(mocker, monkeypatch):
    """Test the start CLI command."""

    runner = CliRunner()
    port_val = 42

    graceful_start_mock = mocker.patch(
        "covalent_dispatcher_legacy._cli.service._graceful_start", return_value=port_val
    )
    set_config_mock = mocker.patch("covalent_dispatcher_legacy._cli.service.set_config")
    monkeypatch.setattr("covalent_dispatcher_legacy._cli.service.UI_SRVDIR", "mock")
    monkeypatch.setattr("covalent_dispatcher_legacy._cli.service.UI_PIDFILE", "mock")
    monkeypatch.setattr("covalent_dispatcher_legacy._cli.service.UI_LOGFILE", "mock")

    runner.invoke(start, f"--port {port_val} -d")
    graceful_start_mock.assert_called_once()
    set_config_mock.assert_called_once()


def test_start_refactor(mocker, monkeypatch):
    """Test the start CLI command."""

    runner = CliRunner()

    # mock methods
    ensure_sd_running = mocker.patch(
        "covalent_dispatcher_legacy._cli.service._ensure_supervisord_running"
    )
    read_process_stdout = mocker.patch(
        "covalent_dispatcher_legacy._cli.service._read_process_stdout"
    )
    popen_mock = mocker.patch("covalent_dispatcher_legacy._cli.service.Popen")

    # invoke command
    runner.invoke(start, "--refactor")

    # assertions
    ensure_sd_running.assert_called_once()
    read_process_stdout.assert_called_once()
    # using call_args instead of 'assert_called_with' to ignore additional args supplied to Popen
    (popen_command,) = popen_mock.call_args[0]
    assert popen_command == ["supervisorctl", "start", f"{SUPEVISORD_PROGRAM_GROUP_NAME}:"]


def test_stop_refactor(mocker, monkeypatch):
    """Test the stop CLI command."""

    runner = CliRunner()

    # mock methods
    ensure_sd_running = mocker.patch(
        "covalent_dispatcher_legacy._cli.service._ensure_supervisord_running"
    )
    read_process_stdout = mocker.patch(
        "covalent_dispatcher_legacy._cli.service._read_process_stdout"
    )
    popen_mock = mocker.patch("covalent_dispatcher_legacy._cli.service.Popen")

    # invoke command
    runner.invoke(stop, "--refactor")

    # assertions
    ensure_sd_running.assert_called_once()
    read_process_stdout.assert_called_once()
    # using call_args instead of 'assert_called_with' to ignore additional args supplied to Popen
    (popen_command,) = popen_mock.call_args[0]
    assert popen_command == ["supervisorctl", "stop", f"{SUPEVISORD_PROGRAM_GROUP_NAME}:"]


def test_restart_refactor(mocker, monkeypatch):
    """Test the restart CLI command."""

    runner = CliRunner()

    # mock methods
    ensure_sd_running = mocker.patch(
        "covalent_dispatcher_legacy._cli.service._ensure_supervisord_running"
    )
    read_process_stdout = mocker.patch(
        "covalent_dispatcher_legacy._cli.service._read_process_stdout"
    )
    popen_mock = mocker.patch("covalent_dispatcher_legacy._cli.service.Popen")

    # invoke command
    runner.invoke(restart, "--refactor")

    # assertions
    ensure_sd_running.assert_called_once()
    read_process_stdout.assert_called_once()
    # using call_args instead of 'assert_called_with' to ignore additional args supplied to Popen
    (popen_command,) = popen_mock.call_args[0]
    assert popen_command == ["supervisorctl", "restart", f"{SUPEVISORD_PROGRAM_GROUP_NAME}:"]


def test_status_refactor(mocker, monkeypatch):
    """Test the status CLI command."""

    runner = CliRunner()

    # mock methods
    ensure_sd_running = mocker.patch(
        "covalent_dispatcher_legacy._cli.service._ensure_supervisord_running"
    )
    read_process_stdout = mocker.patch(
        "covalent_dispatcher_legacy._cli.service._read_process_stdout"
    )
    popen_mock = mocker.patch("covalent_dispatcher_legacy._cli.service.Popen")

    # invoke command
    runner.invoke(status, "--refactor")

    # assertions
    ensure_sd_running.assert_called_once()
    read_process_stdout.assert_called_once()
    # using call_args instead of 'assert_called_with' to ignore additional args supplied to Popen
    (popen_command,) = popen_mock.call_args[0]
    assert popen_command == ["supervisorctl", "status"]


@pytest.mark.parametrize("MOCK_SERVICE_NAME", [("queuer"), (None)])
def test_logs_refactor(mocker, MOCK_SERVICE_NAME):
    """Test the logs CLI command."""

    runner = CliRunner()

    # number of times supervisord is called to get logs (1 sterr, 2 stdout, 3 tail real-time logs)
    NUM_TAIL_COMMANDS = 3

    # mock methods
    ensure_sd_running = mocker.patch(
        "covalent_dispatcher_legacy._cli.service._ensure_supervisord_running"
    )
    read_process_stdout = mocker.patch(
        "covalent_dispatcher_legacy._cli.service._read_process_stdout"
    )
    popen_mock = mocker.patch("covalent_dispatcher_legacy._cli.service.Popen")

    if MOCK_SERVICE_NAME:
        # invoke command with service name
        runner.invoke(logs, f"--service {MOCK_SERVICE_NAME}")
        # assertions
        ensure_sd_running.assert_called_once()
        assert len(read_process_stdout.mock_calls) == NUM_TAIL_COMMANDS
        assert len(popen_mock.mock_calls) == NUM_TAIL_COMMANDS
        # using call_args instead of 'assert_called_with' to ignore additional args supplied to Popen
        # getting args of last call to popen
        (popen_command,) = popen_mock.call_args[0]
        assert popen_command == [
            "supervisorctl",
            "tail",
            "-f",
            f"{SUPEVISORD_PROGRAM_GROUP_NAME}:{MOCK_SERVICE_NAME}",
        ]
    else:
        # invoke command without service name
        res = runner.invoke(logs)
        assert res.output.strip() == NO_SERVICE_PROVIDED_TO_LOGS_ECHO.strip()


@pytest.mark.parametrize("is_supervisord_running_flag", [(True), (False)])
def test_purge_refactor(mocker, monkeypatch, is_supervisord_running_flag):
    """Test the refactor CLI command."""

    runner = CliRunner()

    SD_PIDFILE_MOCK = "some/path/pid"
    SD_CONFIG_FILE = "some/path/supervisord.conf"

    # mock methods
    sd_stop_services = mocker.patch("covalent_dispatcher_legacy._cli.service._sd_stop_services")
    graceful_shutdown = mocker.patch("covalent_dispatcher_legacy._cli.service._graceful_shutdown")
    shutil_rmtree_mock = mocker.patch("covalent_dispatcher_legacy._cli.service.shutil.rmtree")
    purge_config_mock = mocker.patch("covalent_dispatcher_legacy._cli.service.cm.purge_config")
    os_remove = mocker.patch("os.remove")
    monkeypatch.setattr("covalent_dispatcher_legacy._cli.service.SD_PIDFILE", SD_PIDFILE_MOCK)
    monkeypatch.setattr("covalent_dispatcher_legacy._cli.service.SD_CONFIG_FILE", SD_CONFIG_FILE)

    # Supervisord autocreates it's pid file hence if it is running we can assume the pid file to exist
    mocker.patch("os.path.exists", return_value=is_supervisord_running_flag)
    mocker.patch(
        "covalent_dispatcher_legacy._cli.service._is_supervisord_running",
        return_value=is_supervisord_running_flag,
    )

    # invoke command
    runner.invoke(purge, "--refactor")

    if is_supervisord_running_flag:
        sd_stop_services.assert_called_once()
        graceful_shutdown.assert_called_once_with(SD_PIDFILE_MOCK)
        os_remove.assert_called_once_with(SD_CONFIG_FILE)
    else:
        sd_stop_services.assert_not_called()
        graceful_shutdown.assert_not_called()
        os_remove.assert_not_called()


@pytest.mark.parametrize(
    "is_supervisord_running_flag, is_started_success",
    [(True, True), (False, True), (False, False)],
)
def test_is_supervisord_running(
    mocker, monkeypatch, is_supervisord_running_flag, is_started_success
):
    """Test the refactor CLI command."""

    SD_PIDFILE_MOCK = "some/path/pid"
    SD_CONFIG_FILE = "some/path/supervisord.conf"
    SUPERVISORD_PORT_MOCK = 9009
    SUPERVISORD_PID_MOCK = 18290

    # mock methods
    monkeypatch.setattr("covalent_dispatcher_legacy._cli.service.SD_PIDFILE", SD_PIDFILE_MOCK)
    monkeypatch.setattr("covalent_dispatcher_legacy._cli.service.SD_CONFIG_FILE", SD_CONFIG_FILE)
    monkeypatch.setattr(
        "covalent_dispatcher_legacy._cli.service.SUPERVISORD_PORT", SUPERVISORD_PORT_MOCK
    )
    monkeypatch.setattr("covalent_dispatcher_legacy._cli.service.SD_START_TIMEOUT_IN_SECS", 0.1)

    create_config_if_not_exists = mocker.patch(
        "covalent_dispatcher_legacy._cli.service._create_config_if_not_exists"
    )
    read_pid = mocker.patch(
        "covalent_dispatcher_legacy._cli.service._read_pid", return_value=SUPERVISORD_PID_MOCK
    )
    is_port_in_use = mocker.patch(
        "covalent_dispatcher_legacy._cli.service._is_port_in_use", return_value=is_started_success
    )
    mocker.patch(
        "covalent_dispatcher_legacy._cli.service._is_supervisord_running",
        return_value=is_supervisord_running_flag,
    )
    popen_mock = mocker.patch("covalent_dispatcher_legacy._cli.service.Popen")
    echo_mock = mocker.patch("click.echo")

    if not is_supervisord_running_flag and not is_started_success:
        # should raise exception if supervisord port is not binded to within timeout
        with pytest.raises(ClickException) as e:
            _ensure_supervisord_running()
    else:
        _ensure_supervisord_running()

    create_config_if_not_exists.assert_called_once()

    # if supervisord is already running when calling covalent start
    if is_supervisord_running_flag:
        read_pid.assert_called_once_with(SD_PIDFILE_MOCK)
        echo_mock.assert_called_once_with(RUNNING_SUPERVISORD_ECHO.format(SUPERVISORD_PID_MOCK))
    else:
        (popen_command,) = popen_mock.call_args[0]
        assert popen_command == ["supervisord"]

        if is_started_success:
            is_port_in_use.assert_called_once_with(SUPERVISORD_PORT_MOCK)
            read_pid.assert_called_once_with(SD_PIDFILE_MOCK)
            echo_mock.assert_called_once_with(
                STARTED_SUPERVISORD_ECHO.format(SUPERVISORD_PID_MOCK)
            )


def test_stop(mocker, monkeypatch):
    """Test the stop CLI command."""

    runner = CliRunner()
    graceful_shutdown_mock = mocker.patch(
        "covalent_dispatcher_legacy._cli.service._graceful_shutdown"
    )
    monkeypatch.setattr("covalent_dispatcher_legacy._cli.service.UI_PIDFILE", "mock")
    runner.invoke(stop)
    graceful_shutdown_mock.assert_called_once_with("mock")


@pytest.mark.parametrize(
    "port_tag,port,server,pid,restart_called,start_called,stop_called",
    [
        ("port", 42, "ui", -1, False, True, True),
        ("port", 42, "ui", 100, True, True, True),
    ],
)
def test_restart(mocker, port_tag, port, pid, server, restart_called, start_called, stop_called):
    """Test the restart CLI command."""

    start = mocker.patch("covalent_dispatcher_legacy._cli.service.start")
    stop = mocker.patch("covalent_dispatcher_legacy._cli.service.stop")
    mocker.patch("covalent_dispatcher_legacy._cli.service.get_config", return_value=port)

    obj = mocker.MagicMock()
    mocker.patch("covalent_dispatcher_legacy._cli.service._read_pid", return_value=pid)

    runner = CliRunner()
    runner.invoke(restart, f"--{port_tag} {port}", obj=obj)
    assert start.called is start_called
    assert stop.called is stop_called


@pytest.mark.parametrize(
    "port_val,pid,echo_output,file_removed",
    [(None, -1, STOPPED_SERVER_STATUS_ECHO, True), (42, 42, RUNNING_SERVER_STATUS_ECHO, False)],
)
def test_status(mocker, port_val, pid, echo_output, file_removed):
    """Test covalent status command."""

    mocker.patch("covalent_dispatcher_legacy._cli.service.get_config", return_value=port_val)
    mocker.patch("covalent_dispatcher_legacy._cli.service._read_pid", return_value=pid)
    mocker.patch("requests.get", return_value=True)
    rm_pid_file_mock = mocker.patch("covalent_dispatcher_legacy._cli.service._rm_pid_file")

    runner = CliRunner()
    res = runner.invoke(status, ["--port", port_val])

    assert res.output == echo_output
    assert rm_pid_file_mock.called is file_removed


def test_is_server_running(mocker):
    """Test the server status checking function."""

    mocker.patch("covalent_dispatcher_legacy._cli.service._read_pid", return_value=1)
    mocker.patch("requests.get", return_value=True)
    assert _is_server_running("8000")

    mocker.patch("covalent_dispatcher_legacy._cli.service._read_pid", return_value=1)
    mocker.patch("requests.get", side_effect=Exception("mocked error"))
    assert not _is_server_running("8000")

    mocker.patch("covalent_dispatcher_legacy._cli.service._read_pid", return_value=-1)
    mocker.patch("requests.get", return_value=True)
    assert not _is_server_running("8000")

    mocker.patch("covalent_dispatcher_legacy._cli.service._read_pid", return_value=-1)
    mocker.patch("requests.get", side_effect=Exception("mocked error"))
    assert not _is_server_running("8000")


@pytest.mark.parametrize("multiple_vars", [(False), (True)])
def test_config(mocker, multiple_vars):
    """Test the 'covalent config' CLI command."""
    runner = CliRunner()
    config_set_mock = mocker.patch("covalent_dispatcher_legacy._cli.service.cm.set")

    if multiple_vars:
        runner.invoke(config, "var1=val1 var2=val2")
        config_set_mock.assert_has_calls([mock.call("var1", "val1"), mock.call("var2", "val2")])
    else:
        runner.invoke(config, "var1=val1")
        config_set_mock.assert_called_once_with("var1", "val1")


def test_purge(mocker):
    """Test the 'covalent purge' CLI command."""

    from covalent_dispatcher_legacy._cli.service import UI_PIDFILE, get_config

    runner = CliRunner()
    graceful_shutdown_mock = mocker.patch(
        "covalent_dispatcher_legacy._cli.service._graceful_shutdown"
    )
    shutil_rmtree_mock = mocker.patch("covalent_dispatcher_legacy._cli.service.shutil.rmtree")
    purge_config_mock = mocker.patch("covalent_dispatcher_legacy._cli.service.cm.purge_config")
    result = runner.invoke(purge)
    graceful_shutdown_mock.assert_has_calls([mock.call(UI_PIDFILE)])
    shutil_rmtree_mock.assert_has_calls(
        [
            mock.call(get_config("sdk.log_dir"), ignore_errors=True),
            mock.call(get_config("dispatcher.cache_dir"), ignore_errors=True),
            mock.call(get_config("dispatcher.log_dir"), ignore_errors=True),
            mock.call(get_config("user_interface.log_dir"), ignore_errors=True),
        ]
    )
    purge_config_mock.assert_called_once()
    assert result.output == "Covalent server files have been purged.\n"
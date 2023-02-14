import os
import pytest

import config.main as config
from utilities_common.db import Db
from unittest import mock
from click.testing import CliRunner

config_dhcp_relay_add_output = """\
Added DHCP relay address [{}] to Vlan1000
Restarting DHCP relay service...
"""
config_dhcp_relay_del_output = """\
Removed DHCP relay address [{}] from Vlan1000
Restarting DHCP relay service...
"""
expected_dhcp_relay_add_config_db_output = {
    "ipv4": {
        "dhcp_servers": [
            "192.0.0.1", "192.0.0.2", "192.0.0.3", "192.0.0.4", "192.0.0.5"
        ],
        "dhcpv6_servers": [
            "fc02:2000::1", "fc02:2000::2"
        ],
        "vlanid": "1000"
    },
    "ipv6": {
        "dhcpv6_servers": [
            "fc02:2000::1", "fc02:2000::2", "fc02:2000::3"
        ]
    }
}
expected_dhcp_relay_del_config_db_output = {
    "ipv4": {
        "dhcp_servers": [
            "192.0.0.1", "192.0.0.2", "192.0.0.3", "192.0.0.4"
        ],
        "dhcpv6_servers": [
            "fc02:2000::1", "fc02:2000::2"
        ],
        "vlanid": "1000"
    },
    "ipv6": {
        "dhcpv6_servers": [
            "fc02:2000::1", "fc02:2000::2"
        ]
    }
}
expected_dhcp_relay_add_multi_config_db_output = {
    "ipv4": {
        "dhcp_servers": [
            "192.0.0.1", "192.0.0.2", "192.0.0.3", "192.0.0.4", "192.0.0.5", "192.0.0.6", "192.0.0.7"
        ],
        "dhcpv6_servers": [
            "fc02:2000::1", "fc02:2000::2"
        ],
        "vlanid": "1000"
    },
    "ipv6": {
        "dhcpv6_servers": [
            "fc02:2000::1", "fc02:2000::2", "fc02:2000::3", "fc02:2000::4", "fc02:2000::5"
        ]
    }
}

IP_VER_TEST_PARAM_MAP = {
    "ipv4": {
        "command": "helper",
        "ips": [
            "192.0.0.5",
            "192.0.0.6",
            "192.0.0.7"
        ],
        "exist_ip": "192.0.0.1",
        "nonexist_ip": "192.0.0.8",
        "invalid_ip": "192.0.0",
        "table": "VLAN"
    },
    "ipv6": {
        "command": "destination",
        "ips": [
            "fc02:2000::3",
            "fc02:2000::4",
            "fc02:2000::5"
        ],
        "exist_ip": "fc02:2000::1",
        "nonexist_ip": "fc02:2000::6",
        "invalid_ip": "fc02:2000:",
        "table": "DHCP_RELAY"
    }
}


@pytest.fixture(scope="module", params=["ipv4", "ipv6"])
def ip_version(request):
    """
    Parametrize Ip version
    Args:
        request: pytest request object
    Returns:
        Ip version needed for test case
    """
    return request.param


@pytest.fixture(scope="module", params=["add", "del"])
def op(request):
    """
    Parametrize operate tpye
    Args:
        request: pytest request object
    Returns:
        Operate tpye
    """
    return request.param


class TestConfigDhcpRelay(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")

    def test_config_dhcp_relay_add_del_with_nonexist_vlanid(self, ip_version, op):
        runner = CliRunner()

        with mock.patch("utilities_common.cli.run_command") as mock_run_command:
            result = runner.invoke(config.config.commands["dhcp_relay"].commands[ip_version]
                                   .commands[IP_VER_TEST_PARAM_MAP[ip_version]["command"]]
                                   .commands[op], ["1001", IP_VER_TEST_PARAM_MAP[ip_version]["ips"][0]])
            print(result.exit_code)
            print(result.stdout)
            assert result.exit_code != 0
            assert "Error: Vlan1001 doesn't exist" in result.output
            assert mock_run_command.call_count == 0

    def test_config_add_del_dhcp_relay_with_invalid_ip(self, ip_version, op):
        runner = CliRunner()
        invalid_ip = IP_VER_TEST_PARAM_MAP[ip_version]["invalid_ip"]

        with mock.patch("utilities_common.cli.run_command") as mock_run_command:
            result = runner.invoke(config.config.commands["dhcp_relay"].commands[ip_version]
                                   .commands[IP_VER_TEST_PARAM_MAP[ip_version]["command"]]
                                   .commands[op], ["1000", invalid_ip])
            print(result.exit_code)
            print(result.output)
            assert result.exit_code != 0
            assert "Error: {} is invalid IP address".format(invalid_ip) in result.output
            assert mock_run_command.call_count == 0

    def test_config_add_dhcp_with_exist_ip(self, ip_version):
        runner = CliRunner()
        db = Db()
        exist_ip = IP_VER_TEST_PARAM_MAP[ip_version]["exist_ip"]

        with mock.patch("utilities_common.cli.run_command") as mock_run_command:
            result = runner.invoke(config.config.commands["dhcp_relay"].commands[ip_version]
                                   .commands[IP_VER_TEST_PARAM_MAP[ip_version]["command"]]
                                   .commands["add"], ["1000", exist_ip], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0
            assert "{} is already a DHCP relay for Vlan1000".format(exist_ip) in result.output
            assert mock_run_command.call_count == 0

    def test_config_del_nonexist_dhcp_relay(self, ip_version):
        runner = CliRunner()
        db = Db()
        nonexist_ip = IP_VER_TEST_PARAM_MAP[ip_version]["nonexist_ip"]

        with mock.patch("utilities_common.cli.run_command") as mock_run_command:
            result = runner.invoke(config.config.commands["dhcp_relay"].commands[ip_version]
                                   .commands[IP_VER_TEST_PARAM_MAP[ip_version]["command"]]
                                   .commands["del"], ["1000", nonexist_ip], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code != 0
            assert "Error: {} is not a DHCP relay for Vlan1000".format(nonexist_ip) in result.output
            assert mock_run_command.call_count == 0

    def test_config_add_del_dhcp_relay(self, ip_version):
        runner = CliRunner()
        db = Db()
        test_ip = IP_VER_TEST_PARAM_MAP[ip_version]["ips"][0]
        config_db_table = IP_VER_TEST_PARAM_MAP[ip_version]["table"]

        with mock.patch("utilities_common.cli.run_command") as mock_run_command:
            # add new dhcp relay
            result = runner.invoke(config.config.commands["dhcp_relay"].commands[ip_version]
                                   .commands[IP_VER_TEST_PARAM_MAP[ip_version]["command"]]
                                   .commands["add"], ["1000", test_ip], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0
            assert result.output == config_dhcp_relay_add_output.format(test_ip)
            assert db.cfgdb.get_entry(config_db_table, "Vlan1000") \
                == expected_dhcp_relay_add_config_db_output[ip_version]
            assert mock_run_command.call_count == 3

        # del dhcp relay
        with mock.patch("utilities_common.cli.run_command") as mock_run_command:
            result = runner.invoke(config.config.commands["dhcp_relay"].commands[ip_version]
                                   .commands[IP_VER_TEST_PARAM_MAP[ip_version]["command"]]
                                   .commands["del"], ["1000", test_ip], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0
            assert result.output == config_dhcp_relay_del_output.format(test_ip)
            assert mock_run_command.call_count == 3
            assert db.cfgdb.get_entry(config_db_table, "Vlan1000") \
                == expected_dhcp_relay_del_config_db_output[ip_version]

    def test_config_add_del_multiple_dhcp_relay(self, ip_version):
        runner = CliRunner()
        db = Db()
        test_ips = IP_VER_TEST_PARAM_MAP[ip_version]["ips"]
        config_db_table = IP_VER_TEST_PARAM_MAP[ip_version]["table"]

        with mock.patch("utilities_common.cli.run_command") as mock_run_command:
            # add new dhcp relay
            result = runner.invoke(config.config.commands["dhcp_relay"].commands[ip_version]
                                   .commands[IP_VER_TEST_PARAM_MAP[ip_version]["command"]]
                                   .commands["add"], ["1000"] + test_ips, obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0
            assert result.output == config_dhcp_relay_add_output.format(",".join(test_ips))
            assert db.cfgdb.get_entry(config_db_table, "Vlan1000") \
                == expected_dhcp_relay_add_multi_config_db_output[ip_version]
            assert mock_run_command.call_count == 3

        # del dhcp relay
        with mock.patch("utilities_common.cli.run_command") as mock_run_command:
            result = runner.invoke(config.config.commands["dhcp_relay"].commands[ip_version]
                                   .commands[IP_VER_TEST_PARAM_MAP[ip_version]["command"]]
                                   .commands["del"], ["1000"] + test_ips, obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0
            assert result.output == config_dhcp_relay_del_output.format(",".join(test_ips))
            assert mock_run_command.call_count == 3
            assert db.cfgdb.get_entry(config_db_table, "Vlan1000") \
                == expected_dhcp_relay_del_config_db_output[ip_version]

    def test_config_add_del_duplicate_dhcp_relay(self, ip_version, op):
        runner = CliRunner()
        db = Db()
        test_ip = IP_VER_TEST_PARAM_MAP[ip_version]["ips"][0] if op == "add" \
            else IP_VER_TEST_PARAM_MAP[ip_version]["exist_ip"]

        with mock.patch("utilities_common.cli.run_command") as mock_run_command:
            result = runner.invoke(config.config.commands["dhcp_relay"].commands[ip_version]
                                   .commands[IP_VER_TEST_PARAM_MAP[ip_version]["command"]]
                                   .commands[op], ["1000", test_ip, test_ip], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code != 0
            assert "Error: Find duplicate DHCP relay ip {} in {} list".format(test_ip, op) in result.output
            assert mock_run_command.call_count == 0

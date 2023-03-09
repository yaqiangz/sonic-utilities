import pytest
import show.main as show
from click.testing import CliRunner

expected_show_dhcpv6_table = """\
--------  ------------
Vlan1000  fc02:2000::1
          fc02:2000::2
--------  ------------

--------  ------------
Vlan2000  fc02:2000::3
          fc02:2000::4
--------  ------------

"""
expected_show_dhcpv6_counter = """\
  Message Type    Vlan1000
--------------  ----------
       Unknown           0
       Solicit           0
     Advertise           0
       Request           0
       Confirm           0
         Renew           0
        Rebind           0
         Reply           0
       Release           0
       Decline           0
 Relay-Forward           0
   Relay-Reply           0

"""

expected_show_dhcp_relay_ipv4_helper = """\
+-------------+----------------------+
|   Interface |   DHCP Relay Address |
+=============+======================+
|    Vlan1000 |            192.0.0.1 |
|             |            192.0.0.2 |
|             |            192.0.0.3 |
|             |            192.0.0.4 |
+-------------+----------------------+
|    Vlan2000 |            192.0.0.1 |
|             |            192.0.0.2 |
|             |            192.0.0.3 |
|             |            192.0.0.4 |
+-------------+----------------------+

"""

expected_show_dhcp_relay_ipv6_destination = """\
+-------------+----------------------+
|   Interface |   DHCP Relay Address |
+=============+======================+
|    Vlan1000 |         fc02:2000::1 |
|             |         fc02:2000::2 |
+-------------+----------------------+
|    Vlan2000 |         fc02:2000::3 |
|             |         fc02:2000::4 |
+-------------+----------------------+

"""

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


def test_show_dhcprelay_helper():
    runner = CliRunner()
    result = runner.invoke(show.cli.commands["dhcprelay_helper"].commands["ipv6"])
    print(result.output)
    assert result.output == expected_show_dhcpv6_table


def test_show_dhcp6relay_counters():
    runner = CliRunner()
    result = runner.invoke(show.cli.commands["dhcp6relay_counters"].commands["counts"], ["-i", "Vlan1000"])
    print(result.output)
    assert result.output == expected_show_dhcpv6_counter


def test_show_dhcp_relay_ipv6_counter():
    runner = CliRunner()
    result = runner.invoke(show.cli.commands["dhcp_relay"].commands["ipv6"].commands["counters"], ["-i", "Vlan1000"])
    print(result.output)
    assert result.output == expected_show_dhcpv6_counter


def test_show_dhcp_relay(ip_version):
    runner = CliRunner()
    result = runner.invoke(show.cli.commands["dhcp_relay"].commands[ip_version]
                           .commands[IP_VER_TEST_PARAM_MAP[ip_version]["command"]])
    print(result.output)
    expected_output = expected_show_dhcp_relay_ipv4_helper \
        if ip_version == "ipv4" else expected_show_dhcp_relay_ipv6_destination
    assert result.output == expected_output

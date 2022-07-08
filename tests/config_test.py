import filecmp
import imp
import os
import traceback
import json
import ipaddress
from unittest import mock

import click
from click.testing import CliRunner

from sonic_py_common import device_info
from utilities_common.db import Db

load_minigraph_command_output="""\
Stopping SONiC target ...
Running command: /usr/local/bin/sonic-cfggen -H -m --write-to-db
Running command: config qos reload --no-dynamic-buffer
Running command: pfcwd start_default
Restarting SONiC target ...
Reloading Monit configuration ...
Please note setting loaded from minigraph will be lost after system reboot. To preserve setting, run `config save`.
"""

load_mgmt_config_command_ipv4_only_output="""\
Running command: /usr/local/bin/sonic-cfggen -M device_desc.xml --write-to-db
parse dummy device_desc.xml
change hostname to dummy
Running command: ifconfig eth0 10.0.0.100 netmask 255.255.255.0
Running command: ip route add default via 10.0.0.1 dev eth0 table default
Running command: ip rule add from 10.0.0.100 table default
Running command: [ -f /var/run/dhclient.eth0.pid ] && kill `cat /var/run/dhclient.eth0.pid` && rm -f /var/run/dhclient.eth0.pid
Please note loaded setting will be lost after system reboot. To preserve setting, run `config save`.
"""

load_mgmt_config_command_ipv6_only_output="""\
Running command: /usr/local/bin/sonic-cfggen -M device_desc.xml --write-to-db
parse dummy device_desc.xml
change hostname to dummy
Running command: ifconfig eth0 add fc00:1::32/64
Running command: ip -6 route add default via fc00:1::1 dev eth0 table default
Running command: ip -6 rule add from fc00:1::32 table default
Running command: [ -f /var/run/dhclient.eth0.pid ] && kill `cat /var/run/dhclient.eth0.pid` && rm -f /var/run/dhclient.eth0.pid
Please note loaded setting will be lost after system reboot. To preserve setting, run `config save`.
"""

load_mgmt_config_command_ipv4_ipv6_output="""\
Running command: /usr/local/bin/sonic-cfggen -M device_desc.xml --write-to-db
parse dummy device_desc.xml
change hostname to dummy
Running command: ifconfig eth0 10.0.0.100 netmask 255.255.255.0
Running command: ip route add default via 10.0.0.1 dev eth0 table default
Running command: ip rule add from 10.0.0.100 table default
Running command: ifconfig eth0 add fc00:1::32/64
Running command: ip -6 route add default via fc00:1::1 dev eth0 table default
Running command: ip -6 rule add from fc00:1::32 table default
Running command: [ -f /var/run/dhclient.eth0.pid ] && kill `cat /var/run/dhclient.eth0.pid` && rm -f /var/run/dhclient.eth0.pid
Please note loaded setting will be lost after system reboot. To preserve setting, run `config save`.
"""

def mock_run_command_side_effect(*args, **kwargs):
    command = args[0]

    if kwargs.get('display_cmd'):
        click.echo(click.style("Running command: ", fg='cyan') + click.style(command, fg='green'))

    if kwargs.get('return_cmd'):
        if command == "systemctl list-dependencies --plain sonic-delayed.target | sed '1d'":
            return 'snmp.timer'
        elif command == "systemctl list-dependencies --plain sonic.target | sed '1d'":
            return 'swss'
        elif command == "systemctl is-enabled snmp.timer":
            return 'enabled'
        else:
            return ''


class TestLoadMinigraph(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")
        import config.main
        imp.reload(config.main)

    def test_load_minigraph(self, get_cmd_module, setup_single_broadcom_asic):
        with mock.patch("utilities_common.cli.run_command", mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            (config, show) = get_cmd_module
            runner = CliRunner()
            result = runner.invoke(config.config.commands["load_minigraph"], ["-y"])
            print(result.exit_code)
            print(result.output)
            traceback.print_tb(result.exc_info[2])
            assert result.exit_code == 0
            assert "\n".join([l.rstrip() for l in result.output.split('\n')]) == load_minigraph_command_output
            # Verify "systemctl reset-failed" is called for services under sonic.target 
            mock_run_command.assert_any_call('systemctl reset-failed swss')
            # Verify "systemctl reset-failed" is called for services under sonic-delayed.target 
            mock_run_command.assert_any_call('systemctl reset-failed snmp')
            assert mock_run_command.call_count == 11

    def test_load_minigraph_with_port_config_bad_format(self, get_cmd_module, setup_single_broadcom_asic):
        with mock.patch(
            "utilities_common.cli.run_command",
            mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            (config, show) = get_cmd_module

            # Not in an array
            port_config = {"PORT": {"Ethernet0": {"admin_status": "up"}}}
            self.check_port_config(None, config, port_config, "Failed to load port_config.json, Error: Bad format: port_config is not an array")

            # No PORT table
            port_config = [{}]
            self.check_port_config(None, config, port_config, "Failed to load port_config.json, Error: Bad format: PORT table not exists")

    def test_load_minigraph_with_port_config_inconsistent_port(self, get_cmd_module, setup_single_broadcom_asic):
        with mock.patch(
            "utilities_common.cli.run_command",
            mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            (config, show) = get_cmd_module

            db = Db()
            db.cfgdb.set_entry("PORT", "Ethernet1", {"admin_status": "up"})
            port_config = [{"PORT": {"Eth1": {"admin_status": "up"}}}]
            self.check_port_config(db, config, port_config, "Failed to load port_config.json, Error: Port Eth1 is not defined in current device")

    def test_load_minigraph_with_port_config(self, get_cmd_module, setup_single_broadcom_asic):
        with mock.patch(
            "utilities_common.cli.run_command",
            mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            (config, show) = get_cmd_module
            db = Db()

            # From up to down
            db.cfgdb.set_entry("PORT", "Ethernet0", {"admin_status": "up"})
            port_config = [{"PORT": {"Ethernet0": {"admin_status": "down"}}}]
            self.check_port_config(db, config, port_config, "config interface shutdown Ethernet0")

            # From down to up
            db.cfgdb.set_entry("PORT", "Ethernet0", {"admin_status": "down"})
            port_config = [{"PORT": {"Ethernet0": {"admin_status": "up"}}}]
            self.check_port_config(db, config, port_config, "config interface startup Ethernet0")

    def test_load_backend_acl(self, get_cmd_module, setup_single_broadcom_asic):
        db = Db()
        db.cfgdb.set_entry("DEVICE_METADATA", "localhost", {"storage_device": "true"})
        self.check_backend_acl(get_cmd_module, db, device_type='BackEndToRRouter', condition=True)

    def test_load_backend_acl_not_storage(self, get_cmd_module, setup_single_broadcom_asic):
        db = Db()
        self.check_backend_acl(get_cmd_module, db, device_type='BackEndToRRouter', condition=False)

    def test_load_backend_acl_storage_leaf(self, get_cmd_module, setup_single_broadcom_asic):
        db = Db()
        db.cfgdb.set_entry("DEVICE_METADATA", "localhost", {"storage_device": "true"})
        self.check_backend_acl(get_cmd_module, db, device_type='BackEndLeafRouter', condition=False)

    def test_load_backend_acl_storage_no_dataacl(self, get_cmd_module, setup_single_broadcom_asic):
        db = Db()
        db.cfgdb.set_entry("DEVICE_METADATA", "localhost", {"storage_device": "true"})
        db.cfgdb.set_entry("ACL_TABLE", "DATAACL", None)
        self.check_backend_acl(get_cmd_module, db, device_type='BackEndToRRouter', condition=False)

    def check_backend_acl(self, get_cmd_module, db, device_type='BackEndToRRouter', condition=True):
        def is_file_side_effect(filename):
            return True if 'backend_acl' in filename else False
        with mock.patch('os.path.isfile', mock.MagicMock(side_effect=is_file_side_effect)):
            with mock.patch('config.main._get_device_type', mock.MagicMock(return_value=device_type)):
                with mock.patch(
                    "utilities_common.cli.run_command",
                    mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
                    (config, show) = get_cmd_module
                    runner = CliRunner()
                    result = runner.invoke(config.config.commands["load_minigraph"], ["-y"], obj=db)
                    print(result.exit_code)
                    expected_output = ['Running command: acl-loader update incremental /etc/sonic/backend_acl.json',
                                       'Running command: /usr/local/bin/sonic-cfggen -d -t /usr/share/sonic/templates/backend_acl.j2,/etc/sonic/backend_acl.json'
                                      ]
                    print(result.output)
                    assert result.exit_code == 0
                    output = result.output.split('\n')
                    if condition:
                        assert set(expected_output).issubset(set(output))
                    else:
                        assert not(set(expected_output).issubset(set(output)))

    def check_port_config(self, db, config, port_config, expected_output):
        def read_json_file_side_effect(filename):
            return port_config
        with mock.patch('config.main.read_json_file', mock.MagicMock(side_effect=read_json_file_side_effect)):
            def is_file_side_effect(filename):
                return True if 'port_config' in filename else False
            with mock.patch('os.path.isfile', mock.MagicMock(side_effect=is_file_side_effect)):
                runner = CliRunner()
                result = runner.invoke(config.config.commands["load_minigraph"], ["-y"], obj=db)
                print(result.exit_code)
                print(result.output)
                assert result.exit_code == 0
                assert expected_output in result.output

    def test_load_minigraph_with_golden_config(self, get_cmd_module, setup_single_broadcom_asic):
        with mock.patch(
            "utilities_common.cli.run_command",
            mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            (config, show) = get_cmd_module
            db = Db()
            golden_config = {}
            self.check_golden_config(db, config, golden_config,
                                     "config override-config-table /etc/sonic/golden_config_db.json")

    def check_golden_config(self, db, config, golden_config, expected_output):
        def is_file_side_effect(filename):
            return True if 'golden_config' in filename else False
        with mock.patch('os.path.isfile', mock.MagicMock(side_effect=is_file_side_effect)):
            runner = CliRunner()
            result = runner.invoke(config.config.commands["load_minigraph"], ["-y"], obj=db)
            print(result.exit_code)
            print(result.output)
            assert result.exit_code == 0
            assert expected_output in result.output

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")


class TestConfigQos(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ['UTILITIES_UNIT_TESTING'] = "2"
        import config.main
        imp.reload(config.main)

    def test_qos_reload_single(
            self, get_cmd_module, setup_qos_mock_apis,
            setup_single_broadcom_asic
        ):
        (config, show) = get_cmd_module
        runner = CliRunner()
        output_file = os.path.join(os.sep, "tmp", "qos_config_output.json")
        print("Saving output in {}".format(output_file))
        try:
            os.remove(output_file)
        except OSError:
            pass
        json_data = '{"DEVICE_METADATA": {"localhost": {}}}'
        result = runner.invoke(
            config.config.commands["qos"],
            ["reload", "--dry_run", output_file, "--json-data", json_data]
        )
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        cwd = os.path.dirname(os.path.realpath(__file__))
        expected_result = os.path.join(
            cwd, "qos_config_input", "config_qos.json"
        )
        assert filecmp.cmp(output_file, expected_result, shallow=False)

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ['UTILITIES_UNIT_TESTING'] = "0"


class TestConfigQosMasic(object):
    @classmethod
    def setup_class(cls):
        print("SETUP")
        os.environ['UTILITIES_UNIT_TESTING'] = "2"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = "multi_asic"
        import config.main
        imp.reload(config.main)

    def test_qos_reload_masic(
            self, get_cmd_module, setup_qos_mock_apis,
            setup_multi_broadcom_masic
        ):
        (config, show) = get_cmd_module
        runner = CliRunner()
        output_file = os.path.join(os.sep, "tmp", "qos_config_output.json")
        print("Saving output in {}<0,1,2..>".format(output_file))
        num_asic = device_info.get_num_npus()
        for asic in range(num_asic):
            try:
                file = "{}{}".format(output_file, asic)
                os.remove(file)
            except OSError:
                pass
        json_data = '{"DEVICE_METADATA": {"localhost": {}}}'
        result = runner.invoke(
            config.config.commands["qos"],
            ["reload", "--dry_run", output_file, "--json-data", json_data]
        )
        print(result.exit_code)
        print(result.output)
        assert result.exit_code == 0

        cwd = os.path.dirname(os.path.realpath(__file__))

        for asic in range(num_asic):
            expected_result = os.path.join(
                cwd, "qos_config_input", str(asic), "config_qos.json"
            )
            file = "{}{}".format(output_file, asic)
            assert filecmp.cmp(file, expected_result, shallow=False)

    @classmethod
    def teardown_class(cls):
        print("TEARDOWN")
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        os.environ["UTILITIES_UNIT_TESTING_TOPOLOGY"] = ""
        # change back to single asic config
        from .mock_tables import dbconnector
        from .mock_tables import mock_single_asic
        imp.reload(mock_single_asic)
        dbconnector.load_namespace_config()

class TestConfigLoadMgmtConfig(object):
    @classmethod
    def setup_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "1"
        print("SETUP")
        import config.main
        imp.reload(config.main)

    def test_config_load_mgmt_config_ipv4_only(self, get_cmd_module, setup_single_broadcom_asic):
        device_desc_result = {
            'DEVICE_METADATA': {
                'localhost': {
                    'hostname': 'dummy'
                }
            },
            'MGMT_INTERFACE': {
                ('eth0', '10.0.0.100/24') : {
                    'gwaddr': ipaddress.ip_address(u'10.0.0.1')
                }
            }
        }
        self.check_output(get_cmd_module, device_desc_result, load_mgmt_config_command_ipv4_only_output, 5)

    def test_config_load_mgmt_config_ipv6_only(self, get_cmd_module, setup_single_broadcom_asic):
        device_desc_result = {
            'DEVICE_METADATA': {
                'localhost': {
                    'hostname': 'dummy'
                }
            },
            'MGMT_INTERFACE': {
                ('eth0', 'FC00:1::32/64') : {
                    'gwaddr': ipaddress.ip_address(u'fc00:1::1')
                }
            }
        }
        self.check_output(get_cmd_module, device_desc_result, load_mgmt_config_command_ipv6_only_output, 5)
    
    def test_config_load_mgmt_config_ipv4_ipv6(self, get_cmd_module, setup_single_broadcom_asic):
        device_desc_result = {
            'DEVICE_METADATA': {
                'localhost': {
                    'hostname': 'dummy'
                }
            },
            'MGMT_INTERFACE': {
                ('eth0', '10.0.0.100/24') : {
                    'gwaddr': ipaddress.ip_address(u'10.0.0.1')
                },
                ('eth0', 'FC00:1::32/64') : {
                    'gwaddr': ipaddress.ip_address(u'fc00:1::1')
                }
            }
        }
        self.check_output(get_cmd_module, device_desc_result, load_mgmt_config_command_ipv4_ipv6_output, 8)

    def check_output(self, get_cmd_module, parse_device_desc_xml_result, expected_output, expected_command_call_count):
        def parse_device_desc_xml_side_effect(filename):
            print("parse dummy device_desc.xml")
            return parse_device_desc_xml_result
        def change_hostname_side_effect(hostname):
            print("change hostname to {}".format(hostname))
        with mock.patch("utilities_common.cli.run_command", mock.MagicMock(side_effect=mock_run_command_side_effect)) as mock_run_command:
            with mock.patch('config.main.parse_device_desc_xml', mock.MagicMock(side_effect=parse_device_desc_xml_side_effect)):
                with mock.patch('config.main._change_hostname', mock.MagicMock(side_effect=change_hostname_side_effect)):
                    (config, show) = get_cmd_module
                    runner = CliRunner()
                    with runner.isolated_filesystem():
                        with open('device_desc.xml', 'w') as f:
                            f.write('dummy')
                            result = runner.invoke(config.config.commands["load_mgmt_config"], ["-y", "device_desc.xml"])
                            print(result.exit_code)
                            print(result.output)
                            traceback.print_tb(result.exc_info[2])
                            assert result.exit_code == 0
                            assert "\n".join([l.rstrip() for l in result.output.split('\n')]) == expected_output
                            assert mock_run_command.call_count == expected_command_call_count

    @classmethod
    def teardown_class(cls):
        os.environ['UTILITIES_UNIT_TESTING'] = "0"
        print("TEARDOWN")

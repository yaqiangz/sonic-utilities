import click
from tabulate import tabulate
from swsscommon.swsscommon import ConfigDBConnector, SonicV2Connector


import utilities_common.cli as clicommon

DHCP_RELAY = 'DHCP_RELAY'
VLAN = "VLAN"
DHCPV6_SERVERS = "dhcpv6_servers"
DHCPV4_SERVERS = "dhcp_servers"
# STATE_DB Table
DHCPv6_COUNTER_TABLE = 'DHCPv6_COUNTER_TABLE'

# DHCPv6 Counter Messages
messages = ["Unknown", "Solicit", "Advertise", "Request", "Confirm", "Renew", "Rebind", "Reply", "Release", "Decline", "Relay-Forward", "Relay-Reply"]
config_db = ConfigDBConnector()


@click.group(cls=clicommon.AliasedGroup, name="dhcprelay_helper")
def dhcp_relay_helper():
    """Show DHCP_Relay helper information"""
    pass


@dhcp_relay_helper.command('ipv6')
def get_dhcpv6_helper_address():
    """Parse through DHCP_RELAY table for each interface in config_db.json and print dhcpv6 helpers in table format"""
    if config_db is not None:
        config_db.connect()
        table_data = config_db.get_table(DHCP_RELAY)
        if table_data is not None:
            vlans = config_db.get_keys(DHCP_RELAY)
            for vlan in vlans:
                output = get_data(table_data, vlan)
                print(output)


def get_data(table_data, vlan):
    vlan_data = table_data.get(vlan, {})
    helpers_data = vlan_data.get(DHCPV6_SERVERS)
    addr = {vlan: []}
    output = ''
    if helpers_data is not None:
        for ip in helpers_data:
            addr[vlan].append(ip)
        output = tabulate({'Interface': [vlan], vlan: addr.get(vlan)}, tablefmt='simple', stralign='right') + '\n'
    return output


def get_dhcp_relay_data_with_header(table_data, entry_name):
    vlan_relay = {}
    vlans = table_data.keys()
    for vlan in vlans:
        vlan_data = table_data.get(vlan)
        dhcp_relay_data = vlan_data.get(entry_name)
        if dhcp_relay_data is None or len(dhcp_relay_data) == 0:
            continue

        vlan_relay[vlan] = []
        for address in dhcp_relay_data:
            vlan_relay[vlan].append(address)

    dhcp_relay_vlan_keys = vlan_relay.keys()
    relay_address_list = ["\n".join(vlan_relay[key]) for key in dhcp_relay_vlan_keys]
    data = {"Interface": dhcp_relay_vlan_keys, "DHCP Relay Address": relay_address_list}
    return tabulate(data, tablefmt='grid', stralign='right', headers='keys') + '\n'


def get_dhcp_relay(table_name, entry_name, with_header):
    if config_db is None:
        return

    config_db.connect()
    table_data = config_db.get_table(table_name)
    if table_data is None:
        return

    if with_header:
        output = get_dhcp_relay_data_with_header(table_data, entry_name)
        print(output)
    else:
        vlans = config_db.get_keys(table_name)
        for vlan in vlans:
            output = get_data(table_data, vlan)
            print(output)


@click.group(cls=clicommon.AliasedGroup, name="dhcp_relay")
def dhcp_relay():
    """show DHCP_Relay information"""
    pass


@dhcp_relay.group(cls=clicommon.AliasedGroup, name="ipv6")
def dhcp_relay_ipv6():
    pass


@dhcp_relay.group(cls=clicommon.AliasedGroup, name="ipv4")
def dhcp_relay_ipv4():
    pass


@dhcp_relay_ipv4.command("helper")
def dhcp_relay_ipv4_destination():
    get_dhcp_relay(VLAN, DHCPV4_SERVERS, with_header=True)


@dhcp_relay_ipv6.command("destination")
def dhcp_relay_ipv6_destination():
    get_dhcp_relay(DHCP_RELAY, DHCPV6_SERVERS, with_header=True)


class DHCPv6_Counter(object):
    def __init__(self):
        self.db = SonicV2Connector(use_unix_socket_path=False)
        self.db.connect(self.db.STATE_DB)
        self.table_name = DHCPv6_COUNTER_TABLE + self.db.get_db_separator(self.db.STATE_DB)

    def get_interface(self):
        """ Get all names of all interfaces in DHCPv6_COUNTER_TABLE """
        vlans = []
        for key in self.db.keys(self.db.STATE_DB):
            if DHCPv6_COUNTER_TABLE in key:
                vlans.append(key[21:])
        return vlans

    def get_dhcp6relay_msg_count(self, interface, msg):
        """ Get count of a dhcp6relay message """
        count = self.db.get(self.db.STATE_DB, self.table_name + str(interface), str(msg))
        data = [str(msg), count]
        return data

    def clear_table(self, interface):
        """ Reset all message counts to 0 """
        for msg in messages:
            self.db.set(self.db.STATE_DB, self.table_name + str(interface), str(msg), '0') 


def print_count(counter, intf):
    """Print count of each message"""
    data = []
    for i in messages:
        data.append(counter.get_dhcp6relay_msg_count(intf, i))
    print(tabulate(data, headers=["Message Type", intf], tablefmt='simple', stralign='right') + "\n")


#
# 'dhcp6relay_counters' group ###
#


@click.group(cls=clicommon.AliasedGroup, name="dhcp6relay_counters")
def dhcp6relay_counters():
    """Show DHCPv6 counter"""
    pass


# 'counts' subcommand ("show dhcp6relay_counters counts")
@dhcp6relay_counters.command('counts')
@click.option('-i', '--interface', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def counts(interface, verbose):
    """Show dhcp6relay message counts"""
    ipv6_counters(interface)


def ipv6_counters(interface):
    counter = DHCPv6_Counter()
    counter_intf = counter.get_interface()

    if interface:
        print_count(counter, interface)
    else:
        for intf in counter_intf:
            print_count(counter, intf)


# 'clear' subcommand ("clear dhcp6relay_counters counts")
@dhcp6relay_counters.command('clear')
@click.option('-i', '--interface', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def clear(interface, verbose):
    """Clear dhcp6relay message counts"""
    counter = DHCPv6_Counter()
    counter_intf = counter.get_interface()

    if interface:
        counter.clear_table(interface)
        print("Cleared DHCPv6 Relay Counter " + interface)
    else:
        for intf in counter_intf:
            counter.clear_table(intf)
        print("Cleared DHCPv6 Relay Counters")


@dhcp_relay_ipv6.command("counters")
@click.option('-i', '--interface', required=False)
def dhcp_relay_ip6counters(interface):
    ipv6_counters(interface)

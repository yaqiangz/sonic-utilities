import click
import ipaddress
import utilities_common.cli as clicommon
import utilities_common.dhcp_relay_util as dhcp_relay_util
from swsscommon.swsscommon import SonicV2Connector

from time import sleep
from .utils import log

DHCP_RELAY_TABLE = "DHCP_RELAY"
DHCPV6_SERVERS = "dhcpv6_servers"


#
# 'vlan' group ('config vlan ...')
#
@click.group(cls=clicommon.AbbreviationGroup, name='vlan')
def vlan():
    """VLAN-related configuration tasks"""
    pass


def set_dhcp_relay_table(table, config_db, vlan_name, value):
    config_db.set_entry(table, vlan_name, value)


def is_dhcp_relay_running():
    out, _ = clicommon.run_command("systemctl show dhcp_relay.service --property ActiveState --value", return_cmd=True)
    return out.strip() == "active"


@vlan.command('add')
@click.argument('vid', metavar='<vid>', required=True, type=int)
@clicommon.pass_db
def add_vlan(db, vid):
    """Add VLAN"""

    ctx = click.get_current_context()

    if not clicommon.is_vlanid_in_range(vid):
        ctx.fail("Invalid VLAN ID {} (1-4094)".format(vid))

    vlan = 'Vlan{}'.format(vid)
    if clicommon.check_if_vlanid_exist(db.cfgdb, vlan):
        ctx.fail("{} already exists".format(vlan))
    if clicommon.check_if_vlanid_exist(db.cfgdb, vlan, "DHCP_RELAY"):
        ctx.fail("DHCPv6 relay config for {} already exists".format(vlan))

    # set dhcpv4_relay table
    set_dhcp_relay_table('VLAN', db.cfgdb, vlan, {'vlanid': str(vid)})


def is_dhcpv6_relay_config_exist(db, vlan_name):
    keys = db.cfgdb.get_keys(DHCP_RELAY_TABLE)
    if len(keys) == 0 or vlan_name not in keys:
        return False

    table = db.cfgdb.get_entry(DHCP_RELAY_TABLE, vlan_name)
    dhcpv6_servers = table.get(DHCPV6_SERVERS, [])
    if len(dhcpv6_servers) > 0:
        return True


def delete_state_db_entry(entry_name):
    state_db = SonicV2Connector()
    state_db.connect(state_db.STATE_DB)
    exists = state_db.exists(state_db.STATE_DB, 'DHCPv6_COUNTER_TABLE|{}'.format(entry_name))
    if exists:
        state_db.delete(state_db.STATE_DB, 'DHCPv6_COUNTER_TABLE|{}'.format(entry_name))


@vlan.command('del')
@click.argument('vid', metavar='<vid>', required=True, type=int)
@click.option('--no_restart_dhcp_relay', is_flag=True, type=click.BOOL, required=False, default=False,
              help="If no_restart_dhcp_relay is True, do not restart dhcp_relay while del vlan and \
                  require dhcpv6 relay of this is empty")
@clicommon.pass_db
def del_vlan(db, vid, no_restart_dhcp_relay):
    """Delete VLAN"""

    log.log_info("'vlan del {}' executing...".format(vid))

    ctx = click.get_current_context()

    if not clicommon.is_vlanid_in_range(vid):
        ctx.fail("Invalid VLAN ID {} (1-4094)".format(vid))

    vlan = 'Vlan{}'.format(vid)
    if clicommon.check_if_vlanid_exist(db.cfgdb, vlan) == False:
        ctx.fail("{} does not exist".format(vlan))
    if no_restart_dhcp_relay:
        if is_dhcpv6_relay_config_exist(db, vlan):
            ctx.fail("Can't delete {} because related DHCPv6 Relay config is exist".format(vlan))

    intf_table = db.cfgdb.get_table('VLAN_INTERFACE')
    for intf_key in intf_table:
        if ((type(intf_key) is str and intf_key == 'Vlan{}'.format(vid)) or
            (type(intf_key) is tuple and intf_key[0] == 'Vlan{}'.format(vid))):
            ctx.fail("{} can not be removed. First remove IP addresses assigned to this VLAN".format(vlan))

    keys = [ (k, v) for k, v in db.cfgdb.get_table('VLAN_MEMBER') if k == 'Vlan{}'.format(vid) ]

    if keys:
        ctx.fail("VLAN ID {} can not be removed. First remove all members assigned to this VLAN.".format(vid))

    # set dhcpv4_relay table
    set_dhcp_relay_table('VLAN', db.cfgdb, vlan, None)

    if not no_restart_dhcp_relay and is_dhcpv6_relay_config_exist(db, vlan):
        # set dhcpv6_relay table
        set_dhcp_relay_table('DHCP_RELAY', db.cfgdb, vlan, None)
        # We need to restart dhcp_relay service after dhcpv6_relay config change
        if is_dhcp_relay_running():
            dhcp_relay_util.handle_restart_dhcp_relay_service()
    delete_state_db_entry(vlan)


def restart_ndppd():
    verify_swss_running_cmd = "docker container inspect -f '{{.State.Status}}' swss"
    docker_exec_cmd = "docker exec -i swss {}"
    ndppd_config_gen_cmd = "sonic-cfggen -d -t /usr/share/sonic/templates/ndppd.conf.j2,/etc/ndppd.conf"
    ndppd_restart_cmd = "supervisorctl restart ndppd"

    output = clicommon.run_command(verify_swss_running_cmd, return_cmd=True)

    if output and output.strip() != "running":
        click.echo(click.style('SWSS container is not running, changes will take effect the next time the SWSS container starts', fg='red'),)
        return

    clicommon.run_command(docker_exec_cmd.format(ndppd_config_gen_cmd), display_cmd=True)
    sleep(3)
    clicommon.run_command(docker_exec_cmd.format(ndppd_restart_cmd), display_cmd=True)


@vlan.command('proxy_arp')
@click.argument('vid', metavar='<vid>', required=True, type=int)
@click.argument('mode', metavar='<mode>', required=True, type=click.Choice(["enabled", "disabled"]))
@clicommon.pass_db
def config_proxy_arp(db, vid, mode):
    """Configure proxy ARP for a VLAN"""

    log.log_info("'setting proxy ARP to {} for Vlan{}".format(mode, vid))

    ctx = click.get_current_context()

    vlan = 'Vlan{}'.format(vid)

    if not clicommon.is_valid_vlan_interface(db.cfgdb, vlan):
        ctx.fail("Interface {} does not exist".format(vlan))

    db.cfgdb.mod_entry('VLAN_INTERFACE', vlan, {"proxy_arp": mode})
    click.echo('Proxy ARP setting saved to ConfigDB')
    restart_ndppd()
#
# 'member' group ('config vlan member ...')
#
@vlan.group(cls=clicommon.AbbreviationGroup, name='member')
def vlan_member():
    pass

@vlan_member.command('add')
@click.argument('vid', metavar='<vid>', required=True, type=int)
@click.argument('port', metavar='port', required=True)
@click.option('-u', '--untagged', is_flag=True)
@clicommon.pass_db
def add_vlan_member(db, vid, port, untagged):
    """Add VLAN member"""

    ctx = click.get_current_context()

    log.log_info("'vlan member add {} {}' executing...".format(vid, port))

    if not clicommon.is_vlanid_in_range(vid):
        ctx.fail("Invalid VLAN ID {} (1-4094)".format(vid))

    vlan = 'Vlan{}'.format(vid)
    if clicommon.check_if_vlanid_exist(db.cfgdb, vlan) == False:
        ctx.fail("{} does not exist".format(vlan))

    if clicommon.get_interface_naming_mode() == "alias":
        alias = port
        iface_alias_converter = clicommon.InterfaceAliasConverter(db)
        port = iface_alias_converter.alias_to_name(alias)
        if port is None:
            ctx.fail("cannot find port name for alias {}".format(alias))

    if clicommon.is_port_mirror_dst_port(db.cfgdb, port):
        ctx.fail("{} is configured as mirror destination port".format(port))

    if clicommon.is_port_vlan_member(db.cfgdb, port, vlan):
        ctx.fail("{} is already a member of {}".format(port, vlan))

    if clicommon.is_valid_port(db.cfgdb, port):
        is_port = True
    elif clicommon.is_valid_portchannel(db.cfgdb, port):
        is_port = False
    else:
        ctx.fail("{} does not exist".format(port))

    if (is_port and clicommon.is_port_router_interface(db.cfgdb, port)) or \
       (not is_port and clicommon.is_pc_router_interface(db.cfgdb, port)):
        ctx.fail("{} is a router interface!".format(port))
        
    portchannel_member_table = db.cfgdb.get_table('PORTCHANNEL_MEMBER')

    if (is_port and clicommon.interface_is_in_portchannel(portchannel_member_table, port)):
        ctx.fail("{} is part of portchannel!".format(port))

    if (clicommon.interface_is_untagged_member(db.cfgdb, port) and untagged):
        ctx.fail("{} is already untagged member!".format(port))

    db.cfgdb.set_entry('VLAN_MEMBER', (vlan, port), {'tagging_mode': "untagged" if untagged else "tagged" })

@vlan_member.command('del')
@click.argument('vid', metavar='<vid>', required=True, type=int)
@click.argument('port', metavar='<port>', required=True)
@clicommon.pass_db
def del_vlan_member(db, vid, port):
    """Delete VLAN member"""

    ctx = click.get_current_context()

    log.log_info("'vlan member del {} {}' executing...".format(vid, port))

    if not clicommon.is_vlanid_in_range(vid):
        ctx.fail("Invalid VLAN ID {} (1-4094)".format(vid))

    vlan = 'Vlan{}'.format(vid)
    if clicommon.check_if_vlanid_exist(db.cfgdb, vlan) == False:
        ctx.fail("{} does not exist".format(vlan))

    if clicommon.get_interface_naming_mode() == "alias":
        alias = port
        iface_alias_converter = clicommon.InterfaceAliasConverter(db)
        port = iface_alias_converter.alias_to_name(alias)
        if port is None:
            ctx.fail("cannot find port name for alias {}".format(alias))

    if not clicommon.is_port_vlan_member(db.cfgdb, port, vlan):
        ctx.fail("{} is not a member of {}".format(port, vlan))

    db.cfgdb.set_entry('VLAN_MEMBER', (vlan, port), None)

@vlan.group(cls=clicommon.AbbreviationGroup, name='dhcp_relay')
def vlan_dhcp_relay():
    pass

@vlan_dhcp_relay.command('add')
@click.argument('vid', metavar='<vid>', required=True, type=int)
@click.argument('dhcp_relay_destination_ip', metavar='<dhcp_relay_destination_ip>', required=True)
@clicommon.pass_db
def add_vlan_dhcp_relay_destination(db, vid, dhcp_relay_destination_ip):
    """ Add a destination IP address to the VLAN's DHCP relay """

    ctx = click.get_current_context()

    try:
        ipaddress.ip_address(dhcp_relay_destination_ip)
    except Exception:
        ctx.fail('{} is invalid IP address'.format(dhcp_relay_destination_ip))

    vlan_name = 'Vlan{}'.format(vid)
    vlan = db.cfgdb.get_entry('VLAN', vlan_name)
    if len(vlan) == 0:
        ctx.fail("{} doesn't exist".format(vlan_name))

    # Verify all ip addresses are valid and not exist in DB
    dhcp_servers = vlan.get('dhcp_servers', [])
    dhcpv6_servers = vlan.get('dhcpv6_servers', [])

    if dhcp_relay_destination_ip in dhcp_servers + dhcpv6_servers:
        click.echo("{} is already a DHCP relay destination for {}".format(dhcp_relay_destination_ip, vlan_name))
        return

    if clicommon.ipaddress_type(dhcp_relay_destination_ip) == 6:
        dhcpv6_servers.append(dhcp_relay_destination_ip)
        vlan['dhcpv6_servers'] = dhcpv6_servers
    else:
        dhcp_servers.append(dhcp_relay_destination_ip)
        vlan['dhcp_servers'] = dhcp_servers

    db.cfgdb.set_entry('VLAN', vlan_name, vlan)
    click.echo("Added DHCP relay destination address {} to {}".format(dhcp_relay_destination_ip, vlan_name))
    dhcp_relay_util.handle_restart_dhcp_relay_service()

@vlan_dhcp_relay.command('del')
@click.argument('vid', metavar='<vid>', required=True, type=int)
@click.argument('dhcp_relay_destination_ip', metavar='<dhcp_relay_destination_ip>', required=True)
@clicommon.pass_db
def del_vlan_dhcp_relay_destination(db, vid, dhcp_relay_destination_ip):
    """ Remove a destination IP address from the VLAN's DHCP relay """

    ctx = click.get_current_context()

    if not clicommon.is_ipaddress(dhcp_relay_destination_ip):
        ctx.fail('{} is invalid IP address'.format(dhcp_relay_destination_ip))

    vlan_name = 'Vlan{}'.format(vid)
    vlan = db.cfgdb.get_entry('VLAN', vlan_name)
    if len(vlan) == 0:
        ctx.fail("{} doesn't exist".format(vlan_name))

    # Remove dhcp servers if they exist in the DB
    dhcp_servers = vlan.get('dhcp_servers', [])
    dhcpv6_servers = vlan.get('dhcpv6_servers', [])

    if not dhcp_relay_destination_ip in dhcp_servers + dhcpv6_servers:
        ctx.fail("{} is not a DHCP relay destination for {}".format(dhcp_relay_destination_ip, vlan_name))

    if clicommon.ipaddress_type(dhcp_relay_destination_ip) == 6:
        dhcpv6_servers.remove(dhcp_relay_destination_ip)
        if len(dhcpv6_servers) == 0:
            del vlan['dhcpv6_servers']
        else:
            vlan['dhcpv6_servers'] = dhcpv6_servers
    else:
        dhcp_servers.remove(dhcp_relay_destination_ip)
        if len(dhcp_servers) == 0:
            del vlan['dhcp_servers']
        else:
            vlan['dhcp_servers'] = dhcp_servers
    
    db.cfgdb.set_entry('VLAN', vlan_name, vlan)
    click.echo("Removed DHCP relay destination address {} from {}".format(dhcp_relay_destination_ip, vlan_name))
    dhcp_relay_util.handle_restart_dhcp_relay_service()

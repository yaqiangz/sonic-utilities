import click
import utilities_common.cli as clicommon


def restart_dhcp_relay_service():
    """
    Restart dhcp_relay service
    """
    click.echo("Restarting DHCP relay service...")
    clicommon.run_command("systemctl stop dhcp_relay", display_cmd=False)
    clicommon.run_command("systemctl reset-failed dhcp_relay", display_cmd=False)
    clicommon.run_command("systemctl start dhcp_relay", display_cmd=False)


def handle_restart_dhcp_relay_service(ignore_system_exit_error=False):
    try:
        restart_dhcp_relay_service()
    except SystemExit as e:
        ctx = click.get_current_context()

        if ignore_system_exit_error:
            ctx.exit(0)

        ctx.fail("Restart service dhcp_relay failed with error {}".format(e))

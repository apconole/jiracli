import click
import logging

from jcli import connector

LOG = logging.getLogger(__name__)


@click.command(
    name='login'
)
def login_cmd() -> None:
    """Tests that the login routine is working.
    """
    jobj = connector.JiraConnector()

    try:
        jobj.login()
    except Exception as e:
        click.echo(f"Error: {e} when logging in")


@click.command(
    name='myself'
)
def myself_cmd() -> None:
    """Display the logged in user.
    """
    jobj = connector.JiraConnector()
    jobj.login()
    click.echo(jobj.myself())

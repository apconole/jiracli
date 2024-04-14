import click
import logging
import os

from jcli import connector

LOG = logging.getLogger(__name__)

@click.command(
    name='login'
)
def login_cmd() -> None:
    jobj = connector.JiraConnector()

    try:
        jobj.login()
    except Exception as e:
        click.echo(f"Error: {e} when logging in")

@click.command(
    name='myself'
)
def myself_cmd() -> None:
    jobj = connector.JiraConnector()
    jobj.login()
    click.echo(jobj.myself())

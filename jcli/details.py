import click
import logging
import os

from jcli import connector

@click.command(
    name='last-states'
)
def last_states_cmd():
    jobj = connector.JiraConnector()
    jobj.login()
    click.echo(jobj.last_states_names())

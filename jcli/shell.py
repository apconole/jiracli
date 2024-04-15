"""
TODO.
"""

import click
import logging

from jcli import myself as my_cmds
from jcli import issues as issues_cmds

@click.group()
@click.option('--debug', default=False, is_flag=True,
              help="Output more information about what's going on.")
@click.option('--config', metavar="CONFIG", envvar="JCLI_YAML",
              help="Location of jira yaml configuration.  Defaults to "
              "'~/.jira.yml'")
@click.version_option()
def cli(debug, config):
    """Tools for interacting / authenticating with jira
    """
    if debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    else:
        logging.basicConfig(level=logging.INFO, format='%(message)s')


@cli.group()
def issues():
    """Lists the user currently logged in.

    """
    pass


cli.add_command(my_cmds.login_cmd)
cli.add_command(my_cmds.myself_cmd)

issues.add_command(issues_cmds.list_cmd)
issues.add_command(issues_cmds.show_cmd)
issues.add_command(issues_cmds.add_comment_cmd)
issues.add_command(issues_cmds.states_cmd)
issues.add_command(issues_cmds.set_field_cmd)

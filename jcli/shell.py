"""
TODO.
"""

import click
import logging

from jcli import boards as boards_cmds
from jcli import config as config_cmds
from jcli import details as details_cmds
from jcli import issues as issues_cmds
from jcli import myself as my_cmds
from jcli import users as users_cmds
from jcli import utils as utils_cmds


@click.group()
@click.option('--debug', default=False, is_flag=True,
              help="Output more information about what's going on.")
@click.option('--config', metavar="CONFIG", envvar="JCLI_YAML",
              help="Location of jira yaml configuration.  Defaults to "
              "'~/.jira.yml'")
@click.pass_context
@click.version_option()
def cli(ctx, debug, config):
    """Tools for interacting / authenticating with jira
    """
    ctx.ensure_object(dict)

    if debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    else:
        logging.basicConfig(level=logging.INFO, format='%(message)s')


@cli.group()
def config():
    """Commands for interacting with the configuration.
    """
    pass


@cli.group()
def issues():
    """Lists the user currently logged in.

    """
    pass


@cli.group()
def details():
    """Lists details about the JIRA instance"
    """
    pass


@cli.group()
def boards():
    """
    Boards / Sprint related commands.
    """
    pass


@cli.group()
def users():
    """
    User related commands.
    """
    pass


@cli.group()
def utils():
    """
    Generic related utilities.
    """


cli.add_command(my_cmds.login_cmd)
cli.add_command(my_cmds.myself_cmd)

config.add_command(config_cmds.clear_config_cmd)
config.add_command(config_cmds.get_config_cmd)
config.add_command(config_cmds.set_config_cmd)
config.add_command(config_cmds.append_config_cmd)

issues.add_command(issues_cmds.list_cmd)
issues.add_command(issues_cmds.show_cmd)
issues.add_command(issues_cmds.add_comment_cmd)
issues.add_command(issues_cmds.states_cmd)
issues.add_command(issues_cmds.set_state_cmd)
issues.add_command(issues_cmds.set_field_cmd)
issues.add_command(issues_cmds.set_field_from_csv_cmd)
issues.add_command(issues_cmds.create_issue_cmd)
issues.add_command(issues_cmds.add_watcher_cmd)
issues.add_command(issues_cmds.del_watcher_cmd)
issues.add_command(issues_cmds.attachments_cmd)
issues.add_command(issues_cmds.get_field_cmd)
issues.add_command(issues_cmds.del_comment_cmd)
issues.add_command(issues_cmds.update_comment_cmd)
issues.add_command(issues_cmds.eausm_vote_cmd)
issues.add_command(issues_cmds.add_link_cmd)

details.add_command(details_cmds.last_states_cmd)
details.add_command(details_cmds.server_info_cmd)
details.add_command(details_cmds.statuses_cmd)
details.add_command(details_cmds.groups_info_cmd)
details.add_command(details_cmds.components_info_cmd)
details.add_command(details_cmds.link_types_cmd)
details.add_command(details_cmds.dump_project_versions_cmd)

boards.add_command(boards_cmds.list_cmd)
boards.add_command(boards_cmds.show_cmd)
boards.add_command(boards_cmds.get_config_cmd)
boards.add_command(boards_cmds.sprints_cmd)

users.add_command(users_cmds.users_find_cmd)

utils.add_command(utils_cmds.convert_cmd)

# Add a shell-cmd option when click-shell is installed
try:
    from click_shell import shell

    @shell(prompt="jcli> ", intro="Starting...")
    def shell_cmd():
        pass

    shell_cmd.add_command(my_cmds.login_cmd)
    shell_cmd.add_command(my_cmds.myself_cmd)
    shell_cmd.add_command(issues)
    shell_cmd.add_command(details)
    shell_cmd.add_command(boards)
    shell_cmd.add_command(users)
    cli.add_command(shell_cmd)
except:
    pass

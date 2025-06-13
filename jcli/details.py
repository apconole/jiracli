import click
from jcli import connector
import pprint


@click.command(
    name='last-states'
)
def last_states_cmd():
    """Print all the 'final' states for issues on the server.

    NOTE: Not all states are valid for all issues / projects.
    """
    jobj = connector.JiraConnector()
    jobj.login()
    click.echo(jobj.last_states_names())


@click.command(
    name='statuses'
)
def statuses_cmd():
    """Print the various 'states' or 'statuses' known to the server.

    NOTE: Not all states are valid for all issues / projects.
    """
    jobj = connector.JiraConnector()
    jobj.login()
    click.echo([(x.name, x.id) for x in jobj._get_statuses()])


@click.command(
    name="server-info"
)
def server_info_cmd():
    """Dumps basic server details."""
    jobj = connector.JiraConnector()
    jobj.login()

    jobj._ratelimit()
    server_info = jobj.jira.server_info()

    click.echo(pprint.pformat(server_info))


@click.command(
    name="groups"
)
def groups_info_cmd():
    """Display the various GROUPs that are set on the server."""
    jobj = connector.JiraConnector()
    jobj.login()

    grps = jobj._groups()

    click.echo(pprint.pformat(grps))


@click.command(
    name="components"
)
@click.argument("project")
def components_info_cmd(project):
    """Displays a list of components for the given PROJECT."""
    jobj = connector.JiraConnector()
    jobj.login()

    comps = [{'name': x.name, 'id': x.id} for x in jobj._components(project)]

    click.echo(pprint.pformat(comps))


@click.command(
    name="link-types"
)
def link_types_cmd():
    """Displays the types of links that the server supports."""
    jobj = connector.JiraConnector()
    jobj.login()

    click.echo(pprint.pformat(jobj.jira.issue_link_types()))

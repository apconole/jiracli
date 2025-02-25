import click
from jcli import connector
import pprint


@click.command(
    name='last-states'
)
def last_states_cmd():
    jobj = connector.JiraConnector()
    jobj.login()
    click.echo(jobj.last_states_names())


@click.command(
    name='statuses'
)
def statuses_cmd():
    jobj = connector.JiraConnector()
    jobj.login()
    click.echo([(x.name, x.id) for x in jobj._get_statuses()])


@click.command(
    name="server-info"
)
def server_info_cmd():
    jobj = connector.JiraConnector()
    jobj.login()

    server_info = jobj.jira.server_info()

    click.echo(pprint.pformat(server_info))


@click.command(
    name="groups"
)
def groups_info_cmd():
    jobj = connector.JiraConnector()
    jobj.login()

    grps = jobj._groups()

    click.echo(pprint.pformat(grps))


@click.command(
    name="components"
)
@click.argument("project")
def components_info_cmd(project):
    jobj = connector.JiraConnector()
    jobj.login()

    comps = [{'name': x.name, 'id': x.id} for x in jobj._components(project)]

    click.echo(pprint.pformat(comps))


@click.command(
    name="link-types"
)
def link_types_cmd():
    jobj = connector.JiraConnector()
    jobj.login()

    click.echo(pprint.pformat(jobj.jira.issue_link_types()))

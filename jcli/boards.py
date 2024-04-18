import click
import logging
import pprint

from jcli import connector
from jcli.utils import display_via_pager
from jcli.utils import issue_eval

from tabulate import tabulate

LOG = logging.getLogger(__name__)

BOARD_HEADER_MAP = {
    "name": "raw['name']",
    "type": "raw['type']",
}

BOARD_DETAILS_MAP = {
    "key": "key",
    "project": "raw['fields']['project']['name']",
    "priority": "raw['fields']['priority']['name']",
    "summary": "raw['fields']['summary']",
    "status": "raw['fields']['status']['name']",
    "assignee": "raw['fields']['assignee']['name']",
}


@click.command(
    name="list"
)
@click.option("--limit", type=int, default=25,
              help="Limit the number of entries to display (default 25)")
def list_cmd(limit):
    """
    Displays all the boards on the instance (can be crazy)
    """
    jobj = connector.JiraConnector()
    jobj.login()

    boards = jobj.fetch_boards(limit)

    boards_out = []

    for board in boards:
        board_details = issue_eval(board, BOARD_HEADER_MAP)
        boards_out.append(board_details)

    out = tabulate(boards_out, BOARD_HEADER_MAP, 'psql')
    display_via_pager(out)


@click.command(
    name='show'
)
@click.argument('boardname')
@click.option('--assignee', type=str, default=None,
              help="The name of the assignee (defaults to all)")
@click.option('--project', type=str, default=None,
              help="The name of the project (defaults to '')")
@click.option('--issue-offset', type=int, default=0,
              help="Sets the offset for pulling issues")
@click.option('--max-issues', type=int, default=100,
              help="Sets the max number of issues to pull")
def show_cmd(boardname, assignee, project, issue_offset, max_issues):
    """
    Displays the board specified by 'name'
    """
    jobj = connector.JiraConnector()
    jobj.login()

    columns = jobj.fetch_column_config_by_board(boardname)
    ISSUE_HEADER = [k for k in columns]
    issue_col_store = {k: [] for k in columns}

    issues = jobj.fetch_issues_by_board(boardname, issue_offset, max_issues)
    for issue in issues:
        if assignee is not None:
            if ((issue.raw['fields']['assignee'] is None) or
                (('name' in issue.raw['fields']['assignee'] and
                  issue.fields.assignee.name.lower() != assignee.lower()) and
                 ('displayName' in issue.raw['fields']['assignee'] and
                  issue.fields.assignee.displayName.lower() != assignee.lower()))):
                continue
        for k in columns:
            if issue.fields.status in columns[k]:
                issue_col_store[k].append(issue)

    final = tabulate(issue_col_store, ISSUE_HEADER, 'psql')
    display_via_pager(final)


@click.command(name='get-config')
@click.argument('boardname')
def get_config_cmd(boardname):
    """
    Displays the board configuration specified by 'boardname'
    """

    jobj = connector.JiraConnector()
    jobj.login()

    settings = {}

    settings["filter"] = jobj.fetch_jql_config_by_board(boardname)
    cols = jobj.fetch_column_config_by_board(boardname)

    for k, v in cols.items():
        settings[f"column.{k}"] = v

    click.echo(pprint.pprint(settings))

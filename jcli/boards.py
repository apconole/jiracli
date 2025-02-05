import click
import logging
import pprint

from jcli import connector
from jcli.utils import display_via_pager
from jcli.utils import issue_eval
from jcli.utils import trim_text

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


def is_issue_assigned_to(issue, assignee):
    return issue.fields.assignee and \
        (issue.fields.assignee.name.lower() == assignee.lower() or
         issue.fields.assignee.displayName.lower() == assignee.lower())


def is_issue_in_column(issue, column_statuses, jobj):
    return hasattr(issue, 'fields') and \
        issue.fields.status in column_statuses or \
        hasattr(issue, 'statusId') and \
        jobj.get_status_detail(issue.statusId) in column_statuses


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
    display_via_pager(out, "Jira Board List")


@click.command(
    name='show'
)
@click.argument('boardname')
@click.option('--assignee', type=str, default=None,
              help="The name of the assignee (defaults to all)")
@click.option('--project', type=str, default=None,
              help="The name of the project (defaults to '')")
@click.option("--filter", type=str, default=None,
              help="Applies a quick filter to the results (defaults to None)")
@click.option("--summary-len", type=int, default=0,
              help="Includes a summary of the length specified when set (defaults to 0, meaning no summary)")
@click.option('--issue-offset', type=int, default=0,
              help="Sets the offset for pulling issues")
@click.option('--max-issues', type=int, default=100,
              help="Sets the max number of issues to pull")
def show_cmd(boardname, assignee, project, filter, summary_len, issue_offset, max_issues):
    """
    Displays the board specified by 'name'
    """
    jobj = connector.JiraConnector()
    jobj.login()

    columns = jobj.fetch_column_config_by_board(boardname)
    ISSUE_HEADER = [column for column in columns]
    issue_col_store = {column: [] for column in columns}

    if filter:
        issues = jobj.fetch_issues_by_board_qf(boardname, issue_offset, max_issues, filter)
    else:
        issues = jobj.fetch_issues_by_board(boardname, issue_offset, max_issues)

    for issue in issues:
        if assignee and not is_issue_assigned_to(issue, assignee):
            continue
        for column in columns:
            if is_issue_in_column(issue, columns[column], jobj):
                issuestr = f"{issue.key}"
                if summary_len:
                    issuestr += f"\n{'-' * summary_len}\n{trim_text(issue.summary, summary_len)}\n{'_' * summary_len}"
                issue_col_store[column].append(issuestr)

    final_output = tabulate(issue_col_store, ISSUE_HEADER, 'psql')
    display_via_pager(final_output, f"Board: {boardname}")


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

    f = jobj.fetch_quickfilters_by_board(boardname)
    if f:
        for filt in f.quickFilters:
            click.echo(f"quickfilter.name = \"{filt.name}\"")
            click.echo(f"quickfilter.query = \"{filt.query}\"")
            click.echo(f"quickfilter.id = \"{filt.id}\"")


@click.command('sprints')
@click.argument('boardname')
@click.option('--name', type=str, default=None,
              help='Display details for a specific sprint.')
def sprints_cmd(boardname, name):
    """
    Displays the sprints of a board, optionally specified by 'name'
    """
    jobj = connector.JiraConnector()
    jobj.login()

    sprints = jobj.fetch_sprints_by_board(boardname)
    base_filter = jobj.fetch_jql_config_by_board(boardname)
    columns = jobj.fetch_column_config_by_board(boardname)
    ISSUE_HEADER = [column for column in columns]

    final_output = ""
    for sprint in sprints:
        if sprint.state == "closed":
            continue

        if name and name != sprint:
            continue

        issue_col_store = {column: [] for column in columns}
        final_output += f"Sprint: {sprint}, id: {sprint.id}\n   start: {sprint.startDate} -> end: {sprint.endDate}\n"

        issues_query = f'sprint = "{str(sprint)}" and {base_filter}'
        issues = jobj._query_issues(issues_query, 0, 250)

        for issue in issues:
            for column in columns:
                if is_issue_in_column(issue, columns[column], jobj):
                    issuestr = f"{issue.key}"
                    issue_col_store[column].append(issuestr)

        if len(issues):
            final_output += tabulate(issue_col_store, ISSUE_HEADER, 'psql')
            final_output += "\n\n"

    click.echo(final_output)

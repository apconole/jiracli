import click
import logging
import os
import pprint
import sys

from jcli import connector
from jcli.utils import trim_text
from jcli.utils import issue_eval
from jcli.utils import SEP_STR
from jcli.utils import display_via_pager
from jcli.utils import get_text_via_editor
from jcli.utils import fitted_blocks
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
    click.echo(out)

@click.command(
    name='show'
)
@click.argument('boardname')
def show_cmd(boardname):
    """
    Displays the board specified by 'name'
    """

    jobj = connector.JiraConnector()
    jobj.login()

    sprints = jobj.fetch_sprints_by_board(boardname)
    click.echo(len(sprints))

    issues = jobj.fetch_issues_by_board(boardname)
    ISSUE_HEADER = []

    if len(issues) != 0:
        issue_list = []
        summary_pos = None

        for header in BOARD_DETAILS_MAP:
            if header not in ISSUE_HEADER:
                ISSUE_HEADER.append(header)

        if "summary" in ISSUE_HEADER:
            summary_pos = ISSUE_HEADER.index("summary")

        for issue in issues:
            issue_details = issue_eval(issue, BOARD_DETAILS_MAP)
            if summary_pos != None:
                issue_details[summary_pos] = trim_text(
                    issue_details[summary_pos], 45
                )
            issue_list.append(issue_details)

        final = tabulate(issue_list, ISSUE_HEADER, 'psql')
        click.echo(final)

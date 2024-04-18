import click
import logging
import pprint
import shutil
import sys

from jcli import connector
from jcli.utils import display_via_pager
from jcli.utils import fitted_blocks
from jcli.utils import get_text_via_editor
from jcli.utils import issue_eval
from jcli.utils import trim_text
from tabulate import tabulate

LOG = logging.getLogger(__name__)

ISSUE_DETAILS_MAP = {
    "key": "key",
    "project": "raw['fields']['project']['name']",
    "priority": "raw['fields']['priority']['name']",
    "summary": "raw['fields']['summary']",
    "status": "raw['fields']['status']['name']",
    "assignee": "raw['fields']['assignee']['name']",
}


@click.command(
    name='list'
)
@click.option('--assignee', type=str, default="",
              help="The name of the assignee (defaults to current user)")
@click.option('--project', type=str, default=None,
              help="The name of the project (defaults to '')")
@click.option('--jql', type=str, default=None,
              help="A raw JQL string to execute against the issues search")
@click.option("--closed", type=bool, default=False,
              help="Whether to include closed issues (default is False).")
@click.option("--summary-len", 'len_', type=int, default=45,
              help="Trim the summary length to certain number of chars (45 default, 0 for no trim)")
@click.option('--output', type=click.Choice(['table', 'csv', 'simple']),
              default='table',
              help="Output format (default is 'table')")
@click.option("--matching-eq", multiple=True, nargs=2, help="Custom JQL pair")
@click.option("--matching-neq", multiple=True, nargs=2, help="Custom JQL pair")
@click.option("--matching-contains", multiple=True, nargs=2, help="Custom JQL pair")
@click.option("--matching-not", multiple=True, nargs=2, help="Custom JQL pair")
@click.option("--matching-in", multiple=True, nargs=2, help="Custom JQL pair")
@click.option("--matching-gt", multiple=True, nargs=2, help="Custom JQL pair")
@click.option("--matching-lt", multiple=True, nargs=2, help="Custom JQL pair")
@click.option("--matching-ge", multiple=True, nargs=2, help="Custom JQL pair")
@click.option("--matching-le", multiple=True, nargs=2, help="Custom JQL pair")
@click.option("--mentions", type=bool, is_flag=True, default=False,
              help="Checks for mentions on all issues.")
@click.option("--updated-since", type=str, default=None,
              help="Only issues that have been updated since [ARG] - could be a date or an offset (like -1d or -3h, etc.)")
@click.option('--issue-offset', type=int, default=0,
              help="Sets the offset for pulling issues")
@click.option('--max-issues', type=int, default=100,
              help="Sets the max number of issues to pull")
def list_cmd(assignee, project, jql, closed, len_, output, matching_eq,
             matching_neq, matching_contains, matching_not,
             matching_in, matching_gt, matching_lt, matching_ge, matching_le,
             mentions, updated_since,
             issue_offset, max_issues) -> None:
    jobj = connector.JiraConnector()
    jobj.login()

    if jql is not None:
        issues_query = jql
    else:
        qd = {}
        for matches in [(matching_eq, "="), (matching_neq, "!="),
                        (matching_contains, "~"),
                        (matching_not, "is not"),
                        (matching_in, "in"), (matching_gt, ">"),
                        (matching_lt, "<"), (matching_ge, ">="),
                        (matching_le, "<=")]:
            for f, v in matches[0]:
                qd[f] = (matches[1], v)

        if assignee == "-":
            assignee = None
        if mentions:
            # Mentions is special case, so we will fill up the query
            # to check for comments that contain our user info.
            assignee = None
            qd["comment"] = ("~", "currentUser()")
        if updated_since:
            qd["updatedDate"] = (">=", updated_since)

        issues_query = jobj.build_issues_query(assignee, project, closed,
                                               fields_dict=qd)

    issues = jobj._query_issues(issues_query, issue_offset, max_issues)
    ISSUE_HEADER = []

    if len(issues) != 0:
        issue_list = []
        summary_pos = None

        for header in ISSUE_DETAILS_MAP:
            if header not in ISSUE_HEADER:
                ISSUE_HEADER.append(header)

        if "summary" in ISSUE_HEADER:
            summary_pos = ISSUE_HEADER.index("summary")

        for issue in issues:
            issue_details = issue_eval(issue, ISSUE_DETAILS_MAP)
            if summary_pos is not None:
                issue_details[summary_pos] = trim_text(
                    issue_details[summary_pos], len_
                )
            issue_list.append(issue_details)

        if output == 'table':
            final = tabulate(issue_list, ISSUE_HEADER, 'psql')
        elif output == 'simple':
            final = tabulate(issue_list, ISSUE_HEADER, 'simple')
        elif output == 'csv':
            final = ",".join(ISSUE_HEADER) + "\n"
            for line in issue_list:
                final += ",".join(line) + "\n"

        click.echo(final)


@click.command(
    name='show'
)
@click.argument('issuekey')
@click.option("--raw", is_flag=True, default=False,
              help="Dump the issue details in 'raw' form.")
@click.option("--width", type=int, default=0,
              help="Use a set width for display.  Default of '0' will set the display based on the terminal width.")
def show_cmd(issuekey, raw, width):
    jobj = connector.JiraConnector()
    jobj.login()

    issue = jobj.get_issue(issuekey)

    if issue is None:
        click.echo(f"Unable to find issue: {issuekey}")
        return

    if raw is True:
        click.echo(pprint.pprint(vars(issue)))
        click.echo(jobj._fetch_custom_fields())
        return

    # Get terminal width and adjust max width
    if width == 0:
        width = shutil.get_terminal_size().columns - 2
    max_width = max(width, 79)

    issue_details = issue_eval(issue, ISSUE_DETAILS_MAP)
    if issue_details is None:
        click.echo(f"Error with {issuekey}")
        return

    output = "+" + '-' * (max_width - 2) + "+\n"
    pname = jobj.get_field(issue, 'project', 'name')
    aname = jobj.get_field(issue, 'assignee', 'name')

    output += f"| {issue.key:<10} | {pname:<20} | {aname:<39} |\n"
    output += "+" + '-' * (max_width - 2) + "+\n"
    prio = jobj.get_field(issue, 'priority', 'name')
    status = jobj.get_field(issue, 'status', 'name')

    summ = jobj.get_field(issue, 'summary')

    output += f"| priority: {prio:<20} | status: {status:<34} |\n"
    output += "+" + '-' * (max_width - 2) + "+\n"
    output += f"| URL: {jobj.issue_url(issuekey):<{max_width - 9}} |\n"
    output += "+" + '-' * (max_width - 2) + "+\n"
    output += f"| summary: {' ' * (max_width - 13)} |\n"
    output += f"| ------- {' ' * (max_width - 12)} |\n"

    for issue_field in jobj.requested_fields():
        output += f"| {issue_field:<25}: {jobj.get_field(issue, issue_field):<{max_width - 31}} |\n"

    if len(summ) <= max_width - 4:
        output += f"| {summ:<{max_width - 4}} |\n"
    else:
        while len(summ) > 0:
            output += f"| {summ[:max_width - 4]:<{max_width - 4}} |\n"
            summ = summ[max_width - 4:]
    output += "+" + '-' * (max_width - 2) + "+\n\n"

    descr = jobj.get_field(issue, 'description')
    if len(descr) > 0:
        output += f"| Description: {' ' * (max_width - 17)} |\n"
        output += f"|{'-' * (max_width - 2)}|\n"
        output += fitted_blocks(descr, max_width - 4, "|")

    output += f"+ Comments: {' ' * (max_width - 14)} |\n"
    for comment in issue.fields.comment.comments:
        output += f"| Author: {comment.author.displayName:<36} | {comment.created:<20} |\n"
        output += f"|{'-' * (max_width - 2)}|\n"
        output += fitted_blocks(comment.body, max_width - 4, "|")
        output += "+" + '-' * (max_width - 2) + "+\n"

    display_via_pager(output)


@click.command(
    name="add-comment"
)
@click.argument('issuekey')
@click.option("--comment", type=str, default=None,
              help="The comment text to add.  Defaults to opening an editor.")
def add_comment_cmd(issuekey, comment):
    jobj = connector.JiraConnector()
    jobj.login()

    if comment is None:
        comment = get_text_via_editor()

    if comment is None or len(comment) == 0 or comment.isspace():
        click.echo("Error: No comment provided.")
        sys.exit(1)

    jobj.add_comment(issuekey, comment)


@click.command(
    name="states"
)
@click.argument('issuekey')
def states_cmd(issuekey):
    jobj = connector.JiraConnector()
    jobj.login()

    states = jobj.get_states_for_issue(issuekey)

    click.echo(states)


@click.command(
    name="set-status"
)
@click.argument("issuekey")
@click.argument("status")
def set_state_cmd(issuekey, status):
    jobj = connector.JiraConnector()
    jobj.login()

    jobj.set_state_for_issue(issuekey, status)
    click.echo("done.")


@click.command(
    name="set-field"
)
@click.argument('issuekey')
@click.argument('fieldname')
@click.argument('fieldvalue')
def set_field_cmd(issuekey, fieldname, fieldvalue):
    jobj = connector.JiraConnector()
    jobj.login()

    issue = jobj.get_issue(issuekey)

    if issue is None:
        click.echo(f"Error: {issuekey} not found.")
        sys.exit(1)

    old = jobj.get_field(issue, fieldname)

    jobj.set_field(issue, fieldname, fieldvalue)

    new = jobj.get_field(issue, fieldname)

    click.echo(f"Updated {issuekey}, set {fieldname}: {old} -> {new}")

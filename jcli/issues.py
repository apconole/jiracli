import click
import logging
import os
import pprint

from jcli import connector
from jcli.utils import trim_text
from jcli.utils import issue_eval
from jcli.utils import SEP_STR
from jcli.utils import display_via_pager
from jcli.utils import get_text_via_editor
from tabulate import tabulate

LOG = logging.getLogger(__name__)

ISSUE_DETAILS_MAP = {
    "key": "key",
    "project": "raw['fields']['project']['name']",
    "priority": "raw['fields']['priority']['name']",
    "summary": "raw['fields']['summary']",
    "assignee": "raw['fields']['assignee']['name']",
}

@click.command(
    name='list'
)
@click.option('--assignee', type=str, default=None,
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
def list_cmd(assignee, project, jql, closed, len_, output) -> None:
    jobj = connector.JiraConnector()
    jobj.login()

    if jql is not None:
        issues_query = jql
    else:
        issues_query = jobj.build_issues_query(assignee, project, closed)

    issues = jobj._query_issues(issues_query)
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
            if summary_pos != None:
                issue_details[summary_pos] = trim_text(
                    issue_details[summary_pos], len_
                )
            issue_list.append(issue_details)

        if output == 'table':
            final = tabulate(issue_list, ISSUE_HEADER, 'psql')
        elif output == 'simple':
            final = tabulate(issue_list, ISSUE_HEADER, 'simple')

        click.echo(final)

@click.command(
    name='show'
)
@click.argument('issuekey')
@click.option("--raw", is_flag=True, default=False,
              help="Dump the issue details in 'raw' form.")
def show_cmd(issuekey, raw):
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

    issue_details = issue_eval(issue, ISSUE_DETAILS_MAP)
    if issue_details is None:
        click.echo(f"Error with {issuekey}")
        return

    output = SEP_STR + "\n"
    pname = jobj.get_field(issue, 'project', 'name')
    aname = jobj.get_field(issue, 'project', 'name')

    output += f"| {issue.key:<10} | {pname:<20} | {aname:<39} |\n"
    output += SEP_STR + "\n"
    prio = jobj.get_field(issue, 'priority', 'name')
    status = jobj.get_field(issue, 'status', 'name')

    summ = jobj.get_field(issue, 'summary')

    output += f"| priority: {prio:<20} | status: {status:<34} |\n"
    output += SEP_STR + "\n"
    output += f"| URL: {jobj.issue_url(issuekey):<70} |\n"
    output += SEP_STR + "\n"
    output += f"| summary: {' ' * 66} |\n"
    output += f"| ------- {' ' * 67} |\n"

    for issue_field in jobj.requested_fields():
        output += f"| {issue_field:<25}: {jobj.get_field(issue, issue_field):<48} |\n"

    if len(summ) <= 75:
        output += f"| {summ:<75} |\n"
    else:
        while len(summ) > 0:
            output += f"| {summ[:75]:<75} |\n"
            summ = summ[75:]
    output += SEP_STR + "\n\n"

    output += f"> Comments: {' ' * 65} |\n"
    for comment in issue.fields.comment.comments:
        output += f"| Author: {comment.author.displayName:<36} | {comment.created:<20} |\n"
        output += f"|{'-' * 77}|\n"
        body = comment.body.replace('\n', ' ')

        while len(body) > 0:
            output += f"| {body[:75]:<75} |\n"
            body = body[75:]
        output += SEP_STR + "\n"

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

    if comment is None or len(comment) == 0:
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

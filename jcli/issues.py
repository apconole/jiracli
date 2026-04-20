import click
import csv
import json as JSON
import logging
import os
import pprint
import re
import shutil
import sys
import yaml

from click.core import ParameterSource
from jcli import connector
from jcli.utils import display_via_pager
from jcli.utils import fitted_blocks
from jcli.utils import get_text_via_editor
from jcli.utils import git_get_commit_oneline
from jcli.utils import git_get_commit_formatted
from jcli.utils import issue_eval
from jcli.utils import str_containing
from jcli.utils import str_contained
from jcli.utils import trim_text
from jcli.utils import RuntimeEvalChoice
from tabulate import tabulate

reporting_choices = ['table', 'csv', 'simple', 'json',
                     'report']

try:
    import jinja2

    reporting_choices.append('template')

    def template_output(tpl_file, issues, connector):
        tmpl = None
        with open(tpl_file, "r") as f:
            tmpl = jinja2.Template(f.read())

        return tmpl.render(issues=issues, client=connector) if tmpl else ""

except:
    def template_output(tpl_file, issues, connector):
        return f"Module import error: jinja2 - not processing {tpl_file}"


LOG = logging.getLogger(__name__)

ISSUE_DETAILS_MAP = {
    "key": "key",
    "project": "raw['fields']['project']['name']",
    "priority": "raw['fields']['priority']['name']",
    "summary": "raw['fields']['summary']",
    "status": "raw['fields']['status']['name']",
    "assignee": "raw['fields']['assignee']['displayName']",
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
@click.option('--output', type=click.Choice(reporting_choices),
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
@click.option('--sort',
              type=click.Choice(["prio-asc", "prio-desc",
                                 "type-asc", "type-desc",
                                 "created-asc", "created-desc",
                                 "duedate-asc", "duedate-desc",
                                 "status-asc", "status-desc",
                                 "project-asc", "project-desc",
                                 "none"],
                                case_sensitive=False),
              default="none", help="Sort the output")
@click.option('--template-file',
              type=click.Path(),
              default=os.path.join(os.path.expanduser("~"), "template.jcli"),
              help="Use the jinja2 engine to write out the list of issues.")
def list_cmd(assignee, project, jql, closed, len_, output, matching_eq,
             matching_neq, matching_contains, matching_not,
             matching_in, matching_gt, matching_lt, matching_ge, matching_le,
             mentions, updated_since,
             issue_offset, max_issues, sort, template_file) -> None:
    """Runs a query against the JIRA server, and displays a list of issues.
    """
    jobj = connector.JiraConnector()

    if output == 'template' and not os.path.isfile(template_file):
        raise click.UsageError(f"Invalid template file {template_file}.")

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

        if sort != "none":
            qd["ORDER BY"] = jobj.order_by_from_string(sort)

        issues_query = jobj.build_issues_query(assignee, project, closed,
                                               fields_dict=qd)

    issues = jobj._query_issues(issues_query, issue_offset, max_issues)
    final = format_issue_output(jobj, issues, output, len_, sort, template_file)
    click.echo(final)


def format_issue_output(jobj, issues, output, len_, sort=None, template_file=None):
    """Format a list of issues for display.

    Args:
        jobj: JiraConnector instance (logged in)
        issues: list of JIRA issue objects
        output: output format string (table, simple, csv, json, report, template)
        len_: summary trim length (0 for no trim)
        sort: sort string (unused here, kept for interface consistency)
        template_file: path to jinja2 template file

    Returns:
        str: formatted output
    """
    ISSUE_HEADER = []
    final = ""

    if len(issues) != 0 and output in ("table", "simple", "csv"):
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

    elif output == "json":
        final = f'{{"issues_count":{len(issues)},\n'
        final += f'"issues":[{",".join([JSON.dumps(issue.raw) for issue in issues])}],\n'
        final += f'"field_maps":{JSON.dumps(jobj._fetch_custom_fields())}\n'
        final += "}"

    elif output == 'report':
        report_lists = jobj.report_filters()

        final = ""

        sorted_issues = jobj.report_sort_issue_list(issues)

        for li in report_lists:
            remove_ids = []
            listed_issues = jobj.report_filter_issues(li, issues)
            final += f"{li} issues:\n====================\n"
            for issue in listed_issues:
                final += f" * {issue.key:<15} {trim_text(jobj.get_field(issue, 'summary'), len_)}\n"
                remove_ids.append(issue.key)

            sorted_issues = [filt_issue for filt_issue in sorted_issues
                             if filt_issue.key not in remove_ids]
            final += "\n"

        final += "Non-filtered Issues:\n====================\n"
        for issue in sorted_issues:
            final += f" * {issue.key:<15} {trim_text(jobj.get_field(issue, 'summary'), len_)}\n"

    elif output == 'template':
        final = template_output(template_file, issues, jobj)

    return final


@click.command(
    name='show'
)
@click.argument('issuekey')
@click.option("--raw", is_flag=True, default=False,
              help="Dump the issue details in 'raw' form.")
@click.option("--width", type=int, default=0,
              help="Use a set width for display.  Default of '0' will set the display based on the terminal width.")
@click.option("--json", is_flag=True, default=False,
              help="Dump the issue details in json compatible form.")
def show_cmd(issuekey, raw, width, json):
    """Displays a JIRA issue, or dumps the raw issue details.

    The 'show' command will auto-discover the terminal width when displaying,
    unless the WIDTH parameter is set.

    If you want to get the issue information for raw processing, it comes as
    a pythonic-like dictionary, followed by a pythonic-like list of tuples
    mapping field names and the customfield IDs.

    To use the issue information in a more compatible way, the RAW, JSON details
    will create a json list, with the first element being the json
    representation of the JIRA issue, followed by a json map between fields
    and customfield names.
    """
    jobj = connector.JiraConnector()
    jobj.login()

    issue = jobj.get_issue(issuekey)

    if issue is None:
        click.echo(f"Unable to find issue: {issuekey}")
        return

    if raw is True:
        if not json:
            click.echo(pprint.pprint(vars(issue)))
            click.echo(jobj._fetch_custom_fields())
        else:
            click.echo('[')
            click.echo(JSON.dumps(issue.raw))
            click.echo(',')
            click.echo(JSON.dumps(jobj._fetch_custom_fields()))
            click.echo(']')
        return
    elif json is True:
        click.echo("Cannot use 'json' without 'raw'")
        return

    # Get terminal width and adjust max width
    if width == 0:
        width = shutil.get_terminal_size().columns - 2
    max_width = max(width, 79)

    issue_details = issue_eval(issue, ISSUE_DETAILS_MAP)
    if issue_details is None:
        click.echo(f"Error with {issuekey}")
        return

    excluded = jobj.excluded_fields()

    output = "+" + '-' * (max_width - 2) + "+\n"
    pname = jobj.get_field_rendered(issue, 'project', 'name')
    aname = jobj.get_field_rendered(issue, 'assignee', 'displayName')
    a_internal_name = jobj.get_field_rendered(issue, 'assignee', 'name')
    if a_internal_name and len(a_internal_name.strip()):
        aname += f" [~{a_internal_name:<18}]"
    else:
        aeml = jobj.get_field_rendered(issue, 'assignee', 'emailAddress')
        if aeml and len(aeml.strip()):
            aname += f" [~{aeml:<18}] "

    output += f"| {issue.key:<10} | {pname:<20} | {aname:<39} |\n"
    output += "+" + '-' * (max_width - 2) + "+\n"
    prio = jobj.get_field_rendered(issue, 'priority', 'name')
    status = jobj.get_field_rendered(issue, 'status', 'name')

    summ = jobj.get_field_rendered(issue, 'summary')

    reporter = jobj.get_field_rendered(issue, 'reporter', 'displayName')
    rname = jobj.get_field_rendered(issue, 'reporter', 'name')
    if rname and len(rname.strip()):
        reporter += f" [~{rname:<18}]"
    else:
        reml = jobj.get_field_rendered(issue, 'reporter', 'emailAddress')
        if reml and len(reml.strip()):
            reporter += f" [~{reml:<18}] "

    output += f"| priority: {prio:<20} | status: {status:<34} |\n"
    output += "+" + '-' * (max_width - 2) + "+\n"
    output += f"| Reporter: {reporter:<{max_width - 14}} |\n"
    output += "+" + '-' * (max_width - 2) + "+\n"

    if 'url' not in excluded:
        output += f"| URL: {jobj.issue_url(issuekey):<{max_width - 9}} |\n"
        output += "+" + '-' * (max_width - 2) + "+\n"

    if 'summary' not in excluded:
        output += f"| summary: {' ' * (max_width - 13)} |\n"
        output += f"| ------- {' ' * (max_width - 12)} |\n"

    for issue_field in jobj.requested_fields():
        output += f"| {issue_field:<25}: {jobj.get_field_rendered(issue, issue_field):<{max_width - 31}} |\n"

    if len(summ) <= max_width - 4:
        output += f"| {summ:<{max_width - 4}} |\n"
    else:
        while len(summ) > 0:
            output += f"| {summ[:max_width - 4]:<{max_width - 4}} |\n"
            summ = summ[max_width - 4:]
    output += "+" + '-' * (max_width - 2) + "+\n\n"

    if 'eausm' not in excluded and 'eausm' in issue.raw['fields']:
        output += "+" + '-' * (max_width - 2) + "+\n"
        output += f"| EZ Agile: {' ' * (max_width - 14)} |\n"

        if 'votes' in issue.raw['fields']['eausm']:
            total = 0
            if not len(issue.raw['fields']['eausm']['votes']):
                output += f"| No Votes{' ' * (max_width - 12)} |\n"
            for vote in issue.raw['fields']['eausm']['votes']:
                total += int(vote['vote'])
                user = jobj.find_users_by_name(vote['userId'])
                if len(user):
                    user = user[0].displayName
                else:
                    user = f"[{vote['userId']}]?"
                output += f"| Vote: {vote['vote']} by {user} {' ' * (max_width - (15 + len(user) + len(str(vote['vote']))))} |\n"
            output += "|" + '-' * (max_width - 2) + "|\n"
            output += f"| Total: {str(total)} {' ' * (max_width - (len(str(total)) + 12))} |\n"
        else:
            output += f"| No votes. {' ' * (max_width - 14)} |\n"

        output += "+" + '-' * (max_width - 2) + "+\n\n"

    if 'links' not in excluded and issue.fields.issuelinks is not None and \
       len(issue.fields.issuelinks) > 0:
        output += f"| Links: {' ' * (max_width - 11)} |\n"
        output += f"|{'-' * (max_width - 2)}|\n"
        for link in issue.fields.issuelinks:
            link_text = ""
            if hasattr(link, "outwardIssue"):
                link_text = f"| - Linked To Issue: {link.outwardIssue}"
            if hasattr(link, "inwardIssue"):
                link_text = f"| - Linked From Issue: {link.inwardIssue}"
            if hasattr(link, "type") and hasattr(link.type, "name"):
                link_text += f", Relationship: {link.type.name}"
            if len(link_text):
                output += link_text + ' ' * (max_width - (len(link_text) + 1))
                output += "|\n"

        jobj._ratelimit()
        remote_links = jobj.jira.remote_links(issue.key)
        for link_id in remote_links:
            jobj._ratelimit()
            link = jobj.jira.remote_link(issuekey, link_id)
            if hasattr(link, "object"):
                url = ""
                title = ""
                if hasattr(link.object, "url"):
                    url = link.object.url
                if hasattr(link.object, "title"):
                    title = link.object.title
                    url = f"[{title}|{url}]"
                link_text = f"| - Remote: {url}"
                output += link_text + ' ' * (max_width - (len(link_text) + 1))
                output += "|\n"
        output += "\n"

    if 'attachments' not in excluded and issue.fields.attachment is not None \
       and len(issue.fields.attachment) > 0:
        output += f"| Attachments: {' ' * (max_width - 17)} |\n"
        output += f"|{'-' * (max_width - 2)}|\n"
        attach_display = []
        for attachment in issue.fields.attachment:
            attach = (attachment.filename, attachment.created, attachment.size,
                      attachment.author.displayName)
            attach_display.append(attach)
        final = tabulate(attach_display, ('File', 'Created', 'Size', 'Creator'),
                         'psql')
        output += final + "\n\n"

    descr = jobj.jira_text_field_to_md(jobj.get_field_rendered(issue,
                                                               'description'))
    if 'description' not in excluded and len(descr) > 0:
        output += f"| Description: {' ' * (max_width - 17)} |\n"
        output += f"|{'-' * (max_width - 2)}|\n"
        output += fitted_blocks(descr, max_width - 4, "|")

    comments_block = f"+ Comments: {' ' * (max_width - 14)} |\n"
    for comment in issue.fields.comment.comments:
        if max_width < 80:
            comments_block += f"| Author: {comment.author.displayName:<14} "
            if 'name' in comment.author.raw:
                comments_block += f"[~{comment.author.name:<18}] "
            elif 'emailAddress' in comment.author.raw:
                comments_block += f"[~{comment.author.emailAddress:<18}] "
            comments_block += f"| {comment.created:<20} |\n"
        else:
            v = "all"
            try:
                v = f"{comment.visibility.value}"
            except:
                pass
            visibility = f"{v:<20} | "
            add_ln = f"| Author: {comment.author.displayName:<20} "
            if 'name' in comment.author.raw:
                add_ln += f"[~{comment.author.name:<20}] "
            elif 'emailAddress' in comment.author.raw:
                add_ln += f"[~{comment.author.emailAddress:<20}] "
            add_ln += f"| {comment.id:<18} | {visibility}{comment.created:<20}"
            if len(add_ln) > max_width:
                add_ln += "\n"
            else:
                diff = max_width - (len(add_ln) + 1)
                add_ln += " " * diff
                add_ln += "|\n"
            comments_block += add_ln
        comments_block += f"|{'-' * (max_width - 2)}|\n"
        comments_block += fitted_blocks(jobj.jira_text_field_to_md(comment.body),
                                        max_width - 4, "|")
        comments_block += "+" + '-' * (max_width - 2) + "+\n"

    if 'comments' not in excluded:
        output += comments_block

    display_via_pager(output, f"Issue: {issuekey}")


class IntegerOrStr(click.ParamType):
    name = "integer or 'last'"

    def __init__(self, valid_words):
        self.valid_words = valid_words

    def convert(self, value, param, ctx):
        if isinstance(value, str):
            if value.lower() in self.valid_words:
                return value.lower()
            else:
                return int(value)
        elif isinstance(value, int):
            return value

        self.fail(f"{value!r} should be an integer or {self.valid_words!r}")


IN_REPLY_TO = IntegerOrStr(['last'])


@click.command(
    name="add-comment"
)
@click.argument('issuekey')
@click.option("--comment", type=str, default=None,
              help="The comment text to add.  Defaults to opening an editor.")
@click.option("--visibility", type=str, default='all',
              help="Sets the group / role for visibility.  Defaults to 'all'.")
@click.option("--in-reply-to", type=IN_REPLY_TO, default=None,
              help="Includes a quoted reply from an existing comment.")
def add_comment_cmd(issuekey, comment, visibility, in_reply_to):
    """Adds a new comment to a JIRA issue.

    To reply to the most recent comment, simply pass the word 'last' as the
    IN_REPLY_TO argument.
    """
    jobj = connector.JiraConnector()
    jobj.login()

    if comment is not None and in_reply_to is not None:
        click.echo("Error: Cannot reply with defaulted text.")
        sys.exit(1)

    comment_body = None
    if in_reply_to:
        comment_ref = jobj.get_comment(issuekey, in_reply_to)
        if comment_ref:
            comment_body = jobj.in_reply_to_start(comment_ref)
            for line in comment_ref.body.split('\n'):
                comment_body += "> " + line.strip() + "\n"

            if click.get_current_context().get_parameter_source('visibility') \
               == ParameterSource.DEFAULT and 'visibility' in comment_ref.raw:
                visibility = comment_ref.visibility.value

    if comment is None:
        comment = get_text_via_editor(comment_body)

    if comment is None or len(comment) == 0 or comment.isspace() or \
       (comment_body and comment == comment_body):
        click.echo("Error: No comment provided.")
        sys.exit(1)

    comment = jobj.md_text_to_jira_text_field(comment)
    jobj.add_comment(issuekey, comment, visibility)


@click.command(
    name="del-comment"
)
@click.argument('issuekey')
@click.argument('comment_id')
def del_comment_cmd(issuekey, comment_id):
    """Deletes a comment from an issue."""
    jobj = connector.JiraConnector()
    jobj.login()

    issue = jobj.get_issue(issuekey)
    if issue is None:
        click.echo(f"Issue {issuekey} not found.")
        return

    comment = jobj.get_comment(issue.raw['key'], comment_id)
    if comment is not None:
        comment.delete()
        click.echo(f"Comment {comment_id} deleted.")
    else:
        click.echo(f"Comment {comment_id} for issue {issuekey} not found.")


@click.command('update-comment')
@click.argument('issuekey')
@click.argument('comment_id')
@click.option("--body", type=str, default=None,
              help="Set new body to the argument.")
@click.option('--visibility', type=str, default=None,
              help="Sets the group / role for visibility.  Use 'all' for no restriction.")
def update_comment_cmd(issuekey, comment_id, body, visibility):
    """Adjust a comment by modifying the body or visibility.

    If the BODY parameter is passed, it will become the new body.  Otherwise,
    an interactive EDITOR will spawn to allow adjusting the body if desired.
    """
    jobj = connector.JiraConnector()
    jobj.login()

    issue = jobj.get_issue(issuekey)
    if issue is None:
        click.echo(f"Issue {issuekey} not found.")
        return

    comment = jobj.get_comment(issue.raw['key'], comment_id)
    if comment is None:
        click.echo(f"Comment {comment_id} for issue {issuekey} not found.")

    update = {}
    body_text = None
    if body is None:
        ctext = jobj.jira_text_field_to_md(comment.body)
        body_text = get_text_via_editor(ctext)
    elif body != "":
        body_text = body

    if body_text:
        update['body'] = jobj.md_text_to_jira_text_field(body_text)

    if visibility is not None:
        if visibility.lower() == 'all':
            update['visibility'] = {'identifier': None}
        else:
            update['visibility'] = {'type': 'group', 'value': visibility}

    if len(update) == 0:
        click.echo("No Changes.")
        return

    comment.update(**update)
    click.echo(f"Comment {comment_id} updated.")


@click.command(
    name="states"
)
@click.argument('issuekey')
def states_cmd(issuekey):
    """List the available state transitions for an issue."""
    jobj = connector.JiraConnector()
    jobj.login()

    states = jobj.get_states_for_issue(issuekey)

    click.echo(states)


@click.command(
    name="set-status"
)
@click.argument("issuekey")
@click.argument("status")
@click.option("--resolution", type=str, default=None,
              help="Set the resolution when transitioning "
              "(e.g. 'Done', 'Won\\'t Fix').")
def set_state_cmd(issuekey, status, resolution):
    """Set an issue's current state.

    States are per-project in JIRA.  You can use the 'states' command to
    discover what the available transitions for a given issue are.
    """
    jobj = connector.JiraConnector()
    jobj.login()

    jobj.set_state_for_issue(issuekey, status, resolution=resolution)
    click.echo("done.")


@click.command(
    name="add-watcher"
)
@click.argument('issuekey')
@click.argument('watcher')
def add_watcher_cmd(issuekey, watcher):
    """Adds a JIRA account as a watcher for an issue."""
    jobj = connector.JiraConnector()
    jobj.login()

    jobj.add_watcher(issuekey, watcher)
    click.echo('done.')


@click.command(
    name="del-watcher"
)
@click.argument('issuekey')
@click.argument('watcher')
def del_watcher_cmd(issuekey, watcher):
    """Removes a watcher from an issue."""
    jobj = connector.JiraConnector()
    jobj.login()

    jobj.del_watcher(issuekey, watcher)
    click.echo('done.')


@click.command(
    name="get-field"
)
@click.argument('issuekey')
@click.argument('fieldname')
@click.option("--allowed", is_flag=True, default=False,
              help="Also displays the allowed values.")
def get_field_cmd(issuekey, fieldname, allowed):
    """Get a field value from a JIRA issue.

    NOTE: In JIRA, field names are case sensitive, so double check that
          you are specifying the correct field name."""

    jobj = connector.JiraConnector()
    jobj.login()
    issue = jobj.get_issue(issuekey)
    field = jobj.get_field(issue, fieldname)
    click.echo(f"{fieldname}: {field}")
    if allowed:
        allowed_vals_str = jobj.get_field_allowed(issue, fieldname)
        if allowed_vals_str:
            for line in allowed_vals_str:
                click.echo(line)
        else:
            click.echo("- No allowed values found.")


@click.command(
    name="set-field"
)
@click.argument('issuekey')
@click.argument('fieldname')
@click.argument('fieldvalue')
@click.option("--forced", is_flag=True, default=False,
              help="Force the value to be run through python eval and used as-is.")
def set_field_cmd(issuekey, fieldname, fieldvalue, forced):
    """Sets a field in an issue to a specific value.

    JIRA field types are not always properly communicated in the field type
    schema, so the '--forced' option can be used to ensure that the type is
    set correctly.

    NOTE: In JIRA, field names are case sensitive, so double check that
          you are specifying the correct field name.  If the field is not
          correct, you may see blank output."""
    jobj = connector.JiraConnector()
    jobj.login()

    issue = jobj.get_issue(issuekey)

    if issue is None:
        click.echo(f"Error: {issuekey} not found.")
        sys.exit(1)

    old = jobj.get_field(issue, fieldname)

    jobj.set_field(issue, fieldname, fieldvalue, forced)

    new = jobj.get_field(issue, fieldname)

    click.echo(f"Updated {issuekey}, set {fieldname}: {old} -> {new}")


@click.command(
    name="set-field-from-csv"
)
@click.argument('csvfile', type=click.Path(exists=True))
def set_field_from_csv_cmd(csvfile):
    """Bulk field setting for fields and issues.

    Expects a CSV formed as:
      issue1,field,value[,field2,value2,...]
      issue2,field,value

    Currently, there isn't a specifier for 'forcing' a field type.
    """
    jobj = connector.JiraConnector()
    jobj.login()

    with open(csvfile, mode='r', newline='') as file:
        reader = csv.reader(file)
        # we assume no header is set, if one is set we can ignore it with:
        # next(reader, None)

        for row in reader:
            if len(row) < 3:
                click.echo(f"Skipping invalid row: {row}")
                continue

            issuekey = row[0]
            fvp = row[1:]

            issue = jobj.get_issue(issuekey)

            if issue is None:
                click.echo(f"Error: {issuekey} not found - skipping row.")
                continue

            # iterate through fieldname, fieldvalue pairs in the remaining elements of the row
            for i in range(0, len(fvp), 2):
                fieldname = fvp[i]
                fieldvalue = fvp[i + 1]

                old = jobj.get_field(issue, fieldname)
                jobj.set_field(issue, fieldname, fieldvalue)
                new = jobj.get_field(issue, fieldname)
                click.echo(f"Updated {issuekey}, set {fieldname}: {old} -> {new}")


def issue_extract_blocks(issue_block):
    parse_as_git = False

    # Split the text into blocks separated by blank lines
    if issue_block.startswith("From ") and "\n---\n" in issue_block:
        parse_as_git = True

    lines = issue_block.split('\n')

    # Initialize variables to store summary, description, and comments, and
    # track the git sections
    summary = ''
    description = ''
    comments = []
    git_state = 0

    # Flag to indicate whether we are currently parsing the summary or description
    parsing_summary = True

    # Iterate over each line
    for line in lines:
        tabbed = True if line.startswith("\t") else False

        line = line.strip()

        # Skip empty lines
        # Check if we move on to description
        if not line.strip() and parsing_summary:
            parsing_summary = False
            continue

        # If git parsing - check for the subject line, and handle
        # overcontinuation
        if parse_as_git:
            if git_state == 0:
                if line.startswith("Subject:"):
                    pos = line.find("]")
                    line = line[pos + 1:]
                    git_state = 1
                    summary += line
                # ignore lines until 'Subject'
                continue

            if git_state == 1:
                if not parsing_summary:
                    # we move the git-state along
                    # but let it process as normal through the rest of the
                    # machine.
                    git_state = 2
                else:
                    if not tabbed:
                        continue

                    summary += " " + line.lstrip()
                    # this needs to be here to skip double add later
                    # due to the git detection code being here.
                    continue

            # detect the cutline, and switch to flag the 'diff' as the final
            # parse
            if git_state == 2 and line == "---":
                git_state = 3
                continue

            if git_state == 3:
                if line.startswith("diff --git") or \
                   str_containing(line, ["|", "changed", "created mode"]):
                    break

        # accumulate comments
        if line.startswith('#'):
            comments.append(line)
            continue

        if parsing_summary:
            summary += line
        else:
            description += line + '\n'

    summary = summary.strip()
    description = description.strip()
    return summary, description, comments


@click.command(
    name='create'
)
@click.pass_context
@click.option("--summary", type=str, default=None,
              help="The summary for the issue.  Default is to use the text editor interpretation.")
@click.option("--description", type=str, default=None,
              help="Description of the issue.  Default is to use the text editor interpretation.")
@click.option("--project", type=str, default=None,
              help="The project to open.  Default is to use the text editor interpretation.")
@click.option("--issue-type",
              type=click.Choice(["Epic", "Bug", "Story", "Task", "Subtask"],
                                case_sensitive=False),
              default='bug',
              help="Specific issue type.  Defaults to 'bug'.")
@click.option("--set-field", multiple=True, nargs=2,
              help="Sets a specific field.", default=None)
@click.option("--from-file", type=click.Path(exists=True),
              help="Uses a file (like a git patchfile).", default=None)
@click.option("--commit", multiple=True, type=str, default=None,
              help="Create an issue that will reference multiple commits.")
@click.option("--oneline", is_flag=True, default=False,
              help="When specifying a single commit, force the one-line version.")
@click.option("--verbose", is_flag=True, default=False,
              help="Will print the issue details being added.  Ignored with '--dry-run'.")
@click.option("--show-fields", is_flag=True, default=False,
              help="Will include the fields that can be set for the project and"
              " issue type.  Must specify valid values for both on the command line.")
@click.option("--dry-run", is_flag=True, default=False,
              help="Do not actually commit the issue.")
@click.option("--json", is_flag=True, default=False,
              help="Output the created issue in JSON format.")
def create_issue_cmd(ctx, summary, description, project, issue_type, set_field,
                     from_file, commit, oneline, verbose, show_fields, dry_run,
                     json):
    """Creates a new JIRA issue.

    Supports creating a JIRA issue from the command line, using a 'git' like
    interface.  The issue details can be provided by an existing file, or via
    a PATCH file, or from a git commit.  Additionally, various JIRA fields
    can be set during the creation.

    The DRY-RUN flag will not actually push the JIRA issue to the server.  It
    doesn't save the issue details anywhere, so it is important to keep a copy
    for resubmitting if you don't want to re-write the issue details again.
    """
    if 'jobj' not in ctx.obj:
        jobj = connector.JiraConnector()
        jobj.login()
        ctx.obj['jobj'] = jobj
    else:
        jobj = ctx.obj['jobj']

    filled_all = all((summary, description, project))
    special_lines = None
    fields = {}
    set_field = set_field or []

    if verbose and json:
        click.echo("INVALID - cannot set both verbose and json flags.")
        sys.exit(1)

    if commit:
        if len(commit) == 1 and not oneline:
            # treat this as a from-file with a specific commit.
            as_email = git_get_commit_formatted(commit[0])
            summary, description, comments = issue_extract_blocks(as_email)
        else:
            description = "# The following commits will be referenced in the ticket:\n"
            for sha in commit:
                commit_line = git_get_commit_oneline(sha)
                if not commit_line or not len(commit_line):
                    if not json:
                        click.echo(f"ERROR: Unable to find {sha}")
                        click.echo(
                            "Please make sure you are in a git tree, or "
                            "GIT_DIR is defined.")
                    else:
                        click.echo(JSON.dumps({"success": False,
                                               "issue_id": None,
                                               "error":
                                               f"Unable to find sha {sha}"}))
                    sys.exit(1)
                commit_lines = commit_line.split("\n")
                for commit_line in commit_lines:
                    if len(commit_line):
                        description += f"   {commit_line}\n"

    if from_file:
        with open(from_file, "r") as f:
            # We want to ensure that we always let the user edit the final
            # issue text before submitting it.
            filled_all = False

            summary, description, comments = issue_extract_blocks(f.read())
            if str_contained("# set-project: ", comments):
                special_lines = "\n".join(comments)
                for c in comments:
                    if c.startswith("# set-project: ") and not project:
                        project = c[15:]
    else:
        summary = summary or "# The first line in this will be treated as the summary."
        description = description or (
            "# Add your description here.  By default, all lines\n"
            "# starting with a '#' are used to denote special lines")

    project = project or jobj.get_default_str('project', "Default Project")

    if not special_lines:
        special_lines = (f"# set-project: {project}\n"
                         f"# issue-type: {issue_type}\n"
                         "# NOTE: you can use a line '# set-field: \"foo\" bar' to set field 'foo'\n"
                         "#       to value 'bar'.  The 'set-field' directive requires\n"
                         "#       field to be quoted as \"Some Foo\".")

    if project != "Default Project" and show_fields:
        # Try to pull the default fields for project and bug type
        special_lines += "\n# Assignable fields below:\n"

        for f in jobj.get_project_default_types(project, issue_type):
            f = '"' + f + '"'
            fields[f] = "value"

    special_lines += "#\n"
    for f in set_field:
        field = f[0]
        if not field.startswith('"'):
            field = '"' + f[0] + '"'
        special_lines += f"# set-field: {field} {f[1]}\n"

    for k, v in fields.items():
        special_lines += f"## set-field: {k} {v}\n"

    template_data = f"{summary}\n\n{description}\n\n{special_lines}"

    if not filled_all:
        issue_patch = get_text_via_editor(template_data)

        if issue_patch == template_data and not (from_file or
                                                 (commit and not oneline)):
            if not json:
                click.echo("Issue text not set.  Please fill in project, "
                           "summary, and description.")
            else:
                click.echo(JSON.dumps({"success": False,
                                       "issue_id": None,
                                       "error":
                                       "Issue text not set.  Please fill in "
                                       "project, summary, and description."}))
            sys.exit(1)
    else:
        issue_patch = template_data

    # process the results.
    issue = {}

    issue["summary"], issue["description"], comments = issue_extract_blocks(issue_patch)

    for c in comments:
        if c.startswith("# set-field:"):
            m = re.match(r'# set-field:\s*(--forced)?\s*"(.*)" (.*)', c)
            if m:
                forced, f, v = m.groups()
                f = jobj._try_fieldname(f)
                v = jobj.convert_to_field_type(f, v) if not forced else eval(v)
                issue[f] = v
        elif c.startswith("# set-project: "):
            project = c[15:]
        elif c.startswith("# issue-type: "):
            issue_type = c[14:]

    issue["project"] = project
    issue["issuetype"] = issue_type
    if dry_run or verbose:
        click.echo(f"Creating: {pprint.pformat(issue)}")

    try:
        result = "DRY-OKAY" if dry_run else jobj.create_issue(issue)
        if json:
            click.echo(JSON.dumps({"success": True,
                                   "issue_id": result if dry_run else result.key,
                                   "raw": None if dry_run else result.raw}))
        else:
            click.echo(f"done - Result: {result}.")
    except Exception as e:
        if json:
            click.echo(JSON.dumps({"success": False,
                                   "issue_id": None,
                                   "error": str(e)}))
        else:
            click.echo(f"Unable to create issue - {str(e)}.")


@click.command(
    name='attachments'
)
@click.argument('issuekey')
@click.option("--pull", default=None,
              help="The attachment ID to download")
@click.option("--push", default=None,
              help="file to upload as attachment")
def attachments_cmd(issuekey, pull, push):
    """List, Pull, or Push attachments to a JIRA issue."""
    jobj = connector.JiraConnector()
    jobj.login()
    issue = jobj.get_issue(issuekey)

    if pull and push:
        raise click.UsageError("Invalid pull and push specified.")

    if pull:
        i = 0
        for attachment in issue.fields.attachment:
            if pull == attachment.filename or pull == str(i):
                click.echo(f"Downloading: {attachment.filename}")
                jobj.fetch_attachment(attachment.id, attachment.filename)
                return
            i += 1
        click.echo(f"Unknown attachment {pull}.")
        return

    if push:
        with open(push, 'rb') as f:
            jobj.upload_attachment(issue, f, os.path.basename(push))
        return

    output = "Attachments:\n"
    if issue.fields.attachment is not None and \
       len(issue.fields.attachment) > 0:
        attach_display = []
        i = 0
        for attachment in issue.fields.attachment:
            attach = (i, attachment.filename, attachment.created,
                      attachment.size, attachment.author.displayName)
            attach_display.append(attach)
            i += 1
        final = tabulate(attach_display,
                         ('Id', 'File', 'Created', 'Size', 'Creator'),
                         'psql')
        output += final + "\n\n"
    click.echo(output)


@click.command(
    name='eausm-vote'
)
@click.argument('issuekey')
@click.argument('vote')
def eausm_vote_cmd(issuekey, vote):
    """Set a vote for an issue using the Easy Agile planning poker plugin."""
    jobj = connector.JiraConnector()
    jobj.login()
    issue = jobj.get_issue(issuekey)
    if issue is None:
        raise click.UsageError("Issue not found")

    jobj.eausm_vote_issue(issue, vote)

    click.echo("Voted.")


def get_link_type_choices():
    jobj = connector.JiraConnector()
    try:
        jobj.login()
    except:
        return []

    jobj._ratelimit()
    return [x.name for x in jobj.jira.issue_link_types()]


@click.command(
    name="add-link"
)
@click.argument('issuekey')
@click.argument('url')
@click.argument('title')
@click.option("--relationship-type",
              type=click.Choice(["inward", "outward"],
                                case_sensitive=False),
              default='outward',
              help="Add a link to the issue.")
@click.option("--link-type",
              type=RuntimeEvalChoice(get_link_type_choices,
                                     case_sensitive=False),
              help="Set a relationship.")
def add_link_cmd(issuekey, url, title, relationship_type, link_type):
    """Adds a new link to URL to the issue at ISSUEKEY.

       TITLE will be used as a title if the URL is a remote url.  It will be
       treated as a comma if the remote link is another issue.  If it is set
       to the value 'none', it will be defaulted."""
    jobj = connector.JiraConnector()
    jobj.login()

    issue = jobj.get_issue(issuekey)
    if issue is None:
        raise ValueError(f"Issue {issuekey} not found")

    if title.lower() == "none":
        title = None

    if issue.fields.issuelinks is not None and \
       len(issue.fields.issuelinks) > 0:
        jobj._ratelimit()
        links = issue.fields.issuelinks if link_type == 'issue' else \
            jobj.jira.remote_links(issue.key)
        found = False
        for link in links:
            if hasattr(link, "object") and hasattr(link.object, "url") and \
               url == link.object.url:
                found = True
            elif hasattr(link, 'outwardIssue') and link.outwardIssue == url:
                found = True
            elif hasattr(link, 'inwardIssue') and link.inwardIssue == url:
                found = True
        if found:
            click.echo(f"{url} already added to issue.")
            return

    # if we got here, this is a new link
    jobj.add_issue_link(issuekey, url, title, link_type)


# ---------------------------------------------------------------------------
# bulk-import helpers
# ---------------------------------------------------------------------------

def _bulk_parse_file(path):
    """Load a YAML or JSON bulk-import file and return the raw dict."""
    with open(path, 'r') as f:
        if path.endswith('.json'):
            return JSON.load(f)
        return yaml.safe_load(f)


def _bulk_topo_sort(issues, issue_ref_fields=None):
    """Return issues in an order where every dependency appears before its
    dependent.  Raises click.UsageError on cycles.

    Each entry in *issues* is a dict that may contain a 'links' list.  Each
    link entry may have a 'target' that is a local alias.  Fields named in
    *issue_ref_fields* whose values are local aliases are also treated as
    ordering dependencies.  Real Jira keys are already created and impose no
    ordering constraint.
    """
    issue_ref_fields = issue_ref_fields or set()
    local_ids = {issue['id'] for issue in issues if 'id' in issue}

    # Build adjacency: node -> set of local-alias deps that must come first
    deps = {issue.get('id', f'__idx_{i}'): set() for i, issue in enumerate(issues)}
    idx_map = {issue.get('id', f'__idx_{i}'): issue for i, issue in enumerate(issues)}

    for issue in issues:
        node = issue.get('id', f'__idx_{issues.index(issue)}')
        for link in issue.get('links', []):
            target = link.get('target', '')
            if target in local_ids:
                deps[node].add(target)
        for fname, fval in issue.get('fields', {}).items():
            if fname in issue_ref_fields and str(fval) in local_ids:
                deps[node].add(str(fval))

    # Kahn's algorithm
    result = []
    in_degree = {n: 0 for n in deps}
    rev = {n: [] for n in deps}
    for n, d_set in deps.items():
        for d in d_set:
            rev[d].append(n)
            in_degree[n] += 1

    queue = [n for n, deg in in_degree.items() if deg == 0]
    while queue:
        n = queue.pop(0)
        result.append(idx_map[n])
        for m in rev[n]:
            in_degree[m] -= 1
            if in_degree[m] == 0:
                queue.append(m)

    if len(result) != len(issues):
        raise click.UsageError(
            "Cycle detected in bulk-import issue dependencies.")
    return result


def _bulk_validate(issues, jobj, default_project, default_issue_type,
                   ref_fields=None):
    """Query the Jira server to validate an import plan without creating anything.

    Returns a list of human-readable error strings.  An empty list means the
    plan looks valid.  Errors are accumulated (non-fail-fast) so the caller
    sees everything that needs fixing in one pass.
    """
    ref_fields = ref_fields or set()
    errors = []

    # Cache link types from the server once
    try:
        jobj._ratelimit()
        valid_link_types = {lt.name for lt in jobj.jira.issue_link_types()}
    except Exception as exc:
        errors.append(f"Could not fetch link types from server: {exc}")
        valid_link_types = set()

    # Local aliases defined in this batch — these don't need server validation
    local_ids = {issue['id'] for issue in issues if 'id' in issue}

    for i, entry in enumerate(issues):
        label = entry.get('id') or f"issue[{i}]"
        project = entry.get('project', default_project)
        itype = entry.get('issue_type', default_issue_type)

        # Validate project + issue type via createmeta
        try:
            jobj.get_project_default_types(project, itype)
        except Exception as exc:
            errors.append(f"{label}: project/issue-type invalid — {exc}")

        # Validate link types and any existing-key targets
        for link in entry.get('links', []):
            ltype = link.get('link_type')
            target = link.get('target', '')
            if ltype and valid_link_types and ltype not in valid_link_types:
                errors.append(
                    f"{label}: unknown link type '{ltype}'. "
                    f"Valid types: {', '.join(sorted(valid_link_types))}")
            if target and target not in local_ids:
                # Looks like a real Jira key — confirm it exists
                try:
                    if jobj.get_issue(target) is None:
                        errors.append(
                            f"{label}: link target '{target}' not found on server.")
                except Exception as exc:
                    errors.append(
                        f"{label}: link target '{target}' could not be fetched — {exc}")

        # Validate existing-key values in issue_ref_fields
        for fname, fval in entry.get('fields', {}).items():
            if fname not in ref_fields:
                continue
            fval = str(fval)
            if fval in local_ids:
                continue  # will be created as part of this batch
            # Otherwise it should already exist on the server
            try:
                if jobj.get_issue(fval) is None:
                    errors.append(
                        f"{label}: field '{fname}' references '{fval}' "
                        f"which was not found on server.")
            except Exception as exc:
                errors.append(
                    f"{label}: field '{fname}' references '{fval}' "
                    f"which could not be fetched — {exc}")

    return errors


def _bulk_build_issue_dict(entry, jobj, default_project, default_issue_type,
                           alias_map=None, issue_ref_fields=None):
    """Convert a bulk-import entry dict into a jira issue field dict.

    Fields named in *issue_ref_fields* have their values looked up in
    *alias_map* first, so a local alias is transparently replaced with the
    real Jira key before being passed to convert_to_field_type.
    """
    alias_map = alias_map or {}
    issue_ref_fields = issue_ref_fields or set()

    issue = {}
    issue['summary'] = entry.get('summary', '')
    issue['description'] = entry.get('description', '')
    issue['project'] = entry.get('project', default_project)
    issue['issuetype'] = entry.get('issue_type', default_issue_type)

    for fname, fval in entry.get('fields', {}).items():
        resolved_fname = jobj._try_fieldname(fname)
        fval = str(fval)
        if fname in issue_ref_fields:
            # Resolve any local alias to its real key before conversion.
            # convert_to_field_type handles the wire format: issuelinks-type
            # fields get {"key": value}, string/any fields get the plain key.
            fval = alias_map.get(fval, fval)
        issue[resolved_fname] = jobj.convert_to_field_type(resolved_fname, fval)

    return issue


@click.command(name='bulk-import')
@click.pass_context
@click.argument('importfile', type=click.Path(exists=True))
@click.option('--project', type=str, default=None,
              help="Default project for issues that don't specify one.")
@click.option('--issue-type',
              type=click.Choice(["Epic", "Bug", "Story", "Task", "Subtask"],
                                case_sensitive=False),
              default='Bug',
              help="Default issue type when not specified per-issue. Defaults to 'Bug'.")
@click.option('--issue-ref-field', 'issue_ref_fields', multiple=True, type=str,
              help="Field name whose value is a Jira issue key or local alias. "
                   "May be specified multiple times.  Merged with the "
                   "'issue_ref_fields' list in the import file.")
@click.option('--dry-run', is_flag=True, default=False,
              help="Parse and display what would be created without touching Jira.")
@click.option('--validate', is_flag=True, default=False,
              help="Query the server to validate projects, issue types, link "
                   "types, and referenced issue keys — but create nothing.  "
                   "A live run also validates first and aborts on any error.")
@click.option('--verbose', is_flag=True, default=False,
              help="Print each issue dict before creating it.")
def bulk_import_cmd(ctx, importfile, project, issue_type, issue_ref_fields,
                    dry_run, validate, verbose):
    """Bulk-create JIRA issues from a YAML or JSON file.

    \b
    The import file describes a list of issues.  Each issue may reference
    other issues by a local 'id' alias or by an existing Jira issue key.
    Issues are created in dependency order so that a newly-created issue can
    be the target of a link in the same batch.

    \b
    Example YAML layout
    -------------------
    issue_ref_fields:             # field names whose values are issue keys/aliases
      - parent
      - customfield_12345
    issues:
      - id: auth-epic
        summary: "Auth epic"
        description: "Top-level epic for auth work."
        project: MYPROJ
        issue_type: Epic

      - id: auth-spike
        summary: "Spike: auth service design"
        description: "Investigate OAuth2 options."
        project: MYPROJ
        issue_type: Story
        fields:
          Story Points: 3       # Jira display name (spaces OK in YAML keys)
          Fix Version/s: "2.1"
          parent: auth-epic     # alias resolved to real key before submission

      - id: auth-impl
        summary: "Implement auth service"
        project: MYPROJ
        issue_type: Story
        fields:
          Story Points: 8
          parent: auth-epic     # real Jira keys also accepted here
          ^customfield_10020: my-sprint   # ^ bypasses display-name lookup
        links:
          - link_type: "Depends"   # Jira link-type name (e.g. Depends, Blocks)
            direction: outward     # outward (default) or inward
            target: auth-spike     # local alias OR real Jira key (e.g. MYPROJ-42)
          - link_type: "Relates"
            direction: outward
            target: MYPROJ-99      # reference to a pre-existing issue

    \b
    Field name resolution
    ---------------------
    Keys under 'fields' are resolved via the same mechanism as --set-field:

    \b
      * The key is matched against Jira custom field display names
        (e.g. "Story Points" resolves to customfield_10016).
        The match is case-sensitive and must be exact.
      * If no display-name match is found the key is passed through
        as-is, so standard built-in fields (priority, assignee, …)
        work without any special syntax.
      * Prefix the key with ^ to skip name resolution entirely and
        supply the raw Jira field ID directly (e.g. ^customfield_10020).

    \b
    Issue-reference fields
    ----------------------
    Fields like 'parent' hold an issue key rather than a plain value.
    Declare them in the top-level 'issue_ref_fields' list in the import
    file, or with --issue-ref-field on the command line (both sources are
    merged).  When a declared field's value matches a local alias the alias
    is substituted with the real key before the issue is submitted to Jira.
    The topological sort also respects these references, so the referenced
    issue is always created first.

    \b
    Validation
    ----------
    --validate queries the server before creating anything:

    \b
      * Project exists and the chosen issue type is valid for it.
      * Every link_type named in a 'links' entry exists on the server.
      * Every non-alias target in 'links' and issue-reference fields
        resolves to a real issue on the server.

    \b
    A normal (non-dry-run) run always performs the same validation first
    and will abort before creating any issues if errors are found.
    Use --dry-run to skip all server contact entirely.

    \b
    Dependency ordering
    -------------------
    Local aliases referenced in 'links' entries and in issue-reference
    fields are resolved after the target issue has been created.  The
    importer performs a topological sort so that dependencies are created
    first.  A cycle in local-alias dependencies is an error.
    """
    if 'jobj' not in ctx.obj:
        jobj = connector.JiraConnector()
        jobj.login()
        ctx.obj['jobj'] = jobj
    else:
        jobj = ctx.obj['jobj']

    default_project = project or jobj.get_default_str('project',
                                                      'Default Project')
    default_issue_type = issue_type

    data = _bulk_parse_file(importfile)
    raw_issues = data.get('issues', [])
    if not raw_issues:
        click.echo("No issues found in import file.")
        return

    # 'parent' is always an issue-reference field in Jira Enterprise.
    # Merge with any additions from the file and the CLI option.
    ref_fields = {'parent'}
    ref_fields.update(data.get('issue_ref_fields', []))
    ref_fields.update(issue_ref_fields)

    try:
        ordered = _bulk_topo_sort(raw_issues, issue_ref_fields=ref_fields)
    except click.UsageError as exc:
        click.echo(f"ERROR: {exc}")
        sys.exit(1)

    # Server-side validation: runs for --validate and for live runs.
    # Skipped only for --dry-run (no server contact at all).
    if not dry_run:
        click.echo("Validating against server...")
        errors = _bulk_validate(ordered, jobj, default_project, default_issue_type,
                                ref_fields=ref_fields)
        if errors:
            click.echo(f"Validation found {len(errors)} error(s):")
            for err in errors:
                click.echo(f"  ERROR: {err}")
            sys.exit(1)
        click.echo("Validation passed.")
        if validate:
            return

    # alias -> real Jira key, populated as issues are created
    alias_map = {}
    dry_ct = 0

    pending_links = []  # (real_key, link_entry) to process after all creates

    for entry in ordered:
        alias = entry.get('id')
        dry_ct += 1
        issue_dict = _bulk_build_issue_dict(entry, jobj, default_project,
                                            default_issue_type,
                                            alias_map=alias_map,
                                            issue_ref_fields=ref_fields)

        if dry_run or verbose:
            click.echo(f"Issue{' [DRY-RUN]' if dry_run else ''}: {pprint.pformat(issue_dict)}")
            if entry.get('links'):
                click.echo(f"  Links: {entry['links']}")

        if dry_run:
            real_key = f"DRY-{dry_ct}"
        else:
            result = jobj.create_issue(issue_dict)
            real_key = str(result)

        click.echo(f"  Created: {real_key}" + (f" (alias: {alias})" if alias
                                               else ""))

        if alias:
            alias_map[alias] = real_key

        for link_entry in entry.get('links', []):
            pending_links.append((real_key, link_entry))

    # Now resolve and create all links
    click.echo(f"\nProcessing {len(pending_links)} link(s)...")
    for src_key, link_entry in pending_links:
        raw_target = link_entry.get('target', '')
        resolved_target = alias_map.get(raw_target, raw_target)
        ltype = link_entry.get('link_type')
        direction = link_entry.get('direction', 'outward')
        isinward = direction.lower() == 'inward'

        if not ltype:
            click.echo(f"  WARNING: link from {src_key} to {resolved_target} has no "
                       f"link_type – skipping.")
            continue

        if dry_run:
            click.echo(f"  [DRY-RUN] link {src_key} --[{ltype}/{direction}]--> {resolved_target}")
            continue

        try:
            jobj.add_issue_link(src_key, resolved_target, None, ltype, isinward)
            click.echo(f"  Linked {src_key} --[{ltype}/{direction}]--> {resolved_target}")
        except Exception as exc:
            click.echo(f"  ERROR linking {src_key} -> {resolved_target}: {exc}")

    click.echo("Bulk import complete.")

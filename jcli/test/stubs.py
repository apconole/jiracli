from datetime import datetime, timedelta
from jcli.connector import JiraConnector
import random


class jira_url_holder(object):
    def __init__(self):
        self.server_url = 'https://issue.test.com/'


def gen_rand_date(max_drift=30):
    start = datetime.today() - timedelta(days=max_drift)
    end = datetime.today()

    return start + (end - start) * random.random()


class JiraFieldStub(dict):
    def __getattr__(self, attr):
        return self[attr]

    def __setattr__(self, attr, val):
        self[attr] = val

    def __init__(self):
        self['raw'] = {}


class JiraIssueStub(dict):
    def __getattr__(self, attr):
        if attr == 'fields':
            return self['raw']['fields']
        return self[attr]

    def __setattr__(self, attr, val):
        self[attr] = val

    def __init__(self):
        self['raw'] = {}


class JiraCommentStub(dict):
    def __getattr__(self, attr):
        return self[attr]

    def __setattr__(self, attr, val):
        self[attr] = val

    def __init__(self):
        self['raw'] = {}


class JiraAuthorStub(dict):
    def __getattr__(self, attr):
        return self[attr]

    def __setattr__(self, attr, val):
        self[attr] = val

    def __init__(self):
        self['raw'] = {}


class JiraConnectorStub(JiraConnector):
    _issues_list = []
    _last_jql = ""

    def __init__(self, config_file=None):
        self._last_jql = ""
        self.jira = jira_url_holder()
        self.config = {}
        self.config['jira'] = {}
        self.config['jira']['default'] = {}
        self.config['jira']['default']['markdown'] = True
        self._last_comment_reply = None

    def setup_add_random_issue():
        issue = JiraIssueStub()
        prio = random.choice(["Minor", "Normal", "High", "Critical"])
        issue_tag = random.choice(["PROJMAIN-", "PROJEXP-", "CUSTOMER-"]) + str(
            random.randint(100, 100000))

        prefixes = ["Fix", "Implement", "Enhance", "Refactor", "Optimize"]
        actions = ["bugs", "feature", "UI", "performance",
                   "documentation", "security"]
        suffixes = ["issue", "request", "problem", "task", "enhancement",
                    "update"]

        components = ["the algorithmic complexity estimate rig",
                      "the red generator conveyor belt widgets",
                      "multiple list-walk related reciprocator",
                      "sections of the critical voting process",
                      "internal sad elephants quiet trumpeting",
                      "a major security detecting portion ring"]

        random_summary = f"{random.choice(prefixes)} {random.choice(components)} {random.choice(actions)} {random.choice(suffixes)}"

        statuses = ["Closed.....",
                    "Done.......",
                    "New........",
                    "To Do......",
                    "Planning...",
                    "Planned....",
                    "In Progress",
                    "Progressing",
                    "Submitted..",
                    "Reviewed...",
                    "Testing....",
                    "Verified..."]

        status = random.choice(statuses)

        assignees = [{"key": "a", "name": "a@a.com", "displayName": "A A"},
                     {"key": "b", "name": "b@a.com", "displayName": "B B"},
                     {"key": "c", "name": "c@a.com", "displayName": "C C"},
                     {"key": "d", "name": "d@a.com", "displayName": "D D"},
                     {"key": "e", "name": "e@a.com", "displayName": "E E"}]

        assignee = random.choice(assignees)
        f = JiraFieldStub()
        f['priority'] = {"name": prio}
        f['summary'] = random_summary
        f['project'] = {"name": "TEST"}
        f['status'] = {'name': status}
        f['assignee'] = assignee
        issue.raw['fields'] = f
        issue["key"] = issue_tag

        JiraConnectorStub._issues_list.append(issue)

    def setup_clear_issues():
        JiraConnectorStub._issues_list = []

    def login(self):
        pass

    def myself(self):
        pass

    def get_issue(self, issue_identifier):
        pass

    def get_states_for_issue(self, issue_identifier):
        pass

    def set_state_for_issue(self, issue, status):
        pass

    def issue_url(self, issue_identifier):
        pass

    def last_states_names(self):
        return ["Closed", "Done"]

    def _try_fieldname(self, name):
        return name

    def _query_issues(self, jql, offset, maxIssues):
        JiraConnectorStub._last_jql = jql
        return JiraConnectorStub._issues_list

    def requested_fields(self):
        pass

    def get_field(self, issue, fieldname, substruct=None):
        pass

    def set_field(self, issue, fieldname, val):
        pass

    def _fetch_custom_fields(self):
        pass

    def _fetch_field_type_mapping(self):
        pass

    def add_comment(self, issue_identifier, comment_body, visibility):
        for issue in JiraConnectorStub._issues_list:
            if issue['key'] == issue_identifier:

                c = JiraCommentStub()
                c['created'] = gen_rand_date()
                c['body'] = comment_body
                c['visibility'] = visibility
                c['id'] = random.randint(12345, 99999)
                c['author'] = JiraAuthorStub()
                c['author']['displayName'] = 'Random User'
                c['author']['name'] = 'randuser'

                if 'comment' not in issue.raw['fields']:
                    issue.raw['fields']['comment'] = JiraCommentStub()

                if 'comments' not in issue.raw['fields']['comment']:
                    issue.raw['fields']['comment']['comments'] = []

                issue.raw['fields']['comment']['comments'].append(c)

    def get_comment(self, issue_identifier, commentid):
        for issue in JiraConnectorStub._issues_list:
            if issue['key'] == issue_identifier:
                for c in issue.fields.comment.comments:
                    if c.id == commentid:
                        return c
        return None

    def in_reply_to_start(self, comment):
        JiraConnectorStub._last_comment_reply = f"> {comment.body}"

        return JiraConnectorStub._last_comment_reply

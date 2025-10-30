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
    last_issue = None
    config = {}

    def reset_config(cfg=None):
        if cfg:
            JiraConnectorStub.config = cfg
        else:
            JiraConnectorStub.config['jira'] = {}
            JiraConnectorStub.config['jira']['default'] = {}
            JiraConnectorStub.config['jira']['default']['markdown'] = True

    def __init__(self, config_file=None):
        self._last_jql = ""
        self.jira = jira_url_holder()
        self.config = JiraConnectorStub.config
        self._last_comment_reply = None
        self._fields = []

    def setup_add_random_issue():
        JiraConnectorStub.reset_config()
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

        assignee_dict = random.choice(assignees)
        assignee = JiraAuthorStub()
        assignee['key'] = assignee_dict['key']
        assignee['name'] = assignee_dict['name']
        assignee['displayName'] = assignee_dict['displayName']

        f = JiraFieldStub()
        f['priority'] = {"name": prio}
        f['summary'] = random_summary
        f['project'] = {"name": "TEST"}
        f['status'] = {'name': status}
        f['assignee'] = assignee
        f['Component'] = "component"
        issue.raw['fields'] = f
        issue["key"] = issue_tag
        issue["summary"] = random_summary
        issue["statusId"] = random.randint(0, 3)

        JiraConnectorStub._issues_list.append(issue)

    def setup_clear_issues():
        JiraConnectorStub._issues_list = []

    def login(self):
        pass

    def myself(self):
        pass

    def get_issue(self, issue_identifier):
        for i in JiraConnectorStub._issues_list:
            if i['key'] == issue_identifier:
                return i

        return None

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

    def set_field(self, issue, fieldname, val):
        pass

    def create_issue(self, issue_dict):
        print("Including an issue.")
        if 'summary' not in issue_dict or \
           'description' not in issue_dict or \
           'issuetype' not in issue_dict or \
           'project' not in issue_dict:
            raise ValueError("Missing required elements")
        JiraConnectorStub.last_issue = issue_dict
        return 'ISSUE-abc'

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

    def fetch_boards(self, limit=25, name=None):
        """Return stub boards for testing"""
        boards = []
        board_names = ["Sprint Board", "Kanban Board", "Support Board",
                       "Development Board", "QA Board"]
        board_types = ["scrum", "kanban", "simple"]

        for i in range(min(limit, len(board_names))):
            board = JiraFieldStub()
            board['raw'] = {
                'id': i + 1,
                'name': board_names[i],
                'type': random.choice(board_types)
            }
            boards.append(board)

        return boards

    def fetch_column_config_by_board(self, board_name):
        """Return stub column configuration for a board"""
        columns = {
            "To Do": [{"name": "To Do"}, {"name": "New"}],
            "In Progress": [{"name": "In Progress"}, {"name": "Progressing"}],
            "Testing": [{"name": "Testing"}, {"name": "Verified"}],
            "Done": [{"name": "Done"}, {"name": "Closed"}]
        }
        return columns

    def fetch_issues_by_board(self, board_name, offset=0, max_issues=100):
        """Return stub issues for a board"""
        return self._query_issues("", offset, max_issues)

    def fetch_issues_by_board_qf(self, board_name, offset=0, max_issues=100, quick_filter=None):
        """Return stub issues for a board with quick filter"""
        return self._query_issues("", offset, max_issues)

    def fetch_jql_config_by_board(self, board_name):
        """Return stub JQL configuration for a board"""
        return 'project = "TEST" AND status != "Closed"'

    def fetch_quickfilters_by_board(self, board_name):
        """Return stub quick filters for a board"""
        qf = JiraFieldStub()
        qf['quickFilters'] = []

        filter1 = JiraFieldStub()
        filter1['name'] = "My Issues"
        filter1['query'] = "assignee = currentUser()"
        filter1['id'] = "1"
        qf['quickFilters'].append(filter1)

        filter2 = JiraFieldStub()
        filter2['name'] = "High Priority"
        filter2['query'] = "priority = High"
        filter2['id'] = "2"
        qf['quickFilters'].append(filter2)

        return qf

    def fetch_sprints_by_board(self, board_name):
        """Return stub sprints for a board"""
        sprints = []

        # Active sprint
        sprint1 = JiraFieldStub()
        sprint1['id'] = 1
        sprint1['name'] = "Sprint 1"
        sprint1['state'] = "active"
        sprint1['startDate'] = "2025-10-01T00:00:00.000Z"
        sprint1['endDate'] = "2025-10-14T23:59:59.999Z"
        sprints.append(sprint1)

        # Future sprint
        sprint2 = JiraFieldStub()
        sprint2['id'] = 2
        sprint2['name'] = "Sprint 2"
        sprint2['state'] = "future"
        sprints.append(sprint2)

        # Closed sprint
        sprint3 = JiraFieldStub()
        sprint3['id'] = 3
        sprint3['name'] = "Sprint 0"
        sprint3['state'] = "closed"
        sprint3['startDate'] = "2025-09-17T00:00:00.000Z"
        sprint3['endDate'] = "2025-09-30T23:59:59.999Z"
        sprints.append(sprint3)

        return sprints

    def create_sprint(self, board_name, sprint_name, start_date=None, end_date=None, goal=None):
        """Create a stub sprint"""
        return {
            'id': random.randint(100, 999),
            'name': sprint_name,
            'state': 'future',
            'startDate': start_date.isoformat() + 'Z' if start_date else None,
            'endDate': end_date.isoformat() + 'Z' if end_date else None,
            'goal': goal
        }

    def get_status_detail(self, status_id):
        """Return stub status detail"""
        statuses = [
            {"name": "To Do"},
            {"name": "In Progress"},
            {"name": "Testing"},
            {"name": "Done"}
        ]
        return statuses[status_id % len(statuses)]

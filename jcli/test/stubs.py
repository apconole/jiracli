from jcli.connector import JiraConnector
import random


class JiraIssueStub(dict):
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

        components = ["the algorithmic", "our generator parts",
                      "multiple list-walk related",
                      "sections of the critical voting process",
                      "internal many sad elephants trumpeting",
                      "a major security detecting portion"]

        random_summary = f"{random.choice(prefixes)} {random.choice(components)} {random.choice(actions)} {random.choice(suffixes)}"

        statuses = ["Closed", "Done", "New", "To Do", "Planning", "Planned",
                    "In Progress", "Progressing", "Submitted", "Reviewed",
                    "Testing", "Verified"]

        status = random.choice(statuses)

        assignees = [{"key": "a", "name": "a@a.com", "displayName": "A A"},
                     {"key": "b", "name": "b@a.com", "displayName": "B B"},
                     {"key": "c", "name": "c@a.com", "displayName": "C C"},
                     {"key": "d", "name": "d@a.com", "displayName": "D D"},
                     {"key": "e", "name": "e@a.com", "displayName": "E E"}]

        assignee = random.choice(assignees)
        issue.raw['fields'] = {"priority": {"name": prio},
                               "summary": random_summary,
                               "project": {"name": "TEST"},
                               "status": {"name", status},
                               "assignee": assignee}
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

    def add_comment(self, issue_identifier, comment_body):
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

import datetime
import getpass
from jcli import utils
from jira import JIRA
from jira.exceptions import JIRAError
import jira
import os
import pathlib
import pprint
import yaml


class JiraConnector(object):
    def __init__(self, config_file=None):
        self.config_file = config_file or self._default_config_file()
        self.config = self._load_cfg()
        self.jira = None

    def _load_cfg(self):
        """Load a config yaml"""
        with open(self.config_file, 'r') as f:
            config = yaml.safe_load(f)

        if 'jira' not in config:
            raise ValueError("Missing jira section in config yaml")
        return config

    def _default_config_file(self):
        home_dir = os.path.expanduser("~")
        return os.path.join(home_dir, '.jira.yml')

    def _login(self):

        if self.jira is not None:
            # Hope this deletes the connection properly
            self.jira = None

        if 'auth' not in self.config:
            raise ValueError("Missing 'auth' section.")

        if 'username' not in self.config['auth']:
            raise ValueError("Authentication section missing a username.")

        username = self.config['auth']['username']
        auth_type = 'api'

        if 'type' in self.config['auth']:
            auth_type = self.config['auth']['type']

        if auth_type == 'api':
            if 'key' not in self.config['auth']:
                raise ValueError("Missing 'key' for 'api' auth type")
            token = self.config['auth']['key']
            if 'pat' in self.config['auth'] and bool(self.config['auth']['pat']):
                self.jira = JIRA(self.config['jira'], token_auth=token)
        elif auth_type == 'kerberos':
            kerberos_options = None
            if 'kerberos_options' in self.config['auth']:
                kerberos_options = self.config['auth']['kerberos_options']
            self.jira = JIRA(self.config['jira'], kerberos=True,
                             kerberos_options=kerberos_options)
        elif auth_type == 'password':
            if 'password' not in self.config['auth']:
                token = getpass.getpass(prompt="Enter your Jira password: ")
            else:
                token = self.config['auth']['password']
        else:
            raise ValueError(f"Unknown auth type: {auth_type}")

        if self.jira is None:
            self.jira = JIRA(self.config['jira'], basic_auth=(username,
                                                              token))

    def login(self):
        cached_creds = pathlib.Path(f"/tmp/.{getpass.getuser()}.jirasess")
        if cached_creds.is_file():
            # found a cached credentials file
            pass
        else:
            self._login()
            # pprint.pprint(vars(self.jira))
            # pprint.pprint(vars(self.jira._session))

    def user_sprint_field(self):
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        # default field is called 'Sprint' for now.
        sprint_field = "Sprint"

        if 'issues' not in self.config['jira']:
            return sprint_field

        issues_cfg = self.config['jira']['issues']
        for issue in issues_cfg:
            if 'sprint' in issue:
                if bool(issue['sprint']):
                    sprint_field = issue['name']
        return sprint_field

    def myself(self):
        if self.jira is None:
            raise RuntimeError("Need to log-in first")

        try:
            result = self.jira.myself()
        except JIRAError as e:
            result = {'key': f"ERROR retrieving information {e}"}

        return result['name']

    def _query_issues(self, query='', startAt=0, maxResults=100) -> list:
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        issues_list = self.jira.search_issues(query, startAt, maxResults)
        return issues_list

    def get_issue(self, issue_identifier):
        """Retrieve a Jira issue based on either key or ID."""
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        # Check if the issue_identifier is a numeric string (ID) or an
        # alphanumeric string (key)
        if issue_identifier.isdigit():
            # If numeric string, assume it's the issue ID
            issue = self.jira.issue(issue_identifier)
        else:
            # Otherwise, assume it's the issue key
            issue = self.jira.issue(issue_identifier, fields='*all')

        return issue

    def get_states_for_issue(self, issue_identifier) -> list:
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        state_names = []
        issue = self.get_issue(issue_identifier)
        transitions = self.jira.transitions(issue)

        state_names = [t['to']['name'] for t in transitions]
        return state_names

    def set_state_for_issue(self, issue, status):
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        if isinstance(issue, str):
            issue = self.get_issue(issue)

        self.jira.transition_issue(issue, transition=status)

    def issue_url(self, issue_identifier) -> str:
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        # Construct the URL for the issue
        issue_url = f"{self.jira._options['server']}/browse/{issue_identifier}"

        return issue_url

    def add_comment(self, issue_identifier, comment_body):
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        issue = self.get_issue(issue_identifier)

        if issue is not None:
            self.jira.add_comment(issue, comment_body)

    def build_issues_query(self, assignee=None, project=None, closed=None,
                           fields_dict=None, **kwargs):
        """
        Returns a query for a list of issues based on provided criteria

        Args:
        - assignee (str): Assignee of the issues
        - project (str): Project name for the issues
        - closed (bool): Whether or not to include closed issues in the query
        - fields_dict (dict): Dictionary of fields, where key is the field to
                              match, and value may either be a string (with implied
                              equality), or a tuple of (operator, value)
        - kwargs: Additional kwargs to add to the query

        Returns:
        - str: The query
        """
        query_parts = []

        if assignee is not None:
            if assignee == "":
                assignee = self.myself()
            query_parts.append(f'assignee = "{assignee}"')

        if project is not None:
            query_parts.append(f'project = "{project}"')

        if closed is None or not closed:
            stat_query = "status not in ("
            statuses = ",".join(['"' + s + '"' for s in self.last_states_names()])
            stat_query += statuses
            stat_query += ")"
            query_parts.append(stat_query)

        def additional_args(query_parts, fields) -> list:
            if fields:
                for field, m in fields_dict.items():
                    # need to check for field being custom.
                    field = self._try_fieldname(field)
                    oper = "="
                    v = m
                    if isinstance(m, tuple):
                        oper = m[0]
                        v = m[1]
                    query_parts.append(f'{field} {oper} {v}')
            return query_parts

        query_parts = additional_args(query_parts, fields_dict)
        query_parts = additional_args(query_parts, kwargs)

        return " AND ".join(query_parts)

    def _fetch_custom_fields(self) -> dict:
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        if not hasattr(self, "_custom_field_mapping"):
            custom_fields = self.jira.fields()
            self._custom_field_mapping = {field['id']: field['name']
                                          for field in custom_fields if field['custom']}

        return self._custom_field_mapping

    def requested_fields(self) -> list:
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        requested = []

        if 'issues' not in self.config['jira']:
            return requested

        issue_config = self.config['jira']['issues']
        for cfg in issue_config:
            if 'field' in cfg and 'name' in cfg['field']:
                requested.append(cfg['field']['name'])

        return requested

    def _try_fieldname(self, fieldname) -> str:
        """Tries to pick the fieldname for a passed in field"""
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        fields = self._fetch_custom_fields()

        if fieldname[0] == "^":
            return fieldname[1:]

        for k in fields:
            if fieldname == fields[k]:
                return k

        return fieldname

    def _get_field(self, issue, fieldname, substruct=None):
        """Get a raw field value for an issue."""
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        if isinstance(issue, str):
            issue = self.get_issue(issue)

        if fieldname in issue.raw['fields']:
            if issue.raw['fields'][fieldname] is None:
                return "None"
            if isinstance(issue.raw['fields'][fieldname], str):
                return issue.raw['fields'][fieldname]
            elif substruct is not None:
                return issue.raw['fields'][fieldname][substruct]
            else:
                if 'name' in issue.raw['fields'][fieldname]:
                    return issue.raw['fields'][fieldname]['name']
                return "(undecoded)"

        fields = self._fetch_custom_fields()
        val = None
        for field in fields:
            if fields[field] == fieldname:
                try:
                    val = eval(f"issue.fields.{field}")
                except:
                    val = None
        return val

    def get_field(self, issue, fieldname, substruct=None) -> str:
        """Get a field value as a string."""
        val = self._get_field(issue, fieldname, substruct)
        if val is None:
            return ""

        if isinstance(val, str):
            return val
        if isinstance(val, dict):
            if 'name' in val:
                return val['name']

        try:
            return str(val)
        except:
            return "(unknown decode)"

    def find_users_for_name(self, name) -> list:
        """
        Finds the users who match a given display name.
        """
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        return self.jira.search_users(user=name)

    def convert_to_jira_type(self, var_instance, value):
        """
        Converts the input from a JIRA type to a usable type based on
        some kinds of heuristics.

        Arguments:
        - var_instance: an instance of an existing field
        - value: The data to convert

        Returns:
        - The correct type tp put in a dict.
        """
        if isinstance(var_instance, jira.resources.User):
            # Assume the input is a name and look it up
            names = self.find_users_for_name(value)
            if len(names) > 1:
                raise ValueError(f"Ambiguous name {value} with {len(names)} matches.")
            return {"name": names[0].name}

        if isinstance(var_instance, jira.resources.Priority):
            return {"name": value}

        try:
            if 'name' in var_instance:
                return {"name": value}
        except:
            raise ValueError(f"Unable to handle {type(var_instance)}")

    def set_field(self, issue, fieldname, val):
        """Set the field for an issue to a particular value."""
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        if isinstance(issue, str):
            issue = self.get_issue(issue)

        issue_dict = {}
        if fieldname in issue.raw['fields']:
            f = eval(f"issue.fields.{fieldname}")
            val = self.convert_to_jira_type(f, val)
            issue_dict = {fieldname: val}

        fields = self._fetch_custom_fields()
        for field in fields:
            if fields[field] == fieldname:
                val = self.convert_to_field_type(field, val)
                issue_dict = {field: val}

        issue.update(issue_dict)

    def convert_to_field_type(self, field_id, field_value):
        """Convert the field value to the appropriate type."""
        if not hasattr(self, '_field_type_mapping'):
            # Get field type mapping from Jira if not cached
            self._field_type_mapping = self._fetch_field_type_mapping()

        field_type = self._field_type_mapping.get(field_id)
        if field_type is None:
            raise ValueError(f"Field type for field with ID '{field_id}' not found.")

        if field_type == "string":
            return field_value
        elif field_type == "number":
            return float(field_value)
        elif field_type == "date":
            return datetime.strptime(field_value, "%Y-%m-%d").date()
        # Add more conversions for other field types as needed

    def _fetch_field_type_mapping(self):
        """Fetch field type mapping from Jira."""
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        custom_fields = self.jira.fields()
        field_type_mapping = {field['id']: field['schema']['type']
                              for field in custom_fields if field['custom']}

        return field_type_mapping

    def _last_states_list(self) -> list:
        """Try to get all the final states"""

        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        statuses = self._get_statuses()
        final_status = []

        for status in statuses:
            if status.statusCategory.key == 'done':
                final_status.append(status)

        return final_status

    def last_states_names(self) -> list:

        final_statuses = [s.name for s in self._last_states_list()]
        return final_statuses

    def _get_statuses(self):

        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        if hasattr(self, '_cached_statuses'):
            return self._cached_statuses

        self._cached_statuses = self.jira.statuses()
        return self._cached_statuses

    def get_status_detail(self, statusId):
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        if isinstance(statusId, jira.resources.Status):
            statusId = statusId.id

        statuses = self._get_statuses()
        for status in statuses:
            if statusId == status.id or statusId == status.name:
                return status
        return None

    def fetch_boards(self, limit=0) -> list:
        """Try to get all the boards configured in jira"""
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        if limit > 0:
            return self.jira.boards(0, limit)

        return self.jira.boards(0, 0)

    def fetch_board_by_name(self, boardname):
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        return self.jira.boards(name=boardname)

    def fetch_sprints_by_board(self, board) -> list:
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        if isinstance(board, str):
            name = board
            board = self.fetch_board_by_name(name)
            if len(board) != 1:
                raise ValueError(f"Invalid results for {name} - ambiguous?")
            board = board[0]

        try:
            sprints = self.jira.sprints(board.raw['id'])
        except JIRAError:
            # not all boards support sprints, so ignore it
            sprints = []

        return sprints

    def _fetch_board_config_object(self, board):
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        if isinstance(board, str):
            name = board
            board = self.fetch_board_by_name(name)
            if len(board) != 1:
                raise ValueError(f"Invalid results for {name} - ambiguous?")
            board = board[0]

        # Got the board ID - let's get the REST details
        # Don't look at this too long .. it will make you sad.
        cfg = self.jira.find(f"../../agile/1.0/board/{board.raw['id']}/configuration")
        return cfg

    def fetch_issues_by_board(self, board, issue_offset, max_issues) -> list:
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        # This is a silly way of doing things - we need to query for all the
        # epic types and board id details.  BUT, JQL doesn't let us query by
        # board ID, so we need to actually pull the board configuration,
        # without a proper pythonic API and decode it manually to get the
        # correct JQL.
        r = self._fetch_board_config_object(board)
        f = self.jira.filter(r.filter)
        # let's check if the query includes closed issues:
        query = f.jql

        if 'status' not in query:
            oldquery = query
            query = "status not in (" + \
                ",".join(['"' + s + '"' for s in self.last_states_names()]) + \
                ") AND "
            if " order " in oldquery.lower():
                ns = utils.ireplace("order", ") order", oldquery)
                query += "(" + ns

        issues_in_epics = self._query_issues(query, issue_offset, max_issues)

        return issues_in_epics

    def fetch_column_config_by_board(self, board) -> dict:
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")
        r = self._fetch_board_config_object(board)

        cols = r.columnConfig.columns

        ret = {}
        for c in cols:
            ret[c.name] = [self.get_status_detail(status)
                           for status in c.statuses]

        return ret

    def fetch_jql_config_by_board(self, board):
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")
        r = self._fetch_board_config_object(board)
        f = self.jira.filter(r.filter)

        return f.jql

    def fetch_quickfilters_by_board(self, board):
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        if isinstance(board, str):
            name = board
            board = self.fetch_board_by_name(name)
            if len(board) != 1:
                raise ValueError(f"Invalid results for {name} - ambiguous?")
            board = board[0]

        # Boards are a total hack, and this is also sad.
        # Rather than a direct link somewhere to quickfilters, we need to
        # use the greenhopper endpoint to find the quickfilter config
        cfg = self.jira.find(f"../../greenhopper/1.0/rapidviewconfig/editmodel.json?rapidViewId={board.raw['id']}")
        if 'quickFilterConfig' in cfg.raw:
            return cfg.quickFilterConfig
        return None

    def fetch_issues_by_board_qf(self, board, issue_offset, max_issues, filter) -> list:
        if self.jira is None:
            raise RuntimeError("Need to log-in first.")

        if isinstance(board, str):
            name = board
            board = self.fetch_board_by_name(name)
            if len(board) != 1:
                raise ValueError(f"Invalid results for {name} - ambiguous?")
            board = board[0]

        fid = None
        filts = self.fetch_quickfilters_by_board(board)
        if not filts:
            return []

        for f in filts.quickFilters:
            if f.name == filter:
                fid = f.id

        if not fid:
            raise ValueError(f"Uknown query: {filter}")

        # Now query issues by the most absurd interface:
        resp = self.jira.find(f"../../greenhopper/1.0/xboard/work/allData.json?rapidViewId={board.raw['id']}&activeQuickFilters={fid}")

        if 'issuesData' in resp.raw:
            return resp.issuesData.issues

        return []

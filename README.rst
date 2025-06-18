=======
jiracli - A tool for interacting with JIRA on the command line.
=======

What is jiracli
--------------

`jiracli` is a python based framework for interacting with JIRA via the
command line interface.  The use is intended for JIRA users who don't
enjoy using a web based interface to JIRA and would rather use their
familiar editors and interaction tools.

`jiracli` makes use of the click framework, and the Atlassian JIRA
python framework to provide functionality.


Installing
----------

Currently, `jiracli` is a development-only version, and doesn't have much
support for distribution.  In order to install it, clone and run *pip install*::

  $ git clone https://github.com/apconole/jiracli.git
  $ cd jiracli
  $ pip install -e .

This will put the main `jiracli` utility `jcli` into your path.

Using
-----

First, you'll need to populate a jira yaml file that the internal jira
connector class will use to connect to the jira server.  To do this,
you'll want to use the example found in the *examples/* directory.

You'll want to change the authentication information, and you probably
will want to set specific fields to be included with issue information
(depending on what custom fields your JIRA projects use such as
'Story Points', etc).  Once you've set up the basic stuff, you can list
your issues with::

  $ jcli login
  $ jcli myself

And that should display your username, which shows that the connector
is properly configured.

One other convenient change to make to your environment is to use
`auto-click-auto` to generate a shell completion.  If you've installed
the auto-click-auto package, and use bash - you can simply run::

  $ eval "$(_JCLI_COMPLETE=bash_source jcli)"

Alternatively::

  $ source <(_JCLI_COMPLETE=bash_source jcli)

And your shell should have autocomplete for the `jcli` utility.

Additionally, there is the ability to run in interactive shell mode,
provided you've installed the `click-shell` package.  In that case,
you can run in interactive mode with::

  $ jcli shell-cmd
  jcli> help

This will give an interactive interface to the jcli suite of
commands.

Jira yaml field selection
-------------------------

The `.jira.yaml` does allow to select fields for inclusion, and
alternatively for exclusion.  The fields section looks like::

  jira:
  server: https://issues.place.com
  issues:
    - field:
      name: Some Field
      [exclude: true|false]

The exclude line for a field is optional, and can be either true
or false.  There are some 'built-in' fields that have support:

 - url
   The URL for the issue
 - comments
   All of the comments associated with an issue
 - description
   The description of an issue
 - links
   Any issue or remote links associated with an issue
 - attachments
   Attachments that are added to an issue

By default, all of the fields above are included in the issue
display, so you will require changes to the yaml file in order
to disable them.

JIRA Ratelimiting
-----------------

When working with some JIRA servers it may be necessary to keep the
number of requests per second limited.  While the python JIRA client
handles an exponential backoff in the case that the server returns an
unavailable error, the `jiracli` can limit server round trips as well.

The configuration for this is found in the default section of the yaml
file::

  jira:
    default:
      call_interval: time_in_ms
      wait_time: time_in_ms

The ``call_interval`` setting will be the minimum time between calls
measured in milliseconds to allow.  The default value is `500`.  A
value of `0` will disable the ratelimiting feature.

The ``wait_time`` setting will be the time to sleep when we need to
ratelimit (specified in ms).  The default value is `500`.

Interfacing with issues
-----------------------

Querying Issues
---------------

The default display for issues looks something like::

  $ jcli issues list
  +---------+------------+------------+--------------------+--------+----------+
  | key     | project    | priority   | summary            | status | assignee |
  +---------+------------+------------+--------------------+--------+----------+
  | BUG-123 | PROJMAIN   | Normal     | A normal bug       | New    | a@b.com  |
  | BUG-1   | PROJMAIN   | Undefined  | This is some ot... | Plan   | a@b.com  |
  | FEAT-1  | PROJEXTRA  | High       | Add another foo... | To Do  | a@b.com  |
  +---------+------------+------------+--------------------+--------+----------+

This default view presents the table of JIRA issue tickets assigned to the
current user.  The query that it uses is very basic, and only looks at those
tickets assigned to the current user, in all projects, that are not in a
"final" state.

The view can be tuned with a specific jql by using the `--jql` option::

  $ jcli issues list --jql="\"Project\" = \"PROJEXTRA\" AND assignee=\"b@b.com\""
  +---------+------------+------------+--------------------+--------+----------+
  | key     | project    | priority   | summary            | status | assignee |
  +---------+------------+------------+--------------------+--------+----------+
  | FEAT-3  | PROJEXTRA  | Normal     | Add a list of t... | Start  | b@b.com  |
  +---------+------------+------------+--------------------+--------+----------+

Additionally, the different contains and match options can help to build a
JQL query (`--matching-eq`, `--matching-neq`, `--matching-contains`,
`--matching-not`, `--matching-in`) for finer tuned queries to list issues.

As an example, let's say we want to find all the issues for which the custom
field "Response Needed" had the users A or B set::

  $ jcli issues list --assignee=- \
    --matching-in "\"Response Needed\"" "(\"$(jcli myself)\", \"b@b.com\")"
  +---------+------------+------------+--------------------+--------+----------+
  | key     | project    | priority   | summary            | status | assignee |
  +---------+------------+------------+--------------------+--------+----------+
  | BUG-123 | PROJMAIN   | Normal     | A normal bug       | New    | a@b.com  |
  | BUG-124 | PROJMAIN   | High       | The system caug... | QE     | b@b.com  |
  +---------+------------+------------+--------------------+--------+----------+

This output can also be formatted as CSV and used in scripts such as::

  $ for issue in $(jcli issues list --assignee=- --output=csv \
    --matching-in "\"Response Needed\"" "(\"$(jcli myself)\", \"b@b.com\")" |\
    tail -n +2 | cut -d, -f1); do
      notify-send "Issue Needs Response" "$(echo Issue Id: $issue)"
    done

This will call notify-send for all issues on the platform where the field
for "Response Needed" includes the current user or 'b@b.com' user.

Another useful case is to check for mentions in the comments.  This is
something we'd like to see across all issues.  For example, we may want to
see all updates in the last day::

  $ jcli issues list --mentions --updated-since="-1d"
  +---------+------------+------------+--------------------+--------+----------+
  | key     | project    | priority   | summary            | status | assignee |
  +---------+------------+------------+--------------------+--------+----------+
  | BUG-124 | PROJMAIN   | High       | The system caug... | QE     | b@b.com  |
  +---------+------------+------------+--------------------+--------+----------+

This can help to figure out which issues need responses for creating a daily
to-do list.

The output additionally can be formatted as JSON data to be used in more
complex scripts, example::

  $ jcli issues list --output json | jq -rc '.issues[] | keys'
  ["expand","fields","id","key","self"]
  ["expand","fields","id","key","self"]
  ["expand","fields","id","key","self"]
  ["expand","fields","id","key","self"]
  ["expand","fields","id","key","self"]
  ["expand","fields","id","key","self"]

The JSON output has the following fields::

  .issues_count : <num>
  .issues : <list>
  .field_maps : <dict>

Querying Fields
---------------

The `get-field` command allows pulling a **field: value** from the issue, for
any field you are interested in.  Normally, these fields are case sensitive.
That can be controlled by a yaml setting::

  jira:
    default:
      case_sensitive: false

Case sensitivity is defaulted to 'true'.

Bulk Formatting
---------------

The `output` command for listing issues can output in more than just some
simple preformatted responses.  There are two dynamic outputs for bulk
formatting issues: **report** and **template**.  Each provides a different
user-definable form of reporting on issues.

The **report** output is controlled by a series of filter and order
selections in your *jira.yml* file, such as ::

  jira:
    reporting:
      filters:
        FILTER1:
          match:
            status: ["New", "Start"]
        FILTER2:
          or:
            - match:
                Severity: ["Critical", "Blocker"]
            - match:
                priority: ["Super high", "OH NO"]
      ordering:
        field1:
          weight: 200:
          values:
            fv1: 10
            fv2: 11
            fv3: 12
            fv4: 13
        field2:
          weight: 100
          values:
            f2v1: 0
            f2v2: 1

This configuration creates two named filters: *FILTER1* and *FILTER2* which
each have different match criteria.  It also defines priority ordering, using
*field1* and *field2* for defining the relative weights.

When a **report** output is running, first all the issues selected by the
JQL are sorted according to the ordering.  Once they are sorted, then each
issue is evaluated against the filter list.  If it matches, it is removed from
the main list, and printed.  Once all filters have been evaluated, then the
unfiltered issues are displayed.

The **template** output is optionally available if the `jinja2` package is
installed.  In this output mode, `jcli` will open the template file specified
by the *--template-file* argument.  This will be formatted like a **jinja2**
template, and gets two usable references: *issues* which is an issue list,
and *client* which is the ``jcli.Connector`` instance that is currently
in use.  An example template might look like (in ~/template.jcli) ::

  Issues
  ======
  {% for issue in issues %}* {{issue.key | string}} | {{client.get_field(issue, "summary")}}
  {%endfor%}

And will generate output like::

  $ jcli issues list --output template
  Issues
  ======
  * BUG-123 | A normal bug
  * BUG-124 | The system caught a cold because it is really a person

See the Connector object for more details.  This can be useful for writing
dynamic HTML based reports, or for generating RAG documents for an AI to
help summarizing issues.

Display
-------

Interacting with issues usually involves adding comments, and transitioning
through states.  Occasionally, specific fields will need to be modified to
set up specific values.

Reading an issue is a simple `show` command::

  $ jcli issues show BUG-123
  +-----------------------------------------------------------------------------+
  | BUG-123    | PROJMAIN             | PROJMAIN                                |
  +-----------------------------------------------------------------------------+
  | priority: Normal               | status: New                                |
  +-----------------------------------------------------------------------------+
  | URL: https://tickets.b.com/browse/BUG-123                                   |
  +-----------------------------------------------------------------------------+
  | summary:                                                                    |
  | -------                                                                     |
  | A normal bug
  +-----------------------------------------------------------------------------+

  | Description:                                                                |
  |-----------------------------------------------------------------------------|
  | Description of problem:                                                     |
  | Just a normal bug that can happen when a user does foo-bar                  |
  > Comments:
  | Author: B Dev                                | 2023-09-14T07:28:41.000+0000 |
  |-----------------------------------------------------------------------------|
  | I wanted to try and solve this bug but there is an issue when the system ha |
  | s no activity - do we need to do something about this?                      |
  +-----------------------------------------------------------------------------+

This display includes comments, and will include any custom fields configured
in the Jira yaml preference file.

Another option would be to display the raw server side data of the issue::

  $ jcli issues sho

Commenting
----------

Adding a comment should be easy::

  $ jcli issues add-comment BUG-123

This will use the *EDITOR* environment variable to spawn an editor against a
temporary file which will be pushed to the issue as a comment.  Alternatively,
the **add-comment** command can accept a `--comment` option to fill a comment
from the command line directly.

You can set the comment visibility when creating a comment::

  $ jcli issues add-comment BUG-123 --visibility 'Some Group'
  ...

This will set the comment's visibility property to restrict viewing to
a specific group.

If you are intending to reply to a comment, you can specify the
`--in-reply-to` option which will generate a short pre-formatted text
reply::

  $ jcli issues add-comment BUG-123 --in-reply-to 11223344
  ...

This option cannot be combined with the `--comment` option.  The preamble
to the reply is set by a default jira config option in your jira config yaml::

  jira:
    default:
      replyto: On {{date}}, {{author_name}} writes:
    ...

This allows substituting date, comment_id, author_name, and author_id.

You can also edit a specific comment with the `update-comment` command::

  $ jcli issues update-comment BUG-123 11223344
  ...

This will first populate the body text in an editor.  It will then setup the
visibility settings.  You can use the `--visibility` option just as with
adding a comment.

To delete a comment::

  $ jcli issues del-comment BUG-123 11223344

This will attempt to delete a comment.

Comment Formatting
------------------

Tagging an individual in a comment involves using `[]` tags.  For example::

  This is a mention of [~b@b.com] in a comment

This will be the value of the JIRA name.

Adding links in the comment markdown can be done with::

  [link-text|url]

Drop all formatting::

  {noformat}
  text
  {noformat}

Add code that looks like c/c++/java (maybe even bash?)::

  {code:java}
  int foo(char c) {
     char bar;

     return c + bar;
  }
  {code}

The full reference for JIRA's markdown is documented elsewhere.

Setting fields
--------------

Setting a specific field looks like::

  $ jcli issues set-field BUG-123 "Priority" "Normal"
  Updated BUG-123, set Priority High -> Normal

Field names are normally case sensitive, but that setting can be adjusted (see
the section on getting fields).  Field values are **ALWAYS** case sensitive.

To move an issue to a different status, JIRA requires the use of a transition.
The valid transitions for an issue can be determined by::

  $ jcli issues states BUG-123
  ['New', 'Start', 'Post', 'QE', 'Done']

Setting the state can be done by::

  $ jcli issues set-status BUG-123 Post
  done.

Using attachments
-----------------

When printing an issue, any attachments will be displayed with their
filesize, creator, and name::

  | Attachments:                                                                                                                             |
  +--------------------+------------------------------+--------+--------------+
  | File               | Created                      |   Size | Creator      |
  |--------------------+------------------------------+--------+--------------|
  | some_filename_here | 2024-08-20T12:40:18.714+0000 |   4342 | Aaron Conole |
  +--------------------+------------------------------+--------+--------------+

To download, you can simply use the attachments sub-command::

  $ jcli issues attachments --pull some_filename_here BUG-123
  Downloading: some_filename_here
  $ 

If you use the attachments without any options, the same list will be displayed.
In this case, it will include an index to use as an alternate fetch-id::

  $ jcli issues attachments BUG-123
  +------+-------------------+------------------------------+--------+------------+
  |   Id | File               | Created                      |   Size | Creator    |
  |    0 | some_filename_here | 2024-08-20T12:40:18.714+0000 |   4342 | Aaron Conole |
  |------+-------------------+------------------------------+--------+------------|
  $ jcli issues attachments --pull 0 BUG-123
  Downloading: some_filename_here
  $

To upload, use the `--push` option with a filename::

  $ jcli issues attachments --push /tmp/data.txt BUG-321
  $

Adding Links
------------

There are two types of links that can be added to a JIRA ticket.
The first type is an issue relationship, which means that the target
URL is actually another JIRA ticket.  This relationship has an associated
LinkType and a direction (inward, or outward).  This can be added by::

  $ jcli issues add-link BUG-132 BUG-123 "This is a comment" --link-type <>

You can see the available link types, either with the tab-completion (if
enabled), or via the associated `details` command::

  $ jcli details link-types

Setting the direction can be done via the `--relationship-type` option.
*NOTE*: For the 'TITLE', you may use the value "none" to indicate no comment.


Additionally, you may set a link to a remote URL.  That is via an http/https
url::

  $ jcli issues add-link BUG-123 https://www.github.com "GitHub Tracker"

This will set a remote link against the JIRA ticket.

Reporting Issues in JIRA
------------------------

To test out filing a JIRA ticket, simply run::

  $ jcli issues create --dry-run

This will spawn an editor taking in issue text in the following fashion::

  This first block is the issue summary.

  Now add a bit of detailed description about the issue, including
  when it was observed, and what was seen.  Formatting options are valid
  here such as:
  {code:java}
     some_code();
     another_result = code_result();
  {code}

  And links to [searches|https://google.com].
  # This is a comment, and will not be added to the bug.
  # The following comments will be needed - they can live anywhere in
  # the description of the issue:
  # set-project: A Project Name
  # issue-type: Bug

In the above, when creating the issue, the first block of text will be
treated as the summary.  The issue parsing block will try to zap line-breaks
for the summary.  Line breaks for the description will be preserved.
Additionally, the comment blocks must include the `set-project:` and
`issue-type:` directives.  Make sure to use the appropriate issue type for
the project.  Finally, if you have specific fields you wish to set, those
can appear as additional `set-field:` blocks::

  # set-field: "Story Points" 1.0

This will tell the issue creation code to include a field setter for the
*"Story Points"* field and set it to value *1.0*.  NOTE: This only works
if the project is configured to use this field.

The issue creation code can also take all text from a file.  This is useful
when running with the dry-run flag, to check that all the fields have
appropriate settings.  The creation code will show what it will propose as
as issue like::

  Creating: {'description': 'Now add a bit of detailed description about the issue, including\n'
                  'when it was observed, and what was seen.  Formatting options are valid\n'
                  'here such as:\n'
                  '{code:java}\n'
                  '\n'
                  '   some_code();\n'
                  '   another_result = code_result();\n'
                  '{code}\n'
                  '\n'
                  '\n'
                  'And links to [searches|https://google.com].',
             'issuetype': 'Bug',
             'project': 'A Project Name',
             'summary': "This first block is the issue summary."}
  done - Result: DRY-OKAY

Once this is satisfactory, removing the dry-run flag will commit the issue
to the JIRA server.

Additionally, the issue parser will try to parse a patch file into a
formatted issue.  This can be useful when working with cover-letters or
for maintainers who wish to create tickets based on upstream accepted
bugfixes.

Finally, we can construct useful backport tickets by using the `--commit`
and even `--oneline` options to make useful backport related tickets::

  $ pwd
  /home/user/git/linux
  $ jcli issues create --project "Kernel Project" --issue-type Epic \
    --oneline --commit HEAD..HEAD~3

This will pop up an editor with contents like::

  # The first line in this will be treated as the summary.

  # The following commits will be referenced in the ticket
     9664d505853dc net: openvswitch: Debugging stuff
     42d43269220b2 net: openvswitch: kselftest rebase
     c4732113ade45 selftests: openvswitch: rework ovs-dpctl.py with something

  # set-project: Kernel Project
  # issue-type: Epic
  # NOTE: you can use a line '# set-field: "foo" bar' to set field 'foo'
  #       to value 'bar'.  The 'set-field' directive requires
  #       field to be quoted as "Some Foo"

You'll need to edit this and set the summary, and fill out the description
to get a valid issue created.  It is recommended to save a copy of the text
and use the `--dry-run` option to make sure you are confident in the issue
text, and only then run without `--dry-run`.


Interfacing with boards
-----------------------

Displaying a board
------------------

Displaying a board can be done by running the `boards show` command
with the board name as an argument::

  $ jcli boards show "My Board"
  +-----------+------------+---------+---------------------+-----------------------+------------+
  | Backlog   | Triage     | To Do   | In Progress (Dev)   | Code Review / On QA   | Done       |
  |-----------+------------+---------+---------------------+-----------------------+------------|
  |           | BUG-121    | BUG-22  | BUG-455             |                       | BUG-1      |
  |           |            | BUG-23  |                     |                       | BUG-2      |
  |           |            |         |                     |                       | BUG-3      |
  |           |            |         |                     |                       | BUG-4      |
  +-----------+------------+---------+---------------------+-----------------------+------------+

In order to work with boards from the command line, it is important to
know the column mappings for statuses, and the query that generates
the boards.  This information can be retrieved by the `boards get-config`
command to display the board column mappings, and queries::

  $ jcli boards get-config "My Board"
  {'column.Backlog', [<JIRA Status: name='Backlogged', id='12345'],
  ...
  quickfilter.name = "Only Me"
  quickfilter.query = "assignee = currentUser()"
  ...

Additionally, the named *quickfilters* can be displayed and used when
querying for board details::

  $ jcli boards show "My Board" --filter "Only Me"
  +-----------+------------+---------+---------------------+-----------------------+------------+
  | Backlog   | Triage     | To Do   | In Progress (Dev)   | Code Review / On QA   | Done       |
  |-----------+------------+---------+---------------------+-----------------------+------------|
  +-----------+------------+---------+---------------------+-----------------------+------------+


Server Side Extensions
----------------------

`jiracli` has some logic for some server side extensions.  Each extension
is listed below.


EZ Agile Planning Poker
-----------------------

The EZ Agile Planning Poker extension will automatically be detected and add
the 'eausm' details to the issue.raw['fields'] object.  However, this
currently isn't a proper jira type object, so it must be accessed as a dict
obj.  Future enhancements will convert it to a proper object and allow
voting for the picker.

To disable the extension, set the `eausm` config in your `jira` block to
*false*::

  jira:
    ...
    eausm: false
    ...

This will disable any attempts at detected or using the eausm extensions.

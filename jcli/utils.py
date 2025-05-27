"""
Utility stuff...
"""
import click
import codecs
import os
import re
import subprocess
import sys
import tempfile


def trim_text(data, length=45) -> str:
    return data[:length - 1] + "..." \
        if length > 0 and len(data) > length else data


def fitted_blocks(data, length=75, fence=None) -> str:
    eol = "\r\n" if os.name == 'nt' else "\n"
    if os.name != 'nt':
        data = data.replace('\r', '')

    output = ""
    lfence = f"{fence} " if fence else ""
    rfence = f" {fence}" if fence else ""

    for line in data.split('\n'):
        line = line.replace('\t', ' ' * 8)
        while len(line) > 0:
            output += f"{lfence}{line[:length]:<{length}}{rfence}{eol}"
            line = line[length:]

    return output


def issue_eval(issue_obj, header_map) -> list:
    issue_details = []
    for header in header_map:
        attr = header_map[header]
        try:
            val = eval(f"issue_obj.{attr}")
            issue_details.append(val)
        except:
            issue_details.append("--")

    return issue_details


def _display_via_pager(pager, output):
    env = dict(os.environ)
    # When the LESS environment variable is unset, Git sets it to FRX (if
    # LESS environment variable is set, Git does not change it at all).
    if 'LESS' not in env:
        env['LESS'] = 'FRX'

    c = subprocess.Popen(pager, shell=True, stdin=subprocess.PIPE,
                         env=env)
    encoding = getattr(c.stdin, 'encoding', None) or sys.getdefaultencoding()
    try:
        is_ascii = codecs.lookup(encoding).name == 'ascii'
    except LookupError:
        is_ascii = False

    if is_ascii:
        encoding = 'utf-8'

    try:
        for line in output:
            c.stdin.write(line.encode(encoding, 'replace'))
    except (IOError, KeyboardInterrupt):
        pass
    else:
        c.stdin.close()

    while True:
        try:
            c.wait()
        except KeyboardInterrupt:
            pass
        else:
            break


def display_via_pager(output, title=None):
    if title:
        click.echo(f"\033]0;{title}\007", nl=False)  # Set terminal title

    _display_via_pager(os.environ.get('PAGER', 'less'), output)


def get_text_via_editor(starting_text=None) -> str:
    text = ""

    with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False) as temp_file:
        if starting_text:
            temp_file.write(bytes(starting_text, "utf-8"))
        temp_file.close()  # Close the file so it can be opened by the text editor

        # Launch the default text editor for the user to write the comment
        subprocess.run([os.environ.get('EDITOR', 'nano'), temp_file.name])

        # Read the contents of the edited file
        with open(temp_file.name, 'r') as edited_file:
            text = edited_file.read()

        # Delete the temporary file
        os.unlink(temp_file.name)

    return text


def ireplace(old, new, text):
    return re.sub('(?i)' + re.escape(old), lambda m: new, text)


def str_containing(string, lst) -> bool:
    return any(check in string for check in lst)


def str_contained(string, lst) -> bool:
    return any(string in check for check in lst)


def git_get_commit_oneline(shasum) -> str:
    cmd = ['git', 'log']
    if "..." not in shasum and ".." not in shasum:
        cmd.append('-n')
        cmd.append('1')
    cmd.append('--oneline')
    cmd.append(shasum)

    try:
        o = subprocess.run(cmd, capture_output=True)
    except subprocess.CalledProcessError:
        return None

    return o.stdout.decode('utf-8')


def git_get_commit_formatted(shasum) -> str:
    cmd = ['git', 'format-patch', '-1', '--stdout']
    cmd.append(shasum)

    try:
        o = subprocess.run(cmd, capture_output=True)
    except subprocess.CalledProcessError:
        return None

    return o.stdout.decode('utf-8')


def extract_protected_blocks(text, protection_tag, blocks=[]):
    """
    Extracts tagged blocks and replaces them with placeholders to avoid modification.
    Returns the processed text and a list of extracted blocks.
    """

    def replace_with_placeholder(match):
        blocks.append(match.group(0))  # Store the full block
        return f"<<<BLOCK{len(blocks) - 1}>>>"  # Placeholder

    block_text = f"\\{{{protection_tag}\\}}.*?\\{{{protection_tag}\\}}"
    text = re.sub(block_text, replace_with_placeholder,
                  text, flags=re.DOTALL)

    return text, blocks


def restore_protected_blocks(text, blocks):
    """
    Restores {noformat} blocks from placeholders.
    """
    for i, block in enumerate(blocks):
        text = text.replace(f"<<<BLOCK{i}>>>", block)
    return text


def jira_to_md(text):
    """Converts JIRA comments to markdown"""
    # Pull out the text vs noformat blocks
    all_blocks = []
    text, all_blocks = extract_protected_blocks(text, 'noformat', all_blocks)
    text, all_blocks = extract_protected_blocks(text, 'code(:[a-zA-Z0-9]+)?', all_blocks)

    # Convert lists (need to do this before headers)
    text = re.sub(r'^\*\s*(.*?)$', r'- \1', text, flags=re.MULTILINE)
    text = re.sub(r'^#\s*(.*?)$', r'1. \1', text, flags=re.MULTILINE)

    # Convert headers
    text = re.sub(r'^h1\.\s*(.*?)$', r'# \1', text, flags=re.MULTILINE)
    text = re.sub(r'^h2\.\s*(.*?)$', r'## \1', text, flags=re.MULTILINE)
    text = re.sub(r'^h3\.\s*(.*?)$', r'### \1', text, flags=re.MULTILINE)

    # Convert bold and italics
    text = re.sub(r'\*(.*?)\*', r'**\1**', text)
    text = re.sub(r'_(.*?)_', r'*\1*', text)

    # Convert inline code
    text = re.sub(r'{{(.*?)}}', r'`\1`', text)

    # Convert to a markdown URL
    text = re.sub(r'\[([^\]|]+)\|([^\]]*://[^\]]+)\]', r'[\1](\2)', text)

    # Convert noformat and code tags
    for i in range(len(all_blocks)):
        bt = re.sub(r'\{noformat\}\n?(.*)\n?\{noformat\}',
                    lambda m: '\n'.join(f"> {line}" for line in m.group(1).splitlines()),
                    all_blocks[i],
                    flags=re.DOTALL)
        if bt == all_blocks[i]:
            bt = re.sub(r'\{code:?([a-zA-Z0-9]+)?\}\n?(.*)\n?\{code(:[a-zA-Z0-9]+)?\}',
                        lambda m: f"```{m.group(1) if m.group(1) else ''}\n{m.group(2)}\n```",
                        all_blocks[i],
                        flags=re.DOTALL)

        all_blocks[i] = bt

    text = restore_protected_blocks(text, all_blocks)
    return text


def md_to_jira(text):
    """Converts markdown to JIRA comments"""

    # Crazy hack ahead.  We convert the code and noformat tags virst, then
    # store them in blocks.  Then at the end restore the blocks without
    # modifying them

    # Convert Markdown blockquotes (`> `) to Jira `{noformat}`
    blockquote_pattern = re.compile(r'(^> .+(?:\n>(?:(?: .*)|$))*)', re.MULTILINE)
    text = blockquote_pattern.sub(
        lambda m: "{noformat}\n" + "\n".join(line.lstrip("> ") for line in m.group(1).splitlines()) + "\n{noformat}",
        text
    )

    # Convert Markdown code blocks (```) to Jira `{code}`
    text = re.sub(
        r'```([a-zA-Z0-9]*)\n?(.*?)(?:\n)?```',
        lambda m: "{code" + (f":{m.group(1)}}}" if m.group(1) else "}") + f"\n{m.group(2)}{{code}}",
        text,
        flags=re.DOTALL
    )

    # Convert URL formats for http/https
    text = re.sub(r'\[([^\]]+)\]\(([^)]+://[^\)]+)\)', r'[\1|\2]', text)

    all_blocks = []
    text, all_blocks = extract_protected_blocks(text, "noformat", all_blocks)
    text, all_blocks = extract_protected_blocks(text, "code", all_blocks)

    # Convert headers
    text = re.sub(r'^#\s*(.*?)$', r'h1. \1', text, flags=re.MULTILINE)
    text = re.sub(r'^##\s*(.*?)$', r'h2. \1', text, flags=re.MULTILINE)
    text = re.sub(r'^###\s*(.*?)$', r'h3. \1', text, flags=re.MULTILINE)

    # Convert bold and italics
    text = re.sub(r'\*\*(.*?)\*\*', r'*\1*', text)
    text = re.sub(r'\*(.*?)\*', r'_\1_', text)

    # Convert inline code and code blocks
    text = re.sub(r'`(.*?)`', r'{{\1}}', text)

    # Convert lists
    text = re.sub(r'^-\s*(.*?)$', r'* \1', text, flags=re.MULTILINE)
    text = re.sub(r'^\d+\.\s*(.*?)$', r'# \1', text, flags=re.MULTILINE)

    text = restore_protected_blocks(text, all_blocks)

    return text


@click.command(name="convert")
@click.argument("input", type=click.File('r'))
@click.option("--to", type=click.Choice(['jira', 'md']),
              default='md',
              help="The expected conversion type (if md, input should be jira)")
def convert_cmd(input, to):
    data = input.read()
    if to == "jira":
        click.echo(md_to_jira(data))
    elif to == "md":
        click.echo(jira_to_md(data))
    else:
        raise RuntimeError(f"Bad conversion {to}")


class RuntimeEvalChoice(click.Choice):
    def __init__(self, choices_getter, **kwargs):
        self._choice_get = choices_getter
        self._requested = False
        super().__init__([], **kwargs)

    def ensure_requested(self):
        if not self._requested:
            self.choices = self._choice_get()
            self._requested = True

    def convert(self, **kwargs):
        self.ensure_requested()
        return super().convert(**kwargs)

    def shell_complete(self, **kwargs):
        self.ensure_requested()
        return super().shell_complete(**kwargs)

    def __repr__(self):
        self.ensure_requested()
        return f"RuntimeEvalChoice({list(self.choices)})"

    def get_metavar(self, self2, **kwargs):
        self.ensure_requested()
        choices_str = "|".join(
            [str(i) for i in self.choices]
        )

        return f"[{choices_str}]"

"""
Utility stuff...
"""
import codecs
import os
import subprocess
import sys
import tempfile

#          0123456789012345678901234567890123456789012345678901234567890123456789012345678
SEP_STR = "+-----------------------------------------------------------------------------+"

def trim_text(data, length=45) -> str:
    return data[:length - 1] + "..." \
        if length > 0 and len(data) > length else data

def fitted_blocks(data, length=75, fence=None) -> str:
    lines = data.split('\n')
    output = ""

    for line in lines:
        while len(line) > 0:
            output += f"{fence} {line[:length]:<{length}} {fence}\n"
            line = line[length:]  # Corrected slicing index

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

def display_via_pager(output):
    pager = os.environ.get('PAGER')
    if not pager:
        pager = 'less'

    _display_via_pager(pager, output)

def get_text_via_editor() -> str:
    text = ""

    with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False) as temp_file:
        temp_file.close()  # Close the file so it can be opened by the text editor

        # Launch the default text editor for the user to write the comment
        subprocess.run([os.environ.get('EDITOR', 'nano'), temp_file.name])

        # Read the contents of the edited file
        with open(temp_file.name, 'r') as edited_file:
            text = edited_file.read()

        # Delete the temporary file
        os.unlink(temp_file.name)

    return text


"""Export the shared source messages for the Shell, without importing GTK."""

import argparse
import ast
import json
from pathlib import Path


def export(source):
    tree = ast.parse(source.read_text(encoding='utf-8'))
    messages = {}
    for node in tree.body:
        if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name) and node.value.func.id == 'gettext'):
            messages[node.targets[0].id] = ast.literal_eval(node.value.args[0])
        elif isinstance(node, ast.FunctionDef):
            for call in ast.walk(node):
                if (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                        and call.func.id == 'ngettext'):
                    messages[node.name.upper()] = [ast.literal_eval(arg) for arg in call.args[:2]]
    return messages


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1] / 'common/oh_no_parent_control_ui/messages.py'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(export(source), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

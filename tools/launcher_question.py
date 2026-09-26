"""Persist a workflow decision independently of any attached terminal."""

import codecs
import fcntl
import json
import re
import sys
import time

import detached_launcher as launcher


BLOCKER_INSTRUCTIONS = """For blocked, supply blocker with explanation, question and options. Write the
explanation in concise, user-friendly, scenario-oriented language (at most 200
words and 2000 characters): what is finished, what the user/test tries to do,
what actually prevents progress and the practical steps to unblock. Distinguish
test/tooling failures from established product defects. Keep technical evidence,
long commands and continuation prompts in the handoff only; do not repeat them in
the explanation or commentary. Ask one concrete question (under 240 characters)
that resolves the blocker. Provide 2 or 3 specific, distinct suggestions (under
300 characters each), with the recommended action first. The launcher adds the
recommended label and an editable Other option; do not include those yourself.
Never propose bypassing a denied grant or weakening acceptance to make it pass.
For other statuses set blocker to null. Do not print a separate final summary;
the launcher displays the explanation once and waits without a timeout.
"""


def validate_blocker(blocker):
    if (not isinstance(blocker, dict)
            or any(not isinstance(blocker.get(key), str) or not blocker[key].strip()
                   or len(blocker[key]) > limit
                   for key, limit in (('explanation', 2000), ('question', 240)))
            or not isinstance(blocker.get('options'), list)
            or not 2 <= len(blocker['options']) <= 3
            or any(not isinstance(option, str) or not option.strip() or len(option) > 300
                   for option in blocker['options'])
            or len(set(blocker['options'])) != len(blocker['options'])):
        raise ValueError('blocked result needs a concise explanation, question and 2–3 distinct suggestions')


def wait_for_answer(run, blocker, identity, progress_key, *, label, heading,
                    on_wait=lambda: None):
    """The owner waits without a timeout; shared observers submit the answer."""
    from launcher_progress import publish_progress
    from launcher_render import AgentRenderer
    validate_blocker(blocker)
    question = dict(blocker, id=identity, answer=None)
    with launcher.lock(run / 'question-gate') as gate:
        fcntl.flock(gate, fcntl.LOCK_EX)
        path = run / 'question.json'
        previous = json.loads(path.read_text()) if path.exists() else None
        if previous is None or previous['id'] != identity:
            launcher.atomic(path, question)
    on_wait()
    publish_progress(run, progress_key, [heading, 'Paused — waiting for your answer'])
    renderer = AgentRenderer(sys.stdout)
    renderer.message(blocker['explanation'])
    # Only observers render an editable selection; the transcript has no default vote.
    prompt = QuestionInput(question, None)
    prompt.selected = None
    renderer.console.print('\n'.join(prompt.lines()), markup=False)
    print(f'No timeout. Reattach with tools/{label} to answer after a disconnect.', flush=True)
    while True:
        if (run / 'cancel').exists():
            raise launcher.Stopped()
        if (run / 'stop').exists():
            return None
        question = json.loads(path.read_text())
        if question['answer'] is not None:
            renderer.console.print('\n'.join(QuestionInput(question, None).lines()), markup=False)
            return {'question': question['question'], 'answer': question['answer']}
        time.sleep(.1)


def pending(run):
    path = run / 'question.json'
    question = json.loads(path.read_text()) if path.exists() else None
    return question if question and question.get('answer') is None else None


def submit(run, identity, choice, instructions=''):
    """Accept exactly one answer to this question, even with multiple observers."""
    with launcher.lock(run / 'question-gate') as gate:
        fcntl.flock(gate, fcntl.LOCK_EX)
        question = pending(run)
        if question is None or question['id'] != identity:
            return False
        options = question['options']
        if type(choice) is not int or not 0 <= choice <= len(options):
            raise ValueError('invalid question choice')
        if choice == len(options):
            if not isinstance(instructions, str) or not instructions.strip() or len(instructions) > 8000:
                raise ValueError('Other needs instructions (up to 8000 characters)')
            answer = instructions.strip()
        else:
            answer = options[choice]
        launcher.atomic(run / 'question.json', dict(question, answer=answer, choice=choice))
        return True


class QuestionInput:
    """Small keyboard menu with the recommendation selected; Enter submits it."""

    def __init__(self, question, send):
        self.question = question
        self.send = send
        answered = question.get('answer') is not None
        self.selected = question['choice'] if answered else 0
        self.text = question['answer'] if answered and self.selected == len(question['options']) else ''
        self.buffer = ''
        self.decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
        self.pasting = False
        self.sent = answered
        self.explanation_cache = None

    def feed(self, data):
        self.buffer += self.decoder.decode(data)
        keys = ('\x1b[A', '\x1b[B', '\x1b[200~', '\x1b[201~')
        other = len(self.question['options'])
        while self.buffer and not self.sent:
            key = next((key for key in keys if self.buffer.startswith(key)), None)
            if key:
                self.buffer = self.buffer[len(key):]
                if key in ('\x1b[200~', '\x1b[201~'):
                    self.pasting = key == '\x1b[200~'
                elif not self.pasting:
                    delta = -1 if key == '\x1b[A' else 1
                    self.selected = (self.selected + delta) % (other + 1) if self.selected is not None else 0
                continue
            if any(key.startswith(self.buffer) for key in keys):
                break
            if self.buffer.startswith('\x1b['):
                escape = re.match(r'\x1b\[[0-?]*[ -/]*[@-~]', self.buffer)
                if escape is None:
                    break
                self.buffer = self.buffer[escape.end():]
                continue
            char, self.buffer = self.buffer[0], self.buffer[1:]
            if self.pasting:
                if self.selected == other and len(self.text) < 8000:
                    self.text += ' ' if char in '\r\n\t' else char if char.isprintable() else ''
            elif char in '\r\n':
                if self.selected is not None and (self.selected != other or self.text.strip()):
                    self.send(self.question['id'], self.selected, self.text)
                    self.sent = True
            elif char in ('\x7f', '\b'):
                self.text = self.text[:-1]
            elif char == '\x15':
                self.text = ''
            elif self.selected == other:
                if char.isprintable() and len(self.text) < 8000:
                    self.text += char
            elif char in '123456789' and int(char) <= other + 1:
                self.selected = int(char) - 1

    def lines(self, width=None):
        from launcher_render import clean
        options = self.question['options']
        lines = [clean(self.question['question'])]
        for index, option in enumerate(options):
            marker = '›' if index == self.selected else ' '
            suffix = ' (recommended)' if index == 0 else ''
            line = f'{marker} {index + 1}. {clean(option)}{suffix}'
            lines.append(f'\033[1m{line}\033[22m' if index == self.selected else line)
        marker = '›' if self.selected == len(options) else ' '
        value = clean(self.text)
        if width is not None and len(value) > max(1, width - 8):
            value = '…' + value[-max(1, width - 8):]
        value = value or '\033[90mOther\033[39m'
        line = f'{marker} {len(options) + 1}. {value}'
        lines.append(f'\033[1m{line}\033[22m' if self.selected == len(options) else line)
        lines.append('Answer submitted.' if self.sent else
                     'Choose a number or ↑/↓; type for Other; Enter to send. Waiting for your answer.')
        return lines

    def explanation(self, console, width):
        from launcher_render import SessionMarkdown, clean
        if self.explanation_cache is None or self.explanation_cache[0] != width:
            with console.capture() as capture:
                console.print(SessionMarkdown(clean(self.question.get('explanation', ''))), width=width)
            self.explanation_cache = width, capture.get().splitlines()
        return self.explanation_cache[1]

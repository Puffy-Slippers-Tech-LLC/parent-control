"""Persist a workflow decision independently of any attached terminal."""

import codecs
from contextlib import closing
import fcntl
import json
import re
import sys
import time

import detached_launcher as launcher


BLOCKER_INSTRUCTIONS = """Reserve blocked for a decision or action that actually requires the developer:
unresolved product behavior/expectations, missing authority, or a prerequisite
that cannot be repaired within existing authorization and maintained routes.
Routine implementation choices and proven mechanical test, fixture, harness or
input-preparation defects do not require a developer decision. Repair them
automatically while preserving assertions and evidence, within this launcher's
execution boundary. Do not ask whether to perform an already-authorized repair
or offer rebuilding versus restoring generated inputs as a developer choice.
Never infer permission to bypass a denied grant or overwrite unrelated inputs.
For blocked, supply blocker with explanation, question and options. The reader
should be able to answer without knowing how the launcher, tests or Linux work.
Use everyday language and short sentences in ALL three fields, including options.
Explain the immediate problem and its effect first, then why you cannot finish
the repair yourself and the specific decision or action needed from the user.
Mention completed work only when it helps that decision. Aim for 3-5 sentences
and at most 120 words (hard limit 2000 characters). Distinguish test/tooling
failures from established product defects; do not guess the cause.
Translate terms into their practical meaning: 'private SSH worker log' becomes
'the test's error log'; 'live qualification' becomes 'the test in the test VM';
'host execution context' becomes 'how the launcher runs commands on this computer'.
Keep commands, paths, error codes, identifiers such as failure_locations, and
terms such as setuid, pkexec and sandbox in the technical handoff only. If a
technical term is essential to the decision, explain it immediately in plain words.
Never ask the user to diagnose the system or 'restore an authorized context'.
Before asking about access, compare the exact command with the maintained grant,
including option order. A setuid error inside a sandbox does not establish broken
host permissions. Repair proven command/rule mismatches through authorized setup;
do not suggest administrator repair without evidence it is needed.
Ask one concrete question (under 240 characters) that resolves the blocker.
Provide 2 or 3 genuinely different choices (under 300 characters each), with the
recommended action first. Each choice must say who does what and what happens
next, in one short sentence. Do not offer two phrasings of the same repair or
ask the user to choose between internal implementation details. When an external
action is required, identify the exact action and offer waiting or stopping as
honest alternatives; never imply you can perform a repair you cannot access.
For example, after a verified external restriction: 'The test stopped, and I
cannot read its error log because this session blocks the approved log reader.
I cannot change that restriction here. Your computer administrator needs to
restore access before I can find out why the test failed.' Ask 'Should I wait
while your administrator restores access, or stop here?' Choices: 'Wait; I will
ask my administrator to restore access, then you can continue.' / 'Stop here
and keep the test results so we can return later.' Use this only when established
by evidence, not as a diagnosis template. For a product mismatch, describe the
user action, expected result and observed result before asking which is intended.
The launcher adds the
recommended label and an editable Other option; do not include those yourself.
Never propose bypassing a denied grant or weakening acceptance to make it pass.
For other statuses set blocker to null. Do not print a separate final summary;
the launcher displays the explanation once and owns the waiting policy.
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


def developer_timeout():
    """Use the development computer's local daytime/nighttime waiting policy."""
    return (30 if 8 <= time.localtime().tm_hour < 23 else 10) * 60


def allowance_blocker(subject, recordings='', *, stop_option):
    """One concise intervention prompt for repair and implementation launchers."""
    explanation = (f'{subject} still needs work after the allowed sessions. '
                   'The previous session has ended. I am waiting for your instructions.')
    for receipt in recordings.strip().split('\n\n'):
        if receipt and len(explanation) + len(receipt) + 2 <= 2000:
            explanation += '\n\n' + receipt
    return dict(
        explanation=explanation,
        question='How should I proceed?',
        options=['Continue for up to five more sessions.', stop_option])


def wait_for_intervention(*args, **kwargs):
    """Shared fresh session, local deadline, extensions and observer status."""
    return wait_for_answer(*args, **kwargs, timeout=developer_timeout(), intervention=True)


def wait_for_answer(run, blocker, identity, progress_key, *, label, heading,
                    on_wait=lambda: None, on_poll=lambda: None, timeout=None,
                    intervention=False):
    """Wait for an explicit answer, preserving the shared, extendable deadline."""
    from launcher_progress import publish_progress
    from launcher_render import AgentRenderer, SessionTranscript
    validate_blocker(blocker)
    question = dict(blocker, id=identity, answer=None, intervention=intervention)
    with launcher.lock(run / 'question-gate') as gate:
        fcntl.flock(gate, fcntl.LOCK_EX)
        path = run / 'question.json'
        previous = json.loads(path.read_text()) if path.exists() else None
        if previous is None or previous['id'] != identity:
            if timeout is not None:
                question['deadline'] = time.time() + timeout
            launcher.atomic(path, question)
        elif timeout is not None and 'deadline' not in previous:
            launcher.atomic(path, dict(previous, deadline=time.time() + timeout))
    fresh = False
    if intervention:
        view_path = run / 'session-view.json'
        view = json.loads(view_path.read_text()) if view_path.exists() else {}
        fresh = view.get('session') != identity
        if fresh:
            launcher.atomic(view_path, dict(view, session=identity, status='finished',
                                            interactive=False, started_at=time.time(),
                                            continue_transcript=False))
    on_wait()
    publish_progress(run, progress_key, [heading, 'Paused — waiting for your answer'])
    with closing(SessionTranscript(sys.stdout, run, append=not fresh)) as transcript:
        renderer = AgentRenderer(transcript,
            on_description=launcher.descriptive_output(run) if intervention else None)
        renderer.message(blocker['explanation'])
        # Only observers render an editable selection; the transcript has no default vote.
        prompt = QuestionInput(question, None)
        prompt.selected = None
        renderer.console.print('\n'.join(prompt.lines()), markup=False)
        print((f'Waiting up to {timeout // 60} minutes.' if timeout is not None else 'No timeout.')
              + f' Reattach with tools/{label} to answer after a disconnect.',
              file=transcript, flush=True)
        while True:
            if (run / 'cancel').exists():
                raise launcher.Stopped()
            if (run / 'stop').exists():
                return None
            on_poll()
            question = json.loads(path.read_text())
            if question['answer'] is not None:
                renderer.message(question['answer'], 'You')
                # The answer starts a new agent process, but continues the
                # displayed conversation. Consume this display-only flag when
                # the next supervisor publishes its fresh session identity.
                view_path = run / 'session-view.json'
                if view_path.exists():
                    launcher.atomic(view_path, dict(json.loads(view_path.read_text()),
                                                    continue_transcript=True))
                return {'question': question['question'], 'answer': question['answer']}
            if timeout is not None and time.time() >= question['deadline']:
                with launcher.lock(run / 'question-gate') as gate:
                    fcntl.flock(gate, fcntl.LOCK_EX)
                    question = json.loads(path.read_text())
                    if question['answer'] is not None or time.time() < question['deadline']:
                        continue
                    launcher.atomic(path, dict(question, expired=True))
                raise TimeoutError('waiting for input: developer prompt timed out')
            time.sleep(.1)


def pending(run):
    path = run / 'question.json'
    question = json.loads(path.read_text()) if path.exists() else None
    return question if question and question.get('answer') is None and not question.get('expired') else None


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


def extend_deadline(run, identity):
    """Add ten minutes to the still-pending question under its shared gate."""
    with launcher.lock(run / 'question-gate') as gate:
        fcntl.flock(gate, fcntl.LOCK_EX)
        question = pending(run)
        if (question is None or question['id'] != identity
                or question.get('deadline') is None or time.time() >= question['deadline']):
            raise ValueError('This question is no longer accepting extra time.')
        launcher.atomic(run / 'question.json', dict(question, deadline=question['deadline'] + 600))


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

"""Persist a workflow decision independently of any attached terminal."""

import codecs
import fcntl
import json
import re

import detached_launcher as launcher


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

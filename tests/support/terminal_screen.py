"""In-memory VT screen shared by launcher and watcher rendering tests."""

import io
import os
import re

from rich.cells import get_character_cell_size


class Terminal(io.StringIO):
    def __init__(self, width=80, height=24):
        super().__init__()
        self.normal_screen = None
        self.scrollback = []
        self.cursor_visible = True
        self.resize(width, height)

    def resize(self, width, height):
        if getattr(self, 'size', None) == os.terminal_size((width, height)):
            return
        self.size = os.terminal_size((width, height))
        self.cells = [[' '] * width for _ in range(height)]
        self.row = self.column = 0

    def isatty(self):
        return True

    def write(self, value):
        result = super().write(value)
        for token in re.split(r'(\x1b\[[0-?]*[ -/]*[@-~])', value):
            if token.startswith('\x1b['):
                args, operation = token[2:-1], token[-1:]
                if args == '?1049' and operation == 'h':
                    self.normal_screen = ([row[:] for row in self.cells], self.row, self.column)
                elif args == '?1049' and operation == 'l':
                    self.cells, self.row, self.column = self.normal_screen
                    self.normal_screen = None
                elif args == '?25':
                    self.cursor_visible = operation == 'h'
                elif operation == 'H':
                    row, _, column = args.partition(';')
                    self.row, self.column = int(row or 1) - 1, int(column or 1) - 1
                elif operation == 'J' and args == '2':
                    self.cells = [[' '] * self.size.columns for _ in range(self.size.lines)]
                elif operation == 'K' and args == '2':
                    self.cells[self.row] = [' '] * self.size.columns
                continue
            for char in token:
                if char == '\n':
                    self.row += 1
                    self.column = 0
                    continue
                width = get_character_cell_size(char)
                if self.column + width > self.size.columns:
                    self.row += 1
                    self.column = 0
                if self.row >= self.size.lines:
                    if self.normal_screen is None:
                        self.scrollback.append(''.join(self.cells[0]).rstrip())
                    self.cells.pop(0)
                    self.cells.append([' '] * self.size.columns)
                    self.row = self.size.lines - 1
                if width:
                    self.cells[self.row][self.column] = char
                    self.column += width
        return result

    def visible(self):
        return '\n'.join(''.join(row).rstrip() for row in self.cells)


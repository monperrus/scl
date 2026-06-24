from __future__ import annotations

import re
from dataclasses import dataclass, field

_NAME_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]*")
_WS = frozenset(" \t\n\r")
_HWS = frozenset(" \t")  # horizontal whitespace only


@dataclass
class Text:
    content: str


@dataclass
class Command:
    name: str
    args: list[str] = field(default_factory=list)


Document = list[Text | Command]


def _word_boundary(text: str, pos: int) -> bool:
    return pos == 0 or text[pos - 1] in _WS


def _parse_args(text: str, pos: int) -> tuple[list[str], int]:
    """Return (args, new_pos) starting right after the command name."""
    n = len(text)

    # Must have at least one horizontal space before args.
    if pos >= n or text[pos] not in _HWS:
        return [], pos

    # Skip horizontal whitespace.
    while pos < n and text[pos] in _HWS:
        pos += 1

    if pos >= n or text[pos] == "\n":
        return [], pos

    # Quoted form: first non-space char is a quote.
    if text[pos] in "\"'":
        args: list[str] = []
        start = pos  # save for unterminated-quote backtrack
        while pos < n and text[pos] in "\"'":
            quote = text[pos]
            pos += 1
            end = text.find(quote, pos)
            if end == -1:
                # Unterminated quote — backtrack, emit command with no args.
                return [], start
            args.append(text[pos:end])
            pos = end + 1
            while pos < n and text[pos] in _HWS:
                pos += 1
        return args, pos

    # Raw form: scan to EOL, stop early at the next command trigger.
    raw_start = pos
    while pos < n and text[pos] != "\n":
        if text[pos] == "/" and _word_boundary(text, pos):
            m = _NAME_RE.match(text, pos + 1)
            if m:
                break
        pos += 1

    raw = text[raw_start:pos].rstrip()
    if raw:
        return [raw], pos  # pos is EOL, EOF, or start of next command trigger
    return [], pos


def _try_command(text: str, pos: int) -> tuple[Command, int] | None:
    """Try to parse a command at pos (text[pos] must be '/')."""
    m = _NAME_RE.match(text, pos + 1)
    if not m:
        return None
    name = m.group()
    args, end = _parse_args(text, m.end())
    return Command(name, args), end


def parse(text: str) -> Document:
    """Parse *text* into an ordered sequence of Text and Command segments."""
    segments: Document = []
    pos = 0
    text_start = 0
    n = len(text)

    while pos < n:
        if text[pos] == "/" and _word_boundary(text, pos):
            result = _try_command(text, pos)
            if result is not None:
                cmd, end = result
                if pos > text_start:
                    segments.append(Text(text[text_start:pos]))
                segments.append(cmd)
                text_start = pos = end
                continue
        pos += 1

    if text_start < n:
        segments.append(Text(text[text_start:]))

    return segments

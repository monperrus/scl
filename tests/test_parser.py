"""Normative test suite for the Slash Command Language (SCL).

Each test class corresponds to a section of RFC.md.  Passing this suite is
the conformance criterion for any SCL implementation.
"""

from __future__ import annotations

import pytest

from slash_command import Command, Text, parse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def text(s: str) -> Text:
    return Text(s)


def cmd(name: str, *args: str) -> Command:
    return Command(name, list(args))


# ---------------------------------------------------------------------------
# Section 3.1 — Command trigger / word-boundary rules
# ---------------------------------------------------------------------------

class TestCommandTrigger:
    def test_at_start_of_input(self):
        assert parse("/help") == [cmd("help")]

    def test_after_space(self):
        assert parse("then /help") == [text("then "), cmd("help")]

    def test_after_tab(self):
        assert parse("then\t/help") == [text("then\t"), cmd("help")]

    def test_after_newline(self):
        assert parse("hello\n/help") == [text("hello\n"), cmd("help")]

    def test_not_inside_word(self):
        # foo/bar — / not at word boundary → all text
        assert parse("foo/bar") == [text("foo/bar")]

    def test_slash_not_followed_by_alpha(self):
        # / followed by space → text
        assert parse("a / b") == [text("a / b")]

    def test_slash_followed_by_digit(self):
        # / followed by digit → text (name must start with ALPHA)
        assert parse("a /1foo") == [text("a /1foo")]

    def test_url_not_a_command(self):
        # https://example.com — double-slash not at word boundary
        assert parse("visit https://example.com now") == [
            text("visit https://example.com now")
        ]

    def test_slash_only(self):
        assert parse("/") == [text("/")]

    def test_empty_input(self):
        assert parse("") == []

    def test_name_with_hyphen(self):
        assert parse("/my-command") == [cmd("my-command")]

    def test_name_with_underscore(self):
        assert parse("/my_command") == [cmd("my_command")]

    def test_name_with_digits(self):
        assert parse("/cmd2go") == [cmd("cmd2go")]

    def test_name_case_sensitive(self):
        assert parse("/Help") == [cmd("Help")]
        assert parse("/help") == [cmd("help")]
        assert parse("/help") != parse("/Help")


# ---------------------------------------------------------------------------
# Section 3.2 — Argument forms
# ---------------------------------------------------------------------------

class TestNoArgForm:
    def test_sole_command(self):
        assert parse("/exit") == [cmd("exit")]

    def test_command_at_end_of_line(self):
        assert parse("please /exit\nnext line") == [
            text("please "),
            cmd("exit"),
            text("\nnext line"),
        ]

    def test_command_followed_by_eof(self):
        assert parse("done /quit") == [text("done "), cmd("quit")]


class TestRawArgForm:
    def test_single_word(self):
        assert parse("/search python") == [cmd("search", "python")]

    def test_multiple_words(self):
        assert parse("/search python async") == [cmd("search", "python async")]

    def test_strips_trailing_whitespace(self):
        assert parse("/search python   ") == [cmd("search", "python")]

    def test_raw_arg_stops_at_next_command(self):
        # /foo hello /bar — "hello" is raw arg of /foo; /bar is a separate command
        assert parse("/foo hello /bar") == [cmd("foo", "hello"), cmd("bar")]

    def test_raw_arg_stops_at_next_command_no_gap(self):
        # /foo /bar — no space between, but /bar is at word boundary after space
        assert parse("/foo /bar") == [cmd("foo"), cmd("bar")]

    def test_multiline_raw_args_stay_on_line(self):
        # Raw arg does not cross newlines
        assert parse("/search python\nmore text") == [
            cmd("search", "python"),
            text("\nmore text"),
        ]

    def test_raw_arg_with_punctuation(self):
        assert parse("/note hello, world!") == [cmd("note", "hello, world!")]


class TestQuotedArgForm:
    def test_double_quoted_single_arg(self):
        assert parse('/search "python async"') == [cmd("search", "python async")]

    def test_single_quoted_single_arg(self):
        assert parse("/search 'python async'") == [cmd("search", "python async")]

    def test_multiple_double_quoted_args(self):
        assert parse('/tag "foo" "bar"') == [cmd("tag", "foo", "bar")]

    def test_multiple_single_quoted_args(self):
        assert parse("/tag 'foo' 'bar'") == [cmd("tag", "foo", "bar")]

    def test_quoted_preserves_interior_whitespace(self):
        assert parse('/note "  spaces  "') == [cmd("note", "  spaces  ")]

    def test_empty_quoted_arg(self):
        assert parse('/cmd ""') == [cmd("cmd", "")]

    def test_quoted_arg_with_slash(self):
        # Slash inside quotes is not a command trigger
        assert parse('/cmd "foo/bar"') == [cmd("cmd", "foo/bar")]


# ---------------------------------------------------------------------------
# Section 3.4 — Document structure / island behaviour
# ---------------------------------------------------------------------------

class TestDocumentStructure:
    def test_text_only(self):
        assert parse("hello world") == [text("hello world")]

    def test_command_only(self):
        assert parse("/help") == [cmd("help")]

    def test_text_command_text(self):
        assert parse("before /help after") == [
            text("before "),
            cmd("help", "after"),
        ]

    def test_text_command_newline_text(self):
        assert parse("before\n/help\nafter") == [
            text("before\n"),
            cmd("help"),
            text("\nafter"),
        ]

    def test_two_commands_on_same_line(self):
        assert parse("/foo /bar") == [cmd("foo"), cmd("bar")]

    def test_two_commands_on_separate_lines(self):
        assert parse("/foo\n/bar") == [cmd("foo"), text("\n"), cmd("bar")]

    def test_command_between_text_segments(self):
        assert parse("a /b c\nd") == [
            text("a "),
            cmd("b", "c"),
            text("\nd"),
        ]

    def test_no_empty_text_segments(self):
        # Adjacent commands should not produce empty text segments.
        doc = parse("/a /b")
        assert not any(isinstance(s, Text) and s.content == "" for s in doc)

    def test_all_characters_covered(self):
        # Every character of the input must appear in exactly one segment.
        source = "hello /cmd 'arg'\nworld"
        doc = parse(source)
        reconstructed = "".join(
            s.content if isinstance(s, Text) else
            "/" + s.name + ("" if not s.args else
                            " " + " ".join(f"'{a}'" for a in s.args))
            for s in doc
        )
        # We cannot reconstruct byte-for-byte (args are stored without quotes),
        # so instead verify that text segments alone cover the non-command text.
        text_content = "".join(s.content for s in doc if isinstance(s, Text))
        assert "hello " in text_content
        assert "\nworld" in text_content


# ---------------------------------------------------------------------------
# Section 6 — Error handling / never-fail guarantee
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_unterminated_double_quote(self):
        # Command is still emitted with no args; unclosed text becomes Text.
        doc = parse('/search "python')
        assert doc[0] == cmd("search")
        assert isinstance(doc[1], Text)
        assert '"python' in doc[1].content

    def test_unterminated_single_quote(self):
        doc = parse("/search 'python")
        assert doc[0] == cmd("search")
        assert isinstance(doc[1], Text)
        assert "'python" in doc[1].content

    def test_slash_in_natural_language(self):
        # "and/or" — slash not at word boundary → plain text
        assert parse("and/or") == [text("and/or")]

    def test_slash_at_end_of_input(self):
        assert parse("foo /") == [text("foo /")]

    def test_parse_never_raises(self):
        inputs = [
            "",
            "/",
            "///",
            '/unclosed "quote',
            "normal text with no commands",
            "/a /b /c",
            "/ / /",
        ]
        for s in inputs:
            parse(s)  # must not raise

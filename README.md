# Slash Command Language (SCL) — RFC Draft

## Abstract

The Slash Command Language (SCL) defines a syntax for embedding executable
commands within natural-language text.  Text segments are intended for
interpretation by a large language model; command segments are executed
symbolically by a host runtime.  The design follows the *island-parsing*
principle: structured command "islands" are recognized and extracted from an
unstructured text "sea" without requiring the surrounding text to conform to
any grammar.

---

## 1. Introduction

Interactive AI systems frequently mix natural language with structured
directives.  A user might write:

    Please /search "quantum computing" and summarize the top results, then /exit

The words "Please" and "and summarize the top results, then" are addressed to
the language model.  The tokens `/search "quantum computing"` and `/exit` are
addressed to the runtime.

SCL provides a minimal, unambiguous grammar for this interleaving, together
with a normative parsing algorithm and a Python reference implementation
(`slash_command/`).

The test suite in `tests/test_parser.py` is normative: any implementation that
passes every test is considered conformant.

---

## 2. Terminology

| Term | Definition |
|------|------------|
| **Document** | The output of parsing: an ordered sequence of *segments*. |
| **Segment** | Either a *text segment* or a *command segment*. |
| **Text segment** | A contiguous run of characters that carries no command. |
| **Command segment** | A slash command with an optional argument list. |
| **Word boundary** | Position 0 of the input, or any position immediately following a whitespace character (U+0009 TAB, U+000A LF, U+000D CR, U+0020 SP). |
| **Island parsing** | A parsing strategy in which structured sub-languages ("islands") are recognised within an otherwise uninterpreted character stream ("water"). |

---

## 3. Syntax

### 3.1 Command trigger

A command begins with a U+002F SOLIDUS (`/`) located at a word boundary,
followed *immediately* (no intervening space) by a valid command name.

```
command  ::= '/' name args?
name     ::= ALPHA (ALPHA | DIGIT | '-' | '_')*
ALPHA    ::= [a-zA-Z]
DIGIT    ::= [0-9]
```

A `/` that is not at a word boundary, or that is not immediately followed by
an `ALPHA` character, is treated as plain text and does not begin a command.

Examples:

| Input fragment | Verdict |
|----------------|---------|
| `/help` at position 0 | command |
| `then /help` | command (`/` preceded by space) |
| `foo/bar` | text (`/` not at word boundary) |
| `/ help` | text (`/` not followed immediately by ALPHA) |
| `https://example.com` | text (`//` not at word boundary) |

### 3.2 Arguments

Arguments follow the command name.  Three forms are defined:

**No-argument form** — the command name is immediately followed by end-of-line,
end-of-input, or a word-boundary `/` that starts the next command.  The
command carries an empty argument list.

**Quoted form** — when the first non-whitespace character after the command
name is a U+0022 QUOTATION MARK (`"`) or U+0027 APOSTROPHE (`'`), arguments
are parsed as one or more quoted strings.  Each quoted string is delimited by
matching quote characters and may contain any character except the delimiting
quote.  Multiple quoted strings may be separated by horizontal whitespace.

**Raw form** — when the first non-whitespace character after the command name
is neither a quote nor a `/` that would start another command, all remaining
characters up to (but not including) the next newline (or end-of-input) form a
single raw-string argument, with leading and trailing horizontal whitespace
stripped.  Raw-form scanning stops early if it encounters a word-boundary `/`
immediately followed by a valid name, so that adjacent commands are not
consumed as arguments.

```
args         ::= quoted_form | raw_form
quoted_form  ::= (SP+ quoted_string)+
raw_form     ::= SP+ raw_string
quoted_string ::= '"' [^"]* '"' | "'" [^']* "'"
raw_string   ::= <characters to EOL, excluding trailing command trigger, stripped>
SP           ::= U+0020 | U+0009
```

### 3.3 Argument representation

Both forms produce a `list[str]` value on the `Command` object:

| Form | Example input | `args` value |
|------|---------------|--------------|
| No-argument | `/help` | `[]` |
| Raw | `/search python async` | `["python async"]` |
| Quoted (single) | `/search "python async"` | `["python async"]` |
| Quoted (multiple) | `/tag "foo" "bar"` | `["foo", "bar"]` |

### 3.4 Document structure

```
document  ::= segment*
segment   ::= text_segment | command_segment
```

A document is produced by a single left-to-right scan (Section 4).  Every
character of the input belongs to exactly one segment.  Empty text segments
are suppressed.

---

## 4. Normative parsing algorithm

The reference implementation in `slash_command/_parser.py` is normative.
The algorithm is summarised here for clarity.

```
pos        ← 0
text_start ← 0
segments   ← []

while pos < len(input):
    if input[pos] == '/' and word_boundary(input, pos):
        result ← try_command(input, pos)
        if result is not None:
            (cmd, end) ← result
            if pos > text_start:
                append Text(input[text_start:pos]) to segments
            append cmd to segments
            text_start ← pos ← end
            continue
    pos ← pos + 1

if text_start < len(input):
    append Text(input[text_start:]) to segments
```

`try_command(input, pos)` matches a name immediately after `pos`, then
delegates to `parse_args`.  It returns `None` if no valid name follows the
`/`, causing the `/` to be treated as text.

`parse_args` implements the three argument forms described in Section 3.2.
On unterminated quoted strings, it returns an empty argument list and resets
the position to immediately after the command name, leaving the unclosed
quoted text to become part of the following text segment.

---

## 5. Semantics

SCL is a purely syntactic specification.  This RFC does not define the
behaviour of any command; that is the responsibility of the host system.

Conforming implementations MUST:

1. Expose the parsed result as an ordered sequence of `Text` and `Command`
   objects.
2. Preserve text-segment content verbatim (including all whitespace).
3. Expose on each `Command` object: the command `name` (str) and `args`
   (list of str).
4. Never raise a parse error; any unrecognised content becomes a text segment.

---

## 6. Error handling

SCL parsing is total: it always produces a valid `Document`.  Specific cases:

| Situation | Outcome |
|-----------|---------|
| `/` not at word boundary | treated as text |
| `/` followed by non-ALPHA | treated as text |
| Unterminated quoted argument | command emitted with `args=[]`; unclosed content becomes text |
| Unknown command name | command is still emitted; interpretation is host-defined |

---

## 7. Relationship to island parsing

Island parsing (Rekers & Schürr, 1996; Moonen, 2001) is a technique for
recovering structure from partially-parseable input.  "Islands" of
grammatically well-formed content are parsed; everything else is "water" that
is passed through unchanged.

SCL instantiates this idea at a coarser level: slash-command syntax defines
the island grammar; natural language (intended for an LLM) is the water.  The
scanner never attempts to parse the water, which makes the approach robust to
arbitrary natural-language content including code, markup, URLs, and punctuation.

---

## 8. Reference implementation

`slash_command/` (Python 3.11+):

```
slash_command/
├── __init__.py    public API: parse(), Text, Command, Document
└── _parser.py     implementation
```

---

## 9. Test suite (executable specification)

`tests/test_parser.py` contains the normative test cases.  Each test is a
direct transcription of a row in the specification tables above, or covers an
edge case called out in the text.  Running `pytest` against a conformant
implementation must produce no failures.

---

## 10. Known implementations

| Language | Package | Notes |
|----------|---------|-------|
| Python | [slash_command](https://github.com/monperrus/slash_command/) | Packaged reference implementation |

---

## Appendix A. EBNF summary

```ebnf
document      = { segment } ;
segment       = text_segment | command_segment ;
text_segment  = character+ ;  (* any chars not claimed by a command *)
command_segment = '/' , name , [ args ] ;
name          = ALPHA , { ALPHA | DIGIT | '-' | '_' } ;
args          = quoted_form | raw_form ;
quoted_form   = { SP } , quoted_string , { { SP } , quoted_string } ;
raw_form      = SP , { SP } , raw_char , { raw_char } ;
quoted_string = '"' , { any_except_dquote } , '"'
              | "'" , { any_except_squote } , "'" ;
raw_char      = any character except LF, excluding a leading command trigger ;
SP            = ' ' | TAB ;
ALPHA         = 'a'..'z' | 'A'..'Z' ;
DIGIT         = '0'..'9' ;
```

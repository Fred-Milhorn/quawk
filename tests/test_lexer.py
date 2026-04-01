# Scanner and token-location tests.
# These cases verify token classification, text capture, and source-position
# tracking in the frontend scanner.

from __future__ import annotations

import pytest

from quawk.diagnostics import LexError
from quawk.lexer import TokenKind, lex
from quawk.source import ProgramSource


def test_lexes_begin_print_literal_program() -> None:
    tokens = lex('BEGIN { print "hello" }')

    assert [token.kind for token in tokens] == [
        TokenKind.BEGIN,
        TokenKind.LBRACE,
        TokenKind.PRINT,
        TokenKind.STRING,
        TokenKind.RBRACE,
        TokenKind.EOF,
    ]
    assert [token.display_text() for token in tokens] == [
        "BEGIN",
        "{",
        "print",
        '"hello"',
        "}",
        None,
    ]
    assert [token.span.format_start() for token in tokens] == [
        "<inline>:1:1",
        "<inline>:1:7",
        "<inline>:1:9",
        "<inline>:1:15",
        "<inline>:1:23",
        "<inline>:1:24",
    ]


def test_lexes_newlines_and_escaped_quotes() -> None:
    tokens = lex(' \nBEGIN\t{ print "say \\"hi\\"" }\n')

    assert [token.kind for token in tokens] == [
        TokenKind.NEWLINE,
        TokenKind.BEGIN,
        TokenKind.LBRACE,
        TokenKind.PRINT,
        TokenKind.STRING,
        TokenKind.RBRACE,
        TokenKind.NEWLINE,
        TokenKind.EOF,
    ]
    assert tokens[4].text == '"say \\"hi\\""'
    assert tokens[0].span.format_start() == "<inline>:1:2"
    assert tokens[1].span.format_start() == "<inline>:2:1"
    assert tokens[6].span.format_start() == "<inline>:2:29"
    assert tokens[7].span.format_start() == "<inline>:2:29"


def test_lexes_posix_comments_as_trivia_and_preserves_newlines() -> None:
    tokens = lex('# first line\nBEGIN { print 1 # trailing comment\n}\n')

    assert [token.kind for token in tokens] == [
        TokenKind.NEWLINE,
        TokenKind.BEGIN,
        TokenKind.LBRACE,
        TokenKind.PRINT,
        TokenKind.NUMBER,
        TokenKind.NEWLINE,
        TokenKind.RBRACE,
        TokenKind.NEWLINE,
        TokenKind.EOF,
    ]
    assert tokens[0].span.format_start() == "<inline>:1:13"
    assert tokens[5].span.format_start() == "<inline>:2:35"


def test_lexes_hash_inside_string_and_regex_as_data() -> None:
    tokens = lex('BEGIN { print "#"; print /#/ }\n')

    assert [token.kind for token in tokens] == [
        TokenKind.BEGIN,
        TokenKind.LBRACE,
        TokenKind.PRINT,
        TokenKind.STRING,
        TokenKind.SEMICOLON,
        TokenKind.PRINT,
        TokenKind.REGEX,
        TokenKind.RBRACE,
        TokenKind.NEWLINE,
        TokenKind.EOF,
    ]
    assert tokens[3].text == '"#"'
    assert tokens[6].text == "/#/"


def test_lexes_general_identifiers_and_numbers() -> None:
    tokens = lex("foo 123 4.5")

    assert [token.kind for token in tokens] == [
        TokenKind.IDENT,
        TokenKind.NUMBER,
        TokenKind.NUMBER,
        TokenKind.EOF,
    ]
    assert [token.text for token in tokens] == ["foo", "123", "4.5", None]


def test_lexes_regex_literal_in_pattern_position() -> None:
    tokens = lex("/foo/ { print $0 }")

    assert [token.kind for token in tokens] == [
        TokenKind.REGEX,
        TokenKind.LBRACE,
        TokenKind.PRINT,
        TokenKind.DOLLAR,
        TokenKind.NUMBER,
        TokenKind.RBRACE,
        TokenKind.EOF,
    ]
    assert tokens[0].text == "/foo/"
    assert tokens[0].span.format_start() == "<inline>:1:1"


def test_lexes_regex_literal_after_print_keyword() -> None:
    tokens = lex("BEGIN { print /foo/ }")

    assert [token.kind for token in tokens] == [
        TokenKind.BEGIN,
        TokenKind.LBRACE,
        TokenKind.PRINT,
        TokenKind.REGEX,
        TokenKind.RBRACE,
        TokenKind.EOF,
    ]
    assert tokens[3].text == "/foo/"


def test_lexes_slash_as_operator_after_operand() -> None:
    tokens = lex("BEGIN { print 8 / 2 }")

    assert [token.kind for token in tokens] == [
        TokenKind.BEGIN,
        TokenKind.LBRACE,
        TokenKind.PRINT,
        TokenKind.NUMBER,
        TokenKind.SLASH,
        TokenKind.NUMBER,
        TokenKind.RBRACE,
        TokenKind.EOF,
    ]
    assert tokens[4].display_text() == "/"


def test_lexes_regex_with_escaped_slash_and_character_class() -> None:
    tokens = lex(r'/fo\/o[\/]bar/ { print $0 }')

    assert tokens[0].kind is TokenKind.REGEX
    assert tokens[0].text == r'/fo\/o[\/]bar/'


def test_lexes_numeric_print_expression_tokens() -> None:
    tokens = lex("BEGIN { print 1 + 2 }")

    assert [token.kind for token in tokens] == [
        TokenKind.BEGIN,
        TokenKind.LBRACE,
        TokenKind.PRINT,
        TokenKind.NUMBER,
        TokenKind.PLUS,
        TokenKind.NUMBER,
        TokenKind.RBRACE,
        TokenKind.EOF,
    ]
    assert [token.display_text() for token in tokens] == [
        "BEGIN",
        "{",
        "print",
        "1",
        "+",
        "2",
        "}",
        None,
    ]


def test_lexes_equality_expression_tokens() -> None:
    tokens = lex("BEGIN { print 1 == 1 }")

    assert [token.kind for token in tokens] == [
        TokenKind.BEGIN,
        TokenKind.LBRACE,
        TokenKind.PRINT,
        TokenKind.NUMBER,
        TokenKind.EQUAL_EQUAL,
        TokenKind.NUMBER,
        TokenKind.RBRACE,
        TokenKind.EOF,
    ]
    assert [token.display_text() for token in tokens] == [
        "BEGIN",
        "{",
        "print",
        "1",
        "==",
        "1",
        "}",
        None,
    ]
    assert tokens[4].span.format_start() == "<inline>:1:17"


def test_lexes_parenthesized_logical_and_expression_tokens() -> None:
    tokens = lex("BEGIN { print (1 < 2) && (2 < 3) }")

    assert [token.kind for token in tokens] == [
        TokenKind.BEGIN,
        TokenKind.LBRACE,
        TokenKind.PRINT,
        TokenKind.LPAREN,
        TokenKind.NUMBER,
        TokenKind.LESS,
        TokenKind.NUMBER,
        TokenKind.RPAREN,
        TokenKind.AND_AND,
        TokenKind.LPAREN,
        TokenKind.NUMBER,
        TokenKind.LESS,
        TokenKind.NUMBER,
        TokenKind.RPAREN,
        TokenKind.RBRACE,
        TokenKind.EOF,
    ]
    assert tokens[8].display_text() == "&&"
    assert [token.span.format_start() for token in tokens[3:10]] == [
        "<inline>:1:15",
        "<inline>:1:16",
        "<inline>:1:18",
        "<inline>:1:20",
        "<inline>:1:21",
        "<inline>:1:23",
        "<inline>:1:26",
    ]


def test_lexes_assignment_tokens() -> None:
    tokens = lex("BEGIN { x = 1; print x }")

    assert [token.kind for token in tokens] == [
        TokenKind.BEGIN,
        TokenKind.LBRACE,
        TokenKind.IDENT,
        TokenKind.EQUAL,
        TokenKind.NUMBER,
        TokenKind.SEMICOLON,
        TokenKind.PRINT,
        TokenKind.IDENT,
        TokenKind.RBRACE,
        TokenKind.EOF,
    ]


def test_lexes_array_assignment_tokens() -> None:
    tokens = lex('BEGIN { a["x"] = 1; print a["x"] }')

    assert [token.kind for token in tokens] == [
        TokenKind.BEGIN,
        TokenKind.LBRACE,
        TokenKind.IDENT,
        TokenKind.LBRACKET,
        TokenKind.STRING,
        TokenKind.RBRACKET,
        TokenKind.EQUAL,
        TokenKind.NUMBER,
        TokenKind.SEMICOLON,
        TokenKind.PRINT,
        TokenKind.IDENT,
        TokenKind.LBRACKET,
        TokenKind.STRING,
        TokenKind.RBRACKET,
        TokenKind.RBRACE,
        TokenKind.EOF,
    ]


def test_lexes_delete_and_for_tokens() -> None:
    tokens = lex('BEGIN { delete a["x"]; for (i = 0; i < 3; i = i + 1) print i; for (k in a) print k }')

    assert TokenKind.DELETE in [token.kind for token in tokens]
    assert TokenKind.FOR in [token.kind for token in tokens]
    assert TokenKind.IN in [token.kind for token in tokens]


def test_lexes_bare_action_field_tokens() -> None:
    tokens = lex("{ print $1 }")

    assert [token.kind for token in tokens] == [
        TokenKind.LBRACE,
        TokenKind.PRINT,
        TokenKind.DOLLAR,
        TokenKind.NUMBER,
        TokenKind.RBRACE,
        TokenKind.EOF,
    ]


def test_lexes_comparison_and_control_flow_tokens() -> None:
    tokens = lex("BEGIN { if (1 < 2) print 3; while (x < 3) { x = x + 1 } }")

    assert [token.kind for token in tokens] == [
        TokenKind.BEGIN,
        TokenKind.LBRACE,
        TokenKind.IF,
        TokenKind.LPAREN,
        TokenKind.NUMBER,
        TokenKind.LESS,
        TokenKind.NUMBER,
        TokenKind.RPAREN,
        TokenKind.PRINT,
        TokenKind.NUMBER,
        TokenKind.SEMICOLON,
        TokenKind.WHILE,
        TokenKind.LPAREN,
        TokenKind.IDENT,
        TokenKind.LESS,
        TokenKind.NUMBER,
        TokenKind.RPAREN,
        TokenKind.LBRACE,
        TokenKind.IDENT,
        TokenKind.EQUAL,
        TokenKind.IDENT,
        TokenKind.PLUS,
        TokenKind.NUMBER,
        TokenKind.RBRACE,
        TokenKind.RBRACE,
        TokenKind.EOF,
    ]


def test_lexes_function_definition_and_return_tokens() -> None:
    tokens = lex("function f(x) { return x + 1 }")

    assert [token.kind for token in tokens] == [
        TokenKind.FUNCTION,
        TokenKind.IDENT,
        TokenKind.LPAREN,
        TokenKind.IDENT,
        TokenKind.RPAREN,
        TokenKind.LBRACE,
        TokenKind.RETURN,
        TokenKind.IDENT,
        TokenKind.PLUS,
        TokenKind.NUMBER,
        TokenKind.RBRACE,
        TokenKind.EOF,
    ]
    assert [token.span.format_start() for token in tokens[:12]] == [
        "<inline>:1:1",
        "<inline>:1:10",
        "<inline>:1:11",
        "<inline>:1:12",
        "<inline>:1:13",
        "<inline>:1:15",
        "<inline>:1:17",
        "<inline>:1:24",
        "<inline>:1:26",
        "<inline>:1:28",
        "<inline>:1:30",
        "<inline>:1:31",
    ]


def test_lexes_break_and_continue_tokens() -> None:
    tokens = lex("BEGIN { while (1) { break; continue } }")

    assert [token.kind for token in tokens] == [
        TokenKind.BEGIN,
        TokenKind.LBRACE,
        TokenKind.WHILE,
        TokenKind.LPAREN,
        TokenKind.NUMBER,
        TokenKind.RPAREN,
        TokenKind.LBRACE,
        TokenKind.BREAK,
        TokenKind.SEMICOLON,
        TokenKind.CONTINUE,
        TokenKind.RBRACE,
        TokenKind.RBRACE,
        TokenKind.EOF,
    ]


def test_lexes_remaining_posix_keywords() -> None:
    tokens = lex("{ if (1) print 1; else do print 2 while (0); next; nextfile }\nBEGIN { exit 1 }")

    assert [token.kind for token in tokens if token.kind in {
        TokenKind.IF,
        TokenKind.ELSE,
        TokenKind.DO,
        TokenKind.WHILE,
        TokenKind.NEXT,
        TokenKind.NEXTFILE,
        TokenKind.EXIT,
    }] == [
        TokenKind.IF,
        TokenKind.ELSE,
        TokenKind.DO,
        TokenKind.WHILE,
        TokenKind.NEXT,
        TokenKind.NEXTFILE,
        TokenKind.EXIT,
    ]


def test_lexes_remaining_posix_operators_and_compound_assignments() -> None:
    tokens = lex(
        'BEGIN { x += 1; x -= 2; x *= 3; x /= 4; x %= 5; x ^= 6; '
        'print (1 ? 2 : 3) || (4 != 5) || (6 <= 7) || (8 > 9) || (10 >= 11); '
        'print (a ~ /x/); print (a !~ /y/); print !-x; ++x; x++; --y; y--; print 8 - 3 * 2 / 1 % 4 ^ 2 }'
    )

    assert TokenKind.PLUS_EQUAL in [token.kind for token in tokens]
    assert TokenKind.MINUS_EQUAL in [token.kind for token in tokens]
    assert TokenKind.STAR_EQUAL in [token.kind for token in tokens]
    assert TokenKind.SLASH_EQUAL in [token.kind for token in tokens]
    assert TokenKind.PERCENT_EQUAL in [token.kind for token in tokens]
    assert TokenKind.CARET_EQUAL in [token.kind for token in tokens]
    assert TokenKind.QUESTION in [token.kind for token in tokens]
    assert TokenKind.COLON in [token.kind for token in tokens]
    assert TokenKind.OR_OR in [token.kind for token in tokens]
    assert TokenKind.NOT_EQUAL in [token.kind for token in tokens]
    assert TokenKind.LESS_EQUAL in [token.kind for token in tokens]
    assert TokenKind.GREATER in [token.kind for token in tokens]
    assert TokenKind.GREATER_EQUAL in [token.kind for token in tokens]
    assert TokenKind.MATCH in [token.kind for token in tokens]
    assert TokenKind.NOT_MATCH in [token.kind for token in tokens]
    assert TokenKind.BANG in [token.kind for token in tokens]
    assert TokenKind.MINUS in [token.kind for token in tokens]
    assert TokenKind.STAR in [token.kind for token in tokens]
    assert TokenKind.SLASH in [token.kind for token in tokens]
    assert TokenKind.PERCENT in [token.kind for token in tokens]
    assert TokenKind.CARET in [token.kind for token in tokens]
    assert TokenKind.PLUS_PLUS in [token.kind for token in tokens]
    assert TokenKind.MINUS_MINUS in [token.kind for token in tokens]


def test_lexes_regex_after_new_operand_position_tokens() -> None:
    tokens = lex('BEGIN { print (1 ? /x/ : /y/); print !/z/; print (a ~ /q/); print (b !~ /w/) }')

    regex_tokens = [token for token in tokens if token.kind is TokenKind.REGEX]
    assert [token.text for token in regex_tokens] == ["/x/", "/y/", "/z/", "/q/", "/w/"]


def test_lexes_postfix_increment_before_division_operator() -> None:
    tokens = lex("BEGIN { x++ / 2; y-- / 3 }")

    assert [token.kind for token in tokens] == [
        TokenKind.BEGIN,
        TokenKind.LBRACE,
        TokenKind.IDENT,
        TokenKind.PLUS_PLUS,
        TokenKind.SLASH,
        TokenKind.NUMBER,
        TokenKind.SEMICOLON,
        TokenKind.IDENT,
        TokenKind.MINUS_MINUS,
        TokenKind.SLASH,
        TokenKind.NUMBER,
        TokenKind.RBRACE,
        TokenKind.EOF,
    ]


def test_lexes_mixed_begin_record_end_tokens() -> None:
    tokens = lex('BEGIN { print "start" }\n{ print $2 }\nEND { print "done" }')

    assert [token.kind for token in tokens] == [
        TokenKind.BEGIN,
        TokenKind.LBRACE,
        TokenKind.PRINT,
        TokenKind.STRING,
        TokenKind.RBRACE,
        TokenKind.NEWLINE,
        TokenKind.LBRACE,
        TokenKind.PRINT,
        TokenKind.DOLLAR,
        TokenKind.NUMBER,
        TokenKind.RBRACE,
        TokenKind.NEWLINE,
        TokenKind.END,
        TokenKind.LBRACE,
        TokenKind.PRINT,
        TokenKind.STRING,
        TokenKind.RBRACE,
        TokenKind.EOF,
    ]
    assert [token.display_text() for token in tokens] == [
        "BEGIN",
        "{",
        "print",
        '"start"',
        "}",
        "\n",
        "{",
        "print",
        "$",
        "2",
        "}",
        "\n",
        "END",
        "{",
        "print",
        '"done"',
        "}",
        None,
    ]


def test_rejects_unexpected_characters() -> None:
    with pytest.raises(LexError, match="unexpected character") as excinfo:
        lex("BEGIN { @ }")
    assert excinfo.value.span.format_start() == "<inline>:1:9"


def test_rejects_unterminated_string_literals() -> None:
    with pytest.raises(LexError, match="unterminated string literal") as excinfo:
        lex('BEGIN { print "hello }')
    assert excinfo.value.span.format_start() == "<inline>:1:15"


def test_rejects_unterminated_regex_literals() -> None:
    with pytest.raises(LexError, match="unterminated regex literal") as excinfo:
        lex("/foo")
    assert excinfo.value.span.format_start() == "<inline>:1:1"


def test_lex_preserves_file_locations_across_multiple_f_files() -> None:
    source = ProgramSource.from_files([
        ("first.awk", "BEGIN {"),
        ("second.awk", 'print "hello" }'),
    ])

    tokens = lex(source)

    assert [token.kind for token in tokens] == [
        TokenKind.BEGIN,
        TokenKind.LBRACE,
        TokenKind.NEWLINE,
        TokenKind.PRINT,
        TokenKind.STRING,
        TokenKind.RBRACE,
        TokenKind.EOF,
    ]
    assert [token.span.format_start() for token in tokens] == [
        "first.awk:1:1",
        "first.awk:1:7",
        "first.awk:1:8",
        "second.awk:1:1",
        "second.awk:1:7",
        "second.awk:1:15",
        "second.awk:1:16",
    ]

"""
Shared helpers for the fault-injection mutators.

The original mutators computed the insertion point as
`docstring_node.lineno + 1`, which is the SECOND line of the docstring,
not the line after it -- so injected "bugs" ended up as inert text
inside a string literal, invisible to ast/pyflakes/mypy. They also used
`target_node.lineno + 1` for functions with multi-line signatures, which
can land mid-signature and produce unparseable files.

`get_insertion_point` fixes both by deriving the insert line from the
AST's own body node line numbers instead of guessing.
"""
import ast


def get_insertion_point(target_node, lines):
    """
    Return (insert_idx, indent) where insert_idx is the 1-based line
    number a new statement should be inserted BEFORE (i.e. list index
    insert_idx - 1 in a 0-indexed `lines` list).

    Always lands in real function-body code:
      - after the docstring if one exists (never inside it)
      - after the full (possibly multi-line) signature otherwise
    """
    if not target_node.body:
        # Defensive fallback; shouldn't happen for a valid FunctionDef.
        return target_node.lineno + 1, "    "

    first_stmt = target_node.body[0]
    is_docstring = (
        isinstance(first_stmt, ast.Expr)
        and isinstance(first_stmt.value, ast.Constant)
        and isinstance(first_stmt.value.value, str)
    )

    if is_docstring:
        if len(target_node.body) > 1:
            # Insert right before the first real statement after the docstring.
            insert_idx = target_node.body[1].lineno
        else:
            # Docstring-only body (e.g. a `pass`-less stub) -- insert after it ends.
            insert_idx = first_stmt.end_lineno + 1
    else:
        # No docstring: insert right before the first real statement.
        # (Using the statement's own lineno -- not target_node.lineno + 1 --
        # is what makes this safe for multi-line signatures/decorators.)
        insert_idx = first_stmt.lineno

    indent = "    "
    first_body_line = first_stmt.lineno - 1
    if 0 <= first_body_line < len(lines) and lines[first_body_line].strip():
        line = lines[first_body_line]
        indent = line[: len(line) - len(line.lstrip())]

    return insert_idx, indent


def is_inside_string_literal(tree, target_line):
    """
    True if `target_line` (1-based) falls within the span of any string
    constant (docstring or otherwise) in the parsed tree. Used by the
    validator to catch the "inert injection" failure mode directly.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            start = node.lineno
            end = getattr(node, "end_lineno", node.lineno)
            if start <= target_line <= end:
                return True
    return False

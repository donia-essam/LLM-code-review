import ast
import difflib
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = PROJECT_ROOT / "code_review_project" / "data"


def find_clean_file(mutated_file: str) -> Optional[Path]:
    mutated_path = Path(mutated_file)

    parts = list(mutated_path.parts)

    try:
        index = parts.index("mutated_offbyone")
    except ValueError:
        return None

    relative_parts = parts[index + 1:]

    clean_path = (
        DATA_ROOT
        / "clean"
        / "algorithms"
        / Path(*relative_parts)
    )

    if clean_path.exists():
        return clean_path

    return None


def parse_code(path: Path):
    try:
        return ast.parse(
            path.read_text(encoding="utf-8")
        )
    except SyntaxError:
        return None


def normalize_line(line: str) -> str:
    return line.strip()


def is_off_by_one_change(
    clean_line: str,
    mutated_line: str,
) -> bool:

    clean = normalize_line(clean_line)
    mutated = normalize_line(mutated_line)

    if clean == mutated:
        return False

    # Direct numeric boundary changes.
    patterns = [
        (" + 1", " - 1"),
        (" - 1", " + 1"),

        (" + 1", ""),
        ("", " + 1"),

        (" - 1", ""),
        ("", " - 1"),

        ("<", "<="),
        ("<=", "<"),

        (">", ">="),
        (">=", ">"),
    ]

    for old, new in patterns:
        if old in clean and new in mutated:
            return True

    return False


def get_changed_lines(
    clean_path: Path,
    mutated_path: Path,
):
    clean_lines = clean_path.read_text(
        encoding="utf-8"
    ).splitlines()

    mutated_lines = mutated_path.read_text(
        encoding="utf-8"
    ).splitlines()

    matcher = difflib.SequenceMatcher(
        None,
        clean_lines,
        mutated_lines,
    )

    changes = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():

        if tag == "equal":
            continue

        clean_chunk = clean_lines[i1:i2]
        mutated_chunk = mutated_lines[j1:j2]

        changes.append({
            "tag": tag,
            "clean_start": i1 + 1,
            "clean_end": i2,
            "mutated_start": j1 + 1,
            "mutated_end": j2,
            "clean_lines": clean_chunk,
            "mutated_lines": mutated_chunk,
        })

    return changes


def reference_check(
    mutated_file: str,
    entity: str,
    line: int,
) -> bool:

    clean_path = find_clean_file(mutated_file)

    if clean_path is None:
        return False

    mutated_path = Path(mutated_file)

    if not mutated_path.exists():
        return False

    changes = get_changed_lines(
        clean_path,
        mutated_path,
    )

    if not changes:
        return False

    # Allow the LLM to point to a nearby affected line.
    line_start = max(1, line - 3)
    line_end = line + 3

    for change in changes:

        mutated_start = change["mutated_start"]
        mutated_end = change["mutated_end"]

        # Check whether the reported line is near the actual mutation.
        if mutated_end < line_start:
            continue

        if mutated_start > line_end:
            continue

        clean_lines = change["clean_lines"]
        mutated_lines = change["mutated_lines"]

        # ---------------------------------------------------------
        # Case 1: direct line replacement
        # ---------------------------------------------------------

        if len(clean_lines) == len(mutated_lines):

            for clean_line, mutated_line in zip(
                clean_lines,
                mutated_lines,
            ):

                if is_off_by_one_change(
                    clean_line,
                    mutated_line,
                ):
                    return True

        # ---------------------------------------------------------
        # Case 2: injected code
        # ---------------------------------------------------------

        if len(mutated_lines) > len(clean_lines):

            joined_mutated = "\n".join(
                mutated_lines
            ).lower()

            if (
                "injected off-by-one loop" in joined_mutated
                and "range(" in joined_mutated
            ):
                if entity in joined_mutated:
                    return True

                # For injected loops, the entity may simply
                # be the loop variable.
                for mutated_line in mutated_lines:
                    stripped = mutated_line.strip()

                    if (
                        stripped.startswith("for ")
                        and entity in stripped
                        and "range(" in stripped
                    ):
                        return True

        # ---------------------------------------------------------
        # Case 3: AST comparison for nearby changed code
        # ---------------------------------------------------------

        try:
            clean_tree = ast.parse(
                clean_path.read_text(
                    encoding="utf-8"
                )
            )

            mutated_tree = ast.parse(
                mutated_path.read_text(
                    encoding="utf-8"
                )
            )
        except SyntaxError:
            continue

        # Find range() calls involving the reported entity.
        for tree in (mutated_tree,):

            for node in ast.walk(tree):

                if not isinstance(node, ast.Call):
                    continue

                if not isinstance(node.func, ast.Name):
                    continue

                if node.func.id != "range":
                    continue

                node_line = getattr(
                    node,
                    "lineno",
                    0,
                )

                if not (
                    line_start
                    <= node_line
                    <= line_end
                ):
                    continue

                try:
                    expression = ast.unparse(node)
                except Exception:
                    continue

                if entity not in expression:
                    continue

                if "+ 1" in expression or "- 1" in expression:
                    return True

    return False
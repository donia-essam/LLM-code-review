import ast
from typing import Optional


def parse_code(code: str) -> Optional[ast.AST]:
    """Parse Python source code into an AST."""
    try:
        return ast.parse(code)
    except SyntaxError:
        return None


def _normalize_expression(expression: str) -> str:
    """Normalize a Python expression so formatting differences do not matter."""
    try:
        tree = ast.parse(expression, mode="eval")
        return ast.unparse(tree.body)
    except (SyntaxError, ValueError):
        return expression.strip()


def entity_exists(tree: ast.AST, entity: str) -> bool:
    """Check whether a name or expression exists anywhere in the AST."""
    if tree is None or not entity:
        return False

    normalized_entity = _normalize_expression(entity)

    for node in ast.walk(tree):
        # Simple identifiers such as x, data, items
        if isinstance(node, ast.Name) and node.id == entity:
            return True

        # Expressions such as items[i] or range(len(data) + 1)
        try:
            if ast.unparse(node) == normalized_entity:
                return True
        except (AttributeError, ValueError):
            continue

    return False


def entity_exists_at_line(tree: ast.AST, entity: str, line: int) -> bool:
    """
    Check whether the entity occurs at, or is contained by,
    a statement covering the reported source line.

    Supports both simple names and attributes such as:
        tree
        self.tree
        upper_sqrt
        self.upper_sqrt
    """
    if tree is None or not entity or line < 1:
        return False

    normalized_entity = _normalize_expression(entity)

    for node in ast.walk(tree):
        node_line = getattr(node, "lineno", None)
        end_line = getattr(node, "end_lineno", node_line)

        if node_line is None:
            continue

        if not (node_line <= line <= (end_line or node_line)):
            continue

        # 1. Exact simple-name match
        if isinstance(node, ast.Name) and node.id == entity:
            return True

        # 2. Exact expression match
        try:
            if ast.unparse(node) == normalized_entity:
                return True
        except (AttributeError, ValueError):
            pass

        # 3. Attribute match:
        #    If entity is "tree", match self.tree
        #    If entity is "upper_sqrt", match self.upper_sqrt
        for child in ast.walk(node):
            if isinstance(child, ast.Attribute):
                if child.attr == entity:
                    return True

    return False


def verify_entity(code: str, entity: str, line: int) -> dict:
    """Run the AST existence checks for one LLM claim."""
    tree = parse_code(code)

    if tree is None:
        return {
            "valid_syntax": False,
            "entity_exists": False,
            "entity_at_line": False,
        }

    return {
        "valid_syntax": True,
        "entity_exists": entity_exists(tree, entity),
        "entity_at_line": entity_exists_at_line(tree, entity, line),
    }


def entity_exists_nearby_line(
    tree: ast.AST,
    entity: str,
    line: int,
    max_distance: int = 3,
) -> bool:
    """
    Check whether the entity occurs within a small distance
    of the reported source line.
    """
    if tree is None or not entity or line < 1:
        return False

    normalized_entity = _normalize_expression(entity)

    for node in ast.walk(tree):
        node_line = getattr(node, "lineno", None)
        end_line = getattr(node, "end_lineno", node_line)

        if node_line is None:
            continue

        if end_line is None:
            end_line = node_line

        # Nearby source region
        if abs(node_line - line) > max_distance:
            if not (node_line <= line <= end_line):
                continue

        if isinstance(node, ast.Name) and node.id == entity:
            return True

        try:
            if ast.unparse(node) == normalized_entity:
                return True
        except (AttributeError, ValueError):
            continue

    return False


def verify_entity_nearby_line(
    code: str,
    entity: str,
    line: int,
    max_distance: int = 3,
) -> bool:
    """Check whether an entity exists near the reported line."""
    tree = parse_code(code)

    if tree is None:
        return False

    return entity_exists_nearby_line(
        tree,
        entity,
        line,
        max_distance,
    )
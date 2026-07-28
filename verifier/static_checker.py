import ast
from typing import Optional


SUPPORTED_CLAIMS = {
    "unused_variable",
    "null_safety_violation",
    "off_by_one_bound",
}


def _parse(code: str) -> Optional[ast.AST]:
    """Parse Python code safely."""
    try:
        return ast.parse(code)
    except SyntaxError:
        return None


def _base_name(expression: str) -> Optional[str]:
    """
    Extract the root variable name from an expression.

    Examples:
        x                  -> x
        items[i]           -> items
        obj.value          -> obj
        temp_var.strip()   -> temp_var
    """
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        return None

    node = tree.body

    # Unwrap function/method calls.
    if isinstance(node, ast.Call):
        node = node.func

    # Unwrap attributes and subscripts until reaching the root.
    while isinstance(node, (ast.Subscript, ast.Attribute)):
        node = node.value

        # Handle nested calls if present.
        if isinstance(node, ast.Call):
            node = node.func

    if isinstance(node, ast.Name):
        return node.id

    return None


def check_unused_variable(code: str, entity: str) -> bool:
    """Check whether a variable is assigned but never read."""
    tree = _parse(code)

    if tree is None:
        return False

    variable = _base_name(entity) or entity

    assigned = False
    loaded = False

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == variable:
            if isinstance(node.ctx, ast.Store):
                assigned = True
            elif isinstance(node.ctx, ast.Load):
                loaded = True

    return assigned and not loaded


def check_null_safety_violation(code: str, entity: str) -> bool:
    """
    Check whether the reported entity performs a dereference/index
    on a variable that may be None.

    Supports:
    - variable explicitly assigned None
    - function parameters dereferenced without an obvious None guard
    """

    tree = _parse(code)

    if tree is None:
        return False

    variable = _base_name(entity)

    if variable is None:
        return False

    try:
        normalized_entity = ast.unparse(
            ast.parse(entity, mode="eval").body
        )
    except (SyntaxError, ValueError):
        return False

    # Confirm that the exact reported dereference exists.
    entity_found = False

    for node in ast.walk(tree):
        if not isinstance(
            node,
            (ast.Call, ast.Attribute, ast.Subscript),
        ):
            continue

        try:
            if ast.unparse(node) == normalized_entity:
                entity_found = True
                break
        except (AttributeError, ValueError):
            continue

    if not entity_found:
        return False

    # Case 1: variable is explicitly assigned None.
    for node in ast.walk(tree):

        if isinstance(node, ast.Assign):
            if (
                isinstance(node.value, ast.Constant)
                and node.value.value is None
            ):
                for target in node.targets:
                    if (
                        isinstance(target, ast.Name)
                        and target.id == variable
                    ):
                        return True

        if isinstance(node, ast.AnnAssign):
            if (
                isinstance(node.target, ast.Name)
                and node.target.id == variable
                and isinstance(node.value, ast.Constant)
                and node.value.value is None
            ):
                return True

    # Case 2: variable is a function parameter.
    is_parameter = False

    for node in ast.walk(tree):
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        ):
            parameters = (
                list(node.args.posonlyargs)
                + list(node.args.args)
                + list(node.args.kwonlyargs)
            )

            if node.args.vararg is not None:
                parameters.append(node.args.vararg)

            if node.args.kwarg is not None:
                parameters.append(node.args.kwarg)

            if any(
                parameter.arg == variable
                for parameter in parameters
            ):
                is_parameter = True
                break

    if not is_parameter:
        return False

    # Look for an obvious None guard.
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue

        try:
            comparison = ast.unparse(node)
        except (AttributeError, ValueError):
            continue

        compact = comparison.replace(" ", "")

        guarded_patterns = {
            f"{variable}isnotNone",
            f"{variable}!=None",
            f"{variable}isNone",
            f"{variable}==None",
        }

        if compact in guarded_patterns:
            return False

    return True


def check_off_by_one_bound(code: str, entity: str) -> bool:
    """
    Detect supported +1 off-by-one mutations inside range().

    Examples:
        range(length + 1)
        range(len(data) + 1)
        range(len(data + 1))
        range(len(data + 1) - 2)
        range(1 << n + 1)
    """
    tree = _parse(code)

    if tree is None:
        return False

    try:
        normalized_entity = ast.unparse(
            ast.parse(entity, mode="eval").body
        )
    except (SyntaxError, ValueError):
        normalized_entity = entity.strip()

    def contains_plus_one(node: ast.AST) -> bool:
        """
        Return True when an expression contains an addition
        whose right operand is the integer constant 1.
        """
        for child in ast.walk(node):
            if not isinstance(child, ast.BinOp):
                continue

            if not isinstance(child.op, ast.Add):
                continue

            if (
                isinstance(child.right, ast.Constant)
                and child.right.value == 1
            ):
                return True

        return False

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        if (
            not isinstance(node.func, ast.Name)
            or node.func.id != "range"
        ):
            continue

        try:
            if ast.unparse(node) != normalized_entity:
                continue
        except (AttributeError, ValueError):
            continue

        for argument in node.args:
            if contains_plus_one(argument):
                return True

    return False

def verify_claim(code: str, entity: str, claim: str) -> bool:
    """Dispatch a claim to its corresponding static-analysis check."""

    if claim == "unused_variable":
        return check_unused_variable(code, entity)

    if claim == "null_safety_violation":
        return check_null_safety_violation(code, entity)

    if claim == "off_by_one_bound":
        return check_off_by_one_bound(code, entity)

    return False
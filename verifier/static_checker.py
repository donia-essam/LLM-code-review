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


def check_unused_variable(
    code: str,
    entity: str,
    line: int,
) -> bool:
    """
    Check whether the reported variable is assigned on the
    reported line and never read afterward in the same scope.
    """
    tree = _parse(code)

    if tree is None:
        return False

    variable = entity.strip()

    if not variable:
        return False

    # Find the assignment to the reported variable on the reported line.
    target_assignment = None

    for node in ast.walk(tree):
        if not isinstance(node, ast.Name):
            continue

        if node.id != variable:
            continue

        if not isinstance(node.ctx, ast.Store):
            continue

        if getattr(node, "lineno", None) != line:
            continue

        target_assignment = node
        break

    if target_assignment is None:
        return False

    # Find the enclosing scope of the reported assignment.
    scope = None

    for node in ast.walk(tree):
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef,
                ast.Module,
            ),
        ):
            for child in ast.walk(node):
                if child is target_assignment:
                    scope = node
                    break

            if scope is not None:
                break

    if scope is None:
        return False

    # Check whether the variable is loaded after the reported assignment
    # inside the same scope.
    assignment_line = getattr(target_assignment, "lineno", line)

    for node in ast.walk(scope):
        if not isinstance(node, ast.Name):
            continue

        if node.id != variable:
            continue

        if not isinstance(node.ctx, ast.Load):
            continue

        if getattr(node, "lineno", 0) > assignment_line:
            return False

    return True


def check_null_safety_violation(
    code: str,
    entity: str,
    line: int,
) -> bool:
    """
    Check whether the reported entity is dereferenced/indexed on
    the reported line while the variable may be None.

    A None guard only protects a dereference if the guard occurs
    before the reported dereference in the same function scope.
    """
    tree = _parse(code)

    if tree is None:
        return False

    variable = entity.strip()

    if not variable:
        return False

    # ---------------------------------------------------------
    # Find the reported dereference on the reported line.
    # ---------------------------------------------------------

    target_node = None

    for node in ast.walk(tree):
        if not isinstance(
            node,
            (ast.Call, ast.Attribute, ast.Subscript),
        ):
            continue

        if getattr(node, "lineno", None) != line:
            continue

        for child in ast.walk(node):
            if isinstance(child, ast.Name) and child.id == variable:
                target_node = node
                break

        if target_node is not None:
            break

    if target_node is None:
        return False

    # ---------------------------------------------------------
    # Find the function containing the reported dereference.
    # ---------------------------------------------------------

    containing_function = None

    for node in ast.walk(tree):
        if not isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        ):
            continue

        start = getattr(node, "lineno", None)
        end = getattr(node, "end_lineno", start)

        if (
            start is not None
            and end is not None
            and start <= line <= end
        ):
            containing_function = node
            break

    # ---------------------------------------------------------
    # Case 1:
    # Explicitly assigned None before the dereference.
    # ---------------------------------------------------------

    for node in ast.walk(
        containing_function if containing_function is not None else tree
    ):
        if getattr(node, "lineno", None) is None:
            continue

        if node.lineno >= line:
            continue

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

    # ---------------------------------------------------------
    # Case 2:
    # Variable is a function parameter.
    # ---------------------------------------------------------

    is_parameter = False

    if containing_function is not None:
        parameters = (
            list(containing_function.args.posonlyargs)
            + list(containing_function.args.args)
            + list(containing_function.args.kwonlyargs)
        )

        if containing_function.args.vararg is not None:
            parameters.append(containing_function.args.vararg)

        if containing_function.args.kwarg is not None:
            parameters.append(containing_function.args.kwarg)

        is_parameter = any(
            parameter.arg == variable
            for parameter in parameters
        )

    if not is_parameter:
        return False

    # ---------------------------------------------------------
    # Look for a None guard BEFORE the reported dereference.
    #
    # A guard after the dereference does NOT protect it.
    # ---------------------------------------------------------

    guarded_patterns = {
        f"{variable}isnotNone",
        f"{variable}!=None",
        f"{variable}isNone",
        f"{variable}==None",
    }

    search_tree = (
        containing_function
        if containing_function is not None
        else tree
    )

    for node in ast.walk(search_tree):
        if not isinstance(node, ast.Compare):
            continue

        node_line = getattr(node, "lineno", None)

        if node_line is None or node_line >= line:
            continue

        try:
            comparison = ast.unparse(node)
        except (AttributeError, ValueError):
            continue

        compact = comparison.replace(" ", "")

        if compact in guarded_patterns:
            return False

    # No protective guard exists before the dereference.
    return True

def check_off_by_one_bound(
    code: str,
    entity: str,
    line: int,
) -> bool:
    """
    Detect common off-by-one boundary mutations.

    Supported patterns:
    - range(x + 1)
    - range(x - 1)
    - expressions such as (1 << n + 1)
    - comparisons: < <=> > >=
    - boundary expressions such as len(arr + 1)
    """

    tree = _parse(code)

    if tree is None:
        return False

    variable = entity.strip()

    if not variable:
        return False

    # ---------------------------------------------------------
    # Helper: does an expression contain the reported entity?
    # ---------------------------------------------------------

    def contains_entity(node: ast.AST) -> bool:
        for child in ast.walk(node):
            if isinstance(child, ast.Name):
                if child.id == variable:
                    return True

        return False

    # ---------------------------------------------------------
    # Helper: detect +1 / -1 arithmetic
    # ---------------------------------------------------------

    def has_boundary_change(node: ast.AST) -> bool:
        for child in ast.walk(node):

            if not isinstance(child, ast.BinOp):
                continue

            # x + 1
            if isinstance(child.op, ast.Add):
                if (
                    isinstance(child.right, ast.Constant)
                    and child.right.value == 1
                ):
                    return True

            # x - 1
            if isinstance(child.op, ast.Sub):
                if (
                    isinstance(child.right, ast.Constant)
                    and child.right.value == 1
                ):
                    return True

        return False

    # ---------------------------------------------------------
    # 1. range(...) boundary mutations
    # ---------------------------------------------------------

    for node in ast.walk(tree):

        if not isinstance(node, ast.Call):
            continue

        if not isinstance(node.func, ast.Name):
            continue

        if node.func.id != "range":
            continue

        node_line = getattr(node, "lineno", None)

        # Allow the reported line to be a nearby line.
        if node_line is None:
            continue

        if abs(node_line - line) > 3:
            continue

        if not contains_entity(node):
            continue

        if has_boundary_change(node):
            return True

    # ---------------------------------------------------------
    # 2. General arithmetic expressions
    #
    # Handles cases such as:
    #
    #     1 << n + 1
    #     len(arr + 1)
    #     len(current + 1)
    # ---------------------------------------------------------

    for node in ast.walk(tree):

        node_line = getattr(node, "lineno", None)

        if node_line is None:
            continue

        if abs(node_line - line) > 3:
            continue

        if not contains_entity(node):
            continue

        if has_boundary_change(node):
            return True

    # ---------------------------------------------------------
    # 3. Comparison boundary mutations
    #
    # Examples:
    #
    #     x < y
    #     x <= y
    #     x > y
    #     x >= y
    #
    # The static checker cannot know whether the comparison
    # is mutated without the clean reference, but this handles
    # explicit boundary comparisons involving the reported entity.
    # ---------------------------------------------------------

    for node in ast.walk(tree):

        if not isinstance(node, ast.Compare):
            continue

        node_line = getattr(node, "lineno", None)

        if node_line is None:
            continue

        if abs(node_line - line) > 3:
            continue

        if not contains_entity(node):
            continue

        for operator in node.ops:

            if isinstance(
                operator,
                (
                    ast.Lt,
                    ast.LtE,
                    ast.Gt,
                    ast.GtE,
                ),
            ):
                return True

    return False

def verify_claim(
    code: str,
    entity: str,
    claim: str,
    line: int,
) -> bool:
    """Dispatch a claim to its corresponding static-analysis check."""

    if claim == "unused_variable":
        return check_unused_variable(code, entity, line)

    if claim == "null_safety_violation":
        return check_null_safety_violation(code, entity, line)

    if claim == "off_by_one_bound":
        return check_off_by_one_bound(code, entity, line)

    return False
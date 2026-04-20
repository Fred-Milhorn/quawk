"""Stable text formatting for AST inspection output."""

from __future__ import annotations

from .ast import (
    ArrayIndexExpr,
    ArrayLValue,
    AssignExpr,
    AssignOp,
    AssignStmt,
    BeginPattern,
    BinaryExpr,
    BlockStmt,
    BreakStmt,
    CallExpr,
    ConditionalExpr,
    ContinueStmt,
    DeleteStmt,
    DoWhileStmt,
    EndPattern,
    ExitStmt,
    Expr,
    ExprPattern,
    ExprStmt,
    FieldExpr,
    FieldLValue,
    ForInStmt,
    ForStmt,
    FunctionDef,
    GetlineExpr,
    IfStmt,
    LValue,
    NameExpr,
    NameLValue,
    NextFileStmt,
    NextStmt,
    NumericLiteralExpr,
    Pattern,
    PatternAction,
    PostfixExpr,
    PrintfStmt,
    PrintStmt,
    Program,
    RangePattern,
    RegexLiteralExpr,
    ReturnStmt,
    Stmt,
    StringLiteralExpr,
    UnaryExpr,
    WhileStmt,
)


def format_program(program: Program) -> str:
    """Render the AST in a stable text form for `quawk --parse`."""
    lines = [f"Program span={program.span.format_start()}"]
    for item in program.items:
        if isinstance(item, FunctionDef):
            lines.append(f"  FunctionDef span={item.span.format_start()} name={item.name!r}")
            if item.params:
                lines.append(f"    Params {', '.join(repr(param) for param in item.params)}")
            lines.append(f"    Action span={item.body.span.format_start()}")
            for statement in item.body.statements:
                lines.extend(format_statement(statement, "      "))
            continue
        lines.append(f"  PatternAction span={item.span.format_start()}")
        if item.pattern is not None:
            lines.extend(format_pattern(item.pattern, "    "))
        if item.action is not None:
            lines.append(f"    Action span={item.action.span.format_start()}")
            for statement in item.action.statements:
                lines.extend(format_statement(statement, "      "))
    return "\n".join(lines) + "\n"


def format_pattern(pattern: Pattern, indent: str) -> list[str]:
    """Render one pattern node for stable inspection output."""
    match pattern:
        case BeginPattern():
            return [f"{indent}BeginPattern span={pattern.span.format_start()}"]
        case EndPattern():
            return [f"{indent}EndPattern span={pattern.span.format_start()}"]
        case ExprPattern():
            lines = [f"{indent}ExprPattern span={pattern.span.format_start()}"]
            lines.extend(format_expression(pattern.test, indent + "  "))
            return lines
        case RangePattern():
            lines = [f"{indent}RangePattern span={pattern.span.format_start()}"]
            lines.append(f"{indent}  Left")
            lines.extend(format_pattern(pattern.left, indent + "    "))
            lines.append(f"{indent}  Right")
            lines.extend(format_pattern(pattern.right, indent + "    "))
            return lines
    raise AssertionError(f"unhandled pattern type: {type(pattern)!r}")


def format_lvalue(target: LValue, indent: str) -> list[str]:
    """Render one lvalue node for stable inspection output."""
    match target:
        case NameLValue():
            return [f"{indent}NameLValue span={target.span.format_start()} name={target.name!r}"]
        case ArrayLValue():
            lines = [f"{indent}ArrayLValue span={target.span.format_start()} name={target.name!r}"]
            for subscript in target.subscripts:
                lines.extend(format_expression(subscript, indent + "  "))
            return lines
        case FieldLValue():
            lines = [f"{indent}FieldLValue span={target.span.format_start()}"]
            lines.extend(format_expression(target.index, indent + "  "))
            return lines
    raise AssertionError(f"unhandled lvalue type: {type(target)!r}")


def format_assign_op(op: AssignOp) -> str:
    """Return the stable inspection name for one assignment operator."""
    match op:
        case AssignOp.PLAIN:
            return "PlainAssign"
        case AssignOp.ADD:
            return "AddAssign"
        case AssignOp.SUB:
            return "SubAssign"
        case AssignOp.MUL:
            return "MulAssign"
        case AssignOp.DIV:
            return "DivAssign"
        case AssignOp.MOD:
            return "ModAssign"
        case AssignOp.POW:
            return "PowAssign"
    raise AssertionError(f"unhandled assign op: {op!r}")


def format_statement(statement: Stmt, indent: str) -> list[str]:
    """Render a statement node for stable `--parse` inspection output."""
    match statement:
        case PrintStmt():
            lines = [f"{indent}PrintStmt span={statement.span.format_start()}"]
            for argument in statement.arguments:
                lines.extend(format_expression(argument, indent + "  "))
            if statement.redirect is not None:
                lines.append(f"{indent}  Redirect kind={statement.redirect.kind.name}")
                lines.extend(format_expression(statement.redirect.target, indent + "    "))
            return lines
        case PrintfStmt():
            lines = [f"{indent}PrintfStmt span={statement.span.format_start()}"]
            for argument in statement.arguments:
                lines.extend(format_expression(argument, indent + "  "))
            if statement.redirect is not None:
                lines.append(f"{indent}  Redirect kind={statement.redirect.kind.name}")
                lines.extend(format_expression(statement.redirect.target, indent + "    "))
            return lines
        case AssignStmt():
            lines = [
                (
                    f"{indent}AssignStmt span={statement.span.format_start()} "
                    f"op={format_assign_op(statement.op)}"
                )
            ]
            lines.extend(format_lvalue(statement.target, indent + "  "))
            lines.append(f"{indent}  Value")
            lines.extend(format_expression(statement.value, indent + "    "))
            return lines
        case ExprStmt():
            lines = [f"{indent}ExprStmt span={statement.span.format_start()}"]
            lines.extend(format_expression(statement.value, indent + "  "))
            return lines
        case BlockStmt():
            lines = [f"{indent}BlockStmt span={statement.span.format_start()}"]
            for nested in statement.statements:
                lines.extend(format_statement(nested, indent + "  "))
            return lines
        case BreakStmt():
            return [f"{indent}BreakStmt span={statement.span.format_start()}"]
        case ContinueStmt():
            return [f"{indent}ContinueStmt span={statement.span.format_start()}"]
        case NextStmt():
            return [f"{indent}NextStmt span={statement.span.format_start()}"]
        case NextFileStmt():
            return [f"{indent}NextFileStmt span={statement.span.format_start()}"]
        case ExitStmt():
            lines = [f"{indent}ExitStmt span={statement.span.format_start()}"]
            if statement.value is not None:
                lines.extend(format_expression(statement.value, indent + "  "))
            return lines
        case DeleteStmt():
            lines = [f"{indent}DeleteStmt span={statement.span.format_start()}"]
            lines.extend(format_lvalue(statement.target, indent + "  "))
            return lines
        case IfStmt():
            lines = [f"{indent}IfStmt span={statement.span.format_start()}"]
            lines.append(f"{indent}  Condition")
            lines.extend(format_expression(statement.condition, indent + "    "))
            lines.append(f"{indent}  Then")
            lines.extend(format_statement(statement.then_branch, indent + "    "))
            if statement.else_branch is not None:
                lines.append(f"{indent}  Else")
                lines.extend(format_statement(statement.else_branch, indent + "    "))
            return lines
        case WhileStmt():
            lines = [f"{indent}WhileStmt span={statement.span.format_start()}"]
            lines.append(f"{indent}  Condition")
            lines.extend(format_expression(statement.condition, indent + "    "))
            lines.append(f"{indent}  Body")
            lines.extend(format_statement(statement.body, indent + "    "))
            return lines
        case DoWhileStmt():
            lines = [f"{indent}DoWhileStmt span={statement.span.format_start()}"]
            lines.append(f"{indent}  Body")
            lines.extend(format_statement(statement.body, indent + "    "))
            lines.append(f"{indent}  Condition")
            lines.extend(format_expression(statement.condition, indent + "    "))
            return lines
        case ForStmt():
            lines = [f"{indent}ForStmt span={statement.span.format_start()}"]
            if statement.init:
                lines.append(f"{indent}  Init")
                for expression in statement.init:
                    lines.extend(format_expression(expression, indent + "    "))
            if statement.condition is not None:
                lines.append(f"{indent}  Condition")
                lines.extend(format_expression(statement.condition, indent + "    "))
            if statement.update:
                lines.append(f"{indent}  Update")
                for expression in statement.update:
                    lines.extend(format_expression(expression, indent + "    "))
            lines.append(f"{indent}  Body")
            lines.extend(format_statement(statement.body, indent + "    "))
            return lines
        case ForInStmt():
            lines = [
                (
                    f"{indent}ForInStmt span={statement.span.format_start()} "
                    f"name={statement.name!r}"
                )
            ]
            lines.append(f"{indent}  Iterable")
            lines.extend(format_expression(statement.iterable, indent + "    "))
            lines.append(f"{indent}  Body")
            lines.extend(format_statement(statement.body, indent + "    "))
            return lines
        case ReturnStmt():
            lines = [f"{indent}ReturnStmt span={statement.span.format_start()}"]
            if statement.value is not None:
                lines.extend(format_expression(statement.value, indent + "  "))
            return lines
    raise AssertionError(f"unhandled statement type: {type(statement)!r}")


def format_expression(expression: Expr, indent: str) -> list[str]:
    """Render an expression node for stable `--parse` inspection output."""
    match expression:
        case StringLiteralExpr():
            return [f"{indent}StringLiteralExpr span={expression.span.format_start()} value={expression.value!r}"]
        case NumericLiteralExpr():
            return [f"{indent}NumericLiteralExpr span={expression.span.format_start()} value={expression.value!r}"]
        case RegexLiteralExpr():
            return [f"{indent}RegexLiteralExpr span={expression.span.format_start()} raw_text={expression.raw_text!r}"]
        case NameExpr():
            return [f"{indent}NameExpr span={expression.span.format_start()} name={expression.name!r}"]
        case FieldExpr():
            if isinstance(expression.index, int):
                return [f"{indent}FieldExpr span={expression.span.format_start()} index={expression.index}"]
            lines = [f"{indent}FieldExpr span={expression.span.format_start()}"]
            lines.extend(format_expression(expression.index, indent + "  "))
            return lines
        case CallExpr():
            lines = [f"{indent}CallExpr span={expression.span.format_start()} function={expression.function!r}"]
            for argument in expression.args:
                lines.extend(format_expression(argument, indent + "  "))
            return lines
        case ArrayIndexExpr():
            lines = [
                (
                    f"{indent}ArrayIndexExpr span={expression.span.format_start()} "
                    f"array_name={expression.array_name!r}"
                )
            ]
            for subscript in expression.subscripts:
                lines.extend(format_expression(subscript, indent + "  "))
            return lines
        case GetlineExpr():
            lines = [f"{indent}GetlineExpr span={expression.span.format_start()}"]
            if expression.target is not None:
                lines.append(f"{indent}  Target")
                lines.extend(format_lvalue(expression.target, indent + "    "))
            if expression.source is not None:
                lines.append(f"{indent}  Source")
                lines.extend(format_expression(expression.source, indent + "    "))
            return lines
        case BinaryExpr():
            lines = [f"{indent}BinaryExpr span={expression.span.format_start()} op={expression.op.name}"]
            lines.extend(format_expression(expression.left, indent + "  "))
            lines.extend(format_expression(expression.right, indent + "  "))
            return lines
        case ConditionalExpr():
            lines = [f"{indent}ConditionalExpr span={expression.span.format_start()}"]
            lines.append(f"{indent}  Test")
            lines.extend(format_expression(expression.test, indent + "    "))
            lines.append(f"{indent}  IfTrue")
            lines.extend(format_expression(expression.if_true, indent + "    "))
            lines.append(f"{indent}  IfFalse")
            lines.extend(format_expression(expression.if_false, indent + "    "))
            return lines
        case AssignExpr():
            lines = [
                (
                    f"{indent}AssignExpr span={expression.span.format_start()} "
                    f"op={format_assign_op(expression.op)}"
                )
            ]
            lines.extend(format_lvalue(expression.target, indent + "  "))
            lines.append(f"{indent}  Value")
            lines.extend(format_expression(expression.value, indent + "    "))
            return lines
        case UnaryExpr():
            lines = [f"{indent}UnaryExpr span={expression.span.format_start()} op={expression.op.name}"]
            lines.extend(format_expression(expression.operand, indent + "  "))
            return lines
        case PostfixExpr():
            lines = [f"{indent}PostfixExpr span={expression.span.format_start()} op={expression.op.name}"]
            lines.extend(format_expression(expression.operand, indent + "  "))
            return lines
    raise AssertionError(f"unhandled expression type: {type(expression)!r}")

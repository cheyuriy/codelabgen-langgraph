"""The calculator agent's tools: add, multiply and divide."""

from langchain_core.tools import tool

# region arithmetic_tools
# @tool turns each function into a BaseTool with .name (the function name),
# .description (the docstring, which the model reads) and .args (a schema built
# from the type hints). Tools are runnables: add.invoke({"a": 3, "b": 4}) returns 7.


@tool
def add(a: int, b: int) -> int:
    """Add `a` and `b`.

    Args:
        a: First int.
        b: Second int.
    """
    return a + b


@tool
def multiply(a: int, b: int) -> int:
    """Multiply `a` and `b`.

    Args:
        a: First int.
        b: Second int.
    """
    return a * b


@tool
def divide(a: int, b: int) -> float:
    """Divide `a` by `b`.

    Args:
        a: First int.
        b: Second int.
    """
    return a / b


# The list handed both to the model (bind_tools) and to ToolNode.
TOOLS = [add, multiply, divide]
# endregion

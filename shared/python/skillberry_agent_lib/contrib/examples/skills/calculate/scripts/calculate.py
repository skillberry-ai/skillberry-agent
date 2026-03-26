def calculate(expression: str):
    """
    Calculate the result of a mathematical expression.

    Args:
        expression (str): The mathematical expression to calculate, such as '2 + 2'. The expression can contain numbers, operators (+, -, *, /), parentheses, and spaces.

    Returns:
        The result of the mathematical expression.

    Raises:
        ValueError: If the expression is invalid.
    """
    if not all(char in "0123456789+-*/(). " for char in expression):
        raise ValueError("Invalid characters in expression")
    return str(round(float(eval(expression, {"__builtins__": None}, {})), 2))


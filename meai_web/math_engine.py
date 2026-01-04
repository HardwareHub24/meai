from sympy import symbols, solve, simplify
from sympy.parsing.sympy_parser import parse_expr
from sympy.core.sympify import SympifyError

MAX_LEN = 200  # guardrail against abuse

def solve_expr(expr: str, var: str = "x"):
    if len(expr) > MAX_LEN:
        return {"error": "expression too long"}
    try:
        x = symbols(var)
        parsed = parse_expr(expr, evaluate=True)
        result = solve(parsed, x)
        return {"result": str(result)}
    except (SympifyError, Exception) as e:
        return {"error": str(e)}

def simplify_expr(expr: str):
    if len(expr) > MAX_LEN:
        return {"error": "expression too long"}
    try:
        parsed = parse_expr(expr, evaluate=True)
        result = simplify(parsed)
        return {"result": str(result)}
    except (SympifyError, Exception) as e:
        return {"error": str(e)}

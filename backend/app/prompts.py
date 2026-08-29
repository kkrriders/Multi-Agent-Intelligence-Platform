import re

_VAR_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


class MissingVariableError(Exception):
    pass


def extract_variables(body: str) -> list[str]:
    """Ordered, de-duplicated {{name}} variable names in a template body."""
    seen: dict[str, None] = {}
    for match in _VAR_RE.finditer(body):
        seen.setdefault(match.group(1), None)
    return list(seen)


def render_template(body: str, variables: dict) -> str:
    """Replace every {{name}} with str(variables[name]); raise
    MissingVariableError(name) if a {{name}} has no value provided."""

    def repl(match: re.Match) -> str:
        name = match.group(1)
        if name not in variables:
            raise MissingVariableError(name)
        return str(variables[name])

    return _VAR_RE.sub(repl, body)

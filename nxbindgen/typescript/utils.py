import re

__all__ = [
    'to_python',
]


def to_python(name: str) -> str:
    # TODO: Compile REs externally
    if name.isupper():
        return name
    name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    name = re.sub('__([A-Z])', r'_\1', name)
    name = re.sub('([a-z0-9])([A-Z])', r'\1_\2', name)
    return name.lower()

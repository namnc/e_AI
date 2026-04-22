"""Shared utilities for the meta-framework."""

import json


def extract_json(text: str) -> dict | list | None:
    """Extract the first JSON object or array from LLM output.

    Finds whichever appears first in the text — object ({...}) or array ([...]).
    Handles nested structures, escaped quotes, and markdown code blocks.
    Returns None if no valid JSON found.
    """
    # Find the earliest { or [ in the text
    obj_start = text.find('{')
    arr_start = text.find('[')

    # Determine search order based on which appears first
    if obj_start == -1 and arr_start == -1:
        return None
    elif obj_start == -1:
        pairs = [('[', ']')]
    elif arr_start == -1:
        pairs = [('{', '}')]
    elif arr_start < obj_start:
        pairs = [('[', ']'), ('{', '}')]
    else:
        pairs = [('{', '}'), ('[', ']')]

    for start_char, end_char in pairs:
        start = text.find(start_char)
        if start == -1:
            continue
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == start_char:
                depth += 1
            elif ch == end_char:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
    return None

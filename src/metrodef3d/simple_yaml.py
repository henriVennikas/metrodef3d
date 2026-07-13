"""Small YAML subset reader used when PyYAML is unavailable.

It supports the recipe shape used by metrodef3d examples: nested mappings,
lists introduced with ``-``, comments, quoted strings, numbers, booleans, and
nulls. When PyYAML is installed, recipe loading prefers that instead.
"""

import ast
from typing import Any, Dict, List, Tuple

from .errors import RecipeError


def loads(text: str) -> Dict[str, Any]:
    lines = _logical_lines(text)
    if not lines:
        return {}
    root, next_index = _parse_block(lines, 0, lines[0][0])
    if next_index != len(lines):
        raise RecipeError("Could not parse complete YAML document.")
    if not isinstance(root, dict):
        raise RecipeError("Recipe YAML must contain a top-level mapping.")
    return root


def _logical_lines(text: str) -> List[Tuple[int, str]]:
    result = []
    for raw in text.splitlines():
        raw = _strip_comment(raw).rstrip()
        if not raw.strip():
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent % 2:
            raise RecipeError("YAML indentation must use multiples of two spaces.")
        result.append((indent, raw.strip()))
    return result


def _strip_comment(raw: str) -> str:
    quote = None
    escaped = False
    for index, char in enumerate(raw):
        if escaped:
            escaped = False
            continue
        if char == "\\" and quote == '"':
            escaped = True
            continue
        if char in {"'", '"'}:
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
            continue
        if char == "#" and quote is None:
            return raw[:index]
    return raw


def _parse_block(lines: List[Tuple[int, str]], index: int, indent: int) -> Tuple[Any, int]:
    if _is_list_item(lines[index][1]):
        return _parse_list(lines, index, indent)
    return _parse_mapping(lines, index, indent)


def _parse_mapping(lines: List[Tuple[int, str]], index: int, indent: int) -> Tuple[Dict[str, Any], int]:
    mapping = {}
    while index < len(lines):
        line_indent, content = lines[index]
        if line_indent < indent:
            break
        if line_indent > indent:
            raise RecipeError("Unexpected YAML indentation near: " + content)
        if _is_list_item(content):
            break
        if ":" not in content:
            raise RecipeError("Expected 'key: value' near: " + content)
        key, value = content.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise RecipeError("YAML mapping contains an empty key.")
        index += 1
        if value:
            mapping[key] = _parse_scalar(value)
        else:
            if index >= len(lines) or lines[index][0] <= line_indent:
                mapping[key] = {}
            else:
                mapping[key], index = _parse_block(lines, index, lines[index][0])
    return mapping, index


def _parse_list(lines: List[Tuple[int, str]], index: int, indent: int) -> Tuple[List[Any], int]:
    items = []
    while index < len(lines):
        line_indent, content = lines[index]
        if line_indent < indent:
            break
        if line_indent != indent or not _is_list_item(content):
            break
        value = content[1:].strip()
        index += 1
        if value:
            items.append(_parse_scalar(value))
        else:
            if index >= len(lines) or lines[index][0] <= line_indent:
                items.append(None)
            else:
                item, index = _parse_block(lines, index, lines[index][0])
                items.append(item)
    return items, index


def _is_list_item(content: str) -> bool:
    return content == "-" or content.startswith("- ")


def _parse_scalar(value: str) -> Any:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none", "~"}:
        return None
    if value.startswith("[") or value.startswith("{"):
        try:
            return ast.literal_eval(value)
        except (SyntaxError, ValueError) as exc:
            raise RecipeError("Invalid inline YAML value: " + value) from exc
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        try:
            return ast.literal_eval(value)
        except (SyntaxError, ValueError) as exc:
            raise RecipeError("Invalid quoted YAML string: " + value) from exc
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value

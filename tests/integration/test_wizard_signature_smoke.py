import ast
import inspect
from pathlib import Path

import beaupy

from aegis_phase1.v2.cli import menu


def test_menu_kwargs_compatible_with_beaupy_signature():
    menu_path = Path(inspect.getfile(menu))
    menu_source = menu_path.read_text(encoding="utf-8")
    menu_tree = ast.parse(menu_source)
    signature_parameters = set(inspect.signature(beaupy.select).parameters)
    select_calls = [
        node
        for node in ast.walk(menu_tree)
        if isinstance(node, ast.Call)
        and ast.unparse(node.func).endswith("beaupy.select")
    ]
    keyword_names = [keyword.arg for call in select_calls for keyword in call.keywords]

    assert select_calls
    assert all(keyword_name is not None for keyword_name in keyword_names)
    assert "pre_selected" not in keyword_names
    assert "pre_selected" not in menu_source
    for keyword_name in keyword_names:
        assert keyword_name in signature_parameters


def test_no_pre_selected_in_menu_source():
    menu_path = Path(inspect.getfile(menu))
    menu_source = menu_path.read_text(encoding="utf-8")

    assert "pre_selected" not in menu_source

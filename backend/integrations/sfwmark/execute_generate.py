"""Apply the configured model ID in memory; keep the pinned source unchanged."""
import ast
import os
from pathlib import Path
import sys


def main():
    source = Path("generate.py")
    sys.path.insert(0, str(Path.cwd()))
    tree = ast.parse(source.read_text(), filename=str(source))
    replacements = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "model_id" for target in node.targets):
            node.value = ast.copy_location(ast.Constant(os.environ.get("SFW_MODEL_ID", "sd2-community/stable-diffusion-2-1-base")), node.value)
            replacements += 1
    if replacements != 1:
        raise RuntimeError("Unexpected SFWMark generation source; expected one model_id assignment")
    exec(compile(ast.fix_missing_locations(tree), str(source), "exec"), {"__name__": "__main__", "__file__": str(source.resolve())})


if __name__ == "__main__":
    main()

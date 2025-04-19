"""Source parser module for extracting information from source connector files."""

import ast
import re
from ..constants import BACKEND_SOURCES_DIR


def parse_source_file(connector_name):
    """Parse source file for a connector using AST.

    Args:
        connector_name (str): The name of the connector

    Returns:
        list or None: List of source class information or None if file not found
    """
    source_file = BACKEND_SOURCES_DIR / f"{connector_name}.py"
    if not source_file.exists():
        return None

    with open(source_file, "r") as f:
        content = f.read()

    # Parse the Python file
    try:
        tree = ast.parse(content)
    except SyntaxError:
        print(f"  Warning: Could not parse {source_file} due to syntax error")
        return None

    source_classes = []

    # First extract information from decorators
    decorators_info = {}

    for node in ast.walk(tree):
        # Look for classes with @source decorator
        if isinstance(node, ast.ClassDef):
            class_name = node.name
            auth_type = None
            auth_config_class = None

            # Check decorators for @source
            for decorator in node.decorator_list:
                if (
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Name)
                    and decorator.func.id == "source"
                ):
                    # Extract arguments from the @source decorator
                    if len(decorator.args) >= 3 and isinstance(decorator.args[2], ast.Attribute):
                        # Handle AuthType enum reference (e.g., AuthType.config_class)
                        if hasattr(decorator.args[2], "attr"):
                            auth_type = decorator.args[2].attr

                    # Extract named arguments and keyword args
                    for i, arg in enumerate(decorator.args):
                        # First arg is name, second is short_name, third might be auth_type
                        if i == 2 and isinstance(arg, ast.Name) and arg.id.startswith("AuthType"):
                            auth_type = arg.id.replace("AuthType.", "")
                        # Fourth arg might be auth_config_class
                        elif (
                            i == 3 and isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                        ):
                            auth_config_class = arg.value

                    # Check for auth_config_class in keywords
                    for keyword in decorator.keywords:
                        if keyword.arg == "auth_config_class" and isinstance(
                            keyword.value, ast.Constant
                        ):
                            auth_config_class = keyword.value.value
                        elif keyword.arg == "auth_type" and isinstance(
                            keyword.value, ast.Attribute
                        ):
                            if hasattr(keyword.value, "attr"):
                                auth_type = keyword.value.attr

                    decorators_info[class_name] = {
                        "auth_type": auth_type,
                        "auth_config_class": auth_config_class,
                    }

    # Now process class definitions
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            # Check if this class inherits from BaseSource
            is_source = False
            for base in node.bases:
                if isinstance(base, ast.Name) and base.id == "BaseSource":
                    is_source = True
                    break

            if not is_source:
                continue

            class_name = node.name
            docstring = ast.get_docstring(node) or "No description available."

            # Get auth information from decorators or class attributes
            auth_type = None
            auth_config_class = None

            # Check if we found decorator info
            if class_name in decorators_info:
                auth_type = decorators_info[class_name]["auth_type"]
                auth_config_class = decorators_info[class_name]["auth_config_class"]

            # If not found in decorator, check for class attributes
            if not auth_type or not auth_config_class:
                for item in node.body:
                    # Look for _auth_type and _auth_config_class attributes
                    if isinstance(item, ast.Assign) and len(item.targets) == 1:
                        target = item.targets[0]
                        if isinstance(target, ast.Name):
                            if target.id == "_auth_type":
                                if isinstance(item.value, ast.Constant) and isinstance(
                                    item.value.value, str
                                ):
                                    auth_type = item.value.value
                                elif isinstance(item.value, ast.Attribute) and hasattr(
                                    item.value, "attr"
                                ):
                                    auth_type = item.value.attr
                            elif target.id == "_auth_config_class":
                                if isinstance(item.value, ast.Constant) and isinstance(
                                    item.value.value, str
                                ):
                                    auth_config_class = item.value.value

            # If we still don't have auth info, try to extract from the source code using regex
            # This is a fallback for complex cases the AST parser might miss
            if not auth_type:
                auth_type_match = re.search(
                    r'_auth_type\s*=\s*(?:AuthType\.([^\s,\)]*)|[\'"]([^\'"]*)[\'"])', content
                )
                if auth_type_match:
                    auth_type = auth_type_match.group(1) or auth_type_match.group(2)

            if not auth_config_class:
                auth_config_match = re.search(
                    r'_auth_config_class\s*=\s*[\'"]([^\'"]*)[\'"]', content
                )
                if auth_config_match:
                    auth_config_class = auth_config_match.group(1)

            source_classes.append(
                {
                    "name": class_name,
                    "docstring": docstring.strip() if docstring else "No description available.",
                    "auth_type": auth_type,
                    "auth_config_class": auth_config_class,
                }
            )

    return source_classes

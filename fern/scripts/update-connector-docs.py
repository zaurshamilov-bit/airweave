#!/usr/bin/env python3
"""
Script to generate documentation for connectors based on codebase introspection.
"""

import os
import re
import yaml
import shutil
from pathlib import Path

# Define paths - updated for the new location in fern/scripts
REPO_ROOT = Path(__file__).parent.parent.parent
FRONTEND_ICONS_DIR = REPO_ROOT / "frontend" / "src" / "components" / "icons" / "apps"
BACKEND_ENTITIES_DIR = REPO_ROOT / "backend" / "airweave" / "platform" / "entities"
BACKEND_SOURCES_DIR = REPO_ROOT / "backend" / "airweave" / "platform" / "sources"
DOCS_CONNECTORS_DIR = REPO_ROOT / "fern" / "docs" / "pages" / "connectors"
AUTH_CONFIG_PATH = REPO_ROOT / "backend" / "airweave" / "platform" / "configs" / "auth.py"
DOCS_YML_PATH = REPO_ROOT / "fern" / "docs.yml"


def get_connectors_from_icons():
    """Get list of connectors from SVG icons."""
    connectors = []
    for svg_file in FRONTEND_ICONS_DIR.glob("*.svg"):
        connector_name = svg_file.stem
        # Skip light/dark variations
        if connector_name.endswith("-light") or connector_name.endswith("-dark"):
            base_name = connector_name.rsplit("-", 1)[0]
            if base_name not in connectors:
                connectors.append(base_name)
        else:
            if connector_name not in connectors:
                connectors.append(connector_name)
    return connectors


def parse_entity_file(connector_name):
    """Parse entity file for a connector using AST."""
    import ast

    entity_file = BACKEND_ENTITIES_DIR / f"{connector_name}.py"
    if not entity_file.exists():
        return None

    with open(entity_file, "r") as f:
        content = f.read()

    # Parse the Python file
    try:
        tree = ast.parse(content)
    except SyntaxError:
        print(f"  Warning: Could not parse {entity_file} due to syntax error")
        return None

    entity_classes = []

    # Find all class definitions that inherit from BaseEntity or ChunkEntity
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            # Check if this class inherits from BaseEntity or ChunkEntity
            is_entity = False
            for base in node.bases:
                if isinstance(base, ast.Name):
                    if base.id in ["BaseEntity", "ChunkEntity", "PolymorphicEntity"]:
                        is_entity = True
                        break
                # Handle complex inheritance (like with subscripts)
                elif isinstance(base, ast.Subscript) and isinstance(base.value, ast.Name):
                    if base.value.id in ["BaseEntity", "ChunkEntity", "PolymorphicEntity"]:
                        is_entity = True
                        break

            if not is_entity:
                continue

            class_name = node.name
            docstring = ast.get_docstring(node) or "No description available."

            # Extract fields
            fields = []
            for item in node.body:
                # Look for attribute assignments with Field() constructor
                if isinstance(item, ast.AnnAssign) and hasattr(item, "target"):
                    field_name = None
                    if isinstance(item.target, ast.Name):
                        field_name = item.target.id

                    if field_name:
                        # Get field type
                        field_type = None
                        if hasattr(item, "annotation"):
                            if hasattr(ast, "unparse"):  # Python 3.9+
                                field_type = ast.unparse(item.annotation)
                            else:
                                # Fallback for older Python versions
                                if isinstance(item.annotation, ast.Name):
                                    field_type = item.annotation.id
                                elif isinstance(item.annotation, ast.Subscript):
                                    if isinstance(item.annotation.value, ast.Name):
                                        field_type = item.annotation.value.id

                        field_type = field_type or "Unknown"
                        description = "No description"

                        # Extract Field parameters for description if Field constructor is used
                        if hasattr(item, "value") and isinstance(item.value, ast.Call):
                            for keyword in item.value.keywords:
                                if keyword.arg == "description":
                                    # Simple string
                                    if isinstance(keyword.value, ast.Str):
                                        description = keyword.value.s
                                    # String in Python 3.8+ (ast.Constant)
                                    elif isinstance(keyword.value, ast.Constant) and isinstance(
                                        keyword.value.value, str
                                    ):
                                        description = keyword.value.value
                                    # Concatenated strings or multiline description
                                    elif isinstance(keyword.value, ast.BinOp) or isinstance(
                                        keyword.value, ast.Tuple
                                    ):
                                        # We need the original source for this part
                                        try:
                                            lines = content.split("\n")
                                            lineno = (
                                                keyword.value.lineno - 1
                                            )  # Convert to 0-indexed

                                            # Heuristic: take the current line and the next 3 lines
                                            # to capture multiline descriptions
                                            desc_lines = lines[lineno : lineno + 4]

                                            # Extract the part inside the quotes or parentheses
                                            desc_text = " ".join(desc_lines)
                                            desc_match = re.search(
                                                r'description\s*=\s*(?:\(?\s*"([^"]*)"|\(?\s*\'([^\']*)\')',
                                                desc_text,
                                            )
                                            if desc_match:
                                                description = desc_match.group(
                                                    1
                                                ) or desc_match.group(2)
                                        except:
                                            pass

                        # Clean up the description - remove excessive whitespace and newlines
                        description = re.sub(r"\s+", " ", description).strip()

                        fields.append(
                            {"name": field_name, "type": field_type, "description": description}
                        )

            entity_classes.append(
                {
                    "name": class_name,
                    "docstring": docstring.strip() if docstring else "No description available.",
                    "fields": fields,
                }
            )

    return entity_classes


def parse_source_file(connector_name):
    """Parse source file for a connector using AST."""
    import ast

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


def parse_auth_config():
    """Parse auth config file using Python's AST module."""
    import ast

    with open(AUTH_CONFIG_PATH, "r") as f:
        content = f.read()

    # Parse the Python file
    tree = ast.parse(content)

    # Find all class definitions and their inheritance
    auth_configs = {}

    # First pass: collect all classes
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_name = node.name

            # Check if this is an auth config class
            parent_classes = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    parent_classes.append(base.id)

            # Skip if not auth-related
            if not (
                any("AuthConfig" in parent for parent in parent_classes)
                or "AuthConfig" in class_name
            ):
                continue

            # Get docstring
            docstring = ast.get_docstring(node) or "No description available."

            # Get fields
            fields = []
            for item in node.body:
                # Look for attribute assignments with Field() constructor
                if isinstance(item, ast.AnnAssign) and hasattr(item, "value"):
                    field_name = item.target.id if isinstance(item.target, ast.Name) else None

                    if field_name:
                        # Get field type
                        field_type = None
                        if hasattr(item, "annotation"):
                            if hasattr(ast, "unparse"):  # Python 3.9+
                                field_type = ast.unparse(item.annotation)
                            else:
                                # Fallback for older Python versions
                                if isinstance(item.annotation, ast.Name):
                                    field_type = item.annotation.id
                                elif isinstance(item.annotation, ast.Subscript):
                                    if isinstance(item.annotation.value, ast.Name):
                                        field_type = item.annotation.value.id

                        field_type = field_type or "Unknown"
                        description = "No description"
                        is_required = True

                        # Extract Field parameters by traversing the AST
                        if isinstance(item.value, ast.Call):
                            for keyword in item.value.keywords:
                                if keyword.arg == "description":
                                    # Simple string
                                    if isinstance(keyword.value, ast.Str):
                                        description = keyword.value.s
                                    # String in Python 3.8+ (ast.Constant)
                                    elif isinstance(keyword.value, ast.Constant) and isinstance(
                                        keyword.value.value, str
                                    ):
                                        description = keyword.value.value
                                    # Concatenated strings or multiline description
                                    elif isinstance(keyword.value, ast.BinOp) or isinstance(
                                        keyword.value, ast.Tuple
                                    ):
                                        # We need the original source for this part
                                        try:
                                            lines = content.split("\n")
                                            lineno = (
                                                keyword.value.lineno - 1
                                            )  # Convert to 0-indexed

                                            # Heuristic: take the current line and the next 3 lines
                                            # to capture multiline descriptions
                                            desc_lines = lines[lineno : lineno + 4]

                                            # Extract the part inside the quotes or parentheses
                                            desc_text = " ".join(desc_lines)
                                            desc_match = re.search(
                                                r'description\s*=\s*(?:\(?\s*"([^"]*)"|\(?\s*\'([^\']*)\')',
                                                desc_text,
                                            )
                                            if desc_match:
                                                description = desc_match.group(
                                                    1
                                                ) or desc_match.group(2)
                                        except:
                                            pass

                                elif keyword.arg == "default":
                                    is_required = False

                        fields.append(
                            {
                                "name": field_name,
                                "type": field_type,
                                "description": description,
                                "required": is_required,
                            }
                        )

            auth_configs[class_name] = {
                "name": class_name,
                "parent_class": parent_classes[0] if parent_classes else None,
                "docstring": docstring,
                "fields": fields,
            }

    # Second pass: handle inheritance
    for class_name, config in auth_configs.items():
        parent_class = config.get("parent_class")
        if (
            parent_class in auth_configs
            and parent_class != "AuthConfig"
            and parent_class != "BaseConfig"
        ):
            parent_fields = auth_configs[parent_class]["fields"]
            existing_field_names = [field["name"] for field in config["fields"]]

            # Extract the database type from the class name
            db_type = None
            if "AuthConfig" in class_name:
                db_type = class_name.replace("AuthConfig", "")

            for parent_field in parent_fields:
                if parent_field["name"] not in existing_field_names:
                    field_copy = parent_field.copy()

                    # Replace database type in description if needed
                    if db_type and "PostgreSQL" in field_copy["description"]:
                        field_copy["description"] = field_copy["description"].replace(
                            "PostgreSQL", db_type
                        )

                    config["fields"].append(field_copy)

    # Special case for BaseDatabaseAuthConfig
    # Ensure we fully extract the "tables" field which has a complex description in parentheses
    if "BaseDatabaseAuthConfig" in auth_configs:
        tables_pattern = r'tables:\s*str\s*=\s*Field\(\s*default="[^"]*",\s*title="[^"]*",\s*description=\(\s*"([^"]*)"\s*(?:"([^"]*)")?\s*\),?\s*\)'
        tables_match = re.search(tables_pattern, content, re.DOTALL)

        if tables_match:
            description = tables_match.group(1)
            if tables_match.group(2):  # Second part of the description if split
                description += " " + tables_match.group(2)

            # Find tables field and update its description
            for field in auth_configs["BaseDatabaseAuthConfig"]["fields"]:
                if field["name"] == "tables":
                    field["description"] = description
                    break
            # If not found, add it
            else:
                auth_configs["BaseDatabaseAuthConfig"]["fields"].append(
                    {
                        "name": "tables",
                        "type": "str",
                        "description": description,
                        "required": False,  # Has default value
                    }
                )

            # Also propagate to children
            for class_name, config in auth_configs.items():
                if config.get("parent_class") == "BaseDatabaseAuthConfig":
                    tables_found = False
                    for field in config["fields"]:
                        if field["name"] == "tables":
                            tables_found = True
                            break

                    if not tables_found:
                        db_type = class_name.replace("AuthConfig", "")
                        tables_desc = (
                            description.replace("PostgreSQL", db_type) if db_type else description
                        )
                        config["fields"].append(
                            {
                                "name": "tables",
                                "type": "str",
                                "description": tables_desc,
                                "required": False,
                            }
                        )

    print(f"  Parsed {len(auth_configs)} auth configurations")
    return auth_configs


def generate_mdx_content(connector_name, entity_info, source_info, auth_configs):
    """Generate MDX content for a connector."""
    # Normalize connector name for display
    display_name = connector_name.replace("_", " ").title()

    content = f"""<div className="connector-header">
  <img src="icon.svg" alt="{display_name} logo" width="72" height="72" className="connector-icon" />
  <div className="connector-info">
    <h1>{display_name}</h1>
    <p>Connect your {display_name} data to Airweave</p>
  </div>
</div>

## Overview

The {display_name} connector allows you to sync data from {display_name} into Airweave, making it available for search and retrieval by your agents.
"""

    # Add source information
    if source_info:
        content += "\n## Configuration\n\n"
        for source in source_info:
            content += f"""
### {source['name']}

{source['docstring']}

"""
            # Add authentication information section
            content += "#### Authentication\n\n"

            # Map auth_type to human-readable description
            auth_type_descriptions = {
                "oauth2": "OAuth 2.0 authentication flow",
                "oauth2_with_refresh": "OAuth 2.0 with refresh token",
                "oauth2_with_refresh_rotating": "OAuth 2.0 with rotating refresh token",
                "trello_auth": "Trello authentication",
                "api_key": "API key authentication",
                "config_class": "Configuration-based authentication",
                "none": "No authentication required",
                "native_functionality": "Native functionality",
                "url_and_api_key": "URL and API key authentication",
            }

            auth_type = source.get("auth_type")
            auth_config_class = source.get("auth_config_class")

            if auth_type:
                auth_type_display = auth_type_descriptions.get(auth_type, auth_type)
                content += f"This connector uses **{auth_type_display}**.\n\n"

            # If auth_config_class is available and matches an entry in auth_configs, display its fields
            if auth_config_class and auth_config_class in auth_configs:
                auth_info = auth_configs[auth_config_class]
                content += f"Authentication configuration class: `{auth_config_class}`\n\n"

                if auth_info["docstring"]:
                    content += f"{auth_info['docstring']}\n\n"

                if auth_info["fields"]:
                    content += "The following configuration fields are required:\n\n"
                    content += "| Field | Type | Description | Required |\n"
                    content += "|-------|------|-------------|----------|\n"
                    for field in auth_info["fields"]:
                        # Get descriptions from parent class if available
                        field_description = field["description"]
                        if field_description == "No description" and "parent_class" in auth_info:
                            parent_class = auth_info["parent_class"]
                            if parent_class in auth_configs:
                                parent_fields = auth_configs[parent_class]["fields"]
                                for parent_field in parent_fields:
                                    if (
                                        parent_field["name"] == field["name"]
                                        and parent_field["description"] != "No description"
                                    ):
                                        field_description = parent_field["description"]
                                        break

                        content += f"| {field['name']} | {field['type']} | {field_description} | {'Yes' if field['required'] else 'No'} |\n"
                    content += "\n"
            elif (
                auth_type == "oauth2"
                or auth_type == "oauth2_with_refresh"
                or auth_type == "oauth2_with_refresh_rotating"
            ):
                content += "This connector uses OAuth authentication. You can connect through the Airweave UI, which will guide you through the OAuth flow.\n\n"
            elif auth_type == "none":
                content += "This connector does not require authentication.\n\n"
            else:
                content += (
                    "Please refer to the Airweave documentation for authentication details.\n\n"
                )

    # Add entity information
    if entity_info:
        content += "\n## Entities\n\n"
        content += "The following data models are available for this connector:\n\n"

        for entity in entity_info:
            content += f"""
<details>
<summary><strong>{entity['name']}</strong></summary>

{entity['docstring']}

| Field | Type | Description |
|-------|------|-------------|
"""
            for field in entity["fields"]:
                content += f"| {field['name']} | {field['type']} | {field['description']} |\n"

            content += "\n</details>\n"

    # Wrap the content with delimiters
    return (
        "{/* AUTO-GENERATED CONTENT START */}\n\n"
        + content
        + "\n\n{/* AUTO-GENERATED CONTENT END */}"
    )


def copy_svg_icon(connector_name, connector_docs_dir):
    """Copy SVG icon to connector documentation directory."""
    # Look for the icon in the apps directory
    icon_path = None
    for icon_candidate in [f"{connector_name}.svg", f"{connector_name}-light.svg"]:
        source_path = FRONTEND_ICONS_DIR / icon_candidate
        if source_path.exists():
            icon_path = source_path
            break

    if not icon_path:
        print(f"  Warning: No SVG icon found for {connector_name}")
        return False

    # Copy icon to the connector directory
    dest_path = connector_docs_dir / "icon.svg"
    shutil.copy2(icon_path, dest_path)
    print(f"  Copied {icon_path.name} to {dest_path.relative_to(REPO_ROOT)}")
    return True


def update_docs_yml(valid_connectors):
    """Update the docs.yml file with the connector list."""
    try:
        with open(DOCS_YML_PATH, "r") as f:
            docs_config = yaml.safe_load(f)

        # Find the connectors section
        for section in docs_config["navigation"]:
            if isinstance(section, dict) and "section" in section and section["section"] == "Docs":
                for item in section["contents"]:
                    if (
                        isinstance(item, dict)
                        and "section" in item
                        and item["section"] == "Connectors"
                    ):
                        # Clear existing connector list
                        item["contents"] = []

                        # Add all connectors
                        for connector in sorted(valid_connectors):
                            display_name = connector.replace("_", " ").title()
                            item["contents"].append(
                                {
                                    "page": display_name,
                                    "path": f"docs/pages/connectors/{connector}/main.mdx",
                                }
                            )

        # Write back the updated config
        with open(DOCS_YML_PATH, "w") as f:
            yaml.dump(docs_config, f, default_flow_style=False, sort_keys=False)

        print(f"Updated docs.yml with {len(valid_connectors)} connectors")
    except Exception as e:
        print(f"Error updating docs.yml: {str(e)}")


def main():
    """Main function."""
    print("Starting connector documentation generation...")

    connectors = get_connectors_from_icons()
    print(f"Found {len(connectors)} connectors from icons")

    auth_configs = parse_auth_config()
    print(f"Parsed {len(auth_configs)} auth configurations")

    valid_connectors = []

    for connector_name in sorted(connectors):
        print(f"Processing connector: {connector_name}")

        entity_info = parse_entity_file(connector_name)
        source_info = parse_source_file(connector_name)

        # Skip if no entity or source info is available
        if not entity_info and not source_info:
            print(f"  Skipping {connector_name} - no entity or source information found")
            continue

        valid_connectors.append(connector_name)

        # Generate MDX content with delimiters
        mdx_content = generate_mdx_content(connector_name, entity_info, source_info, auth_configs)

        # Create connector docs directory if it doesn't exist
        connector_docs_dir = DOCS_CONNECTORS_DIR / connector_name
        os.makedirs(connector_docs_dir, exist_ok=True)

        # Copy SVG icon to connector directory
        copy_svg_icon(connector_name, connector_docs_dir)

        # Create or update main.mdx
        main_mdx_path = connector_docs_dir / "main.mdx"

        # Format display name for frontmatter
        display_name = connector_name.replace("_", " ").title()

        # Add frontmatter
        frontmatter = f"""---
title: "{display_name}"
description: "{display_name} integration with Airweave"
---

"""

        if main_mdx_path.exists():
            # If file exists, preserve custom content and update only auto-generated part
            with open(main_mdx_path, "r") as f:
                existing_content = f.read()

            # Replace content between auto-generated markers
            auto_gen_start = "{/* AUTO-GENERATED CONTENT START */}"
            auto_gen_end = "{/* AUTO-GENERATED CONTENT END */}"

            start_index = existing_content.find(auto_gen_start)
            end_index = existing_content.find(auto_gen_end) + len(auto_gen_end)

            if start_index != -1 and end_index != -1:
                # Replace only the auto-generated part
                updated_content = (
                    existing_content[:start_index]
                    + auto_gen_start
                    + "\n\n"
                    + mdx_content.replace(auto_gen_start, "").replace(auto_gen_end, "")
                    + "\n\n"
                    + auto_gen_end
                    + existing_content[end_index:]
                )

                with open(main_mdx_path, "w") as f:
                    f.write(updated_content)

                print(f"  Updated auto-generated content for {connector_name}")
            else:
                # No markers found, treat as a new file
                with open(main_mdx_path, "w") as f:
                    f.write(frontmatter + mdx_content)

                print(
                    f"  Created new main.mdx for {connector_name} (no markers found in existing file)"
                )
        else:
            # Create the file with the frontmatter and generated content
            with open(main_mdx_path, "w") as f:
                f.write(frontmatter + mdx_content)

            print(f"  Created new main.mdx for {connector_name}")

    # Update the docs.yml file with the valid connectors
    update_docs_yml(valid_connectors)

    print(f"Generated documentation for {len(valid_connectors)} connectors")
    print("Connector documentation generation complete!")


if __name__ == "__main__":
    main()

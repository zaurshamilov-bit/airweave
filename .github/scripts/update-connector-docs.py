#!/usr/bin/env python3
"""
Script to generate documentation for connectors based on codebase introspection.
"""

import os
import re
import yaml
import shutil
from pathlib import Path

# Define paths
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
    """Parse entity file for a connector."""
    entity_file = BACKEND_ENTITIES_DIR / f"{connector_name}.py"
    if not entity_file.exists():
        return None

    with open(entity_file, "r") as f:
        content = f.read()

    # Extract classes using regex
    class_pattern = r'class\s+(\w+)\(.*?BaseEntity.*?\):\s*(?:"""(.*?)""")?'
    classes = re.findall(class_pattern, content, re.DOTALL)

    entity_classes = []
    for class_name, docstring in classes:
        # Extract fields using regex
        field_pattern = r'(\w+):\s*(\w+)\s*=\s*Field\(.*?description="(.*?)"'
        fields = re.findall(field_pattern, content, re.DOTALL)

        entity_fields = []
        for field_name, field_type, description in fields:
            entity_fields.append(
                {"name": field_name, "type": field_type, "description": description}
            )

        entity_classes.append(
            {
                "name": class_name,
                "docstring": docstring.strip() if docstring else "No description available.",
                "fields": entity_fields,
            }
        )

    return entity_classes


def parse_source_file(connector_name):
    """Parse source file for a connector."""
    source_file = BACKEND_SOURCES_DIR / f"{connector_name}.py"
    if not source_file.exists():
        return None

    with open(source_file, "r") as f:
        content = f.read()

    # Extract classes using regex
    class_pattern = r'class\s+(\w+)\(.*?BaseSource.*?\):\s*(?:"""(.*?)""")?'
    classes = re.findall(class_pattern, content, re.DOTALL)

    source_classes = []
    for class_name, docstring in classes:
        # Extract auth type and auth config class
        auth_type_match = re.search(r'_auth_type\s*=\s*[\'"]([^\'"]*)[\'"]', content)
        auth_config_match = re.search(r'_auth_config_class\s*=\s*[\'"]([^\'"]*)[\'"]', content)

        auth_type = auth_type_match.group(1) if auth_type_match else None
        auth_config_class = auth_config_match.group(1) if auth_config_match else None

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
    """Parse auth config file."""
    with open(AUTH_CONFIG_PATH, "r") as f:
        content = f.read()

    # Extract auth classes using regex
    class_pattern = r'class\s+(\w+)(\(.+?\)):\s*(?:"""(.*?)""")?'
    classes = re.findall(class_pattern, content, re.DOTALL)

    auth_configs = {}
    for class_name, parent_class, docstring in classes:
        if "Auth" in parent_class or "Auth" in class_name:
            # Find the section for this class
            class_section_pattern = f"class\\s+{class_name}{parent_class}:.*?(?=class\\s+\\w+\\(|$)"
            class_section_match = re.search(class_section_pattern, content, re.DOTALL)

            if class_section_match:
                class_section = class_section_match.group(0)

                # Extract field definitions
                field_pattern = r'(\w+):\s*(\w+)\s*=\s*Field\(.*?description="(.*?)".*?\)'
                fields = re.findall(field_pattern, class_section, re.DOTALL)

                auth_fields = []
                for field_name, field_type, description in fields:
                    # Check if required
                    is_required = "required" in class_section or field_name in re.findall(
                        r"required\s*=\s*\[(.*?)\]", class_section, re.DOTALL
                    )

                    auth_fields.append(
                        {
                            "name": field_name,
                            "type": field_type,
                            "description": description,
                            "required": is_required,
                        }
                    )

                auth_configs[class_name] = {
                    "name": class_name,
                    "docstring": docstring.strip() if docstring else "No description available.",
                    "fields": auth_fields,
                }

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

            # Add authentication information if available
            if source["auth_config_class"] and source["auth_config_class"] in auth_configs:
                auth_info = auth_configs[source["auth_config_class"]]
                content += """
#### Authentication

This connector requires the following authentication:

| Field | Type | Description | Required |
|-------|------|-------------|----------|
"""
                for field in auth_info["fields"]:
                    content += f"| {field['name']} | {field['type']} | {field['description']} | {'Yes' if field['required'] else 'No'} |\n"

    # Add entity information
    if entity_info:
        content += "\n## Data Models\n\n"
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

    # Skip Slack as it has custom content
    skip_connectors = ["slack"]

    for connector_name in sorted(connectors):
        if connector_name in skip_connectors:
            print(f"  Skipping {connector_name} as it has custom content")
            valid_connectors.append(connector_name)
            continue

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

        # Create the file with the frontmatter and generated content
        with open(main_mdx_path, "w") as f:
            f.write(frontmatter + mdx_content)

        print(
            f"  {'Updated' if main_mdx_path.exists() else 'Created'} main.mdx for {connector_name}"
        )

    # Update the docs.yml file with the valid connectors
    update_docs_yml(valid_connectors)

    print(f"Generated documentation for {len(valid_connectors)} connectors")
    print("Connector documentation generation complete!")


if __name__ == "__main__":
    main()

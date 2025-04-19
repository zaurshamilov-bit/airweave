"""File utility functions for the connector documentation generator."""

import os
import shutil
import yaml
from pathlib import Path

from ..constants import (
    CONTENT_START_MARKER,
    CONTENT_END_MARKER,
    FRONTEND_ICONS_DIR,
    DOCS_YML_PATH,
)


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
    print(f"  Copied {icon_path.name} to {dest_path.relative_to(Path.cwd())}")
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


def update_or_create_mdx(connector_name, connector_docs_dir, mdx_content):
    """Create or update main.mdx file for a connector."""
    # Create connector docs directory if it doesn't exist
    os.makedirs(connector_docs_dir, exist_ok=True)

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
        start_index = existing_content.find(CONTENT_START_MARKER)
        end_index = existing_content.find(CONTENT_END_MARKER) + len(CONTENT_END_MARKER)

        if start_index != -1 and end_index != -1:
            # Replace only the auto-generated part
            updated_content = (
                existing_content[:start_index]
                + CONTENT_START_MARKER
                + "\n\n"
                + mdx_content.replace(CONTENT_START_MARKER, "").replace(CONTENT_END_MARKER, "")
                + "\n\n"
                + CONTENT_END_MARKER
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

    return True

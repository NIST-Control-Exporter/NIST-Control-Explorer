#!/usr/bin/env python3
# Read a NIST OSCAL catalog and export controls as Markdown.

import json
import re
from pathlib import Path

from prompts import ask, choose, new_markdown_file, path_input, yes_no


DEFAULT_CATALOG = Path(__file__).parent / "catalog" / "nist-catalog.json"

# OSCAL writes a parameter inside prose like this:
# {{ insert: param, ac-02_odp.01 }}
PARAMETER_PATTERN = re.compile(r"\{\{\s*insert:\s*param,\s*([^}]+?)\s*\}\}")


def load_catalog(file_path):
    # Open an OSCAL JSON file and return its catalog.
    json_text = file_path.read_text(encoding="utf-8-sig")
    json_data = json.loads(json_text)
    return json_data["catalog"]


def get_label(item):
    # Return NIST's normal label, such as AC-2 or a.
    for property_item in item.get("props", []):
        is_label = property_item.get("name") == "label"
        is_normal_label = not property_item.get("class")
        if is_label and is_normal_label:
            return property_item["value"]

    return item.get("id", "")


def get_families(catalog):
    # Return every control family in the catalog.
    families = []

    def add_groups(group_list):
        for group in group_list:
            families.append(group)
            add_groups(group.get("groups", []))

    add_groups(catalog.get("groups", []))
    return families


def get_all_controls(control_list):
    # Return base controls and their nested enhancements.
    all_controls = []

    for control in control_list:
        all_controls.append(control)
        child_controls = control.get("controls", [])
        all_controls.extend(get_all_controls(child_controls))

    return all_controls


def build_parameter_lookup(catalog):
    # Build a dictionary used to replace OSCAL parameter insertions.
    parameter_lookup = {}

    def visit(item):
        for parameter in item.get("params", []):
            parameter_lookup[parameter["id"]] = parameter

        for child_type in ("groups", "controls", "parts"):
            for child in item.get(child_type, []):
                visit(child)

    visit(catalog)
    return parameter_lookup


def format_prose(text, parameter_lookup, parameters_in_progress=None):
    # Replace OSCAL parameter codes with readable Markdown placeholders.
    if parameters_in_progress is None:
        parameters_in_progress = set()

    def replace_parameter(match):
        parameter_id = match.group(1).strip()

        if parameter_id in parameters_in_progress or parameter_id not in parameter_lookup:
            raise ValueError(f"Unresolved or recursive OSCAL parameter: {parameter_id}")

        parameter = parameter_lookup[parameter_id]

        if "select" in parameter:
            selection = parameter["select"]
            formatted_choices = []

            for choice in selection.get("choice", []):
                next_in_progress = parameters_in_progress | {parameter_id}
                formatted_choice = format_prose(
                    choice,
                    parameter_lookup,
                    next_in_progress,
                )
                formatted_choices.append(formatted_choice)

            choice_text = "; ".join(formatted_choices)
            if selection.get("how-many") == "one-or-more":
                amount = "one or more"
            else:
                amount = "one"
            return f"[Selection ({amount}): {choice_text}]"

        description = parameter.get("label", parameter_id)
        return f"[Assignment: organization-defined {description}]"

    return PARAMETER_PATTERN.sub(replace_parameter, text)


def format_part(part, parameter_lookup, indent_level=0):
    # Format one statement part and any parts nested beneath it.
    markdown_lines = []
    prose = format_prose(part.get("prose", ""), parameter_lookup)
    is_list_item = part.get("name") == "item"

    if is_list_item:
        # Explicit labels keep Markdown from changing NIST's a., 1., and (a).
        item_label = get_label(part).replace(".", "\\.")
        item_text = f"{item_label} {prose}".strip()
        indentation = "    " * indent_level
        continued_line_indent = "    " * (indent_level + 1)
        item_text = item_text.replace("\n", "\n" + continued_line_indent)
        markdown_lines.append(indentation + "- " + item_text)
        markdown_lines.append("")
    elif prose:
        markdown_lines.append(prose)
        markdown_lines.append("")

    if is_list_item:
        child_indent = indent_level + 1
    else:
        child_indent = indent_level

    for child_part in part.get("parts", []):
        child_lines = format_part(child_part, parameter_lookup, child_indent)
        markdown_lines.extend(child_lines)

    return markdown_lines


def format_related_controls(control):
    # Return the control IDs listed as related by NIST.
    related_controls = []

    for link in control.get("links", []):
        if link.get("rel") != "related":
            continue

        control_id = link["href"].lstrip("#").upper()
        if "." in control_id:
            control_id = control_id.replace(".", "(") + ")"
        related_controls.append(control_id)

    return related_controls


def format_control(control, parameter_lookup, heading_level=2, statement_only=False):
    # Format one control as a Markdown section.
    heading_marks = "#" * heading_level
    heading = f"{heading_marks} {get_label(control)} - {control['title']}"
    markdown_lines = [heading, ""]

    part_names = {
        "statement": "Control",
        "guidance": "Discussion",
    }

    for part in control.get("parts", []):
        part_name = part.get("name")

        if part_name not in part_names:
            continue
        if statement_only and part_name != "statement":
            continue

        markdown_lines.append(f"**{part_names[part_name]}:**")
        markdown_lines.append("")
        markdown_lines.extend(format_part(part, parameter_lookup))
        markdown_lines.append("")

    related_controls = format_related_controls(control)
    if related_controls and not statement_only:
        markdown_lines.append("**Related controls:** " + ", ".join(related_controls))
        markdown_lines.append("")

    return markdown_lines


def normalize_control_id(control_id):
    # Convert AC-02 and AC-2(1) into IDs used inside the OSCAL file.
    normalized_id = control_id.lower()
    normalized_id = re.sub(r"\((\d+)\)", r".\1", normalized_id)
    normalized_id = re.sub(r"-(0+)(\d)", r"-\2", normalized_id)
    return normalized_id


def find_family(families, family_id):
    # Find a family by its short ID, such as AC.
    for family in families:
        if family.get("id", "").lower() == family_id.lower():
            return family

    raise ValueError(f"Unknown family: {family_id}")


def find_selected_controls(families, requested_ids):
    # Find the controls requested by the user.
    control_lookup = {}

    for family in families:
        family_controls = get_all_controls(family.get("controls", []))
        for control in family_controls:
            control_lookup[control["id"].lower()] = control

    selected_controls = []

    for requested_id in requested_ids:
        normalized_id = normalize_control_id(requested_id)

        if normalized_id not in control_lookup:
            raise ValueError(f"Unknown control: {requested_id}")

        control = control_lookup[normalized_id]
        if control not in selected_controls:
            selected_controls.append(control)

    return selected_controls


def export_controls(
    catalog,
    family_id=None,
    control_ids=None,
    include_enhancements=False,
    statement_only=False,
):
    # Create the complete Markdown export.
    families = get_families(catalog)
    parameter_lookup = build_parameter_lookup(catalog)

    if family_id:
        selected_family = find_family(families, family_id)
        selected_controls = selected_family.get("controls", [])
        document_title = f"{selected_family['id'].upper()} - {selected_family['title']}"
    else:
        selected_controls = find_selected_controls(families, control_ids or [])
        document_title = "NIST SP 800-53 Controls"

    metadata = catalog["metadata"]
    markdown_lines = [
        f"# {document_title}",
        "",
        f"Source: {metadata['title']}",
        "",
        (
            f"Catalog release: {metadata['version']} | "
            f"OSCAL: {metadata['oscal-version']} | "
            f"Modified: {metadata['last-modified']}"
        ),
        "",
    ]

    exported_ids = set()

    def add_control(control, heading_level):
        # Add one control, then optionally add its enhancements.
        if control["id"] in exported_ids:
            return

        exported_ids.add(control["id"])
        control_lines = format_control(
            control,
            parameter_lookup,
            heading_level,
            statement_only,
        )
        markdown_lines.extend(control_lines)

        child_controls = control.get("controls", [])
        if include_enhancements and child_controls:
            enhancement_heading = "#" * (heading_level + 1)
            markdown_lines.append(enhancement_heading + " Control Enhancements")
            markdown_lines.append("")

            for child_control in child_controls:
                add_control(child_control, heading_level + 2)

    for selected_control in selected_controls:
        add_control(selected_control, 2)

    return "\n".join(markdown_lines).rstrip() + "\n"


def ask_for_catalog():
    # Keep asking until the user chooses a readable OSCAL catalog.
    while True:
        catalog_path = path_input("Catalog JSON file", DEFAULT_CATALOG)

        try:
            catalog = load_catalog(catalog_path)
            metadata = catalog["metadata"]
            families = get_families(catalog)

            if not families:
                raise ValueError("No control families found.")

            print(f"\n{metadata['title']}")
            print(
                f"Release: {metadata['version']} | "
                f"OSCAL: {metadata['oscal-version']} | "
                f"Modified: {metadata['last-modified']}"
            )
            return catalog, families

        except (OSError, ValueError, KeyError, TypeError) as error:
            print(f"Cannot load this catalog: {error}")
            print("Choose an OSCAL catalog JSON file.")


def ask_for_control_ids(catalog, include_enhancements, statement_only):
    # Ask for control IDs until all IDs are valid.
    while True:
        answer = ask(
            "Control IDs, separated by spaces (example: AC-2 CP-9 AC-2(1))"
        )
        control_ids = answer.replace(",", " ").split()

        if not control_ids:
            print("Enter at least one control ID.")
            continue

        try:
            return export_controls(
                catalog,
                control_ids=control_ids,
                include_enhancements=include_enhancements,
                statement_only=statement_only,
            )
        except ValueError as error:
            print(error)


def main():
    # Run the interactive program.
    print("Export NIST Controls to Markdown")
    print("Press Enter to accept a default. Ctrl+C cancels.\n")

    try:
        catalog, families = ask_for_catalog()

        export_mode = choose(
            "What would you like to export?",
            ["A whole control family", "Selected controls or enhancements"],
        )
        include_enhancements = yes_no(
            "Include child control enhancements?",
            default=True,
        )
        include_discussion = yes_no(
            "Include Discussion and Related controls?",
            default=True,
        )
        statement_only = not include_discussion

        if export_mode == 0:
            family_options = []
            for family in families:
                family_options.append(
                    f"{family['id'].upper()} - {family['title']}"
                )

            family_number = choose("Choose a control family", family_options)
            family_id = families[family_number]["id"]
            markdown = export_controls(
                catalog,
                family_id=family_id,
                include_enhancements=include_enhancements,
                statement_only=statement_only,
            )
            suggested_filename = f"{family_id}-controls.md"
        else:
            markdown = ask_for_control_ids(
                catalog,
                include_enhancements,
                statement_only,
            )
            suggested_filename = "selected-controls.md"

        output_path = new_markdown_file(suggested_filename)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("x", encoding="utf-8") as output_file:
            output_file.write(markdown)

        print(f"Created: {output_path.resolve()}")

    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(f"Error: {error}")
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")


if __name__ == "__main__":
    main()

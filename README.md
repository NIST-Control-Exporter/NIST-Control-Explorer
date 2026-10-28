# CtrlFamily - NIST Control Exporter

A small Python command-line tool for exporting NIST SP 800-53 controls from an [OSCAL](https://pages.nist.gov/OSCAL/) JSON catalog into readable Markdown files.

Select an entire control family or specific controls and enhancements. The exporter preserves control structure and can include discussion text and related controls.

**Requires Python 3.10 or newer**

## Getting started

Download these three files into the same folder:

```text
export_nist_controls.py
prompts.py
nist-catalog.json
```

Open a terminal in that folder and run:

```bash
python export_nist_controls.py
```

On macOS or Linux, you may need to use `python3` instead of `python`.

Follow the prompts to:

1. Select a whole control family or enter control IDs such as `AC-6`, `CP-9`, or `AC-2(1)`.
2. Choose whether to include child control enhancements.
3. Choose whether to include discussion and related controls.
4. Enter a filename ending in `.md` for the export.

The Markdown file is saved to the path you choose. Existing files are not overwritten.

## Updating the NIST catalog

The included `nist-catalog.json` is an OSCAL JSON catalog for **NIST SP 800-53 Rev. 5.2.0**.

To use a newer catalog:

1. Get the updated **OSCAL JSON catalog** from [NIST's OSCAL content repository](https://github.com/usnistgov/oscal-content).
2. Replace `nist-catalog.json` with the updated file.
3. Run the exporter again.

You can also keep multiple catalogs and enter the path to a different JSON file when the script asks for **Catalog JSON file**. Press Enter to use the default `nist-catalog.json` alongside the script.

The file must be a compatible OSCAL **catalog**, not an OSCAL profile, assessment, or arbitrary JSON file. Catalog updates may introduce formatting or structure changes that require exporter updates.

## About the output

The exporter reads the local catalog and creates a Markdown document with the selected controls. Organization-defined parameters are shown as placeholders rather than filled in automatically. The tool does not modify the catalog or require an internet connection to run.

## Project files

- `export_nist_controls.py` — OSCAL parsing, Markdown formatting, and CLI workflow
- `prompts.py` — terminal prompts and output filename handling
- `nist-catalog.json` — source control catalog published by NIST

The catalog content comes from NIST; the Python exporter is a separate project and is not an official NIST tool.

View the web version of this tool at [https://ctrlfamily.com](https://ctrlfamily.com)

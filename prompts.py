"""Simple terminal prompts shared by both programs."""
from pathlib import Path


def ask(message, default=""):
    """Ask for text. Return the default when the user presses Enter."""
    if default:
        default_hint = f" [{default}]"
    else:
        default_hint = ""

    answer = input(f"{message}{default_hint}: ").strip()
    return answer or default


def choose(message, options, default=1):
    """Show a numbered menu and return the selected list position."""
    print("\n" + message)
    for number, option in enumerate(options, 1):
        print(f"  {number}. {option}")

    while True:
        answer = ask("Choose a number", str(default))
        if answer.isdigit() and 1 <= int(answer) <= len(options):
            return int(answer) - 1
        print(f"Enter a number from 1 to {len(options)}.")


def yes_no(message, default=True):
    """Ask a yes-or-no question and return True or False."""
    while True:
        default_answer = "y" if default else "n"
        answer = ask(message + " (y/n)", default_answer).lower()

        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False

        print("Enter y or n.")


def path_input(message, default):
    """Ask for a file path and remove quotes added when a path is copied."""
    answer = ask(message, str(default))
    unquoted_answer = answer.strip('"').strip("'")
    return Path(unquoted_answer).expanduser()


def new_markdown_file(default):
    """Ask for a new .md filename. Never overwrite an existing file."""
    while True:
        path = path_input("Save Markdown as", default)
        if path.suffix.lower() != ".md":
            print("Use a filename ending in .md.")
        elif path.exists():
            print(
                "That file already exists. Choose another name; "
                "it will not be overwritten."
            )
        else:
            return path

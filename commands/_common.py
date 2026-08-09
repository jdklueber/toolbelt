import textwrap

WRAP_WIDTH = 75

HELP_FLAGS = ("-h", "--help")


def wants_help(args):
    return any(a in HELP_FLAGS for a in args)


def print_help(usage, description="", options=None):
    print(f"Usage: {usage}")
    if description:
        print()
        for line in textwrap.wrap(description, width=WRAP_WIDTH, break_on_hyphens=False):
            print(line)
    if options:
        print()
        print("Options:")
        name_width = max(len(name) for name, _ in options)
        indent = " " * (name_width + 3)
        for name, desc in options:
            lines = textwrap.wrap(desc, width=WRAP_WIDTH, break_on_hyphens=False) or [""]
            print(f"  {name.ljust(name_width)} {lines[0]}")
            for line in lines[1:]:
                print(f"{indent}{line}")

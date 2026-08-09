import sys

from _common import print_help, wants_help

USAGE = "toolbelt hello"
DESCRIPTION = 'Smoke-test command. Prints "Hello, World!".'


def main():
    if wants_help(sys.argv[1:]):
        print_help(USAGE, DESCRIPTION)
        return

    print("Hello, World!")


if __name__ == "__main__":
    main()

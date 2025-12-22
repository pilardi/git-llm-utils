import sys


def run():
    try:
        from git_llm_utils.app import app

        app()
    except KeyboardInterrupt:
        print("Aborted!", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    if getattr(sys, "frozen", False):
        run()
    else:
        print(
            "Please run the app using the git-llm-utils command",
            file=sys.stderr,
        )
        sys.exit(-1)

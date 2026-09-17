"""An isolated end-to-end demonstration. It never reuses the current workspace.

Default narration is a labelled synthetic tone fixture. --live-fish is explicit;
keys are inherited through environment only, never copied from another project.
"""

from pipeline.smoke import main

if __name__ == "__main__":
    main()

"""Launch the host preview without VS Code Snap's bundled GTK overrides."""

import os


def restore_desktop_environment():
    # VS Code Snap saves these values before replacing them for its own GTK
    # runtime. In particular, its forced X11 backend can misroute dialog input
    # on a Wayland desktop with multiple monitors. Restore the caller's actual
    # preferences before main (or any translation widget) imports GTK.
    for name in ("GDK_BACKEND", "GSETTINGS_SCHEMA_DIR", "GTK_EXE_PREFIX",
                 "GTK_IM_MODULE_FILE", "GTK_MODULES", "GTK_PATH"):
        original = name + "_VSCODE_SNAP_ORIG"
        if original in os.environ:
            value = os.environ.pop(original)
            if value:
                os.environ[name] = value
            else:
                os.environ.pop(name, None)


def main():
    restore_desktop_environment()
    from .main import main as parent_main
    return parent_main(["--preview"])


if __name__ == "__main__":
    raise SystemExit(main())

bl_info = {
    "name": "Stdout/Stderr to Text (Stable for Blender 5.0)",
    "author": "you",
    "version": (1, 2, 0),
    "blender": (5, 0, 0),
    "location": "Edit > Preferences > Add-ons > Stdout/Stderr to Text",
    "description": "Redirect Python print() and tracebacks to a Blender Text datablock (no System Console needed).",
    "category": "Development",
}

import bpy
import sys
from bpy.props import BoolProperty, StringProperty


# -------- Global state --------
_ORIG_STDOUT = None
_ORIG_STDERR = None
_WRITER = None
_APPLY_TIMER_TAG = None


def _get_text(name: str) -> bpy.types.Text:
    txt = bpy.data.texts.get(name)
    if txt is None:
        txt = bpy.data.texts.new(name)
    return txt


class _TextWriter:
    """
    A lightweight writer that appends to a Blender Text datablock.
    Buffers until newline to reduce frequent Text writes.
    """
    def __init__(self, text_name: str, also_console: bool, orig_out):
        self.text_name = text_name
        self.also_console = also_console
        self.orig_out = orig_out
        self._buf = ""

    def write(self, s):
        if not s:
            return 0

        # Buffer and flush on newline boundaries
        self._buf += s
        if "\n" in self._buf:
            txt = _get_text(self.text_name)
            parts = self._buf.split("\n")
            self._buf = parts.pop()  # trailing partial
            for line in parts:
                txt.write(line + "\n")

        if self.also_console and self.orig_out:
            try:
                self.orig_out.write(s)
            except Exception:
                pass

        return len(s)

    def flush(self):
        if self._buf:
            try:
                _get_text(self.text_name).write(self._buf)
            finally:
                self._buf = ""

        if self.also_console and self.orig_out:
            try:
                self.orig_out.flush()
            except Exception:
                pass


def _install_redirect(text_name: str, clear_on_enable: bool, also_console: bool):
    global _ORIG_STDOUT, _ORIG_STDERR, _WRITER

    if _ORIG_STDOUT is None:
        _ORIG_STDOUT = sys.stdout
    if _ORIG_STDERR is None:
        _ORIG_STDERR = sys.stderr

    txt = _get_text(text_name)
    if clear_on_enable:
        txt.clear()
        txt.write("[stdout redirect enabled]\n")

    _WRITER = _TextWriter(text_name=text_name, also_console=also_console, orig_out=_ORIG_STDOUT)
    sys.stdout = _WRITER
    sys.stderr = _WRITER


def _uninstall_redirect():
    global _WRITER
    # Flush before restoring
    if _WRITER is not None:
        try:
            _WRITER.flush()
        except Exception:
            pass

    if _ORIG_STDOUT is not None:
        sys.stdout = _ORIG_STDOUT
    if _ORIG_STDERR is not None:
        sys.stderr = _ORIG_STDERR

    _WRITER = None


def _read_prefs_or_defaults():
    """
    Preferences may be unavailable during enable/startup, so fall back to defaults.
    """
    addon = bpy.context.preferences.addons.get(__name__)
    if addon is None:
        return {
            "enabled": True,
            "text_name": "PY_STDOUT.txt",
            "clear_on_enable": False,
            "also_console": False,
        }
    p = addon.preferences
    return {
        "enabled": p.enabled,
        "text_name": p.text_name,
        "clear_on_enable": p.clear_on_enable,
        "also_console": p.also_console,
    }


def _apply_now():
    cfg = _read_prefs_or_defaults()
    if cfg["enabled"]:
        _install_redirect(cfg["text_name"], cfg["clear_on_enable"], cfg["also_console"])
    else:
        _uninstall_redirect()


def _apply_later():
    """
    Timer callback: apply once after Blender has finalized enabling the add-on.
    """
    global _APPLY_TIMER_TAG
    _APPLY_TIMER_TAG = None
    try:
        _apply_now()
    except Exception:
        # If anything goes wrong, restore stdout/stderr to avoid breaking Blender environment
        _uninstall_redirect()
    return None  # run once


def _schedule_apply():
    """
    Ensure we don't stack multiple timers.
    """
    global _APPLY_TIMER_TAG
    if _APPLY_TIMER_TAG is None:
        _APPLY_TIMER_TAG = bpy.app.timers.register(_apply_later, first_interval=0.1)


def _prefs_update(self, context):
    # When user toggles prefs, apply immediately (prefs already exist here)
    try:
        _apply_now()
    except Exception:
        _uninstall_redirect()


class StdoutToTextPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    enabled: BoolProperty(
        name="Enable Redirect",
        default=True,
        update=_prefs_update,
    )

    text_name: StringProperty(
        name="Target Text Name",
        default="PY_STDOUT.txt",
        update=_prefs_update,
    )

    clear_on_enable: BoolProperty(
        name="Clear Text when Enabling",
        default=False,
        update=_prefs_update,
    )

    also_console: BoolProperty(
        name="Also Write to Original Console",
        default=False,
        update=_prefs_update,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "enabled")
        col = layout.column(align=True)
        col.prop(self, "text_name")
        col.prop(self, "clear_on_enable")
        col.prop(self, "also_console")
        layout.separator()
        layout.label(text="View output: Text Editor dropdown -> Target Text Name")


classes = (StdoutToTextPreferences,)


def register():
    for c in classes:
        bpy.utils.register_class(c)

    # Do NOT apply immediately; schedule to avoid prefs-not-ready issues in Blender 5.0.
    _schedule_apply()


def unregister():
    _uninstall_redirect()
    for c in reversed(classes):
        bpy.utils.unregister_class(c)

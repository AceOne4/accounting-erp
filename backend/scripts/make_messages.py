"""Update and compile the Arabic translations without GNU gettext (works on Windows).

    python scripts/make_messages.py          # add new msgids to django.po, compile django.mo
    python scripts/make_messages.py --check  # fail if any message is untranslated

It finds every string passed to _(), gettext(), gettext_lazy(), pgettext... in the backend
code, keeps the translations already in locale/ar/LC_MESSAGES/django.po and adds the new
ones with an empty translation for a translator to fill in.
"""
import ast
import sys
from pathlib import Path

import polib

BASE = Path(__file__).resolve().parent.parent
PO = BASE / "locale" / "ar" / "LC_MESSAGES" / "django.po"
FUNCS = {"_", "gettext", "gettext_lazy", "ugettext"}
SKIP = {".venv", "migrations", "locale", "scripts", "__pycache__"}


def collect():
    found = {}
    for path in BASE.rglob("*.py"):
        if SKIP & set(path.relative_to(BASE).parts) or path.name.startswith("test"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in FUNCS
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                found.setdefault(node.args[0].value, f"{path.relative_to(BASE)}:{node.lineno}")
    return found


def main():
    po = polib.pofile(str(PO), encoding="utf-8")
    have = {e.msgid for e in po}
    for msgid, where in collect().items():
        if msgid not in have:
            po.append(polib.POEntry(msgid=msgid, msgstr="", occurrences=[tuple(where.rsplit(":", 1))]))
    po.save(str(PO))
    missing = [e.msgid for e in po if not e.msgstr and not e.obsolete]
    po.save_as_mofile(str(PO.with_suffix(".mo")))
    print(f"{len(po)} messages, {len(missing)} untranslated; compiled {PO.with_suffix('.mo').name}")
    for m in missing:
        print("  -", m)
    if "--check" in sys.argv and missing:
        sys.exit(1)


if __name__ == "__main__":
    main()

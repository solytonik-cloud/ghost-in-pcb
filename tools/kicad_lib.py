"""Чтение символов из стандартных библиотек KiCad (.kicad_sym) без внешних зависимостей."""
import re
from pathlib import Path

SYMBOL_DIR = Path(r"C:\Program Files\KiCad\10.0\share\kicad\symbols")


def _block(text, start):
    """Возвращает s-выражение, начинающееся с '(' в позиции start."""
    depth, i, in_str = 0, start, False
    while i < len(text):
        c = text[i]
        if in_str:
            if c == "\\":
                i += 1
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
        i += 1
    raise ValueError("unbalanced")


def load_symbol(lib, name):
    """Текст символа верхнего уровня (вложенные единицы внутри). Разворачивает extends."""
    text = (SYMBOL_DIR / f"{lib}.kicad_sym").read_text(encoding="utf-8")
    m = re.search(r'\n\t\(symbol "' + re.escape(name) + r'"\s', text)
    if not m:
        raise KeyError(f"{lib}:{name}")
    blk = _block(text, m.start() + 2)
    ext = re.search(r'\(extends "([^"]+)"\)', blk)
    if ext:
        parent = load_symbol(lib, ext.group(1))
        # берём графику и выводы родителя, переименовываем единицы
        parent = parent.replace(f'(symbol "{ext.group(1)}_', f'(symbol "{name}_')
        parent = parent.replace(f'(symbol "{ext.group(1)}"', f'(symbol "{name}"', 1)
        # свойства потомка заменяют свойства родителя
        for prop in re.finditer(r'\(property "([^"]+)"', blk):
            pname = prop.group(1)
            child_prop = _block(blk, prop.start())
            pm = re.search(r'\(property "' + re.escape(pname) + '"', parent)
            if pm:
                parent = parent[:pm.start()] + child_prop + parent[pm.start() + len(_block(parent, pm.start())):]
        blk = parent
    return blk


def pins(symbol_text):
    """{номер: (x, y, угол, длина, имя)} в координатах библиотеки (ось Y вверх)."""
    out = {}
    for m in re.finditer(r"\(pin \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)\s*\(length ([\d.]+)\)", symbol_text):
        rest = _block(symbol_text, m.start())
        name = re.search(r'\(name "([^"]*)"', rest).group(1)
        num = re.search(r'\(number "([^"]*)"', rest).group(1)
        out[num] = (float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4)), name)
    return out


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    for spec in sys.argv[1:]:
        lib, name = spec.split(":")
        s = load_symbol(lib, name)
        print(spec, "extends" if "extends" in s else "")
        for k, v in sorted(pins(s).items(), key=lambda kv: kv[0]):
            print("  ", k, v)

"""Минимальный генератор схем KiCad (.kicad_sch) из описания на Python.

Соединения: цепи (nets) задаются списками выводов "REF.PIN". Выводы, соединённые
явными проводами (wires), образуют группу; если у цепи несколько групп, каждая
получает метку с именем цепи. Цепи питания (POWER_NETS) рисуются символами питания.
"""
import math
import uuid as _uuid
from collections import defaultdict

from kicad_lib import load_symbol, pins

STUB = 2.54
POWER_SYMBOL_DIR = {"GND": 270, "GNDPWR": 270, "+15V": 90, "PWR_FLAG": 90}


def uid():
    return str(_uuid.uuid4())


def r2(v):
    return round(v + 0.0, 4)


def _fmt(v):
    return f"{r2(v):g}"


class Part:
    def __init__(self, ref, lib_id, value, x, y, rot=0, ref_pos=None, val_pos=None):
        self.ref, self.lib_id, self.value = ref, lib_id, value
        self.x, self.y, self.rot = x, y, rot
        lib, name = lib_id.split(":")
        self.sym = load_symbol(lib, name)
        self.pins = pins(self.sym)
        self.ref_pos, self.val_pos = ref_pos, val_pos

    def pin_tip(self, num):
        px, py, ang, _, _ = self.pins[num]
        a = math.radians(self.rot)
        rx = px * math.cos(a) - py * math.sin(a)
        ry = px * math.sin(a) + py * math.cos(a)
        return r2(self.x + rx), r2(self.y - ry)

    def pin_out_dir(self, num):
        """Направление «наружу» от вывода, градусы на экране (0 — вправо, 90 — вверх)."""
        ang = self.pins[num][2]
        return (ang + 180 + self.rot) % 360


class Schematic:
    def __init__(self, title, project, paper="A3"):
        self.title, self.project, self.paper = title, project, paper
        self.root = uid()
        self.parts, self.nets, self.wires, self.rails = {}, {}, [], []
        self.rotate_power = set()
        self.manual_labels = {}     # вывод группы -> (x, y, направление)   # выводы, у которых символ питания поворачивается вместо отвода
        self.items = []
        self.pwr_count = 0
        self.lib_cache = {}

    # --- описание ---
    def add(self, *a, **kw):
        p = Part(*a, **kw)
        self.parts[p.ref] = p
        return p

    def net(self, name, *pin_refs):
        self.nets.setdefault(name, []).extend(pin_refs)

    def wire(self, a, b, via=None):
        """Провод между выводами a и b ('REF.PIN'); via — точка излома (x, y)."""
        self.wires.append((a, b, via))

    def rail(self, *prefs, y=None, x=None):
        """Шина: горизонтальная (y=…) или вертикальная (x=…) линия, к которой
        выводы подходят перпендикулярными отводами. Узлы ставятся автоматически."""
        self.rails.append((prefs, y, x))

    def text(self, s, x, y, size=1.8, bold=False):
        self.items.append(
            f'(text "{s}" (exclude_from_sim no) (at {_fmt(x)} {_fmt(y)} 0) '
            f'(effects (font (size {size} {size}){" (bold yes)" if bold else ""}) (justify left bottom)) (uuid "{uid()}"))')

    def dot(self, x, y):
        self.items.append(
            f'(circle (center {_fmt(x)} {_fmt(y)}) (radius 0.55) (stroke (width 0) (type default)) '
            f'(fill (type color) (color 0 0 0 1)) (uuid "{uid()}"))')

    # --- генерация ---
    def _tip(self, pref):
        ref, num = pref.split(".")
        return self.parts[ref].pin_tip(num)

    def _seg(self, a, b):
        self.items.append(
            f'(wire (pts (xy {_fmt(a[0])} {_fmt(a[1])}) (xy {_fmt(b[0])} {_fmt(b[1])})) '
            f'(stroke (width 0) (type default)) (uuid "{uid()}"))')

    def _junction(self, x, y):
        self.items.append(f'(junction (at {_fmt(x)} {_fmt(y)}) (diameter 0) (color 0 0 0 0) (uuid "{uid()}"))')

    def _power_at_pin(self, name, pref):
        """Символ питания у вывода: GND всегда «вниз», +V — «вверх», с изломом при необходимости."""
        ex, ey, d = self._stub(pref)
        want = POWER_SYMBOL_DIR[name]
        if d == want or pref in self.rotate_power or d == (want + 180) % 360:
            self._power(name, ex, ey, d)
            return
        ny = r2(ey + (STUB if want == 270 else -STUB))
        self._seg((ex, ey), (ex, ny))
        self._power(name, ex, ny, want)

    def _power(self, lib_name, x, y, out_dir):
        self.pwr_count += 1
        base = POWER_SYMBOL_DIR[lib_name]
        rot = (out_dir - base) % 360
        ref = f"#PWR{self.pwr_count:02d}" if lib_name != "PWR_FLAG" else f"#FLG{self.pwr_count:02d}"
        p = Part(ref, f"power:{lib_name}", lib_name, x, y, rot)
        self.items.append(self._symbol_sexpr(p, hide_ref=True, val_offset=out_dir))

    def _label(self, name, x, y, out_dir):
        just = "left bottom" if out_dir in (0, 90) else "right bottom"
        self.items.append(
            f'(label "{name}" (at {_fmt(x)} {_fmt(y)} {out_dir}) '
            f'(effects (font (size 1.27 1.27)) (justify {just})) (uuid "{uid()}"))')

    def _stub(self, pref):
        ref, num = pref.split(".")
        p = self.parts[ref]
        x, y = p.pin_tip(num)
        d = p.pin_out_dir(num)
        ex = r2(x + STUB * math.cos(math.radians(d)))
        ey = r2(y - STUB * math.sin(math.radians(d)))
        self._seg((x, y), (ex, ey))
        return ex, ey, d

    def label_on(self, pref, x, y, out_dir=0):
        """Метка цепи вывода pref в точке (x, y) на проводе его группы."""
        self.manual_labels[pref] = (x, y, out_dir)

    def flag(self, net, x, y, down=True):
        """PWR_FLAG над точкой (x, y), подключённый к цепи коротким проводом."""
        self._power("PWR_FLAG", x, y, 90)
        self._seg((x, y), (x, r2(y + STUB)))
        if net in POWER_SYMBOL_DIR:
            self._power(net, x, r2(y + STUB), 270)
        else:
            self._label(net, x, r2(y + STUB), 0)

    def _symbol_sexpr(self, p, hide_ref=False, val_offset=None):
        lib_sym = p.sym.replace(f'(symbol "{p.lib_id.split(":")[1]}"', f'(symbol "{p.lib_id}"', 1)
        self.lib_cache[p.lib_id] = lib_sym
        tips = [p.pin_tip(n) for n in p.pins]
        horizontal = len(tips) == 2 and tips[0][1] == tips[1][1]
        if p.ref_pos:
            rx, ry = p.ref_pos
        elif horizontal:
            rx, ry = p.x, p.y - 2.54
        else:
            rx, ry = p.x + 2.54, p.y - 1.27
        if p.val_pos:
            vx, vy = p.val_pos
        elif hide_ref:
            off = 4.5
            dx = off * math.cos(math.radians(val_offset or 270))
            dy = -off * math.sin(math.radians(val_offset or 270))
            vx, vy = p.x + dx, p.y + dy
        elif horizontal:
            vx, vy = p.x, p.y + 3.3
        else:
            vx, vy = p.x + 2.54, p.y + 1.27
        just = "" if horizontal or hide_ref else " (justify left)"
        fa = 90 if p.rot in (90, 270) else 0
        hide_val = hide_ref and p.rot != 0 and p.lib_id != "power:PWR_FLAG"
        props = (
            f'(property "Reference" "{p.ref}" (at {_fmt(rx)} {_fmt(ry)} {fa}){" (hide yes)" if hide_ref else ""} '
            f'(effects (font (size 1.27 1.27)){just}))'
            f'(property "Value" "{p.value}" (at {_fmt(vx)} {_fmt(vy)} {fa}){" (hide yes)" if hide_val else ""} '
            f'(effects (font (size 1.27 1.27)){just}))'
            f'(property "Footprint" "" (at {_fmt(p.x)} {_fmt(p.y)} 0) (hide yes) (effects (font (size 1.27 1.27))))'
            f'(property "Datasheet" "" (at {_fmt(p.x)} {_fmt(p.y)} 0) (hide yes) (effects (font (size 1.27 1.27))))'
        )
        pin_s = "".join(f'(pin "{n}" (uuid "{uid()}"))' for n in p.pins)
        return (
            f'(symbol (lib_id "{p.lib_id}") (at {_fmt(p.x)} {_fmt(p.y)} {p.rot}) (unit 1) '
            f'(exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) (uuid "{uid()}") {props} {pin_s} '
            f'(instances (project "{self.project}" (path "/{self.root}" (reference "{p.ref}") (unit 1)))))'
        )

    def build(self):
        pin_net = {}
        for name, prefs in self.nets.items():
            for pr in prefs:
                if pr in pin_net:
                    raise ValueError(f"{pr} в двух цепях: {pin_net[pr]} и {name}")
                pin_net[pr] = name
        for ref, p in self.parts.items():
            for num in p.pins:
                if f"{ref}.{num}" not in pin_net:
                    raise ValueError(f"Вывод {ref}.{num} не подключён")

        # провода и группы
        group = {pr: pr for pr in pin_net}

        def find(a):
            while group[a] != a:
                group[a] = group[group[a]]
                a = group[a]
            return a

        for a, b, via in self.wires:
            if pin_net[a] != pin_net[b]:
                raise ValueError(f"Провод {a}–{b} соединяет разные цепи")
            ta, tb = self._tip(a), self._tip(b)
            if via:
                self._seg(ta, via)
                self._seg(via, tb)
            else:
                if ta[0] != tb[0] and ta[1] != tb[1]:
                    raise ValueError(f"Провод {a}–{b} не прямой: {ta} {tb}")
                self._seg(ta, tb)
            group[find(a)] = find(b)

        for prefs, ry, rx in self.rails:
            names = {pin_net[p] for p in prefs}
            if len(names) != 1:
                raise ValueError(f"Шина {prefs} соединяет разные цепи {names}")
            coords = []
            for p in prefs:
                tx, ty = self._tip(p)
                if ry is not None:
                    if ty != ry:
                        self._seg((tx, ty), (tx, ry))
                    coords.append((tx, ty != ry or None))
                else:
                    if tx != rx:
                        self._seg((tx, ty), (rx, ty))
                    coords.append((ty, tx != rx or None))
                group[find(p)] = find(prefs[0])
            pos = sorted({c for c, _ in coords})
            for a, b in zip(pos, pos[1:]):
                self._seg((a, ry), (b, ry)) if ry is not None else self._seg((rx, a), (rx, b))
            # узел там, где сходятся три и более проводника
            for c in pos:
                deg = (c != pos[0]) + (c != pos[-1]) + sum(1 for cc, _ in coords if cc == c)
                if deg >= 3:
                    self._junction(c, ry) if ry is not None else self._junction(rx, c)

        # метки и символы питания: по одной на группу
        done = set()
        for pr, name in pin_net.items():
            g = find(pr)
            if (name, g) in done:
                continue
            groups = {find(x) for x in self.nets[name]}
            is_power = name in POWER_SYMBOL_DIR
            if len(groups) == 1 and not is_power:
                done.add((name, g))
                continue
            members = [x for x in self.nets[name] if find(x) == g]
            if is_power:
                for m in members:  # символ питания у каждого вывода — так читаемее
                    self._power_at_pin(name, m)
            else:
                manual = [m for m in members if m in self.manual_labels]
                if manual:
                    self._label(name, *self.manual_labels[manual[0]])
                else:
                    ex, ey, d = self._stub(members[0])
                    self._label(name, ex, ey, d)
            done.add((name, g))

        for ref, p in self.parts.items():
            self.items.append(self._symbol_sexpr(p))

        libs = "\n".join(self.lib_cache.values())
        body = "\n".join(self.items)
        return (
            f'(kicad_sch (version 20250610) (generator "eeschema") (generator_version "10.0") '
            f'(uuid "{self.root}") (paper "{self.paper}") '
            f'(title_block (title "{self.title}") (rev "A") (company "Призрак в плате · t.me/ghost_in_pcb")) '
            f'(lib_symbols {libs})\n{body}\n'
            f'(sheet_instances (path "/" (page "1"))) (embedded_fonts no))\n'
        )

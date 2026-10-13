"""Расчёт обратноходового преобразователя 20 Вт, 220 В AC → 15 В DC (DCM, UC3843)."""
import math

# Требования
VAC_NOM, VAC_MIN, VAC_MAX = 220, 176, 264      # ±20 %
F_LINE = 50
VOUT, IOUT = 15.0, 1.33
EFF = 0.85
FSW = 65e3
VF_OUT, VF_AUX = 0.6, 0.8                      # диоды: Шоттки на выходе, быстрый на вспомогательной
VOR = 90.0                                      # отражённое напряжение
VCLAMP = 150.0                                  # уровень RCD-клампа над шиной
C_BULK = 47e-6
B_MAX, AE = 0.25, 45e-6                         # Тл; м² (сердечник EE25, ориентировочно)
VAUX = 13.0
LLK_FRAC = 0.02                                 # индуктивность рассеяния, доля от Lp

POUT = VOUT * IOUT
PIN = POUT / EFF
T = 1 / FSW

# Шина после выпрямителя
v_pk_min = VAC_MIN * math.sqrt(2)
t_dis = 0.7 / (2 * F_LINE)                      # ~70 % полупериода конденсатор отдаёт энергию
v_bulk_min = math.sqrt(v_pk_min**2 - 2 * PIN * t_dis / C_BULK)
v_bulk_max = VAC_MAX * math.sqrt(2)

# Трансформатор
n = VOR / (VOUT + VF_OUT)
d_bcm = VOR / (VOR + v_bulk_min)
lp_bcm = (v_bulk_min * d_bcm) ** 2 / (2 * PIN * FSW)
LP = 1.2e-3                                      # берём меньше граничной → гарантированный DCM
d = math.sqrt(2 * PIN * FSW * LP) / v_bulk_min
ipk = v_bulk_min * d / (LP * FSW)
t_on, t_off = d * T, LP * ipk / VOR
ip_rms = ipk * math.sqrt(d / 3)
np_ = LP * ipk / (B_MAX * AE)
NP = round(np_)
NS = round(NP / n)
n_real = NP / NS
NAUX = round(NS * (VAUX + VF_AUX) / (VOUT + VF_OUT))

# Ключ и клампы
vds_max = v_bulk_max + VCLAMP
llk = LLK_FRAC * LP
p_clamp = 0.5 * llk * ipk**2 * FSW * VCLAMP / (VCLAMP - VOR)
r_clamp = VCLAMP**2 / p_clamp

# Токовый датчик UC3843 (порог 1,0 В)
R_SENSE = 1.0
i_limit = 1.0 / R_SENSE
p_sense = ip_rms**2 * R_SENSE

# Генератор UC3843: f ≈ 1.72 / (RT·CT)
CT = 2.2e-9
rt = 1.72 / (FSW * CT)

# Вторичка
is_pk = ipk * n_real
d2 = t_off / T
is_rms = is_pk * math.sqrt(d2 / 3)
ic_rms = math.sqrt(is_rms**2 - IOUT**2)
vr_diode = VOUT + v_bulk_max / n_real

# Запуск
I_START = 0.5e-3
r_start_max = (v_bulk_min - 8.4) / I_START
R_START = 2 * 200e3
p_start = (v_bulk_max - 13) ** 2 / R_START

# Делитель TL431: Vout = 2.495·(1 + R1/R2)
R1, R2 = 11e3, 2.2e3
vout_set = 2.495 * (1 + R1 / R2)

rows = [
    ("Выходная мощность", f"{POUT:.1f} Вт"),
    ("Входная мощность (КПД 85 %)", f"{PIN:.1f} Вт"),
    ("Шина DC: мин / макс", f"{v_bulk_min:.0f} / {v_bulk_max:.0f} В"),
    ("Коэффициент трансформации Np/Ns", f"{n:.2f} → {NP}:{NS} = {n_real:.2f}"),
    ("Граничная индуктивность (BCM)", f"{lp_bcm*1e3:.2f} мГн"),
    ("Индуктивность первички Lp", f"{LP*1e3:.1f} мГн"),
    ("Коэффициент заполнения при Vmin", f"{d:.3f}"),
    ("Пиковый ток первички", f"{ipk:.2f} А"),
    ("tвкл + tразм / период", f"{t_on*1e6:.1f} + {t_off*1e6:.1f} / {T*1e6:.1f} мкс"),
    ("Витки Np / Ns / Naux (EE25)", f"{NP} / {NS} / {NAUX}"),
    ("Напряжение на стоке, макс", f"{vds_max:.0f} В (ключ 650 В)"),
    ("Мощность в RCD-клампе", f"{p_clamp:.2f} Вт, Rкл ≈ {r_clamp/1e3:.0f} кОм"),
    ("Порог ограничения тока (Rs = 1 Ом)", f"{i_limit:.2f} А, Ps = {p_sense*1e3:.0f} мВт"),
    ("RT при CT = 2,2 нФ", f"{rt/1e3:.1f} кОм → 12 кОм"),
    ("Пиковый ток вторички", f"{is_pk:.1f} А"),
    ("Пульсирующий ток выходных конденсаторов", f"{ic_rms:.2f} А RMS"),
    ("Обратное напряжение на выходном диоде", f"{vr_diode:.0f} В (+выброс) → 150 В"),
    ("Пусковой резистор, макс / выбран", f"{r_start_max/1e3:.0f} / {R_START/1e3:.0f} кОм, {p_start:.2f} Вт"),
    ("Выход по делителю 11k / 2,2k", f"{vout_set:.2f} В"),
]

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    for k, v in rows:
        print(f"{k:42} {v}")

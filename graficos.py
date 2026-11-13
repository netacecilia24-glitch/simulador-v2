"""
Gráficos do simulador solar (matplotlib).

Os gráficos apenas DESENHAM resultados já calculados em solar.py; nenhuma
equação é recalculada aqui.
"""
import math

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

import solar
from solar import T

# Paleta (energia solar)
AMARELO = "#F5B700"
LARANJA = "#F97316"
AZUL = "#1D4ED8"
AZUL_CLARO = "#0EA5E9"
AZUL_ESCURO = "#0B1F44"
CINZA = "#64748B"
CINZA_CLARO = "#CBD5E1"
VERMELHO = "#DC2626"

plt.rcParams.update({
    "font.size": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.edgecolor": CINZA,
    "axes.labelcolor": AZUL_ESCURO,
    "xtick.color": CINZA,
    "ytick.color": CINZA,
    "axes.titleweight": "bold",
    "axes.titlecolor": AZUL_ESCURO,
})


def _horas_eixo(ax):
    """Eixo X de 0 a 24 h, com marcas de hora em hora."""
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25))
    ax.set_xticklabels([f"{h:02d}" for h in range(0, 25)], fontsize=8)
    ax.grid(axis="x", color=CINZA_CLARO, alpha=0.6, lw=0.7)
    ax.set_xlabel("Horário local (h)")


def _segmentos(mascara):
    idx = np.flatnonzero(mascara)
    if idx.size == 0:
        return []
    return np.split(idx, np.flatnonzero(np.diff(idx) > 1) + 1)


# ==========================================================================
# 1. Trajetória aparente do Sol (altura × horário)
# ==========================================================================
def grafico_trajetoria(res, ad, traj):
    t = np.array(traj["t"])
    alt = np.array(traj["alpha"])

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.fill_between(t, -90, 90, where=alt > 0, color=AMARELO, alpha=0.15, lw=0, interpolate=True)
    ax.fill_between(t, -90, 90, where=alt <= 0, color=AZUL_ESCURO, alpha=0.10, lw=0, interpolate=True)

    ax.axhline(0, color=AZUL_ESCURO, lw=1.6, zorder=2)
    ax.text(23.85, 2.5, "Horizonte", ha="right", va="bottom", fontsize=8.5,
            fontweight="bold", color=AZUL_ESCURO)

    ax.plot(t, np.where(alt > 0, alt, np.nan), color=LARANJA, lw=3, zorder=3)
    ax.plot(t, np.where(alt <= 0, alt, np.nan), color=AZUL_CLARO, lw=1.8, ls="--", zorder=3)

    # nascer, meio-dia solar e pôr do sol (quando calculáveis)
    eventos = [(ad.t_meio_dia, "Meio-dia solar")]
    if ad.t_nascer is not None:
        eventos += [(ad.t_nascer, "Nascer do Sol"), (ad.t_por, "Pôr do Sol")]
    for x, rotulo in eventos:
        ax.axvline(x, color=CINZA, ls=":", lw=1.2, zorder=1)
        ax.text(x - 0.12, -87, f"{rotulo} · {solar.hm(x)}", rotation=90,
                ha="right", va="bottom", fontsize=8.5, color=AZUL_ESCURO)
    alt_meio = solar.asind(solar.seno_altura(res.lat, res.delta, 0.0))
    ax.scatter([ad.t_meio_dia], [alt_meio], marker="D", s=42, color=AZUL, zorder=4)
    if ad.t_nascer is not None:
        ax.scatter([ad.t_nascer, ad.t_por], [0, 0], s=38, color=AZUL_ESCURO, zorder=4)
    else:
        aviso = ("O Sol não nasce neste dia (noite contínua)" if ad.tipo_dia == "noite_continua"
                 else "O Sol não se põe neste dia (sol contínuo)")
        ax.text(12, -75, aviso, ha="center", fontsize=9, color=AZUL_ESCURO,
                bbox=dict(boxstyle="round", fc="white", ec=CINZA_CLARO))

    # posição no horário informado
    ax.scatter([res.t_rel], [res.alpha], s=300, color=AMARELO, edgecolor=LARANJA,
               linewidth=2.5, zorder=6)
    dx = 28 if res.t_rel < 15 else -150
    dy = -60 if res.alpha > 25 else 45
    ax.annotate(f"{res.hora:%H:%M} · α = {T(res.alpha, 1)}°",
                xy=(res.t_rel, res.alpha), xytext=(dx, dy), textcoords="offset points",
                fontsize=9, fontweight="bold", color=AZUL_ESCURO,
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=LARANJA),
                arrowprops=dict(arrowstyle="-", color=LARANJA, lw=1.4), zorder=7)

    _horas_eixo(ax)
    ax.set_ylim(-90, 90)
    ax.set_yticks(range(-90, 91, 30))
    ax.set_ylabel("Altura solar α (°)")
    ax.set_title(f"Trajetória aparente do Sol · {res.data:%d/%m/%Y} · "
                 f"φ = {T(res.lat, 2)}°, λ = {T(res.lon, 2)}°", loc="left", fontsize=11)

    fig.legend(
        handles=[
            Line2D([0], [0], color=LARANJA, lw=3, label="Altura solar (Sol acima do horizonte)"),
            Line2D([0], [0], color=AZUL_CLARO, lw=1.8, ls="--", label="Altura solar (abaixo do horizonte)"),
            Line2D([0], [0], marker="o", color="w", markerfacecolor=AMARELO, markeredgecolor=LARANJA,
                   markeredgewidth=2, markersize=11, label="Horário informado"),
            Patch(facecolor=AMARELO, alpha=0.25, label="Dia"),
            Patch(facecolor=AZUL_ESCURO, alpha=0.18, label="Noite"),
        ],
        loc="lower center", ncol=3, frameon=False, fontsize=8.5,
    )
    fig.tight_layout(rect=[0, 0.11, 1, 1])
    return fig


# ==========================================================================
# 1b. Irradiância ao longo do dia
# ==========================================================================
def grafico_irradiancia_dia(res, traj):
    t = np.array(traj["t"])
    g0h = np.array(traj["g0h"])
    ghi = np.array(traj["ghi"])

    fig, ax = plt.subplots(figsize=(10, 4.4))
    ax.fill_between(t, 0, ghi, color=AZUL_CLARO, alpha=0.18, lw=0)
    ax.plot(t, g0h, color=AMARELO, lw=2.8, label="G0h · topo da atmosfera (horizontal)")
    ax.plot(t, ghi, color=AZUL, lw=2.8, label="GHI · solo, céu limpo (Haurwitz)")
    ax.scatter([res.t_rel], [res.g0h], s=70, color=AMARELO, edgecolor=LARANJA, linewidth=2, zorder=5)
    ax.scatter([res.t_rel], [res.ghi], s=70, color=AZUL_CLARO, edgecolor=AZUL, linewidth=2, zorder=5)
    ax.axvline(res.t_rel, color=LARANJA, ls=":", lw=1.2)

    _horas_eixo(ax)
    ax.set_ylim(0, max(max(g0h), 100) * 1.12)
    ax.set_ylabel("Irradiância (W/m²)")
    ax.set_title(f"Irradiância ao longo do dia · {res.data:%d/%m/%Y}", loc="left", fontsize=11)
    ax.legend(loc="upper left", frameon=False, fontsize=8.5)
    fig.tight_layout()
    return fig


# ==========================================================================
# 2. Casa, telhado, Sol e raios (3D simplificado)
# ==========================================================================
def _mix(c1, c2, t):
    return tuple((1 - t) * a + t * b for a, b in zip(c1, c2))


def grafico_casa(res, ad, vista=-60):
    """
    res: Resultado (para o horário de visualização); ad: Adicionais.
    Eixos: x = Leste, y = Norte, z = vertical.
    """
    acima = res.acima_horizonte
    g = math.radians(ad.az_telhado)
    u = np.array([math.sin(g), math.cos(g)])    # direção horizontal da água principal
    v = np.array([math.cos(g), -math.sin(g)])   # direção da cumeeira

    W, Lc, H = 5.0, 6.5, 2.6
    R = (W / 2.0) * math.tan(math.radians(ad.incl))

    def pt(uu, vv, z):
        p = uu * u + vv * v
        return (float(p[0]), float(p[1]), float(z))

    # cores do telhado conforme a incidência real (orientação + inclinação)
    escuro, base, claro = (0.36, 0.25, 0.22), (0.72, 0.30, 0.18), (0.99, 0.68, 0.12)

    def cor_telhado(c):
        return escuro if (not acima or c <= 0) else _mix(base, claro, min(1.0, c))

    polys, fcs, ecs, lws = [], [], [], []

    def face(vertices, fc, ec="#6B7280", lw=0.7):
        polys.append(vertices)
        fcs.append(fc)
        ecs.append(ec)
        lws.append(lw)

    hw, hl = W / 2.0, Lc / 2.0
    # paredes
    face([pt(hw, -hl, 0), pt(hw, hl, 0), pt(hw, hl, H), pt(hw, -hl, H)], "#EBDDCA")
    face([pt(-hw, -hl, 0), pt(-hw, hl, 0), pt(-hw, hl, H), pt(-hw, -hl, H)], "#DCCBB5")
    for s in (-1, 1):
        face([pt(-hw, s * hl, 0), pt(hw, s * hl, 0), pt(hw, s * hl, H),
              pt(0, s * hl, H + R), pt(-hw, s * hl, H)], "#F4E9DA")
    # porta e janelas
    face([pt(hw + 0.02, -0.55, 0), pt(hw + 0.02, 0.55, 0), pt(hw + 0.02, 0.55, 1.8),
          pt(hw + 0.02, -0.55, 1.8)], "#7C4A2D")
    for lado in (hw + 0.02, -hw - 0.02):
        for c in (-2.1, 2.1):
            face([pt(lado, c - 0.6, 1.0), pt(lado, c + 0.6, 1.0), pt(lado, c + 0.6, 2.0),
                  pt(lado, c - 0.6, 2.0)], "#BAE6FD")
    # telhado: água principal (voltada para o azimute γ) e água oposta
    face([pt(hw, -hl, H), pt(hw, hl, H), pt(0, hl, H + R), pt(0, -hl, H + R)],
         cor_telhado(ad.cos_inc), ec=AZUL, lw=2.2)
    face([pt(-hw, -hl, H), pt(-hw, hl, H), pt(0, hl, H + R), pt(0, -hl, H + R)],
         cor_telhado(ad.cos_inc_op), ec="#6B7280", lw=0.8)

    fig = plt.figure(figsize=(7.2, 6.2))
    ax = fig.add_subplot(111, projection="3d")
    try:
        ax.computed_zorder = False
    except Exception:  # noqa: BLE001
        pass

    # chão e bússola
    RAIO = 7.0
    ang = np.linspace(0, 2 * np.pi, 90)
    chao = Poly3DCollection([list(zip(RAIO * np.cos(ang), RAIO * np.sin(ang), np.zeros_like(ang)))],
                            facecolors="#EAF1F8", edgecolors=CINZA_CLARO, linewidths=1.2)
    chao.set_zorder(0)
    ax.add_collection3d(chao)
    nomes = ["N", "NE", "L", "SE", "S", "SO", "O", "NO"]
    for k in range(8):
        a = math.radians(45 * k)
        r1, r2 = (RAIO, RAIO + 0.9) if k % 2 == 0 else (RAIO, RAIO + 0.5)
        ax.plot([r1 * math.sin(a), r2 * math.sin(a)], [r1 * math.cos(a), r2 * math.cos(a)], [0, 0],
                color=CINZA, lw=1.4 if k % 2 == 0 else 0.9, zorder=1)
        cor = VERMELHO if k == 0 else (AZUL_ESCURO if k % 2 == 0 else CINZA)
        ax.text((RAIO + 1.5) * math.sin(a), (RAIO + 1.5) * math.cos(a), 0, nomes[k],
                ha="center", va="center", fontsize=11 if k % 2 == 0 else 8,
                fontweight="bold" if k % 2 == 0 else "normal", color=cor, zorder=1)

    casa = Poly3DCollection(polys, facecolors=fcs, edgecolors=ecs, linewidths=lws)
    casa.set_zorder(2)
    ax.add_collection3d(casa)

    # Sol, raios e direção de incidência
    centro = np.array([0.0, 0.0, H])
    if acima:
        al, az = math.radians(res.alpha), math.radians(ad.azimute)
        s = np.array([math.cos(al) * math.sin(az), math.cos(al) * math.cos(az), math.sin(al)])
        D = 7.5
        S = centro + D * s

        # direção do Sol no chão
        ax.plot([0, RAIO * math.sin(az)], [0, RAIO * math.cos(az)], [0, 0],
                color=LARANJA, lw=2, ls="--", zorder=1)

        # pontos do telhado atingidos pelos raios
        for sinal, c in ((1, ad.cos_inc), (-1, ad.cos_inc_op)):
            if c <= 0:
                continue
            for p in (0.2, 0.5, 0.8):
                for q in (0.25, 0.55, 0.85):
                    uu, vv, z = sinal * hw * (1 - q), -hl + Lc * p, H + R * q
                    x, y, zz = pt(uu, vv, z)
                    ax.plot([S[0], x], [S[1], y], [S[2], zz], color=AMARELO, lw=1.1, alpha=0.85, zorder=3)
                    ax.scatter([x], [y], [zz], s=16, color=LARANJA, depthshade=False, zorder=4)

        ax.scatter([S[0]], [S[1]], [S[2]], s=900, color=AMARELO, alpha=0.25, depthshade=False, zorder=5)
        ax.scatter([S[0]], [S[1]], [S[2]], s=330, color=AMARELO, edgecolor=LARANJA,
                   linewidth=2.2, depthshade=False, zorder=6)
        ax.quiver(S[0], S[1], S[2], *(-s * 3.6), color=LARANJA, linewidth=3,
                  arrow_length_ratio=0.28, zorder=6)
        titulo = (f"{res.hora:%H:%M} · Sol: altura {T(res.alpha, 1)}°, "
                  f"azimute {T(ad.azimute, 1)}° ({ad.rumo})")
    else:
        titulo = f"{res.hora:%H:%M} · Sol abaixo do horizonte (α = {T(res.alpha, 1)}°)"

    ax.set_title(titulo, fontsize=10.5, color=AZUL_ESCURO, fontweight="bold")
    LIM = 9.5
    ax.set_xlim(-LIM, LIM)
    ax.set_ylim(-LIM, LIM)
    ax.set_zlim(0, 11)
    ax.set_box_aspect((2 * LIM, 2 * LIM, 11), zoom=1.35)
    ax.view_init(elev=24, azim=vista)
    ax.set_axis_off()
    fig.subplots_adjust(left=0, right=1, bottom=0.06, top=0.94)
    fig.text(0.5, 0.02, "Contorno azul = água principal do telhado · cor do telhado = intensidade da incidência",
             ha="center", fontsize=8, color=CINZA)
    return fig


# ==========================================================================
# 3. Rosa dos ventos + orientação solar
# ==========================================================================
def _poly_polar(pontos_xy, n=24):
    """Densifica um polígono (x = Leste, y = Norte) e devolve (theta, r) para eixos polares."""
    xs, ys = [], []
    for (x0, y0), (x1, y1) in zip(pontos_xy, pontos_xy[1:] + pontos_xy[:1]):
        xs.extend(np.linspace(x0, x1, n, endpoint=False))
        ys.extend(np.linspace(y0, y1, n, endpoint=False))
    xs, ys = np.array(xs), np.array(ys)
    return np.arctan2(xs, ys), np.hypot(xs, ys)


def _estrela(ax, a_graus, comp, larg, cor, alpha, zorder):
    a = math.radians(a_graus)
    fx, fy = math.sin(a), math.cos(a)  # direção (E, N)
    px, py = math.cos(a), -math.sin(a)  # perpendicular
    d = 0.17
    pts = [(comp * fx, comp * fy),
           (d * fx + larg * px, d * fy + larg * py), (0.0, 0.0),
           (d * fx - larg * px, d * fy - larg * py)]
    th, r = _poly_polar(pts)
    ax.fill(th, r, color=cor, alpha=alpha, zorder=zorder, lw=0)


def grafico_rosa(res, ad, traj):
    acima = res.acima_horizonte
    fig = plt.figure(figsize=(6, 6.8))
    ax = fig.add_axes([0.15, 0.17, 0.70, 0.62], projection="polar")
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 1)
    ax.set_yticks([])
    ax.set_xticks([])
    ax.spines["polar"].set_color(CINZA)

    # anéis de altura solar (0°, 30°, 60°)
    th = np.linspace(0, 2 * np.pi, 361)
    for elev in (30, 60):
        r = (90 - elev) / 90
        ax.plot(th, np.full_like(th, r), color=CINZA_CLARO, lw=0.9, zorder=1)
        ax.text(math.radians(22), r, f"{elev}°", fontsize=7, color=CINZA, ha="left", va="bottom", zorder=1)
    ax.text(math.radians(22), 1.0, "0°", fontsize=7, color=CINZA, ha="left", va="bottom")

    # estrela: cardeais e colaterais
    for k in range(4):
        _estrela(ax, 45 + 90 * k, 0.60, 0.07, CINZA, 0.45, 1)
    for k in range(4):
        _estrela(ax, 90 * k, 0.93, 0.09, VERMELHO if k == 0 else AZUL_ESCURO, 0.88, 2)

    nomes = ["Norte", "Nordeste", "Leste", "Sudeste", "Sul", "Sudoeste", "Oeste", "Noroeste"]
    for k, nome in enumerate(nomes):
        a = math.radians(45 * k)
        card = k % 2 == 0
        ax.text(a, 1.17 if card else 1.19, nome, ha="center", va="center",
                fontsize=10.5 if card else 8, fontweight="bold" if card else "normal",
                color=(VERMELHO if k == 0 else AZUL_ESCURO) if card else CINZA, clip_on=False)

    # trajetória do dia no céu (azimute × altura)
    alt = np.array(traj["alpha"])
    azs = np.radians(np.array(traj["az"]))
    tt = np.array(traj["t"])
    for seg in _segmentos(alt > 0):
        ax.plot(np.unwrap(azs[seg]), (90 - alt[seg]) / 90, color=AMARELO, lw=2.6, alpha=0.75, zorder=3)
    for i in range(0, len(tt), 12):  # marcas de hora em hora
        if alt[i] > 0:
            ax.plot([azs[i]], [(90 - alt[i]) / 90], marker="o", ms=3.5, color=LARANJA, zorder=4)
            if int(round(tt[i])) % 3 == 0:
                ax.text(azs[i], (90 - alt[i]) / 90 - 0.045, f"{int(round(tt[i]))}h",
                        fontsize=7, color=CINZA, ha="center", va="center", zorder=4)

    # telhado: direção da água principal
    gr = math.radians(ad.az_telhado)
    ax.annotate("", xy=(gr, 0.80), xytext=(0, 0),
                arrowprops=dict(arrowstyle="-|>", color=AZUL, lw=2.2, mutation_scale=16), zorder=5)

    # Sol e direção de incidência dos raios
    A = math.radians(ad.azimute)
    if acima:
        r_sol = (90 - res.alpha) / 90
        ax.plot([A + math.pi, A + math.pi], [0, 0.97], color=LARANJA, lw=1.6, ls="--", alpha=0.6, zorder=5)
        ax.annotate("", xy=(0, 0), xytext=(A, r_sol),
                    arrowprops=dict(arrowstyle="-|>", color=LARANJA, lw=3.2, mutation_scale=22), zorder=6)
        ax.scatter([A], [r_sol], s=330, color=AMARELO, edgecolor=LARANJA, linewidth=2.4, zorder=7)
        sub = f"altura {T(res.alpha, 1)}°"
    else:
        ax.scatter([A], [1.0], s=200, facecolor="white", edgecolor=CINZA, linewidth=1.6, zorder=7)
        sub = "Sol abaixo do horizonte"

    fig.text(0.5, 0.965, f"Azimute solar: {T(ad.azimute, 1)}° ({ad.rumo})", ha="center",
             fontsize=12, fontweight="bold", color=AZUL_ESCURO)
    fig.text(0.5, 0.932, f"{res.hora:%H:%M} · {sub}", ha="center", fontsize=9, color=CINZA)

    fig.legend(
        handles=[
            Line2D([0], [0], marker="o", color="w", markerfacecolor=AMARELO, markeredgecolor=LARANJA,
                   markeredgewidth=2, markersize=11, label="Sol (posição no céu)"),
            Line2D([0], [0], color=LARANJA, lw=3, label="Direção dos raios solares"),
            Line2D([0], [0], color=AMARELO, lw=2.6, label="Trajetória do dia"),
            Line2D([0], [0], color=AZUL, lw=2.2, label=f"Água principal ({T(ad.az_telhado, 0)}°)"),
        ],
        loc="lower center", ncol=2, frameon=False, fontsize=8.5,
    )
    return fig

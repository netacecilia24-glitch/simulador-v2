"""
Cálculos do simulador solar.

Todas as equações são implementadas diretamente aqui (sem pvlib), na ordem
definida no projeto. Os ângulos são tratados em graus; a conversão para
radianos é feita apenas dentro de sind/cosd/asind.
"""
import math
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from typing import Optional
from zoneinfo import ZoneInfo

GSC = 1361.0  # constante solar (W/m²)


# --------------------------------------------------------------------------
# Trigonometria em graus
# --------------------------------------------------------------------------
def sind(a: float) -> float:
    return math.sin(math.radians(a))


def cosd(a: float) -> float:
    return math.cos(math.radians(a))


def asind(x: float) -> float:
    # limita o argumento a [-1, 1] para evitar erro por arredondamento
    return math.degrees(math.asin(max(-1.0, min(1.0, x))))


# --------------------------------------------------------------------------
# Formatação (vírgula decimal, só na apresentação)
# --------------------------------------------------------------------------
def _limpa(x: float, d: int) -> float:
    return 0.0 if round(x, d) == 0 else x  # evita "-0,00"


def T(x: float, d: int = 2) -> str:
    """Número em texto comum, com vírgula decimal."""
    return f"{_limpa(x, d):.{d}f}".replace(".", ",")


def L(x: float, d: int = 4) -> str:
    """Número em LaTeX, com vírgula decimal."""
    return f"{_limpa(x, d):.{d}f}".replace(".", "{,}")


def P(x: float, d: int = 4) -> str:
    """Número em LaTeX; negativos entre parênteses."""
    s = L(x, d)
    return f"({s})" if _limpa(x, d) < 0 else s


def hms(horas: float) -> str:
    """Horas decimais -> hh:mm:ss."""
    total = round(horas * 3600)
    return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"


def fill(modelo: str, **valores: str) -> str:
    for k, v in valores.items():
        modelo = modelo.replace(f"<<{k}>>", v)
    return modelo


# --------------------------------------------------------------------------
# Fuso horário
# --------------------------------------------------------------------------
_finder = None


@dataclass
class Fuso:
    nome: str
    deslocamento: float  # horas em relação ao UTC
    meridiano: float  # meridiano central (graus)
    identificado: bool
    avisos: list = field(default_factory=list)


def identificar_fuso(lat: float, lon: float, data: date, hora: time) -> Fuso:
    """Identifica o fuso IANA, o deslocamento UTC na data e o meridiano central."""
    global _finder
    from timezonefinder import TimezoneFinder

    if _finder is None:
        _finder = TimezoneFinder()

    nome = _finder.timezone_at(lat=lat, lng=lon)
    avisos = []

    if nome is None:
        # Sem fuso terrestre (ex.: oceano): estima pelo meridiano mais próximo.
        deslocamento = float(round(lon / 15.0))
        avisos.append(
            "Não há fuso IANA para essas coordenadas (ex.: mar aberto). "
            f"Foi estimado UTC{deslocamento:+.0f} a partir da longitude."
        )
        return Fuso("Estimado pela longitude", deslocamento, deslocamento * 15.0, False, avisos)

    zona = ZoneInfo(nome)
    local = datetime.combine(data, hora, tzinfo=zona)
    deslocamento = local.utcoffset().total_seconds() / 3600.0

    # horário inexistente (adiantamento do horário de verão)?
    volta = local.astimezone(timezone.utc).astimezone(zona)
    if volta.replace(tzinfo=None) != local.replace(tzinfo=None):
        avisos.append(
            "Esse horário não existe nesse dia (mudança de horário de verão). "
            "O deslocamento usado é o anterior à mudança."
        )
    # horário repetido (fim do horário de verão)?
    elif local.replace(fold=1).utcoffset() != local.utcoffset():
        avisos.append(
            "Esse horário ocorre duas vezes nesse dia (fim do horário de verão). "
            "Foi usada a primeira ocorrência."
        )

    return Fuso(nome, deslocamento, deslocamento * 15.0, True, avisos)


# --------------------------------------------------------------------------
# Equações (funções puras, usadas também na curva do dia)
# --------------------------------------------------------------------------
def declinacao(n: int) -> float:
    return 23.45 * sind(360.0 * (284 + n) / 365.0)


def equacao_tempo(n: int) -> float:
    B = 360.0 * (n - 81) / 364.0
    return 9.87 * sind(2 * B) - 7.53 * cosd(B) - 1.5 * sind(B)


def seno_altura(lat: float, delta: float, h: float) -> float:
    return sind(lat) * sind(delta) + cosd(lat) * cosd(delta) * cosd(h)


def irradiancia_extraterrestre_normal(n: int) -> float:
    return GSC * (1 + 0.033 * cosd(360.0 * n / 365.0))


def haurwitz(cosz: float) -> float:
    if cosz <= 0:
        return 0.0
    return 1098.0 * cosz * math.exp(-0.059 / cosz)


# --------------------------------------------------------------------------
# Resultado completo com passo a passo
# --------------------------------------------------------------------------
@dataclass
class Etapa:
    titulo: str
    formula: str  # LaTeX
    substituicao: str  # LaTeX
    resultado: str  # texto


@dataclass
class Resultado:
    data: date
    hora: time
    lat: float
    lon: float
    fuso: Fuso
    n: int
    delta: float
    cl: float
    B: float
    E: float
    t_rel: float
    t_sol_bruto: float
    t_sol: float
    dias_deslocados: int
    h: float
    alpha: float
    theta: float
    cosz: float
    gon: float
    g0h: float
    ghi: float
    acima_horizonte: bool
    etapas: list
    avisos: list


def calcular(data: date, hora: time, lat: float, lon: float, fuso: Fuso) -> Resultado:
    n = data.timetuple().tm_yday
    avisos = list(fuso.avisos)

    # ETAPA 1 — declinação solar
    arg_delta = 360.0 * (284 + n) / 365.0
    delta = declinacao(n)

    # ETAPA 2 — correção da longitude
    cl = 4.0 * (lon - fuso.meridiano)

    # ETAPA 3 — equação do tempo
    B = 360.0 * (n - 81) / 364.0
    E = equacao_tempo(n)

    # ETAPA 4 — hora solar verdadeira
    t_rel = hora.hour + hora.minute / 60.0 + hora.second / 3600.0
    t_sol_bruto = t_rel + (cl + E) / 60.0
    dias_deslocados = math.floor(t_sol_bruto / 24.0)  # -1, 0 ou +1
    t_sol = t_sol_bruto - 24.0 * dias_deslocados
    if dias_deslocados != 0:
        sentido = "seguinte" if dias_deslocados > 0 else "anterior"
        avisos.append(
            f"A correção levou a hora solar para o dia {sentido} ao informado. "
            "A hora solar foi normalizada para 0–24 h; o dia do ano (n) e a "
            "declinação continuam os da data informada (diferença desprezível)."
        )

    # ETAPA 5 — ângulo horário
    h = 15.0 * (t_sol - 12.0)

    # ETAPA 6 — altura solar
    seno_alpha = seno_altura(lat, delta, h)
    alpha = asind(seno_alpha)

    # ETAPA 7 — ângulo zenital
    theta = 90.0 - alpha
    cosz = cosd(theta)
    acima = alpha > 0

    # ETAPA 8 — irradiância extraterrestre normal
    gon = irradiancia_extraterrestre_normal(n)

    # ETAPA 9 — irradiância extraterrestre horizontal
    g0h = gon * cosz if acima else 0.0

    # ETAPA 10 — Haurwitz (céu limpo)
    ghi = haurwitz(cosz) if acima else 0.0

    if not acima:
        avisos.append("O Sol está abaixo do horizonte: as irradiâncias são zero.")

    etapas = [
        Etapa(
            "Etapa 1 — Declinação solar (δ)",
            r"\delta = 23{,}45^\circ \cdot \sin\!\left[\frac{360^\circ\,(284+n)}{365}\right]",
            fill(
                r"\delta = 23{,}45^\circ \cdot \sin\!\left[\frac{360^\circ\,(284+<<n>>)}{365}\right]"
                r" = 23{,}45^\circ \cdot \sin(<<arg>>^\circ)",
                n=str(n), arg=L(arg_delta),
            ),
            f"n = {n}  →  δ = {T(delta, 4)}°",
        ),
        Etapa(
            "Etapa 2 — Correção da longitude (CL)",
            r"CL = 4\,(\lambda - \lambda_c)",
            fill(
                r"CL = 4\,(<<lon>> - <<mc>>)",
                lon=P(lon), mc=P(fuso.meridiano),
            ),
            f"{fuso.nome}, UTC{fuso.deslocamento:+g}  →  CL = {T(cl, 4)} min",
        ),
        Etapa(
            "Etapa 3 — Equação do tempo (E)",
            r"\begin{aligned} B &= \frac{360^\circ\,(n-81)}{364} \\ "
            r"E &= 9{,}87\,\sin(2B) - 7{,}53\,\cos(B) - 1{,}5\,\sin(B) \end{aligned}",
            fill(
                r"\begin{aligned} B &= \frac{360^\circ\,(<<n>>-81)}{364} = <<B>>^\circ \\ "
                r"E &= 9{,}87\,\sin(<<B2>>^\circ) - 7{,}53\,\cos(<<B>>^\circ) - 1{,}5\,\sin(<<B>>^\circ) \end{aligned}",
                n=str(n), B=P(B), B2=P(2 * B),
            ),
            f"B = {T(B, 4)}°  →  E = {T(E, 4)} min",
        ),
        Etapa(
            "Etapa 4 — Hora solar verdadeira (T_sol)",
            r"T_{sol} = T_{rel\acute{o}gio} + \frac{CL + E}{60}",
            fill(
                r"T_{sol} = <<t>> + \frac{<<cl>> + <<e>>}{60} = <<ts>>\ \mathrm{h}",
                t=L(t_rel), cl=P(cl), e=P(E), ts=P(t_sol_bruto),
            ),
            f"T_relógio = {hms(t_rel)} ({T(t_rel, 4)} h)  →  T_sol = {hms(t_sol)} ({T(t_sol, 4)} h)",
        ),
        Etapa(
            "Etapa 5 — Ângulo horário (h)",
            r"h = 15^\circ \cdot (T_{sol} - 12)",
            fill(r"h = 15^\circ \cdot (<<ts>> - 12)", ts=L(t_sol)),
            f"h = {T(h, 4)}°  ({'manhã (antes do meio-dia solar)' if h < 0 else 'tarde (após o meio-dia solar)' if h > 0 else 'meio-dia solar'})",
        ),
        Etapa(
            "Etapa 6 — Altura solar (α)",
            r"\sin\alpha = \sin\varphi\,\sin\delta + \cos\varphi\,\cos\delta\,\cos h",
            fill(
                r"\begin{aligned} \sin\alpha &= \sin(<<lat>>^\circ)\,\sin(<<d>>^\circ) + "
                r"\cos(<<lat>>^\circ)\,\cos(<<d>>^\circ)\,\cos(<<h>>^\circ) = <<sa>> \\ "
                r"\alpha &= \arcsin(<<sa>>) \end{aligned}",
                lat=P(lat), d=P(delta), h=P(h), sa=P(seno_alpha, 6),
            ),
            f"α = {T(alpha, 4)}°",
        ),
        Etapa(
            "Etapa 7 — Ângulo zenital (θz)",
            r"\theta_z = 90^\circ - \alpha",
            fill(r"\theta_z = 90^\circ - <<a>>", a=P(alpha)),
            f"θz = {T(theta, 4)}°  (cos θz = {T(cosz, 6)})",
        ),
        Etapa(
            "Etapa 8 — Irradiância extraterrestre normal (Gon)",
            r"G_{on} = G_{sc}\left[1 + 0{,}033\,\cos\!\left(\frac{360^\circ\,n}{365}\right)\right]",
            fill(
                r"G_{on} = 1361\left[1 + 0{,}033\,\cos\!\left(\frac{360^\circ \cdot <<n>>}{365}\right)\right]",
                n=str(n),
            ),
            f"Gon = {T(gon, 2)} W/m²",
        ),
        Etapa(
            "Etapa 9 — Irradiância extraterrestre horizontal (G0h)",
            r"G_{0h} = G_{on}\,\cos\theta_z",
            (
                fill(r"G_{0h} = <<g>> \cdot <<c>>", g=L(gon, 2), c=L(cosz, 6))
                if acima
                else r"G_{0h} = 0 \quad (\text{Sol abaixo do horizonte: } \cos\theta_z \le 0)"
            ),
            f"G0h = {T(g0h, 2)} W/m²",
        ),
        Etapa(
            "Etapa 10 — Irradiância estimada no solo (Haurwitz, céu limpo)",
            r"GHI = 1098\,\cos\theta_z\,\exp\!\left[\frac{-0{,}059}{\cos\theta_z}\right]",
            (
                fill(
                    r"GHI = 1098 \cdot <<c>> \cdot \exp\!\left[\frac{-0{,}059}{<<c>>}\right]",
                    c=L(cosz, 6),
                )
                if acima
                else r"GHI = 0 \quad (\text{Sol abaixo do horizonte: } \cos\theta_z \le 0)"
            ),
            f"GHI = {T(ghi, 2)} W/m²  — estimativa para céu limpo, não é uma medição real",
        ),
    ]

    return Resultado(
        data=data, hora=hora, lat=lat, lon=lon, fuso=fuso, n=n, delta=delta,
        cl=cl, B=B, E=E, t_rel=t_rel, t_sol_bruto=t_sol_bruto, t_sol=t_sol,
        dias_deslocados=dias_deslocados, h=h, alpha=alpha, theta=theta,
        cosz=cosz, gon=gon, g0h=g0h, ghi=ghi, acima_horizonte=acima,
        etapas=etapas, avisos=avisos,
    )

def hm(horas: float) -> str:
    """Horas decimais -> hh:mm (0–24 h)."""
    total = round(horas * 60) % 1440
    return f"{total // 60:02d}:{total % 60:02d}"


# ==========================================================================
# CÁLCULOS ADICIONAIS
# Azimute solar, nascer/pôr do sol, trajetória do dia e incidência no telhado.
# São implementados separadamente: NÃO alteram nenhuma das 10 etapas originais
# e apenas reutilizam os resultados delas (δ, CL, E, h, α, θz, Gon, GHI).
# ==========================================================================
PONTOS = ["Norte", "Nordeste", "Leste", "Sudeste", "Sul", "Sudoeste", "Oeste", "Noroeste"]


def rumo(az: float) -> str:
    """Nome do ponto cardeal/colateral mais próximo de um azimute (graus)."""
    return PONTOS[int(round((az % 360.0) / 45.0)) % 8]


def _termos_azimute(lat: float, delta: float, h: float):
    cd = cosd(delta)
    y = sind(h) * cd
    x = cosd(h) * sind(lat) * cd - sind(delta) * cosd(lat)
    return y, x


def azimute_solar(lat: float, delta: float, h: float) -> float:
    """Azimute solar medido a partir do Norte, no sentido horário (0–360°)."""
    y, x = _termos_azimute(lat, delta, h)
    return (180.0 + math.degrees(math.atan2(y, x))) % 360.0


def cos_incidencia(alpha: float, az_sol: float, az_sup: float, incl: float) -> float:
    """cos do ângulo entre os raios solares e a normal de uma superfície inclinada."""
    return sind(alpha) * cosd(incl) + cosd(alpha) * sind(incl) * cosd(az_sol - az_sup)


@dataclass
class Adicionais:
    azimute: float
    rumo: str
    tipo_dia: str  # "normal", "sol_continuo" ou "noite_continua"
    h_nascer: Optional[float]  # ângulo horário do pôr do sol (graus, > 0)
    t_nascer: Optional[float]  # hora local do nascer (h)
    t_por: Optional[float]  # hora local do pôr (h)
    t_meio_dia: float  # hora local do meio-dia solar (h)
    az_telhado: float
    incl: float
    # água principal do telhado
    cos_inc: float
    theta_inc: float
    g0_telhado: float
    ghi_telhado: float
    # água oposta
    cos_inc_op: float
    theta_inc_op: float
    g0_op: float
    ghi_op: float
    etapas: list


def _ang(c: float) -> float:
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def calculos_adicionais(res: Resultado, az_telhado: float, incl: float) -> Adicionais:
    off = (res.cl + res.E) / 60.0  # (CL + E)/60, em horas

    # --- Azimute solar ----------------------------------------------------
    y, x = _termos_azimute(res.lat, res.delta, res.h)
    az = azimute_solar(res.lat, res.delta, res.h)

    # --- Nascer, meio-dia e pôr do sol -----------------------------------
    cos_hs = -math.tan(math.radians(res.lat)) * math.tan(math.radians(res.delta))
    t_meio = (12.0 - off) % 24.0
    if cos_hs >= 1.0:
        tipo, hs, t_nasc, t_por = "noite_continua", None, None, None
    elif cos_hs <= -1.0:
        tipo, hs, t_nasc, t_por = "sol_continuo", None, None, None
    else:
        tipo = "normal"
        hs = math.degrees(math.acos(cos_hs))
        t_nasc = (12.0 - hs / 15.0 - off) % 24.0
        t_por = (12.0 + hs / 15.0 - off) % 24.0

    # --- Telhado (água principal e água oposta) --------------------------
    g_p = az_telhado % 360.0
    g_o = (g_p + 180.0) % 360.0
    acima = res.acima_horizonte
    dni_est = res.ghi / res.cosz if acima else 0.0  # irradiância normal equivalente

    def plano(g):
        c = cos_incidencia(res.alpha, az, g, incl)
        ilum = acima and c > 0
        return c, _ang(c), (res.gon * c if ilum else 0.0), (dni_est * c if ilum else 0.0)

    c_p, th_p, g0_p, gs_p = plano(g_p)
    c_o, th_o, g0_o, gs_o = plano(g_o)

    # --- Passo a passo dos cálculos adicionais ---------------------------
    et_az = Etapa(
        "Azimute solar (A)",
        r"A = 180^\circ + \operatorname{atan2}\!\left(\sin h\,\cos\delta,\ "
        r"\cos h\,\sin\varphi\,\cos\delta - \sin\delta\,\cos\varphi\right)",
        fill(
            r"A = 180^\circ + \operatorname{atan2}(<<y>>,\ <<x>>)",
            y=P(y, 6), x=P(x, 6),
        ),
        f"A = {T(az, 2)}° (medido a partir do Norte, no sentido horário) → {rumo(az)}",
    )

    if tipo == "normal":
        et_nasc = Etapa(
            "Nascer, meio-dia solar e pôr do sol",
            r"\begin{aligned} \cos h_s &= -\tan\varphi\,\tan\delta \\ "
            r"T_{sol}^{nascer} &= 12 - \frac{h_s}{15}, \quad T_{sol}^{p\hat{o}r} = 12 + \frac{h_s}{15} \\ "
            r"T_{rel\acute{o}gio} &= T_{sol} - \frac{CL + E}{60} \end{aligned}",
            fill(
                r"\begin{aligned} \cos h_s &= -\tan(<<lat>>^\circ)\,\tan(<<d>>^\circ) = <<c>> "
                r"\;\Rightarrow\; h_s = <<hs>>^\circ \\ "
                r"T_{sol}^{nascer} &= 12 - \frac{<<hs>>}{15} = <<tn>>\ \mathrm{h}, \quad "
                r"T_{sol}^{p\hat{o}r} = 12 + \frac{<<hs>>}{15} = <<tp>>\ \mathrm{h} \\ "
                r"T_{rel\acute{o}gio} &= T_{sol} - \frac{<<cl>> + <<e>>}{60} \end{aligned}",
                lat=P(res.lat), d=P(res.delta), c=P(cos_hs, 6), hs=L(hs),
                tn=L(12 - hs / 15), tp=L(12 + hs / 15), cl=P(res.cl), e=P(res.E),
            ),
            f"Nascer {hm(t_nasc)} · meio-dia solar {hm(t_meio)} · pôr {hm(t_por)} "
            f"(horário local) · duração do dia {T(2 * hs / 15, 2)} h",
        )
    else:
        msg = (
            "Sol permanentemente abaixo do horizonte neste dia (noite contínua)."
            if tipo == "noite_continua"
            else "Sol permanentemente acima do horizonte neste dia (sol da meia-noite)."
        )
        et_nasc = Etapa(
            "Nascer, meio-dia solar e pôr do sol",
            r"\cos h_s = -\tan\varphi\,\tan\delta",
            fill(r"\cos h_s = -\tan(<<lat>>^\circ)\,\tan(<<d>>^\circ) = <<c>>",
                 lat=P(res.lat), d=P(res.delta), c=P(cos_hs, 6)),
            f"|cos h_s| ≥ 1 → nascer e pôr do sol não calculáveis. {msg} "
            f"Meio-dia solar: {hm(t_meio)} (horário local).",
        )

    if acima:
        txt_roof = (
            f"cos θi = {T(c_p, 4)} → θi = {T(th_p, 2)}° · "
            + (f"G0,t = {T(g0_p, 2)} W/m² · G solo,t ≈ {T(gs_p, 2)} W/m²"
               if c_p > 0 else "raios não atingem esta água (cos θi ≤ 0): irradiância direta nula")
        )
    else:
        txt_roof = "Sol abaixo do horizonte: irradiância no telhado nula."
    et_roof = Etapa(
        "Incidência solar no telhado (água principal)",
        r"\begin{aligned} \cos\theta_i &= \sin\alpha\,\cos\beta + \cos\alpha\,\sin\beta\,\cos(A-\gamma) \\ "
        r"G_{0,t} &= G_{on}\,\cos\theta_i \\ "
        r"G_{solo,t} &\approx \frac{GHI}{\cos\theta_z}\,\cos\theta_i \end{aligned}",
        fill(
            r"\begin{aligned} \cos\theta_i &= \sin(<<a>>^\circ)\cos(<<b>>^\circ) + "
            r"\cos(<<a>>^\circ)\sin(<<b>>^\circ)\cos(<<A>>^\circ - <<g>>^\circ) = <<c>> \\ "
            r"G_{0,t} &= <<gon>> \cdot <<c>> = <<g0>>\ \mathrm{W/m^2} \\ "
            r"G_{solo,t} &\approx \frac{<<ghi>>}{<<cz>>} \cdot <<c>> = <<gs>>\ \mathrm{W/m^2} \end{aligned}",
            a=P(res.alpha), b=L(incl), A=L(az), g=L(g_p), c=P(c_p, 6),
            gon=L(res.gon, 2), g0=L(g0_p, 2), ghi=L(res.ghi, 2),
            cz=L(res.cosz, 6) if acima else "0", gs=L(gs_p, 2),
        ),
        txt_roof
        + " | β = inclinação do telhado; γ = azimute da água principal (Norte = 0°, sentido horário). "
          "A estimativa no solo considera apenas a componente direta (GHI/cos θz como irradiância "
          "normal equivalente); não inclui difusa nem refletida.",
    )

    return Adicionais(
        azimute=az, rumo=rumo(az), tipo_dia=tipo, h_nascer=hs,
        t_nascer=t_nasc, t_por=t_por, t_meio_dia=t_meio,
        az_telhado=g_p, incl=incl,
        cos_inc=c_p, theta_inc=th_p, g0_telhado=g0_p, ghi_telhado=gs_p,
        cos_inc_op=c_o, theta_inc_op=th_o, g0_op=g0_o, ghi_op=gs_o,
        etapas=[et_az, et_nasc, et_roof],
    )


def trajetoria_do_dia(res: Resultado, passos: int = 289) -> dict:
    """
    Trajetória aparente do Sol ao longo do dia (n e local da simulação),
    em função do horário local do relógio (0–24 h). Reutiliza as mesmas
    funções das etapas originais (δ, CL, E, altura, Gon, Haurwitz).
    """
    off = (res.cl + res.E) / 60.0
    out = {"t": [], "alpha": [], "az": [], "g0h": [], "ghi": []}
    for i in range(passos):
        t = 24.0 * i / (passos - 1)
        t_sol = (t + off) % 24.0
        h = 15.0 * (t_sol - 12.0)
        sa = seno_altura(res.lat, res.delta, h)
        a = asind(sa)
        out["t"].append(t)
        out["alpha"].append(a)
        out["az"].append(azimute_solar(res.lat, res.delta, h))
        out["g0h"].append(res.gon * sa if a > 0 else 0.0)  # cos θz = sen α
        out["ghi"].append(haurwitz(sa) if a > 0 else 0.0)
    return out

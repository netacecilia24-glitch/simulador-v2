from datetime import date, time, timedelta

import matplotlib.pyplot as plt
import streamlit as st

import graficos
import solar
from solar import T

st.set_page_config(
    page_title="Simulador Solar · Posição do Sol e Irradiância",
    page_icon="☀️",
    layout="wide",
)

# --------------------------------------------------------------------------
# Estilo
# --------------------------------------------------------------------------
st.markdown(
    """
<style>
.block-container {max-width: 1180px; padding-top: 1.6rem; padding-bottom: 3rem;}
.hero {background: linear-gradient(120deg, #0B1F44 0%, #1D4ED8 58%, #F59E0B 135%);
  color: #fff; padding: 1.5rem 1.8rem; border-radius: 16px; margin-bottom: 1.4rem;}
.hero h1 {color: #fff !important; font-size: 1.9rem; font-weight: 800; margin: 0; padding: 0;}
.hero p {color: #E2E8F0; margin: .35rem 0 0 0; font-size: 1rem;}
.secao {display: flex; align-items: center; gap: .8rem; margin: 2.2rem 0 .9rem 0;
  padding-bottom: .6rem; border-bottom: 2px solid #FDE68A;}
.secao .num {background: #F59E0B; color: #fff; font-weight: 800; border-radius: 50%;
  width: 2rem; height: 2rem; display: flex; align-items: center; justify-content: center; flex: none;}
.secao h2 {margin: 0; padding: 0; font-size: 1.35rem; color: #0B1F44;}
.secao p {margin: 0; color: #64748B; font-size: .88rem;}
.cards {display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 1rem; margin: .4rem 0 .6rem 0;}
.card {background: #fff; border: 1px solid #E2E8F0; border-top: 6px solid var(--accent);
  border-radius: 14px; padding: 1rem 1.2rem; box-shadow: 0 2px 10px rgba(15,23,42,.07);}
.card .rotulo {font-size: .78rem; color: #475569; font-weight: 700; text-transform: uppercase; letter-spacing: .04em;}
.card .valor {font-size: 2.5rem; font-weight: 800; color: #0B1F44; line-height: 1.2; margin-top: .2rem;}
.card .unid {font-size: 1.05rem; color: #64748B; font-weight: 600;}
.card .desc {font-size: .82rem; color: #64748B; margin-top: .2rem;}
[data-testid="stForm"] {border: 1px solid #E2E8F0; border-radius: 14px; background: #F8FAFC; padding: 1.2rem 1.4rem;}
[data-testid="stForm"] button {width: 100%; font-weight: 700;}
[data-testid="stMetric"] {background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 12px; padding: .7rem 1rem;}
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="hero"><h1>☀️ Simulador Solar</h1>'
    "<p>Posição aparente do Sol, irradiância e incidência da radiação sobre uma edificação "
    "· ferramenta didática com equações explícitas</p></div>",
    unsafe_allow_html=True,
)


def secao(num, titulo, sub=""):
    st.markdown(
        f'<div class="secao"><div class="num">{num}</div><div><h2>{titulo}</h2>'
        f"<p>{sub}</p></div></div>",
        unsafe_allow_html=True,
    )


def Tm(x, d=1):
    """Número com separador de milhar (.) e vírgula decimal."""
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def cartao(rotulo, valor, descricao, cor):
    return (
        f'<div class="card" style="--accent:{cor}"><div class="rotulo">{rotulo}</div>'
        f'<div class="valor">{valor}<span class="unid"> W/m²</span></div>'
        f'<div class="desc">{descricao}</div></div>'
    )


def mostrar(fig):
    st.pyplot(fig)
    plt.close(fig)


# --------------------------------------------------------------------------
# 1. Entrada de dados
# --------------------------------------------------------------------------
secao(1, "Dados de entrada", "Data, horário e localização · telhado opcional")

with st.form("entrada"):
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        data = st.date_input(
            "Data", value=date.today(), min_value=date(1900, 1, 1),
            max_value=date(2100, 12, 31), format="DD/MM/YYYY",
        )
    with c2:
        hora = st.time_input("Horário local (hh:mm)", value=time(12, 0), step=60)
    with c3:
        lat = st.number_input(
            "Latitude (°)", min_value=-90.0, max_value=90.0, value=-12.60,
            step=0.01, format="%.5f", help="Graus decimais. Sul é negativo.",
        )
    with c4:
        lon = st.number_input(
            "Longitude (°)", min_value=-180.0, max_value=180.0, value=-38.97,
            step=0.01, format="%.5f", help="Graus decimais. Oeste é negativo.",
        )

    c5, c6, c7 = st.columns([1, 1, 2])
    with c5:
        az_t = st.number_input(
            "Azimute do telhado (°)", min_value=0.0, max_value=360.0, value=0.0, step=5.0,
            help="Direção para a qual a água principal do telhado está voltada, medida a partir "
                 "do Norte no sentido horário: 0 = Norte, 90 = Leste, 180 = Sul, 270 = Oeste.",
        )
    with c6:
        incl = st.number_input(
            "Inclinação do telhado (°)", min_value=0.0, max_value=60.0, value=20.0, step=1.0,
            help="Ângulo do telhado com a horizontal (0° = telhado plano).",
        )
    with c7:
        st.caption(
            "O fuso horário é identificado automaticamente pelas coordenadas. "
            "O telhado é usado apenas na visualização da casa (seção 4)."
        )
    calcular = st.form_submit_button("Calcular", type="primary")


def validar(data, hora, lat, lon, az_t, incl):
    erros = []
    if data is None or not isinstance(data, date):
        erros.append("Informe uma data válida.")
    if hora is None or not isinstance(hora, time):
        erros.append("Informe um horário válido.")
    if lat is None or not (-90 <= lat <= 90):
        erros.append("A latitude deve estar entre −90° e +90°.")
    if lon is None or not (-180 <= lon <= 180):
        erros.append("A longitude deve estar entre −180° e +180°.")
    if az_t is None or not (0 <= az_t <= 360):
        erros.append("O azimute do telhado deve estar entre 0° e 360°.")
    if incl is None or not (0 <= incl <= 60):
        erros.append("A inclinação do telhado deve estar entre 0° e 60°.")
    return erros


def executar(data, hora, lat, lon, az_t, incl):
    erros = validar(data, hora, lat, lon, az_t, incl)
    if erros:
        for e in erros:
            st.error(e)
        st.session_state.pop("res", None)
        return
    try:
        fuso = solar.identificar_fuso(lat, lon, data, hora)
        st.session_state["res"] = solar.calcular(data, hora, lat, lon, fuso)
        st.session_state["roof"] = (az_t % 360.0, incl)
    except Exception as erro:  # noqa: BLE001
        st.session_state.pop("res", None)
        st.error(f"Erro no cálculo: {erro}")


if calcular:
    executar(data, hora, lat, lon, az_t, incl)
elif not st.session_state.get("iniciado"):
    st.session_state["iniciado"] = True  # primeira abertura: calcula com os valores iniciais
    executar(data, hora, lat, lon, az_t, incl)

res = st.session_state.get("res")

if not res:
    st.info("Preencha os dados e clique em **Calcular**.")
    st.stop()

az_roof, incl_roof = st.session_state["roof"]
ad = solar.calculos_adicionais(res, az_roof, incl_roof)
traj = solar.trajetoria_do_dia(res)

# --------------------------------------------------------------------------
# 2. Painel principal de irradiância
# --------------------------------------------------------------------------
secao(2, "Irradiância", "Energia incidente por unidade de área, em W/m²")

for aviso in res.avisos:
    st.warning(aviso)

st.markdown(
    '<div class="cards">'
    + cartao("Extraterrestre normal aos raios (Gon)", Tm(res.gon, 1),
             "No topo da atmosfera, perpendicular aos raios solares", "#F5B700")
    + cartao("Extraterrestre horizontal (G0h)", Tm(res.g0h, 1),
             "No topo da atmosfera, sobre superfície horizontal", "#F97316")
    + cartao("Estimada no solo (GHI)", Tm(res.ghi, 1),
             "Modelo de Haurwitz · céu limpo · superfície horizontal", "#0EA5E9")
    + "</div>",
    unsafe_allow_html=True,
)
st.caption(
    f"{res.data:%d/%m/%Y} · {res.hora:%H:%M} · φ = {T(res.lat, 4)}°, λ = {T(res.lon, 4)}° · "
    f"{res.fuso.nome} (UTC{res.fuso.deslocamento:+g}). "
    "A irradiância no solo é uma **estimativa para céu limpo**, não uma medição real."
)

# --------------------------------------------------------------------------
# 3. Trajetória aparente do Sol
# --------------------------------------------------------------------------
secao(3, "Trajetória aparente do Sol", "Calculada para a data e a localização informadas")

m1, m2, m3, m4 = st.columns(4)
if ad.t_nascer is not None:
    dur_min = round(2 * ad.h_nascer / 15.0 * 60)
    m1.metric("Nascer do Sol", solar.hm(ad.t_nascer))
    m3.metric("Pôr do Sol", solar.hm(ad.t_por))
    m4.metric("Duração do dia", f"{dur_min // 60} h {dur_min % 60:02d} min")
else:
    texto = "Sol não nasce" if ad.tipo_dia == "noite_continua" else "Sol não se põe"
    m1.metric("Nascer do Sol", "—", texto, delta_color="off")
    m3.metric("Pôr do Sol", "—")
    m4.metric("Duração do dia", "0 h" if ad.tipo_dia == "noite_continua" else "24 h")
m2.metric("Meio-dia solar", solar.hm(ad.t_meio_dia))
st.caption("Horários no relógio local, calculados a partir de h = 0 e do ângulo horário do pôr do Sol "
           "(detalhes em *Desenvolvimento matemático*).")

aba_alt, aba_irr = st.tabs(["Altura do Sol ao longo do dia", "Irradiância ao longo do dia"])
with aba_alt:
    mostrar(graficos.grafico_trajetoria(res, ad, traj))
with aba_irr:
    mostrar(graficos.grafico_irradiancia_dia(res, traj))

# --------------------------------------------------------------------------
# 4. Casa, telhado e rosa dos ventos
# --------------------------------------------------------------------------
secao(4, "Casa, telhado e rosa dos ventos",
      "Incidência real sobre o telhado, considerando orientação e inclinação")

chave = f"hv_{res.data.isoformat()}_{res.hora.isoformat()}_{res.lat}_{res.lon}"
s1, s2 = st.columns([3, 1])
with s1:
    hv = st.slider(
        "Horário da visualização (mova para ver o Sol se deslocar)",
        min_value=time(0, 0), max_value=time(23, 59),
        value=time(res.hora.hour, res.hora.minute),
        step=timedelta(minutes=1), format="HH:mm", key=chave,
    )
with s2:
    vista = st.slider("Girar a vista (°)", -180, 180, -60, step=5)

rv = solar.calcular(res.data, hv, res.lat, res.lon, res.fuso)  # mesmas equações, outro horário
adv = solar.calculos_adicionais(rv, az_roof, incl_roof)

col_casa, col_rosa = st.columns([6, 5])
with col_casa:
    st.markdown("#### Casa e telhado")
    mostrar(graficos.grafico_casa(rv, adv, vista))
with col_rosa:
    st.markdown("#### Rosa dos ventos e orientação solar")
    mostrar(graficos.grafico_rosa(rv, adv, traj))

st.markdown(f"##### Incidência sobre o telhado · {hv:%H:%M}")
linhas_roof = [
    ("Água principal", adv.az_telhado, adv.cos_inc, adv.theta_inc, adv.g0_telhado, adv.ghi_telhado),
    ("Água oposta", (adv.az_telhado + 180) % 360, adv.cos_inc_op, adv.theta_inc_op, adv.g0_op, adv.ghi_op),
]
tab = ("| Superfície | Azimute | cos θi | Ângulo de incidência θi | G0,t (topo da atm.) | "
       "Estimativa no solo |\n|---|---|---|---|---|---|\n")
for nome, g, c, th, g0, gs in linhas_roof:
    tab += (f"| {nome} (β = {T(adv.incl, 0)}°) | {T(g, 0)}° | {T(c, 3)} | {T(th, 1)}° | "
            f"{T(g0, 1)} W/m² | {T(gs, 1)} W/m² |\n")
tab += (f"| **Plano horizontal (referência)** | — | {T(rv.cosz, 3) if rv.acima_horizonte else '0,000'} | "
        f"{T(rv.theta, 1)}° | {T(rv.g0h, 1)} W/m² | {T(rv.ghi, 1)} W/m² |")
st.markdown(tab)
st.caption(
    "A incidência no telhado **não é igual à horizontal**: depende do ângulo entre os raios solares e a "
    "normal de cada água (cos θi). A estimativa no solo considera só a componente direta "
    "(GHI/cos θz × cos θi); não inclui radiação difusa, refletida nem sombreamento."
)

# --------------------------------------------------------------------------
# 5. Desenvolvimento matemático
# --------------------------------------------------------------------------
secao(5, "Desenvolvimento matemático", "Parâmetros, fórmulas, substituições e resultados")

with st.expander("Desenvolvimento matemático", expanded=False):
    aba_par, aba_etapas, aba_add = st.tabs(
        ["Parâmetros calculados", "Passo a passo (etapas 1 a 10)", "Cálculos adicionais"]
    )

    with aba_par:
        linhas = [
            ("1", "Dados de entrada",
             f"{res.data:%d/%m/%Y} (n = {res.n}), {res.hora:%H:%M}, "
             f"φ = {T(res.lat, 5)}°, λ = {T(res.lon, 5)}°"),
            ("2", "Fuso horário identificado", f"{res.fuso.nome} (UTC{res.fuso.deslocamento:+g})"),
            ("3", "Meridiano central do fuso", f"{T(res.fuso.meridiano, 2)}°"),
            ("4", "Declinação solar (δ)", f"{T(res.delta, 4)}°"),
            ("5", "Correção da longitude (CL)", f"{T(res.cl, 4)} min"),
            ("6", "Equação do tempo (E)", f"{T(res.E, 4)} min"),
            ("7", "Hora solar verdadeira (T_sol)", f"{solar.hms(res.t_sol)} ({T(res.t_sol, 4)} h)"),
            ("8", "Ângulo horário (h)", f"{T(res.h, 4)}°"),
            ("9", "Altura solar (α)", f"{T(res.alpha, 4)}°"),
            ("10", "Ângulo zenital (θz)", f"{T(res.theta, 4)}°"),
            ("11", "Irradiância extraterrestre normal (Gon)", f"{T(res.gon, 2)} W/m²"),
            ("12", "Irradiância extraterrestre horizontal (G0h)", f"{T(res.g0h, 2)} W/m²"),
            ("13", "Irradiância estimada no solo (GHI, céu limpo)", f"{T(res.ghi, 2)} W/m²"),
            ("+", "Azimute solar (cálculo adicional)", f"{T(ad.azimute, 2)}° ({ad.rumo})"),
        ]
        tabela = "| # | Grandeza | Valor |\n|---|---|---|\n"
        tabela += "\n".join(f"| {a} | {b} | {c} |" for a, b, c in linhas)
        st.markdown(tabela)

    with aba_etapas:
        for etapa in res.etapas:
            st.markdown(f"#### {etapa.titulo}")
            st.markdown("**Fórmula**")
            st.latex(etapa.formula)
            st.markdown("**Substituição**")
            st.latex(etapa.substituicao)
            st.markdown(f"**Resultado:** {etapa.resultado}")
            st.divider()

    with aba_add:
        st.caption(
            "Cálculos implementados separadamente das 10 etapas originais; eles apenas reutilizam "
            "os resultados delas (δ, CL, E, h, α, θz, Gon e GHI) e não alteram nenhum valor."
        )
        for etapa in ad.etapas:
            st.markdown(f"#### {etapa.titulo}")
            st.markdown("**Fórmula**")
            st.latex(etapa.formula)
            st.markdown("**Substituição**")
            st.latex(etapa.substituicao)
            st.markdown(f"**Resultado:** {etapa.resultado}")
            st.divider()
        st.markdown(
            "**Observações:** o azimute é medido a partir do Norte (0°), no sentido horário "
            "(90° = Leste, 180° = Sul, 270° = Oeste). O ângulo horário do pôr do Sol é "
            "h_s = arccos(−tan φ · tan δ); a hora do relógio é obtida invertendo a Etapa 4."
        )

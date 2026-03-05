import streamlit as st
import gspread
import json
from google.oauth2.service_account import Credentials
import os

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _get_secret(key: str, default: str | None = None) -> str:
    """Lê variável de st.secrets (Streamlit Cloud / .streamlit/secrets.toml)
    com fallback para os.environ. Compatível com execução local e em nuvem."""
    if key in st.secrets:
        return st.secrets[key]
    if default is not None:
        return os.environ.get(key, default)
    return os.environ[key]


@st.cache_resource
def _autenticar_sheets():
    # Prioridade 1: tabela TOML [gcp_service_account] — formato recomendado pelo Streamlit
    if "gcp_service_account" in st.secrets:
        info = dict(st.secrets["gcp_service_account"])
    else:
        # Prioridade 2: variável GOOGLE_CREDENTIALS_JSON como string JSON ou dict
        creds_raw = _get_secret("GOOGLE_CREDENTIALS_JSON")
        info = json.loads(creds_raw) if isinstance(creds_raw, str) else dict(creds_raw)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)


@st.cache_data(ttl=3600)
def _carregar_estatisticas() -> dict | None:
    """Lê planilha de dados e retorna estatísticas agregadas (sem repetição por proposição)."""
    try:
        planilha_id = _get_secret("PLANILHA_DADOS_ID", "")
        if not planilha_id:
            return None
        aba_dados = _get_secret("ABA_DADOS", "dados")
        cliente = _autenticar_sheets()
        aba = cliente.open_by_key(planilha_id).worksheet(aba_dados)
        rows = aba.get_all_values()
    except Exception:
        return None

    if len(rows) < 2:
        return None

    header = rows[0]
    try:
        idx_casa = header.index("casa")
        idx_id   = header.index("id")
        idx_data = header.index("data_consulta")
        idx_kw   = header.index("keywords_encontradas")
    except ValueError:
        return None

    vistas = set()
    camara = 0
    senado = 0
    datas  = []
    keyword_counts: dict[str, int] = {}
    for row in rows[1:]:
        if len(row) <= max(idx_casa, idx_id, idx_data, idx_kw):
            continue
        casa = row[idx_casa].strip()
        pid  = row[idx_id].strip()
        chave = (casa, pid)
        if chave not in vistas and pid:
            vistas.add(chave)
            if "câmara" in casa.lower() or "camara" in casa.lower():
                camara += 1
            elif "senado" in casa.lower():
                senado += 1
            for kw in row[idx_kw].split(", "):
                kw = kw.strip()
                if kw:
                    keyword_counts[kw] = keyword_counts.get(kw, 0) + 1
        data_val = row[idx_data].strip()
        if data_val:
            datas.append(data_val)

    return {
        "total":         len(vistas),
        "camara":        camara,
        "senado":        senado,
        "data_inicio":   min(datas) if datas else None,
        "data_fim":      max(datas) if datas else None,
        "keyword_counts": keyword_counts,
    }


def remover_inscrito(email: str) -> tuple[bool, str]:
    try:
        cliente = _autenticar_sheets()
        planilha = cliente.open_by_key(_get_secret("PLANILHA_EMAILS_ID"))
        aba = planilha.worksheet(_get_secret("ABA_EMAILS", "emails"))
        valores = aba.col_values(1)
        email_normalizado = email.strip().lower()
        linha_encontrada = None
        for i, valor in enumerate(valores, start=1):
            if valor.strip().lower() == email_normalizado:
                linha_encontrada = i
                break
        if linha_encontrada is None:
            return False, "Email não encontrado na lista de inscritos."
        aba.delete_rows(linha_encontrada)
        return True, "Inscrição cancelada com sucesso."
    except Exception as e:
        return False, f"Erro ao cancelar inscrição ({type(e).__name__}): {e}"


def adicionar_inscrito(email: str) -> tuple[bool, str]:
    try:
        cliente = _autenticar_sheets()
        planilha = cliente.open_by_key(_get_secret("PLANILHA_EMAILS_ID"))
        aba = planilha.worksheet(_get_secret("ABA_EMAILS", "emails"))

        # Verificar se já existe
        emails_existentes = [v.strip().lower() for v in aba.col_values(1)]
        if email.lower() in emails_existentes:
            return False, "Email já cadastrado."

        aba.append_row([email], value_input_option="RAW")
        return True, "Inscrição realizada com sucesso!"
    except Exception as e:
        return False, f"Erro ao inscrever ({type(e).__name__}): {e}"


# --- UI ---
st.set_page_config(page_title="Monitor Legislativo", page_icon="🏛️", layout="centered")

st.markdown("""
<style>
/* ── Base ─────────────────────────────────────────── */
[data-testid="stAppViewContainer"] { background-color: #f5f7fa; }
[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 1.5rem; padding-bottom: 2.5rem; max-width: 820px; }

/* ── Hero ─────────────────────────────────────────── */
.hero {
    background: linear-gradient(135deg, #0c2340 0%, #1a4068 55%, #1d6a3c 100%);
    padding: 3rem 2.5rem 2.5rem;
    border-radius: 16px;
    text-align: center;
    margin-bottom: 1.75rem;
    color: white;
}
.hero-badge {
    display: inline-block;
    background: rgba(255,255,255,0.15);
    border: 1px solid rgba(255,255,255,0.3);
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.6px;
    text-transform: uppercase;
    margin-bottom: 1rem;
}
.hero h1 {
    font-size: 2.3rem;
    font-weight: 800;
    margin: 0 0 0.75rem;
    letter-spacing: -0.5px;
    line-height: 1.2;
}
.hero p {
    font-size: 1.05rem;
    opacity: 0.9;
    max-width: 560px;
    margin: 0 auto;
    line-height: 1.65;
}

/* ── Form ─────────────────────────────────────────── */
.form-label {
    font-size: 0.95rem;
    font-weight: 600;
    color: #1a3a5c;
    margin-bottom: 0.3rem;
}
[data-testid="stForm"] {
    background: white;
    border-radius: 12px;
    padding: 1.5rem 1.75rem !important;
    box-shadow: 0 2px 12px rgba(0,0,0,0.07);
    border: 1px solid #e8ecf0;
}

/* ── Section headers ──────────────────────────────── */
.section-header {
    font-size: 1.2rem;
    font-weight: 700;
    color: #0c2340;
    margin: 1.75rem 0 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 2px solid #e4e9f0;
}

/* ── Stat cards ───────────────────────────────────── */
.stats-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
    margin-bottom: 0.75rem;
}
.stat-card {
    background: white;
    border-radius: 12px;
    padding: 1.25rem 1rem;
    text-align: center;
    box-shadow: 0 2px 10px rgba(0,0,0,0.07);
    border-top: 4px solid #1d6a3c;
}
.stat-card.camara { border-top-color: #1a4068; }
.stat-card.senado  { border-top-color: #0c2340; }
.stat-number {
    font-size: 2.1rem;
    font-weight: 800;
    color: #0c2340;
    line-height: 1.1;
    margin-bottom: 0.35rem;
}
.stat-label {
    font-size: 0.78rem;
    color: #6c7a8a;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.stat-period {
    font-size: 0.82rem;
    color: #8a96a3;
    text-align: center;
    margin-bottom: 1rem;
}

/* ── Keyword chips ────────────────────────────────── */
.kw-label {
    font-size: 0.88rem;
    font-weight: 600;
    color: #2c3e50;
    margin: 0.75rem 0 0.5rem;
}
.kw-chips { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 1.25rem; }
.kw-chip {
    background: #eaf4ee;
    color: #1a5c2e;
    border: 1px solid #c3dfc9;
    border-radius: 20px;
    padding: 5px 12px;
    font-size: 0.82rem;
    font-weight: 500;
    display: inline-flex;
    align-items: center;
    gap: 7px;
    white-space: nowrap;
}
.kw-count {
    background: #1d6a3c;
    color: white;
    border-radius: 10px;
    padding: 1px 7px;
    font-size: 0.72rem;
    font-weight: 700;
}

/* ── Step cards ───────────────────────────────────── */
.step-intro { color: #5d6d7e; font-size: 0.93rem; margin-bottom: 0.85rem; line-height: 1.6; }
.step-card {
    display: flex;
    gap: 1rem;
    align-items: flex-start;
    margin-bottom: 0.65rem;
    padding: 1rem 1.25rem;
    background: white;
    border-radius: 10px;
    box-shadow: 0 1px 6px rgba(0,0,0,0.06);
    border-left: 3px solid #e4e9f0;
    transition: border-left-color 0.2s;
}
.step-card:hover { border-left-color: #1d6a3c; }
.step-num {
    background: #0c2340;
    color: white;
    min-width: 28px;
    height: 28px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 0.82rem;
    flex-shrink: 0;
    margin-top: 2px;
}
.step-text { font-size: 0.92rem; color: #2c3e50; line-height: 1.65; }
.step-text a { color: #1d6a3c; }
.step-text strong { color: #1a3a5c; }

/* ── Expanders ────────────────────────────────────── */
[data-testid="stExpander"] {
    background: white;
    border-radius: 10px !important;
    border: 1px solid #e4e9f0 !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
    margin-bottom: 0.5rem;
}

/* ── Footer ───────────────────────────────────────── */
.footer {
    text-align: center;
    font-size: 0.84rem;
    color: #9aa5b1;
    padding: 1.5rem 0 0;
    border-top: 1px solid #e4e9f0;
    margin-top: 2rem;
}
.footer a { color: #1a4068; text-decoration: none; font-weight: 500; }
.footer a:hover { text-decoration: underline; }
</style>
""", unsafe_allow_html=True)

# --- Cancelamento de inscrição via URL params ---
_params = st.query_params
if _params.get("action") == "unsubscribe":
    # Streamlit já decodifica URL automaticamente (ex: %40 → @)
    email_param = _params.get("email", "").strip()
    st.markdown("""
<div style="background:#fff3f3;border:1px solid #e74c3c;border-radius:8px;padding:20px 24px;margin-bottom:24px;">
    <h3 style="color:#c0392b;margin-top:0;">Cancelar inscrição</h3>
""", unsafe_allow_html=True)
    if email_param and "@" in email_param:
        # Processa apenas uma vez por sessão (evita reprocessamento em reruns do Streamlit)
        _session_key = f"unsub_{email_param}"
        if _session_key not in st.session_state:
            _ok, _msg = remover_inscrito(email_param)
            st.session_state[_session_key] = (_ok, _msg)
        _ok, _msg = st.session_state[_session_key]
        if _ok:
            st.success(f"Inscrição cancelada para **{email_param}**. Você não receberá mais o relatório diário.")
        else:
            if "não encontrado" in _msg:
                st.info(f"O email **{email_param}** não está na lista de inscritos.")
            else:
                st.error(_msg)
    else:
        st.markdown(
            '<p>Informe o email cadastrado para cancelar a inscrição:</p>',
            unsafe_allow_html=True,
        )
        with st.form("form_cancelar"):
            email_cancelar = st.text_input("Email", placeholder="voce@exemplo.com", label_visibility="collapsed")
            submitted_cancelar = st.form_submit_button("Cancelar inscrição")
        if submitted_cancelar:
            if email_cancelar and "@" in email_cancelar:
                ok, msg = remover_inscrito(email_cancelar.strip())
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)
            else:
                st.error("Informe um email válido.")
    st.markdown("</div>", unsafe_allow_html=True)
    st.divider()

# Hero
st.markdown("""
<div class="hero">
    <div class="hero-badge">🏛️ Monitoramento Legislativo</div>
    <h1>Jornalismo no Congresso</h1>
    <p>Receba diariamente proposições da <strong>Câmara dos Deputados</strong> e do
    <strong>Senado Federal</strong> que mencionam temas relacionados ao jornalismo.</p>
</div>
""", unsafe_allow_html=True)

# Subscription form
st.markdown('<p class="form-label">Inscreva-se para receber o relatório diário no seu email</p>', unsafe_allow_html=True)
with st.form("form_inscricao"):
    email = st.text_input("Email", placeholder="voce@exemplo.com", label_visibility="collapsed")
    submitted = st.form_submit_button("✉️  Inscrever-se", use_container_width=True)

if submitted:
    if email and "@" in email:
        ok, msg = adicionar_inscrito(email.strip())
        if ok:
            st.success(msg)
        else:
            st.warning(msg)
    else:
        st.error("Informe um email válido.")

# Statistics
stats = _carregar_estatisticas()
if stats and stats["total"] > 0:
    st.markdown('<div class="section-header">Dados coletados — coleta iniciada em fevereiro de 2026</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-number">{stats['total']}</div>
            <div class="stat-label">Proposições únicas</div>
        </div>
        <div class="stat-card camara">
            <div class="stat-number">{stats['camara']}</div>
            <div class="stat-label">Câmara dos Deputados</div>
        </div>
        <div class="stat-card senado">
            <div class="stat-number">{stats['senado']}</div>
            <div class="stat-label">Senado Federal</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    if stats["data_inicio"] and stats["data_fim"]:
        st.markdown(f'<p class="stat-period">Período: {stats["data_inicio"]} a {stats["data_fim"]}</p>', unsafe_allow_html=True)
    kw_counts = stats.get("keyword_counts", {})
    if kw_counts:
        sorted_kw = sorted(kw_counts.items(), key=lambda x: x[1], reverse=True)
        chips = "".join(
            f'<span class="kw-chip">{kw.title()} <span class="kw-count">{n}</span></span>'
            for kw, n in sorted_kw
        )
        st.markdown(f"""
        <div class="kw-label">Temas encontrados nas proposições:</div>
        <div class="kw-chips">{chips}</div>
        """, unsafe_allow_html=True)

# Como funciona
st.markdown('<div class="section-header">Como funciona</div>', unsafe_allow_html=True)
st.markdown("""
<p class="step-intro">O monitor roda automaticamente <strong>todo dia às 07h (horário de Brasília)</strong> via GitHub Actions e:</p>
<div class="step-card">
    <div class="step-num">1</div>
    <div class="step-text">Coleta todas as proposições recentes da <strong>API da Câmara dos Deputados (v2 REST)</strong> e da <strong>API de Dados Abertos do Senado Federal</strong> — são coletadas as movimentações diárias, por isso uma mesma proposição pode aparecer mais de uma vez</div>
</div>
<div class="step-card">
    <div class="step-num">2</div>
    <div class="step-text">Filtra as que mencionam algum dos temas monitorados (veja abaixo)</div>
</div>
<div class="step-card">
    <div class="step-num">3</div>
    <div class="step-text">Compara com os dados já gravados na planilha — apenas movimentações com status, órgão ou data diferentes do que já foi registrado são consideradas <strong>novidades</strong></div>
</div>
<div class="step-card">
    <div class="step-num">4</div>
    <div class="step-text">Se houver novidades: grava na planilha e envia um <strong>relatório HTML por email</strong> para todos os inscritos. Se não houver novidades, nenhuma linha é adicionada e nenhum email é enviado</div>
</div>
<div class="step-card">
    <div class="step-num">5</div>
    <div class="step-text">Veja os dados na <a href="https://docs.google.com/spreadsheets/d/1GJ03OC8B7G3DBDCfvaZHx5RQDUAauuxDmhaxKy5Yq04/edit?usp=sharing" target="_blank">planilha do Google Sheets</a></div>
</div>
<p style="font-size:0.88rem;color:#7f8c8d;margin-top:0.75rem">Ao se inscrever acima, você passará a receber o relatório diário automaticamente.</p>
""", unsafe_allow_html=True)

with st.expander("Temas monitorados (16 palavras-chave)"):
    st.markdown(
        """
- Jornalismo / Jornalista / Jornalistas
- Comunicadores
- Imprensa
- Mídia
- Comunicação social
- Liberdade de imprensa
- Verificadores de fatos
- Checagem de fatos
- Fake news
- Desinformação
- Transparência na internet
- Liberdade de expressão e informações de interesse coletivo
- Transparência dos dados
- ONGs
"""
    )

with st.expander("Fontes de dados"):
    st.markdown(
        """
- **Câmara dos Deputados:** [dadosabertos.camara.leg.br/api/v2](https://dadosabertos.camara.leg.br/swagger/api.html)
- **Senado Federal:** [legis.senado.leg.br/dadosabertos](https://legis.senado.leg.br/dadosabertos/docs/)

Os dados são públicos e disponibilizados pelas próprias casas legislativas.
"""
    )

st.markdown("""
<div class="footer">
    Projeto independente de <strong>Reinaldo Chaves</strong> ·
    <a href="https://github.com/reichaves/congresso_monitor_jornalismo" target="_blank">Repositório e documentação completa</a>
</div>
""", unsafe_allow_html=True)

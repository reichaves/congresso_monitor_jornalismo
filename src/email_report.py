"""
Módulo de envio de relatório por email via Gmail SMTP.
Autor: Reinaldo Chaves

Usa smtplib + App Password do Gmail.
Não requer bibliotecas externas — usa apenas a stdlib do Python.
"""

import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import quote

from . import config

logger = logging.getLogger(__name__)


_STREAMLIT_URL = "https://congreapp-monitor-jornalismo.streamlit.app/"


def _gerar_html_relatorio(
    resultados_camara: list[dict],
    resultados_senado: list[dict],
    data_inicio: str,
    data_fim: str,
    stats_planilha: dict | None = None,
    email_destinatario: str = "",
) -> str:
    """Gera o corpo HTML do relatório por email."""
    total = len(resultados_camara) + len(resultados_senado)
    agora = datetime.now().strftime("%d/%m/%Y às %H:%M")

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Monitor Legislativo</title>
<style>
    body {{
        font-family: Arial, Helvetica, sans-serif;
        color: #333;
        max-width: 800px;
        margin: 0 auto;
        padding: 20px;
        background-color: #f5f5f5;
    }}
    .container {{
        background: #ffffff;
        border-radius: 8px;
        padding: 24px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }}
    h1 {{
        color: #1a5276;
        border-bottom: 3px solid #1a5276;
        padding-bottom: 12px;
        font-size: 22px;
        margin-top: 0;
    }}
    h2 {{
        color: #2c3e50;
        font-size: 18px;
        margin-top: 30px;
        padding-bottom: 6px;
        border-bottom: 1px solid #eee;
    }}
    .resumo {{
        background: #eaf2f8;
        border-left: 4px solid #2980b9;
        padding: 14px 18px;
        margin: 18px 0;
        border-radius: 0 6px 6px 0;
    }}
    .resumo strong {{
        color: #1a5276;
    }}
    .proposicao {{
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 16px;
        margin: 14px 0;
        background: #fafafa;
    }}
    .proposicao h3 {{
        margin-top: 0;
        margin-bottom: 8px;
        color: #1a5276;
        font-size: 16px;
    }}
    .proposicao .ementa {{
        color: #444;
        line-height: 1.5;
        margin-bottom: 10px;
    }}
    .meta {{
        color: #666;
        font-size: 13px;
        line-height: 1.7;
    }}
    .meta strong {{
        color: #555;
    }}
    .tag {{
        display: inline-block;
        background: #d5e8d4;
        color: #2d6a2e;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: bold;
        margin: 2px 3px 2px 0;
    }}
    .tag-senado {{
        background: #dae8fc;
        color: #1a5276;
    }}
    .tag-tema {{
        background: #fff2cc;
        color: #7f6000;
    }}
    .links {{
        margin-top: 10px;
        padding-top: 8px;
        border-top: 1px solid #eee;
    }}
    .links a {{
        color: #2980b9;
        text-decoration: none;
        font-size: 13px;
        margin-right: 16px;
    }}
    .links a:hover {{
        text-decoration: underline;
    }}
    .vazio {{
        text-align: center;
        padding: 30px;
        color: #888;
        font-style: italic;
    }}
    .rodape {{
        margin-top: 30px;
        padding-top: 16px;
        border-top: 2px solid #eee;
        font-size: 12px;
        color: #999;
        line-height: 1.6;
    }}
    .keywords-lista {{
        background: #f0f0f0;
        padding: 8px 12px;
        border-radius: 4px;
        font-size: 11px;
        color: #666;
        word-break: break-word;
    }}
    .stats-planilha {{
        background: #f0f4f0;
        border-left: 4px solid #1d6a3c;
        padding: 14px 18px;
        margin: 24px 0 8px;
        border-radius: 0 6px 6px 0;
    }}
    .stats-planilha strong {{
        color: #1a4a2a;
    }}
    .stats-planilha .stat-linha {{
        font-size: 15px;
        margin: 6px 0;
        color: #2c3e50;
    }}
    .stats-planilha .kw-lista {{
        margin: 8px 0 10px;
        padding-left: 0;
        list-style: none;
        font-size: 12px;
        color: #555;
        columns: 2;
        column-gap: 24px;
    }}
    .stats-planilha .kw-lista li::before {{
        content: "▸ ";
        color: #1d6a3c;
        font-weight: bold;
    }}
    .link-planilha {{
        display: inline-block;
        background: #1d6a3c;
        color: #ffffff !important;
        padding: 8px 18px;
        border-radius: 6px;
        text-decoration: none;
        font-size: 13px;
        font-weight: bold;
        margin-top: 6px;
    }}
</style>
</head>
<body>
<div class="container">
    <h1>&#128203; Monitor Legislativo &mdash; Jornalismo no Congresso</h1>

    <div class="resumo">
        <strong>Per&iacute;odo:</strong> {data_inicio} a {data_fim}<br>
        <strong>Total de proposi&ccedil;&otilde;es encontradas:</strong> {total}
        (C&acirc;mara: {len(resultados_camara)} | Senado: {len(resultados_senado)})<br>
        <strong>Relat&oacute;rio gerado em:</strong> {agora}
    </div>
"""

    if total == 0:
        html += """
    <div class="vazio">
        Nenhuma proposi&ccedil;&atilde;o com as palavras-chave monitoradas foi
        encontrada no per&iacute;odo consultado.
    </div>
"""
    else:
        # --- Câmara ---
        if resultados_camara:
            html += f'    <h2>&#127963;&#65039; C&acirc;mara dos Deputados ({len(resultados_camara)})</h2>\n'
            for r in resultados_camara:
                html += _formatar_proposicao(r, "camara")

        # --- Senado ---
        if resultados_senado:
            html += f'    <h2>&#127963;&#65039; Senado Federal ({len(resultados_senado)})</h2>\n'
            for r in resultados_senado:
                html += _formatar_proposicao(r, "senado")

    # Estatísticas acumuladas da planilha
    if stats_planilha and stats_planilha.get("total", 0) > 0:
        kw_counts = stats_planilha.get("keyword_counts", {})
        kw_items = sorted(kw_counts.items(), key=lambda x: x[1], reverse=True)
        kw_html = "\n".join(
            f"            <li>{kw.title()}: <strong>{n}</strong></li>"
            for kw, n in kw_items
        )
        html += f"""
    <div class="stats-planilha">
        <strong>&#128202; Dados acumulados na planilha</strong><br>
        <div class="stat-linha">
            <strong>Total de proposi&ccedil;&otilde;es &uacute;nicas:</strong>
            {stats_planilha['total']}
            (C&acirc;mara: {stats_planilha['camara']} | Senado: {stats_planilha['senado']})
        </div>
        <div class="stat-linha"><strong>Temas encontrados (proposi&ccedil;&otilde;es &uacute;nicas):</strong></div>
        <ul class="kw-lista">
{kw_html}
        </ul>
        <a class="link-planilha"
           href="https://docs.google.com/spreadsheets/d/1GJ03OC8B7G3DBDCfvaZHx5RQDUAauuxDmhaxKy5Yq04/edit?usp=sharing">
            &#128203; Acessar planilha completa
        </a>
    </div>
"""

    # Palavras-chave monitoradas + links de rodapé
    keywords_str = ", ".join(config.PALAVRAS_CHAVE)

    cancelar_url = ""
    if email_destinatario:
        cancelar_url = (
            f"{_STREAMLIT_URL}?action=unsubscribe&email={quote(email_destinatario)}"
        )

    html += f"""
    <div class="rodape">
        <strong>Palavras-chave monitoradas:</strong>
        <div class="keywords-lista">{keywords_str}</div>
        <br>
        Projeto independente de Reinaldo Chaves.<br>
        Dados: API da C&acirc;mara dos Deputados (v2) e Dados Abertos do Senado Federal.<br><br>
        <a href="{_STREAMLIT_URL}" style="color:#2980b9;">&#127968; Acessar o Monitor Legislativo</a>
        &nbsp;&nbsp;|&nbsp;&nbsp;
        <a href="https://docs.google.com/spreadsheets/d/1GJ03OC8B7G3DBDCfvaZHx5RQDUAauuxDmhaxKy5Yq04/edit?usp=sharing" style="color:#2980b9;">&#128203; Planilha de dados</a>
        &nbsp;&nbsp;|&nbsp;&nbsp;
        <a href="https://github.com/reichaves/congresso_monitor_jornalismo" style="color:#2980b9;">&#128279; Veja o c&oacute;digo do projeto</a>
"""

    if cancelar_url:
        html += f"""        &nbsp;&nbsp;|&nbsp;&nbsp;
        <a href="{cancelar_url}" style="color:#c0392b;font-size:11px;">Cancelar inscri&ccedil;&atilde;o</a>
"""

    html += """    </div>
</div>
</body>
</html>"""

    return html


def _formatar_proposicao(registro: dict, casa: str) -> str:
    """Formata uma proposição individual para o HTML."""
    sigla = registro.get("siglaTipo", "")
    numero = registro.get("numero", "")
    ano = registro.get("ano", "")
    titulo = f"{sigla} {numero}/{ano}".strip()
    if titulo == "/":
        titulo = f"ID {registro.get('id', '?')}"

    ementa = registro.get("ementa", "Sem ementa dispon&iacute;vel")
    autores = registro.get("autores", "N&atilde;o informado")
    status = registro.get("statusSituacao", "")
    orgao = registro.get("statusOrgao", "")
    data_apres = registro.get("dataApresentacao", "")
    url_pagina = registro.get("pagina_proposicao", "")
    url_texto = registro.get("urlInteiroTeor", "")
    keywords = registro.get("keywords_encontradas", "")
    tema = registro.get("tema_monitoramento", "")
    indexacao = registro.get("indexacao_oficial", "")

    tag_class = "tag-senado" if casa == "senado" else "tag"

    html = f"""
    <div class="proposicao">
        <h3>{titulo}</h3>
        <p class="ementa">{ementa}</p>
        <div class="meta">
            <strong>Autor(es):</strong> {autores}<br>
"""

    if data_apres:
        html += f"            <strong>Apresenta&ccedil;&atilde;o:</strong> {data_apres}<br>\n"
    if status:
        html += f"            <strong>Situa&ccedil;&atilde;o:</strong> {status}"
        if orgao:
            html += f" ({orgao})"
        html += "<br>\n"
    if indexacao:
        html += f"            <strong>Indexa&ccedil;&atilde;o oficial:</strong> {indexacao}<br>\n"

    html += "        </div>\n"

    # Tags de keywords
    if keywords or tema:
        html += '        <div style="margin-top: 8px;">\n'
        if keywords:
            for kw in keywords.split(", "):
                html += f'            <span class="{tag_class}">{kw}</span>\n'
        if tema:
            html += f'            <span class="tag-tema">Tema: {tema}</span>\n'
        html += "        </div>\n"

    # Links
    if url_pagina or url_texto:
        html += '        <div class="links">\n'
        if url_pagina:
            html += f'            <a href="{url_pagina}">&#128196; Ver proposi&ccedil;&atilde;o</a>\n'
        if url_texto:
            html += f'            <a href="{url_texto}">&#128221; Inteiro teor</a>\n'
        html += "        </div>\n"

    html += "    </div>\n"
    return html


def enviar_relatorio(
    destinatarios: list[str],
    resultados_camara: list[dict],
    resultados_senado: list[dict],
    data_inicio: str,
    data_fim: str,
    stats_planilha: dict | None = None,
) -> bool:
    """Envia relatório HTML por email via Gmail SMTP com App Password.

    Retorna True se o envio foi bem-sucedido.
    """
    if not destinatarios:
        logger.warning("Email — nenhum destinatário. Envio cancelado.")
        return False

    if not config.GMAIL_APP_PASSWORD:
        logger.error(
            "GMAIL_APP_PASSWORD não configurada. "
            "Crie uma App Password em https://myaccount.google.com/apppasswords"
        )
        return False

    if not config.GMAIL_USER:
        logger.error("GMAIL_USER não configurado.")
        return False

    total = len(resultados_camara) + len(resultados_senado)
    data_formatada = datetime.now().strftime("%d/%m/%Y")

    if total > 0:
        subject = (
            f"Monitor Legislativo — {total} proposição(ões) encontrada(s) "
            f"em {data_formatada}"
        )
    else:
        subject = f"Monitor Legislativo — Nenhuma proposição em {data_formatada}"

    texto_simples = (
        f"Monitor Legislativo — {total} proposição(ões) encontrada(s)\n"
        f"Período: {data_inicio} a {data_fim}\n\n"
        "Este email contém um relatório em HTML. "
        "Abra em um cliente de email que suporte HTML para visualizá-lo.\n\n"
        f"Acesse o Monitor Legislativo: {_STREAMLIT_URL}"
    )

    enviados = 0
    try:
        with smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT) as servidor:
            servidor.ehlo()
            servidor.starttls()
            servidor.ehlo()
            servidor.login(config.GMAIL_USER, config.GMAIL_APP_PASSWORD)

            for dest in destinatarios:
                html_body = _gerar_html_relatorio(
                    resultados_camara, resultados_senado, data_inicio, data_fim,
                    stats_planilha=stats_planilha,
                    email_destinatario=dest,
                )
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = config.GMAIL_USER
                msg["To"] = dest
                msg.attach(MIMEText(texto_simples, "plain", "utf-8"))
                msg.attach(MIMEText(html_body, "html", "utf-8"))
                try:
                    servidor.sendmail(config.GMAIL_USER, [dest], msg.as_string())
                    enviados += 1
                except smtplib.SMTPException as exc:
                    logger.error("Erro SMTP ao enviar para %s: %s", dest, exc)

    except smtplib.SMTPAuthenticationError as exc:
        logger.error(
            "Falha de autenticação Gmail. Verifique GMAIL_USER e "
            "GMAIL_APP_PASSWORD. Erro: %s", exc
        )
        return False
    except smtplib.SMTPException as exc:
        logger.error("Erro SMTP ao conectar: %s", exc)
        return False
    except Exception as exc:
        logger.error("Erro inesperado ao enviar email: %s", exc)
        return False

    logger.info(
        "Email — enviado com sucesso para %d/%d destinatário(s) via Gmail SMTP",
        enviados, len(destinatarios),
    )
    return enviados > 0

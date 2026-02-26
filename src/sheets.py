"""
Módulo de integração com Google Sheets.
Autor: Reinaldo Chaves

Funções:
- Ler movimentações já existentes na planilha (para deduplicação)
- Gravar dados coletados na planilha de dados
- Ler lista de emails da planilha de destinatários
"""

import json
import logging

import gspread
from google.oauth2.service_account import Credentials

from . import config

logger = logging.getLogger(__name__)

# Escopos necessários para leitura e escrita no Sheets
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _autenticar() -> gspread.Client:
    """Autentica com credenciais de service account (JSON do GitHub Secret)."""
    if not config.GOOGLE_CREDENTIALS_JSON:
        raise RuntimeError(
            "GOOGLE_CREDENTIALS_JSON não configurado. "
            "Defina o secret no GitHub Actions."
        )

    info = json.loads(config.GOOGLE_CREDENTIALS_JSON)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)


def ler_movimentacoes_existentes() -> set[tuple]:
    """Lê a planilha de dados e retorna o conjunto de chaves de movimentação já registradas.

    Cada chave é uma tupla (casa, id, numero, ano, statusSituacao, statusOrgao, statusData).
    Usada em main.py para filtrar apenas registros realmente novos antes de gravar e emailar.
    Retorna conjunto vazio se a planilha não estiver acessível.
    """
    if not config.PLANILHA_DADOS_ID:
        logger.warning("PLANILHA_DADOS_ID não configurado — pulando leitura de movimentações")
        return set()

    try:
        cliente = _autenticar()
        planilha = cliente.open_by_key(config.PLANILHA_DADOS_ID)
        aba = planilha.worksheet(config.ABA_DADOS)
        rows = aba.get_all_values()
    except Exception as exc:
        logger.error("Erro ao ler movimentações existentes: %s", exc)
        return set()

    if len(rows) < 2:
        return set()

    header = rows[0]
    campos = ["casa", "id", "numero", "ano", "statusSituacao", "statusOrgao", "statusData"]
    try:
        indices = [header.index(c) for c in campos]
    except ValueError as exc:
        logger.error("Coluna ausente na planilha ao ler movimentações: %s", exc)
        return set()

    existentes: set[tuple] = set()
    max_idx = max(indices)
    for row in rows[1:]:
        if len(row) <= max_idx:
            continue
        chave = tuple(row[i].strip() for i in indices)
        existentes.add(chave)

    logger.info("Sheets — %d movimentações existentes lidas para deduplicação", len(existentes))
    return existentes


def ler_estatisticas_planilha() -> dict | None:
    """Lê a planilha de dados e retorna estatísticas acumuladas.

    Retorna dict com:
      - total: proposições únicas (por casa+id)
      - camara: proposições únicas da Câmara
      - senado: proposições únicas do Senado
      - keyword_counts: {keyword: n_proposições_únicas}
    Retorna None se a planilha estiver inacessível ou vazia.
    """
    if not config.PLANILHA_DADOS_ID:
        return None

    try:
        cliente = _autenticar()
        planilha = cliente.open_by_key(config.PLANILHA_DADOS_ID)
        aba = planilha.worksheet(config.ABA_DADOS)
        rows = aba.get_all_values()
    except Exception as exc:
        logger.error("Erro ao ler estatísticas da planilha: %s", exc)
        return None

    if len(rows) < 2:
        return None

    header = rows[0]
    try:
        idx_casa = header.index("casa")
        idx_id   = header.index("id")
        idx_kw   = header.index("keywords_encontradas")
    except ValueError as exc:
        logger.error("Coluna ausente ao ler estatísticas: %s", exc)
        return None

    max_idx = max(idx_casa, idx_id, idx_kw)
    vistas: set[tuple] = set()
    camara = 0
    senado = 0
    keyword_counts: dict[str, int] = {}

    for row in rows[1:]:
        if len(row) <= max_idx:
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

    logger.info("Sheets — estatísticas: %d proposições únicas lidas", len(vistas))
    return {
        "total":          len(vistas),
        "camara":         camara,
        "senado":         senado,
        "keyword_counts": keyword_counts,
    }


def gravar_dados(registros: list[dict]) -> int:
    """Grava registros na planilha de dados.

    Adiciona header se a planilha estiver vazia.
    Retorna o número de linhas inseridas.
    """
    if not registros:
        logger.info("Sheets — nenhum registro para gravar")
        return 0

    if not config.PLANILHA_DADOS_ID:
        logger.warning("PLANILHA_DADOS_ID não configurado — pulando gravação")
        return 0

    try:
        cliente = _autenticar()
        planilha = cliente.open_by_key(config.PLANILHA_DADOS_ID)
        aba = planilha.worksheet(config.ABA_DADOS)
    except Exception as exc:
        logger.error("Erro ao acessar planilha de dados: %s", exc)
        return 0

    # Verificar se precisa adicionar header
    try:
        valores_existentes = aba.get_all_values()
        if not valores_existentes:
            aba.append_row(config.COLUNAS_PLANILHA, value_input_option="RAW")
            logger.info("Sheets — header inserido na planilha")
    except Exception:
        # Planilha vazia — adicionar header
        aba.append_row(config.COLUNAS_PLANILHA, value_input_option="RAW")

    # Converter registros em linhas (seguindo a ordem de COLUNAS_PLANILHA)
    linhas = []
    for reg in registros:
        linha = [str(reg.get(col, "")) for col in config.COLUNAS_PLANILHA]
        linhas.append(linha)

    try:
        aba.append_rows(linhas, value_input_option="RAW")
        logger.info("Sheets — %d linhas inseridas com sucesso", len(linhas))
        return len(linhas)
    except Exception as exc:
        logger.error("Erro ao inserir linhas na planilha: %s", exc)
        return 0


def ler_emails_destinatarios() -> list[str]:
    """Lê lista de emails da planilha de destinatários.

    Espera uma coluna com emails (primeira coluna, a partir da linha 2).
    Ignora linhas vazias e emails inválidos.
    """
    if not config.PLANILHA_EMAILS_ID:
        logger.warning("PLANILHA_EMAILS_ID não configurado — sem destinatários")
        return []

    try:
        cliente = _autenticar()
        planilha = cliente.open_by_key(config.PLANILHA_EMAILS_ID)
        aba = planilha.worksheet(config.ABA_EMAILS)
    except Exception as exc:
        logger.error("Erro ao acessar planilha de emails: %s", exc)
        return []

    try:
        # Pega todos os valores da primeira coluna (A)
        valores = aba.col_values(1)
    except Exception as exc:
        logger.error("Erro ao ler coluna de emails: %s", exc)
        return []

    # Pular header (primeira linha) e filtrar emails válidos
    emails = []
    for valor in valores[1:]:  # skip header
        email = valor.strip()
        if email and "@" in email:
            emails.append(email)

    logger.info("Sheets — %d emails de destinatários lidos", len(emails))
    return emails

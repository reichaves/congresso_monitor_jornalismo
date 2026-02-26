"""
Módulo de coleta da API da Câmara dos Deputados (v2 REST).
Autor: Reinaldo Chaves

Correções aplicadas em relação ao projeto original da Abraji:
- Bug #1: operador lógico `or` corrigido — usa `in` corretamente
- Bug #2: paginação robusta via urllib.parse (não mais posição fixa)
- Bug #3: endpoint SOAP substituído por REST v2 /proposicoes/{id}/autores
- Adicionado: retry com backoff exponencial
- Adicionado: logging estruturado
- Adicionado: coleta de temas oficiais via /proposicoes/{id}/temas
"""

import logging
import re
import time
from datetime import datetime
from urllib.parse import parse_qs, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sessão HTTP com retry automático
# ---------------------------------------------------------------------------
def criar_sessao_http() -> requests.Session:
    """Cria sessão com retry + backoff para status 429/5xx."""
    sessao = requests.Session()
    estrategia = Retry(
        total=config.HTTP_MAX_RETRIES,
        backoff_factor=config.HTTP_BACKOFF_FACTOR,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adaptador = HTTPAdapter(max_retries=estrategia)
    sessao.mount("https://", adaptador)
    sessao.mount("http://", adaptador)
    return sessao


# ---------------------------------------------------------------------------
# Paginação robusta
# ---------------------------------------------------------------------------
def _extrair_total_paginas(link_header: str) -> int:
    """Extrai o total de páginas do header Link usando urllib.parse.

    Corrige o bug original que usava fatiamento fixo (posição 139).
    """
    if not link_header:
        return 1

    for parte in link_header.split(","):
        if 'rel="last"' in parte:
            url_raw = parte.split(";")[0].strip().strip("<>")
            qs = parse_qs(urlparse(url_raw).query)
            paginas = qs.get("pagina", ["1"])
            return int(paginas[0])
    return 1


# ---------------------------------------------------------------------------
# Coleta paginada de proposições
# ---------------------------------------------------------------------------
def coletar_proposicoes(
    sessao: requests.Session,
    data_inicio: str,
    data_fim: str,
) -> list[dict]:
    """Busca TODAS as proposições no intervalo [data_inicio, data_fim].

    Itera por todas as páginas da API v2.
    Datas no formato AAAA-MM-DD.
    """
    todas = []
    pagina_atual = 1
    total_paginas = 1

    while pagina_atual <= total_paginas:
        params = {
            "dataInicio": data_inicio,
            "dataFim": data_fim,
            "itens": config.CAMARA_ITENS_POR_PAGINA,
            "pagina": pagina_atual,
            "ordem": "ASC",
            "ordenarPor": "id",
        }

        logger.info("Câmara — página %d/%d", pagina_atual, total_paginas)

        try:
            resp = sessao.get(
                f"{config.CAMARA_API_BASE}/proposicoes",
                params=params,
                timeout=config.HTTP_TIMEOUT,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Erro ao buscar proposições (pág %d): %s", pagina_atual, exc)
            break

        dados = resp.json().get("dados", [])
        if not dados:
            break

        todas.extend(dados)

        # Atualiza total de páginas na primeira iteração
        if pagina_atual == 1:
            link_header = resp.headers.get("Link", "")
            total_paginas = _extrair_total_paginas(link_header)
            logger.info("Câmara — total de páginas: %d", total_paginas)

        pagina_atual += 1
        time.sleep(config.HTTP_DELAY_ENTRE_REQUESTS)

    logger.info("Câmara — total bruto coletado: %d proposições", len(todas))
    return todas


# ---------------------------------------------------------------------------
# Classificação por palavras-chave (FIX do Bug #1)
# ---------------------------------------------------------------------------
def classificar_tema(ementa: str) -> str | None:
    """Retorna o rótulo do PRIMEIRO tema encontrado na ementa.

    CORRIGE o bug original: o uso incorreto de `or` fazia com que
    a condição sempre fosse True no último elif, classificando
    toda proposição como "ONGs".
    """
    ementa_upper = (ementa or "").upper()
    for palavra in config.PALAVRAS_CHAVE:
        if palavra in ementa_upper:
            return config.ROTULO_TEMA.get(palavra, palavra)
    return None


def filtrar_proposicoes(proposicoes: list[dict]) -> list[dict]:
    """Filtra proposições que contenham ao menos uma palavra-chave.

    Retorna apenas as que tiverem match, com campos extras:
    - _tema_monitoramento: rótulo legível
    - _keywords_encontradas: lista de keywords presentes
    """
    # Regex com todas as keywords para performance
    padrao = re.compile(
        "|".join(re.escape(p) for p in config.PALAVRAS_CHAVE),
        re.IGNORECASE,
    )

    resultado = []
    for prop in proposicoes:
        ementa = prop.get("ementa") or ""
        matches = padrao.findall(ementa.upper())
        if matches:
            prop["_tema_monitoramento"] = classificar_tema(ementa)
            prop["_keywords_encontradas"] = list(set(m.upper() for m in matches))
            resultado.append(prop)

    logger.info("Câmara — %d proposições após filtro por keywords", len(resultado))
    return resultado


# ---------------------------------------------------------------------------
# Enriquecimento: detalhes, autores, temas
# ---------------------------------------------------------------------------
def _buscar_detalhes(sessao: requests.Session, prop_id: int) -> dict:
    """Busca detalhes completos via /proposicoes/{id}."""
    try:
        resp = sessao.get(
            f"{config.CAMARA_API_BASE}/proposicoes/{prop_id}",
            timeout=config.HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("dados", {})
    except requests.RequestException as exc:
        logger.warning("Erro ao buscar detalhes da proposição %s: %s", prop_id, exc)
        return {}


def _buscar_autores(sessao: requests.Session, prop_id: int) -> str:
    """Busca autores via REST v2 /proposicoes/{id}/autores.

    SUBSTITUI o endpoint SOAP legado SitCamaraWS que o projeto
    original usava e que está em risco de descontinuação.
    """
    try:
        resp = sessao.get(
            f"{config.CAMARA_API_BASE}/proposicoes/{prop_id}/autores",
            timeout=config.HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        autores = resp.json().get("dados", [])
        nomes = [a.get("nome", "Desconhecido") for a in autores]
        return "; ".join(nomes)
    except requests.RequestException as exc:
        logger.warning("Erro ao buscar autores da proposição %s: %s", prop_id, exc)
        return ""


def _buscar_temas(sessao: requests.Session, prop_id: int) -> str:
    """Busca temas oficiais via /proposicoes/{id}/temas."""
    try:
        resp = sessao.get(
            f"{config.CAMARA_API_BASE}/proposicoes/{prop_id}/temas",
            timeout=config.HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        temas = resp.json().get("dados", [])
        nomes = [t.get("tema", "") for t in temas]
        return "; ".join(filter(None, nomes))
    except requests.RequestException as exc:
        logger.warning("Erro ao buscar temas da proposição %s: %s", prop_id, exc)
        return ""


def enriquecer_proposicoes(
    sessao: requests.Session,
    proposicoes: list[dict],
) -> list[dict]:
    """Enriquece proposições filtradas com detalhes, autores e temas."""
    enriquecidas = []
    total = len(proposicoes)

    for idx, prop in enumerate(proposicoes, 1):
        prop_id = prop.get("id")
        logger.info("Câmara — enriquecendo %d/%d (id=%s)", idx, total, prop_id)

        detalhes = _buscar_detalhes(sessao, prop_id)
        time.sleep(config.HTTP_DELAY_ENTRE_REQUESTS)

        autores = _buscar_autores(sessao, prop_id)
        time.sleep(config.HTTP_DELAY_ENTRE_REQUESTS)

        temas = _buscar_temas(sessao, prop_id)
        time.sleep(config.HTTP_DELAY_ENTRE_REQUESTS)

        status = detalhes.get("statusProposicao", {}) or {}

        registro = {
            "data_consulta": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "casa": "Câmara",
            "id": str(prop_id),
            "siglaTipo": prop.get("siglaTipo", ""),
            "numero": str(prop.get("numero", "")),
            "ano": str(prop.get("ano", "")),
            "ementa": prop.get("ementa", ""),
            "dataApresentacao": detalhes.get("dataApresentacao", ""),
            "statusSituacao": status.get("descricaoSituacao", ""),
            "statusOrgao": status.get("siglaOrgao", ""),
            "statusData": status.get("dataHora", ""),
            "keywords_encontradas": ", ".join(prop.get("_keywords_encontradas", [])),
            "urlInteiroTeor": detalhes.get("urlInteiroTeor", ""),
            "autores": autores,
            "temas_api": temas,
            "tema_monitoramento": prop.get("_tema_monitoramento", ""),
            "indexacao_oficial": "",  # campo exclusivo do Senado
            "pagina_proposicao": (
                f"https://www.camara.leg.br/proposicoesWeb/"
                f"fichadetramitacao?idProposicao={prop_id}"
            ),
            "uri": detalhes.get("uri", ""),
        }

        enriquecidas.append(registro)

    return enriquecidas


# ---------------------------------------------------------------------------
# Pipeline completo da Câmara
# ---------------------------------------------------------------------------
def executar_coleta(data_inicio: str, data_fim: str) -> list[dict]:
    """Executa pipeline: coletar → filtrar → enriquecer.

    Retorna lista de dicts prontos para planilha/email.
    """
    logger.info("=== CÂMARA: Coleta de %s a %s ===", data_inicio, data_fim)

    sessao = criar_sessao_http()

    # 1. Coleta paginada
    proposicoes = coletar_proposicoes(sessao, data_inicio, data_fim)

    # 2. Filtro por palavras-chave
    filtradas = filtrar_proposicoes(proposicoes)

    # 3. Enriquecimento
    if filtradas:
        resultado = enriquecer_proposicoes(sessao, filtradas)
    else:
        resultado = []

    logger.info("=== CÂMARA: %d proposições encontradas ===", len(resultado))
    return resultado

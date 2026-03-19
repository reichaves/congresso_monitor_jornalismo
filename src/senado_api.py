"""
Módulo de coleta da API de Dados Abertos do Senado Federal.
Autor: Reinaldo Chaves

Particularidades da API do Senado:
- Formato padrão é XML; JSON requer sufixo .json ou header Accept
- Não há busca textual nativa — filtragem local obrigatória
- Sem paginação — respostas vêm completas
- JSON profundamente aninhado e pode ser dict (1 item) ou list (N itens)
- Campo IndexacaoMateria contém palavras-chave oficiais do Senado

Formatos de resposta por endpoint:
- /materia/atualizadas: nested (IdentificacaoMateria.CodigoMateria, DadosBasicosMateria.EmentaMateria, ...)
- /materia/pesquisa/lista: flat (Codigo, Ementa, Autor, Data, ...)
- _normalizar_materia() unifica os dois formatos em chaves comuns
"""

import logging
import re
import time
from datetime import datetime

import requests

from . import config
from .camara_api import criar_sessao_http

logger = logging.getLogger(__name__)

# Sufixo padrão para forçar JSON
_JSON = ".json"


# ---------------------------------------------------------------------------
# Utilitários para navegar o JSON aninhado do Senado
# ---------------------------------------------------------------------------
def _garantir_lista(valor) -> list:
    """Garante que o valor seja uma lista.

    A API do Senado retorna dict quando há 1 resultado
    e list quando há N resultados.
    """
    if valor is None:
        return []
    if isinstance(valor, dict):
        return [valor]
    if isinstance(valor, list):
        return valor
    return []


def _extrair_campo(dicionario: dict, *chaves: str, padrao: str = "") -> str:
    """Navega chaves aninhadas com segurança. Retorna string."""
    atual = dicionario
    for chave in chaves:
        if isinstance(atual, dict):
            atual = atual.get(chave)
        else:
            return padrao
        if atual is None:
            return padrao
    return str(atual) if atual is not None else padrao


def _normalizar_materia(mat: dict) -> dict:
    """Normaliza a matéria para um formato flat comum, independente do endpoint.

    O endpoint /materia/atualizadas retorna estrutura nested:
      IdentificacaoMateria.CodigoMateria, DadosBasicosMateria.EmentaMateria, etc.

    O endpoint /materia/pesquisa/lista retorna estrutura flat:
      Codigo, Ementa, Autor, Data, etc.

    Após normalização, os campos CodigoMateria, EmentaMateria, IndexacaoMateria,
    SiglaSubtipoMateria, NumeroMateria, AnoMateria, DataApresentacao e _AutorRaw
    estão disponíveis no nível raiz do dict.
    """
    if "IdentificacaoMateria" in mat:
        # Formato atualizadas: nested
        ident = mat.get("IdentificacaoMateria", {})
        dados = mat.get("DadosBasicosMateria", {})
        mat.setdefault("CodigoMateria", ident.get("CodigoMateria", ""))
        mat.setdefault("SiglaSubtipoMateria", ident.get("SiglaSubtipoMateria", ""))
        mat.setdefault("NumeroMateria", ident.get("NumeroMateria", ""))
        mat.setdefault("AnoMateria", ident.get("AnoMateria", ""))
        mat.setdefault("EmentaMateria", dados.get("EmentaMateria", ""))
        mat.setdefault("IndexacaoMateria", dados.get("IndexacaoMateria", ""))
        mat.setdefault("DataApresentacao", dados.get("DataApresentacao", ""))
        mat.setdefault("_AutorRaw", dados.get("Autor", ""))
    elif "Codigo" in mat:
        # Formato pesquisa/lista: flat
        mat.setdefault("CodigoMateria", mat.get("Codigo", ""))
        mat.setdefault("SiglaSubtipoMateria", mat.get("Sigla", ""))
        mat.setdefault("NumeroMateria", mat.get("Numero", ""))
        mat.setdefault("AnoMateria", mat.get("Ano", ""))
        mat.setdefault("EmentaMateria", mat.get("Ementa", ""))
        mat.setdefault("IndexacaoMateria", "")  # não disponível em pesquisa/lista
        mat.setdefault("DataApresentacao", mat.get("Data", ""))
        mat.setdefault("_AutorRaw", mat.get("Autor", ""))
    return mat


# ---------------------------------------------------------------------------
# Coleta de matérias atualizadas
# ---------------------------------------------------------------------------
def coletar_materias_atualizadas(
    sessao: requests.Session,
    num_dias: int | None = None,
) -> list[dict]:
    """Busca matérias atualizadas nos últimos N dias.

    Usa /materia/atualizadas.json que retorna matérias com ações
    legislativas recentes — ideal para monitoramento periódico.
    """
    if num_dias is None:
        num_dias = config.SENADO_DIAS_ATUALIZADAS

    url = f"{config.SENADO_API_BASE}/materia/atualizadas{_JSON}"
    params = {"numdias": num_dias}
    headers = {"Accept": "application/json"}

    logger.info("Senado — buscando matérias atualizadas (últimos %d dias)", num_dias)

    try:
        resp = sessao.get(
            url, params=params, headers=headers, timeout=config.HTTP_TIMEOUT
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.error("Erro ao buscar matérias atualizadas do Senado: %s", exc)
        return []

    dados = resp.json()

    lista_container = (
        dados
        .get("ListaMateriasAtualizadas", {})
        .get("Materias", {})
    )
    materias = [
        _normalizar_materia(m)
        for m in _garantir_lista(lista_container.get("Materia"))
    ]

    logger.info("Senado — %d matérias atualizadas encontradas", len(materias))
    return materias


def coletar_materias_pesquisa(
    sessao: requests.Session,
    ano: int | None = None,
    tramitando: bool = True,
) -> list[dict]:
    """Busca matérias via /materia/pesquisa/lista.json.

    Usado como complemento quando o endpoint de atualizadas
    não retorna volume suficiente.
    """
    if ano is None:
        ano = datetime.now().year

    url = f"{config.SENADO_API_BASE}/materia/pesquisa/lista{_JSON}"
    params = {"ano": ano}
    if tramitando:
        params["tramitando"] = "S"

    headers = {"Accept": "application/json"}

    logger.info("Senado — pesquisando matérias (ano=%d, tramitando=%s)", ano, tramitando)

    try:
        resp = sessao.get(
            url, params=params, headers=headers, timeout=config.HTTP_TIMEOUT
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.error("Erro ao pesquisar matérias do Senado: %s", exc)
        return []

    dados = resp.json()

    lista_container = (
        dados
        .get("PesquisaBasicaMateria", {})
        .get("Materias", {})
    )
    materias = [
        _normalizar_materia(m)
        for m in _garantir_lista(lista_container.get("Materia"))
    ]

    logger.info("Senado — %d matérias encontradas na pesquisa", len(materias))
    return materias


# ---------------------------------------------------------------------------
# Filtro local por palavras-chave
# ---------------------------------------------------------------------------
def filtrar_materias(materias: list[dict]) -> list[dict]:
    """Filtra matérias do Senado por palavras-chave.

    Busca tanto na ementa quanto na indexação oficial.
    A API do Senado NÃO tem busca textual — filtro é local.
    Requer que as matérias já tenham sido normalizadas por _normalizar_materia().
    """
    padrao = re.compile(
        "|".join(re.escape(p) for p in config.PALAVRAS_CHAVE),
        re.IGNORECASE,
    )

    resultado = []
    for mat in materias:
        ementa = _extrair_campo(mat, "EmentaMateria")
        indexacao = _extrair_campo(mat, "IndexacaoMateria")
        texto_busca = f"{ementa} {indexacao}".upper()

        matches = padrao.findall(texto_busca)
        if matches:
            mat["_keywords_encontradas"] = list(set(m.upper() for m in matches))
            mat["_tema_monitoramento"] = _classificar_tema(texto_busca)
            resultado.append(mat)

    logger.info("Senado — %d matérias após filtro por keywords", len(resultado))
    return resultado


def _classificar_tema(texto_upper: str) -> str:
    """Retorna rótulo do primeiro tema encontrado no texto."""
    for palavra in config.PALAVRAS_CHAVE:
        if palavra in texto_upper:
            return config.ROTULO_TEMA.get(palavra, palavra)
    return ""


# ---------------------------------------------------------------------------
# Enriquecimento: detalhes, situação atual, textos
# ---------------------------------------------------------------------------
def _buscar_detalhes_materia(sessao: requests.Session, codigo: str) -> dict:
    """Busca detalhes via /materia/{codigo}.json.

    Retorna DetalheMateria.Materia com DadosBasicosMateria.Autor e Assunto (quando disponível).
    """
    url = f"{config.SENADO_API_BASE}/materia/{codigo}{_JSON}"
    headers = {"Accept": "application/json"}

    try:
        resp = sessao.get(url, headers=headers, timeout=config.HTTP_TIMEOUT)
        resp.raise_for_status()
        dados = resp.json()
        return (
            dados
            .get("DetalheMateria", {})
            .get("Materia", {})
        )
    except requests.RequestException as exc:
        logger.warning("Erro ao buscar detalhes da matéria %s: %s", codigo, exc)
        return {}


def _buscar_textos_materia(sessao: requests.Session, codigo: str) -> str:
    """Busca URL do inteiro teor via /materia/textos/{codigo}.json."""
    url = f"{config.SENADO_API_BASE}/materia/textos/{codigo}{_JSON}"
    headers = {"Accept": "application/json"}

    try:
        resp = sessao.get(url, headers=headers, timeout=config.HTTP_TIMEOUT)
        resp.raise_for_status()
        dados = resp.json()

        textos_container = (
            dados
            .get("TextoMateria", {})
            .get("Materia", {})
            .get("Textos", {})
        )
        textos = _garantir_lista(textos_container.get("Texto"))

        if textos:
            return _extrair_campo(textos[0], "UrlTexto")
        return ""
    except requests.RequestException as exc:
        logger.warning("Erro ao buscar textos da matéria %s: %s", codigo, exc)
        return ""


def _buscar_situacao_materia(sessao: requests.Session, codigo: str) -> dict:
    """Busca situação atual via /materia/situacaoatual/{codigo}.json.

    Retorna dict com:
      - descricao: DescricaoSituacao (ex: "AGUARDANDO DESIGNAÇÃO DO RELATOR")
      - local: SiglaLocal do comitê/órgão atual (ex: "CDIR")
      - data: data da situação ou do local atual
    """
    url = f"{config.SENADO_API_BASE}/materia/situacaoatual/{codigo}{_JSON}"
    headers = {"Accept": "application/json"}

    try:
        resp = sessao.get(url, headers=headers, timeout=config.HTTP_TIMEOUT)
        resp.raise_for_status()
        dados = resp.json()

        mat_list = _garantir_lista(
            dados
            .get("SituacaoAtualMateria", {})
            .get("Materias", {})
            .get("Materia")
        )
        if not mat_list:
            return {}

        situacao_atual = mat_list[0].get("SituacaoAtual", {})
        autuacoes = _garantir_lista(
            situacao_atual.get("Autuacoes", {}).get("Autuacao")
        )
        if not autuacoes:
            return {}

        ultima = autuacoes[-1]

        # DescricaoSituacao — presente apenas para matérias em tramitação
        situacoes = _garantir_lista(ultima.get("Situacoes", {}).get("Situacao"))
        descricao = ""
        data_situacao = ""
        if situacoes:
            ultima_sit = situacoes[-1]
            descricao = ultima_sit.get("DescricaoSituacao", "")
            data_situacao = ultima_sit.get("DataSituacao", "")

        # Local legislativo (comissão/plenário); fallback para local administrativo
        local = ultima.get("Local") or ultima.get("LocalAdministrativo") or {}
        sigla_local = local.get("SiglaLocal", "")
        data_local = local.get("DataLocal", "")

        return {
            "descricao": descricao,
            "local": sigla_local,
            "data": data_situacao or data_local,
        }
    except requests.RequestException as exc:
        logger.warning("Erro ao buscar situação da matéria %s: %s", codigo, exc)
        return {}


def enriquecer_materias(
    sessao: requests.Session,
    materias: list[dict],
) -> list[dict]:
    """Enriquece matérias filtradas com detalhes, situação atual, textos e autores."""
    enriquecidas = []
    total = len(materias)

    for idx, mat in enumerate(materias, 1):
        codigo = _extrair_campo(mat, "CodigoMateria")
        if not codigo:
            continue

        logger.info("Senado — enriquecendo %d/%d (código=%s)", idx, total, codigo)

        detalhes = _buscar_detalhes_materia(sessao, codigo)
        time.sleep(config.HTTP_DELAY_ENTRE_REQUESTS)

        url_texto = _buscar_textos_materia(sessao, codigo)
        time.sleep(config.HTTP_DELAY_ENTRE_REQUESTS)

        situacao = _buscar_situacao_materia(sessao, codigo)
        time.sleep(config.HTTP_DELAY_ENTRE_REQUESTS)

        # Autores: vem de DadosBasicosMateria.Autor no detail endpoint (string simples)
        # com fallback para _AutorRaw normalizado da fonte original (atualizadas/pesquisa)
        autores = (
            _extrair_campo(detalhes, "DadosBasicosMateria", "Autor")
            or mat.get("_AutorRaw", "")
        )

        # temas_api: Assunto.AssuntoEspecifico.Descricao
        # Disponível no endpoint atualizadas (mat) e no detail (detalhes) para alguns
        temas_api = (
            _extrair_campo(mat, "Assunto", "AssuntoEspecifico", "Descricao")
            or _extrair_campo(detalhes, "Assunto", "AssuntoEspecifico", "Descricao")
        )

        registro = {
            "data_consulta": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "casa": "Senado",
            "id": codigo,
            "siglaTipo": _extrair_campo(mat, "SiglaSubtipoMateria"),
            "numero": _extrair_campo(mat, "NumeroMateria"),
            "ano": _extrair_campo(mat, "AnoMateria"),
            "ementa": _extrair_campo(mat, "EmentaMateria"),
            "dataApresentacao": _extrair_campo(mat, "DataApresentacao"),
            "statusSituacao": situacao.get("descricao", ""),
            "statusOrgao": situacao.get("local", ""),
            "statusData": situacao.get("data", ""),
            "keywords_encontradas": ", ".join(mat.get("_keywords_encontradas", [])),
            "urlInteiroTeor": url_texto,
            "autores": autores,
            "temas_api": temas_api,
            "tema_monitoramento": mat.get("_tema_monitoramento", ""),
            "indexacao_oficial": _extrair_campo(mat, "IndexacaoMateria"),
            "pagina_proposicao": (
                f"https://www25.senado.leg.br/web/atividade/materias/-/"
                f"materia/{codigo}"
            ),
            "uri": f"{config.SENADO_API_BASE}/materia/{codigo}",
        }

        enriquecidas.append(registro)

    return enriquecidas


# ---------------------------------------------------------------------------
# Pipeline completo do Senado
# ---------------------------------------------------------------------------
def executar_coleta(data_inicio: str, data_fim: str) -> list[dict]:
    """Executa pipeline: coletar → filtrar → enriquecer.

    Usa /materia/atualizadas como fonte principal e complementa com
    /materia/pesquisa/lista para o ano corrente (fonte mais abrangente).
    data_inicio/data_fim são usados para calcular numdias.
    """
    logger.info("=== SENADO: Coleta de %s a %s ===", data_inicio, data_fim)

    sessao = criar_sessao_http()

    # Calcular número de dias entre as datas
    try:
        dt_inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
        dt_fim = datetime.strptime(data_fim, "%Y-%m-%d")
        # Usa pelo menos SENADO_DIAS_ATUALIZADAS para garantir cobertura suficiente
        num_dias = max((dt_fim - dt_inicio).days, config.SENADO_DIAS_ATUALIZADAS)
    except ValueError:
        num_dias = config.SENADO_DIAS_ATUALIZADAS

    # 1a. Fonte principal: matérias com movimentação recente
    materias_atualizadas = coletar_materias_atualizadas(sessao, num_dias=num_dias)

    # 1b. Fonte complementar: pesquisa por ano (captura proposições sem movimentação recente)
    ano_atual = datetime.now().year
    materias_pesquisa = coletar_materias_pesquisa(sessao, ano=ano_atual, tramitando=False)

    # Mesclar e deduplicar por CodigoMateria (já normalizado)
    codigos_vistos: set[str] = set()
    materias_combinadas: list[dict] = []
    for mat in materias_atualizadas + materias_pesquisa:
        cod = _extrair_campo(mat, "CodigoMateria")
        if cod and cod not in codigos_vistos:
            codigos_vistos.add(cod)
            materias_combinadas.append(mat)
        elif not cod:
            materias_combinadas.append(mat)

    logger.info(
        "Senado — total combinado (atualizadas=%d + pesquisa=%d → únicos=%d)",
        len(materias_atualizadas), len(materias_pesquisa), len(materias_combinadas),
    )

    # 2. Filtrar por palavras-chave
    filtradas = filtrar_materias(materias_combinadas)

    # 3. Enriquecer
    if filtradas:
        resultado = enriquecer_materias(sessao, filtradas)
    else:
        resultado = []

    logger.info("=== SENADO: %d matérias encontradas ===", len(resultado))
    return resultado

"""
Módulo de coleta da API de Dados Abertos do Senado Federal.
Autor: Reinaldo Chaves

Particularidades da API do Senado:
- Formato padrão é XML; JSON requer sufixo .json ou header Accept
- Não há busca textual nativa — filtragem local obrigatória
- Sem paginação — respostas vêm completas
- JSON profundamente aninhado e pode ser dict (1 item) ou list (N itens)
- Campo IndexacaoMateria contém palavras-chave oficiais do Senado

Esquemas de campo por endpoint:
  /materia/atualizadas → campos aninhados:
    IdentificacaoMateria.CodigoMateria, .SiglaSubtipoMateria, .NumeroMateria, .AnoMateria
    DadosBasicosMateria.EmentaMateria, .IndexacaoMateria, .DataApresentacao
  /materia/pesquisa/lista → campos planos:
    Codigo, Sigla, Numero, Ano, Ementa, Data
    (sem IndexacaoMateria nesse endpoint)
  A função _normalizar_materia() unifica ambos os esquemas em campos _privados.
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


# ---------------------------------------------------------------------------
# Normalização: unifica os dois esquemas de campo em campos _privados
# ---------------------------------------------------------------------------
def _normalizar_materia(mat: dict) -> dict:
    """Adiciona campos _privados normalizados ao dict da matéria.

    Suporta dois esquemas retornados pelos endpoints do Senado:
    - /materia/atualizadas  → campos aninhados em IdentificacaoMateria /
                               DadosBasicosMateria
    - /materia/pesquisa/lista → campos planos: Codigo, Sigla, Ementa, etc.
    """
    # Esquema 1: atualizadas (campos aninhados)
    ident = mat.get("IdentificacaoMateria", {})
    dados = mat.get("DadosBasicosMateria", {})

    if ident:
        mat["_codigo"] = str(ident.get("CodigoMateria") or "")
        mat["_sigla"] = str(ident.get("SiglaSubtipoMateria") or "")
        mat["_numero"] = str(ident.get("NumeroMateria") or "")
        mat["_ano"] = str(ident.get("AnoMateria") or "")
        mat["_ementa_busca"] = str(dados.get("EmentaMateria") or "")
        mat["_indexacao_busca"] = str(dados.get("IndexacaoMateria") or "")
        mat["_data_apresentacao"] = str(dados.get("DataApresentacao") or "")
    else:
        # Esquema 2: pesquisa/lista (campos planos)
        mat["_codigo"] = str(mat.get("Codigo") or "")
        mat["_sigla"] = str(mat.get("Sigla") or "")
        mat["_numero"] = str(mat.get("Numero") or "")
        mat["_ano"] = str(mat.get("Ano") or "")
        mat["_ementa_busca"] = str(mat.get("Ementa") or mat.get("EmentaMateria") or "")
        mat["_indexacao_busca"] = str(mat.get("IndexacaoMateria") or "")
        mat["_data_apresentacao"] = str(mat.get("Data") or mat.get("DataApresentacao") or "")

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
    Limite máximo aceito pela API: 30 dias.
    """
    if num_dias is None:
        num_dias = config.SENADO_DIAS_ATUALIZADAS

    # API retorna HTTP 400 para numdias > 30
    num_dias = min(num_dias, 30)

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

    # Navegar estrutura aninhada do Senado
    # Campos aninhados: IdentificacaoMateria / DadosBasicosMateria
    lista_container = (
        dados
        .get("ListaMateriasAtualizadas", {})
        .get("Materias", {})
    )
    materias = _garantir_lista(lista_container.get("Materia"))
    materias = [_normalizar_materia(m) for m in materias]

    logger.info("Senado — %d matérias atualizadas encontradas", len(materias))
    return materias


def coletar_materias_pesquisa(
    sessao: requests.Session,
    ano: int | None = None,
    tramitando: bool | None = None,
) -> list[dict]:
    """Busca matérias via /materia/pesquisa/lista.json.

    Usado como fonte principal de busca. Retorna campos PLANOS (não
    aninhados): Codigo, Sigla, Numero, Ano, Ementa, Data.
    A API ignora parâmetros de busca textual — filtragem é local.
    tramitando=None busca todas (sem filtro), maximizando a cobertura.
    """
    if ano is None:
        ano = datetime.now().year

    url = f"{config.SENADO_API_BASE}/materia/pesquisa/lista{_JSON}"
    params = {"ano": ano}
    if tramitando is True:
        params["tramitando"] = "S"
    elif tramitando is False:
        params["tramitando"] = "N"
    # tramitando=None → sem parâmetro → retorna todas

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
    materias = _garantir_lista(lista_container.get("Materia"))
    materias = [_normalizar_materia(m) for m in materias]

    logger.info("Senado — %d matérias encontradas na pesquisa", len(materias))
    return materias


# ---------------------------------------------------------------------------
# Filtro local por palavras-chave
# ---------------------------------------------------------------------------
def filtrar_materias(materias: list[dict]) -> list[dict]:
    """Filtra matérias do Senado por palavras-chave.

    Usa os campos normalizados _ementa_busca e _indexacao_busca
    preenchidos por _normalizar_materia(), que suporta ambos os
    esquemas de campo da API (atualizadas e pesquisa/lista).
    A API do Senado NÃO tem busca textual — filtro é local.
    """
    padrao = re.compile(
        "|".join(re.escape(p) for p in config.PALAVRAS_CHAVE),
        re.IGNORECASE,
    )

    resultado = []
    for mat in materias:
        ementa = mat.get("_ementa_busca", "")
        indexacao = mat.get("_indexacao_busca", "")
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
# Enriquecimento: detalhes, movimentações, textos
# ---------------------------------------------------------------------------
def _buscar_detalhes_materia(sessao: requests.Session, codigo: str) -> dict:
    """Busca detalhes completos via /materia/{codigo}.json."""
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
            # Pega a URL do primeiro texto disponível
            return _extrair_campo(textos[0], "UrlTexto")
        return ""
    except requests.RequestException as exc:
        logger.warning("Erro ao buscar textos da matéria %s: %s", codigo, exc)
        return ""


def _extrair_autores(detalhes: dict) -> str:
    """Extrai nomes dos autores do detalhe da matéria."""
    autoria = detalhes.get("Autoria", {})
    autores = _garantir_lista(autoria.get("Autor"))

    nomes = []
    for autor in autores:
        nome = _extrair_campo(autor, "NomeAutor")
        if not nome:
            nome = _extrair_campo(autor, "DescricaoTipoAutor")
        if nome:
            uf = _extrair_campo(autor, "UfAutor")
            partido = _extrair_campo(autor, "SiglaPartidoAutor")
            partes = [nome]
            if partido:
                partes.append(f"({partido}")
                if uf:
                    partes[-1] += f"/{uf})"
                else:
                    partes[-1] += ")"
            nomes.append(" ".join(partes))

    return "; ".join(nomes)


def _extrair_situacao(detalhes: dict) -> dict:
    """Extrai informações de situação atual da matéria."""
    situacao = detalhes.get("SituacaoAtual", {}).get("Audesp", {})
    if not situacao:
        situacao = detalhes.get("SituacaoAtual", {})

    return {
        "descricao": _extrair_campo(situacao, "DescricaoSituacao"),
        "local": _extrair_campo(situacao, "Local", "NomeCasaLocal"),
        "data": _extrair_campo(situacao, "DataSituacao"),
    }


def enriquecer_materias(
    sessao: requests.Session,
    materias: list[dict],
) -> list[dict]:
    """Enriquece matérias filtradas com detalhes, textos e autores.

    Usa os campos _privados normalizados por _normalizar_materia().
    Os detalhes completos são buscados via /materia/{codigo}.json,
    que tem estrutura: DetalheMateria.Materia.IdentificacaoMateria /
    DadosBasicosMateria (independente da fonte original).
    """
    enriquecidas = []
    total = len(materias)

    for idx, mat in enumerate(materias, 1):
        # Usa campo normalizado — funciona para atualizadas e pesquisa/lista
        codigo = mat.get("_codigo", "")
        if not codigo:
            continue

        logger.info("Senado — enriquecendo %d/%d (código=%s)", idx, total, codigo)

        detalhes = _buscar_detalhes_materia(sessao, codigo)
        time.sleep(config.HTTP_DELAY_ENTRE_REQUESTS)

        url_texto = _buscar_textos_materia(sessao, codigo)
        time.sleep(config.HTTP_DELAY_ENTRE_REQUESTS)

        autores = _extrair_autores(detalhes) if detalhes else ""
        situacao = _extrair_situacao(detalhes) if detalhes else {}

        # Preferir dados do detalhe (mais completos) e cair nos normalizados
        det_ident = detalhes.get("IdentificacaoMateria", {}) if detalhes else {}
        det_dados = detalhes.get("DadosBasicosMateria", {}) if detalhes else {}

        sigla = det_ident.get("SiglaSubtipoMateria") or mat.get("_sigla", "")
        numero = det_ident.get("NumeroMateria") or mat.get("_numero", "")
        ano = det_ident.get("AnoMateria") or mat.get("_ano", "")
        ementa = det_dados.get("EmentaMateria") or mat.get("_ementa_busca", "")
        data_apresentacao = det_dados.get("DataApresentacao") or mat.get("_data_apresentacao", "")
        indexacao = det_dados.get("IndexacaoMateria") or mat.get("_indexacao_busca", "")

        registro = {
            "data_consulta": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "casa": "Senado",
            "id": codigo,
            "siglaTipo": sigla,
            "numero": numero,
            "ano": ano,
            "ementa": ementa,
            "dataApresentacao": data_apresentacao,
            "statusSituacao": situacao.get("descricao", ""),
            "statusOrgao": situacao.get("local", ""),
            "statusData": situacao.get("data", ""),
            "keywords_encontradas": ", ".join(mat.get("_keywords_encontradas", [])),
            "urlInteiroTeor": url_texto,
            "autores": autores,
            "temas_api": _extrair_campo(detalhes, "Assunto", "AssuntoEspecifico"),
            "tema_monitoramento": mat.get("_tema_monitoramento", ""),
            "indexacao_oficial": indexacao,
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

    Fontes combinadas para máxima cobertura:
    - /materia/atualizadas (máx. 30 dias) — movimentação recente
    - /materia/pesquisa/lista (ano corrente, sem filtro tramitando) — todas as matérias do ano
    data_inicio/data_fim são usados para calcular numdias de atualizadas.
    """
    logger.info("=== SENADO: Coleta de %s a %s ===", data_inicio, data_fim)

    sessao = criar_sessao_http()

    # Calcular número de dias; a API aceita no máximo 30
    try:
        dt_inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
        dt_fim = datetime.strptime(data_fim, "%Y-%m-%d")
        num_dias = max((dt_fim - dt_inicio).days, config.SENADO_DIAS_ATUALIZADAS)
        num_dias = min(num_dias, 30)  # limite da API
    except ValueError:
        num_dias = config.SENADO_DIAS_ATUALIZADAS

    # 1a. Fonte principal: matérias com movimentação recente
    materias_atualizadas = coletar_materias_atualizadas(sessao, num_dias=num_dias)

    # 1b. Fonte complementar: todas as matérias do ano (tramitando=None → sem filtro)
    ano_atual = datetime.now().year
    materias_pesquisa = coletar_materias_pesquisa(sessao, ano=ano_atual, tramitando=None)

    # Mesclar e deduplicar pelo campo normalizado _codigo
    codigos_vistos: set[str] = set()
    materias_combinadas: list[dict] = []
    for mat in materias_atualizadas + materias_pesquisa:
        cod = mat.get("_codigo", "")
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

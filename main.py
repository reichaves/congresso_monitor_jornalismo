"""
Monitor Legislativo — Jornalismo no Congresso
Script principal de orquestração.
Autor: Reinaldo Chaves

Pipeline:
1. Lê movimentações já existentes na planilha (deduplicação)
2. Coleta proposições da Câmara (API v2 REST)
3. Coleta matérias do Senado (API Dados Abertos)
4. Filtra apenas movimentações novas (não registradas anteriormente)
5. Se houver novidades: grava na planilha e envia relatório por email
   Se não houver novidades: encerra sem gravar nem emailar
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta

from src import config
from src.camara_api import executar_coleta as coleta_camara
from src.senado_api import executar_coleta as coleta_senado
from src.sheets import (
    gravar_dados,
    ler_emails_destinatarios,
    ler_movimentacoes_existentes,
    ler_estatisticas_planilha,
)
from src.email_report import enviar_relatorio

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("monitor")


_CAMPOS_CHAVE = ["casa", "id", "numero", "ano", "statusSituacao", "statusOrgao", "statusData"]


def _filtrar_novos(registros: list[dict], existentes: set[tuple]) -> list[dict]:
    """Retorna apenas os registros cuja movimentação ainda não está na planilha."""
    novos = []
    for reg in registros:
        chave = tuple(str(reg.get(c, "")).strip() for c in _CAMPOS_CHAVE)
        if chave not in existentes:
            novos.append(reg)
    return novos


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Monitor Legislativo — coleta, armazena e notifica"
    )
    parser.add_argument(
        "--dias",
        type=int,
        default=2,
        help="Número de dias retroativos para buscar (padrão: 2)",
    )
    parser.add_argument(
        "--data-inicio",
        type=str,
        default=None,
        help="Data de início no formato AAAA-MM-DD (sobrepõe --dias)",
    )
    parser.add_argument(
        "--data-fim",
        type=str,
        default=None,
        help="Data de fim no formato AAAA-MM-DD (padrão: hoje)",
    )
    parser.add_argument(
        "--sem-email",
        action="store_true",
        help="Pular envio de email (útil para testes)",
    )
    parser.add_argument(
        "--sem-sheets",
        action="store_true",
        help="Pular gravação no Google Sheets (útil para testes)",
    )

    args = parser.parse_args()

    # Determinar intervalo de datas
    if args.data_fim:
        data_fim = args.data_fim
    else:
        data_fim = datetime.now().strftime("%Y-%m-%d")

    if args.data_inicio:
        data_inicio = args.data_inicio
    else:
        dt_inicio = datetime.now() - timedelta(days=args.dias)
        data_inicio = dt_inicio.strftime("%Y-%m-%d")

    logger.info("=" * 60)
    logger.info("MONITOR LEGISLATIVO — JORNALISMO NO CONGRESSO")
    logger.info("Período: %s a %s", data_inicio, data_fim)
    logger.info("Palavras-chave: %d termos", len(config.PALAVRAS_CHAVE))
    logger.info("=" * 60)

    # ------------------------------------------------------------------
    # 1. Ler movimentações já existentes na planilha (deduplicação)
    # ------------------------------------------------------------------
    existentes: set[tuple] = set()
    if not args.sem_sheets:
        try:
            existentes = ler_movimentacoes_existentes()
        except Exception as exc:
            logger.error("Falha ao ler movimentações existentes: %s", exc, exc_info=True)
    else:
        logger.info("Sheets: leitura de existentes pulada (--sem-sheets)")

    # ------------------------------------------------------------------
    # 2. Coleta da Câmara
    # ------------------------------------------------------------------
    try:
        resultados_camara = coleta_camara(data_inicio, data_fim)
    except Exception as exc:
        logger.error("Falha na coleta da Câmara: %s", exc, exc_info=True)
        resultados_camara = []

    # ------------------------------------------------------------------
    # 3. Coleta do Senado
    # ------------------------------------------------------------------
    try:
        resultados_senado = coleta_senado(data_inicio, data_fim)
    except Exception as exc:
        logger.error("Falha na coleta do Senado: %s", exc, exc_info=True)
        resultados_senado = []

    todos = resultados_camara + resultados_senado
    logger.info(
        "Coletados: %d proposições (Câmara=%d, Senado=%d)",
        len(todos),
        len(resultados_camara),
        len(resultados_senado),
    )

    # ------------------------------------------------------------------
    # 4. Filtrar apenas movimentações novas
    # ------------------------------------------------------------------
    novos_camara = _filtrar_novos(resultados_camara, existentes)
    novos_senado = _filtrar_novos(resultados_senado, existentes)
    novos = novos_camara + novos_senado

    repetidos = len(todos) - len(novos)
    logger.info(
        "Novidades: %d (Câmara=%d, Senado=%d) | Repetidos/sem novidade: %d",
        len(novos), len(novos_camara), len(novos_senado), repetidos,
    )

    if not novos:
        logger.info("=" * 60)
        logger.info("SEM NOVIDADES — todas as movimentações já estavam na planilha.")
        logger.info("Nenhuma linha será gravada e nenhum email será enviado.")
        logger.info("=" * 60)
        return

    # ------------------------------------------------------------------
    # 5. Gravar apenas novidades no Google Sheets
    # ------------------------------------------------------------------
    if not args.sem_sheets:
        try:
            linhas_inseridas = gravar_dados(novos)
            logger.info("Sheets: %d linhas inseridas", linhas_inseridas)
        except Exception as exc:
            logger.error("Falha ao gravar no Sheets: %s", exc, exc_info=True)
    else:
        logger.info("Sheets: gravação pulada (--sem-sheets)")

    # ------------------------------------------------------------------
    # 5b. Ler estatísticas acumuladas (após gravar, para incluir hoje)
    # ------------------------------------------------------------------
    stats_planilha = None
    if not args.sem_sheets:
        try:
            stats_planilha = ler_estatisticas_planilha()
        except Exception as exc:
            logger.warning("Falha ao ler estatísticas da planilha: %s", exc)

    # ------------------------------------------------------------------
    # 6. Enviar relatório por email com as novidades
    # ------------------------------------------------------------------
    if not args.sem_email:
        try:
            destinatarios = ler_emails_destinatarios()
            if destinatarios:
                sucesso = enviar_relatorio(
                    destinatarios,
                    novos_camara,
                    novos_senado,
                    data_inicio,
                    data_fim,
                    stats_planilha=stats_planilha,
                )
                if sucesso:
                    logger.info("Email: relatório enviado para %d destinatários", len(destinatarios))
                else:
                    logger.error("Email: falha no envio")
            else:
                logger.warning("Email: nenhum destinatário encontrado na planilha")
        except Exception as exc:
            logger.error("Falha ao enviar email: %s", exc, exc_info=True)
    else:
        logger.info("Email: envio pulado (--sem-email)")

    # ------------------------------------------------------------------
    # Resumo final
    # ------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("RESUMO DAS NOVIDADES ENCONTRADAS:")
    for r in novos:
        sigla = r.get("siglaTipo", "")
        numero = r.get("numero", "")
        ano = r.get("ano", "")
        casa = r.get("casa", "")
        keywords = r.get("keywords_encontradas", "")
        logger.info(
            "  [%s] %s %s/%s — keywords: %s",
            casa, sigla, numero, ano, keywords,
        )
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

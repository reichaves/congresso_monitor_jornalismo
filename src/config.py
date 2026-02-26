"""
Configurações centralizadas do monitor legislativo.
Autor: Reinaldo Chaves
"""

import os

# ---------------------------------------------------------------------------
# Palavras-chave monitoradas (canônicas, sempre em UPPER para comparação)
# ---------------------------------------------------------------------------
PALAVRAS_CHAVE = [
    "JORNALISMO",
    "JORNALISTA",
    "JORNALISTAS",
    "COMUNICADORES",
    "IMPRENSA",
    "VERIFICADORES DE FATOS",
    "CHECAGEM DE FATOS",
    "FAKE NEWS",
    "DESINFORMAÇÃO",
    "TRANSPARÊNCIA NA INTERNET",
    "LIBERDADE DE EXPRESSÃO E INFORMAÇÕES DE INTERESSE COLETIVO",
    "TRANSPARÊNCIA DOS DADOS",
    "ONGS",
]

# Mapa de palavras-chave → rótulo legível para relatórios
ROTULO_TEMA = {
    "JORNALISMO": "Jornalismo",
    "JORNALISTA": "Jornalista",
    "JORNALISTAS": "Jornalistas",
    "COMUNICADORES": "Comunicadores",
    "IMPRENSA": "Imprensa",
    "VERIFICADORES DE FATOS": "Verificadores de fatos",
    "CHECAGEM DE FATOS": "Checagem de fatos",
    "FAKE NEWS": "Fake news",
    "DESINFORMAÇÃO": "Desinformação",
    "TRANSPARÊNCIA NA INTERNET": "Transparência na internet",
    "LIBERDADE DE EXPRESSÃO E INFORMAÇÕES DE INTERESSE COLETIVO": "Liberdade de expressão",
    "TRANSPARÊNCIA DOS DADOS": "Transparência dos dados",
    "ONGS": "ONGs",
}

# ---------------------------------------------------------------------------
# API da Câmara dos Deputados (v2 REST)
# ---------------------------------------------------------------------------
CAMARA_API_BASE = "https://dadosabertos.camara.leg.br/api/v2"
CAMARA_ITENS_POR_PAGINA = 100

# ---------------------------------------------------------------------------
# API do Senado Federal (Dados Abertos)
# ---------------------------------------------------------------------------
SENADO_API_BASE = "https://legis.senado.leg.br/dadosabertos"
SENADO_DIAS_ATUALIZADAS = 3  # dias a buscar em /materia/atualizadas

# ---------------------------------------------------------------------------
# Parâmetros de requisição HTTP
# ---------------------------------------------------------------------------
HTTP_TIMEOUT = 30          # segundos
HTTP_MAX_RETRIES = 3
HTTP_BACKOFF_FACTOR = 2    # 2s, 4s, 8s
HTTP_DELAY_ENTRE_REQUESTS = 0.5  # segundos entre chamadas

# ---------------------------------------------------------------------------
# Colunas da planilha Google Sheets (ordem fixa)
# ---------------------------------------------------------------------------
COLUNAS_PLANILHA = [
    "data_consulta",
    "casa",                 # "Câmara" ou "Senado"
    "id",
    "siglaTipo",
    "numero",
    "ano",
    "ementa",
    "dataApresentacao",
    "statusSituacao",
    "statusOrgao",
    "statusData",
    "keywords_encontradas",
    "urlInteiroTeor",
    "autores",
    "temas_api",
    "tema_monitoramento",
    "indexacao_oficial",     # campo exclusivo Senado
    "pagina_proposicao",
    "uri",
]

# ---------------------------------------------------------------------------
# Gmail SMTP (envio de email via App Password)
# ---------------------------------------------------------------------------
GMAIL_USER = os.environ.get("GMAIL_USER", "reichaves@gmail.com")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# ---------------------------------------------------------------------------
# Variáveis de ambiente esperadas (GitHub Secrets)
# ---------------------------------------------------------------------------
GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")
PLANILHA_DADOS_ID = os.environ.get("PLANILHA_DADOS_ID", "")
PLANILHA_EMAILS_ID = os.environ.get("PLANILHA_EMAILS_ID", "")
ABA_DADOS = os.environ.get("ABA_DADOS", "dados")
ABA_EMAILS = os.environ.get("ABA_EMAILS", "emails")

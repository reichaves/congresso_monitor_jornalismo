# Monitor Legislativo — Jornalismo no Congresso

Projeto independente de **Reinaldo Chaves** para monitoramento automatizado de proposições legislativas na Câmara dos Deputados e no Senado Federal que mencionem temas relacionados ao jornalismo.

## O que faz

- Coleta de proposições de segunda a sábado, às 07h BRT, da **Câmara dos Deputados** (API v2 REST) e do **Senado Federal** (API Dados Abertos)
- Filtra por **16 palavras-chave** relacionadas a jornalismo, imprensa, fake news, transparência e ONGs
- **Deduplicação inteligente:** antes de gravar, compara com os dados já existentes na planilha — somente movimentações com `statusSituacao`, `statusOrgao` ou `statusData` diferentes são tratadas como novidade
- Grava apenas as **novidades** em uma **planilha Google Sheets** (histórico cumulativo)
- Envia **relatório HTML personalizado por email** via Gmail SMTP para cada inscrito — **apenas quando há novidades** — com link direto para cancelar a assinatura
- Interface web **Streamlit** com formulário de inscrição, página de cancelamento de assinatura e estatísticas dos dados coletados
- Roda automaticamente via **GitHub Actions** (sem custo, sem servidor)

## Inscreva-se para receber o relatório

Receba o boletim diário no seu email sem precisar configurar nada. Acesse o formulário de inscrição:

**[congreapp-monitor-jornalismo.streamlit.app](https://congreapp-monitor-jornalismo.streamlit.app/)**

---

## Palavras-chave monitoradas

`JORNALISMO` · `JORNALISTA` · `JORNALISTAS` · `COMUNICADORES` · `IMPRENSA` · `MÍDIA` · `COMUNICAÇÃO SOCIAL` · `LIBERDADE DE IMPRENSA` · `VERIFICADORES DE FATOS` · `CHECAGEM DE FATOS` · `FAKE NEWS` · `DESINFORMAÇÃO` · `TRANSPARÊNCIA NA INTERNET` · `LIBERDADE DE EXPRESSÃO E INFORMAÇÕES DE INTERESSE COLETIVO` · `TRANSPARÊNCIA DOS DADOS` · `ONGS`

## Arquitetura

```
┌─────────────────────────────────────────────────────────┐
│  app.py (Streamlit Cloud)                               │
│  Formulário de inscrição + estatísticas dos dados       │
└──────────────────────────────┬──────────────────────────┘
                               │ gspread (leitura/escrita)
                               ▼
                    ┌─────────────────────┐
                    │   Google Sheets     │
                    │  aba "dados"        │← proposições (main.py)
                    │  aba "emails"       │← lista de inscritos
                    └─────────┬───────────┘
                              │ gspread (leitura/escrita)
┌─────────────────────────────▼──────────────────────────┐
│  main.py (GitHub Actions — seg a sáb às 07h BRT)       │
│  1. Lê movimentações já existentes na planilha          │
│  2. Coleta Câmara + Senado                             │
│  3. Filtra apenas movimentações novas (deduplicação)   │
│  4. Se há novidades: grava em "dados" + envia email    │
│     Se não há novidades: encerra sem gravar nem emailar│
└────────────────────────────────────────────────────────┘
```

## Estrutura do Projeto

```
monitor-legislativo/
├── .github/
│   └── workflows/
│       └── monitor.yml      ← Agendamento GitHub Actions (diário, 07h BRT)
├── src/
│   ├── __init__.py
│   ├── config.py            ← Palavras-chave, URLs de API, colunas, env vars
│   ├── camara_api.py        ← Coleta paginada da Câmara (API v2 REST)
│   ├── senado_api.py        ← Coleta do Senado (API Dados Abertos)
│   ├── sheets.py            ← Leitura/escrita Google Sheets via gspread
│   └── email_report.py      ← Geração HTML + envio SMTP Gmail
├── app.py                   ← Interface Streamlit: formulário de inscrição + estatísticas
├── main.py                  ← Orquestrador: CLI → coleta → Sheets → email
├── requirements.txt         ← Dependências com versões fixadas
└── README.md                ← Este arquivo
```

## Dados coletados por proposição

| Campo | Descrição |
|---|---|
| `data_consulta` | Data/hora da coleta |
| `casa` | "Câmara" ou "Senado" |
| `id` | ID interno da proposição |
| `siglaTipo` | PL, PEC, PLP, MPV, etc. |
| `numero` | Número da proposição |
| `ano` | Ano de apresentação |
| `ementa` | Texto resumo da proposição |
| `dataApresentacao` | Data de apresentação |
| `statusSituacao` | Situação atual (tramitando, arquivada, etc.) |
| `statusOrgao` | Órgão onde está tramitando |
| `statusData` | Data da última situação |
| `keywords_encontradas` | Quais palavras-chave foram detectadas |
| `urlInteiroTeor` | Link para o texto completo |
| `autores` | Nome(s) do(s) autor(es) com partido/UF |
| `temas_api` | Temas oficiais da API |
| `tema_monitoramento` | Classificação pelo monitor |
| `indexacao_oficial` | Palavras-chave oficiais do Senado |
| `pagina_proposicao` | Link para a página da proposição |
| `uri` | URI da API |

---

# Guia Completo de Configuração

## Pré-requisitos

- Conta no **GitHub** (gratuita)
- Conta no **Google** (para Google Sheets, Service Account e Gmail)
- Conta no **Streamlit Community Cloud** (gratuita — para o formulário de inscrição)

---

## ETAPA 1 — Criar as planilhas no Google Sheets

### 1.1 Planilha de dados (onde os resultados são gravados)

1. Acesse [sheets.google.com](https://sheets.google.com) e crie uma nova planilha
2. Renomeie para: **Monitor Legislativo — Dados**
3. Renomeie a aba inferior para: **dados**
4. Deixe a planilha vazia — o script cria o cabeçalho automaticamente na primeira execução
5. Copie o **ID da planilha** que aparece na URL:
   ```
   https://docs.google.com/spreadsheets/d/ESTE_E_O_ID/edit
   ```
   Anote como `PLANILHA_DADOS_ID`

### 1.2 Planilha de emails (lista de destinatários e inscritos)

1. Crie outra planilha nova
2. Renomeie para: **Monitor Legislativo — Emails**
3. Renomeie a aba inferior para: **emails**
4. Na célula **A1**, escreva: `email` (cabeçalho)
5. A partir de **A2**, você pode inserir emails manualmente (ou deixar vazio — o formulário Streamlit preencherá):
   ```
   email
   redacao@jornal.com
   ```
6. Copie o ID desta planilha também — anote como `PLANILHA_EMAILS_ID`

> **Nota:** você pode usar a mesma planilha para dados e emails (abas diferentes) ou planilhas separadas. O projeto suporta ambos os casos.

---

## ETAPA 2 — Criar Service Account no Google Cloud

A Service Account permite que o script acesse as planilhas via API, sem interação humana. É gratuito.

### 2.1 Criar projeto no Google Cloud

1. Acesse [console.cloud.google.com](https://console.cloud.google.com/)
2. Clique em **Selecionar projeto** → **Novo Projeto**
3. Nome: `monitor-legislativo` → **Criar**
4. Aguarde a criação e selecione o projeto

### 2.2 Ativar as APIs necessárias

1. No menu lateral, vá em **APIs e serviços** → **Biblioteca**
2. Pesquise e ative:
   - **Google Sheets API** → **Ativar**
   - **Google Drive API** → **Ativar**

### 2.3 Criar a Service Account

1. Vá em **APIs e serviços** → **Credenciais**
2. Clique em **Criar credenciais** → **Conta de serviço**
3. Nome: `monitor-sheets` → **Criar e continuar** → **Continuar** → **Concluído**
4. Na lista de contas de serviço, clique na que acabou de criar
5. Aba **Chaves** → **Adicionar chave** → **Criar nova chave** → formato **JSON** → **Criar**
6. Um arquivo `.json` será baixado automaticamente. **Guarde-o com segurança — será usado em todas as próximas etapas.**

### 2.4 Compartilhar as planilhas com a Service Account

1. Abra o arquivo JSON baixado, localize o campo `client_email`. Será algo como:
   ```
   monitor-sheets@monitor-legislativo.iam.gserviceaccount.com
   ```
2. Abra a **Planilha de Dados** no Google Sheets → **Compartilhar** → cole o email da service account → permissão **Editor** → **Enviar**
3. Repita para a **Planilha de Emails** (permissão **Editor**, pois o `app.py` precisa escrever nela)

---

## ETAPA 3 — Criar App Password no Gmail

O Gmail não permite login com senha normal em aplicativos. A App Password é uma senha de 16 caracteres criada especificamente para acesso por scripts.

### 3.1 Verificação em duas etapas (pré-requisito)

1. Acesse [myaccount.google.com/security](https://myaccount.google.com/security)
2. Certifique-se de que **Verificação em duas etapas** está **Ativada**. Se não estiver, ative antes de continuar.

### 3.2 Gerar a App Password

1. Acesse [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. No campo **Nome do app**, digite: `Monitor Legislativo` → **Criar**
3. O Google exibirá uma senha de **16 caracteres** (ex: `abcd efgh ijkl mnop`)
4. **Copie esta senha imediatamente** — ela é exibida apenas uma vez
5. **Remova os espaços** ao usar. O valor final deve ser: `abcdefghijklmnop`
6. Anote como `GMAIL_APP_PASSWORD`

> Se precisar revogar o acesso, volte à mesma página e clique no ícone de lixeira ao lado do app.

---

## ETAPA 4 — Configurar o repositório no GitHub

### 4.1 Criar o repositório

1. Acesse [github.com/new](https://github.com/new)
2. Nome: `monitor-legislativo`
3. Visibilidade: **Private** (recomendado — protege os workflows que contêm secrets)
4. **Não** marque "Add a README file" (o projeto já tem um)
5. **Create repository**

### 4.2 Subir os arquivos

```bash
git clone https://github.com/SEU_USUARIO/monitor-legislativo.git
cd monitor-legislativo

# Copie todos os arquivos do projeto para esta pasta, mantendo a estrutura:
# .github/workflows/monitor.yml
# src/__init__.py, config.py, camara_api.py, senado_api.py, sheets.py, email_report.py
# app.py, main.py, requirements.txt, README.md

git add .
git commit -m "Adicionar monitor legislativo"
git push origin main
```

> **Atenção:** ao fazer o upload pela interface web do GitHub, pastas que começam com ponto (`.github/`) não podem ser criadas via "Upload files". Use o git na linha de comando, ou crie o arquivo do workflow manualmente como descrito abaixo.

### 4.2.1 — Criar o arquivo de agendamento (monitor.yml)

O arquivo `.github/workflows/monitor.yml` é o responsável por dizer ao GitHub **quando e como** executar o monitor automaticamente. Sem ele, nada roda.

**Localização obrigatória:** `.github/workflows/monitor.yml` — exatamente neste caminho, a partir da raiz do repositório.

**Como criar via interface web do GitHub** (sem usar git na linha de comando):

1. No repositório, clique em **Add file → Create new file**
2. No campo do nome do arquivo (onde aparece o ícone de pasta), digite:
   ```
   .github/workflows/monitor.yml
   ```
   O GitHub reconhece as barras e cria as pastas automaticamente. Você verá `.github/` e `workflows/` aparecerem como diretórios separados enquanto digita.
3. Na área de edição (abaixo), cole o conteúdo completo do arquivo:

```yaml
name: Monitor Legislativo

on:
  schedule:
    - cron: "0 10 * * 1-6"  # 10:00 UTC = 07:00 BRT — seg a sáb
  workflow_dispatch:         # execução manual pelo GitHub UI

jobs:
  monitorar:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Instalar dependências
        run: pip install -r requirements.txt

      - name: Executar monitor
        env:
          GMAIL_USER: ${{ secrets.GMAIL_USER }}
          GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
          GOOGLE_CREDENTIALS_JSON: ${{ secrets.GOOGLE_CREDENTIALS_JSON }}
          PLANILHA_DADOS_ID: ${{ secrets.PLANILHA_DADOS_ID }}
          PLANILHA_EMAILS_ID: ${{ secrets.PLANILHA_EMAILS_ID }}
          ABA_DADOS: ${{ vars.ABA_DADOS }}
          ABA_EMAILS: ${{ vars.ABA_EMAILS }}
        run: python main.py --dias 1
```

4. Role até o fim da página e clique em **Commit changes**
5. Na janela que aparecer, mantenha a opção **Commit directly to the `main` branch** selecionada
6. Clique em **Commit changes** para confirmar

O arquivo estará ativo imediatamente. O GitHub Actions passará a aparecer na aba **Actions** do repositório, e a primeira execução automática ocorrerá no horário configurado (padrão: 07h BRT).

> **Nota sobre o YAML:** o formato YAML é sensível a indentação. Se copiar e colar alterar os espaços, o workflow falhará com erro de sintaxe. Use sempre 2 espaços por nível de indentação — nunca tabs.

### 4.3 Configurar os Secrets (credenciais sensíveis)

1. No repositório, vá em **Settings** → **Secrets and variables** → **Actions**
2. Clique em **New repository secret** para cada um:

| Secret | Valor | Onde obter |
|---|---|---|
| `GMAIL_USER` | `seuemail@gmail.com` | Sua conta Gmail remetente |
| `GMAIL_APP_PASSWORD` | `abcdefghijklmnop` | Etapa 3.2 — 16 chars, sem espaços |
| `GOOGLE_CREDENTIALS_JSON` | `{"type":"service_account",...}` | **Todo o conteúdo** do arquivo JSON da Etapa 2.3 |
| `PLANILHA_DADOS_ID` | `1aBcDeFgH...` | ID da URL da planilha de dados (Etapa 1.1) |
| `PLANILHA_EMAILS_ID` | `1xYzAbCdE...` | ID da URL da planilha de emails (Etapa 1.2) |

**Como colar o `GOOGLE_CREDENTIALS_JSON`:** abra o arquivo `.json` da service account num editor de texto, selecione todo o conteúdo (Ctrl+A), copie (Ctrl+C) e cole no campo de valor do secret. O JSON inteiro vai em uma única string.

### 4.4 Configurar as Variáveis (valores não-sensíveis)

Ainda em **Settings → Secrets and variables → Actions**, clique na aba **Variables**:

| Variable | Valor padrão | Descrição |
|---|---|---|
| `ABA_DADOS` | `dados` | Nome da aba na planilha de dados |
| `ABA_EMAILS` | `emails` | Nome da aba na planilha de emails |

> Se suas abas já se chamam `dados` e `emails`, você pode pular este passo — esses são os valores padrão do código.

---

## ETAPA 5 — Testar o GitHub Actions

### 5.1 Disparo manual (primeiro teste)

1. No repositório, vá em **Actions** → clique em **Monitor Legislativo** na barra lateral
2. Clique em **Run workflow** → **Run workflow**
3. Clique no workflow em execução para acompanhar os logs em tempo real

### 5.2 O que verificar nos logs

Procure por estas linhas nos logs da execução:

```
=== CÂMARA: Coleta de AAAA-MM-DD a AAAA-MM-DD ===
Câmara — total de páginas: N
=== CÂMARA: X proposições encontradas ===
=== SENADO: Y matérias encontradas ===
Sheets — Z movimentações existentes lidas para deduplicação
Novidades: N (Câmara=X, Senado=Y) | Repetidos/sem novidade: M
Sheets: N linhas inseridas
Email — enviado com sucesso para N destinatário(s) via Gmail SMTP
```

Se não houver novidades, o log termina com:

```
SEM NOVIDADES — todas as movimentações já estavam na planilha.
Nenhuma linha será gravada e nenhum email será enviado.
```

### 5.3 Verificar resultados

- **Planilha de dados:** abra e verifique se novas linhas apareceram com as colunas preenchidas
- **Email:** verifique a caixa de entrada dos destinatários cadastrados (verifique também a pasta **Spam** — na primeira vez pode cair lá)

### 5.4 Resolução de problemas comuns

| Mensagem no log | Causa provável | Solução |
|---|---|---|
| `GMAIL_APP_PASSWORD não configurada` | Secret não criado | Criar o secret `GMAIL_APP_PASSWORD` nas configurações do repositório |
| `Falha de autenticação Gmail` | App Password incorreta ou revogada | Gerar nova App Password na Etapa 3.2 |
| `GOOGLE_CREDENTIALS_JSON não configurado` | Secret não criado ou vazio | Verificar se o JSON inteiro foi colado no secret |
| `Erro ao acessar planilha de dados` | Planilha não compartilhada | Compartilhar a planilha com o email da service account (Editor) |
| `Email — nenhum destinatário` | Planilha de emails vazia | Adicionar pelo menos um email a partir da linha A2, ou usar o formulário Streamlit |
| `403 Forbidden` (API Câmara) | Rate limiting temporário | Normal — a próxima execução resolve automaticamente |
| `0 proposições encontradas` | Nenhuma proposição com as palavras-chave no período | Normal para dias sem atividade legislativa relevante |
| `SEM NOVIDADES` | Todas as proposições encontradas já estavam na planilha com o mesmo status | Comportamento esperado — nenhum dado novo foi detectado |
| Email cai no Spam | Primeiro envio de remetente novo | Destinatário deve clicar em "Não é spam" |

### 5.5 Execução automática

O workflow está configurado para rodar **de segunda a sábado às 10:00 UTC (07:00 de Brasília)**. Para alterar, edite [.github/workflows/monitor.yml](.github/workflows/monitor.yml):

```yaml
schedule:
  - cron: '0 10 * * 1-6'  # 10:00 UTC = 07:00 BRT — seg a sáb
```

Outros exemplos de cron:

| Cron | Horário BRT |
|---|---|
| `0 10 * * *` | 07:00 BRT, todos os dias |
| `0 12 * * *` | 09:00 BRT, todos os dias |
| `0 10 * * 1-5` | 07:00 BRT, apenas dias úteis (seg–sex) |
| `0 10 * * 1-6` | 07:00 BRT, seg a sáb (configuração atual) |

> O cron do GitHub Actions pode ter atraso de 5 a 30 minutos em relação ao horário programado — isso é normal.

---

## ETAPA 6 — Deploy do formulário de inscrição (Streamlit Cloud)

O `app.py` é uma interface web onde qualquer pessoa pode se inscrever para receber o relatório diário. Ela salva o email direto na aba `emails` da planilha do Google Sheets.

### 6.1 Criar conta no Streamlit Community Cloud

1. Acesse [share.streamlit.io](https://share.streamlit.io)
2. Clique em **Sign up** e autentique com sua conta do **GitHub**
3. Autorize o Streamlit a acessar seus repositórios quando solicitado

### 6.2 Criar o deploy

1. No Streamlit Cloud, clique em **New app**
2. Preencha os campos:
   - **Repository:** `SEU_USUARIO/monitor-legislativo`
   - **Branch:** `main`
   - **Main file path:** `app.py`
3. Clique em **Advanced settings** (importante — as credenciais ficam aqui)

### 6.3 Configurar as variáveis de ambiente no Streamlit Cloud

Em **Advanced settings → Secrets**, cole o seguinte bloco e substitua os valores pelos seus:

```toml
GOOGLE_CREDENTIALS_JSON = '{"type":"service_account","project_id":"...","private_key_id":"...","private_key":"-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n","client_email":"monitor-sheets@...iam.gserviceaccount.com","client_id":"...","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_x509_cert_url":"..."}'

PLANILHA_EMAILS_ID = "1xYzAbCdE..."

ABA_EMAILS = "emails"
```

> **Formato importante:** o `GOOGLE_CREDENTIALS_JSON` deve estar em uma única linha, com o JSON inteiro entre aspas simples. Copie o conteúdo do arquivo `.json` e cole-o respeitando esse formato. O Streamlit Cloud usa o formato TOML para secrets.

### 6.4 Finalizar o deploy

1. Clique em **Deploy!**
2. Aguarde o build (1–3 minutos na primeira vez)
3. O Streamlit gerará uma URL pública no formato: `https://seu-usuario-monitor-legislativo-app-XXXX.streamlit.app`
4. Acesse a URL e teste o formulário: insira um email válido e clique em **Inscrever-se**
5. Verifique se o email apareceu na aba `emails` da planilha do Google Sheets

### 6.5 Comportamento do formulário e cancelamento

- **Inscrição nova:** exibe mensagem verde de sucesso e salva o email na planilha
- **Email duplicado:** exibe aviso amarelo informando que já está cadastrado (verificação case-insensitive)
- **Email inválido:** exibe erro vermelho pedindo email válido
- A autenticação com o Google Sheets ocorre uma única vez por processo (cache via `@st.cache_resource`)

**Cancelamento de assinatura:** cada email recebido contém um link personalizado de cancelamento no rodapé. Ao clicar, o leitor é levado para a URL:

```
https://congreapp-monitor-jornalismo.streamlit.app/?action=unsubscribe&email=SEU_EMAIL
```

O app detecta os parâmetros, remove o email da planilha automaticamente (uma única vez por sessão, via `st.session_state`) e exibe confirmação. O cancelamento também pode ser feito manualmente pela mesma página, sem precisar de um link pré-preenchido.

### 6.6 Atualizar o deploy

Toda vez que você fizer `git push` para a branch `main`, o Streamlit Cloud atualiza o deploy automaticamente.

---

## Execução Local (desenvolvimento)

Para rodar na sua máquina sem GitHub Actions:

```bash
# Instalar dependências
pip install -r requirements.txt

# Exportar variáveis de ambiente
export GMAIL_USER="seuemail@gmail.com"
export GMAIL_APP_PASSWORD="abcdefghijklmnop"
export GOOGLE_CREDENTIALS_JSON='{"type":"service_account",...}'
export PLANILHA_DADOS_ID="1aBcDeFgH..."
export PLANILHA_EMAILS_ID="1xYzAbCdE..."

# Executar o monitor (coleta + Sheets + email)
python main.py --dias 3

# Apenas coletar e gravar no Sheets (sem enviar email)
python main.py --dias 3 --sem-email

# Apenas coletar (sem Sheets, sem email — útil para debug)
python main.py --dias 3 --sem-sheets --sem-email

# Especificar intervalo de datas manualmente
python main.py --data-inicio 2026-02-01 --data-fim 2026-02-10

# Rodar o formulário Streamlit localmente
streamlit run app.py
```

---

## Variáveis de Ambiente — Referência Completa

| Variável | Onde configurar | Obrigatória | Descrição |
|---|---|---|---|
| `GMAIL_USER` | GitHub Secrets, `.env` local | Sim | Email Gmail remetente |
| `GMAIL_APP_PASSWORD` | GitHub Secrets, `.env` local | Sim | App Password de 16 chars (sem espaços) |
| `GOOGLE_CREDENTIALS_JSON` | GitHub Secrets, Streamlit Secrets, `.env` local | Sim | JSON completo da Service Account GCP |
| `PLANILHA_DADOS_ID` | GitHub Secrets, `.env` local | Sim | ID da planilha de dados (fragmento alfanumérico da URL) |
| `PLANILHA_EMAILS_ID` | GitHub Secrets, Streamlit Secrets, `.env` local | Sim | ID da planilha de emails |
| `ABA_DADOS` | GitHub Variables, `.env` local | Não | Nome da aba de dados (padrão: `dados`) |
| `ABA_EMAILS` | GitHub Variables, Streamlit Secrets, `.env` local | Não | Nome da aba de emails (padrão: `emails`) |

---

## Melhorias em relação ao projeto original (Abraji)

1. **Bug de operador lógico corrigido** — `'ongs' or 'imprensa' in texto` sempre avaliava como `True` em Python. Corrigido com regex `|`.
2. **Paginação robusta** — usa `urllib.parse` em vez de slicing de string na URL do header `Link`
3. **Endpoint SOAP substituído** — `/SitCamaraWS/Proposicoes.asmx` (legado) substituído por `/api/v2/proposicoes/{id}/autores` (REST v2)
4. **Retry com backoff exponencial** — resiliência automática a erros 429/5xx (2s → 4s → 8s)
5. **Delay entre requisições** — evita bloqueio por rate limiting
6. **Logging estruturado** — substitui `print()` por módulo `logging`
7. **Coleta de temas oficiais** — endpoint `/proposicoes/{id}/temas` da Câmara
8. **Senado Federal incluído** — novo módulo usando API Dados Abertos com busca em ementa + indexação oficial
9. **GitHub Actions** — sem dependência de Heroku (gratuito, sem servidor)
10. **Gmail SMTP** — envio direto via App Password, sem serviços pagos (SendGrid, Mailgun)
11. **Formulário de inscrição + cancelamento** — `app.py` (Streamlit) para cadastro e remoção de destinatários; link de cancelamento personalizado em cada email (`?action=unsubscribe&email=...`)
12. **Deduplicação inteligente** — lê as movimentações já existentes antes de gravar; só registra e emaila quando há `statusSituacao`, `statusOrgao` ou `statusData` realmente novos, evitando ruído desnecessário
13. **Estatísticas no app** — `app.py` exibe total de proposições únicas, split Câmara/Senado, período e contagem por tema, com cache de 1 hora
14. **Palavras-chave ampliadas** — de 13 para 16 termos, com adição de `MÍDIA`, `COMUNICAÇÃO SOCIAL` e `LIBERDADE DE IMPRENSA` para melhor cobertura da API do Senado
15. **Senado: dupla fonte de dados** — pipeline agora combina `/materia/atualizadas` (movimentações recentes) com `/materia/pesquisa/lista` (todas as matérias do ano), deduplicando por `CodigoMateria`; janela de busca mínima ampliada de 3 para 7 dias
16. **Email individualizado** — relatório é enviado separadamente para cada destinatário (uma conexão SMTP, N envios), permitindo links de cancelamento personalizados por email
17. **Agendamento seg–sáb** — GitHub Actions configurado para `1-6` (segunda a sábado), cobrindo sábados quando há sessões extraordinárias

## Fontes de Dados

- **Câmara dos Deputados:** [dadosabertos.camara.leg.br/api/v2](https://dadosabertos.camara.leg.br/swagger/api.html)
- **Senado Federal:** [legis.senado.leg.br/dadosabertos](https://legis.senado.leg.br/dadosabertos/docs/)

## Licença

Projeto independente de uso livre. Os dados legislativos são públicos.

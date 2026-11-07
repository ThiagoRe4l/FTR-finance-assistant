# 🪙 Assistente Financeiro com CrewAI — B3 / Ibovespa

Projeto de estudo de **agentes de IA com [CrewAI](https://www.crewai.com/)** aplicado ao mercado financeiro.
Os agentes consultam **dados reais de mercado** (via [`yfinance`](https://github.com/ranaroussi/yfinance)) e usam um LLM
hospedado no **[Groq](https://console.groq.com/)** (plano gratuito) para interpretar os números e responder em português.

O projeto tem duas formas de uso:

1. **Notebook de relatório** (`assistente_financas_ibovespa.ipynb`): dois agentes trabalham em sequência e geram um
   relatório de mercado em Markdown (`relatorio_ibovespa.md`).
2. **Chatbot Streamlit** (`streamlit_app.py`): uma interface de conversa em que você pergunta em linguagem natural
   ("Como está a PETR4 hoje?", "Compare VALE3 e ITUB4") e o agente busca os dados e responde.

> ⚠️ **Aviso:** todo o conteúdo gerado é **apenas informativo** e **não constitui recomendação de investimento**.
> As cotações do Yahoo Finance têm atraso de aproximadamente 15 minutos.

---

## 📁 Estrutura do projeto

| Arquivo | Descrição |
|---|---|
| `assistente_financas_ibovespa.ipynb` | Notebook didático com a crew de dois agentes (Analista de Mercado + Consultor Financeiro) que gera o relatório. |
| `streamlit_app.py` | Chatbot web que responde perguntas sobre qualquer ativo (B3, bolsas internacionais, índices e cripto). |
| `testes_yfinance.ipynb` | Laboratório para explorar o `yfinance` sozinho, sem CrewAI (histórico, `fast_info`, `.info`, intradiário, armadilhas comuns). |
| `relatorio_ibovespa.md` | Exemplo de relatório gerado pelo notebook. |
| `requirements.txt` | Dependências do projeto. |
| `.env` | Guarda a `GROQ_API_KEY` localmente (**não versione este arquivo**). |

---

## 🧠 Como funciona

### Notebook — crew de dois agentes

```
Usuário define os tickers
        │
        ▼
┌──────────────────────┐     usa a tool      ┌──────────────────────┐
│  Analista de Mercado │ ──────────────────▶ │  Consulta de Ativos  │
│   (coleta os dados)  │ ◀────────────────── │      da B3 (tool)    │
└──────────────────────┘  cotação/variação   └──────────────────────┘
        │
        │ context (passa os dados adiante)
        ▼
┌──────────────────────┐
│ Consultor Financeiro │  ──▶  relatório em Markdown (relatorio_ibovespa.md)
│  (analisa e escreve) │
└──────────────────────┘
```

- **Analista de Mercado**: único agente com acesso à ferramenta; coleta cotação, variação diária e volume.
- **Consultor Financeiro**: recebe os dados via `context` e escreve o relatório com tabela-resumo, maiores alta e baixa,
  observações sobre volume e o aviso de que não é recomendação.
- As tasks rodam com `Process.sequential` e o resultado final é salvo com `output_file`.

### Chatbot Streamlit — um agente consultor

- Um único **Consultor Financeiro** com a tool `ConsultaAtivos`, que aceita ativos de **qualquer bolsa**:
  - Ações da B3 com ou sem `.SA` (`PETR4`, `VALE3.SA`)
  - Ações internacionais (`AAPL`, `MSFT`, `AIR.PA`)
  - Índices (`^BVSP`, `^GSPC`)
  - Criptomoedas (`BTC-USD`)
- Para um ticker "puro" (ex.: `PETR4`), a tool tenta primeiro o símbolo como veio e, se não houver dados, tenta com `.SA`.
- As últimas 6 mensagens da conversa são enviadas como contexto, dando ao agente uma "memória" curta.
- O agente é criado uma única vez por sessão (`@st.cache_resource`).

### Conceitos de CrewAI abordados

- **Tool customizada** (`BaseTool` + schema de entrada com Pydantic)
- **Agent** (`role`, `goal`, `backstory`)
- **Task** (`description`, `expected_output`, `context`, `output_file`)
- **Crew** com `Process.sequential`
- **LLM** via LiteLLM com o prefixo `groq/`

---

## ✅ Pré-requisitos

- **Python 3.10+** (testado com 3.12)
- Uma **chave de API do Groq** gratuita: crie em <https://console.groq.com/keys>

---

## ⚙️ Instalação

```bash
# 1. (Opcional, recomendado) crie e ative um ambiente virtual
python -m venv .venv
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# Linux / macOS
source .venv/bin/activate

# 2. Instale as dependências
pip install -r requirements.txt
```

---

## 🔑 Configurando a chave do Groq

Escolha uma das opções:

- **Variável de ambiente** (vale para o notebook e o Streamlit):
  ```powershell
  # Windows (PowerShell)
  $env:GROQ_API_KEY = "gsk_..."
  ```
  ```bash
  # Linux / macOS
  export GROQ_API_KEY="gsk_..."
  ```
- **Notebook**: se a variável não existir, o notebook pede a chave com `getpass` (sem exibi-la na tela).
- **Streamlit**: informe a chave na barra lateral do app **ou** crie o arquivo `.streamlit/secrets.toml`:
  ```toml
  GROQ_API_KEY = "gsk_..."
  ```

> 💡 O arquivo `.env` **não é carregado automaticamente** pelo código. Se quiser usá-lo, carregue-o com
> [`python-dotenv`](https://pypi.org/project/python-dotenv/) ou exporte a variável no terminal.
> Nunca faça commit de chaves de API.

---

## ▶️ Como usar

### 1. Gerar o relatório (notebook)

1. Abra `assistente_financas_ibovespa.ipynb` no Jupyter ou VS Code.
2. Execute as células em ordem.
3. Para mudar os ativos analisados, edite a variável:
   ```python
   ATIVOS = "PETR4, VALE3, ITUB4, BBDC4, ABEV3"
   ```
4. O relatório é exibido na saída e salvo em `relatorio_ibovespa.md`.

> No Jupyter já existe um event loop rodando, por isso o notebook usa `await crew.kickoff_async()`.
> Em scripts `.py` comuns use `crew.kickoff()`.

### 2. Conversar com o chatbot (Streamlit)

```bash
streamlit run streamlit_app.py
```

O app abre em <http://localhost:8501>. Informe a `GROQ_API_KEY` na barra lateral (se ainda não estiver configurada) e
pergunte, por exemplo:

- *Como está a PETR4 hoje?*
- *Compare VALE3, ITUB4 e BBDC4*
- *E o Ibovespa (^BVSP), como fechou?*
- *Cotação da AAPL e da MSFT*
- *Como está o S&P 500 (^GSPC)?*
- *Preço do Bitcoin (BTC-USD)*

Use o botão **Limpar conversa** na barra lateral para reiniciar o histórico.

### 3. Explorar o yfinance (opcional)

Abra `testes_yfinance.ipynb` para entender a fonte de dados: histórico de preços, `fast_info`, dados fundamentalistas
com `.info`, candles intradiários, `yf.download()` com vários ativos e o cálculo da variação diária usado pela tool.

---

## 📄 Exemplo de saída

```markdown
| Ativo | Preço (R$) | Variação | Volume |
|-------|------------|----------|--------|
| PETR4 | 45,36 | -1,28 % | 47 069 700 |
| VALE3 | 64,04 | +2,19 % | 19 016 100 |
| BBDC4 | 14,20 | +3,12 % | 45 442 800 |

## Destaques do Dia
- Maior alta: BBDC4 (+3,12 %)
- Maior baixa: PETR4 (-1,28 %)
```

Veja o relatório completo em [`relatorio_ibovespa.md`](relatorio_ibovespa.md).

---

## 🛠️ Solução de problemas

| Problema | Causa / solução |
|---|---|
| `BadRequestError: property 'cache_breakpoint' is unsupported` | O CrewAI ≥ 1.15 adiciona um marcador de prompt caching que o Groq rejeita. O código já aplica uma correção que neutraliza esse marcador; mantenha-a ao modificar o projeto. |
| `RuntimeError` ao rodar `crew.kickoff()` no Jupyter | Use `await crew.kickoff_async()` no notebook. |
| `dados não encontrados` para um ticker | Ticker incorreto, ativo sem pregão no período ou instabilidade do Yahoo. Confira o símbolo no [Yahoo Finance](https://finance.yahoo.com/). |
| Erros de limite de requisições | Muitas chamadas seguidas ao Yahoo ou ao Groq (free tier). Aguarde alguns instantes e consulte vários tickers em uma única pergunta. |
| "Informe sua GROQ_API_KEY na barra lateral primeiro." | Configure a chave conforme a seção [Configurando a chave do Groq](#-configurando-a-chave-do-groq). |

---

## 🚀 Próximos passos

- Trocar ou complementar a fonte de dados com a [brapi.dev](https://brapi.dev/) para dados fundamentalistas (P/L, dividend yield).
- Adicionar um terceiro agente de **gestão de risco** comentando a volatilidade.
- Estruturar a saída com `output_pydantic` em vez de texto livre.
- Exibir gráficos de preço no chatbot.

---

## 🧰 Tecnologias

- [CrewAI](https://docs.crewai.com/) — orquestração de agentes
- [LiteLLM](https://docs.litellm.ai/) + [Groq](https://groq.com/) — acesso ao LLM (`groq/openai/gpt-oss-20b`)
- [yfinance](https://github.com/ranaroussi/yfinance) — dados de mercado
- [Streamlit](https://streamlit.io/) — interface de chat
- [Pydantic](https://docs.pydantic.dev/) — schema de entrada das tools

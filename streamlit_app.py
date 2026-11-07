"""
Assistente Financeiro — Chatbot Streamlit (B3 / Ibovespa)
=========================================================

Evolução do projeto de agentes para uma interface de conversa. O usuário digita
perguntas em linguagem natural ("Como está a PETR4 hoje?", "Compare VALE3 e ITUB4")
e o agente consultor busca os dados reais e responde no chat.

Como rodar:
    pip install crewai yfinance streamlit
    streamlit run streamlit_app.py

A chave do Groq pode ser informada na barra lateral OU em .streamlit/secrets.toml:
    GROQ_API_KEY = "gsk_..."

Diferença importante em relação ao notebook:
    No Jupyter usamos `await crew.kickoff_async()` por causa do event loop já ativo.
    No Streamlit (script comum) usamos `crew.kickoff()` normal — sem async.

Observação: conteúdo informativo, não é recomendação de investimento.
"""

import os
from typing import Type

import streamlit as st
import yfinance as yf
from pydantic import BaseModel, Field
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import BaseTool

# ---------------------------------------------------------------------------
# Correção de compatibilidade Groq (crewai >= 1.15)
# O crewai marca as mensagens com a chave 'cache_breakpoint' (prompt caching
# estilo Anthropic). A API do Groq não aceita esse campo e retorna
# BadRequestError. Como o caminho do Groq usa o LiteLLM genérico e o crewai
# não remove a chave, neutralizamos o marcador antes de qualquer chamada.
import crewai.llms.cache as _crewai_cache
_crewai_cache.mark_cache_breakpoint = lambda message: message


# ---------------------------------------------------------------------------
# 1. Tool customizada — consulta qualquer ativo, em qualquer bolsa
# ---------------------------------------------------------------------------
# Símbolo de moeda para exibição, a partir do código ISO devolvido pelo Yahoo.
_SIMBOLO_MOEDA = {"BRL": "R$", "USD": "US$", "EUR": "€", "GBP": "£", "JPY": "¥"}


def _candidatos_yf(symbol: str) -> list[str]:
    """Gera os símbolos do Yahoo Finance a testar para o que o usuário digitou.

    - Índices (^BVSP, ^GSPC) e símbolos que já trazem mercado/sufixo
      (PETR4.SA, BTC-USD, BRK-B) são usados como vieram.
    - Um ticker "puro" é ambíguo: pode ser global (AAPL) ou da B3 (PETR4).
      Tentamos primeiro como veio e, se não houver dados, com o sufixo .SA.
    """
    s = symbol.strip().upper()
    if not s:
        return []
    if s.startswith("^") or "." in s or "-" in s:
        return [s]
    return [s, f"{s}.SA"]


class ConsultaAtivosInput(BaseModel):
    tickers: str = Field(
        ...,
        description=(
            "Um ou mais tickers separados por vírgula, de QUALQUER bolsa. "
            "Ações da B3 podem vir sem o .SA (ex.: 'PETR4,VALE3'); ações dos EUA "
            "pelo símbolo (ex.: 'AAPL,MSFT'); índices com ^ (ex.: '^BVSP,^GSPC'); "
            "cripto no formato par (ex.: 'BTC-USD'). Você também pode passar o "
            "símbolo completo do Yahoo Finance (ex.: 'PETR4.SA', 'AIR.PA')."
        ),
    )


class ConsultaAtivos(BaseTool):
    name: str = "Consulta de Ativos da Bolsa"
    description: str = (
        "Busca cotação atual, variação diária (%) e volume de qualquer ativo "
        "negociado em bolsa: ações brasileiras (B3), ações internacionais, "
        "índices, ETFs e criptomoedas. Use sempre que a pergunta envolver a "
        "cotação ou o desempenho de um ou mais ativos."
    )
    args_schema: Type[BaseModel] = ConsultaAtivosInput

    def _run(self, tickers: str) -> str:
        linhas = []
        for bruto in tickers.split(","):
            entrada = bruto.strip().upper()
            if not entrada:
                continue
            try:
                hist = None
                yf_symbol = None
                for candidato in _candidatos_yf(entrada):
                    ativo = yf.Ticker(candidato)
                    h = ativo.history(period="5d")
                    if not h.empty:
                        hist, yf_symbol = h, candidato
                        break

                if hist is None:
                    linhas.append(f"{entrada}: dados não encontrados")
                    continue

                # Moeda do ativo (BRL, USD, ...) para exibir o símbolo correto.
                try:
                    moeda = ativo.fast_info.get("currency") or ""
                except Exception:
                    moeda = ""
                cifrao = _SIMBOLO_MOEDA.get(moeda, f"{moeda} " if moeda else "")

                fech = hist["Close"].iloc[-1]
                ant = hist["Close"].iloc[-2] if len(hist) >= 2 else fech
                var = (fech - ant) / ant * 100
                vol = f"{int(hist['Volume'].iloc[-1]):,}".replace(",", ".")
                # Mostra qual símbolo do Yahoo foi usado quando difere do digitado.
                rotulo = entrada if yf_symbol == entrada else f"{entrada} ({yf_symbol})"
                linhas.append(
                    f"{rotulo}: {cifrao}{fech:.2f} | variação {var:+.2f}% | volume {vol}"
                )
            except Exception as e:
                linhas.append(f"{entrada}: erro ({e})")
        return "\n".join(linhas) if linhas else "Nenhum ticker válido informado."


# ---------------------------------------------------------------------------
# 2. Construção do agente
#    @st.cache_resource garante que o agente seja criado UMA vez por sessão,
#    e não a cada mensagem (economiza tempo e memória).
# ---------------------------------------------------------------------------
@st.cache_resource
def construir_agente():
    llm = LLM(model="groq/openai/gpt-oss-20b", temperature=0.3)
    return Agent(
        role="Consultor Financeiro",
        goal="Responder perguntas sobre ativos de qualquer bolsa usando dados reais de mercado.",
        backstory=(
            "Você é um consultor que explica o mercado de ações em linguagem clara, "
            "tanto da bolsa brasileira (B3) quanto de bolsas internacionais, índices e "
            "criptomoedas. SEMPRE busca os dados com a ferramenta antes de responder "
            "sobre um ativo e NUNCA dá recomendação personalizada de compra ou venda — "
            "apenas apresenta dados e contexto. Encerre toda resposta com a frase: "
            "'Isto não é recomendação de investimento.'"
        ),
        tools=[ConsultaAtivos()],
        llm=llm,
        verbose=False,
    )


# ---------------------------------------------------------------------------
# 3. Função que roda a crew para uma pergunta
#    Montamos a task dinamicamente com a pergunta do usuário + um resumo do
#    histórico, para o agente ter alguma "memória" da conversa.
# ---------------------------------------------------------------------------
def responder(pergunta: str, historico: str) -> str:
    agente = construir_agente()
    task = Task(
        description=(
            f"Histórico recente da conversa:\n{historico}\n\n"
            f"Pergunta atual do usuário: {pergunta}\n\n"
            "Se a pergunta envolver ativos específicos, use a ferramenta para obter os "
            "dados antes de responder. Responda em português, de forma direta e útil."
        ),
        expected_output="Uma resposta clara à pergunta, baseada em dados quando aplicável.",
        agent=agente,
    )
    crew = Crew(agents=[agente], tasks=[task], process=Process.sequential, verbose=False)
    # Streamlit é síncrono: kickoff() normal (sem async, diferente do Jupyter).
    return str(crew.kickoff())


# ---------------------------------------------------------------------------
# 4. Interface
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Assistente Financeiro", page_icon="🪙")
st.title("🪙 Assistente Financeiro — Ações, Índices e Cripto")
st.caption(
    "Consulte qualquer ativo (B3, bolsas internacionais, índices e cripto). "
    "Dados via yfinance (atraso ~15 min). Conteúdo informativo, "
    "não é recomendação de investimento."
)

# --- Barra lateral: chave de API e exemplos ---
with st.sidebar:
    st.header("Configuração")

    # Tenta ler a chave de secrets.toml; se não houver, deixa em branco.
    default_key = ""
    try:
        default_key = st.secrets.get("GROQ_API_KEY", "")
    except Exception:
        default_key = ""

    chave = st.text_input("GROQ_API_KEY", value=default_key, type="password")
    if chave:
        os.environ["GROQ_API_KEY"] = chave

    st.markdown(
        "**Exemplos de pergunta:**\n\n"
        "- Como está a PETR4 hoje?\n"
        "- Compare VALE3, ITUB4 e BBDC4\n"
        "- E o Ibovespa (^BVSP), como fechou?\n"
        "- Cotação da AAPL e da MSFT\n"
        "- Como está o S&P 500 (^GSPC)?\n"
        "- Preço do Bitcoin (BTC-USD)"
    )
    if st.button("Limpar conversa"):
        st.session_state.messages = []
        st.rerun()

# --- Estado da conversa ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# Renderiza o histórico
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- Entrada do usuário ---
if pergunta := st.chat_input("Pergunte sobre qualquer ativo (ações, índices, cripto)..."):
    if not os.environ.get("GROQ_API_KEY"):
        st.warning("Informe sua GROQ_API_KEY na barra lateral primeiro.")
        st.stop()

    # Mostra e guarda a mensagem do usuário
    st.session_state.messages.append({"role": "user", "content": pergunta})
    with st.chat_message("user"):
        st.markdown(pergunta)

    # Gera e mostra a resposta do agente
    with st.chat_message("assistant"):
        with st.spinner("Consultando o mercado..."):
            historico = "\n".join(
                f"{m['role']}: {m['content']}" for m in st.session_state.messages[-6:]
            )
            try:
                resposta = responder(pergunta, historico)
            except Exception as e:
                resposta = f"Ocorreu um erro ao processar sua pergunta: {e}"
            st.markdown(resposta)

    st.session_state.messages.append({"role": "assistant", "content": resposta})

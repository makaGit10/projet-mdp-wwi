"""
Application de demonstration : interroger la couche GOLD de Snowflake en langage naturel.

Lancement :  streamlit run app/streamlit_app.py
"""
import os
import sys
import threading
from pathlib import Path

import pandas as pd
import plotly.express as px
import snowflake.connector
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.text_to_sql import MODELS, ask, build_system_prompt, load_gold_schema, run_query, warm_up  # noqa: E402
from common.config import env, snowflake_connect_args  # noqa: E402

ACCENT = "#2a78d6"
TIME_HINTS = ("mois", "month", "date", "annee", "year", "periode", "trimestre", "quarter", "semaine", "jour")
EXAMPLES = [
    "Quels sont les dix meilleurs clients par chiffre d'affaires ?",
    "Quel est le montant total des ventes par mois ?",
    "Quels produits generent le plus de benefices ?",
    "Quel est le chiffre d'affaires par territoire commercial en 2015 ?",
    "Quel commercial a realise le plus gros chiffre d'affaires ?",
    "Quels articles sont sous leur seuil de reapprovisionnement ?",
]

st.set_page_config(page_title="WWI - Assistant de donnees", page_icon="❄️", layout="wide")

# En ligne (Streamlit Cloud), les parametres sont fournis par les secrets de l'application, pas par .env
try:
    for _key, _value in st.secrets.items():
        os.environ.setdefault(_key, str(_value))
except Exception:
    pass  # execution locale sans secrets.toml : le fichier .env suffit

# Le modele local (Ollama) n'existe pas sur un serveur en ligne : il n'est propose qu'en local
ONLINE = os.getenv("DEPLOY_MODE") == "cloud"
AVAILABLE_MODELS = [m for m in MODELS if not (ONLINE and m.startswith("ollama:"))]


# ------------------------------------------------------------------ CONNEXIONS
@st.cache_resource(show_spinner="Connexion a Snowflake...")
def get_connection(role: str):
    conn = snowflake.connector.connect(
        **snowflake_connect_args(role=role),
        client_session_keep_alive=True,
        session_parameters={"QUERY_TAG": "wwi_streamlit", "STATEMENT_TIMEOUT_IN_SECONDS": 120},
    )
    # Sans cela, Snowflake active aussi les autres roles de l'utilisateur (roles secondaires)
    # et le role lecteur pourrait lire BRONZE / SILVER
    conn.cursor().execute("use secondary roles none")
    return conn


@st.cache_data(ttl=3600, show_spinner=False)
def get_schema() -> str:
    return load_gold_schema(reader(), DATABASE)


@st.cache_data(ttl=600, show_spinner=False)
def query(sql: str, role: str = "reader") -> pd.DataFrame:
    return run_query(reader() if role == "reader" else admin(), sql)


def reader():
    # Role en lecture seule sur GOLD : c'est lui qui execute le SQL genere par l'IA
    return get_connection(env("SNOWFLAKE_READER_ROLE", "WWI_READER"))


def admin():
    # Role technique, utilise uniquement pour l'onglet "Plateforme" (requetes fixes)
    return get_connection(env("SNOWFLAKE_ROLE"))


try:
    DATABASE = env("SNOWFLAKE_DATABASE")
    reader()
except Exception as err:
    st.error(f"Connexion a Snowflake impossible : {err}")
    st.info("Verifiez le fichier `.env` (SNOWFLAKE_ACCOUNT...) et l'execution de `snowflake/setup.sql`.")
    st.stop()


@st.cache_resource(show_spinner=False)
def preheat(model_id: str):
    """Charge le modele local en arriere-plan des l'ouverture de l'application."""
    thread = threading.Thread(target=warm_up, args=(model_id, build_system_prompt(get_schema(), DATABASE)), daemon=True)
    thread.start()
    return thread


# ------------------------------------------------------------------ GRAPHIQUES
def _style(fig):
    fig.update_layout(margin=dict(l=10, r=10, t=30, b=10), hovermode="closest", showlegend=False)
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.15)")
    return fig


def auto_chart(df: pd.DataFrame, key: str) -> None:
    """Choisit une visualisation adaptee a la forme du resultat."""
    if df is None or df.empty:
        return
    numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and not c.endswith(("_id", "_key"))]
    others = [c for c in df.columns if c not in numeric]

    # Une seule valeur : chiffre cle
    if len(df) == 1 and numeric and len(df.columns) <= 4:
        cols = st.columns(len(numeric))
        for col, name in zip(cols, numeric):
            col.metric(name.replace("_", " ").capitalize(), f"{df[name].iloc[0]:,.2f}".replace(",", " "))
        return
    if not numeric or not others:
        return

    measure = numeric[0]
    if len(numeric) > 1:
        measure = st.selectbox("Mesure a afficher", numeric, key=f"m_{key}")
    dim = others[0]

    if any(h in dim.lower() for h in TIME_HINTS) or pd.api.types.is_datetime64_any_dtype(df[dim]):
        data = df.sort_values(dim)
        fig = px.line(data, x=dim, y=measure, markers=len(data) <= 24)
        fig.update_traces(line=dict(color=ACCENT, width=2), marker=dict(size=8))
        st.plotly_chart(_style(fig), width="stretch", key=f"c_{key}")
    elif len(df) <= 50:
        data = df.sort_values(measure, ascending=True)
        fig = px.bar(data, x=measure, y=dim, orientation="h")
        fig.update_traces(marker_color=ACCENT, marker_cornerradius=4)
        fig.update_layout(height=max(280, 28 * len(data)))
        st.plotly_chart(_style(fig), width="stretch", key=f"c_{key}")


def show_result(res, key: str) -> None:
    # Question hors perimetre : le modele renvoie une seule colonne "message"
    if res.data is not None and list(res.data.columns) == ["message"]:
        st.info(res.data["message"].iloc[0])
        return
    if res.explanation:
        st.markdown(f"**{res.explanation}**")
    if res.error:
        if res.blocked:
            st.warning("🔒 Demande refusee : cette application est en lecture seule, "
                       "elle ne peut ni modifier ni supprimer de donnees.")
        else:
            st.error("Je n'ai pas reussi a repondre a cette question. Essayez de la reformuler plus simplement "
                     "(ex : preciser la mesure, la periode ou le niveau de detail).")
        with st.expander("Detail technique"):
            st.code(res.error)
    if res.data is not None:
        auto_chart(res.data, key)
        st.dataframe(res.data, width="stretch", hide_index=True)
        st.caption(f"{len(res.data)} ligne(s) — requete generee par {res.model}")
    if res.sql:
        with st.expander("Voir la requete SQL generee par l'IA"):
            st.code(res.sql, language="sql")
            if len(res.attempts) > 1:
                st.caption(f"Requete corrigee automatiquement apres {len(res.attempts) - 1} erreur(s).")


# ------------------------------------------------------------------ BARRE LATERALE
with st.sidebar:
    st.header("Parametres")
    # Groq par defaut si une cle est configuree, sinon le modele local
    fallback = "groq:openai/gpt-oss-120b" if os.getenv("GROQ_API_KEY") else "ollama:qwen2.5-coder:3b"
    default_model = os.getenv("LLM_MODEL") or fallback
    model = st.selectbox(
        "Modele d'IA", AVAILABLE_MODELS,
        index=AVAILABLE_MODELS.index(default_model) if default_model in AVAILABLE_MODELS else 0,
        help="groq : modeles open source heberges, reponse en quelques secondes (cle gratuite). "
             "ollama : modele open source execute sur ce PC, sans Internet. "
             "cortex : Snowflake Cortex AI (compte Snowflake payant requis).",
    )
    if model.startswith("groq:"):
        st.caption("Modele open source heberge par Groq : reponse en quelques secondes (Internet requis).")
        if not os.getenv("GROQ_API_KEY"):
            st.warning("Cle GROQ_API_KEY absente du fichier .env : choisissez le modele ollama.")
    elif model.startswith("ollama:"):
        st.caption("Modele open source execute sur ce PC, sans Internet. La premiere question peut prendre "
                   "1 a 2 minutes (chargement du modele), les suivantes 10 a 40 secondes.")
        preheat(model)
    else:
        st.caption("Snowflake Cortex AI : indisponible sur un compte d'essai.")
    if st.button("Effacer la reponse", width="stretch"):
        st.session_state.last = None
    with st.expander("Schema GOLD transmis a l'IA"):
        st.text(get_schema())

st.title("Wide World Importers — Assistant de donnees")
tab_chat, tab_dash, tab_platform = st.tabs(["💬 Poser une question", "📊 Tableau de bord", "🏗️ Plateforme"])

# ------------------------------------------------------------------ ONGLET 1 : TEXT-TO-SQL
with tab_chat:
    st.write("Posez votre propre question en francais, ou cliquez sur un exemple : l'IA la traduit en SQL, "
             "l'execute sur la couche **Gold** et affiche le resultat.")

    # Saisie libre en haut de page : la reponse s'affiche juste en dessous
    with st.form("question_form", border=False):
        c_input, c_button = st.columns([5, 1], vertical_alignment="bottom")
        typed = c_input.text_input("Votre question", placeholder="Ex : Quel est le chiffre d'affaires par "
                                   "categorie de client en 2015 ?")
        submitted = c_button.form_submit_button("Demander", type="primary", width="stretch")

    st.caption("Exemples :")
    cols = st.columns(3)
    clicked = None
    for i, example in enumerate(EXAMPLES):
        if cols[i % 3].button(example, key=f"ex_{i}", width="stretch"):
            clicked = example

    question = typed.strip() if submitted and typed.strip() else clicked
    if question:
        # Une nouvelle question remplace la precedente
        with st.spinner(f"{model} genere la requete..."):
            st.session_state.last = ask(reader(), question, get_schema(), DATABASE, model)

    res = st.session_state.get("last")
    if res is not None:
        st.divider()
        st.markdown(f"#### ❓ {res.question}")
        show_result(res, key="last")

# ------------------------------------------------------------------ ONGLET 2 : TABLEAU DE BORD
with tab_dash:
    G = f"{DATABASE}.GOLD"
    years = query(f"select distinct year from {G}.dim_date d join {G}.fct_sales f using (date_key) order by 1")["year"].tolist()
    year = st.selectbox("Annee", ["Toutes"] + years)
    where = "" if year == "Toutes" else f"where d.year = {int(year)}"
    base = f"from {G}.fct_sales f join {G}.dim_date d using (date_key)"

    k = query(f"""select sum(revenue_excl_tax) ca, sum(profit) marge, count(distinct invoice_id) factures,
                         count(distinct customer_key) clients {base} {where}""").iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Chiffre d'affaires HT", f"{k.ca / 1e6:,.2f} M$")
    c2.metric("Marge", f"{k.marge / 1e6:,.2f} M$", f"{k.marge / k.ca:.1%} du CA", delta_color="off")
    c3.metric("Factures", f"{int(k.factures):,}".replace(",", " "))
    c4.metric("Clients actifs", f"{int(k.clients):,}".replace(",", " "))

    st.subheader("Chiffre d'affaires HT par mois")
    monthly = query(f"select d.year_month mois, sum(revenue_excl_tax) chiffre_affaires {base} {where} group by 1 order by 1")
    fig = px.line(monthly, x="mois", y="chiffre_affaires", markers=True)
    fig.update_traces(line=dict(color=ACCENT, width=2), marker=dict(size=8))
    st.plotly_chart(_style(fig), width="stretch")

    left, right = st.columns(2)
    with left:
        st.subheader("Top 10 produits par marge")
        top = query(f"""select p.product_name produit, sum(profit) marge {base}
                        join {G}.dim_product p using (product_key) {where}
                        group by 1 order by 2 desc limit 10""")
        fig = px.bar(top.sort_values("marge"), x="marge", y="produit", orientation="h")
        fig.update_traces(marker_color=ACCENT, marker_cornerradius=4)
        st.plotly_chart(_style(fig), width="stretch")
    with right:
        st.subheader("CA par territoire commercial")
        terr = query(f"""select c.sales_territory territoire, sum(revenue_excl_tax) chiffre_affaires {base}
                         join {G}.dim_customer c using (customer_key) {where} group by 1""")
        fig = px.bar(terr.sort_values("chiffre_affaires"), x="chiffre_affaires", y="territoire", orientation="h")
        fig.update_traces(marker_color=ACCENT, marker_cornerradius=4)
        st.plotly_chart(_style(fig), width="stretch")

# ------------------------------------------------------------------ ONGLET 3 : PLATEFORME
with tab_platform:
    st.subheader("Architecture")
    st.graphviz_chart("""
    digraph {
      rankdir=LR; node [shape=box, style="rounded,filled", fontname="Helvetica", fillcolor="#eef3fb", color="#2a78d6"];
      sql [label="SQL Server\\nWideWorldImporters"];
      bronze [label="BRONZE\\ndonnees brutes", fillcolor="#f3e3d3"];
      silver [label="SILVER\\nnettoyees", fillcolor="#e9e9e9"];
      gold [label="GOLD\\nmodele en etoile", fillcolor="#f7e7a8"];
      app [label="Streamlit\\n+ IA Text-to-SQL"];
      sql -> bronze [label="DLT"]; bronze -> silver [label="dbt"]; silver -> gold [label="dbt"]; gold -> app [label="SQL"];
      dag [label="Dagster\\n(orchestration)", shape=ellipse, fillcolor="#ffffff"];
      dag -> bronze [style=dashed]; dag -> silver [style=dashed]; dag -> gold [style=dashed];
    }""")
    try:
        layers = query(f"""select table_schema couche, count(*) nb_tables, sum(row_count) nb_lignes
                           from {DATABASE}.information_schema.tables
                           where table_schema in ('BRONZE','SILVER','GOLD') and table_type = 'BASE TABLE'
                             and not startswith(table_name, '_DLT')
                           group by 1 order by case table_schema when 'BRONZE' then 1 when 'SILVER' then 2 else 3 end""",
                       role="admin")
        st.subheader("Volumetrie par couche")
        st.dataframe(layers, hide_index=True, width="stretch")
        st.subheader("Derniers chargements DLT")
        loads = query(f"""select load_id, schema_name, status, inserted_at
                          from {DATABASE}.BRONZE._DLT_LOADS order by inserted_at desc limit 10""", role="admin")
        st.dataframe(loads, hide_index=True, width="stretch")
    except Exception as err:
        st.warning(f"Informations de la plateforme indisponibles : {err}")

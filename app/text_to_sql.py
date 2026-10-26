"""
Moteur Text-to-SQL : question en langage naturel -> SQL Snowflake.

Etapes :
 1. Le schema GOLD (tables, colonnes, commentaires dbt) est lu dans INFORMATION_SCHEMA.
 2. Un prompt decrit ce schema + les regles metier ; un modele de langage genere la requete.
 3. La requete est validee (une seule instruction SELECT, lecture seule) avec sqlglot.
 4. Elle est executee dans Snowflake avec le role WWI_READER ; en cas d'erreur, l'erreur
    est renvoyee au modele pour une tentative de correction automatique.

Deux fournisseurs de modele sont pris en charge :
 - "ollama" : modele open source execute localement (Qwen2.5-Coder), utilise par defaut car
   les fonctions IA de Snowflake ne sont pas disponibles sur les comptes d'essai ;
 - "cortex" : Snowflake Cortex AI (fonction AI_COMPLETE), sur un compte Snowflake payant.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from decimal import Decimal

import pandas as pd
import requests
import sqlglot
from sqlglot import exp

MAX_ROWS = 5000
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Modeles proposes, au format "fournisseur:modele"
MODELS = [
    "groq:openai/gpt-oss-120b",
    "groq:openai/gpt-oss-20b",
    "groq:qwen/qwen3.8-27b",
    "ollama:qwen2.5-coder:3b",
    "ollama:qwen2.5-coder:7b",
    "cortex:claude-3-5-sonnet",
    "cortex:mistral-large2",
    "cortex:llama3.3-70b",
]

BUSINESS_RULES = """
Regles metier :
- Chiffre d'affaires (CA, ventes, revenus) = SUM(fct_sales.revenue_excl_tax) (hors taxes) sauf si l'utilisateur demande explicitement le TTC (revenue_incl_tax).
- Benefice / marge / profit = SUM(fct_sales.profit). Taux de marge = SUM(profit) / NULLIF(SUM(revenue_excl_tax), 0).
- Nombre de factures = COUNT(DISTINCT fct_sales.invoice_id) ; nombre de commandes = COUNT(DISTINCT fct_orders.order_id).
- Les faits se joignent aux dimensions par leurs cles : date_key -> dim_date.date_key, customer_key -> dim_customer.customer_key,
  product_key -> dim_product.product_key, salesperson_key -> dim_employee.employee_key, supplier_key -> dim_supplier.supplier_key.
- Utiliser dim_date.year_month (AAAA-MM) pour les series mensuelles et dim_date.year pour les annees.
- Pour afficher un jour ou un mois, utiliser les libelles dim_date.day_name et dim_date.month_name plutot que leur numero.
- Les donnees couvrent la periode du 2013-01-01 au 2016-05-31 : "cette annee" = 2016, "l'annee derniere" = 2015.
- Les clients sont des magasins (dim_customer.customer_name) ; les commerciaux sont dans dim_employee.
- Groupement d'achat (Tailspin Toys, Wingtip Toys, Independant) = dim_customer.buying_group.
- Montant des achats fournisseurs = SUM(fct_purchases.purchase_amount) ; "acheter le plus" se mesure en montant, pas en nombre de lignes.
- Paiements / encaissements clients = table fct_customer_payments (montants deja positifs : SUM(payment_amount)).
- "Ventes" ou "vendre le plus" se mesure en chiffre d'affaires, sauf si l'utilisateur parle explicitement de quantites.
- Les montants sont en dollars americains.
- Si la question ne peut pas etre traitee avec ces tables (meteo, donnees externes...), repondre exactement :
  SELECT 'Cette question sort du perimetre des donnees disponibles (ventes, achats, stocks, clients, produits).' AS message
"""

# Exemples (few-shot) : ils montrent au modele le style de requete attendu
EXAMPLES = """
Exemples :
Question : Quel est le chiffre d'affaires par categorie de client en 2015 ?
```sql
-- Chiffre d'affaires HT 2015 par categorie de client
SELECT c.customer_category AS categorie_client, ROUND(SUM(f.revenue_excl_tax), 2) AS chiffre_affaires
FROM {db}.GOLD.FCT_SALES f
JOIN {db}.GOLD.DIM_CUSTOMER c ON f.customer_key = c.customer_key
JOIN {db}.GOLD.DIM_DATE d ON f.date_key = d.date_key
WHERE d.year = 2015
GROUP BY c.customer_category
ORDER BY chiffre_affaires DESC
```
Question : Combien de commandes chaque commercial a-t-il prises ?
```sql
-- Nombre de commandes distinctes par commercial
SELECT e.employee_name AS commercial, COUNT(DISTINCT o.order_id) AS nb_commandes
FROM {db}.GOLD.FCT_ORDERS o
JOIN {db}.GOLD.DIM_EMPLOYEE e ON o.salesperson_key = e.employee_key
GROUP BY e.employee_name
ORDER BY nb_commandes DESC
```
Question : Quelle est la marge par trimestre ?
```sql
-- Marge totale par trimestre, dans l'ordre chronologique
SELECT d.year AS annee, d.quarter AS trimestre, ROUND(SUM(f.profit), 2) AS marge
FROM {db}.GOLD.FCT_SALES f
JOIN {db}.GOLD.DIM_DATE d ON f.date_key = d.date_key
GROUP BY d.year, d.quarter
ORDER BY annee, trimestre
```
Question : Quel montant les clients ont-ils paye par moyen de paiement ?
```sql
-- Nombre et montant des paiements clients recus, par moyen de paiement
SELECT p.payment_method AS moyen_paiement, COUNT(*) AS nb_paiements, ROUND(SUM(p.payment_amount), 2) AS montant_paye
FROM {db}.GOLD.FCT_CUSTOMER_PAYMENTS p
GROUP BY p.payment_method
ORDER BY montant_paye DESC
```
"""

SYSTEM_PROMPT = """Tu es un expert SQL Snowflake qui traduit des questions metier en une requete SQL.
Tu reponds UNIQUEMENT avec un bloc ```sql ... ``` contenant UNE seule requete SELECT (ou WITH ... SELECT), sans autre texte.
Contraintes :
- Utiliser exclusivement les tables et colonnes decrites ci-dessous, avec le nom complet {database}.GOLD.<table>.
- Ne jamais modifier les donnees (pas d'INSERT, UPDATE, DELETE, CREATE, DROP, MERGE...).
- La premiere ligne du bloc est un commentaire SQL "-- " expliquant en une phrase, en francais, ce que fait la requete.
- Donner des alias de colonnes courts, en francais, en snake_case et sans accents (ex : chiffre_affaires, nom_client).
- Arrondir les montants a 2 decimales avec ROUND(). Trier les resultats de maniere pertinente.
- Pour un classement ("top", "meilleurs") ajouter ORDER BY ... DESC et LIMIT (10 par defaut).
- Ne pas ajouter de LIMIT pour une serie temporelle.
{rules}
Schema disponible :
{schema}
{examples}"""


@dataclass
class TextToSqlResult:
    question: str
    sql: str | None = None
    explanation: str | None = None
    data: pd.DataFrame | None = None
    error: str | None = None
    model: str | None = None
    blocked: bool = False  # vrai si une tentative d'ecriture a ete bloquee
    attempts: list[dict] = field(default_factory=list)


def load_gold_schema(conn, database: str) -> str:
    """Decrit les tables GOLD et leurs colonnes (avec les commentaires dbt) pour le prompt."""
    cur = conn.cursor()
    cur.execute(
        f"""
        select t.table_name, t.comment, c.column_name, c.data_type, c.comment
        from {database}.information_schema.tables t
        join {database}.information_schema.columns c
          on c.table_schema = t.table_schema and c.table_name = t.table_name
        where t.table_schema = 'GOLD'
        order by t.table_name, c.ordinal_position
        """
    )
    lines, current = [], None
    for table, table_comment, column, dtype, col_comment in cur.fetchall():
        if table != current:
            lines.append(f"\nTable {database}.GOLD.{table} -- {table_comment or ''}")
            current = table
        lines.append(f"  - {column.lower()} ({dtype}) : {col_comment or ''}")
    return "\n".join(lines).strip()


def build_system_prompt(schema: str, database: str) -> str:
    return SYSTEM_PROMPT.format(
        database=database, rules=BUSINESS_RULES, schema=schema, examples=EXAMPLES.format(db=database)
    )


# ------------------------------------------------------------------ FOURNISSEURS DE MODELE
def _call_ollama(model: str, messages: list[dict]) -> str:
    resp = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": model,
            "messages": messages,
            "stream": False,
            # Le prompt systeme reste identique d'une question a l'autre : Ollama le garde en cache
            "keep_alive": "60m",
            # num_thread = tous les fils du processeur (mesure : 4,3 jetons/s contre 3,1 avec la valeur
            # par defaut) ; num_ctx laisse ~2 000 jetons de marge au-dela du prompt systeme
            "options": {"temperature": 0, "num_ctx": 6144, "num_thread": os.cpu_count() or 4, "num_predict": 600},
        },
        timeout=600,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def _call_cortex(conn, model: str, messages: list[dict]) -> str:
    # AI_COMPLETE prend un prompt texte : on y serialise la conversation
    prompt = "\n\n".join(f"[{m['role'].upper()}]\n{m['content']}" for m in messages) + "\n\n[ASSISTANT]\n"
    cur = conn.cursor()
    cur.execute(
        f"select ai_complete('{model}', %s, {{'temperature': 0, 'max_tokens': 1500}})",
        (prompt,),
    )
    return str(cur.fetchone()[0])


def _call_groq(model: str, messages: list[dict]) -> str:
    # API compatible OpenAI ; les modeles proposes sont open source (GPT-OSS, Qwen)
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        raise RuntimeError("cle GROQ_API_KEY absente du fichier .env (cle gratuite sur https://console.groq.com/keys)")
    resp = requests.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": model, "messages": messages, "temperature": 0, "max_tokens": 2000,
            # modeles a raisonnement : reflexion courte et non renvoyee dans la reponse
            **({"reasoning_effort": "low"} if "gpt-oss" in model else {"reasoning_format": "hidden"}),
        },
        timeout=60,
    )
    if resp.status_code == 429:
        raise RateLimitError(f"quota gratuit de {model} atteint pour cette minute")
    if resp.status_code != 200:
        raise RuntimeError(f"Groq HTTP {resp.status_code} : {resp.text[:200]}")
    return resp.json()["choices"][0]["message"]["content"]


class RateLimitError(RuntimeError):
    """Quota gratuit Groq atteint (limite de jetons par minute et par modele)."""


def call_model(conn, model_id: str, messages: list[dict]) -> tuple[str, str]:
    """Renvoie (reponse, modele reellement utilise)."""
    if model_id not in MODELS:
        raise ValueError(f"Modele non autorise : {model_id}")
    provider, model = model_id.split(":", 1)
    if provider == "groq":
        # Relais : chaque modele Groq a son propre quota ; si le modele choisi est sature,
        # on passe au suivant plutot que de faire attendre l'utilisateur
        relay = [model_id] + [m for m in MODELS if m.startswith("groq:") and m != model_id]
        for candidate in relay:
            try:
                return _call_groq(candidate.split(":", 1)[1], messages), candidate
            except RateLimitError:
                continue
            except requests.exceptions.RequestException:
                break  # pas d'Internet : inutile d'essayer les autres modeles Groq
        # Dernier recours : le modele local (plus lent, mais disponible hors ligne)
        local = next(m for m in MODELS if m.startswith("ollama:"))
        try:
            return _call_ollama(local.split(":", 1)[1], messages), local
        except requests.exceptions.RequestException:
            raise RateLimitError("Groq indisponible (quota gratuit atteint ou pas d'Internet) et modele local "
                                 "Ollama non demarre : reessayez dans une minute") from None
    if provider == "ollama":
        return _call_ollama(model, messages), model_id
    return _call_cortex(conn, model, messages), model_id


def warm_up(model_id: str, system_prompt: str) -> None:
    """Charge le modele local et met le prompt systeme en cache (premiere question plus rapide)."""
    provider, model = model_id.split(":", 1)
    if provider == "ollama":
        _call_ollama(model, [{"role": "system", "content": system_prompt},
                             {"role": "user", "content": "Reponds uniquement : OK"}])


# ------------------------------------------------------------------ SQL
def extract_sql(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S | re.I)  # raisonnement eventuel du modele
    match = re.search(r"```(?:sql)?\s*(.*?)```", text, flags=re.S | re.I)
    sql = (match.group(1) if match else text).strip()
    return sql.rstrip(";").strip()


def split_explanation(sql: str) -> tuple[str | None, str]:
    lines = sql.splitlines()
    if lines and lines[0].lstrip().startswith("--"):
        return lines[0].lstrip()[2:].strip(), "\n".join(lines[1:]).strip()
    return None, sql


class WriteAttemptError(ValueError):
    """Tentative de modification des donnees : bloquee sans nouvelle tentative."""


# Mots-cles SQL d'ecriture reperes directement dans la question de l'utilisateur
WRITE_KEYWORDS = re.compile(r"\b(delete|drop|truncate|update|insert|alter|merge|create|grant|revoke)\s", re.I)


def validate_read_only(sql: str) -> None:
    """Refuse tout ce qui n'est pas une unique requete de lecture."""
    try:
        statements = [s for s in sqlglot.parse(sql, read="snowflake") if s is not None]
    except sqlglot.errors.ParseError as err:
        raise ValueError(f"SQL invalide : {err}") from err
    if not statements:
        raise ValueError("Le modele n'a produit aucune requete SQL.")
    if len(statements) > 1:
        raise WriteAttemptError("Une seule requete est autorisee.")
    stmt = statements[0]
    if not isinstance(stmt, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        raise WriteAttemptError("Seules les requetes SELECT sont autorisees.")
    forbidden = (exp.Insert, exp.Update, exp.Delete, exp.Create, exp.Drop, exp.Merge, exp.Alter, exp.Command)
    if any(stmt.find(node) for node in forbidden):
        raise WriteAttemptError("La requete contient une instruction de modification interdite.")


def run_query(conn, sql: str) -> pd.DataFrame:
    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchmany(MAX_ROWS)
    columns = [c[0].lower() for c in cur.description]
    df = pd.DataFrame(rows, columns=columns)
    # Les DECIMAL Snowflake arrivent en objets Decimal : on les convertit pour les graphiques
    for col in df.columns:
        sample = df[col].dropna()
        if not sample.empty and isinstance(sample.iloc[0], Decimal):
            df[col] = pd.to_numeric(df[col])
    return df


def ask(conn, question: str, schema: str, database: str, model_id: str, max_retries: int = 2) -> TextToSqlResult:
    result = TextToSqlResult(question=question, model=model_id)
    if WRITE_KEYWORDS.search(question):
        result.blocked = True
        result.error = "Demande de modification des donnees detectee dans la question : refusee avant tout appel au modele."
        return result
    messages = [
        {"role": "system", "content": build_system_prompt(schema, database)},
        {"role": "user", "content": question},
    ]

    for _ in range(max_retries + 1):
        try:
            answer, result.model = call_model(conn, model_id, messages)
        except Exception as err:  # modele indisponible, Ollama arrete, droits Cortex manquants...
            result.error = f"Appel au modele {model_id} impossible : {err}"
            return result

        result.explanation, sql = split_explanation(extract_sql(answer))
        result.sql = sql
        try:
            validate_read_only(sql)
            result.data = run_query(conn, sql)
            result.error = None
            result.attempts.append({"sql": sql, "statut": "ok"})
            return result
        except WriteAttemptError as err:
            # Pas d'autocorrection : une demande d'ecriture est refusee definitivement
            result.blocked, result.error = True, str(err)
            result.attempts.append({"sql": sql, "statut": f"bloquee : {err}"})
            return result
        except Exception as err:
            result.error = str(err)
            result.attempts.append({"sql": sql, "statut": f"erreur : {err}"})
            # Autocorrection : on renvoie l'erreur au modele
            messages += [
                {"role": "assistant", "content": answer},
                {"role": "user", "content": f"Cette requete a echoue avec l'erreur suivante :\n{err}\n"
                                            "Corrige-la et renvoie uniquement la requete corrigee."},
            ]
    return result

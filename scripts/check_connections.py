"""Verifie l'acces a SQL Server, a Snowflake et a Cortex AI avant de lancer la plateforme."""
import os
import sys
from pathlib import Path

import sqlalchemy as sa
import snowflake.connector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.config import env, mssql_url, snowflake_connect_args  # noqa: E402

ok = True

try:
    with sa.create_engine(mssql_url()).connect() as c:
        n = c.execute(sa.text("select count(*) from Sales.Invoices")).scalar()
    print(f"[OK]     SQL Server : {n} factures dans WideWorldImporters")
except Exception as err:
    ok = False
    print(f"[ECHEC]  SQL Server : {err}")

for role in (env("SNOWFLAKE_ROLE"), env("SNOWFLAKE_READER_ROLE", "WWI_READER")):
    try:
        with snowflake.connector.connect(**snowflake_connect_args(role=role)) as conn:
            cur = conn.cursor()
            cur.execute("select current_user(), current_role(), current_warehouse(), current_region()")
            print(f"[OK]     Snowflake ({role}) : {cur.fetchone()}")
    except Exception as err:
        ok = False
        print(f"[ECHEC]  Snowflake ({role}) : {err}")

import requests

if os.getenv("GROQ_API_KEY"):
    try:
        r = requests.get("https://api.groq.com/openai/v1/models",
                         headers={"Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}"}, timeout=15)
        r.raise_for_status()
        print(f"[OK]     Groq : cle valide, {len(r.json()['data'])} modeles disponibles")
    except Exception as err:
        ok = False
        print(f"[ECHEC]  Groq : {err}")
else:
    print("[INFO]   Groq : pas de cle GROQ_API_KEY dans .env (le modele local sera utilise)")

try:
    tags = requests.get("http://localhost:11434/api/tags", timeout=5).json()["models"]
    found = any(m["name"] == "qwen2.5-coder:3b" for m in tags)
    print(f"[{'OK' if found else 'INFO'}]{'     ' if found else '   '}Ollama (modele local de secours) : "
          f"{'qwen2.5-coder:3b present' if found else 'modele absent'}")
except Exception:
    print("[INFO]   Ollama (modele local de secours) : serveur non demarre")

try:
    with snowflake.connector.connect(**snowflake_connect_args(role=env("SNOWFLAKE_READER_ROLE", "WWI_READER"))) as conn:
        conn.cursor().execute("select ai_complete('mistral-large2', 'OK')")
        print("[OK]     Cortex AI disponible")
except Exception as err:
    print(f"[INFO]   Cortex AI indisponible (normal sur un compte d'essai) : {str(err)[:80]}")

sys.exit(0 if ok else 1)

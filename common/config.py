"""Configuration partagee par l'ingestion, l'orchestration et l'application."""
import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_DIR / ".env")


def env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None or value == "":
        raise RuntimeError(f"Variable d'environnement manquante : {name} (voir le fichier .env)")
    return value


def mssql_url() -> str:
    """URL SQLAlchemy vers la base source SQL Server (authentification Windows)."""
    driver = quote_plus(env("MSSQL_DRIVER", "ODBC Driver 18 for SQL Server"))
    return (
        f"mssql+pyodbc://@{env('MSSQL_SERVER', 'localhost')}/{env('MSSQL_DATABASE', 'WideWorldImporters')}"
        f"?driver={driver}&trusted_connection=yes&TrustServerCertificate=yes"
    )


def private_key_pem() -> str:
    # En ligne (Streamlit Cloud) la cle est fournie directement dans les secrets ; en local, par un fichier
    if os.getenv("SNOWFLAKE_PRIVATE_KEY"):
        return os.environ["SNOWFLAKE_PRIVATE_KEY"]
    return Path(env("SNOWFLAKE_PRIVATE_KEY_PATH")).read_text()


def snowflake_connect_args(role: str | None = None) -> dict:
    """Parametres pour snowflake.connector.connect()."""
    from cryptography.hazmat.primitives import serialization

    key = serialization.load_pem_private_key(private_key_pem().encode(), password=None)
    return {
        "account": env("SNOWFLAKE_ACCOUNT"),
        "user": env("SNOWFLAKE_USER"),
        "private_key": key.private_bytes(
            serialization.Encoding.DER,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
        "role": role or env("SNOWFLAKE_ROLE"),
        "warehouse": env("SNOWFLAKE_WAREHOUSE"),
        "database": env("SNOWFLAKE_DATABASE"),
    }

"""
Ingestion DLT : SQL Server (WideWorldImporters) -> Snowflake, schema BRONZE.

- Les petites tables de reference sont rechargees entierement (write_disposition = replace).
- Les grosses tables transactionnelles sont chargees en INCREMENTAL sur la colonne
  LastEditedWhen et fusionnees sur leur cle primaire (write_disposition = merge).
- Les colonnes non exploitables (geographie, binaires) sont ecartees a l'extraction.

Usage :
    python ingestion/pipeline_wwi.py                 # charge vers Snowflake
    python ingestion/pipeline_wwi.py --destination duckdb   # test local
"""
import argparse
import os
import re
import sys
import warnings
from pathlib import Path

import dlt
import sqlalchemy as sa
from dlt.sources.sql_database import sql_database

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.config import env, mssql_url, private_key_pem  # noqa: E402

# SQLAlchemy ne connait pas le type geography : la colonne est ecartee plus bas
warnings.filterwarnings("ignore", message="Did not recognize type")
# Ajoute la colonne _dlt_load_id (tracabilite du lot de chargement) en mode pyarrow
os.environ.setdefault("NORMALIZE__PARQUET_NORMALIZER__ADD_DLT_LOAD_ID", "true")

# Tables extraites par schema source
SOURCE_TABLES: dict[str, list[str]] = {
    "Application": [
        "Cities", "StateProvinces", "Countries", "DeliveryMethods",
        "PaymentMethods", "People", "TransactionTypes",
    ],
    "Sales": [
        "Customers", "CustomerCategories", "BuyingGroups", "Orders",
        "OrderLines", "Invoices", "InvoiceLines", "CustomerTransactions",
    ],
    "Purchasing": [
        "Suppliers", "SupplierCategories", "PurchaseOrders",
        "PurchaseOrderLines", "SupplierTransactions",
    ],
    "Warehouse": [
        "StockItems", "StockItemHoldings", "StockGroups", "StockItemStockGroups",
        "Colors", "PackageTypes", "StockItemTransactions",
    ],
}

# Tables volumineuses chargees en incremental (curseur = LastEditedWhen)
INCREMENTAL_TABLES = {
    "Orders", "OrderLines", "Invoices", "InvoiceLines",
    "CustomerTransactions", "StockItemTransactions",
    "PurchaseOrders", "PurchaseOrderLines", "SupplierTransactions",
}


def bronze_table_name(schema: str, table: str) -> str:
    """Sales.InvoiceLines -> sales_invoice_lines"""
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", table).lower()
    return f"{schema.lower()}_{snake}"


def drop_unsupported_columns(table: sa.Table) -> sa.Table:
    """Retire les colonnes geography (non lisibles par ODBC) et binaires (photos, mots de passe)."""
    for col in list(table.columns):
        if isinstance(col.type, (sa.types.NullType, sa.types.LargeBinary, sa.types._Binary)):
            table._columns.remove(col)
    return table


def build_sources():
    for schema, tables in SOURCE_TABLES.items():
        source = sql_database(
            credentials=mssql_url(),
            schema=schema,
            table_names=tables,
            backend="pyarrow",
            chunk_size=50_000,
            reflection_level="full",
            table_adapter_callback=drop_unsupported_columns,
        )

        for table in tables:
            resource = source.resources[table]
            hints = {"table_name": bronze_table_name(schema, table)}
            if table in INCREMENTAL_TABLES:
                hints["incremental"] = dlt.sources.incremental("LastEditedWhen")
                hints["write_disposition"] = "merge"
            else:
                hints["write_disposition"] = "replace"
            resource.apply_hints(**hints)
        yield schema, source


def snowflake_destination():
    return dlt.destinations.snowflake(
        credentials={
            "database": env("SNOWFLAKE_DATABASE"),
            "username": env("SNOWFLAKE_USER"),
            "host": env("SNOWFLAKE_ACCOUNT"),
            "warehouse": env("SNOWFLAKE_WAREHOUSE"),
            "role": env("SNOWFLAKE_ROLE"),
            "private_key": private_key_pem(),
        }
    )


def run(destination: str = "snowflake", full_refresh: bool = False) -> dict[str, int]:
    """Execute le chargement et renvoie le nombre de lignes chargees par table Bronze."""
    pipeline = dlt.pipeline(
        # Nom distinct par destination : un test local ne doit pas deplacer les curseurs incrementaux Snowflake
        pipeline_name="wwi_sqlserver_to_snowflake" if destination == "snowflake" else f"wwi_sqlserver_to_{destination}",
        destination=snowflake_destination() if destination == "snowflake" else destination,
        dataset_name="bronze",
        progress="log",
    )
    infos, row_counts = [], {}
    for schema, source in build_sources():
        print(f"--> Extraction du schema source {schema}")
        # full_refresh : vide les tables et remet a zero les curseurs incrementaux
        info = pipeline.run(source, refresh="drop_resources" if full_refresh else None)
        print(info)
        infos.append(info)
        row_counts.update(pipeline.last_trace.last_normalize_info.row_counts)
    print("\nLignes chargees par table (0 = aucune nouveaute en incremental) :")
    for table, rows in sorted(row_counts.items()):
        if not table.startswith("_dlt"):
            print(f"  {table:<40} {rows:>9}")
    return row_counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", default="snowflake", help="snowflake (defaut) ou duckdb pour un test local")
    parser.add_argument("--full-refresh", action="store_true", help="recharge tout depuis zero (ignore l'incremental)")
    args = parser.parse_args()
    run(args.destination, args.full_refresh)

"""
Orchestration Dagster de la Modern Data Platform WWI.

Graphe d'assets :  SQL Server --(DLT)--> BRONZE --(dbt)--> SILVER --(dbt)--> GOLD
- Les tables Bronze sont produites par un multi-asset qui execute le pipeline DLT.
- Les modeles dbt deviennent des assets ; leurs tests deviennent des "asset checks".
- Dagster deduit les dependances : les sources dbt "bronze.*" pointent vers les assets DLT.
"""
import os
import sys
from pathlib import Path

from dagster import (
    AssetExecutionContext,
    AssetSelection,
    AssetSpec,
    Backoff,
    DefaultScheduleStatus,
    Definitions,
    MaterializeResult,
    RetryPolicy,
    ScheduleDefinition,
    define_asset_job,
    multi_asset,
)
from dagster_dbt import DagsterDbtTranslator, DbtCliResource, DbtProject, dbt_assets

PROJECT_DIR = Path(__file__).resolve().parents[1]
# dbt est installe dans le meme environnement virtuel que Dagster
DBT_EXECUTABLE = str(Path(sys.executable).with_name("dbt.exe" if sys.platform == "win32" else "dbt"))
# "dagster dev" relance "dbt parse" en cherchant dbt dans le PATH : on y ajoute le dossier du venv
os.environ["PATH"] = str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")
sys.path.insert(0, str(PROJECT_DIR))

from ingestion.pipeline_wwi import SOURCE_TABLES, bronze_table_name, run as run_dlt  # noqa: E402

# ---------------------------------------------------------------- BRONZE (DLT)
BRONZE_TABLES = [bronze_table_name(s, t) for s, tables in SOURCE_TABLES.items() for t in tables]


@multi_asset(
    name="ingestion_dlt_sqlserver",
    specs=[
        AssetSpec(
            key=["bronze", table],
            group_name="bronze",
            kinds={"dlt", "snowflake"},
            description=f"Table brute {table} chargee par DLT depuis SQL Server",
        )
        for table in BRONZE_TABLES
    ],
    retry_policy=RetryPolicy(max_retries=2, delay=30, backoff=Backoff.EXPONENTIAL),
)
def bronze_dlt_assets(context: AssetExecutionContext):
    row_counts = run_dlt("snowflake")
    for table in BRONZE_TABLES:
        yield MaterializeResult(
            asset_key=["bronze", table],
            metadata={"lignes_chargees_dernier_lot": row_counts.get(table, 0)},
        )


# ---------------------------------------------------------------- SILVER / GOLD (dbt)
dbt_project = DbtProject(project_dir=PROJECT_DIR / "dbt_wwi", profiles_dir=PROJECT_DIR / "dbt_wwi")
dbt_project.prepare_if_dev()


class MedallionTranslator(DagsterDbtTranslator):
    """Range chaque modele dbt dans le groupe Dagster de sa couche (silver / gold)."""

    def get_group_name(self, dbt_resource_props):
        fqn = dbt_resource_props.get("fqn", [])
        return fqn[1] if len(fqn) > 2 else "dbt"


@dbt_assets(manifest=dbt_project.manifest_path, dagster_dbt_translator=MedallionTranslator())
def dbt_medallion_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()


# ---------------------------------------------------------------- JOB + PLANIFICATION
pipeline_complet = define_asset_job(
    name="pipeline_complet",
    description="Ingestion DLT puis transformations dbt Silver et Gold, avec tests de qualite",
    selection=AssetSelection.all(),
)

planification_quotidienne = ScheduleDefinition(
    name="chaque_jour_6h",
    job=pipeline_complet,
    cron_schedule="0 6 * * *",
    execution_timezone="Africa/Dakar",
    default_status=DefaultScheduleStatus.RUNNING,
)

defs = Definitions(
    assets=[bronze_dlt_assets, dbt_medallion_assets],
    jobs=[pipeline_complet],
    schedules=[planification_quotidienne],
    resources={"dbt": DbtCliResource(project_dir=dbt_project, dbt_executable=DBT_EXECUTABLE)},
)

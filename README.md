# Modern Data Platform — Wide World Importers

Architecture Médaillon sur Snowflake + application Text-to-SQL avec des modèles d'IA open source
(Groq : GPT-OSS, Qwen ; secours local : Ollama ; option : Snowflake Cortex sur compte payant).

```
SQL Server (WideWorldImporters)
      │  DLT  (ingestion/pipeline_wwi.py) : complet pour les référentiels, incrémental sur LastEditedWhen pour les transactions
      ▼
Snowflake BRONZE  (27 tables brutes)
      │  dbt  (dbt_wwi/models/silver) : nettoyage, normalisation, dédoublonnage
      ▼
Snowflake SILVER  (27 tables)
      │  dbt  (dbt_wwi/models/gold) : modèle en étoile documenté + 88 tests qualité
      ▼
Snowflake GOLD    (5 dimensions, 6 faits)
      │  IA (app/text_to_sql.py) : question -> SQL -> résultat
      │      Groq (GPT-OSS 120B/20B, Qwen 3.8 27B, relais automatique) ; secours Ollama local ; option Cortex
      ▼
Streamlit (app/streamlit_app.py)

Orchestration de bout en bout : Dagster (orchestration/definitions.py), planifié tous les jours à 6h.
```

## Lancement rapide

Double-cliquer sur **`LANCER.bat`** : un menu propose de lancer l'application, Dagster, la documentation dbt,
le pipeline complet ou la vérification des connexions. Le serveur d'IA local (Ollama) est démarré automatiquement.

## Mise en route

1. **Snowflake** : ouvrir une feuille de calcul Snowsight en `ACCOUNTADMIN`, exécuter `snowflake/setup.sql`.
   Copier la valeur `account` affichée à la fin dans `.env` (`SNOWFLAKE_ACCOUNT=`).
2. Créer une clé gratuite sur https://console.groq.com/keys et la coller dans `.env` (`GROQ_API_KEY=`).
   Optionnel (secours sans Internet) : installer Ollama puis `ollama pull qwen2.5-coder:3b`.
3. `.\mdp.ps1 test` : vérifie SQL Server, Snowflake et le modèle d'IA.
4. `.\mdp.ps1 ingest` : charge la couche Bronze (`--full-refresh` via python pour tout recharger).
5. `.\mdp.ps1 dbt` : construit Silver et Gold, exécute les tests.
6. `.\mdp.ps1 app` : lance l'application (http://localhost:8501).

`.\mdp.ps1 dagster` ouvre Dagster (http://localhost:3000) : le job `pipeline_complet` enchaîne les étapes 4 et 5.
`.\mdp.ps1 docs` affiche la documentation et le lignage dbt (http://localhost:8080).

## Modèle Gold

| Table | Grain | Contenu |
|---|---|---|
| `dim_date` | jour | calendrier 2013-2016 (libellés en français) |
| `dim_customer` | client | catégorie, groupement d'achat, ville, territoire |
| `dim_product` | article | famille, marque, couleur, fournisseur, prix |
| `dim_supplier` | fournisseur | catégorie, localisation |
| `dim_employee` | employé | commerciaux |
| `fct_sales` | ligne de facture | CA HT/TTC, coût, marge, quantités |
| `fct_orders` | ligne de commande | quantités commandées / préparées |
| `fct_purchases` | ligne d'achat | achats fournisseurs |
| `fct_stock` | article | stock actuel, valeur, alerte de réapprovisionnement |
| `fct_customer_transactions` | transaction | factures et paiements mélangés, soldes restant dus |
| `fct_customer_payments` | paiement | paiements reçus uniquement (montants positifs) |

## Sécurité du Text-to-SQL

- Le SQL généré est exécuté avec le rôle `WWI_READER`, qui ne peut **que lire** le schéma GOLD.
- Avant exécution, la requête est analysée (sqlglot) : une seule instruction, de type SELECT uniquement.
- En cas d'erreur SQL, l'erreur est renvoyée au modèle pour une correction automatique (1 tentative).
- Authentification Snowflake par paire de clés RSA (`keys/`, jamais versionné), sans mot de passe.

## Pourquoi des modèles open source plutôt que Cortex ?

Sur un compte Snowflake d'essai, toutes les fonctions d'IA (`AI_COMPLETE`, `AI_SENTIMENT`...) renvoient
« not available for trial accounts ». Le moteur Text-to-SQL accepte donc plusieurs fournisseurs :

| Fournisseur | Modèles | Temps par question |
|---|---|---|
| Groq (par défaut) | GPT-OSS 120B, GPT-OSS 20B, Qwen 3.8 27B | 1,3 à 4,7 s (médiane 2,5 s) |
| Ollama (secours, sans Internet) | Qwen2.5-Coder 3B | 15 à 23 s (après ~2 min 30 de chargement) |
| Snowflake Cortex (option) | selon la région | compte payant requis |

Le quota gratuit de Groq (8 000 jetons/min par modèle, ~2 questions/min) est contourné par un relais
automatique entre les trois modèles. Seuls la question et le schéma sont envoyés au modèle : les données
restent dans Snowflake, interrogées avec le rôle en lecture seule.

## Tests de l'IA

| Série | Qwen2.5-Coder 3B (local) | Groq |
|---|---|---|
| 6 questions de démonstration | 6/6 | 6/6 |
| 12 questions variées (chiffres vérifiés contre des requêtes de référence) | 8/10 puis 12/12 après ajustements | 12/12 du premier coup |
| Demande de suppression | refusée | refusée |
| Question hors sujet | message de périmètre | message de périmètre |

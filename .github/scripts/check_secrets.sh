#!/usr/bin/env bash
# Vérifie le FORMAT des secrets Databricks avant de se connecter, sans jamais afficher leur valeur.
#
# Erreur typique : coller dans le secret la ligne entière du .env (« DATABRICKS_HOST=https://… ») au lieu de
# la valeur seule. dbt tente alors de joindre un hôte « databricks_host=… » et reste bloqué ~15 minutes.
#
# Lit les variables d'environnement DATABRICKS_HOST, DATABRICKS_TOKEN, DATABRICKS_HTTP_PATH, DBT_CATALOG,
# DBT_SCHEMA. Code de sortie : 0 si tout est conforme, 1 sinon (une annotation ::error:: par problème).

failures=0
fail() {
  echo "::error::$1"
  failures=$((failures + 1))
}

for name in DATABRICKS_HOST DATABRICKS_TOKEN DATABRICKS_HTTP_PATH DBT_CATALOG DBT_SCHEMA; do
  value="${!name:-}"
  if [ -z "$value" ]; then
    fail "Le secret $name est absent ou vide (voir CLAUDE.md, section CI/CD GitHub Actions)."
    continue
  fi
  case "$value" in
    "$name="*)
      fail "Le secret $name commence par « $name= » : coller la valeur seule, sans le nom de la variable."
      continue
      ;;
  esac
  case "$value" in
    *[[:space:]]*)
      fail "Le secret $name contient un espace ou un retour à la ligne : le recoller sans caractère superflu."
      continue
      ;;
  esac
done

case "${DATABRICKS_HOST:-}" in
  *=*) fail "DATABRICKS_HOST contient « = » : seule l'URL du workspace est attendue (https://dbc-….cloud.databricks.com)." ;;
esac

case "${DATABRICKS_HTTP_PATH:-}" in
  "" | /sql/*) ;;
  *) fail "DATABRICKS_HTTP_PATH doit commencer par /sql/ (ex. /sql/1.0/warehouses/<identifiant>)." ;;
esac

if [ "$failures" -gt 0 ]; then
  echo "::error::$failures secret(s) mal configuré(s). Corriger dans Settings > Secrets and variables > Actions."
  exit 1
fi
echo "Format des secrets conforme (valeurs non affichées)."

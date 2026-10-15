#!/usr/bin/env bash
# Teste la connexion à Databricks avec plusieurs essais.
#
# Un warehouse arrêté refuse parfois les premières connexions pendant son démarrage, avec une erreur
# immédiate et non un délai dépassé : « BAD_REQUEST: Cannot create the resource, please try again later ».
# Augmenter un timeout n'y change rien ; il faut réessayer.
#
# Usage : wait_for_databricks.sh <cible dbt : ci ou prod>   (à lancer depuis le dossier dbt/)
# Variables facultatives : ATTEMPTS (5), ATTEMPT_TIMEOUT en secondes (120), PAUSE en secondes (30).
# Durée maximale par défaut : 5 x 120 s + 4 x 30 s = 12 minutes.

target="${1:?cible dbt manquante (ci ou prod)}"
attempts="${ATTEMPTS:-5}"
limit="${ATTEMPT_TIMEOUT:-120}"
pause="${PAUSE:-30}"

for attempt in $(seq 1 "$attempts"); do
  if timeout "$limit" dbt debug --target "$target" --connection; then
    echo "Connexion Databricks établie (tentative $attempt/$attempts)."
    exit 0
  fi
  if [ "$attempt" -lt "$attempts" ]; then
    echo "::warning::Connexion Databricks refusée (tentative $attempt/$attempts) : le warehouse démarre peut-être. Nouvel essai dans ${pause} s."
    sleep "$pause"
  fi
done

echo "::error::Connexion à Databricks impossible après $attempts tentatives : vérifier DATABRICKS_HOST, DATABRICKS_HTTP_PATH, DATABRICKS_TOKEN et le démarrage du warehouse."
exit 1

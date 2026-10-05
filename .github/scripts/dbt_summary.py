"""Résumé Markdown d'une exécution dbt, pour le résumé de job GitHub Actions.

Usage : python .github/scripts/dbt_summary.py "<titre>" [chemin/vers/run_results.json]

Le résumé est ajouté à $GITHUB_STEP_SUMMARY s'il est défini, sinon écrit sur la sortie standard.
Sans fichier de résultats (étape dbt qui n'a rien produit), le script ne fait rien et réussit.
"""

import json
import os
import sys
from collections import Counter
from pathlib import Path

DEFAULT_RESULTS = Path("target/run_results.json")
PROBLEM_STATUSES = {"error", "fail", "runtime error"}


def build_summary(title: str, results: dict) -> str:
    """Construit le résumé Markdown d'un `run_results.json`.

    Args:
        title: Titre du résumé (ex. « dbt test »).
        results: Contenu décodé de `run_results.json`.

    Returns:
        Tableau des statuts, suivi de la liste des nœuds en échec.
    """
    entries = results.get("results", [])
    if not entries:
        return f"### {title}\n\nAucun nœud sélectionné.\n"

    counts = Counter(entry["status"] for entry in entries)
    lines = [f"### {title}", "", "| Statut | Nombre |", "|---|---|"]
    lines += [f"| {status} | {count} |" for status, count in sorted(counts.items())]

    problems = [entry for entry in entries if entry["status"] in PROBLEM_STATUSES]
    if problems:
        lines += ["", "**En échec :**", ""]
        for entry in problems:
            message = (entry.get("message") or entry["status"]).strip().splitlines()[0]
            lines.append(f"- `{entry['unique_id']}` : {message}")

    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    """Point d'entrée CLI.

    Args:
        argv: Arguments de la ligne de commande (titre, puis chemin optionnel).

    Returns:
        Code de sortie (0 si le résumé est écrit ou s'il n'y a rien à résumer, 2 si usage incorrect).
    """
    if len(argv) < 2:
        print(__doc__)
        return 2

    path = Path(argv[2]) if len(argv) > 2 else DEFAULT_RESULTS
    if not path.exists():
        print(f"Pas de {path} : aucun résumé.")
        return 0

    summary = build_summary(argv[1], json.loads(path.read_text(encoding="utf-8")))
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if target:
        with open(target, "a", encoding="utf-8") as handle:
            handle.write(summary + "\n")
    else:
        print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

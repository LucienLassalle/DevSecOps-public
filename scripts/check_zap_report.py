import json
import sys
from pathlib import Path

EXPECTED_TARGET = "http://127.0.0.1:8000"
LEVELS = {
    "0": "Information",
    "1": "Faible",
    "2": "Moyen",
    "3": "Élevé",
}

try:
    report = json.loads(
        Path("report_json.json").read_text(encoding="utf-8")
    )

    if not isinstance(report, dict):
        raise ValueError("Format du rapport incorrect.")

    sites = report.get("site")
    if not isinstance(sites, list) or not sites:
        raise ValueError("Aucun site présent dans le rapport.")

    counts = {risk: 0 for risk in LEVELS}
    target_found = False

    for site in sites:
        if not isinstance(site, dict):
            raise ValueError("Site mal formé.")

        name = site.get("@name", "")
        if not isinstance(name, str):
            raise ValueError("Adresse du site incorrecte.")

        if name.rstrip("/") == EXPECTED_TARGET:
            target_found = True

        alerts = site.get("alerts")
        if not isinstance(alerts, list):
            raise ValueError("Liste des alertes absente ou incorrecte.")

        for alert in alerts:
            if not isinstance(alert, dict):
                raise ValueError("Alerte mal formée.")

            risk = str(alert.get("riskcode"))
            if risk not in LEVELS:
                raise ValueError("Gravité absente ou inconnue.")

            counts[risk] += 1

    if not target_found:
        raise ValueError("La cible attendue est absente du rapport.")

except (OSError, ValueError) as error:
    print(f"BLOCAGE : rapport inexploitable : {error}")
    sys.exit(1)

for risk, label in LEVELS.items():
    print(f"{label} : {counts[risk]}")

if counts["3"]:
    print("BLOCAGE : alertes de risque élevé détectées.")
    sys.exit(1)

print("PASS : aucune alerte de risque élevé.")
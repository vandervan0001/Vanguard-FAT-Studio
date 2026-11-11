"""Attributed offline index; the server never fetches arbitrary catalogue URLs."""

CATALOG_SOURCE = {
    "name": "Public Chemical Manufacturing Datasets, Scott Duncan",
    "url": "https://github.com/ScottDuncanAI/public-chemical-manufacturing-datasets",
    "license": "CC BY 4.0 (index et descriptions uniquement)",
    "revision": "3f21a8540cac027489d22ebc7af757b0b5299880",
    "changes": "Sélection et descriptions adaptées en français pour Vanguard FAT Studio.",
}


def entry(identifier, title, category, description, url, pages="", license_note="Conditions de la source à vérifier avant redistribution."):
    return {"id": identifier, "title": title, "category": category, "description": description,
            "url": url, "pages": pages, "license_note": license_note}


ENTRIES = [
    entry("haile", "Haile Gold Mine CWTP", "pid", "Traitement des eaux de mine, PDF numérique (environ 13 Mo).",
          "https://des.sc.gov/sites/des/files/media/document/BOW_HGM_ContactWWTreatmentUpgrade.pdf", "47-60"),
    entry("pahala", "Pahala WWTP", "pid", "Station d'épuration à Hawaii, PDF numérique avec légendes (environ 7 Mo).",
          "https://www.epa.gov/system/files/documents/2021-08/pahala-wwtp-design-build-drawings-2021-07-23.pdf", "9-25"),
    entry("virden", "Virden WWTF", "pid", "Station d'épuration au Manitoba, plans scannés (environ 3 Mo).",
          "https://www.gov.mb.ca/sd/eal/registries/5697virden/2019-04-26_5697_00_phase_2_p_and_i_drwngs.pdf", "5-14"),
    entry("salina", "Salina WWTP", "pid", "Rapport de conception, couche texte mixte (environ 33 Mo). Extraire d'abord les pages utiles pour respecter la limite d'import.",
          "https://www.salina-ks.gov/media/utilities/Document%20Library/Salina_WWTP_Improvement_Project_BDR_Report_Final_051121%20%281%29.pdf",
          "114,117,119,121,126,127,132,134"),
    entry("ruttan", "Ruttan Mine WTP", "pid", "Traitement d'eau de mine au Manitoba, plans dans un manuel (environ 18 Mo).",
          "https://gov.mb.ca/sd/eal/registries/294.30/20250618_letter.pdf", "50-52,62-63"),
    entry("tep", "Tennessee Eastman Process", "timeseries", "Procédé simulé pour comparer la détection de défauts. Compte Kaggle gratuit requis.",
          "https://www.kaggle.com/datasets/afrniomelo/tep-csv"),
    entry("noboom", "NOBOOM", "timeseries", "Séries réelles de laboratoire, pilote et installation industrielle. Compte Kaggle gratuit requis.",
          "https://www.kaggle.com/datasets/faebs94/noboom-anomaly-detection-in-chemical-processes"),
    entry("boiler", "Coal-Fired Industrial Boiler", "timeseries", "Mesures réelles de chaudière industrielle à cinq secondes. Compte Kaggle gratuit requis.",
          "https://www.kaggle.com/datasets/nikitamanaenkov/time-series-of-industrial-boiler-operations"),
    entry("indpensim", "IndPenSim", "timeseries", "Fermentation simulée et jeux de lots pour l'analyse de procédé.",
          "http://www.industrialpenicillinsimulation.com/"),
    entry("historianrca", "HistorianRCA", "timeseries", "Historique simulé avec défauts et qualité des mesures ; corrigé conservé privé par l'auteur.",
          "https://github.com/ScottDuncanAI/HistorianRCA"),
]


def public_catalog() -> dict:
    return {"source": CATALOG_SOURCE, "entries": ENTRIES,
            "notice": "Télécharger le document depuis sa source, puis l'ouvrir localement. "
                      "Les séries temporelles sont des références documentaires ; elles ne sont pas des P&ID importables."}

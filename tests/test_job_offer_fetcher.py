"""
Récupération du contenu d'une annonce depuis son URL
(services.job_offer_fetcher).

Aucun test n'effectue de vraie requête réseau : trafilatura est
importé dynamiquement dans la fonction testée, donc on le remplace
dans sys.modules avant l'appel — comme pour les autres dépendances
importées à la demande dans ce projet (docx, reportlab, google.genai).
"""

from __future__ import annotations

import json
import sys
import types

from services.job_offer_fetcher import fetch_job_offer_from_url


def _installer_faux_trafilatura(monkeypatch, fetch_url=None, extract=None):
    """
    Installe un faux module `trafilatura` dans sys.modules le temps
    du test, avec les comportements fournis pour fetch_url/extract.
    """

    faux_module = types.ModuleType("trafilatura")
    faux_module.fetch_url = fetch_url or (lambda url: None)
    faux_module.extract = extract or (lambda *a, **k: None)

    monkeypatch.setitem(sys.modules, "trafilatura", faux_module)


# ============================================================
# VALIDATION DE L'URL
# ============================================================

def test_une_url_vide_ne_tente_rien():
    resultat = fetch_job_offer_from_url("   ")

    assert resultat.success is False
    assert "lien" in resultat.error.lower()


def test_une_url_sans_schema_http_est_refusee():
    resultat = fetch_job_offer_from_url("ftp://exemple.com/offre")

    assert resultat.success is False
    assert "http" in resultat.error.lower()


# ============================================================
# ECHECS DE TELECHARGEMENT / EXTRACTION
# ============================================================

def test_un_telechargement_impossible_retourne_une_erreur_lisible(
    monkeypatch,
):
    """
    Cas LinkedIn typique : le téléchargement ne renvoie rien (site
    qui bloque la requête).
    """

    _installer_faux_trafilatura(monkeypatch, fetch_url=lambda url: None)

    resultat = fetch_job_offer_from_url("https://www.linkedin.com/jobs/1")

    assert resultat.success is False
    assert resultat.text == ""
    assert resultat.error


def test_une_exception_au_telechargement_ne_plante_pas(monkeypatch):
    def _fetch_url(url):
        raise ConnectionError("timeout")

    _installer_faux_trafilatura(monkeypatch, fetch_url=_fetch_url)

    resultat = fetch_job_offer_from_url("https://exemple.com/offre")

    assert resultat.success is False
    assert "timeout" in resultat.error


def test_une_extraction_vide_retourne_une_erreur_lisible(monkeypatch):
    """Page accessible mais contenu chargé en JavaScript, par exemple."""

    _installer_faux_trafilatura(
        monkeypatch,
        fetch_url=lambda url: "<html>...</html>",
        extract=lambda *a, **k: None,
    )

    resultat = fetch_job_offer_from_url("https://exemple.com/offre")

    assert resultat.success is False
    assert "JavaScript" in resultat.error


# ============================================================
# SUCCES
# ============================================================

def test_une_extraction_reussie_retourne_titre_et_texte(monkeypatch):
    _installer_faux_trafilatura(
        monkeypatch,
        fetch_url=lambda url: "<html>...</html>",
        extract=lambda *a, **k: json.dumps(
            {
                "title": "Product Owner E-commerce",
                "text": "Nous recherchons un Product Owner...",
            }
        ),
    )

    resultat = fetch_job_offer_from_url("https://exemple.com/offre")

    assert resultat.success is True
    assert resultat.title == "Product Owner E-commerce"
    assert "Product Owner" in resultat.text
    assert resultat.error == ""


def test_un_texte_vide_apres_extraction_est_un_echec(monkeypatch):
    _installer_faux_trafilatura(
        monkeypatch,
        fetch_url=lambda url: "<html>...</html>",
        extract=lambda *a, **k: json.dumps({"title": "Titre", "text": "   "}),
    )

    resultat = fetch_job_offer_from_url("https://exemple.com/offre")

    assert resultat.success is False

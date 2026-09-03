"""
Client bas niveau Gemini : logique de nouvelle tentative sur
surcharge temporaire (503).

Aucun appel réseau réel : _get_client() est remplacé par un faux
client dont generate_content() se comporte comme on le décide.
"""

from __future__ import annotations

import pytest

import services.ai.gemini_client as gemini_client
from services.ai.gemini_client import (
    GeminiNotConfiguredError,
    GeminiRequestError,
    _is_transient_overload,
    generate_multimodal,
    generate_text,
)


class _FausseReponse:
    def __init__(self, text: str):
        self.text = text


class _FauxModels:
    """
    Simule client.models.generate_content : appelle une séquence de
    comportements préparés à l'avance, un par appel.
    """

    def __init__(self, comportements):
        self._comportements = list(comportements)
        self.appels = 0

    def generate_content(self, **kwargs):
        self.appels += 1
        comportement = self._comportements.pop(0)

        if isinstance(comportement, Exception):
            raise comportement

        return _FausseReponse(comportement)


class _FauxClient:
    def __init__(self, comportements):
        self.models = _FauxModels(comportements)


def _patch_client(monkeypatch, comportements):
    faux_client = _FauxClient(comportements)
    monkeypatch.setattr(
        gemini_client,
        "_get_client",
        lambda *args, **kwargs: faux_client,
    )
    # Pas d'attente réelle entre les tentatives dans les tests.
    monkeypatch.setattr(gemini_client.time, "sleep", lambda _: None)
    return faux_client


# ============================================================
# CLASSIFICATION DES ERREURS
# ============================================================

@pytest.mark.parametrize(
    "message",
    [
        "503 UNAVAILABLE. High demand.",
        "UNAVAILABLE: try again",
        "Request timed out after 30000ms",
        "Read timeout.",
        "504 DEADLINE_EXCEEDED. Deadline expired.",
    ],
)
def test_une_surcharge_est_reconnue_comme_transitoire(message):
    assert _is_transient_overload(RuntimeError(message))


def test_un_timeout_httpx_est_reconnu_par_son_type(monkeypatch):
    """
    httpx nomme certaines de ses exceptions sans que le mot "timeout"
    apparaisse forcément dans le message : le type de l'exception est
    un filet de sécurité supplémentaire.
    """

    class ReadTimeout(Exception):
        pass

    assert _is_transient_overload(ReadTimeout("délai dépassé"))


@pytest.mark.parametrize(
    "message",
    [
        "404 NOT_FOUND. Model unknown.",
        "401 UNAUTHENTICATED. Invalid API key.",
    ],
)
def test_une_erreur_permanente_n_est_pas_consideree_transitoire(
    message,
):
    assert not _is_transient_overload(RuntimeError(message))


# ============================================================
# NOUVELLE TENTATIVE
# ============================================================

def test_reussit_du_premier_coup_sans_nouvelle_tentative(
    monkeypatch,
):
    faux_client = _patch_client(monkeypatch, ["OK"])

    resultat = generate_text("prompt")

    assert resultat == "OK"
    assert faux_client.models.appels == 1


def test_generate_multimodal_partage_la_meme_logique_de_retentative(
    monkeypatch,
):
    """
    generate_multimodal doit bénéficier du même retry/timeout que
    generate_text — les deux passent par _call_gemini.
    """

    faux_client = _patch_client(
        monkeypatch,
        [
            RuntimeError("503 UNAVAILABLE. High demand."),
            "Réponse multimodale.",
        ],
    )

    resultat = generate_multimodal(["partie 1", "partie 2"])

    assert resultat == "Réponse multimodale."
    assert faux_client.models.appels == 2


def test_reessaie_apres_une_surcharge_puis_reussit(monkeypatch):
    faux_client = _patch_client(
        monkeypatch,
        [
            RuntimeError("503 UNAVAILABLE. High demand."),
            "Réponse obtenue au second essai.",
        ],
    )

    resultat = generate_text("prompt")

    assert resultat == "Réponse obtenue au second essai."
    assert faux_client.models.appels == 2


def test_abandonne_apres_trois_surcharges_successives(monkeypatch):
    faux_client = _patch_client(
        monkeypatch,
        [RuntimeError("503 UNAVAILABLE.")] * 3,
    )

    with pytest.raises(GeminiRequestError):
        generate_text("prompt")

    assert faux_client.models.appels == 3


def test_une_erreur_permanente_n_est_jamais_retentee(monkeypatch):
    """
    Une clé invalide ne se résoudra pas en insistant : inutile de
    perdre du temps à réessayer.
    """

    faux_client = _patch_client(
        monkeypatch,
        [
            RuntimeError("401 UNAUTHENTICATED. Invalid API key."),
            "ne devrait jamais être atteint",
        ],
    )

    with pytest.raises(GeminiRequestError):
        generate_text("prompt")

    assert faux_client.models.appels == 1


def test_une_reponse_vide_est_une_erreur(monkeypatch):
    _patch_client(monkeypatch, ["   "])

    with pytest.raises(GeminiRequestError):
        generate_text("prompt")


def test_sans_client_configure_leve_l_erreur_dediee(monkeypatch):

    def _get_client_sans_cle(*args, **kwargs):
        raise GeminiNotConfiguredError("pas de clé")

    monkeypatch.setattr(
        gemini_client,
        "_get_client",
        _get_client_sans_cle,
    )

    with pytest.raises(GeminiNotConfiguredError):
        generate_text("prompt")

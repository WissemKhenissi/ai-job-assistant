"""
Client bas niveau pour l'API Gemini (Google).

Choix acté le 2 septembre 2026 (voir docs/cadrage_et_feuille_de_route.md,
section 7) : palier gratuit de l'API Gemini, jusqu'à ce qu'un usage
plus intensif justifie une option payante. Appeler cette API envoie le
texte transmis aux serveurs de Google — c'est le compromis de
confidentialité explicitement accepté pour ce choix.

Ce module ne contient aucune logique métier : il sait seulement parler
à l'API. Les garde-fous anti-invention vivent dans reformulation.py.
"""

from __future__ import annotations

import os
import time

from dotenv import load_dotenv

load_dotenv()



# "-latest" plutôt qu'un nom de version épinglé : Google a fait
# migrer les utilisateurs de gemini-2.5-flash vers gemini-3.6-flash
# en cours de session (l'ancien renvoyait un 404 explicite), et
# gemini-3.6-flash s'est révélé plafonné à seulement 20 requêtes
# gratuites/jour — bien plus restrictif que prévu. Le palier "flash
# lite" (optimisé pour le débit) accepte davantage de requêtes
# gratuites ; l'alias "-latest" suit le modèle recommandé du moment
# sans dépendre d'un nom de version qui finira par être déprécié à
# son tour.
GEMINI_MODEL = "gemini-flash-lite-latest"

# Délai maximal d'une requête HTTP individuelle, en millisecondes.
#
# Le SDK n'impose aucune limite par défaut : sous forte demande,
# une requête peut rester bloquée indéfiniment sans jamais renvoyer
# ni réponse ni erreur — observé en conditions réelles (un appel
# resté suspendu plus de 3 minutes). Sans ce délai, la logique de
# nouvelle tentative sur 503 ne sert à rien : elle ne se déclenche
# jamais si l'appel ne se termine jamais.
GEMINI_TIMEOUT_MS = 30_000

# Un enregistrement de plusieurs minutes (le candidat qui répond à
# toutes les questions d'un coup à l'oral) est nettement plus long à
# téléverser et à traiter qu'un prompt texte : 30 s ne suffisent pas,
# et l'appel échouerait systématiquement sans que la cause soit
# évidente pour l'utilisateur.
GEMINI_AUDIO_TIMEOUT_MS = 180_000

# Lire un CV entier et le restituer en JSON structuré produit
# beaucoup plus de texte qu'une reformulation de puce. Mesuré sur dix
# CV inventés : 30 s échouaient dans **dix cas sur dix**, en 504
# DEADLINE_EXCEEDED, et l'utilisateur ne voyait qu'une extraction
# vide sans comprendre pourquoi.
GEMINI_LONG_TIMEOUT_MS = 120_000

# Attentes entre deux tentatives, en secondes. L'ancien barème
# (2 s puis 4 s) abandonnait après six secondes d'attente cumulée :
# beaucoup trop court face à un « 503 high demand », qui dure
# couramment plusieurs dizaines de secondes. Observé en rafale sur
# dix lectures de CV — huit échecs, tous après six secondes.
ATTENTES_ENTRE_TENTATIVES = (2, 6, 15)


class GeminiNotConfiguredError(RuntimeError):
    """Aucune clé GEMINI_API_KEY n'est configurée dans .env."""


class GeminiRequestError(RuntimeError):
    """L'appel à l'API Gemini a échoué (réseau, quota, réponse vide...)."""


def is_configured() -> bool:
    """True si une clé API est présente dans l'environnement."""

    return bool(os.environ.get("GEMINI_API_KEY", "").strip())


def _get_client(timeout_ms: int | None = None):

    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()

    if not api_key:
        raise GeminiNotConfiguredError(
            "GEMINI_API_KEY n'est pas configurée. Ajoute ta clé dans "
            ".env (obtenue sur https://aistudio.google.com/apikey) "
            "pour activer la reformulation IA."
        )

    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=timeout_ms or GEMINI_TIMEOUT_MS
        ),
    )


def _is_transient_overload(error: Exception) -> bool:
    """
    503 "high demand" : le palier gratuit en renvoie régulièrement
    sous charge, et ça se résout en général en réessayant. Une clé
    invalide ou un modèle inconnu, à l'inverse, ne se résoudront
    jamais en insistant.
    """

    texte_erreur_minuscules = str(error).lower()
    nom_type_erreur = type(error).__name__

    return (
        "503" in texte_erreur_minuscules
        or "504" in texte_erreur_minuscules
        or "unavailable" in texte_erreur_minuscules
        or "deadline" in texte_erreur_minuscules
        or "timeout" in texte_erreur_minuscules
        or "timed out" in texte_erreur_minuscules
        or "Timeout" in nom_type_erreur
    )


def _call_gemini(
    contents,
    temperature: float,
    timeout_ms: int | None = None,
) -> str:
    """
    Envoie `contents` (texte seul, ou liste de parties texte/image
    pour un appel multimodal) à Gemini et retourne le texte de la
    réponse.

    Lève GeminiNotConfiguredError si aucune clé n'est disponible, et
    GeminiRequestError pour toute autre défaillance (réseau, quota
    dépassé, réponse vide) — l'appelant décide alors du repli.

    Jusqu'à trois tentatives supplémentaires en cas de surcharge
    temporaire (503) avant d'abandonner.
    """

    from google.genai import types

    client = _get_client(timeout_ms)

    config = types.GenerateContentConfig(temperature=temperature)

    max_tentatives = len(ATTENTES_ENTRE_TENTATIVES) + 1

    derniere_erreur: Exception = GeminiRequestError(
        "Aucune tentative n'a été effectuée."
    )

    for tentative in range(max_tentatives):

        if tentative > 0:
            time.sleep(ATTENTES_ENTRE_TENTATIVES[tentative - 1])

        try:

            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config=config,
            )

            texte = (response.text or "").strip()

            if not texte:
                raise GeminiRequestError(
                    "L'API Gemini a renvoyé une réponse vide."
                )

            return texte

        except GeminiNotConfiguredError:
            raise

        except Exception as error:

            derniere_erreur = error

            derniere_tentative = tentative == max_tentatives - 1

            if derniere_tentative or not _is_transient_overload(
                error
            ):
                raise GeminiRequestError(
                    f"Échec de l'appel à l'API Gemini : {error}"
                ) from error

    # Inatteignable : la boucle lève ou retourne systématiquement.
    raise GeminiRequestError(
        f"Échec de l'appel à l'API Gemini : {derniere_erreur}"
    ) from derniere_erreur


def generate_text(
    prompt: str,
    temperature: float = 0.4,
    timeout_ms: int | None = None,
) -> str:
    """
    Envoie un prompt texte à Gemini et retourne le texte de la réponse.

    `timeout_ms` desserre le délai par défaut pour les appels qui
    produisent beaucoup de texte : lire un CV entier et le restituer
    en JSON dépasse régulièrement les 30 secondes, et l'échec se
    présentait alors comme une extraction vide.
    """

    return _call_gemini(prompt, temperature, timeout_ms)


def generate_multimodal(
    parts: list,
    temperature: float = 0.4,
    timeout_ms: int | None = None,
) -> str:
    """
    Envoie un contenu multimodal (texte + images) à Gemini et retourne
    le texte de la réponse.

    `parts` est une liste d'objets `google.genai.types.Part`
    (`Part.from_text` pour du texte, `Part.from_bytes` pour une
    image) — construite par l'appelant, ce module ne sait pas d'où
    viennent les images.
    """

    return _call_gemini(parts, temperature, timeout_ms)

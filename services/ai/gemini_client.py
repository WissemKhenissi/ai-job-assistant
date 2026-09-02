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

from dotenv import load_dotenv

load_dotenv()


GEMINI_MODEL = "gemini-2.5-flash"


class GeminiNotConfiguredError(RuntimeError):
    """Aucune clé GEMINI_API_KEY n'est configurée dans .env."""


class GeminiRequestError(RuntimeError):
    """L'appel à l'API Gemini a échoué (réseau, quota, réponse vide...)."""


def is_configured() -> bool:
    """True si une clé API est présente dans l'environnement."""

    return bool(os.environ.get("GEMINI_API_KEY", "").strip())


def _get_client():

    from google import genai

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()

    if not api_key:
        raise GeminiNotConfiguredError(
            "GEMINI_API_KEY n'est pas configurée. Ajoute ta clé dans "
            ".env (obtenue sur https://aistudio.google.com/apikey) "
            "pour activer la reformulation IA."
        )

    return genai.Client(api_key=api_key)


def generate_text(prompt: str, temperature: float = 0.4) -> str:
    """
    Envoie un prompt à Gemini et retourne le texte de la réponse.

    Lève GeminiNotConfiguredError si aucune clé n'est disponible, et
    GeminiRequestError pour toute autre défaillance (réseau, quota
    dépassé, réponse vide) — l'appelant décide alors du repli.
    """

    from google.genai import types

    client = _get_client()

    try:

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
            ),
        )

    except GeminiNotConfiguredError:
        raise

    except Exception as error:

        raise GeminiRequestError(
            f"Échec de l'appel à l'API Gemini : {error}"
        ) from error

    texte = (response.text or "").strip()

    if not texte:
        raise GeminiRequestError(
            "L'API Gemini a renvoyé une réponse vide."
        )

    return texte

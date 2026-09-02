"""
Structures d'une lettre de motivation.

Chaque paragraphe garde la trace des données du Master CV dont il est
issu : une lettre générée doit pouvoir être justifiée ligne à ligne.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class LetterParagraph:
    """
    Un paragraphe de la lettre.

    `sources` contient les identifiants des données du Master CV
    utilisées (preuves, réalisations). Un paragraphe sans source est
    un paragraphe de forme (formule d'appel, politesse), jamais une
    affirmation sur le parcours.
    """

    text: str
    sources: tuple[str, ...] = ()

    @property
    def est_une_affirmation(self) -> bool:
        return bool(self.sources)


@dataclass
class CoverLetter:
    candidate_id: str
    full_name: str
    email: str
    phone: str
    location: str

    job_offer_id: str
    job_offer_title: str
    company: str

    redaction_date: date

    objet: str
    salutation: str
    paragraphs: list[LetterParagraph] = field(default_factory=list)
    closing: str = ""
    signature: str = ""

    # Transparence : ce que la lettre s'interdit d'affirmer.
    claimed_skills: list[str] = field(default_factory=list)
    not_claimed_skills: list[str] = field(default_factory=list)

    # Une lettre générée n'est jamais finale tant que l'utilisateur
    # ne l'a pas relue. Le drapeau n'est pas positionné par le
    # générateur, mais par l'interface après validation explicite.
    validated_by_user: bool = False

    @property
    def body_text(self) -> str:
        return "\n\n".join(
            paragraph.text for paragraph in self.paragraphs
        )

    @property
    def full_text(self) -> str:
        blocs = [
            self.objet,
            self.salutation,
            self.body_text,
            self.closing,
            self.signature,
        ]

        return "\n\n".join(bloc for bloc in blocs if bloc)

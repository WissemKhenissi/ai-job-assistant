"""
Export d'un CV ciblé en DOCX et en PDF.

L'export est une mise en forme : il n'ajoute, ne reformule et ne
complète aucun contenu. Tout ce qui apparaît dans le fichier produit
vient de l'objet TargetedCV, donc du Master CV.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from pathlib import Path

from services.cv.results import TargetedCV


EXPORT_DIR = (
    Path(__file__).resolve().parent.parent.parent / "exports"
)


MOIS = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre",
    "décembre",
)


def _format_periode(
    debut: date,
    fin: date | None,
) -> str:

    def _mois_annee(valeur: date) -> str:
        return f"{MOIS[valeur.month - 1]} {valeur.year}"

    if fin is None:
        return f"{_mois_annee(debut)} → aujourd'hui"

    return f"{_mois_annee(debut)} → {_mois_annee(fin)}"


def _slugify(value: str) -> str:

    normalise = unicodedata.normalize("NFKD", value)

    normalise = "".join(
        caractere
        for caractere in normalise
        if not unicodedata.combining(caractere)
    )

    normalise = re.sub(r"[^a-zA-Z0-9]+", "-", normalise)

    return normalise.strip("-").lower()[:60] or "cv"


def default_export_path(
    cv: TargetedCV,
    extension: str,
) -> Path:
    """
    Chemin de sortie par défaut, stable pour un même CV et une même
    offre : régénérer écrase le fichier au lieu d'en empiler.
    """

    nom = _slugify(cv.full_name)
    poste = _slugify(cv.job_offer_title)

    return EXPORT_DIR / f"cv-{nom}-{poste}.{extension}"


# ============================================================
# DOCX
# ============================================================

def export_docx(
    cv: TargetedCV,
    path: Path | str | None = None,
) -> Path:
    """Écrit le CV ciblé dans un fichier .docx et retourne son chemin."""

    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt

    destination = Path(
        path
        if path is not None
        else default_export_path(cv, "docx")
    )

    destination.parent.mkdir(parents=True, exist_ok=True)

    document = Document()

    # --------------------------------------------------------
    # IDENTITE
    # --------------------------------------------------------

    titre = document.add_heading(cv.full_name, level=0)
    titre.alignment = WD_ALIGN_PARAGRAPH.CENTER

    coordonnees = " • ".join(
        partie
        for partie in (
            cv.location,
            cv.phone,
            cv.email,
            cv.linkedin_url,
        )
        if partie
    )

    if coordonnees:
        paragraphe = document.add_paragraph(coordonnees)
        paragraphe.alignment = WD_ALIGN_PARAGRAPH.CENTER

    if cv.summary:
        document.add_paragraph(cv.summary)

    # --------------------------------------------------------
    # COMPETENCES
    # --------------------------------------------------------
    #
    # Uniquement les compétences prouvées : c'est la garantie
    # d'honnêteté du CV généré.

    if cv.skills:

        document.add_heading("Compétences", level=1)

        document.add_paragraph(" • ".join(cv.skills))

    # --------------------------------------------------------
    # EXPERIENCES
    # --------------------------------------------------------

    if cv.experiences:

        document.add_heading("Expérience professionnelle", level=1)

        for experience in cv.experiences:

            entete = document.add_paragraph()

            titre_poste = entete.add_run(
                f"{experience.job_title} — {experience.company}"
            )
            titre_poste.bold = True

            periode = document.add_paragraph(
                _format_periode(
                    experience.start_date,
                    experience.end_date,
                )
            )

            for run in periode.runs:
                run.italic = True
                run.font.size = Pt(9)

            if experience.business_context:
                document.add_paragraph(
                    experience.business_context
                )

            for ligne in experience.lines:
                document.add_paragraph(
                    ligne.text,
                    style="List Bullet",
                )

    # --------------------------------------------------------
    # REALISATIONS
    # --------------------------------------------------------

    if cv.achievements:

        document.add_heading("Réalisations", level=1)

        for achievement in cv.achievements:

            paragraphe = document.add_paragraph()

            titre_realisation = paragraphe.add_run(
                achievement.title
            )
            titre_realisation.bold = True

            for libelle, valeur in (
                ("Situation", achievement.situation),
                ("Actions", achievement.action),
                ("Résultat", achievement.result),
            ):

                if valeur:
                    document.add_paragraph(
                        f"{libelle} : {valeur}"
                    )

            if achievement.metrics:

                for metrique in achievement.metrics.split("\n"):

                    if metrique.strip():
                        document.add_paragraph(
                            metrique.strip(),
                            style="List Bullet",
                        )

    document.save(str(destination))

    return destination


# ============================================================
# PDF
# ============================================================

def export_pdf(
    cv: TargetedCV,
    path: Path | str | None = None,
) -> Path:
    """Écrit le CV ciblé dans un fichier .pdf et retourne son chemin."""

    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import (
        ParagraphStyle,
        getSampleStyleSheet,
    )
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        ListFlowable,
        ListItem,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
    )

    destination = Path(
        path
        if path is not None
        else default_export_path(cv, "pdf")
    )

    destination.parent.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()

    style_nom = ParagraphStyle(
        "NomCandidat",
        parent=styles["Title"],
        alignment=TA_CENTER,
        spaceAfter=4,
    )

    style_contact = ParagraphStyle(
        "Contact",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontSize=9,
        spaceAfter=12,
    )

    style_periode = ParagraphStyle(
        "Periode",
        parent=styles["Normal"],
        fontSize=9,
        textColor="#555555",
        spaceAfter=4,
    )

    document = SimpleDocTemplate(
        str(destination),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title=f"CV {cv.full_name}",
    )

    elements = [Paragraph(cv.full_name, style_nom)]

    coordonnees = " • ".join(
        partie
        for partie in (
            cv.location,
            cv.phone,
            cv.email,
            cv.linkedin_url,
        )
        if partie
    )

    if coordonnees:
        elements.append(
            Paragraph(coordonnees, style_contact)
        )

    if cv.summary:
        elements.append(
            Paragraph(cv.summary, styles["Normal"])
        )
        elements.append(Spacer(1, 10))

    # --------------------------------------------------------
    # COMPETENCES
    # --------------------------------------------------------

    if cv.skills:

        elements.append(
            Paragraph("Compétences", styles["Heading2"])
        )

        elements.append(
            Paragraph(
                " • ".join(cv.skills),
                styles["Normal"],
            )
        )

        elements.append(Spacer(1, 8))

    # --------------------------------------------------------
    # EXPERIENCES
    # --------------------------------------------------------

    if cv.experiences:

        elements.append(
            Paragraph(
                "Expérience professionnelle",
                styles["Heading2"],
            )
        )

        for experience in cv.experiences:

            elements.append(
                Paragraph(
                    f"<b>{experience.job_title} — "
                    f"{experience.company}</b>",
                    styles["Normal"],
                )
            )

            elements.append(
                Paragraph(
                    _format_periode(
                        experience.start_date,
                        experience.end_date,
                    ),
                    style_periode,
                )
            )

            if experience.business_context:
                elements.append(
                    Paragraph(
                        experience.business_context,
                        styles["Normal"],
                    )
                )

            if experience.lines:
                elements.append(
                    ListFlowable(
                        [
                            ListItem(
                                Paragraph(
                                    ligne.text,
                                    styles["Normal"],
                                )
                            )
                            for ligne in experience.lines
                        ],
                        bulletType="bullet",
                        leftIndent=12,
                    )
                )

            elements.append(Spacer(1, 8))

    # --------------------------------------------------------
    # REALISATIONS
    # --------------------------------------------------------

    if cv.achievements:

        elements.append(
            Paragraph("Réalisations", styles["Heading2"])
        )

        for achievement in cv.achievements:

            elements.append(
                Paragraph(
                    f"<b>{achievement.title}</b>",
                    styles["Normal"],
                )
            )

            for libelle, valeur in (
                ("Situation", achievement.situation),
                ("Actions", achievement.action),
                ("Résultat", achievement.result),
            ):

                if valeur:
                    elements.append(
                        Paragraph(
                            f"{libelle} : {valeur}",
                            styles["Normal"],
                        )
                    )

            metriques = [
                metrique.strip()
                for metrique in (
                    achievement.metrics or ""
                ).split("\n")
                if metrique.strip()
            ]

            if metriques:
                elements.append(
                    ListFlowable(
                        [
                            ListItem(
                                Paragraph(
                                    metrique,
                                    styles["Normal"],
                                )
                            )
                            for metrique in metriques
                        ],
                        bulletType="bullet",
                        leftIndent=12,
                    )
                )

            elements.append(Spacer(1, 8))

    document.build(elements)

    return destination

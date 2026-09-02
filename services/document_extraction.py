"""
Extraction de texte depuis un fichier téléversé (.docx / .pdf).

Purement mécanique, aucune IA : on ne fait qu'assembler le texte déjà
présent dans le document pour le transmettre ensuite comme contexte à
l'entretien IA (services/ai/interview.py). Un échec d'extraction
(fichier corrompu, PDF scanné sans texte) retourne une chaîne vide
plutôt que de lever une exception — l'appelant décide alors comment
réagir (par exemple, inviter à fournir une capture d'écran à la
place).
"""

from __future__ import annotations

import io


def extract_text_from_upload(uploaded_file) -> str:
    """
    Extrait le texte d'un fichier `.docx` ou `.pdf` téléversé via
    `st.file_uploader` (ou tout objet exposant `.name` et `.read()`).

    Retourne une chaîne vide si le format n'est pas géré ou que
    l'extraction échoue — jamais d'exception.
    """

    nom = (getattr(uploaded_file, "name", "") or "").lower()

    donnees = uploaded_file.read()

    if nom.endswith(".docx"):
        return _extract_docx(donnees)

    if nom.endswith(".pdf"):
        return _extract_pdf(donnees)

    return ""


def _extract_docx(donnees: bytes) -> str:

    from docx import Document

    try:
        document = Document(io.BytesIO(donnees))

    except Exception:
        return ""

    return "\n".join(
        paragraphe.text
        for paragraphe in document.paragraphs
        if paragraphe.text.strip()
    )


def _extract_pdf(donnees: bytes) -> str:

    from pypdf import PdfReader

    try:
        lecteur = PdfReader(io.BytesIO(donnees))

    except Exception:
        return ""

    morceaux = []

    for page in lecteur.pages:

        try:
            texte_page = page.extract_text() or ""

        except Exception:
            texte_page = ""

        if texte_page.strip():
            morceaux.append(texte_page)

    return "\n".join(morceaux)

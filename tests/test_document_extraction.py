"""
Extraction de texte depuis un fichier téléversé
(services.document_extraction).

Utilise de vrais fichiers .docx/.pdf générés en mémoire (python-docx,
reportlab, déjà des dépendances du projet) plutôt que des mocks : ce
module ne fait qu'assembler ce qu'une vraie bibliothèque extrait, le
test le plus fiable est donc de lui donner un vrai fichier.
"""

from __future__ import annotations

import io

from services.document_extraction import extract_text_from_upload


class _FauxFichierTeleverse:
    """Imite l'objet retourné par st.file_uploader (.name + .read())."""

    def __init__(self, name: str, donnees: bytes):
        self.name = name
        self._donnees = donnees

    def read(self) -> bytes:
        return self._donnees


def _creer_docx(texte: str) -> bytes:
    from docx import Document

    document = Document()
    document.add_paragraph(texte)

    tampon = io.BytesIO()
    document.save(tampon)

    return tampon.getvalue()


def _creer_pdf(texte: str) -> bytes:
    from reportlab.pdfgen import canvas

    tampon = io.BytesIO()
    dessin = canvas.Canvas(tampon)
    dessin.drawString(100, 750, texte)
    dessin.save()

    return tampon.getvalue()


def test_extrait_le_texte_d_un_docx():
    donnees = _creer_docx("Chef de projet digital chez Groupe Meridiem.")

    fichier = _FauxFichierTeleverse("cv.docx", donnees)

    texte = extract_text_from_upload(fichier)

    assert "Chef de projet digital chez Groupe Meridiem." in texte


def test_extrait_le_texte_d_un_pdf():
    donnees = _creer_pdf("Product Owner E-commerce")

    fichier = _FauxFichierTeleverse("cv.pdf", donnees)

    texte = extract_text_from_upload(fichier)

    assert "Product Owner E-commerce" in texte


def test_un_format_non_gere_retourne_une_chaine_vide():
    fichier = _FauxFichierTeleverse("capture.png", b"donnees-image")

    assert extract_text_from_upload(fichier) == ""


def test_un_fichier_docx_corrompu_ne_leve_pas_d_exception():
    fichier = _FauxFichierTeleverse("cv.docx", b"pas un vrai docx")

    assert extract_text_from_upload(fichier) == ""


def test_un_fichier_pdf_corrompu_ne_leve_pas_d_exception():
    fichier = _FauxFichierTeleverse("cv.pdf", b"pas un vrai pdf")

    assert extract_text_from_upload(fichier) == ""

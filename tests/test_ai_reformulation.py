"""
Reformulation IA (Gemini) du CV et de la lettre.

Aucun test ici n'appelle la vraie API : services.ai.reformulation
importe generate_text/is_configured par leur nom, donc on les
remplace directement dans le module (comme pour
find_semantic_skill_matches dans test_matching_status.py).

Ce qui est vérifié n'est pas la qualité de la reformulation — on ne
peut pas la tester sans clé réelle — mais les garde-fous : ce que le
code fait quand l'IA n'est pas configurée, échoue, ou invente un
chiffre. C'est là que se joue le principe "rien n'est inventé"
appliqué à l'IA.
"""

from __future__ import annotations

from datetime import date

import pytest

import services.ai.reformulation as reformulation
from services.ai.gemini_client import GeminiNotConfiguredError, GeminiRequestError
from services.cv.results import CVEvidenceLine, CVExperience, TargetedCV
from services.cv.vocabulary import OfferVocabulary


JOB_TEXT = "Nous cherchons un profil produit avec de l'expérience e-commerce."


@pytest.fixture(autouse=True)
def vocabulaire_neutre(monkeypatch):
    """
    Le vocabulaire autorisé se calcule en base : sans ce garde-fou de
    test, reformulate_targeted_cv irait interroger la vraie base de
    l'utilisateur. Les tests qui vérifient le vocabulaire posent le
    leur explicitement.
    """

    monkeypatch.setattr(
        reformulation,
        "build_offer_vocabulary",
        lambda *args, **kwargs: OfferVocabulary(),
    )


# ============================================================
# GARDE-FOUS DE _safe_reformulate
# ============================================================

def test_un_texte_vide_n_appelle_pas_l_api(monkeypatch):
    """Rien à reformuler : pas d'appel réseau pour rien."""

    appele = False

    def _generate_text(*args, **kwargs):
        nonlocal appele
        appele = True
        return "peu importe"

    monkeypatch.setattr(reformulation, "is_configured", lambda: True)
    monkeypatch.setattr(reformulation, "generate_text", _generate_text)

    resultat = reformulation._safe_reformulate("   ", "instructions")

    assert resultat.text == "   "
    assert resultat.was_reformulated is False
    assert not appele


def test_sans_cle_configuree_le_texte_source_est_conserve(
    monkeypatch,
):
    monkeypatch.setattr(reformulation, "is_configured", lambda: False)

    resultat = reformulation._safe_reformulate(
        "Pilotage de projets.",
        "instructions",
    )

    assert resultat.text == "Pilotage de projets."
    assert resultat.was_reformulated is False
    assert "GEMINI_API_KEY" in resultat.warning


@pytest.mark.parametrize(
    "erreur",
    [
        GeminiNotConfiguredError("pas de clé"),
        GeminiRequestError("quota dépassé"),
    ],
)
def test_une_erreur_api_fait_replier_sur_le_texte_source(
    monkeypatch,
    erreur,
):
    monkeypatch.setattr(reformulation, "is_configured", lambda: True)

    def _generate_text(*args, **kwargs):
        raise erreur

    monkeypatch.setattr(reformulation, "generate_text", _generate_text)

    resultat = reformulation._safe_reformulate(
        "Pilotage de projets.",
        "instructions",
    )

    assert resultat.text == "Pilotage de projets."
    assert resultat.was_reformulated is False
    assert resultat.warning


def test_une_reformulation_sans_nouveau_chiffre_est_acceptee(
    monkeypatch,
):
    monkeypatch.setattr(reformulation, "is_configured", lambda: True)

    monkeypatch.setattr(
        reformulation,
        "generate_text",
        lambda *a, **k: "Pilotage de projets digitaux à fort enjeu.",
    )

    resultat = reformulation._safe_reformulate(
        "Pilotage de projets.",
        "instructions",
    )

    assert resultat.text == "Pilotage de projets digitaux à fort enjeu."
    assert resultat.was_reformulated is True
    assert resultat.warning == ""


def test_un_chiffre_invente_fait_rejeter_la_reformulation(
    monkeypatch,
):
    """
    Le garde-fou central : si l'IA introduit un chiffre absent du
    texte source (un pourcentage, une durée, un montant inventé),
    la reformulation est rejetée et le texte déterministe est gardé.
    """

    monkeypatch.setattr(reformulation, "is_configured", lambda: True)

    monkeypatch.setattr(
        reformulation,
        "generate_text",
        lambda *a, **k: "Marge publicitaire portée à 40 % de croissance.",
    )

    resultat = reformulation._safe_reformulate(
        "Marge publicitaire passée de 1,4 M€ à 2,5 M€.",
        "instructions",
    )

    assert resultat.text == "Marge publicitaire passée de 1,4 M€ à 2,5 M€."
    assert resultat.was_reformulated is False
    assert "40" in resultat.warning


def test_un_chiffre_deja_present_ne_declenche_pas_le_garde_fou(
    monkeypatch,
):
    """
    Réutiliser un chiffre déjà présent dans le texte source (même
    reformulé autour) ne doit pas être pris pour une invention.
    """

    monkeypatch.setattr(reformulation, "is_configured", lambda: True)

    monkeypatch.setattr(
        reformulation,
        "generate_text",
        lambda *a, **k: (
            "Une marge portée de 1,4 M€ à 2,5 M€, soit une forte "
            "progression."
        ),
    )

    resultat = reformulation._safe_reformulate(
        "Marge publicitaire passée de 1,4 M€ à 2,5 M€.",
        "instructions",
    )

    assert resultat.was_reformulated is True


# ============================================================
# CV CIBLE
# ============================================================

def _cv_de_test() -> TargetedCV:
    return TargetedCV(
        candidate_id="candidate-test",
        full_name="Wissem Khenissi",
        email="test@example.com",
        phone="",
        location="",
        linkedin_url="",
        summary="Profil produit avec 7 ans d'expérience e-commerce.",
        headline="Product Owner Digital",
        job_offer_id="job-test",
        job_offer_title="Product Owner",
        skills=["Product Discovery"],
        experiences=[
            CVExperience(
                experience_id="experience-test",
                job_title="Chef de projet",
                company="Groupe Meridiem",
                location="Ivry-sur-Seine",
                start_date=date(2018, 1, 1),
                end_date=date(2024, 12, 31),
                business_context="",
                lines=[
                    CVEvidenceLine(
                        text="Conception de produits digitaux.",
                        skill="Product Discovery",
                        evidence_id="evidence-1",
                    )
                ],
            )
        ],
    )


def test_reformulate_targeted_cv_preserve_skill_et_evidence_id(
    monkeypatch,
):
    monkeypatch.setattr(reformulation, "is_configured", lambda: True)

    monkeypatch.setattr(
        reformulation,
        "generate_text",
        lambda *a, **k: "Conception de produits digitaux à fort trafic.",
    )

    cv = _cv_de_test()

    cv_reformule, _avertissements = (
        reformulation.reformulate_targeted_cv(cv, JOB_TEXT)
    )

    ligne = cv_reformule.experiences[0].lines[0]

    assert ligne.text == "Conception de produits digitaux à fort trafic."
    assert ligne.skill == "Product Discovery"
    assert ligne.evidence_id == "evidence-1"


def test_reformulate_targeted_cv_rejette_un_chiffre_invente(
    monkeypatch,
):
    monkeypatch.setattr(reformulation, "is_configured", lambda: True)

    monkeypatch.setattr(
        reformulation,
        "generate_text",
        lambda *a, **k: "Conception ayant généré 25 % de trafic en plus.",
    )

    cv = _cv_de_test()

    cv_reformule, avertissements = (
        reformulation.reformulate_targeted_cv(cv, JOB_TEXT)
    )

    ligne = cv_reformule.experiences[0].lines[0]

    assert ligne.text == "Conception de produits digitaux."
    assert avertissements


def test_reformulate_targeted_cv_reformule_aussi_le_resume(
    monkeypatch,
):
    monkeypatch.setattr(reformulation, "is_configured", lambda: True)

    monkeypatch.setattr(
        reformulation,
        "generate_text",
        lambda *a, **k: "Résumé reformulé sans nouveau chiffre.",
    )

    cv = _cv_de_test()

    cv_reformule, _avertissements = (
        reformulation.reformulate_targeted_cv(cv, JOB_TEXT)
    )

    assert cv_reformule.summary == "Résumé reformulé sans nouveau chiffre."


# ============================================================
# RESUME DU CV
# ============================================================

def test_reformulate_cv_summary_sans_nouveau_chiffre_est_accepte(
    monkeypatch,
):
    monkeypatch.setattr(reformulation, "is_configured", lambda: True)

    monkeypatch.setattr(
        reformulation,
        "generate_text",
        lambda *a, **k: (
            "Profil produit orienté e-commerce, 7 ans d'expérience."
        ),
    )

    resultat = reformulation.reformulate_cv_summary(
        "Profil produit avec 7 ans d'expérience e-commerce.",
        "Product Owner Digital",
        JOB_TEXT,
    )

    assert resultat.was_reformulated is True
    assert "7 ans" in resultat.text


def test_reformulate_cv_summary_rejette_un_chiffre_invente(
    monkeypatch,
):
    monkeypatch.setattr(reformulation, "is_configured", lambda: True)

    monkeypatch.setattr(
        reformulation,
        "generate_text",
        lambda *a, **k: "Profil produit avec 12 ans d'expérience.",
    )

    resultat = reformulation.reformulate_cv_summary(
        "Profil produit avec 7 ans d'expérience e-commerce.",
        "",
        JOB_TEXT,
    )

    assert resultat.was_reformulated is False
    assert resultat.text == "Profil produit avec 7 ans d'expérience e-commerce."


# ============================================================
# GARDE-FOU DE VOCABULAIRE
# ============================================================
#
# Les chiffres protègent des faits inventés ; les termes protègent des
# compétences inventées. Sans ce second contrôle, « adapte-toi au
# vocabulaire de l'offre » suffirait à faire écrire au modèle une
# compétence que le candidat ne possède pas.

VOCABULAIRE = OfferVocabulary(
    authorized=("Product Discovery",),
    forbidden=("Kubernetes", "SQL"),
)


def test_un_terme_non_prouve_fait_rejeter_la_reformulation(monkeypatch):
    monkeypatch.setattr(reformulation, "is_configured", lambda: True)

    monkeypatch.setattr(
        reformulation,
        "generate_text",
        lambda *a, **k: "Conception de produits digitaux, requêtes SQL.",
    )

    resultat = reformulation.reformulate_cv_line(
        "Conception de produits digitaux.",
        JOB_TEXT,
        VOCABULAIRE,
    )

    assert resultat.was_reformulated is False
    assert resultat.text == "Conception de produits digitaux."
    assert "SQL" in resultat.warning


def test_un_terme_autorise_ne_declenche_pas_le_garde_fou(monkeypatch):
    """
    Employer le mot de l'annonce est le but recherché — tant que le
    référentiel le relie à une compétence réellement prouvée.
    """

    monkeypatch.setattr(reformulation, "is_configured", lambda: True)

    monkeypatch.setattr(
        reformulation,
        "generate_text",
        lambda *a, **k: "Product Discovery sur des produits digitaux.",
    )

    resultat = reformulation.reformulate_cv_line(
        "Conception de produits digitaux.",
        JOB_TEXT,
        VOCABULAIRE,
    )

    assert resultat.was_reformulated is True


def test_un_terme_deja_present_dans_la_source_n_est_pas_reproche(
    monkeypatch,
):
    """
    Si le Master CV parle déjà de SQL, le retirer reviendrait à
    censurer le candidat plutôt qu'à le protéger.
    """

    monkeypatch.setattr(reformulation, "is_configured", lambda: True)

    monkeypatch.setattr(
        reformulation,
        "generate_text",
        lambda *a, **k: "Extraction de données via des requêtes SQL.",
    )

    resultat = reformulation.reformulate_cv_line(
        "Requêtes SQL sur l'entrepôt de données.",
        JOB_TEXT,
        VOCABULAIRE,
    )

    assert resultat.was_reformulated is True


def test_un_terme_interdit_n_est_pas_reconnu_dans_un_mot_plus_long(
    monkeypatch,
):
    """
    « SQL » ne doit pas se reconnaître dans « SQLite » : un garde-fou
    qui se déclenche à tort ferait perdre toutes les reformulations.
    """

    monkeypatch.setattr(reformulation, "is_configured", lambda: True)

    monkeypatch.setattr(
        reformulation,
        "generate_text",
        lambda *a, **k: "Conception d'une base embarquée SQLite.",
    )

    resultat = reformulation.reformulate_cv_line(
        "Conception d'une base SQLite.",
        JOB_TEXT,
        VOCABULAIRE,
    )

    assert resultat.was_reformulated is True


def test_le_prompt_annonce_les_termes_autorises_et_interdits(monkeypatch):
    monkeypatch.setattr(reformulation, "is_configured", lambda: True)

    prompts: list[str] = []

    def _generate_text(prompt, *args, **kwargs):
        prompts.append(prompt)
        return "Conception de produits digitaux."

    monkeypatch.setattr(reformulation, "generate_text", _generate_text)

    reformulation.reformulate_cv_line(
        "Conception de produits digitaux.",
        JOB_TEXT,
        VOCABULAIRE,
    )

    prompt = prompts[0]

    assert "VOCABULAIRE AUTORISÉ" in prompt
    assert "Product Discovery" in prompt
    assert "TERMES INTERDITS" in prompt
    assert "Kubernetes" in prompt


def test_la_reformulation_appelle_le_modele_a_basse_temperature(
    monkeypatch,
):
    """
    Reformuler, c'est redire la même chose autrement : la créativité
    n'y apporte que de l'enjolivement, et un essai à 0.4 avait ajouté
    au résumé une compétence pourtant absente du texte source.
    """

    monkeypatch.setattr(reformulation, "is_configured", lambda: True)

    recus: list[float] = []

    def _generate_text(prompt, temperature=None, *args, **kwargs):
        recus.append(temperature)
        return "Conception de produits digitaux."

    monkeypatch.setattr(reformulation, "generate_text", _generate_text)

    reformulation._safe_reformulate("Texte source.", "instructions")

    assert recus == [reformulation.REFORMULATION_TEMPERATURE]
    assert reformulation.REFORMULATION_TEMPERATURE <= 0.2


def test_sans_vocabulaire_la_reformulation_reste_possible(monkeypatch):
    """
    Une offre non analysée ne doit pas empêcher de reformuler : les
    autres garde-fous continuent de s'appliquer.
    """

    monkeypatch.setattr(reformulation, "is_configured", lambda: True)

    monkeypatch.setattr(
        reformulation,
        "generate_text",
        lambda *a, **k: "Conception de produits digitaux ambitieux.",
    )

    resultat = reformulation.reformulate_cv_line(
        "Conception de produits digitaux.",
        JOB_TEXT,
    )

    assert resultat.was_reformulated is True


# ============================================================
# SECONDE CHANCE APRES REJET
# ============================================================

def test_une_seconde_tentative_est_donnee_apres_un_rejet(monkeypatch):
    """
    Sans reprise, un seul mot de trop faisait retomber la phrase sur
    sa version déterministe : la section n'était alors plus adaptée
    du tout à l'annonce.
    """

    monkeypatch.setattr(reformulation, "is_configured", lambda: True)

    reponses = [
        "Expert en pilotage de projets digitaux.",
        "Pilotage de projets digitaux de bout en bout.",
    ]

    monkeypatch.setattr(
        reformulation,
        "generate_text",
        lambda *a, **k: reponses.pop(0),
    )

    resultat = reformulation._safe_reformulate(
        "Pilotage de projets digitaux.",
        "instructions",
    )

    assert resultat.was_reformulated is True
    assert resultat.text == "Pilotage de projets digitaux de bout en bout."
    assert resultat.warning == ""


def test_la_seconde_tentative_recoit_le_motif_du_refus(monkeypatch):
    monkeypatch.setattr(reformulation, "is_configured", lambda: True)

    prompts: list[str] = []

    def _generate_text(prompt, *args, **kwargs):
        prompts.append(prompt)
        return "Expert en pilotage de projets digitaux."

    monkeypatch.setattr(reformulation, "generate_text", _generate_text)

    reformulation._safe_reformulate(
        "Pilotage de projets digitaux.",
        "instructions",
    )

    assert len(prompts) == 2
    assert "REFUSÉE" in prompts[1]
    assert "expert" in prompts[1]


def test_deux_echecs_de_suite_font_garder_le_texte_source(monkeypatch):
    monkeypatch.setattr(reformulation, "is_configured", lambda: True)

    appels: list[int] = []

    def _generate_text(*args, **kwargs):
        appels.append(1)
        return "Marge en hausse de 79 %."

    monkeypatch.setattr(reformulation, "generate_text", _generate_text)

    resultat = reformulation._safe_reformulate(
        "Marge publicitaire en progression.",
        "instructions",
    )

    assert len(appels) == 2
    assert resultat.was_reformulated is False
    assert resultat.text == "Marge publicitaire en progression."
    assert "79" in resultat.warning


# ============================================================
# GARDE-FOU DE SENIORITE
# ============================================================

def test_un_niveau_rehausse_fait_rejeter_la_reformulation(monkeypatch):
    """
    Cas observé en réel : le Master CV dit « une expérience de
    pilotage », la reformulation renvoyait « Expert en pilotage ».
    Ni chiffre ni nom de compétence : les deux autres garde-fous
    laissaient passer.
    """

    monkeypatch.setattr(reformulation, "is_configured", lambda: True)

    monkeypatch.setattr(
        reformulation,
        "generate_text",
        lambda *a, **k: "Expert en pilotage de projets digitaux.",
    )

    resultat = reformulation._safe_reformulate(
        "Une expérience de pilotage de projets digitaux.",
        "instructions",
    )

    assert resultat.was_reformulated is False
    assert "expert" in resultat.warning


def test_un_niveau_deja_annonce_reste_permis(monkeypatch):
    """
    Un candidat réellement responsable d'une équipe doit pouvoir le
    rester après reformulation.
    """

    monkeypatch.setattr(reformulation, "is_configured", lambda: True)

    monkeypatch.setattr(
        reformulation,
        "generate_text",
        lambda *a, **k: "Responsable de l'équipe produit, à Paris.",
    )

    resultat = reformulation._safe_reformulate(
        "Responsable d'une équipe produit.",
        "instructions",
    )

    assert resultat.was_reformulated is True


# ============================================================
# REPETITIONS (§42)
# ============================================================

def test_les_ouvertures_deja_employees_sont_transmises(monkeypatch):
    """
    Chaque ligne était jusqu'ici reformulée sans connaître les autres :
    rien n'empêchait le modèle d'ouvrir trois puces par « Pilotage ».
    """

    monkeypatch.setattr(reformulation, "is_configured", lambda: True)

    prompts: list[str] = []

    def _generate_text(prompt, *args, **kwargs):
        prompts.append(prompt)
        return "Pilotage de produits digitaux, sans nouveau chiffre."

    monkeypatch.setattr(reformulation, "generate_text", _generate_text)

    cv = _cv_de_test()

    cv.experiences[0].lines.append(
        CVEvidenceLine(
            text="Animation des rituels agiles.",
            skill="Product Discovery",
            evidence_id="evidence-2",
        )
    )

    reformulation.reformulate_targeted_cv(cv, JOB_TEXT)

    # prompts[0] = résumé, prompts[1] = 1re ligne, prompts[2] = 2e.
    assert "RÉPÉTITIONS À ÉVITER" not in prompts[1]
    assert "RÉPÉTITIONS À ÉVITER" in prompts[2]
    assert "pilotage" in prompts[2]


def test_un_echec_du_vocabulaire_est_signale_sans_bloquer(monkeypatch):
    monkeypatch.setattr(reformulation, "is_configured", lambda: True)

    monkeypatch.setattr(
        reformulation,
        "generate_text",
        lambda *a, **k: "Conception de produits digitaux à fort trafic.",
    )

    def _echoue(*args, **kwargs):
        raise RuntimeError("base indisponible")

    monkeypatch.setattr(
        reformulation, "build_offer_vocabulary", _echoue
    )

    cv_reformule, avertissements = (
        reformulation.reformulate_targeted_cv(_cv_de_test(), JOB_TEXT)
    )

    assert any("Vocabulaire" in item for item in avertissements)
    assert (
        cv_reformule.experiences[0].lines[0].text
        == "Conception de produits digitaux à fort trafic."
    )

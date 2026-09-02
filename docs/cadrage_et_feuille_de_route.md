# AI Job Assistant — Cadrage et feuille de route

*Document établi le 2 septembre 2026, à partir du rapport de reprise du 1er septembre 2026 et d'une session de recadrage. Complété le 2 septembre 2026 (soir) avec la décision sur le choix du LLM et une note V2 sur la solution IA pour un produit grand public.*

---

## 1. Finalité du projet

L'application n'est pas un simple générateur de CV : c'est un outil personnel qui transforme un Master CV structuré en un assistant de recherche d'emploi honnête, pour Wissem Khenissi (positionnement Product Owner / Product Manager / Chef de projet IT / PMO).

Le parcours cible :

```text
Master CV structuré
    ↓
Offre d'emploi collée
    ↓
Extraction des compétences demandées
    ↓
Matching explicable (prouvé / déduit / manquant)
    ↓
CV ciblé + lettre de motivation
    ↓
Suivi automatique de la candidature
```

Trois principes portent l'ensemble du projet :

1. **Le Master CV est la seule source de vérité.** Rien n'est inventé — ni compétence, ni expérience, ni réalisation.
2. **Le matching doit être honnête, pas flatteur.** Une compétence déduite reste une hypothèse, jamais un fait affirmé.
3. **Chaque candidature laisse une trace.** Ce qui a été généré et envoyé doit rester retrouvable.

---

## 2. Portée retenue pour cette première étape (V1 — projet personnel)

Décision de cadrage : on construit d'abord un outil **pour un usage personnel**, avant d'envisager une éventuelle V2 destinée à d'autres utilisateurs.

La V1 couvre :

- Le moteur de matching existant (Master CV ↔ offre), **stabilisé et testé**.
- La **génération d'un CV ciblé** à partir du Master CV et du résultat de matching.
- La **génération d'une lettre de motivation** personnalisée.
- Un **suivi de candidature** créé automatiquement à chaque génération de CV/lettre.

Rien d'autre n'est développé tant que ces quatre briques ne sont pas fiables.

---

## 3. Explicitement hors périmètre de la V1 (backlog V2 — produit grand public)

Le document de vision élargie ("Career Intelligence Platform") reste une **carte de référence à long terme**, pas un plan d'exécution actuel. Sont repoussés à une éventuelle V2 :

- Career DNA complet (profil humain, préférences, motivations, frustrations, personnalité professionnelle).
- Orientation métier, compétences transférables à grande échelle, séniorité par dimension.
- Career Value Score, analyse de salaire, salary gap/upside, simulateur what-if.
- Training Recommendation Engine.
- Side Business Engine.
- Market Intelligence (données marché, demande, concurrence).
- Interview Preparation, STAR Evidence automatisé, Career Analytics.
- Feedback Loop (apprentissage à partir des résultats de candidature).
- Authentification, multi-utilisateur, séparation User/Candidate.
- Migration technique PostgreSQL / FastAPI / React-Next.js.
- RAG, connecteurs job boards, lecture automatique d'emails.
- **Solution IA de reformulation adaptée à un produit grand public** (ajouté le 2 septembre 2026, en réponse à une question exploratoire — pas une décision d'implémentation). Le choix fait pour la V1 (Gemini, palier gratuit) ne tient pas à l'échelle :
  - Ollama en local devient inapproprié : hébergé pour tous les utilisateurs, il perd son avantage de confidentialité (les données de tous les utilisateurs transiteraient par des serveurs centraux, sous la responsabilité RGPD de l'éditeur) et impose un coût GPU dédié.
  - Les paliers gratuits (Gemini, Groq) sont dimensionnés pour un seul compte/projet, pas pour un produit — le quota serait épuisé en quelques heures avec plusieurs dizaines d'utilisateurs actifs.
  - À cette échelle, le critère change : coût par génération × nombre d'utilisateurs, politique de non-entraînement sur les données contractuelle, conformité RGPD/localisation des données (Mistral, hébergement France/UE, est un candidat pertinent pour cet argument même si ce n'est pas l'option la moins chère).
  - Implique une architecture différente : clé API strictement côté serveur, comptage d'usage par utilisateur, et un modèle économique (freemium avec quota, abonnement...) qui absorbe le coût — à trancher avec le reste de la bascule V2, pas isolément.
- **Récupération fiable du contenu d'une annonce depuis un lien, tous sites confondus** (ajouté le 2 septembre 2026, après test réel). La version V1 (téléchargement HTTP simple + extraction de texte, sans IA) fonctionne sur les pages au contenu statique, mais échoue sur la plupart des grands jobboards (LinkedIn en tête, qui bloque activement ce type de requête et charge son contenu en JavaScript). Une version fiable demanderait un rendu JavaScript complet (navigateur headless) voire une intégration officielle par site — hors périmètre V1, le copier-coller manuel reste la solution.
- **Entretien vocal pour enrichir le Master CV** (ajouté le 2 septembre 2026). Recueillir les informations du candidat par chat vocal retranscrit, pour l'aider à prendre le temps de développer ses expériences à l'oral plutôt qu'à l'écrit — explicitement noté par l'utilisateur comme pouvant attendre une V2, une fois le mécanisme d'entretien textuel (voir Phase 5) éprouvé.

Ces éléments ne sont pas abandonnés : ils constituent le backlog de la V2, à réévaluer une fois la V1 stable et testée.

---

## 4. Principes non négociables

- Ne jamais inventer une compétence, une expérience ou une réalisation.
- Une compétence **déduite** n'est jamais affichée comme une compétence affirmée sur un CV généré. Seules les compétences **prouvées** (avec une preuve `EvidenceDB` liée) peuvent apparaître comme ligne de compétence explicite.
- Toute génération (CV, lettre) doit rester traçable jusqu'à une donnée du Master CV.
- Une lettre générée par IA doit être **validée par l'utilisateur** avant d'être considérée comme finale. Aucun envoi automatique.
- Le profil reste local ; tout appel à une IA externe pour la reformulation de lettre est un choix explicite à valider au moment venu (confidentialité des données personnelles). **Décidé le 2 septembre 2026 : Gemini (API Google, palier gratuit) pour la V1** — voir section 7.
- `skill_catalog` devient l'unique source de vérité pour la normalisation des compétences — fin du dictionnaire `SKILL_ALIASES` dupliqué dans `matching_service.py`.

---

## 5. Plan de phases

### Phase 0 — Stabilité opérationnelle

- Arrêter toutes les instances Streamlit actives.
- Lancer une seule instance depuis la racine (`streamlit run .\app.py`).
- Vérifier que l'application testée est bien celle servie sur le bon port.

### Phase 1 — Fondations : base de données, migrations, source de vérité

- Corriger `alembic/env.py` pour importer `database.model_registry`.
- Décider d'une stratégie Alembic : reconstruire proprement l'historique en dev, ou figer l'existant et ne créer que des migrations prospectives.
- Nettoyer ou désélectionner les offres de démonstration qui polluent la mémoire de marché.
- Unifier `skill_catalog` comme référentiel unique de compétences (alias, relations, exclusions).

### Phase 2 — Refactor du matching + couche de tests

- Découper `matching_service.py` en sous-modules (ex. `skill_matching`, `semantic_matching`, `composite_skills`, `scoring`, `explanations`).
- Corriger le bug identifié de double calcul de `score_experience`.
- Ajouter une table `job_skill_matches` pour historiser le détail par compétence (score individuel, explication, preuves) — aujourd'hui perdu après l'analyse.
- Construire un dataset de test (annonce + compétences attendues + résultat attendu) et mesurer precision / recall / faux positifs.
- Couvrir en priorité par des tests unitaires : normalisation des accents/alias, exclusion des compétences techniques de l'inférence sémantique, statut `proven` avec et sans preuve, mémoire de marché à 0/1/2/3 annonces.

### Phase 3 — Génération CV / lettre + suivi de candidature

- **Générateur de CV ciblé** : sélection déterministe des expériences, réalisations et preuves pertinentes à partir du résultat de matching. Seules les compétences au statut `proven` apparaissent comme compétences listées.
- **Générateur de lettre de motivation** : squelette assemblé à partir du Master CV et de l'offre, puis reformulation IA légère, avec validation obligatoire de l'utilisateur avant finalisation.
- Export DOCX / PDF (dépendances déjà présentes : `python-docx`, `reportlab`).
- Nouvelle table `applications` : `candidate_id`, `job_offer_id`, date, texte et lien de l'offre, fichier CV généré, fichier lettre générée, statut. **Créée automatiquement** dès qu'un CV et une lettre sont générés pour une offre.
- Les statuts suivants (entretien, réponse, refus, etc.) sont mis à jour manuellement dans l'interface — pas de lecture automatique d'emails en V1.

### Phase 4 — Qualité de sortie (ajoutée le 2 septembre 2026)

- ~~Reformulation IA (Gemini) du CV et de la lettre, contrainte à reformuler le contenu déjà sélectionné sans y ajouter de compétence, chiffre ou fait absent du texte source.~~ **Fait, puis dépassé le 2 septembre 2026** : après test réel, la reformulation paragraphe par paragraphe s'est révélée insuffisante (elle ne fait que polir des formules déjà pauvres). Remplacée pour la lettre par une **rédaction IA complète** (`services/ai/letter_authoring.py`) : Gemini compose l'argumentaire à partir d'une fiche de faits structurée (Master CV + motivations + analyse de matching + offre), avec un garde-fou numérique sur l'ensemble de la fiche et un panneau des faits affiché à l'écran pour la relecture humaine. Le CV garde la reformulation légère (résumé + lignes de preuve), le contenu factuel restant sélectionné déterministiquement.
- **Ajouté le 2 septembre 2026** : champ `motivations` sur le profil candidat (reconversion, intérêt pour un secteur ou une entreprise) — collecté via une vraie UI de profil (`ui/profile_page.py`, qui n'existait pas avant), et seule source utilisée par la lettre pour parler de motivation personnelle.
- **Ajouté le 2 septembre 2026** : sections du CV activables/désactivables à l'export (Profil, Compétences, Expériences, Formation & certifications, Langues, Centres d'intérêt) — le candidat choisit, par candidature, ce qui reste pertinent à montrer.
- **Ajouté le 2 septembre 2026** : page "Mes candidatures" réorganisée en onglets (`ui/job_matching/`, éclaté depuis un fichier unique de 880 lignes) — Nouvelle annonce / CV & lettre / Suivi / Mémoire de marché.
- CV limité à une page, avec un budget de contenu qui remplit la page au mieux sans jamais la dépasser. **Toujours ouvert.**
- Validation explicite d'une compétence déclarée sans preuve par l'utilisateur lui-même (son attestation, pas une invention du système) pour qu'elle devienne utilisable par le générateur. **Toujours ouvert.**
- Suggestions de compétences déduites du parcours, soumises à validation utilisateur avant d'entrer au Master CV. **Toujours ouvert** — voir Phase 5, qui l'englobe dans un mécanisme plus large.

### Phase 5 — Entretien IA d'enrichissement du Master CV (brainstorm ouvert le 2 septembre 2026)

Constat déclencheur : construire un Master CV riche et honnête à la seule initiative du candidat plafonne vite — on oublie des expériences, on sous-décrit ce qu'on a fait, on ne pense pas à formuler une compétence qu'on possède réellement. L'utilisateur demande :

- Une seule page regroupant profil, expériences et compétences (aujourd'hui trois pages séparées dans `app.py`), pour construire/enrichir le Master CV en un seul endroit.
- Une IA (Gemini) qui analyse le profil/CV envoyé et pose les questions de relance les plus pertinentes, expérience par expérience, jusqu'à ce que continuer n'apporte plus de valeur.
- Que l'IA "creuse" chaque expérience pour suggérer des compétences et des éléments d'expérience plausibles mais non explicitement mentionnés — **jamais ajoutés directement** : ce sont des suggestions soumises à validation explicite, exactement comme pour les compétences déduites (voir ci-dessus) et par cohérence avec le principe "rien n'est inventé" (une suggestion validée par le candidat devient un fait qu'il atteste, pas une invention du système).
- Explicitement repoussé en V2 par l'utilisateur lui-même : la collecte par **chat vocal retranscrit**, pour que le candidat soit à l'aise et prenne le temps de développer à l'oral. Le mécanisme d'entretien (textuel, V1) doit être conçu pour ne pas dépendre de la modalité de saisie, afin qu'ajouter la voix en V2 n'implique pas de le refondre.

**Fait le 2 septembre 2026**, après brainstorm avec l'utilisateur (préférence confirmée : largeur plutôt que profondeur — un éventail de questions couvrant plusieurs expériences et le poste recherché, pas un dialogue adaptatif expérience par expérience) :

- Page unique "Mon Master CV" (`ui/master_cv/`), qui remplace les trois anciennes pages.
- Entretien IA en un seul round (`services/ai/interview.py`) : poste recherché optionnel, upload optionnel de CV externe (`.pdf`/`.docx`, texte extrait par `services/document_extraction.py`) et de captures d'écran (`.png`/`.jpg`, transmises à Gemini en pièces multimodales via `services/ai/gemini_client.generate_multimodal`, sans OCR local) → génération d'un éventail large de questions (8 à 15) couvrant plusieurs expériences → réponses libres, aucune obligatoire → propositions de preuves reformulées à partir des réponses données, chacune éditable et validée une par une avant d'écrire en base (`SkillDB`/`EvidenceDB`, mécanisme existant — aucun nouveau statut, aucune nouvelle table).
- Garde-fou principal : toute proposition dont l'extrait source cité par l'IA n'est pas retrouvé mot pour mot dans une réponse réellement donnée est rejetée automatiquement avant même d'être affichée.
- Vérifié en conditions réelles (clé Gemini) : 10 questions générées couvrant les 3 expériences du Master CV + le poste recherché indiqué, réponse à une question ayant produit 3 propositions distinctes et correctement tracées, validation écrivant réellement une nouvelle compétence prouvée.
- Chat vocal retranscrit : toujours backlog V2, comme prévu — le mécanisme textuel ne dépend d'aucune modalité de saisie particulière.

---

## 6. Décisions de conception actées lors du cadrage

- La table `applications` se relie à `job_offers` existante plutôt que de dupliquer les informations de l'offre.
- Pas d'automatisation par lecture d'emails pour le suivi de candidature en V1 — ça nécessiterait un connecteur externe, explicitement hors périmètre.
- La lettre de motivation peut être générée de deux façons, toujours soumises à validation avant d'être considérées comme finales : un squelette déterministe (zéro invention, toujours disponible sans IA) ou une rédaction complète par Gemini à partir d'une fiche de faits (repli automatique sur le déterministe en cas d'échec ou de garde-fou déclenché).

---

## 7. Points ouverts à trancher plus tard

- ~~Choix du LLM pour la reformulation de la lettre~~ **Tranché le 2 septembre 2026 : Gemini (API Google), palier gratuit (1 500 requêtes/jour, largement suffisant pour un usage personnel), sans carte bancaire.** Préféré à Ollama en local (qualité inférieure pour ce cas d'usage) et aux options payantes (OpenAI, Anthropic — écartées tant que le gratuit suffit). Implique d'accepter que le texte du CV/de la lettre transite par les serveurs Google à chaque reformulation — décision explicite de l'utilisateur, conformément au principe de confidentialité du cadrage.
- Stratégie Alembic définitive : reconstruction de l'historique vs conservation + migrations prospectives. **Tranché en Phase 1 : conservation + migrations prospectives.**
- Moment de bascule vers la V2 (produit grand public) : à réexaminer uniquement une fois la V1 stable, testée et utilisée en conditions réelles. Voir section 3 pour la note sur la solution IA à cette échelle.

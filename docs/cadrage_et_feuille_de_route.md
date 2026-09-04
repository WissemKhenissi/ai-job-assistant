# AI Job Assistant — Cadrage et feuille de route

*Document établi le 2 septembre 2026, à partir du rapport de reprise du 1er septembre 2026 et d'une session de recadrage.*

*Refondu le 5 septembre 2026. Le document décrivait un plan ; il décrivait de moins en moins le projet. La V1 est close, et le projet a changé de nature depuis — il fallait l'acter plutôt que d'empiler les mentions « ajouté le… ». L'historique des décisions est conservé, ce qui change est la structure : ce qui est fait, ce qui est ouvert, ce qui est su et assumé.*

---

## 1. Finalité du projet

L'application n'est pas un simple générateur de CV : c'est un outil qui transforme un Master CV structuré en un assistant de recherche d'emploi honnête.

Le parcours cible :

```text
Master CV structuré
    ↓
Offre d'emploi collée
    ↓
Extraction des compétences demandées
    ↓
Matching explicable (prouvé / déclaré / déduit / manquant)
    ↓
CV ciblé + lettre de motivation
    ↓
Suivi automatique de la candidature
```

**Changement de portée acté le 3 septembre 2026**, à la demande de l'utilisateur (« il faut garder en tête que l'outil n'est pas destiné qu'à mon expérience ») : l'outil ne vise plus le seul positionnement Product Owner / Product Manager / Chef de projet IT / PMO de Wissem Khenissi, mais **n'importe quel candidat, dans n'importe quel métier**. Cette décision n'a pas modifié la finalité ; elle a modifié à peu près tout le reste, et une partie du moteur ne l'a pas encore rattrapée — voir section 6.

### Principes non négociables

1. **Le Master CV est la seule source de vérité.** Rien n'est inventé — ni compétence, ni expérience, ni réalisation.
2. **Le matching doit être honnête, pas flatteur.** Une compétence déduite reste une hypothèse, jamais un fait affirmé.
3. **Chaque candidature laisse une trace.** Ce qui a été généré et envoyé doit rester retrouvable.

Déclinaisons opérationnelles :

- Une compétence **déduite** n'est jamais affichée comme affirmée sur un CV généré. Seules les compétences **prouvées** (preuve `EvidenceDB` liée) peuvent apparaître comme ligne de compétence explicite.
- Toute génération (CV, lettre) reste traçable jusqu'à une donnée du Master CV.
- Une lettre générée par IA est **validée par l'utilisateur** avant d'être finale. Aucun envoi automatique.
- Le profil reste local ; chaque appel à une IA externe est un choix explicite. **Tranché le 2 septembre 2026 : Gemini (API Google, palier gratuit)** — le texte du CV et de la lettre transite donc par les serveurs Google à chaque génération, décision assumée par l'utilisateur.
- Un garde-fou déterministe prime toujours sur une auto-vérification par l'IA. Concrètement : comparaison des chiffres, présence mot pour mot de l'extrait source, vocabulaire interdit, rehaussement de séniorité. En cas de déclenchement, repli automatique sur le contenu déterministe.
- `skill_catalog` est l'unique source de vérité pour la normalisation des compétences.

---

## 2. État au 5 septembre 2026

**La V1 est close.** Les cinq phases prévues sont livrées, plus quatre briques qui appartenaient au backlog V2.

Ordres de grandeur : 78 modules applicatifs, 531 tests, 41 fichiers de test, un référentiel de 13 476 compétences, 13 annonces analysées, 7 candidatures suivies.

### Phases V1

| phase | objet | état |
|---|---|---|
| 0 | Stabilité opérationnelle | fait |
| 1 | Base, migrations, source de vérité | fait |
| 2 | Refactor du matching + couche de tests | fait |
| 3 | Génération CV / lettre + suivi de candidature | fait |
| 4 | Qualité de sortie | fait |
| 5 | Entretien IA d'enrichissement du Master CV | fait |

**Phase 1** — `alembic/env.py` importe `database.model_registry` ; stratégie Alembic tranchée (conservation de l'historique + migrations prospectives) ; `skill_catalog` unifié, fin du dictionnaire `SKILL_ALIASES` dupliqué.

**Phase 2** — `matching_service.py` éclaté en `services/matching/` (`analysis`, `config`, `inference`, `normalization`, `profile_text`, `results`) ; double calcul de `score_experience` corrigé ; table `job_skill_matches` historisant le détail par compétence ; harnais de mesure precision/recall dans `evaluation/`.

**Phase 3** — sélection déterministe du contenu (`services/cv/selection.py`), export DOCX et PDF, lettre déterministe puis rédigée par IA, table `applications` créée automatiquement à chaque génération.

**Phase 4** — la reformulation paragraphe par paragraphe s'est révélée insuffisante après test réel (elle polissait des formules déjà pauvres) ; remplacée pour la lettre par une **rédaction complète** (`services/ai/letter_authoring.py`) à partir d'une fiche de faits structurée, garde-fou numérique sur l'ensemble de la fiche, panneau des faits affiché pour relecture. Le CV garde une reformulation encadrée, son contenu factuel restant sélectionné déterministiquement. S'y ajoutent : champ `motivations` sur le profil, sections du CV activables à l'export, page candidatures en onglets, cahier des charges de génération découpé par étape (`services/cv/prompt_rules.py`) avec vocabulaire borné par le référentiel, contrainte d'une page par **mesure réelle** puis élagage priorisé (`services/cv/fitting.py`), validateur déterministe (`services/cv/validation.py`), réalisations chiffrées atteignant enfin le CV, seuil des compétences affichées au choix du candidat.

**Phase 5** — page unique « Mon Master CV » en onglets, entretien IA par expérience (récit puis relance ciblée), historique d'entretien persistant, compétences en pastilles éditables. Réponses **vocales** livrées le même jour que le textuel : chaque enregistrement est transcrit avant tout traitement, puis emprunte exactement le même chemin qu'une réponse écrite — garde-fou de traçabilité compris, jamais une porte dérobée. Garde-fou principal : toute proposition dont l'extrait source cité par l'IA n'est pas retrouvé mot pour mot dans une réponse réellement donnée est rejetée avant même d'être affichée.

### Livré au-delà de la V1 (3 – 5 septembre 2026)

Ces quatre chantiers découlent du changement de portée. Ils appartenaient au backlog V2 ; ils ont été faits parce que sans eux l'outil ne servait qu'un seul profil.

- **Le référentiel apprend des annonces analysées.** Tout terme inconnu est enregistré, l'IA propose une entrée complète (nom canonique, catégorie, alias), l'utilisateur intègre / rattache / ignore, et chaque décision est réversible.
- **Import de CV pour amorcer le Master CV.** Extraction par IA sous quatre garde-fous : puces verbatim, compétence obligatoirement présente dans le document, chiffres, identité (e-mail, téléphone, LinkedIn doivent figurer dans le document). L'import ajoute sans écraser et refuse les expériences en double. Validé sur un CV d'infirmière.
- **Cloisonnement multi-profils.** `get_candidate` / `get_experiences` filtrent par candidat, sélecteur de profil courant, création et suppression en cascade (avec saisie du nom du profil pour confirmer).
- **Référentiel multi-métiers : ESCO.** 13 476 compétences importées (v1.2.1, CC BY 4.0, jointure FR/EN par `conceptUri`, 26 catégories dérivées). Rendu viable par un index n-grammes : la détection coûte 0,4 à 0,6 ms, qu'il y ait 46 ou 14 000 entrées, contre près de sept secondes en extrapolant l'ancienne méthode.

Trois correctifs ont suivi l'import, parce qu'un référentiel large casse ce qu'un référentiel étroit masquait : la recherche sémantique encodait tout le corpus à chaque appel (209 s par analyse → 1,4 s), les quasi-doublons ESCO doublaient des entrées maison, et une entrée importée bénéficiait du même blanc-seing qu'une entrée curée à la main.

Enfin, le **niveau d'exigence** (5 septembre) : chaque exigence extraite porte désormais « essentielle », « souhaitée » ou « mention », lu dans l'annonce par marqueurs de langage, l'IA pouvant proposer un niveau que le code n'accepte que s'il fait partie des trois valeurs connues. Le score confondait auparavant « exigence » et « mention » — une énumération de dix outils comptait pour dix conditions non couvertes.

---

## 3. Ce qui reste ouvert

Par ordre d'importance décroissante, telle qu'elle apparaît aujourd'hui.

### 3.1 Le moteur est encore mono-profil par endroits

C'est la dette la plus lourde, et la plus contradictoire avec la portée retenue. Détail en section 6.

### 3.2 Qualité de l'extraction des exigences

Le niveau d'exigence n'a pas corrigé ce qui entre dans la liste, il a seulement cessé de l'amplifier. Restent comptées comme exigences :

- des libellés ESCO en forme de phrase verbale (« utiliser des outils en ligne pour collaborer ») ;
- des concepts périphériques cités en passant (« logistique », « responsabilité sociale des entreprises ») ;
- l'**intitulé du poste** lui-même (« Product Owner » compté comme compétence manquante sur une annonce de Product Owner) — le prompt le proscrit désormais, aucun garde-fou déterministe ne le rattrape.

`GENERIC_TERMS` (`services/requirement_cleaning.py`) filtre le bruit, mais c'est une liste écrite à la main, non modifiable depuis l'interface : quand elle se trompe, l'utilisateur ne peut rien.

### 3.3 Le score reste un chiffre, pas une décision

La question à laquelle un candidat veut une réponse n'est pas « 52 sur 100 ? » mais « quelles conditions je ne couvre pas ? ». `missing_essential_skills` répond maintenant à la seconde, et l'interface l'affiche en premier. Reste à décider si le score global unique garde un sens, ou s'il doit céder la place à la seule couverture des conditions.

### 3.4 Français uniquement

Mots de séniorité, suffixes « k€ / M€ », forme nominale des puces, marqueurs d'exigence : tout est écrit en français, en dur. La rédaction du CV dans la langue de l'annonce (§46 du cahier des charges) est repoussée pour une raison précise : les garde-fous chiffres et verbatim s'affaiblissent à la traversée d'une traduction, et il faudrait leur en substituer d'autres avant d'ouvrir la porte.

### 3.5 Reliquats de données V1

- L'annonce parasite « Emplois | Indeed » est toujours en base.
- Deux expériences sans `business_context` ; mois exacts manquants sur les expériences datées approximativement ; URL LinkedIn absente du profil.
- 16 compétences au statut `declared` qu'un entretien assisté pourrait convertir en `proven`.

---

## 4. Backlog V2 — produit grand public

Le document de vision élargie (« Career Intelligence Platform ») reste une carte de référence à long terme, pas un plan d'exécution.

Non commencé :

- Career DNA complet (profil humain, préférences, motivations, frustrations).
- Orientation métier, séniorité par dimension.
- Career Value Score, analyse de salaire, salary gap/upside, simulateur what-if.
- Training Recommendation Engine. Side Business Engine.
- Market Intelligence (au-delà de la mémoire de marché déjà en place).
- Préparation d'entretien d'embauche, STAR Evidence automatisé, Career Analytics.
- **Authentification et multi-utilisateur.** Le cloisonnement par candidat est fait ; il n'y a ni compte, ni mot de passe, ni séparation User/Candidate.
- Migration technique PostgreSQL / FastAPI / React-Next.js.
- RAG, connecteurs job boards, lecture automatique d'emails.

Deux points étudiés et documentés, non implémentés :

- **Solution IA à l'échelle d'un produit** (2 septembre 2026). Le choix V1 ne tient pas : Ollama hébergé perd son avantage de confidentialité et impose un coût GPU ; les paliers gratuits sont dimensionnés pour un compte, pas pour un produit. À cette échelle le critère change — coût par génération × utilisateurs, non-entraînement contractuel, localisation RGPD (Mistral, hébergement UE, est un candidat pertinent sur ce dernier argument). Implique clé API strictement serveur, comptage d'usage, et un modèle économique. À trancher avec le reste de la bascule, pas isolément.
- **Récupération fiable d'une annonce depuis un lien** (2 septembre 2026, après test réel). La version V1 (HTTP simple + extraction de texte) fonctionne sur les pages statiques et échoue sur la plupart des grands jobboards, LinkedIn en tête. Une version fiable demanderait un navigateur headless voire une intégration officielle par site. Le copier-coller manuel reste la solution.

---

## 5. Décisions actées

| date | décision |
|---|---|
| 2 sept. 2026 | `applications` se relie à `job_offers` plutôt que de dupliquer l'offre. |
| 2 sept. 2026 | Pas d'automatisation par lecture d'emails en V1. |
| 2 sept. 2026 | Deux voies pour la lettre — squelette déterministe (zéro invention, sans IA) ou rédaction complète par Gemini à partir d'une fiche de faits — avec repli automatique sur la première. |
| 2 sept. 2026 | LLM : Gemini, palier gratuit. Préféré à Ollama local (qualité) et aux options payantes (tant que le gratuit suffit). |
| 2 sept. 2026 | Alembic : conservation de l'historique + migrations prospectives. |
| 3 sept. 2026 | **L'outil vise tout candidat, pas un seul profil.** |
| 4 sept. 2026 | Référentiel public plutôt que catalogue écrit à la main : ESCO, CC BY 4.0, attribution affichée dans l'application. |
| 4 sept. 2026 | Une entrée de référentiel importée en masse ne bénéficie pas de la confiance accordée à une entrée curée : elle passe la même épreuve que l'inconnu. |
| 5 sept. 2026 | Le niveau d'exigence est lu dans l'annonce, l'IA ne fait que proposer ; en cas de doute, le niveau médian. |
| 5 sept. 2026 | La couche de modèles Pydantic parallèle est supprimée plutôt que maintenue : le projet n'a qu'une représentation, les modèles SQLAlchemy. |

---

## 6. Dette technique — état au 5 septembre 2026

Un balayage complet a été passé le 5 septembre 2026. Ce qui suit distingue ce qui a été corrigé de ce qui reste **su et assumé** : une dette écrite est une décision, une dette tue est un piège.

### 6.1 Corrigé le 5 septembre 2026

- **Code mort supprimé** : la branche de reformulation de lettre (remplacée le 2 septembre par `letter_authoring` et jamais retirée, encore couverte par quatre tests) ; une couche de modèles Pydantic parallèle jamais utilisée, présente depuis l'import initial et déjà désynchronisée du schéma réel ; sept fonctions ou constantes définies et jamais appelées ; huit imports inutilisés. 718 lignes en moins.
- **Formes de comparaison unifiées** dans `services/text_normalization.py`. Deux copies mot pour mot de « minuscules sans accents », deux quasi-copies de « sans ponctuation ». Ce n'était pas qu'une redite : le tri des exigences dédupliquait sur une forme quand le classement de leur niveau indexait sur l'autre — une divergence d'un caractère aurait suffi à ce qu'une exigence retenue cesse silencieusement de retrouver son niveau.
- Ce regroupement a **révélé un vrai défaut** : la normalisation NFKD réécrit « … » en trois points, et la fenêtre de lecture se coupait au premier. Sur une annonce réelle, « maîtrise des outils produits (Jira, Confluence, Figma, …) » perdait son dernier élément et Jira redevenait une condition d'entrée. Corrigé et couvert par un test.

Vérification : 531 tests verts, `alembic check` sans dérive, scores des 13 annonces inchangés après regroupement.

### 6.2 Dette assumée, non corrigée

**Le moteur de matching contient encore trois artefacts mono-profil**, hérités d'avant le changement de portée du 3 septembre. Aucun n'a été touché ce jour-là, et chacun contredit la portée retenue :

1. `score_domain` (`services/matching/analysis.py`) ne reconnaît que trois domaines : « e-commerce », « adtech », « digital ». Pour tout autre métier, ce dixième du score global ne mesure rien.
2. `SEMANTIC_INFERENCE_SKILLS` (`services/matching/config.py`) est une liste blanche de douze compétences produit, écrite à la main : elle seule autorise l'inférence sémantique. Avec 13 476 entrées au référentiel, un profil d'infirmière ou de développeur ne peut structurellement produire aucune compétence « déduite ».
3. `INFERENCE_KEYWORDS` et l'inférence composite `PRODUCT_MANAGEMENT_COMPONENTS` codent en dur le vocabulaire d'un rôle produit.

C'est la dette prioritaire. Elle ne se voit pas en lisant les scores d'un profil produit — elle ne se voit que sur un autre métier.

**Trois `_normalize` restent séparés** dans `services/job_requirements_service.py`, `services/matching/normalization.py` et `services/skill_semantic_service.py`. Leurs règles diffèrent réellement (traitement des tirets, du point de « node.js », des séparateurs de chemin) : les fusionner changerait les résultats de matching. À traiter comme un arbitrage, pas comme un nettoyage.

**Deux pondérations de statut restent volontairement neutres** : une compétence `declared` sans preuve pèse autant qu'une `proven` dans le score d'expérience et dans l'inférence composite. Leur donner un poids intermédiaire ferait baisser tous les scores existants — arbitrage à part entière, noté dans le code, jamais fait.

**Un arbre de travail Git abandonné** subsiste dans `.claude/worktrees/hungry-gagarin-102307`, sur un commit du 2 septembre, avec du travail non commité sur des horodatages (`database/timestamps.py`, `tests/test_timestamps.py`) qui n'a jamais atterri sur `master`. À reprendre ou à supprimer — décision de l'utilisateur, pas une suppression à faire à sa place.

**Seize sauvegardes de base** s'accumulent dans `data/` (60 Mo). Correctement ignorées par Git, mais personne ne les purge.

---

## 7. Points ouverts à trancher

- **Le score global unique doit-il survivre ?** Voir 3.3.
- **La V2 est-elle un objectif ?** La section 4 la décrit, la section 2 montre que quatre de ses briques sont déjà là. Le moment de bascule devait être réexaminé « une fois la V1 stable, testée et utilisée en conditions réelles » : c'est le cas.
- **Jusqu'où ouvrir le multi-métiers ?** Corriger les trois artefacts de la section 6.2 est nécessaire ; suffisant est une autre question, et seule une série de tests sur des profils réellement éloignés y répondra.

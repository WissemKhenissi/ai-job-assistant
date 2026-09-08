# Journal de décisions — AI Job Assistant

**Wissem Khenissi** — cadrage en août 2026, construction du 2 au 5 septembre 2026.
79 commits, 578 tests automatisés, une base de 13 476 compétences.

---

## À quoi sert ce document

Le dépôt montre ce que le produit fait. Ce document montre **comment les décisions ont
été prises** : quel problème, quelle mesure, quel arbitrage, quel résultat — et ce que
j'ai dû abandonner en route.

Il est écrit pour être lu par quelqu'un qui recrute, pas par quelqu'un qui code. Chaque
décision renvoie au commit qui la porte : tout ce qui est affirmé ici est vérifiable
dans l'historique.

### Deux précisions d'honnêteté, tout de suite

**Le code a été écrit en binôme avec une IA (Claude).** Les commits le portent
explicitement (`Co-Authored-By`), et c'est visible dès qu'on ouvre le dépôt. Ce que j'ai
fait moi-même, c'est le travail décrit dans ce document : définir le problème, choisir ce
qu'on mesure, arbitrer, refuser, et supprimer ce qui ne tenait pas la mesure. Trois des
huit décisions qui suivent consistent à **retirer** quelque chose que l'IA faisait, parce
que la mesure a montré qu'elle le faisait mal.

**Le rythme réel n'est pas une cadence de sprints.** Un mois de cadrage, puis quatre
journées de construction intensive. Je ne présente pas ce projet comme un programme géré
sur six itérations : c'est un prototype construit vite, avec des décisions documentées au
fil de l'eau. C'est cette documentation-là qui est l'objet du travail.

---

## Le projet en trois phrases

Un assistant de recherche d'emploi construit autour d'un **Master CV** : tout ce que le
candidat a réellement fait, chaque affirmation rattachée à une preuve. Face à une annonce,
le moteur classe chaque compétence demandée en **prouvée / déclarée / déduite / manquante**,
et seule une compétence prouvée peut figurer telle quelle sur un CV généré.

Le principe qui gouverne tout : **le matching doit être honnête, pas flatteur.** C'est ce
principe qui a coûté le plus cher, et c'est de lui que viennent la plupart des décisions
ci-dessous.

---

## Table des compétences démontrées

| Ce qu'un recruteur cherche | Décision à lire |
|---|---|
| Poser une règle produit et la tenir contre le confort | 1 |
| Dérisquer avant d'engager | 2 |
| Sortir de son propre biais d'utilisateur | 3 |
| Renoncer à sa propre solution sur la mesure | 4 |
| Ne pas s'arrêter à « ça marche » | 5 |
| Priorisation explicite sous contrainte | 6 |
| Ne pas faire confiance à la conformité d'une IA | 7 |
| Honnêteté sur ses propres métriques | 8 |

---

## 1. Une compétence sans preuve n'est pas une compétence prouvée

*2 septembre — commit `c7ea97b`*

**La situation.** Le moteur donnait le statut « prouvée » à toute compétence figurant au
Master CV, qu'une preuve y soit rattachée ou non. Seul le score différait légèrement
(0,90 contre 1,00). Personne ne s'en serait aperçu.

**Ce que ça allait produire.** L'étape suivante prévoyait que le générateur de CV ne
retienne que les compétences prouvées. En filtrant sur ce statut, il aurait affiché des
compétences que rien ne démontre — exactement ce que le principe du projet interdit. Le
défaut était invisible tant que la fonctionnalité n'existait pas, et devenait un mensonge
le jour de sa mise en service.

**L'arbitrage.** Introduire un quatrième statut plutôt que d'ajuster un score :

- `prouvée` — déclarée **et** soutenue par une preuve
- `déclarée` — affirmée par le candidat, sans preuve
- `déduite` — non déclarée, déduite du parcours
- `manquante` — absente

**Le coût assumé.** Aucun score ne change : les endroits qui comptaient « prouvée »
comptent désormais « prouvée + déclarée ». Deux d'entre eux méritaient un arbitrage
distinct — je ne l'ai pas tranché ce jour-là, je l'ai **signalé dans le code** pour ne pas
le perdre.

**Ce que ça m'a appris.** La distinction qui coûte le plus est celle qui ne se voit pas
encore. Un défaut latent se corrige quand on le trouve, pas quand il fait mal.

---

## 2. Mesurer le coût d'un import avant de l'engager

*4 septembre — commit `2b8d7b3`*

**La situation.** Le référentiel de compétences comptait 46 entrées, écrites à la main —
les miennes. Pour que l'outil serve d'autres métiers, il fallait importer une taxonomie
publique : ESCO, environ 14 000 entrées.

**Ce que j'ai fait avant d'importer.** Mesuré le coût des deux fonctions qui lisent le
référentiel, à 46 entrées, puis extrapolé à 14 000 :

| | extraction | recherche |
|---|---|---|
| 46 entrées | 23 ms | 1,3 ms |
| 14 000 (estimé) | **7 s** | **400 ms** |

La fonction de recherche étant appelée plusieurs fois par exigence, une annonce de vingt
exigences aurait demandé une vingtaine de secondes rien qu'en recherches. **L'import était
impossible en l'état** — et je l'ai su avant de le faire, pas après.

**La décision.** Indexer d'abord, importer ensuite. Et inverser la logique d'extraction :
au lieu de chercher chaque alias dans l'annonce, découper l'annonce une fois et chercher
chaque groupe de mots dans un dictionnaire.

| | extraction | recherche |
|---|---|---|
| 46 entrées | 0,5 ms | 0,003 ms |
| 14 000 (réel) | **0,4 ms** | **0,004 ms** |

Le coût ne suit plus la taille du référentiel : il est plat de 46 à 14 000 entrées.

**Un piège écarté au passage.** Trois caches dans trois modules : celui qu'on oublie rend
une compétence fraîchement créée invisible jusqu'au redémarrage, **sans message d'erreur**.
Un seul point d'entrée pour les vider, appelé partout où c'est nécessaire.

**Ce que ça m'a appris.** Le bon moment pour mesurer un changement d'échelle est avant de
le subir. Cette étape n'avait aucun test alors qu'elle décide de tout ce qui suit — j'en
ai ajouté douze.

---

## 3. Mon moteur ne marchait que pour moi

*5 septembre — commit `18921fa`*

**La situation.** Le référentiel était passé de 46 à 13 476 entrées. Le moteur, lui,
portait toujours le vocabulaire d'un seul métier — le mien — **à quatre endroits
différents**. Sur 46 compétences produit, ça ne se voyait pas. Sur 13 476, ça décidait de
tout, et toujours dans le même sens.

**Ce que j'ai trouvé.**

1. Une liste blanche de douze compétences produit, seules autorisées à être déduites :
   **13 464 compétences condamnées à ne jamais l'être.**
2. Un dictionnaire de mots-clés décrivant à la main le champ lexical de ces douze mêmes
   compétences.
3. Les composantes d'une seule compétence — « Product Management » — codées en dur.
4. **Trouvé en vérifiant les trois premiers :** 280 lignes de formulations écrites à la
   main pour vingt-sept compétences produit. Celles-là décidaient encore plus que la liste
   blanche — sans entrée, aucune règle de déduction ne pouvait plus être satisfaite.

**Comment je l'ai prouvé.** J'ai fabriqué un profil d'infirmière et je l'ai passé dans le
moteur. La ressemblance sémantique atteignait 0,65, au-dessus du seuil — et la déduction
échouait quand même, par construction. Après correction : **deux compétences déduites là
où l'ancien moteur en produisait zéro**, et « premiers soins aux animaux » reste
correctement manquante.

**Le score de domaine, aussi.** Il cherchait « e-commerce », « adtech », « digital » dans
le texte de l'annonce. Mesuré sur mes treize annonces : il valait 100 sur les treize. Il
ne mesurait plus rien et ajoutait dix points à tout le monde.

**Deux régressions trouvées en mesurant, et corrigées.** « Jira » se retrouvait déduit par
composition parce qu'il est *associé* à Agile et au backlog — **associé n'est pas fait de**.
Et la déduction lexicale, en réutilisant les compétences associées comme indices, refaisait
la déduction composite avec un seuil plus bas et sans son garde-fou.

**Le prix de l'ouverture.** Ouvrir la déduction a fait passer une analyse de dix-sept
exigences à **165 secondes** : le corpus des 13 476 entrées était recomposé et réencodé à
chaque appel. Mise en cache → **14,6 s au premier appel, 0,0 s ensuite.**

**Résultat mesuré sur les treize annonces réelles :** deux déductions de plus, et les
scores globaux baissent de 2,5 à 8,8 points — exactement ce que le score de domaine
ajoutait à tort. 540 tests verts.

**Ce que ça m'a appris.** J'étais le seul utilisateur du produit, donc le seul profil sur
lequel il avait jamais été éprouvé. Le seul moyen de voir le biais était de construire un
utilisateur qui ne me ressemble en rien.

---

## 4. Retirer l'IA de la fonction qu'elle remplissait

*5 septembre — commits `9d0197c`, `eacf17c`, `7670079`*

C'est la décision dont je suis le plus satisfait, parce qu'elle s'est faite en trois temps
et que les deux premiers étaient faux.

### Acte 1 — le problème

Une annonce qui écrit *« vous maîtrisez un ou plusieurs outils de gestion de projet : Jira,
Confluence, Trello, Miro, GitLab, BaseCamp, Planner, TFS, Clarity, MS Project »* produisait
**dix exigences manquantes là où elle n'en pose qu'une**. Le score mesurait la longueur de
l'énumération autant que l'adéquation du candidat.

J'ai donc donné un niveau à chaque exigence — *essentielle*, *souhaitée*, *mention* — lu
dans le texte par des marqueurs de langage, avec l'IA autorisée à proposer un niveau quand
le texte se tait. Motif : l'IA lit mieux le découpage en sections d'une annonce.

### Acte 2 — la mesure dément

Sur les treize annonces, l'IA et le texte divergeaient sur **29 exigences**. Le sens du
désaccord était toujours le même : l'IA promeut en condition d'entrée ce que l'annonce se
contente de citer (14 fois) ou de souhaiter (13 fois). **Jamais l'inverse.**

Le cas décisif : deux captures d'une même offre, identiques à 99,3 %, notées **38,3 et
44,1**. Huit termes classés « essentielle » d'un côté et « mention » de l'autre, quand la
lecture du texte répondait « mention » aux deux.

J'ai inversé la priorité : le texte décide, l'IA comble les silences.

### Acte 3 — ça ne suffisait pas

**137 exigences sur 202 tombaient dans le silence des marqueurs**, où l'IA décidait encore.
Deux captures d'une même offre — seules différences : des bandeaux de navigation LinkedIn —
obtenaient **34,6 et 44,5**. L'écart tenait à deux termes dont l'un, « CRM », n'apparaît
que dans le titre de la page.

**Un score qui bouge de dix points sur le même texte n'aide à décider de rien.**

J'ai retiré l'IA du classement. Le silence vaut désormais le niveau médian : il n'exagère
ni ne minimise l'écart, et il ne change pas d'avis.

**Retiré partout plutôt que laissé inerte** — le champ du prompt, le champ du modèle de
données, le paramètre du moteur, son passage depuis l'interface, la constante de
validation, et les tests qui les couvraient. *Un prompt qui réclame une donnée que
personne ne lit est une dette.*

Un test verrouille la propriété qui manquait : **deux fois le même texte donnent deux fois
le même classement.**

**Ce que ça m'a appris.** Le classement par l'IA n'a jamais démontré qu'il apportait de la
justesse — seulement de la sévérité et de la variance. J'ai mis deux tentatives à
l'admettre, parce que c'était ma solution. La reproductibilité vaut mieux qu'une finesse
qu'on ne peut pas vérifier.

---

## 5. Reproductible, mais muet : le travail n'était pas fini

*5 septembre — commit `dff2327`*

**La situation.** Retirer l'IA avait rendu le score reproductible. Il était aussi devenu
inutile : **11 exigences essentielles sur 178**, et la liste des conditions non couvertes —
le seul résultat vraiment exploitable pour un candidat — était presque toujours vide.

Il aurait été confortable de s'arrêter là : le score était juste, stable, défendable. Il ne
servait à rien.

**Trois causes, mesurées avant d'être corrigées.**

1. **Le titre de section ne portait que sur sa première puce.** La recherche remontait deux
   lignes non vides ; dans une liste à puces, ces deux lignes sont les puces voisines,
   jamais le titre.
2. **L'exigence était cherchée sous un nom que l'annonce n'emploie pas.** Le référentiel
   reconnaît « Agile / Scrum » derrière le mot « Agile », et c'est le nom canonique qui
   devenait l'exigence. **69 des 121 silences venaient de là**, tous rattrapables par un
   alias.
3. **Une liste évidente était rejetée pour un seul membre bavard** : *« les principales
   plateformes du marché : CRM, CDP, CMS, solutions marketing automation et e-commerce »*
   cessait d'être une énumération à cause du dernier terme. Une majorité franche suffit.

**Un détail qui n'en est pas un.** Les marqueurs de section s'enrichissent des titres
**réellement relevés dans le corpus** — « Votre profil », « Vous maîtrisez : », « Vous êtes
reconnu(e) pour : », « Hard skills », « Les compétences qui feront votre succès » — et non
de titres imaginés à mon bureau.

**Résultat mesuré :** 90 exigences muettes contre 121, **30 essentielles contre 11**. Les
conditions non couvertes redeviennent lisibles — Marketplace B2B, frameworks de
priorisation, Cycle en V, Pack Office — au lieu d'être vides.

**Ce que ça m'a appris.** « Correct » et « utile » sont deux critères distincts, et le
premier ne dispense pas du second.

---

## 6. Ne pas demander au modèle ce qu'il ne peut pas savoir

*3 septembre — commit `90a29fe`*

**La contrainte.** Un CV doit tenir sur une page.

**Ce que je n'ai pas fait.** Demander au modèle d'estimer la longueur. Il en est incapable
de façon fiable : le nombre de pages dépend de la police, des marges et du gabarit, pas du
nombre de mots.

**Ce que j'ai fait.** Le PDF est **réellement rendu**, ses pages comptées, l'élément le
moins précieux retiré, et on recommence.

**L'ordre de sacrifice, décidé explicitement** — du moins au plus coûteux : centres
d'intérêt, langues, résumé réduit à sa première phrase, lignes de preuve des expériences
les plus anciennes (jusqu'à en laisser une par expérience), formation et certifications.

**Deux garde-fous de fond.**

- L'élagage **ne fait que retirer, jamais réécrire ni résumer** : un CV raccourci reste
  exactement aussi vrai que le CV complet. Un test dédié le verrouille.
- **Aucune expérience n'est supprimée entièrement** — un trou dans la chronologie appelle
  une question gênante en entretien.

Si le CV déborde encore après tout cela, c'est dit franchement plutôt que de compresser
jusqu'à l'illisible.

**Ce que ça m'a appris.** Une contrainte de mise en forme se vérifie par la mise en forme.
Et un ordre de priorité explicite vaut mieux qu'un algorithme qui décide seul : ici, la
hiérarchie de ce qu'on sacrifie **est** la décision produit.

---

## 7. Le modèle a ignoré la consigne

*5 septembre — commit `c7ec3dd`*

**La situation.** Neuf compétences de mon Master CV étaient déclarées sans qu'aucun élément
du parcours ne les démontre. Ce n'est pas un défaut du candidat : il a fait ces choses, il
ne les a pas racontées. J'ai donc ajouté un entretien qui aide à raconter **une occasion
précise** où la compétence a été exercée.

**L'essai réel.** À la réponse *« oui je fais de la veille, c'est important dans mon métier,
je regarde ce que font les autres »*, le modèle a proposé la ligne de preuve *« Réalisation
régulière de veille concurrentielle et information sur les pratiques du marché »*.

Rien n'est inventé — c'est une reformulation fidèle. Mais la valider ferait passer la
compétence de « déclarée » à « **prouvée** » **sur sa propre déclaration reformulée**. La
consigne du prompt l'interdisait explicitement. **Le modèle l'a ignorée.**

**La décision.** Ne pas renforcer la consigne. Ajouter un contrôle déterministe : une ligne
de preuve doit porter une trace — un chiffre, une quantité, un rythme, ou le nom propre
d'un projet, d'un outil, d'une entreprise. Sinon la case est **décochée par défaut**, avec
l'explication.

**Jamais un refus.** Le contrôle se trompe dans un sens connu — *« mise en place d'un
tableau de bord partagé »* est un fait concret qu'il ne reconnaît pas — et une case se
recoche d'un clic. **L'erreur va vers la prudence, jamais vers la complaisance.**

**Ce que ça m'a appris.** Une consigne dans un prompt est une intention, pas une garantie.
Quand la règle compte vraiment, elle doit vivre ailleurs que dans le prompt.

---

## 8. Une mesure qui se compare à elle-même ne mesure rien

*2 septembre — commit `1a9e7a1`*

**La situation.** Je jugeais la qualité du moteur à l'impression que me laissaient deux
annonces. J'ai construit un harnais pour la mesurer.

**Ce que j'ai choisi de mettre en avant.** Pas un taux d'exactitude global, mais la
**surévaluation** : les cas où le moteur affirme une compétence mieux établie qu'elle ne
l'est. C'est l'erreur qui produirait un CV malhonnête. Un moteur à 95 % d'exactitude qui
surévalue systématiquement serait inutilisable ici. L'erreur inverse apparaît comme un
simple écart.

**Le piège que j'ai désamorcé.** Le jeu de données était amorcé avec les deux annonces déjà
en base — mais leurs annotations étaient **pré-remplies avec la sortie du moteur lui-même**.
Les compter reviendrait à comparer le moteur à lui-même, pour un score de 100 % qui ne
mesurerait rien. Le script les **exclut** et explique pourquoi. Un test vérifie qu'aucun cas
encore pré-rempli n'est marqué comme relu.

**L'aveu.** À ce jour, **ce harnais n'a jamais été alimenté** : zéro cas relu par un humain.
Il est prêt, il est testé, il ne mesure encore rien. C'est la première dette de la liste
ci-dessous.

**Ce que ça m'a appris.** Concevoir la métrique avant d'en avoir besoin oblige à choisir
quelle erreur est inacceptable. Ici, ce n'était pas « se tromper » — c'était « flatter ».

---

## Autres décisions traçables

| date | décision | commit |
|---|---|---|
| 3 sept. | **Le validateur de CV est sans IA, délibérément.** Faire vérifier une IA par une autre remplacerait une garantie par une probabilité. Tout ce qui est contrôlé est confrontable exactement au Master CV. Le validateur constate, ne corrige rien : l'utilisateur tranche. | `5700ad3` |
| 4 sept. | **L'IA propose l'entrée de référentiel, l'utilisateur valide.** Rien n'est appliqué automatiquement. Quatre garde-fous s'appliquent avant même l'affichage, dont l'écart des rattachements vers une compétence inexistante — le modèle invente parfois sa cible. | `8135ea6` |
| 4 sept. | **Marche arrière possible sur chaque décision de tri du référentiel.** Une décision de classement qu'on ne peut pas défaire est un piège. | `05b5801` |
| 4 sept. | **Cloisonnement des profils.** `get_experiences` retournait le parcours de *tout le monde*. Invisible avec une seule fiche ; à la deuxième, un CV généré aurait pu porter l'expérience de quelqu'un d'autre. Audit du reste : les deux seuls défauts étaient là. Dit franchement dans le code : **ce n'est pas de l'authentification**, c'est un sélecteur de profil. | `2aa007d` |
| 4 sept. | **Une entrée importée en masse ne bénéficie pas de la confiance d'une entrée curée** : elle passe la même épreuve que l'inconnu. | `d599168` |
| 5 sept. | **Suppression de la couche de modèles parallèle** plutôt que la maintenir : le projet n'a qu'une représentation des données. | `0cc5da5` |

---

## Ce que ce projet ne fait pas

Cette section existe parce qu'un portfolio sans limites déclarées n'est pas crédible.

- **Le harnais d'évaluation n'a jamais été alimenté.** Zéro cas relu par un humain. Les
  chiffres de ce document sont des mesures avant/après sur un corpus réel de treize
  annonces — ce ne sont pas des taux de précision validés.
- **Un seul utilisateur réel : moi.** Le profil d'infirmière était fabriqué pour éprouver
  le moteur, pas pour l'utiliser.
- **« Prouvé » veut dire auto-déclaré et situé, pas vérifié.** Le contrôle vérifie qu'une
  affirmation porte un chiffre, un rythme ou un nom propre — c'est-à-dire **sa forme, pas
  sa véracité**. Le produit rend les affirmations *falsifiables*, il ne les vérifie pas.
  La confusion entre les deux serait la faute la plus grave que ce projet puisse commettre.
- **Français uniquement**, et le référentiel ESCO n'est exploité que dans sa version
  française.
- **Pas d'authentification.** Le sélecteur de profil ne protège de personne ayant accès au
  fichier de base.
- **68 termes inconnus et 29 reconnaissances douteuses** attendent un tri ; 9 compétences
  déclarées restent sans preuve.

La dette connue est tenue à jour dans [`cadrage_et_feuille_de_route.md`](cadrage_et_feuille_de_route.md),
section 6. **Une dette écrite est une décision ; une dette tue est un piège.**

---

## Chiffres du projet

| | |
|---|---|
| Commits | 79 (1 le 3 août, 72 du 2 au 5 septembre, 6 de mise en portfolio) |
| Tests automatisés | 578, verts |
| Référentiel de compétences | 13 476 entrées (ESCO v1.2.1, CC BY 4.0) |
| Corpus d'annonces réelles | 13 |
| Coût mesuré d'une candidature complète | 10 appels LLM, ~19 700 tokens en entrée |
| Migrations de base | Alembic, historique conservé |

---

*Chaque affirmation de ce document renvoie à un commit du dépôt. Les messages de commit
contiennent le détail des mesures, y compris celles qui m'ont donné tort.*

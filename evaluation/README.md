# Mesurer la qualité du moteur de matching

Ce dossier contient un jeu d'annonces annotées et un script qui compare
ce que le moteur produit à ce qui est réellement attendu.

## Lancer la mesure

```bash
.venv/Scripts/python.exe -m evaluation.evaluate
```

Avec le détail annonce par annonce :

```bash
.venv/Scripts/python.exe -m evaluation.evaluate --detail
```

## Deux refus, avant de mesurer quoi que ce soit

Le harnais s'arrête plutôt que de produire un chiffre trompeur.

**Les cas non relus sont exclus.** Une annotation pré-remplie par le
moteur reviendrait à le comparer à lui-même : le score serait de
100 % et ne mesurerait rien. `--inclure-non-revises` passe outre.

**Une base qui ne correspond plus au dépôt arrête tout.** Le
référentiel pilote entièrement l'extraction, et l'écran Référentiel
écrit directement en base : un alias ajouté là et jamais remonté dans
`database/seed_skill_catalog.py` donne un moteur que personne d'autre
ne peut reconstituer — et que le prochain passage du seed effacera.

C'est arrivé. Quatorze alias issus du tri des termes n'existaient
qu'en base ; la mesure publiée portait sur un moteur plus riche que
celui du dépôt, et un seed a fait tomber le recall de 83,0 % à
75,5 % d'un coup. `--ignorer-la-derive` passe outre, en sachant que
les chiffres ne vaudront que pour cette machine.

## Ce qui est mesuré

Deux couches, évaluées séparément parce qu'elles échouent différemment.

**1. Extraction** — à partir du texte de l'annonce, quelles compétences le
moteur considère-t-il comme demandées ?

Mesurée deux fois : par le seul catalogue, puis avec l'extraction par
l'IA que l'application intercale. L'écart entre les deux colonnes est
la seule réponse honnête à « l'IA apporte-t-elle quelque chose ? ».

La réponse de l'IA n'est pas redemandée à chaque mesure — elle varie
d'un appel à l'autre, et une mesure qui bouge toute seule ne mesure
rien. Elle est figée une fois, datée, versionnée à côté de l'annonce :

```bash
.venv/Scripts/python.exe -m evaluation.enregistrer_reponses_ia
```

Réenregistrer après une mise à jour du modèle est une décision à
prendre, pas un automatisme : sans quoi la référence suivrait
silencieusement ce qu'elle est censée juger.

- *precision* : parmi les compétences détectées, combien sont réellement
  demandées ? Une precision basse = le moteur voit des exigences qui
  n'existent pas.
- *recall* : parmi les compétences réellement demandées, combien ont été
  détectées ? Un recall bas = le moteur passe à côté d'exigences.
- *faux positifs* : la liste nominative des compétences détectées à tort.

**2. Statuts** — pour chaque compétence demandée, le moteur répond
`proven` / `declared` / `inferred` / `missing`. On compare au statut
attendu.

## La métrique qui compte vraiment

Toutes les erreurs ne se valent pas.

Le script isole les **surévaluations** : les cas où le moteur affirme une
compétence mieux établie qu'elle ne l'est (il répond `proven` là où la
réalité est `declared`, ou `inferred` là où c'est `missing`).

C'est l'erreur qui produirait un CV malhonnête. Elle est comptée et
affichée à part, jamais noyée dans un taux global — un moteur à 95 %
d'exactitude qui surévalue systématiquement les compétences techniques
serait inutilisable pour ce projet.

L'erreur inverse — sous-évaluer — apparaît comme un simple « écart » :
elle fait perdre des opportunités, elle ne fait pas mentir le CV.

## Annoter une annonce

Un cas = un dossier dans `dataset/`, avec deux fichiers.

```
dataset/
  mon-annonce/
    annonce.txt     le texte brut de l'annonce
    attendu.json    ce que le moteur devrait trouver
```

### `attendu.json`

```json
{
  "titre": "Product Owner E-commerce",
  "revise_par_humain": true,
  "commentaire": "Annonce reçue le 12/09, poste chez X.",

  "competences_attendues": [
    "Product Discovery",
    "Backlog Management",
    "SQL"
  ],

  "statuts_attendus": {
    "Product Discovery": "proven",
    "SQL": "missing"
  }
}
```

**`competences_attendues`** — les compétences que l'annonce demande
réellement, selon toi. C'est la vérité terrain de la couche 1.

**`statuts_attendus`** — le statut que tu considères honnête pour chaque
compétence. **L'annotation peut être partielle** : n'annote que les
compétences dont tu es sûr, les autres sont simplement ignorées. Mieux
vaut 3 statuts fiables que 12 approximatifs.

Les quatre statuts :

| Statut | Signification |
|---|---|
| `proven` | Tu l'as fait, et tu peux le prouver par une réalisation du Master CV |
| `declared` | C'est dans ton CV, mais tu n'as pas de preuve concrète à montrer |
| `inferred` | Ce n'est pas déclaré, mais ton parcours le rend plausible |
| `missing` | Tu ne l'as pas |

**`revise_par_humain`** — tant que ce champ est à `false`, le cas est
**exclu de la mesure**.

C'est volontaire. Les cas amorcés automatiquement ont leurs annotations
pré-remplies avec la sortie du moteur lui-même : les compter reviendrait
à comparer le moteur à lui-même, ce qui donnerait 100 % et ne mesurerait
rien. Passe le champ à `true` une fois que tu as relu et corrigé.

La comparaison des noms se fait sur la forme canonique du référentiel
`skill_catalog` : écrire « Project Management » ou « Gestion de projet »
revient au même, pas besoin de deviner l'orthographe exacte attendue.

## Ajouter une annonce

1. Créer un dossier dans `dataset/`.
2. Coller le texte de l'annonce dans `annonce.txt`.
3. Écrire `attendu.json` avec les compétences réellement demandées.
4. Passer `revise_par_humain` à `true`.
5. Relancer la mesure.

Une dizaine d'annonces représentatives des postes visés suffit pour que
les chiffres commencent à être parlants. En dessous de 3 ou 4, une seule
annonce atypique fait bouger tous les taux.

"""
Les écrans du Master CV : profil, expériences, compétences, entretien
d'enrichissement.

Ce paquet n'expose plus de page unique. Les quatre écrans étaient
d'abord empilés sur un seul défilement, au point que le bouton d'envoi
de l'entretien passait inaperçu en bas de page ; ils sont ensuite
passés en onglets, puis en pages à part entière — voir
ui/navigation.py, qui les assemble.

L'entretien, qui *reconstruit* le Master CV, vit ainsi séparément de
son *résultat*.
"""

"""
Les écrans de candidature : analyse d'annonce, génération de CV et de
lettre, suivi, mémoire de marché, référentiel.

Ce paquet n'expose plus de page unique. Tout tenait à l'origine dans
un fichier de 880 lignes empilé sur un seul défilement ; il a été
éclaté en un module par écran, d'abord présentés en onglets, puis en
pages à part entière — voir ui/navigation.py, qui les assemble.

Le regroupement y suit désormais l'intention plutôt que l'origine du
code : analyser, générer et suivre forment une suite, tandis que le
référentiel et la mémoire de marché relèvent de l'entretien de l'outil.
"""

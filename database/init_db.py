from database.db import engine

# Via model_registry, et non database.models : les modèles sont répartis
# entre database/models.py et le paquet models/, et seul le registre les
# importe tous. Importer Base depuis database.models créait la base avec
# 11 tables sur 15 — job_offers, applications, job_matches et
# job_skill_matches manquaient, sans le moindre message. C'est la même
# raison qui fait passer alembic/env.py par ce registre.
from database.model_registry import Base


Base.metadata.create_all(engine)


print("Base de données initialisée.")

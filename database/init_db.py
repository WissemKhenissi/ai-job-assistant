from database.db import engine
from database.models import Base


Base.metadata.create_all(engine)


print("Base de données initialisée.")
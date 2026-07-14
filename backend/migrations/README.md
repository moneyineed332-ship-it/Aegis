# Migrations AEGIS

La couche actuelle utilise SQLite pour le MVP. Les migrations Alembic de production seront ajoutées ici lors du basculement de `storage.py` vers SQLAlchemy/PostgreSQL.

La variable `DATABASE_URL` est fournie par Docker Compose ou `backend/.env`.

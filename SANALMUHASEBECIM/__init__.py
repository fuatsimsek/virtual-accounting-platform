from SANALMUHASEBECIM.app import create_app
from SANALMUHASEBECIM.extensions import db, login_manager, mail, migrate

# Backwards compatibility for modules importing app, db, etc.
app = create_app()

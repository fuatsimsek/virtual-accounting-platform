"""
Create SQLite database + all tables + admin & user accounts.
Run once:  python init_db.py
Then start the app:  python start.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from dotenv import load_dotenv
load_dotenv()

# Minimal app only for DB creation (same config as start.py)
from flask import Flask
from SANALMUHASEBECIM.config import config
from SANALMUHASEBECIM.extensions import init_extensions, db
from SANALMUHASEBECIM.models import User
from werkzeug.security import generate_password_hash

app = Flask(__name__)
app.config.from_object(config[os.environ.get('FLASK_ENV', 'development')])
init_extensions(app)

with app.app_context():
    uri = app.config.get('SQLALCHEMY_DATABASE_URI') or ''
    if 'sqlite' not in uri:
        print('Not SQLite. Set DATABASE_URL to sqlite or leave unset.')
        sys.exit(1)
    db_path = uri.replace('sqlite:///', '')
    print(f'Creating: {db_path}')
    db.create_all()
    # Admin
    if User.query.filter_by(email='admin@example.com').first() is None:
        a = User(name='Admin', email='admin@example.com', password=generate_password_hash('admin'))
        a.is_admin = True
        a.email_confirmed = True
        a.role = 'admin'
        db.session.add(a)
        print('  + admin@example.com / admin')
    # User
    if User.query.filter_by(email='user@example.com').first() is None:
        u = User(name='User', email='user@example.com', password=generate_password_hash('user'))
        u.email_confirmed = True
        u.role = 'client'
        db.session.add(u)
        print('  + user@example.com / user')
    db.session.commit()
print('OK. Run: python start.py')
print('Logins: admin@example.com / admin  |  user@example.com / user')

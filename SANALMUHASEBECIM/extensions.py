from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask import request, abort, redirect, url_for, flash
from flask_mail import Mail
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import current_user
from flask_caching import Cache
from flask_wtf.csrf import CSRFProtect
from authlib.integrations.flask_client import OAuth

# Database
db = SQLAlchemy()

# Login Manager
login_manager = LoginManager()
login_manager.login_view = 'account.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# Özel yetkisiz erişim davranışı: /admin için 404 döndür
@login_manager.unauthorized_handler
def _unauthorized_handler():
    try:
        path = request.path or ''
        if path.startswith('/admin'):
            # Admin URL'lerini gizlemek için 404 ver
            abort(404)
        # Diğer yollar için klasik yönlendirme ve Türkçe mesaj
        if login_manager.login_message:
            try:
                flash(login_manager.login_message, login_manager.login_message_category or 'info')
            except Exception:
                pass
        next_url = None
        try:
            next_url = request.url
        except Exception:
            next_url = None
        return redirect(url_for('account.login', next=next_url) if next_url else url_for('account.login'))
    except Exception:
        # Herhangi bir hata halinde güvenli varsayılan
        abort(404)

# Mail - UTF-8 encoding ile
mail = Mail()

# Migrations
migrate = Migrate()

# Rate Limiting
def _rate_limit_key():
    # Profesyonel yaklaşım: Giriş yapan kullanıcı için kullanıcı ID'siyle sınırla,
    # anonim isteklerde IP adresine göre sınırla.
    try:
        if current_user and getattr(current_user, 'is_authenticated', False):
            return f"user:{current_user.id}"
    except Exception:
        pass
    return get_remote_address()

limiter = Limiter(
    key_func=_rate_limit_key,
    # Daha yüksek ve gerçekçi varsayılan limitler
    default_limits=[
        "20000 per day",   # günlük 20k
        "1200 per hour"    # saatte 1200 (~dakikada 20)
    ]
)

# Cache
cache = Cache(config={
    'CACHE_TYPE': 'simple',
    'CACHE_DEFAULT_TIMEOUT': 300
})

# CSRF Protection
csrf = CSRFProtect()

# OAuth
oauth = OAuth()

def _register_oauth_providers(app):
    """Register OAuth providers if credentials exist in config."""
    # Google (OIDC)
    google_client_id = app.config.get('GOOGLE_CLIENT_ID')
    google_client_secret = app.config.get('GOOGLE_CLIENT_SECRET')
    if google_client_id and google_client_secret:
        oauth.register(
            name='google',
            client_id=google_client_id,
            client_secret=google_client_secret,
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={
                'scope': 'openid email profile',
                'token_endpoint_auth_method': 'client_secret_post'
            }
        )

    # Facebook
    facebook_client_id = app.config.get('FACEBOOK_CLIENT_ID')
    facebook_client_secret = app.config.get('FACEBOOK_CLIENT_SECRET')
    if facebook_client_id and facebook_client_secret:
        oauth.register(
            name='facebook',
            client_id=facebook_client_id,
            client_secret=facebook_client_secret,
            access_token_url='https://graph.facebook.com/v19.0/oauth/access_token',
            authorize_url='https://www.facebook.com/v19.0/dialog/oauth',
            api_base_url='https://graph.facebook.com/v19.0/',
            client_kwargs={'scope': 'email'}
        )

def init_extensions(app):
    """Initialize all Flask extensions"""
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)
    cache.init_app(app)
    csrf.init_app(app)
    oauth.init_app(app)
    _register_oauth_providers(app)

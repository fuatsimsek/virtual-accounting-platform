import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


class Config:
    # Enter your secret key in .env (e.g. SECRET_KEY=your-random-secret-here)
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'change-me-in-production'

    # Enter your database URL in .env (e.g. sqlite for local: sqlite:///app.db)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(BASE_DIR, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    REMEMBER_COOKIE_SECURE = False
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_REFRESH_EACH_REQUEST = True
    REMEMBER_COOKIE_NAME = 'remember_token'

    # Mail (optional) – enter your SMTP details in .env if you need email
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or ''
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_SSL = False
    MAIL_USE_TLS = bool(os.environ.get('MAIL_USE_TLS', 'true').lower() in ('1', 'true', 'yes'))
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or ''
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or ''
    MAIL_DEFAULT_SENDER = (os.environ.get('MAIL_SENDER_NAME') or 'App', os.environ.get('MAIL_SENDER_EMAIL') or '')
    MAIL_SUPPRESS_SEND = True  # Set to False when you have real mail configured
    MAIL_MAX_EMAILS = None
    MAIL_ASCII_ATTACHMENTS = False
    MAIL_USE_UTF8 = True
    MAIL_CHARSET = 'utf-8'

    BASE_URL = os.environ.get('BASE_URL') or 'http://127.0.0.1:5000'

    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 10 * 1024 * 1024))
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or os.path.join(BASE_DIR, 'SANALMUHASEBECIM', 'static', 'uploads')
    ALLOWED_EXTENSIONS = set((os.environ.get('ALLOWED_EXTENSIONS') or 'pdf,jpg,jpeg,png,doc,docx,xls,xlsx').split(','))

    # Optional: enter your credentials in .env if you use these features
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN') or ''
    TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID') or ''
    GOOGLE_SERVICE_ACCOUNT_JSON = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON') or ''
    GOOGLE_CALENDAR_ID = os.environ.get('GOOGLE_CALENDAR_ID') or ''
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID') or ''
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET') or ''
    FACEBOOK_CLIENT_ID = os.environ.get('FACEBOOK_CLIENT_ID') or ''
    FACEBOOK_CLIENT_SECRET = os.environ.get('FACEBOOK_CLIENT_SECRET') or ''

    # Payment / IBAN (optional) – enter your info in .env
    IBAN = os.environ.get('IBAN') or ''
    IBAN_ACCOUNT_HOLDER = os.environ.get('IBAN_ACCOUNT_HOLDER') or ''
    IBAN_BANK_NAME = os.environ.get('IBAN_BANK_NAME') or ''
    IBAN_PAYMENT_NOTE = os.environ.get('IBAN_PAYMENT_NOTE') or ''


class DevelopmentConfig(Config):
    DEBUG = True
    FLASK_ENV = 'development'


class ProductionConfig(Config):
    DEBUG = False
    FLASK_ENV = 'production'
    SECRET_KEY = os.environ.get('SECRET_KEY')
    REMEMBER_COOKIE_SECURE = True
    TESTING = False
    LOG_LEVEL = 'WARNING'


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig,
}

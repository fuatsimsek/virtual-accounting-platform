from flask import Flask, request, render_template
from werkzeug.middleware.proxy_fix import ProxyFix
from SANALMUHASEBECIM.extensions import init_extensions
from SANALMUHASEBECIM.config import config
from werkzeug.security import generate_password_hash
import os
from dotenv import load_dotenv


def seed_default_users(app):
    """Create default admin and user if they do not exist."""
    with app.app_context():
        from SANALMUHASEBECIM.extensions import db
        from SANALMUHASEBECIM.models import User
        try:
            if User.query.filter_by(email='admin@example.com').first() is None:
                admin = User(name='Admin', email='admin@example.com', password=generate_password_hash('admin'))
                admin.is_admin = True
                admin.email_confirmed = True
                db.session.add(admin)
            if User.query.filter_by(email='user@example.com').first() is None:
                user = User(name='User', email='user@example.com', password=generate_password_hash('user'))
                user.email_confirmed = True
                db.session.add(user)
            db.session.commit()
        except Exception:
            db.session.rollback()


def create_app(config_name=None):
    load_dotenv()
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Initialize extensions
    init_extensions(app)
    # Create tables when using SQLite (no migrations needed for quick local run)
    with app.app_context():
        from SANALMUHASEBECIM.extensions import db
        from sqlalchemy import text
        uri = app.config.get('SQLALCHEMY_DATABASE_URI') or ''
        if 'sqlite' in uri:
            db.create_all()
            # Add seen_notifications column if missing (e.g. DB created before it was in model)
            try:
                db.session.execute(text('SELECT seen_notifications FROM user LIMIT 1'))
            except Exception:
                try:
                    db.session.execute(text('ALTER TABLE user ADD COLUMN seen_notifications TEXT'))
                    db.session.commit()
                except Exception:
                    db.session.rollback()
    seed_default_users(app)
    # Respect X-Forwarded headers when behind proxies (e.g., trycloudflare)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
    
    # Production güvenlik middleware'i
    if not app.config.get('DEBUG'):
        # Rate limiting için basit cache
        from collections import defaultdict
        import time
        login_attempts = defaultdict(list)
        
        @app.before_request
        def rate_limiting():
            # Admin panel için rate limiting
            if request.path.startswith('/admin'):
                client_ip = request.remote_addr
                current_time = time.time()
                
                # Son 1 dakikada 5'ten fazla admin erişim denemesi varsa engelle
                login_attempts[client_ip] = [t for t in login_attempts[client_ip] if current_time - t < 60]
                
                if len(login_attempts[client_ip]) >= 5:
                    app.logger.warning(f'Rate limit exceeded for IP: {client_ip}')
                    return "Rate limit exceeded. Please try again later.", 429
                
                login_attempts[client_ip].append(current_time)
        
        @app.before_request
        def security_headers():
            # Güvenlik header'ları
            from flask import make_response
            response = make_response()
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'SAMEORIGIN'
            response.headers['X-XSS-Protection'] = '1; mode=block'
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:;"
            return response
        
        @app.before_request
        def admin_access_log():
            # Admin panel erişim log'u
            if request.path.startswith('/admin'):
                app.logger.warning(f'Admin panel erişim denemesi: {request.remote_addr} - {request.path} - User-Agent: {request.headers.get("User-Agent", "Unknown")}')
    
    # Production'da gereksiz debug logları kaldırıldı
    
    # Register blueprints
    from SANALMUHASEBECIM.blueprints.public import bp as public_bp
    from SANALMUHASEBECIM.blueprints.account import bp as account_bp
    from SANALMUHASEBECIM.blueprints.blog import bp as blog_bp
    from SANALMUHASEBECIM.blueprints.admin import bp as admin_bp
    from SANALMUHASEBECIM.blueprints.booking import bp as booking_bp
    from SANALMUHASEBECIM.blueprints.helpdesk import bp as helpdesk_bp
    
    app.register_blueprint(public_bp)
    app.register_blueprint(account_bp, url_prefix='/account')
    app.register_blueprint(blog_bp, url_prefix='/blog')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(booking_bp, url_prefix='/booking')
    app.register_blueprint(helpdesk_bp, url_prefix='/helpdesk')
    
    # Global template context
    @app.context_processor
    def inject_footer_services():
        try:
            from SANALMUHASEBECIM.models import Service
            footer_services = Service.query.filter_by(is_active=True).order_by(Service.order_index).limit(6).all()
        except Exception:
            footer_services = []
        return dict(footer_services=footer_services)

    @app.context_processor
    def inject_oauth_flags():
        google_oauth_enabled = False  # Set credentials in .env to enable
        facebook_oauth_enabled = False
        # Unread ticket count for current user
        unread_ticket_count = 0
        try:
            from flask_login import current_user
            from flask import session
            from SANALMUHASEBECIM.models import Ticket, TicketMessage
            if current_user.is_authenticated and not current_user.is_admin:
                tickets = Ticket.query.filter_by(user_id=current_user.id).all()
                last_seen_map = session.get('ticket_last_seen', {}) or {}
                total = 0
                for t in tickets:
                    seen_iso = last_seen_map.get(str(t.id))
                    seen_dt = None
                    if seen_iso:
                        from datetime import datetime as _dt
                        try:
                            seen_dt = _dt.fromisoformat(seen_iso)
                        except Exception:
                            seen_dt = None
                    q = TicketMessage.query.filter(
                        TicketMessage.ticket_id == t.id,
                        TicketMessage.user_id != current_user.id
                    )
                    if seen_dt:
                        q = q.filter(TicketMessage.created_at > seen_dt)
                    total += q.count()
                unread_ticket_count = total
        except Exception:
            unread_ticket_count = 0
        return dict(
            google_oauth_enabled=google_oauth_enabled,
            facebook_oauth_enabled=facebook_oauth_enabled,
            unread_ticket_count=unread_ticket_count
        )
    
    # Ping endpoint
    @app.route("/ping")
    def ping():
        return "Bağlantı başarılı"

    # Quick auto-login for testing / screenshots (remove in production)
    @app.route("/auto-login/<user_type>")
    def auto_login(user_type):
        from flask_login import login_user
        from SANALMUHASEBECIM.models import User
        if user_type == 'admin':
            user = User.query.filter_by(email='admin@example.com').first()
        elif user_type == 'user':
            user = User.query.filter_by(email='user@example.com').first()
        else:
            return "Invalid user type. Use /auto-login/admin or /auto-login/user", 400
        if user:
            login_user(user)
            from flask import redirect, url_for
            if user.is_admin:
                return redirect(url_for('admin.dashboard'))
            return redirect(url_for('public.index'))
        return "User not found", 404
    
    # 404 - Not Found (TR)
    @app.errorhandler(404)
    def not_found(error):
        try:
            return render_template('404.html'), 404
        except Exception:
            return "Aradığınız sayfa bulunamadı.", 404

    # 500 - Show real error in development to fix Internal Server Error
    @app.errorhandler(500)
    def internal_error(error):
        if app.config.get('DEBUG'):
            import traceback
            tb = traceback.format_exc()
            return f'<pre style="white-space:pre-wrap;text-align:left;">Internal Server Error\n\n{tb}</pre>', 500
        return "Internal Server Error", 500

    return app

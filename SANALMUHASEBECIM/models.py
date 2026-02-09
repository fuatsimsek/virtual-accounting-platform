from SANALMUHASEBECIM.extensions import db, login_manager
from sqlalchemy import Index
from datetime import datetime, timedelta
from flask_login import UserMixin
import secrets

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Unicode(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(20))
    birthdate = db.Column(db.Date)
    address = db.Column(db.Unicode(200))
    job = db.Column(db.Unicode(100))
    is_admin = db.Column(db.Boolean, default=False)
    email_confirmed = db.Column(db.Boolean, default=False)
    confirmation_token = db.Column(db.String(100), nullable=True, index=True)
    reset_token = db.Column(db.String(100), nullable=True, index=True)
    reset_token_expiry = db.Column(db.DateTime)
    role = db.Column(db.String(20), default='client')  # admin|staff|client
    profile_photo = db.Column(db.String(255))  # Profil fotoğrafı URL'i
    new_email = db.Column(db.String(120))  # Yeni e-posta (onay bekleyen)
    old_email_token = db.Column(db.String(100))  # Eski e-posta onay kodu
    new_email_token = db.Column(db.String(100))  # Yeni e-posta onay kodu
    email_change_expiry = db.Column(db.DateTime)  # E-posta değiştirme son tarihi
    delete_account_token = db.Column(db.String(100))  # Hesap silme onay kodu
    delete_account_expiry = db.Column(db.DateTime)  # Hesap silme kod son tarihi
    password_change_token = db.Column(db.String(100))  # Şifre değiştirme onay kodu
    password_change_expiry = db.Column(db.DateTime)  # Şifre değiştirme kod son tarihi
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    seen_notifications = db.Column(db.Text)  # JSON: which notifications user has seen

    # İlişkiler
    comments = db.relationship('Comment', backref='author', lazy=True)
    appointments = db.relationship('Appointment', foreign_keys='Appointment.user_id', backref='user', lazy=True)
    staff_appointments = db.relationship('Appointment', foreign_keys='Appointment.staff_id', backref='staff', lazy=True)
    profile = db.relationship('Profile', backref='user', uselist=False, lazy=True)
    tickets = db.relationship('Ticket', foreign_keys='Ticket.user_id', lazy=True)
    ticket_messages = db.relationship('TicketMessage', foreign_keys='TicketMessage.user_id', lazy=True)
    assigned_tickets = db.relationship('Ticket', foreign_keys='Ticket.assigned_to', lazy=True)
    completed_tickets = db.relationship('Ticket', foreign_keys='Ticket.completed_by', lazy=True)
    
    # CRM İlişkileri
    service_requests = db.relationship('ServiceRequest', foreign_keys='ServiceRequest.user_id', back_populates='user', lazy=True)
    leads = db.relationship('Lead', foreign_keys='Lead.user_id', back_populates='user', lazy=True)
    customer_services = db.relationship('CustomerService', foreign_keys='CustomerService.user_id', back_populates='user', lazy=True)

    def __init__(self, name, email, password, phone=None, birthdate=None, address=None, job=None):
        self.name = name
        self.email = email
        self.password = password
        self.phone = phone
        self.birthdate = birthdate
        self.address = address
        self.job = job

    def __repr__(self):
        return f'User: {self.name}, {self.email}'

    # Flask-Login aktiflik kontrolü: pasif kullanıcılar giriş yapamaz
    @property
    def is_active(self):  # type: ignore[override]
        try:
            return (self.role or 'client') != 'disabled'
        except Exception:
            return True

    def generate_confirmation_token(self):
        if not self.confirmation_token:
            self.confirmation_token = secrets.token_urlsafe(32)
            db.session.commit()
        return self.confirmation_token

    def generate_reset_token(self):
        self.reset_token = secrets.token_urlsafe(32)
        self.reset_token_expiry = datetime.utcnow() + timedelta(hours=1)  # 1 saat geçerli
        db.session.commit()
        return self.reset_token

    def is_reset_token_valid(self):
        if not self.reset_token or not self.reset_token_expiry:
            return False
        return datetime.utcnow() < self.reset_token_expiry

    def clear_reset_token(self):
        self.reset_token = None
        self.reset_token_expiry = None
        db.session.commit()

    def mark_notification_seen(self, notification_type, notification_id):
        """Mark a specific notification as seen by the user"""
        import json
        if not hasattr(self, 'seen_notifications'):
            return
        seen = self.get_seen_notifications()
        key = f"{notification_type}_{notification_id}"
        seen[key] = True
        self.seen_notifications = json.dumps(seen)
        db.session.commit()

    def has_seen_notification(self, notification_type, notification_id):
        """Check if user has seen a specific notification"""
        import json
        seen = self.get_seen_notifications()
        key = f"{notification_type}_{notification_id}"
        return seen.get(key, False)

    def get_seen_notifications(self):
        """Get the dictionary of seen notifications"""
        import json
        val = getattr(self, 'seen_notifications', None)
        if not val:
            return {}
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return {}

class Profile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    company_name = db.Column(db.String(150))
    tax_office = db.Column(db.String(100))
    tax_number = db.Column(db.String(50))
    address = db.Column(db.String(250))
    notes = db.Column(db.Text)

# Post-Tag ilişki tablosu
post_tag = db.Table(
    'post_tag',
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)

class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False)

class Media(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    file_name = db.Column(db.String(255), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    mime = db.Column(db.String(100))
    size = db.Column(db.Integer)  # bytes
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    subtitle = db.Column(db.String(150))
    slug = db.Column(db.String(160), unique=True)
    excerpt = db.Column(db.String(300))
    post_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    post_text = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    status = db.Column(db.String(20), default='draft')  # draft|published
    published_at = db.Column(db.DateTime)
    seo_title = db.Column(db.String(160))
    seo_desc = db.Column(db.String(180))

    # Ana sayfa öne çıkanlar için
    is_featured = db.Column(db.Boolean, nullable=False, default=False)
    featured_order = db.Column(db.Integer)  # küçükten büyüğe sıralanır

    cover_id = db.Column(db.Integer, db.ForeignKey('media.id'))
    cover = db.relationship('Media', lazy=True)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    author = db.relationship('User', backref='posts', lazy=True)
    comments = db.relationship('Comment', backref='post', lazy=True, cascade='all, delete-orphan')
    likes = db.relationship('Like', backref='post', lazy=True, cascade='all, delete-orphan')

    tags = db.relationship('Tag', secondary=post_tag, lazy='subquery', backref=db.backref('posts', lazy=True))

    def __init__(self, title, subtitle, post_text, user):
        self.title = title
        self.subtitle = subtitle
        self.post_text = post_text
        self.author = user
        self.is_active = True

    def __repr__(self):
        return f'Post: {self.title}, {self.subtitle}'

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True)
    is_approved = db.Column(db.Boolean, default=True)
    like_count = db.Column(db.Integer, default=0)

    # İlişkiler
    replies = db.relationship('Comment', backref=db.backref('parent', remote_side=[id]), lazy=True)
    likes = db.relationship('CommentLike', backref='comment', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'Comment by User {self.user_id} on Post {self.post_id}'

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

    # İlişkiler
    user = db.relationship('User', backref='post_likes', lazy=True)

    def __repr__(self):
        return f'Like by User {self.user_id} on Post {self.post_id}'

class CommentLike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    comment_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # İlişkiler
    user = db.relationship('User', backref='comment_likes', lazy=True)

    def __repr__(self):
        return f'CommentLike by User {self.user_id} on Comment {self.comment_id}'

class Appointment(db.Model):
    __tablename__ = 'Appointments'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    appointment_datetime = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, confirmed, cancelled, awaiting_payment, paid, completed
    purpose = db.Column(db.Text, nullable=True)  # Randevu amacı
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Opsiyonel, giriş yapmış kullanıcılar için
    service_request_id = db.Column(db.Integer, db.ForeignKey('service_request.id'), nullable=True)  # Hizmet talebi ile bağlantı

    # Opsiyonel yeni alanlar (ileri kullanım için)
    staff_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    starts_at = db.Column(db.DateTime)
    ends_at = db.Column(db.DateTime)
    meeting_link = db.Column(db.String(500))
    platform = db.Column(db.String(20))  # meet|zoom|teams
    payment_status = db.Column(db.String(20), default='none')  # none|awaiting|paid
    price_amount = db.Column(db.Numeric(10, 2))

    def __init__(self, email, appointment_datetime, purpose=None, user=None, notes=None, status='pending', service_request_id=None):
        self.email = email
        self.appointment_datetime = appointment_datetime
        self.purpose = purpose
        self.user = user
        self.notes = notes
        self.status = status
        self.service_request_id = service_request_id

    def __repr__(self):
        return f'Appointment({self.email}, {self.appointment_datetime})'

class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), default='new')  # new|open|waiting|closed|completed
    priority = db.Column(db.String(20), default='normal')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    closed_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)  # Tamamlanma tarihi
    completed_by = db.Column(db.Integer, db.ForeignKey('user.id'))  # Kim tamamladı
    assigned_to = db.Column(db.Integer, db.ForeignKey('user.id'))  # Atanan yetkili
    messages = db.relationship('TicketMessage', backref='ticket', lazy=True, cascade='all, delete-orphan')
    
    # İlişkiler
    owner = db.relationship('User', foreign_keys=[user_id])
    assignee = db.relationship('User', foreign_keys=[assigned_to])
    completer = db.relationship('User', foreign_keys=[completed_by])

class TicketMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('ticket.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    attachment_id = db.Column(db.Integer, db.ForeignKey('media.id'))
    attachment = db.relationship('Media')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_internal = db.Column(db.Boolean, default=False)
    message_type = db.Column(db.String(20), default='text')  # text|system|status_change
    read_at = db.Column(db.DateTime)  # Mesaj okunma zamanı
    
    # İlişkiler
    author = db.relationship('User', foreign_keys=[user_id])

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(160), unique=True, nullable=False)
    summary = db.Column(db.String(300))
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(10, 2))
    is_active = db.Column(db.Boolean, default=True)
    order_index = db.Column(db.Integer, default=0)

class ContactLead(db.Model):
    """İletişim formu lead modeli - Basit iletişim talepleri için"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(30))
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'))
    service = db.relationship('Service')
    message = db.Column(db.Text)
    utm_source = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(30), default='new')

class Subscriber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), unique=True, nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_notified_at = db.Column(db.DateTime)

class MonthlyPayment(db.Model):
    """Aylık ödeme modeli - Aylık müşterilerin ödemelerini takip etmek için"""
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('lead.id'), nullable=False)
    lead = db.relationship('Lead', backref='monthly_payments')
    payment_month = db.Column(db.Date, nullable=False)  # Hangi ay için ödeme (YYYY-MM-01)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, paid, confirmed, overdue
    payment_date = db.Column(db.Date)  # Kullanıcının ödeme yaptığı tarih
    confirmation_date = db.Column(db.DateTime)  # Admin'in onayladığı tarih
    next_payment_date = db.Column(db.Date)  # Bir sonraki ödeme tarihi
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'MonthlyPayment(lead_id={self.lead_id}, month={self.payment_month}, status={self.status})'

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User')
    type = db.Column(db.String(20))  # email|sms|whatsapp
    payload_json = db.Column(db.Text)
    sent_at = db.Column(db.DateTime)
    status = db.Column(db.String(20))

# Yeni CRM Modelleri
class ServiceRequest(db.Model):
    """Hizmet talep modeli - Kullanıcının hizmet talebi"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    additional_details = db.Column(db.Text)  # Ekstra detaylar
    status = db.Column(db.String(20), default='pending')  # pending, approved, payment_confirmed, completed, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime)
    approved_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    payment_confirmed_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    
    # İlişkiler
    user = db.relationship('User', foreign_keys=[user_id], back_populates='service_requests')
    service = db.relationship('Service', backref='requests')
    approver = db.relationship('User', foreign_keys=[approved_by])
    lead = db.relationship('Lead', backref='service_request', uselist=False)
    appointment = db.relationship('Appointment', backref='service_request', uselist=False)

class Lead(db.Model):
    """Lead modeli - Müşteri adayı"""
    id = db.Column(db.Integer, primary_key=True)
    service_request_id = db.Column(db.Integer, db.ForeignKey('service_request.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    # MSSQL tablo şemasında NOT NULL olan name sütunu
    name = db.Column(db.String(150), nullable=False, default='Lead')
    
    # Lead bilgileri
    lead_type = db.Column(db.String(20), default='monthly')  # monthly, one_time
    status = db.Column(db.String(20), default='active')  # active, cancelled, completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    cancelled_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    
    # Ödeme bilgileri
    monthly_amount = db.Column(db.Numeric(10, 2))  # Aylık ücret
    one_time_amount = db.Column(db.Numeric(10, 2))  # Tek seferlik ücret
    payment_method = db.Column(db.String(20), default='bank_transfer')  # bank_transfer, automatic
    iban = db.Column(db.String(50))  # IBAN numarası
    # Ödeme aktarımı yapılacak alıcı bilgisi (Ad Soyad) - UTF-8 destekli
    recipient_full_name = db.Column(db.Unicode(150))
    next_payment_date = db.Column(db.Date)  # Sonraki ödeme tarihi
    
    # Görüşme bilgileri
    meeting_link = db.Column(db.String(500))
    meeting_date = db.Column(db.DateTime)
    
    # İlişkiler
    user = db.relationship('User', foreign_keys=[user_id], back_populates='leads')
    service = db.relationship('Service')
    payments = db.relationship('Payment', backref='lead', lazy=True)
    customer_services = db.relationship('CustomerService', backref='lead', lazy=True)

class Payment(db.Model):
    """Ödeme modeli"""
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('lead.id'), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, paid, overdue, cancelled
    payment_method = db.Column(db.String(20), default='bank_transfer')
    transaction_id = db.Column(db.String(100))  # Banka işlem numarası
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    paid_at = db.Column(db.DateTime)

class CustomerService(db.Model):
    """Müşteri hizmeti modeli - Aktif hizmetler"""
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('lead.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Hizmet detayları
    service_name = db.Column(db.String(150), nullable=False)
    service_details = db.Column(db.Text)  # Admin tarafından belirlenen detaylar
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date)  # Aylık hizmetler için null, tek seferlik için dolu
    status = db.Column(db.String(20), default='active')  # active, cancelled, completed
    
    # Fiyat bilgileri
    monthly_fee = db.Column(db.Numeric(10, 2))  # Aylık ücret
    one_time_fee = db.Column(db.Numeric(10, 2))  # Tek seferlik ücret
    total_amount = db.Column(db.Numeric(10, 2))  # Toplam tutar
    
    # Admin notları
    admin_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # İlişkiler
    user = db.relationship('User', foreign_keys=[user_id], back_populates='customer_services')
    service = db.relationship('Service')

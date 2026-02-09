from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, BooleanField, DateField, TimeField, SelectField, DecimalField, IntegerField, EmailField, HiddenField, DateTimeField
from wtforms.validators import DataRequired, Length, Email, Optional, EqualTo, ValidationError, NumberRange
import re
from datetime import datetime, timedelta, date

# Türkçe karakter desteği için regex pattern
TURKISH_CHAR_PATTERN = r'^[a-zA-ZğüşıöçĞÜŞİÖÇ\s\-\.]+$'
TURKISH_TEXT_PATTERN = r'^[a-zA-ZğüşıöçĞÜŞİÖÇ0-9\s\-\.\,\!\?\:\;\(\)\"\']+$'

def validate_turkish_text(field, message="Sadece Türkçe karakterler, sayılar ve temel noktalama işaretleri kullanılabilir"):
    """Türkçe metin validasyonu"""
    if field.data and not re.match(TURKISH_TEXT_PATTERN, field.data):
        raise ValidationError(message)

def validate_turkish_name(field, message="Sadece Türkçe karakterler ve boşluk kullanılabilir"):
    """Türkçe isim validasyonu"""
    if field.data and not re.match(TURKISH_CHAR_PATTERN, field.data):
        raise ValidationError(message)

class RegisterForm(FlaskForm):
    name = StringField('Ad Soyad', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email', validators=[DataRequired(), Email(check_deliverability=False, message='Geçerli bir e-posta adresi girin')])
    password = PasswordField('Şifre', validators=[DataRequired(), Length(min=8, message='Şifre en az 8 karakter olmalıdır'),
        ])
    confirm_password = PasswordField('Şifre Tekrar', validators=[DataRequired(), EqualTo('password', message='Şifreler eşleşmiyor!')])
    phone = StringField('Telefon', validators=[Optional(), Length(min=10, max=20)])
    birthdate = DateField('Doğum Tarihi', validators=[Optional()])
    address = StringField('Adres', validators=[Optional(), Length(max=200)])
    job = StringField('Meslek', validators=[Optional(), Length(max=100)])
    accept_terms = BooleanField('KVKK ve Kullanım Şartlarını kabul ediyorum', validators=[DataRequired(message='Devam etmek için şartları kabul etmelisiniz')])
    submit = SubmitField('Kayıt Ol')

    @staticmethod
    def _validate_password_policy(pwd: str) -> bool:
        if not pwd or len(pwd) < 8:
            return False
        if not re.search(r"[A-Z]", pwd):
            return False
        if not re.search(r"[a-z]", pwd):
            return False
        if not re.search(r"[0-9]", pwd):
            return False
        if not re.search(r"[^A-Za-z0-9]", pwd):
            return False
        return True

    def validate_password(self, field):
        if not self._validate_password_policy(field.data):
            raise ValidationError('Şifre en az 8 karakter, bir büyük harf, bir küçük harf, bir sayı ve bir sembol içermelidir. Bu dışında desteklenmemektedir.')

    def validate_birthdate(self, field):
        if field.data:
            today = date.today()
            age = today.year - field.data.year - ((today.month, today.day) < (field.data.month, field.data.day))
            if age < 18:
                raise ValidationError('18 yaş altı kayıt olamaz.')
            if field.data > today:
                raise ValidationError('Doğum tarihi ileri bir tarih olamaz.')
    
    def validate_phone(self, field):
        if field.data:
            # Türkiye telefon numarası formatı kontrolü
            phone = field.data.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
            if not phone.startswith('+90') and not phone.startswith('0'):
                raise ValidationError('Geçerli bir Türkiye telefon numarası giriniz.')
            if len(phone) < 10 or len(phone) > 13:
                raise ValidationError('Telefon numarası 10-13 karakter arasında olmalıdır.')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email(check_deliverability=False, message='Geçerli bir e-posta adresi girin')])
    password = PasswordField('Şifre', validators=[DataRequired()])
    remember = BooleanField('Beni Hatırla')
    submit = SubmitField('GİRİŞ YAP')

class ForgotPasswordForm(FlaskForm):
    email = StringField('E-posta', validators=[DataRequired(), Email(check_deliverability=False, message='Geçerli bir e-posta adresi girin')])
    submit = SubmitField('Şifre Sıfırlama Bağlantısı Gönder')

class ResetPasswordForm(FlaskForm):
    new_password = PasswordField('Yeni Şifre', validators=[DataRequired(), Length(min=8, message='Şifre en az 8 karakter olmalıdır')])
    confirm_new_password = PasswordField('Yeni Şifre (Tekrar)', validators=[DataRequired(), EqualTo('new_password', message='Şifreler eşleşmiyor!')])
    submit = SubmitField('Şifreyi Sıfırla')

    @staticmethod
    def _validate_password_policy(pwd: str) -> bool:
        if not pwd or len(pwd) < 8:
            return False
        if not re.search(r"[A-Z]", pwd):
            return False
        if not re.search(r"[a-z]", pwd):
            return False
        if not re.search(r"[0-9]", pwd):
            return False
        if not re.search(r"[^A-Za-z0-9]", pwd):
            return False
        return True

    def validate_new_password(self, field):
        if not self._validate_password_policy(field.data):
            raise ValidationError('Şifre en az 8 karakter, bir büyük harf, bir küçük harf, bir sayı ve bir sembol içermelidir. Bu dışında desteklenmemektedir.')

class PostForm(FlaskForm):
    title = StringField('Başlık', validators=[DataRequired(), Length(max=150)])
    subtitle = StringField('Alt Başlık', validators=[Optional(), Length(max=150)])
    post_text = TextAreaField('İçerik', validators=[DataRequired()])
    submit = SubmitField('PAYLAŞ')

class ContactForm(FlaskForm):
    name = StringField('İsim', validators=[DataRequired()])
    email = StringField('Email Adresi', validators=[DataRequired(), Email(check_deliverability=False, message='Geçerli bir e-posta adresi girin')])
    phone = StringField('Telefon Numarası', validators=[DataRequired()])
    subject = StringField('Konu', validators=[DataRequired(), Length(max=150)])
    message = TextAreaField('Mesaj', validators=[DataRequired()])
    submit = SubmitField('GÖNDER')

    def validate_name(self, field):
        validate_turkish_name(field, "İsim sadece Türkçe karakterler ve boşluk içerebilir")
    
    def validate_subject(self, field):
        validate_turkish_text(field, "Konu sadece Türkçe karakterler, sayılar ve temel noktalama işaretleri içerebilir")
    
    def validate_message(self, field):
        validate_turkish_text(field, "Mesaj sadece Türkçe karakterler, sayılar ve temel noktalama işaretleri içerebilir")

class EditUserForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email(check_deliverability=False, message='Geçerli bir e-posta adresi girin')])
    is_admin = BooleanField('Is Admin')
    submit = SubmitField('Update')

    def validate_name(self, field):
        validate_turkish_name(field, "İsim sadece Türkçe karakterler ve boşluk içerebilir")

class CommentForm(FlaskForm):
    content = TextAreaField('Yorum', validators=[DataRequired()])
    submit = SubmitField('YORUM YAP')

class DanismanlikForm(FlaskForm):
    email = StringField('E-posta', validators=[DataRequired(), Email(check_deliverability=False, message='Geçerli bir e-posta adresi girin')])
    appointment_date = DateField('Randevu Tarihi', validators=[DataRequired()], format='%Y-%m-%d')
    appointment_time = SelectField('Randevu Saati', validators=[DataRequired()], choices=[])
    platform = SelectField('Görüşme Platformu', validators=[DataRequired()], choices=[
        ('meet', 'Google Meet'),
        ('zoom', 'Zoom'),
        ('teams', 'Microsoft Teams'),
    ], default='meet')
    purpose = TextAreaField('Randevu Amacı', validators=[DataRequired()])
    submit = SubmitField('Randevu Al')

    def __init__(self, *args, **kwargs):
        super(DanismanlikForm, self).__init__(*args, **kwargs)
        # Saat seçeneklerini oluştur (09:00-17:00 arası, 30'ar dakikalık dilimler)
        time_slots = []
        for hour in range(9, 18):
            for minute in ['00', '30']:
                time_slots.append((f'{hour:02d}:{minute}', f'{hour:02d}:{minute}'))
        self.appointment_time.choices = time_slots

    def validate_appointment_date(self, field):
        today = date.today()
        max_date = today + timedelta(days=14)  # 2 hafta
        
        if field.data < today:
            raise ValidationError('Randevu tarihi bugünden önce olamaz.')
        if field.data > max_date:
            raise ValidationError('Randevu tarihi en fazla 2 hafta sonrası için alınabilir.')

class UpdatePasswordForm(FlaskForm):
    old_password = PasswordField('Eski Şifre', validators=[DataRequired()])
    new_password = PasswordField('Yeni Şifre', validators=[DataRequired(), Length(min=8, message='Şifre en az 8 karakter olmalıdır')])
    confirm_new_password = PasswordField('Yeni Şifre (Tekrar)', validators=[DataRequired(), EqualTo('new_password', message='Şifreler eşleşmiyor!')])
    submit = SubmitField('Şifreyi Güncelle')

    @staticmethod
    def _validate_password_policy(pwd: str) -> bool:
        if not pwd or len(pwd) < 8:
            return False
        if not re.search(r"[A-Z]", pwd):
            return False
        if not re.search(r"[a-z]", pwd):
            return False
        if not re.search(r"[0-9]", pwd):
            return False
        if not re.search(r"[^A-Za-z0-9]", pwd):
            return False
        return True

    def validate_new_password(self, field):
        if not self._validate_password_policy(field.data):
            raise ValidationError('Şifre en az 8 karakter, bir büyük harf, bir küçük harf, bir sayı ve bir sembol içermelidir. Bu dışında desteklenmemektedir.')

# KALDIRILDI - CompleteProfileForm
# class CompleteProfileForm(FlaskForm):
#     # KALDIRILDI

# Yeni formlar
class ServiceForm(FlaskForm):
    name = StringField('Hizmet Adı', validators=[DataRequired(), Length(max=150)])
    slug = StringField('URL Slug', validators=[DataRequired(), Length(max=160)])
    summary = StringField('Özet', validators=[Optional(), Length(max=300)])
    description = TextAreaField('Açıklama', validators=[Optional()])
    price = DecimalField('Fiyat', validators=[Optional(), NumberRange(min=0)])
    is_active = BooleanField('Aktif', default=True)
    order_index = IntegerField('Sıra', validators=[Optional()], default=0)
    submit = SubmitField('Kaydet')

    def validate_name(self, field):
        validate_turkish_name(field, "Hizmet adı sadece Türkçe karakterler ve boşluk içerebilir")
    
    def validate_slug(self, field):
        validate_turkish_text(field, "URL slug sadece Türkçe karakterler, sayılar ve temel noktalama işaretleri içerebilir")

class LeadForm(FlaskForm):
    name = StringField('Ad Soyad', validators=[DataRequired(), Length(min=2, max=120)])
    email = EmailField('E-posta', validators=[DataRequired(), Email(check_deliverability=False, message='Geçerli bir e-posta adresi girin')])
    phone = StringField('Telefon', validators=[Optional(), Length(max=30)])
    service_id = SelectField('Hizmet', coerce=int, validators=[DataRequired()])
    message = TextAreaField('Mesaj', validators=[Optional(), Length(max=1000)])
    utm_source = HiddenField('UTM Source')
    submit = SubmitField('Gönder')

    def __init__(self, *args, **kwargs):
        super(LeadForm, self).__init__(*args, **kwargs)
        from SANALMUHASEBECIM.models import Service
        self.service_id.choices = [(s.id, s.name) for s in Service.query.filter_by(is_active=True).order_by(Service.order_index).all()]

    def validate_name(self, field):
        validate_turkish_name(field, "Ad soyad sadece Türkçe karakterler ve boşluk içerebilir")

class ServiceRequestForm(FlaskForm):
    """Hizmet talep formu"""
    additional_details = TextAreaField('Ekstra Detaylar', validators=[
        Optional(), 
        Length(max=2000, message='Maksimum 2000 karakter girebilirsiniz.')
    ], render_kw={
        'placeholder': 'Bu paketle ilgili ekstra ihtiyaçlarınızı veya özel isteklerinizi yazabilirsiniz...',
        'rows': 4
    })
    submit = SubmitField('Ön Görüşme Talep Et')

    def validate_additional_details(self, field):
        if field.data:
            validate_turkish_text(field, "Ekstra detaylar sadece Türkçe karakterler, sayılar ve temel noktalama işaretleri içerebilir")

class LeadManagementForm(FlaskForm):
    """Lead yönetim formu - Admin için"""
    lead_type = SelectField('Lead Tipi', choices=[
        ('monthly', 'Aylık Müşteri'),
        ('one_time', 'Tek Seferlik')
    ], validators=[DataRequired()])
    monthly_amount = DecimalField('Aylık Ücret', validators=[Optional()])
    one_time_amount = DecimalField('Tek Seferlik Ücret', validators=[Optional()])
    payment_method = SelectField('Ödeme Yöntemi', choices=[
        ('bank_transfer', 'Banka Havalesi'),
        ('automatic', 'Otomatik Ödeme')
    ], validators=[DataRequired()])
    iban = StringField('IBAN', validators=[Optional(), Length(max=50)])
    next_payment_date = DateField('Sonraki Ödeme Tarihi', validators=[Optional()])
    meeting_link = StringField('Görüşme Linki', validators=[Optional(), Length(max=500)])
    meeting_date = DateTimeField('Görüşme Tarihi', validators=[Optional()])
    submit = SubmitField('Lead Oluştur')

class CustomerServiceForm(FlaskForm):
    """Müşteri hizmeti formu - Admin için"""
    service_name = StringField('Hizmet Adı', validators=[DataRequired(), Length(max=150)])
    service_details = TextAreaField('Hizmet Detayları', validators=[Optional()])
    start_date = DateField('Başlangıç Tarihi', validators=[DataRequired()])
    end_date = DateField('Bitiş Tarihi', validators=[Optional()])
    monthly_fee = DecimalField('Aylık Ücret', validators=[Optional()])
    one_time_fee = DecimalField('Tek Seferlik Ücret', validators=[Optional()])
    total_amount = DecimalField('Toplam Tutar', validators=[Optional()])
    admin_notes = TextAreaField('Admin Notları', validators=[Optional()])
    submit = SubmitField('Hizmet Oluştur')

    def validate_service_name(self, field):
        validate_turkish_name(field, "Hizmet adı sadece Türkçe karakterler ve boşluk içerebilir")
    
    def validate_service_details(self, field):
        if field.data:
            validate_turkish_text(field, "Hizmet detayları sadece Türkçe karakterler, sayılar ve temel noktalama işaretleri içerebilir")
    
    def validate_admin_notes(self, field):
        if field.data:
            validate_turkish_text(field, "Admin notları sadece Türkçe karakterler, sayılar ve temel noktalama işaretleri içerebilir")

class PaymentForm(FlaskForm):
    """Ödeme formu - Admin için"""
    amount = DecimalField('Tutar', validators=[DataRequired()])
    payment_date = DateField('Ödeme Tarihi', validators=[DataRequired()])
    due_date = DateField('Vade Tarihi', validators=[DataRequired()])
    payment_method = SelectField('Ödeme Yöntemi', choices=[
        ('bank_transfer', 'Banka Havalesi'),
        ('automatic', 'Otomatik Ödeme')
    ], validators=[DataRequired()])
    transaction_id = StringField('İşlem Numarası', validators=[Optional(), Length(max=100)])
    notes = TextAreaField('Notlar', validators=[Optional()])
    submit = SubmitField('Ödeme Oluştur')

    def validate_notes(self, field):
        if field.data:
            validate_turkish_text(field, "Notlar sadece Türkçe karakterler, sayılar ve temel noktalama işaretleri içerebilir")

class ProfileForm(FlaskForm):
    company_name = StringField('Şirket Adı', validators=[Optional(), Length(max=150)])
    tax_office = StringField('Vergi Dairesi', validators=[Optional(), Length(max=100)])
    tax_number = StringField('Vergi Numarası', validators=[Optional(), Length(max=50)])
    address = StringField('Adres', validators=[Optional(), Length(max=250)])
    notes = TextAreaField('Notlar', validators=[Optional()])
    submit = SubmitField('Profil Güncelle')

    def validate_company_name(self, field):
        if field.data:
            validate_turkish_name(field, "Şirket adı sadece Türkçe karakterler ve boşluk içerebilir")
    
    def validate_tax_office(self, field):
        if field.data:
            validate_turkish_name(field, "Vergi dairesi sadece Türkçe karakterler ve boşluk içerebilir")
    
    def validate_address(self, field):
        if field.data:
            validate_turkish_text(field, "Adres sadece Türkçe karakterler, sayılar ve temel noktalama işaretleri içerebilir")
    
    def validate_notes(self, field):
        if field.data:
            validate_turkish_text(field, "Notlar sadece Türkçe karakterler, sayılar ve temel noktalama işaretleri içerebilir")

class TicketForm(FlaskForm):
    subject = StringField('Konu', validators=[DataRequired(), Length(max=200)])
    message = TextAreaField('Mesaj', validators=[DataRequired()])
    priority = SelectField('Öncelik', choices=[
        ('low', 'Düşük'),
        ('normal', 'Normal'),
        ('high', 'Yüksek'),
        ('urgent', 'Acil')
    ], default='normal')
    submit = SubmitField('Ticket Oluştur')

    def validate_subject(self, field):
        validate_turkish_text(field, "Konu sadece Türkçe karakterler, sayılar ve temel noktalama işaretleri içerebilir")
    
    def validate_message(self, field):
        validate_turkish_text(field, "Mesaj sadece Türkçe karakterler, sayılar ve temel noktalama işaretleri içerebilir")
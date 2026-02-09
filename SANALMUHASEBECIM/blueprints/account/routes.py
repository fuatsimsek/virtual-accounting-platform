from flask import render_template, flash, redirect, url_for, request, current_app, jsonify, session
from flask_login import login_user, current_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from . import bp
from SANALMUHASEBECIM.models import User, Media, Profile, ServiceRequest, Lead, CustomerService, Payment, Service, MonthlyPayment
from SANALMUHASEBECIM.forms import RegisterForm, LoginForm, ForgotPasswordForm, ResetPasswordForm, UpdatePasswordForm, ProfileForm, ServiceRequestForm
from SANALMUHASEBECIM.extensions import db, limiter, oauth, csrf
from authlib.integrations.base_client.errors import OAuthError
from SANALMUHASEBECIM.utils import send_confirmation_email, send_password_reset_email, send_telegram_message
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta
import secrets
import random


def allowed_file(filename):
    allowed = current_app.config.get('ALLOWED_EXTENSIONS', set())
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed



@bp.route("/register", methods=['GET','POST'])
@limiter.limit("20 per hour")
def register():
    if current_user.is_authenticated:
        return redirect(url_for('public.index'))
    form = RegisterForm()
    if form.validate_on_submit():
        # Önce e-posta kontrolü yap
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            flash(f'Bu e-posta adresi ({form.email.data}) zaten kayıtlı. Giriş yapmak için <a href="{url_for("account.login")}" class="alert-link">buraya tıklayın</a> veya şifrenizi unuttuysanız <a href="{url_for("account.forgot_password")}" class="alert-link">şifrenizi sıfırlayın</a>.', 'warning')
            return render_template('register.html', title='Kayıt Ol', form=form)
        
        try:
            hashed_password = generate_password_hash(form.password.data)
            user = User(
                name=form.name.data,
                email=form.email.data,
                password=hashed_password,
                phone=form.phone.data,
                birthdate=form.birthdate.data,
                address=form.address.data,
                job=form.job.data
            )
            # SQL Server'da UNIQUE + NULL çakışmasını önlemek için ilk commit öncesi token ata
            import secrets as _secrets
            user.confirmation_token = _secrets.token_urlsafe(32)
            db.session.add(user)
            db.session.commit()

            # Onay e-postası gönder
            send_confirmation_email(user)

            flash(f'Hoş geldiniz {form.name.data}! Kayıt işleminiz başarıyla tamamlandı. E-posta adresinizi onaylamak için gelen kutunuzu kontrol edin.', 'success')
            return redirect(url_for('account.login'))
        except IntegrityError:
            db.session.rollback()
            flash('Kayıt sırasında bir hata oluştu. Lütfen tekrar deneyin.', 'danger')
    return render_template('register.html', title='Kayıt Ol', form=form)

@bp.route('/confirm/<token>')
def confirm_email(token):
    user = User.query.filter_by(confirmation_token=token).first()
    if user is None:
        flash('Geçersiz veya süresi dolmuş onay bağlantısı.', 'danger')
        return redirect(url_for('public.index'))
    
    user.email_confirmed = True
    user.confirmation_token = None
    db.session.commit()
    
    flash('E-posta adresiniz başarıyla onaylandı! Artık giriş yapabilirsiniz.', 'success')
    return redirect(url_for('account.login'))

@bp.route("/login", methods=['GET','POST'])
@limiter.limit("60 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('public.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password, form.password.data):
            # Pasif kullanıcılara giriş izni verme
            if getattr(user, 'role', None) == 'disabled':
                flash('Hesabınız pasif durumdadır. Lütfen yönetici ile iletişime geçin.', 'danger')
                return redirect(url_for('account.login'))
            if not user.email_confirmed:
                resend_url = url_for('account.resend_confirmation', email=form.email.data)
                flash(f'Merhaba {user.name}! Hesabınıza erişim için önce e-posta adresinizi onaylamanız gerekiyor. Onay linkini almadıysanız <a href="{resend_url}" class="alert-link">buraya tıklayarak</a> tekrar gönderebilirsiniz.', 'warning')
                return redirect(url_for('account.login'))
            # Remember me özelliği için
            remember_me = form.remember.data
            login_user(user, remember=remember_me)
            
            if remember_me:
                # Remember me seçildiyse session'ı uzun süreli yap
                session.permanent = True
                session['_remember'] = True
                flash(f'Hoş geldiniz {user.name}! Başarıyla giriş yaptınız.', 'success')
            else:
                session.permanent = False
                session['_remember'] = False
                flash(f'Hoş geldiniz {user.name}! Başarıyla giriş yaptınız.', 'success')
            
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('public.index'))
        else:
            # Kullanıcı var mı kontrol et
            user_exists = User.query.filter_by(email=form.email.data).first()
            if user_exists:
                flash(f'Şifre yanlış! <a href="{url_for("account.forgot_password")}" class="alert-link">Şifrenizi mi unuttunuz?</a>', 'danger')
            else:
                flash(f'Bu e-posta adresi ({form.email.data}) ile kayıtlı hesap bulunamadı. <a href="{url_for("account.register")}" class="alert-link">Kayıt olmak için tıklayın</a>.', 'warning')
    return render_template('login.html', title='Giriş Yap', form=form)

@bp.route('/login/google')
def login_google():
    # Google OAuth yapılandırması var mı kontrol et
    if 'google' not in oauth._clients:
        flash('Google ile giriş henüz yapılandırılmadı.', 'info')
        return redirect(url_for('account.login'))
    # Proxy (trycloudflare) arkasında ise HTTPS şemasını zorla
    forwarded_proto = request.headers.get('X-Forwarded-Proto', '').lower()
    is_cloudflare = isinstance(request.host, str) and request.host.endswith('trycloudflare.com')
    scheme = 'https' if (forwarded_proto == 'https' or is_cloudflare) else request.scheme
    redirect_uri = url_for('account.google_callback', _external=True, _scheme=scheme)
    return oauth.google.authorize_redirect(redirect_uri)

@bp.route('/login/facebook')
def login_facebook():
    if 'facebook' not in oauth._clients:
        flash('Facebook ile giriş henüz yapılandırılmadı.', 'info')
        return redirect(url_for('account.login'))
    redirect_uri = url_for('account.facebook_callback', _external=True, _scheme='https')
    return oauth.facebook.authorize_redirect(redirect_uri)

@bp.route('/auth/google/callback')
def google_callback():
    if 'google' not in oauth._clients:
        flash('Google OAuth yapılandırması eksik.', 'danger')
        return redirect(url_for('account.login'))
    try:
        # Token alma sırasında aynı redirect_uri'yi geç
        forwarded_proto = request.headers.get('X-Forwarded-Proto', '').lower()
        is_cloudflare = isinstance(request.host, str) and request.host.endswith('trycloudflare.com')
        scheme = 'https' if (forwarded_proto == 'https' or is_cloudflare) else request.scheme
        # authorize_access_token redirect_uri'sini içerde kendisi kullanır; tekrar geçmeyelim
        token = oauth.google.authorize_access_token()
        user_info = None
        try:
            # OIDC id_token parse etmeyi dene
            user_info = oauth.google.parse_id_token(token)
        except Exception:
            user_info = None
        if not user_info:
            # UserInfo endpoint'inden al (resmi OIDC userinfo)
            resp = oauth.google.get('https://openidconnect.googleapis.com/v1/userinfo')
            if resp is not None and resp.status_code == 200:
                user_info = resp.json()

        if not user_info:
            flash('Google kimlik bilgileri alınamadı.', 'danger')
            return redirect(url_for('account.login'))

        email = user_info.get('email')
        name = user_info.get('name') or user_info.get('given_name') or email or 'Google User'
        if not email:
            flash('Google e-posta bilgisi gerekli ve paylaşılamadı.', 'danger')
            return redirect(url_for('account.login'))

        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(name=name, email=email, password=generate_password_hash(secrets.token_urlsafe(16)))
            user.email_confirmed = True
            user.confirmation_token = secrets.token_urlsafe(32)
            user.reset_token = secrets.token_urlsafe(32)
            db.session.add(user)
            db.session.commit()

        login_user(user, remember=True)
        user.last_login = datetime.utcnow()
        db.session.commit()

        try:
            kvkk_url = url_for('public.kvkk')
            terms_url = url_for('public.terms')
            flash(
                f"""
                <div>
                    <div style='font-weight:700;margin-bottom:6px;'>KVKK ve Kullanım Koşulları</div>
                    <div style='font-size:13px;color:#475569;margin-bottom:8px;'>Devam etmeden önce metinleri incelemek ister misiniz?</div>
                    <div style='display:flex;gap:8px;flex-wrap:wrap;'>
                        <a href='{kvkk_url}' class='btn btn-sm btn-primary' style='padding:6px 10px;border-radius:8px;'>KVKK</a>
                        <a href='{terms_url}' class='btn btn-sm btn-outline-primary' style='padding:6px 10px;border-radius:8px;'>Kullanım Şartları</a>
                    </div>
                </div>
                """,
                'kvkk_terms'
            )
        except Exception:
            pass

        next_page = request.args.get('next')
        return redirect(next_page) if next_page else redirect(url_for('public.index'))
    except OAuthError as oe:
        try:
            current_app.logger.error(f"[Google OAuth] {oe.error} - {oe.description}")
        except Exception:
            pass
        flash('Google ile giriş yapılamadı. Lütfen tekrar deneyin.', 'danger')
        return redirect(url_for('account.login'))
    except Exception as e:
        try:
            # Sunucu loguna detay yaz (kullanıcıya göstermeden)
            resp = getattr(e, 'response', None)
            if resp is not None:
                current_app.logger.error(f"[Google OAuth] Token error body: {resp.text}")
            current_app.logger.exception(f"[Google OAuth] Callback error: {e}")
        except Exception:
            pass
        flash('Google ile giriş yapılamadı. Lütfen tekrar deneyin. (Yönlendirme URI ve istemci ayarlarını kontrol edin)', 'danger')
        return redirect(url_for('account.login'))

@bp.route('/auth/facebook/callback')
def facebook_callback():
    if 'facebook' not in oauth._clients:
        flash('Facebook OAuth yapılandırması eksik.', 'danger')
        return redirect(url_for('account.login'))
    token = oauth.facebook.authorize_access_token()
    resp = oauth.facebook.get('me?fields=id,name,email', token=token)
    data = resp.json()
    email = data.get('email')
    name = data.get('name') or email or 'Facebook User'
    if not email:
        flash('Facebook e-posta bilgisi gerekli ve paylaşılamadı.', 'danger')
        return redirect(url_for('account.login'))
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(name=name, email=email, password=generate_password_hash(secrets.token_urlsafe(16)))
        user.email_confirmed = True
        user.confirmation_token = secrets.token_urlsafe(32)  # Generate unique token
        user.reset_token = secrets.token_urlsafe(32)  # Generate unique reset token
        db.session.add(user)
        db.session.commit()
    login_user(user, remember=True)
    user.last_login = datetime.utcnow()
    db.session.commit()
    # KVKK/Kullanım şartları hatırlatması (küçük sağ panel, 10 sn'de kapanır)
    try:
        kvkk_url = url_for('public.kvkk')
        terms_url = url_for('public.terms')
        flash(
            f"""
            <div>
                <div style='font-weight:700;margin-bottom:6px;'>KVKK ve Kullanım Koşulları</div>
                <div style='font-size:13px;color:#475569;margin-bottom:8px;'>Devam etmeden önce metinleri incelemek ister misiniz?</div>
                <div style='display:flex;gap:8px;flex-wrap:wrap;'>
                    <a href='{kvkk_url}' class='btn btn-sm btn-primary' style='padding:6px 10px;border-radius:8px;'>KVKK</a>
                    <a href='{terms_url}' class='btn btn-sm btn-outline-primary' style='padding:6px 10px;border-radius:8px;'>Kullanım Şartları</a>
                </div>
            </div>
            """,
            'kvkk_terms'
        )
    except Exception:
        pass
    return redirect(url_for('public.index'))

@bp.route("/logout")
def logout():
    # Remember me cookie'sini temizle
    response = redirect(url_for('public.index'))
    response.delete_cookie('remember_token')
    logout_user()
    return response

@bp.route("/debug-session")
@login_required
def debug_session():
    """Debug için session bilgilerini göster"""
    session_info = {
        'user_id': current_user.id,
        'user_name': current_user.name,
        'session_permanent': session.get('_permanent', False),
        'session_lifetime': session.get('_fresh', False),
        'remember_me': session.get('_remember', False),
        'all_session_keys': list(session.keys())
    }
    return jsonify(session_info)

@bp.route("/forgot-password", methods=['GET', 'POST'])
@limiter.limit("30 per minute")
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('public.index'))
    
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        # Pasif hesaplara reset maili gönderme
        if user and getattr(user, 'role', None) == 'disabled':
            flash('Bu hesap pasif durumdadır. Lütfen yönetici ile iletişime geçin.', 'warning')
            return redirect(url_for('account.login'))
        if user:
            send_password_reset_email(user)
        flash('Şifre sıfırlama bağlantısı e-posta adresinize gönderildi.', 'info')
        return redirect(url_for('account.login'))
    
    return render_template('forgot_password.html', title='Şifremi Unuttum', form=form)

@bp.route("/reset-password/<token>", methods=['GET', 'POST'])
@limiter.limit("30 per minute")
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('public.index'))
    
    user = User.query.filter_by(reset_token=token).first()
    if not user or not user.is_reset_token_valid():
        flash('Geçersiz veya süresi dolmuş şifre sıfırlama bağlantısı.', 'danger')
        return redirect(url_for('account.forgot_password'))
    # Pasif hesap şifre sıfırlamasını engelle
    if getattr(user, 'role', None) == 'disabled':
        flash('Bu hesap pasif durumdadır. Lütfen yönetici ile iletişime geçin.', 'danger')
        return redirect(url_for('account.login'))
    
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.password = generate_password_hash(form.new_password.data)
        user.clear_reset_token()
        flash('Şifreniz başarıyla güncellendi! Artık yeni şifrenizle giriş yapabilirsiniz.', 'success')
        return redirect(url_for('account.login'))
    
    return render_template('reset_password.html', title='Şifre Sıfırla', form=form)

@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = UpdatePasswordForm()
    company_form = ProfileForm(obj=current_user.profile)
    if request.method == 'POST' and 'old_password' in request.form and form.validate_on_submit():
        if check_password_hash(current_user.password, form.old_password.data):
            current_user.password = generate_password_hash(form.new_password.data)
            db.session.commit()
            flash('Şifreniz başarıyla güncellendi!', 'success')
            return redirect(url_for('account.profile'))
        else:
            flash('Mevcut şifreniz yanlış!', 'danger')
    elif request.method == 'POST' and 'company_name' in request.form and company_form.validate_on_submit():
        profile = current_user.profile or Profile(user_id=current_user.id)
        company_form.populate_obj(profile)
        db.session.add(profile)
        db.session.commit()
        flash('Şirket bilgileriniz güncellendi.', 'success')
        return redirect(url_for('account.profile'))
    
    # Kullanıcı dosyaları
    uploads = Media.query.filter_by(user_id=current_user.id).order_by(Media.created_at.desc()).all()
    
    # Aylık hizmetler: aktif olanlar (paid/completed) + iptal edilmiş fakat son ödeme tarihine kadar erişimi devam edenler
    today = datetime.utcnow().date()
    active_monthly_services = Lead.query.filter(
        Lead.user_id == current_user.id,
        Lead.lead_type == 'monthly',
        (
            Lead.status.in_(['completed', 'paid']) |
            ((Lead.status == 'cancelled') & (Lead.next_payment_date != None) & (Lead.next_payment_date >= today))
        )
    ).all()
    
    # Her aylık hizmet için ödeme bilgilerini hazırla
    for service in active_monthly_services:
        # Son ödeme kaydını bul
        last_payment = MonthlyPayment.query.filter_by(lead_id=service.id).order_by(MonthlyPayment.payment_month.desc()).first()
        service.last_payment = last_payment
        
        # Bir sonraki ödeme tarihini hesapla
        if last_payment and last_payment.next_payment_date:
            service.next_payment_date = last_payment.next_payment_date
        elif service.next_payment_date:
            service.next_payment_date = service.next_payment_date
        else:
            # İlk ödeme için varsayılan tarih
            service.next_payment_date = datetime.utcnow().date().replace(day=28)
        
        # Onaylanmış ödeme bildirimlerini görüldü olarak işaretle
        if last_payment and last_payment.status == 'confirmed':
            notification_id = f"payment_confirmed_{service.id}_{last_payment.payment_month.strftime('%Y%m')}"
            # Notification will be marked as seen when displayed in template
            service.notification_id = notification_id
    
    return render_template('profile.html', title='Profil', form=form, company_form=company_form, uploads=uploads, active_monthly_services=active_monthly_services, now=datetime.utcnow().date())

@bp.route('/mark-notification-seen', methods=['POST'])
@login_required
@csrf.exempt
def mark_notification_seen():
    """Mark a notification as seen via AJAX"""
    data = request.get_json()
    notification_type = data.get('type')
    notification_id = data.get('id')
    
    if notification_type and notification_id:
        current_user.mark_notification_seen(notification_type, notification_id)
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Missing parameters'})

@bp.route('/upload', methods=['POST'])
@login_required
def upload():
    if 'file' not in request.files:
        flash('Dosya bulunamadı.', 'danger')
        return redirect(url_for('account.profile'))
    file = request.files['file']
    if file.filename == '':
        flash('Dosya seçilmedi.', 'danger')
        return redirect(url_for('account.profile'))
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)
        # URL oluştur (statik yol)
        rel_path = os.path.relpath(filepath, os.path.join(current_app.root_path, 'static'))
        url = url_for('static', filename=rel_path.replace('\\', '/'))
        media = Media(file_name=filename, url=url, mime=file.mimetype, size=os.path.getsize(filepath), user_id=current_user.id)
        db.session.add(media)
        db.session.commit()
        flash('Dosya yüklendi.', 'success')
    else:
        flash('İzin verilmeyen dosya türü.', 'danger')
    return redirect(url_for('account.profile'))

@bp.route('/upload-profile-photo', methods=['POST'])
@login_required
@csrf.exempt
def upload_profile_photo():
    if 'profile_photo' not in request.files:
        flash('Profil fotoğrafı seçilmedi.', 'danger')
        return redirect(url_for('account.profile'))
    
    file = request.files['profile_photo']
    if file.filename == '':
        flash('Profil fotoğrafı seçilmedi.', 'danger')
        return redirect(url_for('account.profile'))
    
    # Sadece resim dosyalarına izin ver
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    if not ('.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
        flash('Sadece resim dosyaları yüklenebilir (PNG, JPG, JPEG, GIF, WEBP).', 'danger')
        return redirect(url_for('account.profile'))
    
    if file and file.filename:
        filename = secure_filename(f"profile_{current_user.id}_{int(datetime.utcnow().timestamp())}.{file.filename.rsplit('.', 1)[1].lower()}")
        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)
        
        # URL oluştur
        rel_path = os.path.relpath(filepath, os.path.join(current_app.root_path, 'static'))
        url = url_for('static', filename=rel_path.replace('\\', '/'))
        
        # Kullanıcının profil fotoğrafını güncelle
        current_user.profile_photo = url
        db.session.commit()
        
        flash('Profil fotoğrafınız başarıyla güncellendi.', 'success')
    else:
        flash('Profil fotoğrafı yüklenirken hata oluştu.', 'danger')
    
    return redirect(url_for('account.profile'))

@bp.route('/notify-payment/<int:lead_id>', methods=['POST'])
@login_required
def notify_payment(lead_id):
    """Kullanıcının ödeme yaptığını bildirmesi - Ödeme Bekleniyor durumundaki lead'ler için"""
    lead = Lead.query.get_or_404(lead_id)
    
    # Kullanıcının kendi lead'i mi kontrol et
    if lead.user_id != current_user.id:
        flash('Bu işlem için yetkiniz yok.', 'danger')
        return redirect(url_for('account.my_services'))
    
    # Lead durumu "payment_pending" mi kontrol et
    if lead.status != 'payment_pending':
        flash('Bu işlem sadece ödeme bekleyen hizmetler için geçerlidir.', 'danger')
        return redirect(url_for('account.my_services'))
    
    # Lead tipini kontrol et
    if lead.lead_type not in ['one_time_payment_pending', 'monthly_payment_pending']:
        flash('Bu işlem sadece ödeme bekleyen hizmetler için geçerlidir.', 'danger')
        return redirect(url_for('account.my_services'))
    
    # Lead durumunu "user_paid" olarak güncelle
    lead.status = 'user_paid'  # Kullanıcı ödedi durumu
    db.session.commit()
    
    # Admin'e bildirim gönder
    try:
        service_name = lead.service.name if lead.service else 'Hizmet'
        amount = lead.one_time_amount if 'one_time' in lead.lead_type else lead.monthly_amount
        send_telegram_message(f"💰 Ödeme Bildirimi\n\nMüşteri: {current_user.name}\nHizmet: {service_name}\nTutar: {amount} ₺\nLead ID: #{lead.id}\n\nAdmin panelinden 'Ödeme Alındı' olarak onaylayabilirsiniz.")
    except:
        pass
    
    flash('Ödeme bildiriminiz alındı. Admin onayından sonra durum güncellenecektir.', 'success')
    return redirect(url_for('account.my_services'))

@bp.route('/update-profile', methods=['POST'])
@login_required
def update_profile():
    try:
        # Profil bilgilerini güncelle
        current_user.name = request.form.get('name', current_user.name)
        current_user.phone = request.form.get('phone') or None
        current_user.job = request.form.get('job') or None
        current_user.address = request.form.get('address') or None
        
        # Doğum tarihi
        birthdate_str = request.form.get('birthdate')
        if birthdate_str:
            try:
                current_user.birthdate = datetime.strptime(birthdate_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        
        # E-posta değişikliği kontrolü
        new_email = request.form.get('new_email')
        if new_email and new_email != current_user.email:
            # Yeni e-posta zaten kullanılıyor mu kontrol et
            existing_user = User.query.filter_by(email=new_email).first()
            if existing_user:
                flash('Bu e-posta adresi zaten kullanılıyor.', 'danger')
                return redirect(url_for('account.profile'))
            
            # E-posta değiştirme işlemini başlat
            current_user.new_email = new_email
            current_user.old_email_token = secrets.token_urlsafe(32)
            current_user.new_email_token = secrets.token_urlsafe(32)
            current_user.email_change_expiry = datetime.utcnow() + timedelta(hours=24)
            
            # E-posta gönderme (şimdilik sadece flash message)
            flash(f'E-posta değiştirme işlemi başlatıldı. Önce {current_user.email} adresine, sonra {new_email} adresine onay kodu gönderilecektir.', 'info')
        
        db.session.commit()
        flash('Profil bilgileriniz başarıyla güncellendi.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Profil güncellenirken bir hata oluştu.', 'danger')
    
    return redirect(url_for('account.profile'))

@bp.route('/confirm-old-email/<token>')
@login_required
def confirm_old_email(token):
    if (current_user.old_email_token == token and 
        current_user.email_change_expiry and 
        current_user.email_change_expiry > datetime.utcnow()):
        
        flash(f'Eski e-posta onaylandı. Şimdi {current_user.new_email} adresine gelen onay kodunu kullanın.', 'success')
        # Gerçek uygulamada burada yeni e-postaya kod gönderilecek
        return redirect(url_for('account.profile'))
    else:
        flash('Geçersiz veya süresi dolmuş onay kodu.', 'danger')
        return redirect(url_for('account.profile'))

@bp.route('/confirm-new-email/<token>')
@login_required
def confirm_new_email(token):
    if (current_user.new_email_token == token and 
        current_user.email_change_expiry and 
        current_user.email_change_expiry > datetime.utcnow() and
        current_user.old_email_token is None):  # Eski e-posta onaylanmış olmalı
        
        # E-posta değişikliğini tamamla
        current_user.email = current_user.new_email
        current_user.new_email = None
        current_user.old_email_token = None
        current_user.new_email_token = None
        current_user.email_change_expiry = None
        
        db.session.commit()
        flash('E-posta adresiniz başarıyla değiştirildi.', 'success')
        return redirect(url_for('account.profile'))
    else:
        flash('Geçersiz veya süresi dolmuş onay kodu.', 'danger')
        return redirect(url_for('account.profile'))

@bp.route('/send-password-change-code', methods=['POST'])
@login_required
def send_password_change_code():
    try:
        data = request.get_json()
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        
        # Mevcut şifreyi kontrol et
        if not current_user.check_password(current_password):
            return jsonify({'success': False, 'message': 'Mevcut şifre yanlış.'})
        
        # 6 haneli kod oluştur
        code = str(random.randint(100000, 999999))
        
        # Kodu veritabanına kaydet
        current_user.password_change_token = code
        current_user.password_change_expiry = datetime.utcnow() + timedelta(minutes=15)
        db.session.commit()
        
        # E-posta gönderme (şimdilik konsola yazdır)
        print(f"Şifre değiştirme kodu: {code} - {current_user.email}")
        
        return jsonify({'success': True, 'message': 'Onay kodu e-posta adresinize gönderildi.'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': 'Bir hata oluştu.'})

@bp.route('/confirm-password-change', methods=['POST'])
@login_required
def confirm_password_change():
    try:
        code = request.form.get('code')
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        
        # Kod kontrolü
        if (current_user.password_change_token != code or 
            not current_user.password_change_expiry or 
            current_user.password_change_expiry < datetime.utcnow()):
            flash('Geçersiz veya süresi dolmuş onay kodu.', 'danger')
            return redirect(url_for('account.profile'))
        
        # Mevcut şifreyi tekrar kontrol et
        if not current_user.check_password(current_password):
            flash('Mevcut şifre yanlış.', 'danger')
            return redirect(url_for('account.profile'))
        
        # Şifreyi güncelle
        current_user.set_password(new_password)
        current_user.password_change_token = None
        current_user.password_change_expiry = None
        db.session.commit()
        
        flash('Şifreniz başarıyla değiştirildi.', 'success')
        return redirect(url_for('account.profile'))
        
    except Exception as e:
        flash('Şifre değiştirilirken hata oluştu.', 'danger')
        return redirect(url_for('account.profile'))

@bp.route('/send-delete-code', methods=['POST'])
@login_required
def send_delete_code():
    try:
        # 6 haneli kod oluştur
        code = str(random.randint(100000, 999999))
        
        # Kodu veritabanına kaydet
        current_user.delete_account_token = code
        current_user.delete_account_expiry = datetime.utcnow() + timedelta(minutes=15)
        db.session.commit()
        
        # E-posta gönderme (şimdilik konsola yazdır)
        print(f"Hesap silme kodu: {code} - {current_user.email}")
        
        return jsonify({'success': True, 'message': 'Onay kodu e-posta adresinize gönderildi.'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': 'Bir hata oluştu.'})

@bp.route('/confirm-delete-account', methods=['POST'])
@login_required
def confirm_delete_account():
    try:
        code = request.form.get('code')
        
        # Kod kontrolü
        if (current_user.delete_account_token != code or 
            not current_user.delete_account_expiry or 
            current_user.delete_account_expiry < datetime.utcnow()):
            flash('Geçersiz veya süresi dolmuş onay kodu.', 'danger')
            return redirect(url_for('account.profile'))
        
        # Hesabı sil
        user_name = current_user.name
        db.session.delete(current_user)
        db.session.commit()
        
        flash(f'{user_name}, hesabınız başarıyla silindi.', 'success')
        return redirect(url_for('public.index'))
        
    except Exception as e:
        flash('Hesap silinirken hata oluştu.', 'danger')
        return redirect(url_for('account.profile'))

@bp.route('/delete-account', methods=['POST'])
@login_required
def delete_account():
    # Kullanıcı hesabını silme işlemi
    db.session.delete(current_user)
    db.session.commit()
    logout_user()
    flash('Hesabınız başarıyla silindi.', 'success')
    return redirect(url_for('public.index'))

@bp.route('/resend-confirmation')
def resend_confirmation():
    email = request.args.get('email')
    user = None
    if current_user.is_authenticated:
        user = current_user
    elif email:
        user = User.query.filter_by(email=email).first()
    if not user:
        flash('E-posta adresi bulunamadı. Lütfen yeniden kayıt olun veya giriş deneyin.', 'warning')
        return redirect(url_for('account.login'))
    if getattr(user, 'email_confirmed', False):
        flash('E-posta adresiniz zaten onaylanmış.', 'info')
        return redirect(url_for('account.login'))
    send_confirmation_email(user)
    flash('Onay e-postası tekrar gönderildi. Gelen kutunuzu ve spam klasörünü kontrol edin.', 'success')
    return redirect(url_for('account.login'))

@bp.route('/request-service/<int:service_id>', methods=['GET', 'POST'])
@login_required
def request_service(service_id):
    """Hizmet talep etme sayfası"""
    service = Service.query.get_or_404(service_id)
    form = ServiceRequestForm()
    
    if form.validate_on_submit():
        # Kullanıcının bekleyen hizmet talebi var mı kontrol et
        pending_request = ServiceRequest.query.filter_by(
            user_id=current_user.id, 
            status='pending'
        ).first()
        
        if pending_request:
            flash('Bekleyen bir hizmet talebiniz var. Ön görüşme planlama adımına yönlendirildiniz.', 'info')
            return redirect(url_for('booking.new_appointment', service_request_id=pending_request.id))
        
        # Hizmet talebi oluştur
        service_request = ServiceRequest(
            user_id=current_user.id,
            service_id=service_id,
            additional_details=form.additional_details.data,
            status='pending'
        )
        
        db.session.add(service_request)
        db.session.commit()
        
        # Randevu sayfasına yönlendir
        return redirect(url_for('booking.new_appointment', service_request_id=service_request.id))
    
    return render_template('account/request_service.html', title='Hizmet Talep Et', form=form, service=service)

@bp.route('/my-services')
@login_required
def my_services():
    """Kullanıcının hizmetleri sayfası"""
    # Hizmet talepleri
    service_requests = ServiceRequest.query.filter_by(user_id=current_user.id).order_by(ServiceRequest.created_at.desc()).all()
    
    # Aktif hizmetler (CustomerService)
    customer_services = CustomerService.query.filter_by(user_id=current_user.id).order_by(CustomerService.created_at.desc()).all()
    
    # Lead'ler
    leads = Lead.query.filter_by(user_id=current_user.id).order_by(Lead.created_at.desc()).all()
    
    # Her lead için bildirim ID'lerini hazırla
    for lead in leads:
        if lead.status == 'completed':
            # Tamamlanan hizmetler için bildirim ID'si
            notification_id = f"service_completed_{lead.id}"
            lead.notification_id = notification_id
    
    # Şu anki tarih (gecikmiş ödemeler için)
    now = datetime.utcnow().date()
    
    return render_template('account/my_services.html', 
                         title='Hizmetlerim', 
                         service_requests=service_requests,
                         customer_services=customer_services,
                         leads=leads,
                         now=now)

@bp.route('/service-request/<int:request_id>')
@login_required
def service_request_detail(request_id):
    """Hizmet talep detayı"""
    service_request = ServiceRequest.query.filter_by(id=request_id, user_id=current_user.id).first_or_404()
    
    # İlgili randevu ve lead bilgilerini getir
    appointment = None
    lead = None
    
    if service_request:
        # İlgili randevu
        appointment = service_request.appointment
        
        # İlgili lead
        lead = Lead.query.filter_by(service_request_id=service_request.id).first()
        
        # Lead için bildirim ID'sini hazırla
        if lead and lead.status == 'completed':
            notification_id = f"service_completed_{lead.id}"
            lead.notification_id = notification_id
    
    # Şu anki tarih (gecikmiş ödemeler için)
    now = datetime.utcnow().date()
    
    return render_template('account/service_request_detail.html', 
                         title='Hizmet Talep Detayı', 
                         service_request=service_request,
                         appointment=appointment,
                         lead=lead,
                         now=now)

@bp.route('/customer-service/<int:service_id>')
@login_required
def customer_service_detail(service_id):
    """Müşteri hizmeti detayı"""
    customer_service = CustomerService.query.filter_by(id=service_id, user_id=current_user.id).first_or_404()
    
    # Ödemeler
    payments = Payment.query.filter_by(lead_id=customer_service.lead_id).order_by(Payment.due_date.desc()).all()
    
    return render_template('account/customer_service_detail.html', 
                         title='Hizmet Detayı', 
                         customer_service=customer_service,
                         payments=payments)

# KALDIRILDI - Profil tamamlama özelliği
# @bp.route('/complete-profile', methods=['GET', 'POST'])
# @login_required
# def complete_profile():
#     """Eksik profil bilgilerini tamamlama sayfası"""
#     # KALDIRILDI

# @bp.route('/send-phone-verification', methods=['POST'])
# @login_required
# def send_phone_verification():
#     """Telefon doğrulama kodu gönder"""
#     # KALDIRILDI

from flask import render_template, flash, redirect, url_for, request, jsonify, Response
from flask_login import current_user, login_required
from functools import wraps
from sqlalchemy import text
from . import bp
from SANALMUHASEBECIM.models import User, Post, Comment, Appointment, Service, Lead, Ticket, Subscriber, MonthlyPayment
from sqlalchemy.exc import IntegrityError
from SANALMUHASEBECIM.forms import EditUserForm, ServiceForm
from SANALMUHASEBECIM.extensions import db
from SANALMUHASEBECIM.utils import send_iban_payment_email, send_email, send_telegram_message, create_gcal_event, delete_gcal_event
import csv
import io
from datetime import datetime, timedelta

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Bu sayfaya erişim yetkiniz yok.', 'danger')
            return redirect(url_for('public.index'))
        return f(*args, **kwargs)
    return decorated_function

#def super_admin_required(f):
#    @wraps(f)
#    def decorated_function(*args, **kwargs):
#        if not current_user.is_authenticated:
#            flash('Bu sayfaya erişim için giriş yapmalısınız.', 'danger')
#            return redirect(url_for('public.index'))
#        
#        if not current_user.is_admin:
#            flash('Bu sayfaya erişim yetkiniz yok.', 'danger')
#            return redirect(url_for('public.index'))
#        
#       if not current_user.is_super_admin:
#            flash('Bu işlem için super admin yetkisi gereklidir.', 'danger')
#            return redirect(url_for('admin.dashboard'))
#        
#        return f(*args, **kwargs)
#    return decorated_function

@bp.route("/")
@login_required
@admin_required
def dashboard():
    # Dashboard istatistikleri
    total_users = User.query.count()
    total_posts = Post.query.count()
    total_comments = Comment.query.count()
    total_appointments = Appointment.query.count()
    total_leads = Lead.query.count()
    total_tickets = Ticket.query.count()
    total_services = Service.query.count()
    
    # Son aktiviteler
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    recent_posts = Post.query.order_by(Post.post_date.desc()).limit(5).all()
    recent_appointments = Appointment.query.order_by(Appointment.created_at.desc()).limit(5).all()
    recent_leads = Lead.query.order_by(Lead.created_at.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html', 
                         title='Admin Dashboard',
                         total_users=total_users,
                         total_posts=total_posts,
                         total_comments=total_comments,
                         total_appointments=total_appointments,
                         total_leads=total_leads,
                         total_tickets=total_tickets,
                         total_services=total_services,
                         recent_users=recent_users,
                         recent_posts=recent_posts,
                         recent_appointments=recent_appointments,
                         recent_leads=recent_leads)

@bp.route("/users")
@login_required
@admin_required
def users():
    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', type=str)
    query = User.query
    if q:
        # Türkçe karakter desteği ile arama
        like = f"%{q}%"
        # SQL Server'da Turkish collation kullanarak arama
        query = query.filter(
            text("(User.name COLLATE Turkish_CI_AS LIKE :like COLLATE Turkish_CI_AS) OR (User.email LIKE :email)"),
            like=like, email=like
        )
    users = query.order_by(User.created_at.desc()).paginate(page=page, per_page=20)
    return render_template('admin/users.html', title='Kullanıcı Yönetimi', users=users, q=q)

#@bp.route("/user/<int:user_id>/edit", methods=['GET', 'POST'])
#@login_required
#@admin_required
#def edit_user(user_id):
#    user = User.query.get_or_404(user_id)
#    form = EditUserForm()
#    if form.validate_on_submit():
#        # Admin yetkisi verilirken ekstra güvenlik kontrolü
#        if form.is_admin.data and not user.is_admin:
#            # Sadece super admin başka admin yapabilir
#            if not current_user.is_super_admin:
#                flash('Sadece super admin başka admin yapabilir!', 'danger')
#                return redirect(url_for('admin.users'))
#            
#            # Admin yetkisi verilirken log kaydı
#            app.logger.warning(f'Admin yetkisi verildi: User {user.id} ({user.email}) by {current_user.id} ({current_user.email})')
#        
#        user.name = form.name.data
#        user.email = form.email.data
#        user.is_admin = form.is_admin.data
#        db.session.commit()
#        flash('Kullanıcı başarıyla güncellendi!', 'success')
#        return redirect(url_for('admin.users'))
#    elif request.method == 'GET':
#        form.name.data = user.name
#        form.email.data = user.email
#        form.is_admin.data = user.is_admin
#    return render_template('admin/edit_user.html', title='Kullanıcı Düzenle', form=form, user=user)

@bp.route("/user/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)

    # Formu mevcut kullanıcı objesiyle başlat
    form = EditUserForm(obj=user)

    if form.validate_on_submit():
        from flask import current_app
        became_admin = form.is_admin.data and not user.is_admin
        lost_admin   = (not form.is_admin.data) and user.is_admin

        # KENDİNİ adminlikten alma gibi tehlikeli durumları engelle
        if user.id == current_user.id and lost_admin:
            flash("Kendi admin yetkinizi kaldıramazsınız.", "danger")
            return redirect(url_for("admin.users"))

        # (İstersen) sadece super admin başka birini admin yapabilir kuralı:
        # if became_admin and not current_user.is_super_admin:
        #     flash("Sadece super admin başka kullanıcıyı admin yapabilir.", "danger")
        #     return redirect(url_for("admin.users"))

        # Alanları güncelle
        user.name = form.name.data.strip()
        user.email = form.email.data.strip()
        user.is_admin = bool(form.is_admin.data)

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Bu e-posta zaten kullanılıyor.", "danger")
            return render_template("admin/edit_user.html", title="Kullanıcı Düzenle", form=form, user=user)

        # Basit audit log
        if became_admin:
            current_app.logger.warning(
                f"[ADMIN-GRANT] user_id={user.id} email={user.email} by admin_id={current_user.id} admin_email={current_user.email}"
            )
        elif lost_admin:
            current_app.logger.warning(
                f"[ADMIN-REVOKE] user_id={user.id} email={user.email} by admin_id={current_user.id} admin_email={current_user.email}"
            )

        flash("Kullanıcı başarıyla güncellendi!", "success")
        return redirect(url_for("admin.users"))

    # GET: form zaten obj=user ile dolu
    return render_template("admin/edit_user.html", title="Kullanıcı Düzenle", form=form, user=user)


@bp.route("/user/<int:user_id>/delete", methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user == current_user:
        flash('Kendinizi silemezsiniz!', 'danger')
        return redirect(url_for('admin.users'))
    
    try:
        # Bağımlı kayıtları temizle (ilişkisel bütünlük için)
        Comment.query.filter_by(user_id=user.id).delete(synchronize_session=False)
        Post.query.filter_by(user_id=user.id).delete(synchronize_session=False)
        Ticket.query.filter_by(user_id=user.id).delete(synchronize_session=False)
        Appointment.query.filter_by(user_id=user.id).delete(synchronize_session=False)
        Lead.query.filter_by(user_id=user.id).delete(synchronize_session=False)
        # ServiceRequest tablosunda user_id NOT NULL ise doğrudan sil
        db.session.execute(text("DELETE FROM service_request WHERE user_id = :uid"), {"uid": user.id})

        db.session.delete(user)
        db.session.commit()
        flash('Kullanıcı ve ilişkili kayıtları silindi.', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Kullanıcı silinirken bir bütünlük hatası oluştu. Önce ilişkili kayıtları kaldırın.', 'danger')
    return redirect(url_for('admin.users'))

@bp.route("/user/<int:user_id>/toggle", methods=['POST'])
@login_required
@admin_required
def toggle_user_active(user_id):
    user = User.query.get_or_404(user_id)
    if user.is_admin:
        flash('Admin kullanıcı pasifleştirilemez.', 'danger')
        return redirect(url_for('admin.users'))
    # Basit pasif/aktif: role alanını kullan (disabled ↔ client)
    if user.role == 'disabled':
        user.role = 'client'
        flash('Kullanıcı aktifleştirildi.', 'success')
    else:
        user.role = 'disabled'
        flash('Kullanıcı pasifleştirildi.', 'info')
    db.session.commit()
    return redirect(url_for('admin.users'))

@bp.route("/posts")
@login_required
@admin_required
def posts():
    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', type=str)
    query = Post.query
    if q:
        like = f"%{q}%"
        query = query.join(User, Post.user_id == User.id).filter(
            (Post.title.ilike(like)) | (Post.subtitle.ilike(like)) | (User.name.ilike(like))
        )
    # Öne çıkanları üstte göstermek için sıralama (kolonlar mevcut değilse fallback)
    try:
        posts = query.order_by(
            Post.is_featured.desc(),
            Post.published_at.desc().nullslast(),
            Post.post_date.desc()
        ).paginate(page=page, per_page=20)
    except Exception:
        posts = query.order_by(Post.post_date.desc()).paginate(page=page, per_page=20)
    return render_template('admin/posts.html', title='Gönderi Yönetimi', posts=posts, q=q)


@bp.route("/post/<int:post_id>/feature", methods=['POST'])
@login_required
@admin_required
def feature_post(post_id):
    post = Post.query.get_or_404(post_id)
    is_featured = bool(request.form.get('is_featured'))
    featured_order = None
    # Maksimum 5 öne çıkan sınırı
    if is_featured:
        try:
            current_count = Post.query.filter(Post.is_featured == True, Post.id != post.id).count()
        except Exception:
            current_count = 0
        if current_count >= 5:
            flash('En fazla 5 gönderi öne çıkarılabilir.', 'warning')
            return redirect(request.referrer or url_for('admin.posts'))
        # Sıra mantığı kaldırıldı; sadece featured işaretlenir
    post.is_featured = is_featured
    # Sıra kullanılmıyor; model alanı dursa da set etmiyoruz
    try:
        post.featured_order = None
    except Exception:
        pass
    db.session.commit()
    flash('Öne çıkarma ayarları güncellendi.', 'success')
    return redirect(request.referrer or url_for('admin.posts'))

@bp.route("/post/<int:post_id>/toggle-status", methods=['POST'])
@login_required
@admin_required
def toggle_post_status(post_id):
    post = Post.query.get_or_404(post_id)
    post.is_active = not post.is_active
    db.session.commit()
    status = "aktif" if post.is_active else "pasif"
    flash(f'Gönderi {status} hale getirildi!', 'success')
    return redirect(url_for('admin.posts'))

@bp.route("/comments")
@login_required
@admin_required
def comments():
    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', type=str)
    query = Comment.query
    if q:
        like = f"%{q}%"
        # Join user and post for richer filtering
        query = query.join(User, Comment.user_id == User.id).join(Post, Comment.post_id == Post.id).filter(
            (User.name.ilike(like)) | (Post.title.ilike(like)) | (Comment.content.ilike(like))
        )
    comments = query.order_by(Comment.date.desc()).paginate(page=page, per_page=20)
    pending_count = Comment.query.filter_by(is_approved=False).count()
    return render_template('admin/comments.html', title='Yorum Yönetimi', comments=comments, pending_count=pending_count, q=q)

@bp.route("/comment/<int:comment_id>/approve", methods=['POST'])
@login_required
@admin_required
def approve_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    comment.is_approved = True
    db.session.commit()
    flash('Yorum onaylandı.', 'success')
    return redirect(url_for('admin.comments'))

@bp.route("/comment/<int:comment_id>/delete", methods=['POST'])
@login_required
@admin_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    db.session.delete(comment)
    db.session.commit()
    flash('Yorum başarıyla silindi!', 'success')
    return redirect(url_for('admin.comments'))

@bp.route("/appointments")
@login_required
@admin_required
def appointments():
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status')
    q = request.args.get('q')
    query = Appointment.query
    if status:
        query = query.filter(Appointment.status == status)
    if q:
        # Türkçe karakter desteği ile arama
        query = query.filter(text("Appointment.email COLLATE Turkish_CI_AS LIKE :q COLLATE Turkish_CI_AS"), q=f"%{q}%")
    appointments = query.order_by(Appointment.appointment_datetime.desc()).paginate(page=page, per_page=20)
    return render_template('admin/appointments.html', title='Randevu Yönetimi', appointments=appointments, status=status, q=q)

@bp.route("/appointments/export")
@login_required
@admin_required
def export_appointments():
    status = request.args.get('status')
    q = request.args.get('q')
    query = Appointment.query
    if status:
        query = query.filter(Appointment.status == status)
    if q:
        # Türkçe karakter desteği ile arama
        query = query.filter(text("Appointment.email COLLATE Turkish_CI_AS LIKE :q COLLATE Turkish_CI_AS"), q=f"%{q}%")
    rows = query.order_by(Appointment.appointment_datetime.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["email", "datetime", "status", "purpose"])
    for r in rows:
        writer.writerow([r.email, r.appointment_datetime, r.status, (r.purpose or "")])
    return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=appointments.csv'})

@bp.route("/services")
@login_required
@admin_required
def services():
    page = request.args.get('page', 1, type=int)
    services = Service.query.order_by(Service.id.desc()).paginate(page=page, per_page=20)
    
    # Her hizmet için bağlı kayıt sayılarını hesapla
    from SANALMUHASEBECIM.models import Lead, ServiceRequest
    
    for service in services.items:
        service.lead_count = Lead.query.filter_by(service_id=service.id).count()
        service.service_request_count = ServiceRequest.query.filter_by(service_id=service.id).count()
        service.total_related = (service.lead_count + service.service_request_count)
    
    return render_template('admin/services.html', title='Hizmet Yönetimi', services=services)

@bp.route("/service/new", methods=['GET', 'POST'])
@login_required
@admin_required
def new_service():
    form = ServiceForm()
    if form.validate_on_submit():
        service = Service(
            name=form.name.data,
            slug=form.slug.data,
            summary=form.summary.data,
            description=form.description.data,
            price=form.price.data,
            is_active=form.is_active.data,
            order_index=form.order_index.data
        )
        db.session.add(service)
        db.session.commit()
        flash('Hizmet başarıyla oluşturuldu!', 'success')
        return redirect(url_for('admin.services'))
    return render_template('admin/service_form.html', title='Yeni Hizmet', form=form)

@bp.route("/service/<int:service_id>/edit", methods=['GET', 'POST'])
@login_required
@admin_required
def edit_service(service_id):
    service = Service.query.get_or_404(service_id)
    form = ServiceForm()
    if form.validate_on_submit():
        service.name = form.name.data
        service.slug = form.slug.data
        service.summary = form.summary.data
        service.description = form.description.data
        service.price = form.price.data
        service.is_active = form.is_active.data
        service.order_index = form.order_index.data
        db.session.commit()
        flash('Hizmet başarıyla güncellendi!', 'success')
        return redirect(url_for('admin.services'))
    elif request.method == 'GET':
        form.name.data = service.name
        form.slug.data = service.slug
        form.summary.data = service.summary
        form.description.data = service.description
        form.price.data = service.price
        form.is_active.data = service.is_active
        form.order_index.data = service.order_index
    return render_template('admin/service_form.html', title='Hizmet Düzenle', form=form, service=service)

@bp.route("/service/<int:service_id>/delete", methods=['POST'])
@login_required
@admin_required
def delete_service(service_id):
    service = Service.query.get_or_404(service_id)
    
    try:
        from SANALMUHASEBECIM.models import Lead, ServiceRequest
        
        # Önce ServiceRequest'leri sil (service_id NOT NULL olduğu için)
        service_requests = ServiceRequest.query.filter_by(service_id=service.id).all()
        for sr in service_requests:
            # ServiceRequest'e bağlı Lead'leri de sil
            if hasattr(sr, 'lead') and sr.lead:
                db.session.delete(sr.lead)
            db.session.delete(sr)
        
        # Lead'lerin service_id'sini NULL yap (Lead'de service_id nullable olabilir)
        Lead.query.filter_by(service_id=service.id).update({'service_id': None}, synchronize_session=False)
        
        # Service'i sil
        db.session.delete(service)
        db.session.commit()
        
        deleted_count = len(service_requests)
        flash(f'Hizmet başarıyla silindi. {deleted_count} hizmet talebi ve bağlı lead kaydı silindi.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Hizmet silinirken hata oluştu: {str(e)}', 'danger')
        
    return redirect(url_for('admin.services'))

@bp.route("/service/<int:service_id>/toggle", methods=['POST'])
@login_required
@admin_required
def toggle_service_status(service_id):
    service = Service.query.get_or_404(service_id)
    service.is_active = not service.is_active
    db.session.commit()
    flash(f'Hizmet {"aktif" if service.is_active else "pasif"} yapıldı.', 'success')
    return redirect(url_for('admin.services'))

@bp.route("/services/seed", methods=['POST'])
@login_required
@admin_required
def seed_services():
    defaults = [
        {
            'name': 'Standart Paket',
            'slug': 'standart-paket',
            'description': 'Aylık temel muhasebe danışmanlığı\nAylık özet finansal rapor\nE-posta ile destek\nTemel vergi takvimi hatırlatmaları',
            'order_index': 1
        },
        {
            'name': 'Profesyonel Paket',
            'slug': 'profesyonel-paket',
            'description': 'Kapsamlı muhasebe danışmanlığı\nHaftalık detaylı raporlama\nTelefon + e-posta destek\nVergi planlama ve optimizasyon\nFinansal performans analizi',
            'order_index': 2
        },
        {
            'name': 'Kurumsal Paket',
            'slug': 'kurumsal-paket',
            'description': 'Tam kapsamlı muhasebe hizmeti\nGünlük raporlama ve yönetici özeti\nÖncelikli destek\nŞirketinize özel stratejik danışmanlık\nSüreç dijitalleştirme ve entegrasyon',
            'order_index': 3
        }
    ]
    created_or_updated = 0
    for d in defaults:
        service = Service.query.filter_by(slug=d['slug']).first()
        if not service:
            service = Service(slug=d['slug'])
            db.session.add(service)
        service.name = d['name']
        service.summary = None
        service.description = d['description']
        service.price = None
        service.is_active = True
        service.order_index = d['order_index']
        created_or_updated += 1
    db.session.commit()
    flash(f'Varsayılan paketler yüklendi/güncellendi ({created_or_updated}).', 'success')
    return redirect(url_for('admin.services'))

@bp.route("/leads")
@login_required
@admin_required
def leads():
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status')
    lead_type = request.args.get('lead_type')
    q = request.args.get('q')
    query = Lead.query.join(User).join(Service)
    
    if status:
        query = query.filter(Lead.status == status)
    if lead_type:
        query = query.filter(Lead.lead_type == lead_type)
    if q:
        like = f"%{q}%"
        query = query.filter((User.name.ilike(like)) | (User.email.ilike(like)))
    
    leads = query.order_by(Lead.created_at.desc()).paginate(page=page, per_page=20)
    return render_template('admin/leads.html', title='Lead Yönetimi', leads=leads, status=status, lead_type=lead_type, q=q)

@bp.route("/lead/<int:lead_id>/delete", methods=['POST'])
@login_required
@admin_required
def delete_lead(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    db.session.delete(lead)
    db.session.commit()
    flash('Lead başarıyla silindi!', 'success')
    return redirect(url_for('admin.leads'))

@bp.route("/leads/export")
@login_required
@admin_required
def export_leads():
    status = request.args.get('status')
    q = request.args.get('q')
    query = Lead.query.join(User).join(Service)
    if status:
        query = query.filter(Lead.status == status)
    if q:
        like = f"%{q}%"
        query = query.filter((User.name.ilike(like)) | (User.email.ilike(like)))
    rows = query.order_by(Lead.created_at.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["user_name", "user_email", "service_name", "lead_type", "status", "created_at", "one_time_amount", "monthly_amount", "iban", "next_payment_date"])
    for r in rows:
        writer.writerow([
            r.user.name if r.user else 'N/A',
            r.user.email if r.user else 'N/A',
            r.service.name if r.service else 'N/A',
            r.lead_type,
            r.status,
            r.created_at,
            r.one_time_amount,
            r.monthly_amount,
            r.iban,
            r.next_payment_date
        ])
    return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=leads.csv'})

@bp.route("/ticket/<int:ticket_id>/open", methods=['POST'])
@login_required
@admin_required
def admin_open_ticket(ticket_id):
    """Admin panelinden ticket'ı aç"""
    ticket = Ticket.query.get_or_404(ticket_id)
    
    if ticket.status != 'new':
        flash('Ticket zaten açık veya kapatılmış.', 'info')
        return redirect(url_for('admin.tickets'))
    
    # Ticket durumunu 'open' olarak güncelle
    ticket.status = 'open'
    db.session.commit()
    
    flash('Ticket başarıyla açıldı.', 'success')
    return redirect(url_for('admin.tickets'))

@bp.route("/tickets")
@login_required
@admin_required
def tickets():
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status')
    priority = request.args.get('priority')
    q = request.args.get('q')
    query = Ticket.query
    if status:
        query = query.filter(Ticket.status == status)
    if priority:
        query = query.filter(Ticket.priority == priority)
    if q:
        # Türkçe karakter desteği ile arama
        query = query.filter(text("Ticket.subject COLLATE Turkish_CI_AS LIKE :q COLLATE Turkish_CI_AS"), q=f"%{q}%")
    tickets = query.order_by(Ticket.created_at.desc()).paginate(page=page, per_page=20)
    return render_template('admin/tickets.html', title='Ticket Yönetimi', tickets=tickets, status=status, priority=priority, q=q)

@bp.route("/subscribers")
@login_required
@admin_required
def subscribers():
    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', type=str)
    status = request.args.get('status', type=str)
    query = Subscriber.query
    if q:
        # Türkçe karakter desteği ile arama
        query = query.filter(text("Subscriber.email COLLATE Turkish_CI_AS LIKE :q COLLATE Turkish_CI_AS"), q=f"%{q}%")
    if status == 'active':
        query = query.filter_by(is_active=True)
    elif status == 'inactive':
        query = query.filter_by(is_active=False)
    subs = query.order_by(Subscriber.created_at.desc()).paginate(page=page, per_page=20)
    return render_template('admin/subscribers.html', title='Aboneler', subs=subs, q=q, status=status)

@bp.route("/subscriber/<int:sub_id>/toggle", methods=['POST'])
@login_required
@admin_required
def toggle_subscriber(sub_id):
    sub = Subscriber.query.get_or_404(sub_id)
    sub.is_active = not sub.is_active
    db.session.commit()
    flash('Abone durumu güncellendi.', 'success')
    return redirect(request.referrer or url_for('admin.subscribers'))

@bp.route("/subscriber/add", methods=['POST'])
@login_required
@admin_required
def add_subscriber():
    """Yeni e-posta abonesi ekle"""
    email = request.form.get('email')
    is_active = request.form.get('is_active') == 'true'
    
    if not email:
        flash('E-posta adresi gerekli.', 'danger')
        return redirect(url_for('admin.subscribers'))
    
    # E-posta formatını kontrol et
    if '@' not in email or '.' not in email:
        flash('Geçerli bir e-posta adresi girin.', 'danger')
        return redirect(url_for('admin.subscribers'))
    
    # E-posta zaten var mı kontrol et
    existing_sub = Subscriber.query.filter_by(email=email).first()
    if existing_sub:
        flash('Bu e-posta adresi zaten abone listesinde mevcut.', 'warning')
        return redirect(url_for('admin.subscribers'))
    
    # Yeni abone oluştur
    new_subscriber = Subscriber(
        email=email,
        is_active=is_active,
        created_at=datetime.utcnow()
    )
    
    db.session.add(new_subscriber)
    db.session.commit()
    
    flash(f'{email} adresi başarıyla abone listesine eklendi.', 'success')
    return redirect(url_for('admin.subscribers'))

@bp.route("/subscriber/<int:sub_id>/delete", methods=['POST'])
@login_required
@admin_required
def delete_subscriber(sub_id):
    sub = Subscriber.query.get_or_404(sub_id)
    db.session.delete(sub)
    db.session.commit()
    flash('Abone silindi.', 'success')
    return redirect(request.referrer or url_for('admin.subscribers'))

@bp.route("/ticket/<int:ticket_id>/update-status", methods=['POST'])
@login_required
@admin_required
def update_ticket_status(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    new_status = request.form.get('status')
    if new_status not in ['new','open','waiting','completed']:
        flash('Geçersiz durum.', 'danger')
        return redirect(url_for('admin.tickets'))
    
    ticket.status = new_status
    
    if new_status == 'completed':
        ticket.completed_at = datetime.utcnow()
        ticket.completed_by = current_user.id
    else:
        ticket.closed_at = None
        ticket.completed_at = None
        ticket.completed_by = None
    
    db.session.commit()
    flash('Ticket durumu güncellendi.', 'success')
    # Aynı sayfaya filtreleri koruyarak dön
    return redirect(request.referrer or url_for('admin.tickets'))

@bp.route("/tickets/export")
@login_required
@admin_required
def export_tickets():
    status = request.args.get('status')
    priority = request.args.get('priority')
    q = request.args.get('q')
    query = Ticket.query
    if status:
        query = query.filter(Ticket.status == status)
    if priority:
        query = query.filter(Ticket.priority == priority)
    if q:
        query = query.filter(text("Ticket.subject COLLATE Turkish_CI_AS LIKE :q COLLATE Turkish_CI_AS"), q=f"%{q}%")
    rows = query.order_by(Ticket.created_at.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "user_id", "subject", "status", "priority", "created_at", "completed_at"])
    for r in rows:
        writer.writerow([r.id, r.user_id, r.subject, r.status, r.priority, r.created_at, r.completed_at])
    return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=tickets.csv'})

@bp.route("/analytics")
@login_required
@admin_required
def analytics():
    # Kullanıcı aktivite özeti
    user_activity = db.session.execute(text("""
        SELECT 
            u.name,
            u.email,
            u.profile_photo,
            COUNT(DISTINCT p.id) as post_count,
            COUNT(DISTINCT c.id) as comment_count,
            COUNT(DISTINCT a.id) as appointment_count,
            u.created_at
        FROM "user" u
        LEFT JOIN post p ON u.id = p.user_id
        LEFT JOIN comment c ON u.id = c.user_id
        LEFT JOIN "Appointments" a ON u.id = a.user_id
        GROUP BY u.id, u.name, u.email, u.profile_photo, u.created_at
        ORDER BY u.created_at DESC
    """)).fetchall()
    
    return render_template('admin/analytics.html', title='Analitik', user_activity=user_activity)

@bp.route("/lead/<int:lead_id>/update-type", methods=['POST'])
@login_required
@admin_required
def update_lead_type(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    lead_type = request.form.get('lead_type')
    
    # Tüm geçerli lead tiplerini kontrol et
    valid_lead_types = [
        'one_time_meeting_pending', 'monthly_meeting_pending',
        'one_time_payment_pending', 'monthly_payment_pending', 
        'one_time', 'monthly'
    ]
    
    if lead_type not in valid_lead_types:
        flash('Geçersiz müşteri tipi.', 'danger')
        return redirect(url_for('admin.leads'))
    

    
    lead.lead_type = lead_type
    db.session.commit()
    
    # Başarı mesajları
    if lead_type == 'one_time_meeting_pending':
        flash('Müşteri tipi "Tek Hizmet Görüşme Bekleniyor" olarak güncellendi.', 'success')
    elif lead_type == 'monthly_meeting_pending':
        flash('Müşteri tipi "Aylık Görüşme Bekleniyor" olarak güncellendi.', 'success')
    elif lead_type == 'one_time_payment_pending':
        flash('Müşteri tipi "Tek Hizmet Ödeme Bekleniyor" olarak güncellendi. Şimdi ödeme bilgilerini gönderebilirsiniz.', 'success')
    elif lead_type == 'monthly_payment_pending':
        flash('Müşteri tipi "Aylık Müşteri Ödeme Bekleniyor" olarak güncellendi. Şimdi ödeme bilgilerini gönderebilirsiniz.', 'success')
    elif lead_type == 'one_time':
        flash('Müşteri tipi "Tek Hizmet" olarak güncellendi.', 'success')
    elif lead_type == 'monthly':
        flash('Müşteri tipi "Aylık Müşteri" olarak güncellendi.', 'success')
    
    return redirect(url_for('admin.leads'))

@bp.route("/lead/<int:lead_id>/send-payment-request", methods=['POST'])
@login_required
@admin_required
def send_payment_request(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    amount = request.form.get('amount')
    iban = request.form.get('iban')
    recipient_full_name = request.form.get('recipient_full_name')
    
    # UTF-8 encoding ile alıcı ismini işle
    if recipient_full_name:
        recipient_full_name = recipient_full_name.encode('utf-8').decode('utf-8')
    
    try:
        amount_val = float(amount)
    except (TypeError, ValueError):
        flash('Geçersiz tutar.', 'danger')
        return redirect(url_for('admin.leads'))
    
    if not lead.user or not lead.user.email:
        flash('Lead için e-posta bulunamadı.', 'danger')
        return redirect(url_for('admin.leads'))
    
    # Lead'i güncelle - payment_pending durumunda tutar ve IBAN kaydet
    if lead.lead_type == 'one_time_payment_pending':
        lead.one_time_amount = amount_val
    elif lead.lead_type == 'monthly_payment_pending':
        lead.monthly_amount = amount_val
        lead.next_payment_date = datetime.utcnow() + timedelta(days=30)
    
    lead.iban = iban
    if recipient_full_name:
        lead.recipient_full_name = recipient_full_name.strip()
    lead.status = 'payment_pending'
    db.session.commit()
    
    # E-posta gönder
    service_name = lead.service.name if lead.service else 'Hizmet'
    honorific = 'Bey' if (lead.user and lead.user.name and not lead.user.name.endswith(('Hanım','Bey'))) else 'Hanım'
    user_name = (lead.user.name if lead.user else 'Müşterimiz').split()[0]
    greeting = f"Sayın {user_name} {honorific},"
    recipient_line = f"\nAlıcı: {lead.recipient_full_name}" if lead.recipient_full_name else ""
    if lead.lead_type == 'one_time_payment_pending':
        subject = f"{service_name} Hizmetiniz İçin Ödeme Bilgileri"
        text_body = f"{greeting}\n\nGörüşmemiz sonrasında {service_name} hizmetiniz için ödeme bilgileriniz aşağıdadır:\n\n💰 Tutar: {amount_val:.2f} TL\n🏦 IBAN: {iban}{recipient_line}\n\nÖdemenizi yaptıktan sonra, ödeme onayı alındığında toplantı planlama bilgilerini sizinle paylaşacağız.\n\nHerhangi bir sorunuz olursa bizimle iletişime geçebilirsiniz.\n\nSaygılarımızla,\nSanal Muhasebecim Ekibi"
        html_body = f"<p>{greeting}</p><p>Görüşmemiz sonrasında <strong>{service_name}</strong> hizmetiniz için ödeme bilgileriniz aşağıdadır:</p><div style='background-color: #f8f9fa; padding: 15px; border-radius: 8px; margin: 15px 0;'><p><strong>💰 Tutar:</strong> {amount_val:.2f} TL</p><p><strong>🏦 IBAN:</strong> {iban}</p>{(f'<p><strong>👤 Alıcı:</strong> {lead.recipient_full_name}</p>' if lead.recipient_full_name else '')}</div><p>Ödemenizi yaptıktan sonra, ödeme onayı alındığında toplantı planlama bilgilerini sizinle paylaşacağız.</p><p>Herhangi bir sorunuz olursa bizimle iletişime geçebilirsiniz.</p><p>Saygılarımızla,<br><strong>Sanal Muhasebecim Ekibi</strong></p>"
    else:
        subject = f"{service_name} Aylık Hizmet Ödeme Bilgileri"
        text_body = f"{greeting}\n\n{service_name} aylık hizmetiniz için ödeme bilgileriniz aşağıdadır:\n\n💰 Aylık Tutar: {amount_val:.2f} TL\n🏦 IBAN: {iban}{recipient_line}\n\nHer ay belirtilen tutarı ilgili tarihe kadar ödemenizi rica ederiz. Ödemeniz alındığında hizmetlerimiz devam edecektir.\n\nHerhangi bir sorunuz olursa bizimle iletişime geçebilirsiniz.\n\nSaygılarımızla,\nSanal Muhasebecim Ekibi"
        html_body = f"<p>{greeting}</p><p><strong>{service_name}</strong> aylık hizmetiniz için ödeme bilgileriniz aşağıdadır:</p><div style='background-color: #f8f9fa; padding: 15px; border-radius: 8px; margin: 15px 0;'><p><strong>💰 Aylık Tutar:</strong> {amount_val:.2f} TL</p><p><strong>🏦 IBAN:</strong> {iban}</p>{(f'<p><strong>👤 Alıcı:</strong> {lead.recipient_full_name}</p>' if lead.recipient_full_name else '')}</div><p>Her ay belirtilen tutarı ilgili tarihe kadar ödemenizi rica ederiz. Ödemeniz alındığında hizmetlerimiz devam edecektir.</p><p>Herhangi bir sorunuz olursa bizimle iletişime geçebilirsiniz.</p><p>Saygılarımızla,<br><strong>Sanal Muhasebecim Ekibi</strong></p>"
    
    send_email(subject=subject, recipients=[lead.user.email], text_body=text_body, html_body=html_body)
    flash('Ödeme bilgileri e-posta ile gönderildi. Kullanıcı hizmetlerim sayfasında görebilecek.', 'success')
    return redirect(url_for('admin.leads'))

@bp.route("/lead/<int:lead_id>/confirm-payment", methods=['POST'])
@login_required
@admin_required
def confirm_payment(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    lead.status = 'paid'
    
    # Lead tipini güncelle
    if lead.lead_type == 'one_time_payment_pending':
        lead.lead_type = 'one_time'
    elif lead.lead_type == 'monthly_payment_pending':
        lead.lead_type = 'monthly'
    
    # ServiceRequest durumunu da güncelle
    if lead.service_request:
        lead.service_request.status = 'payment_confirmed'
        lead.service_request.payment_confirmed_at = datetime.utcnow()
    
    db.session.commit()
    
    if lead.user and lead.user.email:
        service_name = lead.service.name if lead.service else 'Hizmet'
        honorific = 'Bey' if (lead.user and lead.user.name and not lead.user.name.endswith(('Hanım','Bey'))) else 'Hanım'
        user_name = (lead.user.name if lead.user else 'Müşterimiz').split()[0]
        greeting = f"Sayın {user_name} {honorific},"
        if lead.lead_type == 'one_time':
            subject = f"{service_name} Hizmetiniz İçin Ödemeniz Alındı"
            text_body = f"{greeting}\n\n✅ {service_name} hizmetiniz için ödemeniz başarıyla alınmıştır.\n\nEn kısa sürede toplantı planlama bilgilerini sizinle paylaşacağız. Toplantı tarih ve saat bilgileri e-posta ile gönderilecektir.\n\nHerhangi bir sorunuz olursa bizimle iletişime geçebilirsiniz.\n\nSaygılarımızla,\nSanal Muhasebecim Ekibi"
            html_body = f"<p>{greeting}</p><p><strong>✅ {service_name} hizmetiniz için ödemeniz başarıyla alınmıştır.</strong></p><p>En kısa sürede toplantı planlama bilgilerini sizinle paylaşacağız. Toplantı tarih ve saat bilgileri e-posta ile gönderilecektir.</p><p>Herhangi bir sorunuz olursa bizimle iletişime geçebilirsiniz.</p><p>Saygılarımızla,<br><strong>Sanal Muhasebecim Ekibi</strong></p>"
        else:
            subject = f"{service_name} Aylık Ödemeniz Alındı"
            text_body = f"{greeting}\n\n✅ {service_name} aylık hizmetiniz için ödemeniz başarıyla alınmıştır.\n\nDesteğimiz planlandığı şekilde devam edecektir. Bir sonraki ay ödeme bilgileri size tekrar gönderilecektir.\n\nHerhangi bir sorunuz olursa bizimle iletişime geçebilirsiniz.\n\nSaygılarımızla,\nSanal Muhasebecim Ekibi"
            html_body = f"<p>{greeting}</p><p><strong>✅ {service_name} aylık hizmetiniz için ödemeniz başarıyla alınmıştır.</strong></p><p>Desteğimiz planlandığı şekilde devam edecektir. Bir sonraki ay ödeme bilgileri size tekrar gönderilecektir.</p><p>Herhangi bir sorunuz olursa bizimle iletişime geçebilirsiniz.</p><p>Saygılarımızla,<br><strong>Sanal Muhasebecim Ekibi</strong></p>"
        
        send_email(
            subject=subject,
            recipients=[lead.user.email],
            text_body=text_body,
            html_body=html_body
        )
    
    flash('Ödeme onaylandı ve müşteri tipi güncellendi.', 'success')
    return redirect(url_for('admin.leads'))

@bp.route("/lead/<int:lead_id>/confirm-user-payment", methods=['POST'])
@login_required
@admin_required
def confirm_user_payment(lead_id):
    """Kullanıcının ödeme bildirimini onayla"""
    lead = Lead.query.get_or_404(lead_id)
    
    # Lead durumunu "paid" yap
    lead.status = 'paid'
    
    # Lead tipini güncelle
    if lead.lead_type == 'one_time_payment_pending':
        lead.lead_type = 'one_time'
    elif lead.lead_type == 'monthly_payment_pending':
        lead.lead_type = 'monthly'
    
    # ServiceRequest durumunu da güncelle
    if lead.service_request:
        lead.service_request.status = 'payment_confirmed'
        lead.service_request.payment_confirmed_at = datetime.utcnow()
    
    db.session.commit()
    
    # Kullanıcıya onay e-postası gönder
    if lead.user and lead.user.email:
        service_name = lead.service.name if lead.service else 'Hizmet'
        honorific = 'Bey' if (lead.user and lead.user.name and not lead.user.name.endswith(('Hanım','Bey'))) else 'Hanım'
        user_name = (lead.user.name if lead.user else 'Müşterimiz').split()[0]
        greeting = f"Sayın {user_name} {honorific},"
        
        if lead.lead_type == 'one_time':
            send_email(
                subject=f"{service_name} - Ödeme Alındı",
                recipients=[lead.user.email],
                text_body=f"{greeting}\n\n{service_name} hizmeti için ödemeniz alınmıştır.\n\nToplantı planlanacak ve bilgiler e-posta ile gönderilecektir.\n\nSaygılarımızla,\nSanal Muhasebecim Ekibi",
                html_body=f"<p>{greeting}</p><p><strong>{service_name} hizmeti için ödemeniz alınmıştır.</strong></p><p>Toplantı planlanacak ve bilgiler e-posta ile gönderilecektir.</p><p>Saygılarımızla,<br><strong>Sanal Muhasebecim Ekibi</strong></p>"
            )
        elif lead.lead_type == 'monthly':
            send_email(
                subject=f"{service_name} - Aylık Ödeme Alındı",
                recipients=[lead.user.email],
                text_body=f"{greeting}\n\n{service_name} hizmeti için aylık ödemeniz alınmıştır.\n\nToplantı planlanacak ve bilgiler e-posta ile gönderilecektir.\n\nSaygılarımızla,\nSanal Muhasebecim Ekibi",
                html_body=f"<p>{greeting}</p><p><strong>{service_name} hizmeti için aylık ödemeniz alınmıştır.</strong></p><p>Toplantı planlanacak ve bilgiler e-posta ile gönderilecektir.</p><p>Saygılarımızla,<br><strong>Sanal Muhasebecim Ekibi</strong></p>"
            )
    
    flash('Kullanıcı ödeme bildirimi onaylandı ve ödeme alındı olarak işaretlendi.', 'success')
    return redirect(url_for('admin.leads'))

@bp.route("/lead/<int:lead_id>/correct-payment", methods=['POST'])
@login_required
@admin_required
def correct_payment(lead_id):
    """Ödeme bilgilerini düzeltmek için ödeme bilgilerini sıfırla ve durumu pending yap"""
    lead = Lead.query.get_or_404(lead_id)
    
    # Ödeme bilgilerini sıfırla
    lead.amount = None
    lead.iban = None
    lead.recipient_full_name = None
    lead.payment_sent_at = None
    
    # Lead durumunu pending yap ki "Ödeme Talebi Gönder" kısmı tekrar görünsün
    lead.status = 'pending'
    
    db.session.commit()
    
    # Kullanıcıya bilgilendirme e-postası gönder
    if lead.user and lead.user.email:
        service_name = lead.service.name if lead.service else 'Hizmet'
        honorific = 'Bey' if (lead.user and lead.user.name and not lead.user.name.endswith(('Hanım','Bey'))) else 'Hanım'
        user_name = (lead.user.name if lead.user else 'Müşterimiz').split()[0]
        greeting = f"Sayın {user_name} {honorific},"
        
        subject = f"{service_name} Ödeme Bilgileri Düzeltildi"
        text_body = f"{greeting}\n\n{service_name} hizmetiniz için ödeme bilgileriniz düzeltilmiştir.\n\nYeni ödeme bilgileri yakında size gönderilecektir.\n\nHerhangi bir sorunuz olursa bizimle iletişime geçebilirsiniz.\n\nSaygılarımızla,\nSanal Muhasebecim Ekibi"
        html_body = f"<p>{greeting}</p><p><strong>{service_name} hizmetiniz için ödeme bilgileriniz düzeltilmiştir.</strong></p><p>Yeni ödeme bilgileri yakında size gönderilecektir.</p><p>Herhangi bir sorunuz olursa bizimle iletişime geçebilirsiniz.</p><p>Saygılarımızla,<br><strong>Sanal Muhasebecim Ekibi</strong></p>"
        
        send_email(
            subject=subject,
            recipients=[lead.user.email],
            text_body=text_body,
            html_body=html_body
        )
    
    flash('Ödeme bilgileri düzeltildi. Lead tekrar "Bekleniyor" durumuna çevrildi. Yeni ödeme bilgileri girebilirsiniz.', 'info')
    return redirect(url_for('admin.leads'))

@bp.route("/confirm-monthly-payment/<int:payment_id>", methods=['POST'])
@login_required
@admin_required
def confirm_monthly_payment(payment_id):
    """Aylık ödeme onayı"""
    payment = MonthlyPayment.query.get_or_404(payment_id)
    
    # Ödeme durumunu güncelle
    payment.status = 'confirmed'
    payment.confirmation_date = datetime.utcnow()
    
    # Lead'in next_payment_date'ini güncelle
    if payment.lead:
        payment.lead.next_payment_date = payment.next_payment_date
    
    db.session.commit()
    
    # Kullanıcıya e-posta gönder
    if payment.lead and payment.lead.user and payment.lead.user.email:
        try:
            # Türkçe ay isimleri
            turkish_months = {
                1: 'Ocak', 2: 'Şubat', 3: 'Mart', 4: 'Nisan', 5: 'Mayıs', 6: 'Haziran',
                7: 'Temmuz', 8: 'Ağustos', 9: 'Eylül', 10: 'Ekim', 11: 'Kasım', 12: 'Aralık'
            }
            
            month_name = turkish_months[payment.payment_month.month]
            year = payment.payment_month.year
            
            send_email(
                subject=f"Ödeme Onaylandı - {month_name} {year}",
                recipients=[payment.lead.user.email],
                body=f"""
                Merhaba {payment.lead.user.name},
                
                {month_name} {year} ayı ödemeniz onaylandı.
                
                Ödeme Detayları:
                - Tutar: {payment.amount} ₺
                - Onay Tarihi: {payment.confirmation_date.strftime('%d.%m.%Y %H:%M')}
                - Sonraki Ödeme Tarihi: {payment.next_payment_date.strftime('%d.%m.%Y')}
                
                Teşekkürler!
                SanalMuhasebe
                """
            )
        except:
            pass
    
    flash(f'{month_name} {year} ayı ödemesi onaylandı.', 'success')
    return redirect(url_for('admin.leads'))

@bp.route("/lead/<int:lead_id>/schedule-meeting", methods=['POST'])
@login_required
@admin_required
def schedule_meeting(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    meeting_date = request.form.get('meeting_date')
    meeting_time = request.form.get('meeting_time')
    platform = request.form.get('platform')
    meeting_link = request.form.get('meeting_link')
    
    # Toplantı tarihini birleştir
    meeting_datetime = datetime.combine(
        datetime.strptime(meeting_date, '%Y-%m-%d').date(),
        datetime.strptime(meeting_time, '%H:%M').time()
    )
    
    # Lead'i güncelle
    lead.meeting_date = meeting_datetime
    lead.meeting_link = meeting_link
    lead.status = 'completed'
    
    # Lead tipini de güncelle (payment_pending durumundan çıkar)
    if lead.lead_type == 'one_time_payment_pending':
        lead.lead_type = 'one_time'
    elif lead.lead_type == 'monthly_payment_pending':
        lead.lead_type = 'monthly'
    
    # ServiceRequest durumunu da güncelle
    if lead.service_request:
        lead.service_request.status = 'completed'
        lead.service_request.completed_at = datetime.utcnow()
    
    db.session.commit()
    
    # Kullanıcıya e-posta gönder
    if lead.user and lead.user.email:
        service_name = lead.service.name if lead.service else 'Hizmet'
        honorific = 'Bey' if (lead.user and lead.user.name and not lead.user.name.endswith(('Hanım','Bey'))) else 'Hanım'
        user_name = (lead.user.name if lead.user else 'Müşterimiz').split()[0]
        greeting = f"Sayın {user_name} {honorific},"
        send_email(
            subject=f"{service_name} Hizmetiniz İçin Toplantı Planlandı",
            recipients=[lead.user.email],
            text_body=f"{greeting}\n\nToplantınız planlanmıştır.\nTarih: {meeting_datetime.strftime('%d.%m.%Y %H:%M')}\nPlatform: {platform}\nLink: {meeting_link}\n\nSaygılarımızla\nSanal Muhasebecim Ekibi",
            html_body=f"<p>{greeting}</p><p>Toplantınız planlanmıştır.</p><p><b>Tarih:</b> {meeting_datetime.strftime('%d.%m.%Y %H:%M')}</p><p><b>Platform:</b> {platform}</p><p><b>Link:</b> <a href='{meeting_link}'>{meeting_link}</a></p><p>Saygılarımızla<br>Sanal Muhasebecim Ekibi</p>"
        )
    
    flash('Toplantı planlandı ve e-posta gönderildi. Kullanıcı hizmetlerim sayfasında görebilecek.', 'success')
    return redirect(url_for('admin.leads'))

@bp.route("/lead/<int:lead_id>/update-monthly-payment", methods=['POST'])
@login_required
@admin_required
def update_monthly_payment(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    new_amount = request.form.get('new_amount')
    new_iban = request.form.get('new_iban')
    new_recipient_full_name = request.form.get('new_recipient_full_name')
    
    if new_amount:
        try:
            lead.monthly_amount = float(new_amount)
        except (TypeError, ValueError):
            flash('Geçersiz tutar.', 'danger')
            return redirect(url_for('admin.leads'))
    
    if new_iban:
        lead.iban = new_iban
    if new_recipient_full_name is not None:
        try:
            lead.recipient_full_name = new_recipient_full_name.encode('utf-8').decode('utf-8').strip() or None
        except Exception:
            lead.recipient_full_name = (new_recipient_full_name or '').strip() or None
    
    # Sonraki ödeme tarihini güncelle (30 gün sonra)
    lead.next_payment_date = datetime.utcnow() + timedelta(days=30)
    
    db.session.commit()
    
    # Kullanıcıya güncelleme e-postası gönder
    if lead.user and lead.user.email:
        update_text = []
        if new_amount:
            update_text.append(f"Yeni aylık tutar: {new_amount} TL")
        if new_iban:
            update_text.append(f"Yeni IBAN: {new_iban}")
        if new_recipient_full_name:
            update_text.append(f"Yeni Alıcı: {lead.recipient_full_name}")
        
        if update_text:
            send_email(
                subject="Ödeme Bilgileri Güncellendi",
                recipients=[lead.user.email],
                text_body=f"Ödeme bilgileriniz güncellendi:\n" + "\n".join(update_text) + f"\n\nSonraki ödeme tarihi: {lead.next_payment_date.strftime('%d.%m.%Y')}",
                html_body=f"<p>Ödeme bilgileriniz güncellendi:</p><ul>" + "".join([f"<li>{text}</li>" for text in update_text]) + f"</ul><p><b>Sonraki ödeme tarihi:</b> {lead.next_payment_date.strftime('%d.%m.%Y')}</p>"
            )
    
    flash('Aylık ödeme bilgileri güncellendi.', 'success')
    return redirect(url_for('admin.leads'))

@bp.route("/send-monthly-reminders", methods=['POST'])
@login_required
@admin_required
def send_monthly_reminders():
    """Aylık müşteriler için ödeme hatırlatması gönder"""
    # Ödeme tarihi yaklaşan aylık müşterileri bul (5 gün kala)
    reminder_date = datetime.utcnow() + timedelta(days=5)
    monthly_leads = Lead.query.filter(
        Lead.lead_type == 'monthly',
        Lead.status.in_(['paid', 'completed']),
        Lead.next_payment_date <= reminder_date,
        Lead.next_payment_date >= datetime.utcnow()
    ).all()
    
    sent_count = 0
    for lead in monthly_leads:
        if lead.user and lead.user.email:
            send_email(
                subject="Aylık Ödeme Hatırlatması",
                recipients=[lead.user.email],
                text_body=f"Aylık ödeme tarihiniz yaklaşıyor.\n\nTutar: {lead.monthly_amount} TL\nIBAN: {lead.iban}\nSon Ödeme Tarihi: {lead.next_payment_date.strftime('%d.%m.%Y')}\n\nÖdemenizi yaptıktan sonra hizmetleriniz devam edecektir.",
                html_body=f"<p>Aylık ödeme tarihiniz yaklaşıyor.</p><p><b>Tutar:</b> {lead.monthly_amount} TL</p><p><b>IBAN:</b> {lead.iban}</p><p><b>Son Ödeme Tarihi:</b> {lead.next_payment_date.strftime('%d.%m.%Y')}</p><p>Ödemenizi yaptıktan sonra hizmetleriniz devam edecektir.</p>"
            )
            sent_count += 1
    
    flash(f'{sent_count} aylık müşteriye ödeme hatırlatması gönderildi.', 'success')
    return redirect(url_for('admin.leads'))

@bp.route("/mark-monthly-payment-received", methods=['POST'])
@login_required
@admin_required
def mark_monthly_payment_received():
    """Aylık ödeme alındı olarak işaretle"""
    lead_id = request.form.get('lead_id')
    lead = Lead.query.get_or_404(lead_id)
    
    if lead.lead_type != 'monthly':
        flash('Bu işlem sadece aylık müşteriler için geçerlidir.', 'danger')
        return redirect(url_for('admin.leads'))
    
    # Sonraki ödeme tarihini 30 gün sonraya ayarla
    lead.next_payment_date = datetime.utcnow() + timedelta(days=30)
    lead.status = 'paid'  # Ödeme alındı olarak işaretle
    db.session.commit()
    
    # Kullanıcıya onay e-postası gönder
    if lead.user and lead.user.email:
        send_email(
            subject="Aylık Ödeme Alındı",
            recipients=[lead.user.email],
            text_body=f"Aylık ödemeniz alındı.\n\nTutar: {lead.monthly_amount} TL\nSonraki ödeme tarihi: {lead.next_payment_date.strftime('%d.%m.%Y')}\n\nHizmetleriniz devam etmektedir.",
            html_body=f"<p>Aylık ödemeniz alındı.</p><p><b>Tutar:</b> {lead.monthly_amount} TL</p><p><b>Sonraki ödeme tarihi:</b> {lead.next_payment_date.strftime('%d.%m.%Y')}</p><p>Hizmetleriniz devam etmektedir.</p>"
        )
    
    flash('Aylık ödeme alındı olarak işaretlendi ve sonraki ödeme tarihi güncellendi.', 'success')
    return redirect(url_for('admin.leads'))

@bp.route("/lead/<int:lead_id>/cancel", methods=['POST'])
@login_required
@admin_required
def cancel_lead(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    lead.status = 'cancelled'
    db.session.commit()
    
    if lead.user and lead.user.email:
        service_name = lead.service.name if lead.service else 'Hizmet'
        user_name = lead.user.name.split()[0] if lead.user.name else 'Değerli Müşterimiz'
        
        # Profesyonel iptal e-postası
        send_email(
            subject=f"{service_name} Hizmet Talebiniz Hakkında",
            recipients=[lead.user.email],
            text_body=f"Sayın {user_name},\n\n{service_name} hizmet talebinizle ilgili olarak size bilgi vermek isteriz.\n\nMevcut durum ve iş yükümüz nedeniyle, bu hizmet talebini şu an için karşılayamayacağımızı üzülerek bildirmek isteriz.\n\nAncak, gelecekte tekrar hizmet talebinde bulunmak isterseniz:\n• Web sitemizi ziyaret edebilirsiniz\n• Bizimle doğrudan iletişime geçebilirsiniz\n• Yeni bir randevu talebi oluşturabilirsiniz\n\nBu durumdan dolayı yaşadığınız memnuniyetsizlik için özür dileriz.\n\nHerhangi bir sorunuz olursa bizimle iletişime geçmekten çekinmeyin.\n\nSaygılarımızla,\nSanal Muhasebecim Ekibi",
            html_body=f"<p>Sayın <strong>{user_name}</strong>,</p><p>{service_name} hizmet talebinizle ilgili olarak size bilgi vermek isteriz.</p><p>Mevcut durum ve iş yükümüz nedeniyle, bu hizmet talebini şu an için karşılayamayacağımızı üzülerek bildirmek isteriz.</p><p>Ancak, gelecekte tekrar hizmet talebinde bulunmak isterseniz:</p><ul><li>Web sitemizi ziyaret edebilirsiniz</li><li>Bizimle doğrudan iletişime geçebilirsiniz</li><li>Yeni bir randevu talebi oluşturabilirsiniz</li></ul><p>Bu durumdan dolayı yaşadığınız memnuniyetsizlik için özür dileriz.</p><p>Herhangi bir sorunuz olursa bizimle iletişime geçmekten çekinmeyin.</p><p>Saygılarımızla,<br><strong>Sanal Muhasebecim Ekibi</strong></p>"
        )
    
    flash('Hizmet talebi iptal edildi.', 'success')
    return redirect(url_for('admin.leads'))

@bp.route("/lead/<int:lead_id>/restore", methods=['POST'])
@login_required
@admin_required
def restore_lead(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    
    # İptal durumundan geri al - önceki duruma döndür
    if lead.lead_type in ['one_time_payment_pending', 'monthly_payment_pending']:
        lead.status = 'payment_pending'
    elif lead.lead_type in ['one_time', 'monthly']:
        lead.status = 'paid'
    else:
        lead.status = 'pending'
    
    db.session.commit()
    
    if lead.user and lead.user.email:
        service_name = lead.service.name if lead.service else 'Hizmet'
        user_name = lead.user.name.split()[0] if lead.user.name else 'Değerli Müşterimiz'
        
        send_email(
            subject=f"{service_name} Hizmet Talebiniz Devam Ediyor",
            recipients=[lead.user.email],
            text_body=f"Sayın {user_name},\n\n{service_name} hizmet talebiniz tekrar aktif hale getirilmiştir. İşlemleriniz kaldığı yerden devam edecektir.\n\nHerhangi bir sorunuz olursa bizimle iletişime geçebilirsiniz.\n\nSaygılarımızla,\nSanal Muhasebecim Ekibi",
            html_body=f"<p>Sayın <strong>{user_name}</strong>,</p><p>{service_name} hizmet talebiniz tekrar aktif hale getirilmiştir. İşlemleriniz kaldığı yerden devam edecektir.</p><p>Herhangi bir sorunuz olursa bizimle iletişime geçebilirsiniz.</p><p>Saygılarımızla,<br><strong>Sanal Muhasebecim Ekibi</strong></p>"
        )
    
    flash('Hizmet talebi geri alındı ve önceki duruma döndürüldü.', 'success')
    return redirect(url_for('admin.leads'))

@bp.route("/lead/<int:lead_id>/send-iban", methods=['POST'])
@login_required
@admin_required
def send_iban(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    amount = request.form.get('amount')
    description = request.form.get('description') or 'Danışmanlık/ hizmet bedeli'
    try:
        amount_val = float(amount)
    except (TypeError, ValueError):
        flash('Geçersiz tutar.', 'danger')
        return redirect(url_for('admin.leads'))
    if not lead.user or not lead.user.email:
        flash('Lead için e-posta bulunamadı.', 'danger')
        return redirect(url_for('admin.leads'))
    send_iban_payment_email(to_email=lead.user.email, amount_try=amount_val, description=description)
    flash('IBAN ödeme talimatı e-posta ile gönderildi.', 'success')
    return redirect(url_for('admin.leads'))

@bp.route("/appointment/<int:appointment_id>/update-status", methods=['POST'])
@login_required
@admin_required
def update_appointment_status(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    new_status = request.form.get('status')
    meeting_link = request.form.get('meeting_link')
    price_amount = request.form.get('price_amount')
    starts_at_raw = request.form.get('starts_at')
    ends_at_raw = request.form.get('ends_at')

    if meeting_link is not None:
        appointment.meeting_link = meeting_link
        # Link eklendiyse ve SADECE yeni durum confirmed olacaksa e-posta gönder
        if appointment.email and meeting_link and new_status == 'confirmed':
            # Randevu tarih ve saat bilgilerini formatla
            appointment_date = appointment.appointment_datetime.strftime('%d.%m.%Y')
            appointment_time = appointment.appointment_datetime.strftime('%H:%M')
            
            send_email(
                subject="Randevunuz Onaylandı - Toplantı Bilgileri",
                recipients=[appointment.email],
                text_body=f"Merhaba,\n\nRandevunuz başarıyla onaylanmıştır. Aşağıda toplantı detaylarını bulabilirsiniz:\n\n📅 Tarih: {appointment_date}\n🕐 Saat: {appointment_time}\n🔗 Toplantı Linki: {meeting_link}\n\nToplantı saatinden 5 dakika önce linke tıklayarak toplantıya katılabilirsiniz.\n\nHerhangi bir sorunuz olursa bizimle iletişime geçebilirsiniz.\n\nSaygılarımızla,\nSanal Muhasebecim Ekibi",
                html_body=f"<p>Merhaba,</p><p><strong>Randevunuz başarıyla onaylanmıştır.</strong> Aşağıda toplantı detaylarını bulabilirsiniz:</p><div style='background-color: #f8f9fa; padding: 15px; border-radius: 8px; margin: 15px 0;'><p><strong>📅 Tarih:</strong> {appointment_date}</p><p><strong>🕐 Saat:</strong> {appointment_time}</p><p><strong>🔗 Toplantı Linki:</strong> <a href='{meeting_link}' style='color: #007bff;'>{meeting_link}</a></p></div><p>Toplantı saatinden 5 dakika önce linke tıklayarak toplantıya katılabilirsiniz.</p><p>Herhangi bir sorunuz olursa bizimle iletişime geçebilirsiniz.</p><p>Saygılarımızla,<br><strong>Sanal Muhasebecim Ekibi</strong></p>"
            )
            send_telegram_message(f"Randevu #{appointment.id} toplantı linki gönderildi: {meeting_link}")
            flash('Randevu onaylandı ve toplantı linki e-posta ile gönderildi.', 'success')

    if starts_at_raw and ends_at_raw:
        try:
            appointment.starts_at = datetime.fromisoformat(starts_at_raw)
            appointment.ends_at = datetime.fromisoformat(ends_at_raw)
            # Opsiyonel: Google Calendar etkinliği oluştur
            link = create_gcal_event(
                summary=f"Danışmanlık - {appointment.email}",
                description=appointment.purpose or "",
                starts_at=appointment.starts_at,
                ends_at=appointment.ends_at,
                attendees_emails=[appointment.email]
            )
            if link:
                send_email(
                    subject="Takvim Daveti",
                    recipients=[appointment.email],
                    text_body=f"Takvim daveti oluşturuldu: {link}",
                    html_body=f"<p>Takvim daveti oluşturuldu: <a href='{link}' target='_blank'>Etkinliği aç</a></p>"
                )
                send_telegram_message(f"Randevu #{appointment.id} için Google Calendar etkinliği oluşturuldu.")
            flash('Başlangıç ve bitiş saatleri kaydedildi.', 'success')
        except Exception:
            flash('Tarih/saat formatı geçersiz. ISO format kullanın: 2025-08-20T14:30', 'danger')

    # Ödeme ve tutar alanları kullanılmıyor (kaldırıldı)

    if new_status in ['pending', 'confirmed', 'cancelled']:
        # İptal notunu kim yaptığına göre işaretle
        if new_status == 'cancelled':
            try:
                prev_notes = (appointment.notes or '').strip()
                # eski kullanıcı etiketi İngilizce/Türkçe varyantlarını temizle
                for user_tag in ['cancelled_by_user', 'kullanici_iptal']:
                    if user_tag in prev_notes:
                        prev_notes = prev_notes.replace(user_tag, '').strip()
                # admin etiketi Türkçe kullan
                if 'admin_iptal' not in prev_notes and 'cancelled_by_admin' not in prev_notes:
                    prev_notes = (prev_notes + ' admin_iptal').strip()
                appointment.notes = prev_notes or 'admin_iptal'
            except Exception:
                pass
            # İlgili lead'i iptal durumuna çek
            try:
                if appointment.service_request and appointment.service_request.lead:
                    appointment.service_request.lead.status = 'cancelled'
            except Exception:
                pass
        appointment.status = new_status
        send_telegram_message(f"Randevu #{appointment.id} durumu: {new_status}")
        
        # Randevu onaylandıysa ve service_request varsa veya yoksa uygun işlemleri yap
        if new_status == 'confirmed':
            try:
                # Eğer service_request yoksa otomatik oluştur (tek hizmet akışı)
                if not appointment.service_request:
                    # Varsayılan "Tek Hizmet" kaydını bul / yoksa oluştur
                    default_service = Service.query.filter(
                        (Service.slug == 'tek-hizmet') | (Service.name.ilike('%tek hizmet%'))
                    ).first()
                    if not default_service:
                        default_service = Service(
                            name='Tek Hizmet',
                            slug='tek-hizmet',
                            description='Hizmet seçilmeden onaylanan randevular için tek seferlik hizmet.',
                            is_active=True,
                            order_index=0
                        )
                        db.session.add(default_service)
                        db.session.flush()

                    # ServiceRequest oluştur ve randevuya bağla
                    from SANALMUHASEBECIM.models import ServiceRequest  # local import to avoid cycles
                    new_sr = ServiceRequest(
                        user_id=appointment.user_id,
                        service_id=default_service.id,
                        additional_details=None,
                        status='approved',
                        approved_at=datetime.utcnow(),
                        approved_by=current_user.id
                    )
                    db.session.add(new_sr)
                    db.session.flush()
                    appointment.service_request_id = new_sr.id
                    send_telegram_message(f"Randevu #{appointment.id} için ServiceRequest oluşturuldu: #{new_sr.id}")

                # Eğer artık service_request mevcutsa leads sistemine düşür
                if appointment.service_request:
                    # ServiceRequest durumunu güncelle
                    appointment.service_request.status = 'approved'
                    appointment.service_request.approved_at = datetime.utcnow()
                    appointment.service_request.approved_by = current_user.id

                    # Mevcut lead var mı kontrol et
                    existing_lead = Lead.query.filter_by(
                        user_id=appointment.user_id,
                        service_request_id=appointment.service_request_id
                    ).first()

                    if not existing_lead:
                        # Varsayılan olarak "görüşme bekleniyor" durumunda başlat
                        service = appointment.service_request.service
                        if service and 'paket' in service.name.lower():
                            # Paket hizmeti ise aylık görüşme bekleniyor olarak başlat
                            default_lead_type = 'monthly_meeting_pending'
                        else:
                            # Paket değilse tek hizmet görüşme bekleniyor olarak başlat
                            default_lead_type = 'one_time_meeting_pending'

                        # Yeni lead oluştur - durum "görüşme bekleniyor" olarak ayarla
                        lead = Lead(
                            name=f"{service.name if service else 'Hizmet'} - {appointment.user.name if appointment.user else appointment.email}",
                            user_id=appointment.user_id,
                            service_request_id=appointment.service_request_id,
                            service_id=appointment.service_request.service_id,
                            lead_type=default_lead_type,
                            status='meeting_pending',  # Görüşme bekleniyor durumu
                            created_at=datetime.utcnow()
                        )
                        db.session.add(lead)
                        db.session.flush()  # ID'yi almak için flush
                        send_telegram_message(f"🎯 YENİ LEAD OLUŞTURULDU: #{lead.id} - {appointment.email} - Tip: {default_lead_type} - Hizmet: {service.name if service else 'N/A'}")
                        flash(f'✅ Randevu onaylandı ve leads sistemine eklendi! Lead ID: #{lead.id}', 'success')
                    else:
                        send_telegram_message(f"ℹ️ Randevu #{appointment.id} için zaten lead mevcut: #{existing_lead.id}")
                        flash('ℹ️ Randevu onaylandı. Zaten leads sisteminde mevcut.', 'info')
                else:
                    send_telegram_message(f"⚠️ Randevu #{appointment.id} onaylandı ama ServiceRequest oluşturulamadı!")
                    flash('⚠️ Randevu onaylandı ama ServiceRequest oluşturulamadı!', 'warning')
                    
            except Exception as e:
                send_telegram_message(f"❌ Randevu #{appointment.id} onaylanırken hata: {str(e)}")
                flash(f'❌ Randevu onaylanırken hata oluştu: {str(e)}', 'danger')
        
        if new_status == 'cancelled':
            # Takvimden sil (best-effort), zaman bilgisi mevcutsa
            try:
                if appointment.appointment_datetime and appointment.email:
                    delete_gcal_event(
                        summary=f"Danışmanlık - {appointment.email}",
                        starts_at=appointment.appointment_datetime,
                        ends_at=(appointment.appointment_datetime + timedelta(minutes=30)) if appointment.appointment_datetime else None,
                        attendee_email=appointment.email
                    )
            except Exception:
                pass
        if new_status == 'cancelled' and appointment.email:
            # İptal bilgilendirmesi
            send_email(
                subject="Randevunuz İptal Edildi",
                recipients=[appointment.email],
                text_body="Merhaba,\n\nMaalesef randevunuz iptal edilmiştir. Bu durumdan dolayı üzgünüz.\n\nYeni bir randevu talep etmek isterseniz, web sitemizden veya bizimle iletişime geçerek yeni bir randevu oluşturabilirsiniz.\n\nHerhangi bir sorunuz olursa bizimle iletişime geçebilirsiniz.\n\nSaygılarımızla,\nSanal Muhasebecim Ekibi",
                html_body="<p>Merhaba,</p><p><strong>Maalesef randevunuz iptal edilmiştir.</strong> Bu durumdan dolayı üzgünüz.</p><p>Yeni bir randevu talep etmek isterseniz, web sitemizden veya bizimle iletişime geçerek yeni bir randevu oluşturabilirsiniz.</p><p>Herhangi bir sorunuz olursa bizimle iletişime geçebilirsiniz.</p><p>Saygılarımızla,<br><strong>Sanal Muhasebecim Ekibi</strong></p>"
            )
            flash('İptal bilgisi e-posta ile gönderildi.', 'info')

    db.session.commit()
    flash('Randevu güncellendi!', 'success')
    return redirect(url_for('admin.appointments'))


@bp.route("/appointment/<int:appointment_id>/delete", methods=['POST'])
@login_required
@admin_required
def delete_appointment(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    db.session.delete(appointment)
    db.session.commit()
    flash('Randevu başarıyla silindi!', 'success')
    return redirect(url_for('admin.appointments'))

@bp.route("/tickets/new-count")
@login_required
@admin_required
def new_tickets_count():
    """JSON endpoint to get count of new tickets for real-time updates"""
    new_count = Ticket.query.filter_by(status='new').count()
    return {
        'new_count': new_count,
        'timestamp': datetime.utcnow().isoformat()
    }

@bp.route("/leads/pending-count")
@login_required
@admin_required
def pending_leads_count():
    """JSON endpoint to get count of pending leads for real-time updates"""
    pending_count = Lead.query.filter_by(status='pending').count()
    return {
        'pending_count': pending_count,
        'timestamp': datetime.utcnow().isoformat()
    }

@bp.route("/appointments/pending-count")
@login_required
@admin_required
def pending_appointments_count():
    """JSON endpoint to get count of pending appointments for real-time updates"""
    pending_count = Appointment.query.filter_by(status='pending').count()
    return {
        'pending_count': pending_count,
        'timestamp': datetime.utcnow().isoformat()
    }

@bp.route("/comments/pending-count")
@login_required
@admin_required
def pending_comments_count():
    """JSON endpoint to get count of pending comments for real-time updates"""
    pending_count = Comment.query.filter_by(is_approved=False).count()
    return {
        'pending_count': pending_count,
        'timestamp': datetime.utcnow().isoformat()
    }

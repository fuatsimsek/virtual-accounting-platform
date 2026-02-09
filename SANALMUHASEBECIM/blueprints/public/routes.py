from flask import render_template, flash, redirect, url_for, request, get_flashed_messages, Response
from flask_login import current_user
from . import bp
from SANALMUHASEBECIM.models import Post, Service, ContactLead, User, Comment, Subscriber, Like
from SANALMUHASEBECIM.forms import ContactForm, LeadForm
from SANALMUHASEBECIM.extensions import db, mail
from flask_mail import Message
from datetime import datetime
from SANALMUHASEBECIM.utils import send_telegram_message, send_email, get_email_signature



@bp.route("/")
def index():
    try:
        page = request.args.get('page', 1, type=int)
        posts = Post.query.filter_by(is_active=True).order_by(Post.id.desc()).paginate(page=page, per_page=3)
        next_url = url_for('public.index', page=posts.next_num) if posts.has_next else None
        prev_url = url_for('public.index', page=posts.prev_num) if posts.has_prev else None
        services = Service.query.filter_by(is_active=True).order_by(Service.order_index.asc(), Service.id.asc()).limit(3).all()
        posts_items = posts.items
        # Öne çıkanlar + popüler fallback (toplam 5)
        from sqlalchemy import func
        featured_q = (
            Post.query.filter_by(is_active=True, is_featured=True)
            .order_by(Post.published_at.desc().nullslast(), Post.post_date.desc())
        )
        featured_posts = featured_q.limit(5).all()
        popular_posts = featured_posts[:]
        if len(popular_posts) < 5:
            remaining = 5 - len(popular_posts)
            exclude_ids = [p.id for p in popular_posts] or [0]
            popular_q = (
                Post.query
                .filter(Post.is_active == True, ~Post.id.in_(exclude_ids))
                .outerjoin(Like, Like.post_id == Post.id)
                .group_by(Post.id)
                .order_by(func.count(Like.id).desc(), Post.post_date.desc())
                .limit(remaining)
            )
            popular_posts.extend(popular_q.all())
    except Exception as e:
        posts = {'items': [], 'has_next': False, 'has_prev': False, 'next_num': None, 'prev_num': None}
        next_url = None
        prev_url = None
        services = []
        popular_posts = []
        posts_items = []
        print(f"Database hatası: {e}")

    messages = get_flashed_messages(with_categories=True)

    return render_template(
        'index.html',
        title='Ana Sayfa | Muhasebe ve Vergi Danışmanlığı',
        posts=posts,
        next_url=next_url,
        prev_url=prev_url,
        messages=messages,
        services=services,
        popular_posts=popular_posts,
        posts_items=posts_items
    )
@bp.route("/home")
def index_home_redirect():
    return redirect(url_for('public.index'), code=301)

@bp.route("/about")
def about():
    return render_template('about.html', title='Hakkımızda')
@bp.route("/about/")
def about_trailing_redirect():
    return redirect(url_for('public.about'), code=301)
@bp.route("/kvkk")
def kvkk():
    return render_template('kvkk.html', title='KVKK')

@bp.route("/privacy")
def privacy():
    return render_template('privacy.html', title='Gizlilik Politikası')

@bp.route("/terms")
def terms():
    return render_template('terms.html', title='Kullanım Şartları')

@bp.route("/cerez-politikasi")
def cerez():
    return render_template('cerez-politikasi.html', title='Çerez Politikası')

@bp.route('/sitemap.xml')
def sitemap():
    pages = []
    now = datetime.utcnow().date().isoformat()
    # Static pages
    for rule in ['public.index','public.services','public.about','public.contact']:
        pages.append({
            'loc': url_for(rule, _external=True),
            'lastmod': now
        })
    
    try:
        # Blog posts
        for p in Post.query.filter_by(is_active=True).all():
            pages.append({'loc': url_for('blog.post_detail', slug=p.slug, _external=True), 'lastmod': now})
        # Services
        for s in Service.query.filter_by(is_active=True).all():
            pages.append({'loc': url_for('public.service_detail', slug=s.slug, _external=True), 'lastmod': now})
    except Exception as e:
        print(f"Sitemap database hatası: {e}")
    
    xml = render_template('sitemap.xml.j2', pages=pages)
    return Response(xml, mimetype='application/xml')

@bp.route('/robots.txt')
def robots():
    content = f"""User-agent: *
Allow: /
Sitemap: {url_for('public.sitemap', _external=True)}
"""
    return Response(content, mimetype='text/plain')
@bp.route('/yandex_f68ba828758a8aff.html')
def yandex_verification():
    html = """
<html>
    <head>
        <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
    </head>
    <body>Verification: f68ba828758a8aff</body>
</html>
""".strip()
    return Response(html, mimetype='text/html; charset=UTF-8')
@bp.route('/subscribe', methods=['POST'])
def subscribe():
    email = (request.form.get('email') or '').strip().lower()
    if not email or '@' not in email:
        flash('Lütfen geçerli bir e-posta girin.', 'warning')
        return redirect(request.referrer or url_for('public.index'))
    try:
        existing = Subscriber.query.filter_by(email=email).first()
        if existing:
            if not existing.is_active:
                existing.is_active = True
                db.session.commit()
                flash('Aboneliğiniz tekrar aktifleştirildi.', 'success')
            else:
                flash('Zaten abonesiniz. Teşekkürler!', 'info')
            return redirect(request.referrer or url_for('public.index'))
        sub = Subscriber(email=email, is_active=True)
        db.session.add(sub)
        db.session.commit()
        # Hoş geldiniz e-postası
        send_email(
            subject='Bültene Abone Oldunuz - Sanal Muhasebecim',
            recipients=[email],
            text_body='Bültenimize abone olduğunuz için teşekkür ederiz. Yeni yazılar yayınlandığında sizi bilgilendireceğiz.',
            html_body='<p>Bültenimize abone olduğunuz için teşekkür ederiz. Yeni yazılar yayınlandığında sizi bilgilendireceğiz.</p>'
        )
        flash('Aboneliğiniz oluşturuldu. Teşekkürler!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Abonelik oluşturulamadı. Lütfen daha sonra tekrar deneyin.', 'danger')
    return redirect(request.referrer or url_for('public.index'))

@bp.route("/contact", methods=['GET','POST'])
def contact():
    form = ContactForm()
    if form.validate_on_submit():
        try:
            # Contact verilerini hazırla
            contact_data = {
                'name': form.name.data,
                'email': form.email.data,
                'phone': form.phone.data,
                'subject': form.subject.data,
                'message': form.message.data,
                'ip_address': request.remote_addr
            }
            
            # Kullanıcıya otomatik teşekkür maili gönder
            from SANALMUHASEBECIM.utils import send_contact_confirmation_email
            send_contact_confirmation_email(contact_data)
            
            # Admin'e bildirim maili gönder
            from SANALMUHASEBECIM.utils import send_contact_notification_email
            send_contact_notification_email(contact_data)
            
            flash('Mesajınız başarıyla gönderildi. En kısa sürede size dönüş yapacağız.', 'success')
        except Exception as e:
            flash('Mesaj gönderilirken bir hata oluştu. Lütfen daha sonra tekrar deneyin.', 'danger')
            print(f"Contact mail hatası: {e}")
        
        return redirect(url_for('public.contact'))
    
    return render_template('contact.html', title='İletişim', form=form)
@bp.route("/contact/")
def contact_trailing_redirect():
    return redirect(url_for('public.contact'), code=301)
@bp.route("/services")
def services():
    try:
        # Tüm aktif hizmetler: order_index'e göre sırala, aynı sırada olanları id'ye göre sırala
        services = Service.query.filter_by(is_active=True).order_by(Service.order_index.asc(), Service.id.asc()).all()
        packages = services  # Tüm hizmetleri packages olarak da gönder (template'de kullanılıyor)
    except Exception as e:
        services = []
        packages = []
        print(f"Database hatası: {e}")
    
    return render_template('services.html', title='Hizmetler', services=services, packages=packages)
@bp.route("/services/")
def services_trailing_redirect():
    return redirect(url_for('public.services'), code=301)
@bp.route("/u/<int:user_id>")
def user_public_profile(user_id):
    user = User.query.get_or_404(user_id)
    # Son 5 yazı
    # SQL Server 'NULLS LAST' desteklemez; COALESCE ile sıralayalım
    from sqlalchemy import func
    recent_posts = (
        Post.query
        .filter_by(user_id=user.id, is_active=True)
        .order_by(func.coalesce(Post.published_at, Post.post_date).desc(), Post.post_date.desc())
        .limit(5)
        .all()
    )
    # Son 5 yorum (giriş yapılmamışsa da listeleyeceğiz; arayüzde blur/overlay ile kısıtlanır)
    recent_comments = (
        Comment.query
        .filter_by(user_id=user.id)
        .order_by(Comment.date.desc())
        .limit(5)
        .all()
    )
    return render_template('public/user_profile.html', title=user.name, user=user, recent_posts=recent_posts, recent_comments=recent_comments)

@bp.route("/services/<slug>")
def service_detail(slug):
    try:
        service = Service.query.filter_by(slug=slug, is_active=True).first_or_404()
        
        # Giriş yapmış kullanıcılar için ServiceRequestForm, yapmamış kullanıcılar için LeadForm
        from flask_login import current_user
        if current_user.is_authenticated:
            from SANALMUHASEBECIM.forms import ServiceRequestForm
            form = ServiceRequestForm()
        else:
            form = LeadForm()
            # Hizmet seçeneklerini form'a ekle
            form.service_id.choices = [(service.id, service.name)]
            form.service_id.data = service.id
        
        return render_template('service_detail.html', title=service.name, service=service, form=form)
    except Exception as e:
        print(f"Database hatası: {e}")
        flash('Hizmet bulunamadı veya veritabanı hatası oluştu.', 'danger')
        return redirect(url_for('public.services'))

@bp.route("/lead", methods=['POST'])
def create_lead():
    form = LeadForm()
    # Populate service choices before validation to satisfy WTForms SelectField
    try:
        services = Service.query.filter_by(is_active=True).order_by(Service.order_index).all()
        form.service_id.choices = [(s.id, s.name) for s in services]
    except Exception as e:
        form.service_id.choices = []
        print(f"Database hatası: {e}")
    
    if form.validate_on_submit():
        try:
            from SANALMUHASEBECIM.models import Lead
            lead = Lead(
                name=form.name.data,
                email=form.email.data,
                phone=form.phone.data,
                service_id=form.service_id.data,
                message=form.message.data,
                utm_source=request.args.get('utm_source', 'direct')
            )
            db.session.add(lead)
            db.session.commit()
            
            # Telegram bildirimi
            service = Service.query.get(lead.service_id) if lead.service_id else None
            send_telegram_message(f"Yeni lead: {lead.name} - {lead.email} - Hizmet: {(service.name if service else '-')}")
            
            # Lead'e otomatik teşekkür maili
            if lead.email:
                send_email(
                    subject="Talebinizi Aldık",
                    recipients=[lead.email],
                    text_body=f"Merhaba {lead.name}, talebiniz alınmıştır. En kısa sürede dönüş yapacağız.",
                    html_body=f"<p>Merhaba {lead.name},</p><p>Talebiniz alınmıştır. En kısa sürede size dönüş yapacağız.</p>"
                )
            
            flash('Teklif talebiniz alındı! En kısa sürede size dönüş yapacağız.', 'success')
            return redirect(url_for('public.services'))
        except Exception as e:
            print(f"Lead oluşturma hatası: {e}")
            flash('Teklif talebiniz kaydedilirken bir hata oluştu. Lütfen daha sonra tekrar deneyin.', 'danger')
            return redirect(url_for('public.services'))
    
    flash('Form verilerinde hata var. Lütfen tekrar deneyin.', 'danger')
    return redirect(url_for('public.services'))

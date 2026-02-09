from flask import render_template, flash, redirect, url_for, abort, request, jsonify, get_flashed_messages
from flask_mail import Message
from SANALMUHASEBECIM import app, db, mail
from SANALMUHASEBECIM.forms import (
    RegisterForm, 
    LoginForm, 
    PostForm, 
    ContactForm, 
    CommentForm, 
    EditUserForm,
    DanismanlikForm,  # Yeni eklenen form
    UpdatePasswordForm,
    ForgotPasswordForm,
    ResetPasswordForm
)
from SANALMUHASEBECIM.models import User, Post, Comment, Like, CommentLike
from flask_login import login_user, current_user, logout_user, login_required
from functools import wraps
from datetime import datetime, date, timedelta
from sqlalchemy import text
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
import json
from werkzeug.security import generate_password_hash, check_password_hash
from SANALMUHASEBECIM.utils import send_confirmation_email, send_password_reset_email, get_email_signature

from SANALMUHASEBECIM.models import User, Post, Comment, Like, CommentLike, Appointment
from flask_login import login_user, current_user, logout_user, login_required
from functools import wraps
from datetime import datetime, timedelta

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Bu sayfaya erişim yetkiniz yok.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/")
@app.route("/home")
def index():
    page = request.args.get('page',1,type=int)
    posts = Post.query.filter_by(is_active=True).order_by(Post.id.desc()).paginate(page=page, per_page=3)
    next_url=url_for('index',page=posts.next_num) if posts.has_next else None
    prev_url=url_for('index',page=posts.prev_num) if posts.has_prev else None
    
    # Flash mesajlarını al
    messages = get_flashed_messages(with_categories=True)
    
    return render_template('index.html', 
                         title='HOME', 
                         posts=posts, 
                         next_url=next_url, 
                         prev_url=prev_url,
                         messages=messages)

@app.route("/about")
def about():
    return render_template('about.html', title='ABOUT')

@app.route("/register", methods=['GET','POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegisterForm()
    if form.validate_on_submit():
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
        db.session.add(user)
        db.session.commit()
        
        # Onay e-postası gönder
        send_confirmation_email(user)
        
        flash('Kayıt başarılı! Lütfen e-posta adresinizi onaylamak için gelen kutunuzu kontrol edin.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Kayıt Ol', form=form)

@app.route('/confirm/<token>')
def confirm_email(token):
    user = User.query.filter_by(confirmation_token=token).first()
    if user is None:
        flash('Geçersiz veya süresi dolmuş onay bağlantısı.', 'danger')
        return redirect(url_for('index'))
    
    user.email_confirmed = True
    user.confirmation_token = None
    db.session.commit()
    
    flash('E-posta adresiniz başarıyla onaylandı! Şimdi giriş yapabilirsiniz.', 'success')
    return redirect(url_for('login'))

@app.route("/login", methods=['GET','POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password, form.password.data):
            if not user.email_confirmed:
                flash('Lütfen önce e-posta adresinizi onaylayın.', 'warning')
                return redirect(url_for('login'))
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Giriş başarısız. Lütfen e-posta ve şifrenizi kontrol edin.', 'danger')
    return render_template('login.html', title='Giriş Yap', form=form)

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route("/forgot-password", methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            send_password_reset_email(user)
            flash('Şifre sıfırlama bağlantısı e-posta adresinize gönderildi. Lütfen gelen kutunuzu kontrol edin.', 'success')
        else:
            flash('Bu e-posta adresi ile kayıtlı kullanıcı bulunamadı.', 'warning')
        return redirect(url_for('login'))
    
    return render_template('forgot_password.html', title='Şifremi Unuttum', form=form)

@app.route("/reset-password/<token>", methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    user = User.query.filter_by(reset_token=token).first()
    if not user or not user.is_reset_token_valid():
        flash('Geçersiz veya süresi dolmuş şifre sıfırlama bağlantısı.', 'danger')
        return redirect(url_for('login'))
    
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.password = generate_password_hash(form.new_password.data)
        user.clear_reset_token()
        db.session.commit()
        flash('Şifreniz başarıyla güncellendi! Şimdi yeni şifrenizle giriş yapabilirsiniz.', 'success')
        return redirect(url_for('login'))
    
    return render_template('reset_password.html', title='Şifre Sıfırla', form=form)

@app.route("/post/new", methods=['GET','POST'])
@login_required
@admin_required
def new_post():
    form = PostForm()
    if form.validate_on_submit():
        post = Post(
            title=form.title.data,
            subtitle=form.subtitle.data,
            post_text=form.post_text.data,
            user=current_user
        )
        db.session.add(post)
        db.session.commit()
        flash('Gönderi oluşturuldu!', 'success')
        return redirect(url_for('index'))
    return render_template('create_post.html', title='Yeni Gönderi', form=form)

@app.route("/post/<int:post_id>", methods=['GET', 'POST'])
def post(post_id):
    post = Post.query.get_or_404(post_id)
    form = CommentForm()
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash('Yorum yapmak için giriş yapmalısınız.', 'info')
            return redirect(url_for('login'))
        comment = Comment(content=form.content.data, author=current_user, post=post)
        db.session.add(comment)
        db.session.commit()
        flash('Yorumunuz eklendi!', 'success')
        return redirect(url_for('post', post_id=post.id))
    return render_template('post.html', title=post.title, post=post, form=form)

@app.route('/post/<int:post_id>/edit', methods=['GET','POST'])
@login_required
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)
    if not current_user.is_admin and post.user != current_user:
        abort(403)
    form = PostForm()
    if form.validate_on_submit():
        post.title = form.title.data
        post.subtitle = form.subtitle.data
        post.post_text = form.post_text.data
        db.session.commit()
        flash(f'Post başarıyla düzenlendi.', 'success')
        return redirect(url_for('post',post_id=post.id))
    elif request.method == 'GET':
        form.title.data = post.title
        form.subtitle.data = post.subtitle
        form.post_text.data = post.post_text
        return render_template('create_post.html', title='Post Düzenle', form=form)
    
@app.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if not current_user.is_admin and post.user != current_user:
        abort(403)
    db.session.delete(post)
    db.session.commit()
    flash(f'Post başarıyla silindi','success')
    return redirect(url_for('index'))

@app.route("/post/<int:post_id>/like", methods=['POST'])
@login_required
def like_post(post_id):
    if not current_user.is_authenticated:
        return jsonify({'error': 'Beğeni yapmak için giriş yapmalısınız.'}), 401
        
    post = Post.query.get_or_404(post_id)
    like = Like.query.filter_by(user_id=current_user.id, post_id=post.id).first()
    
    if like:
        db.session.delete(like)
        db.session.commit()
        return jsonify({'status': 'unliked', 'likes': len(post.likes)})
    else:
        like = Like(user=current_user, post=post)
        db.session.add(like)
        db.session.commit()
        return jsonify({'status': 'liked', 'likes': len(post.likes)})

@app.route("/comment/<int:comment_id>/like", methods=['POST'])
@login_required
def like_comment(comment_id):
    if not current_user.is_authenticated:
        return jsonify({'error': 'Beğeni yapmak için giriş yapmalısınız.'}), 401
        
    comment = Comment.query.get_or_404(comment_id)
    like = CommentLike.query.filter_by(user_id=current_user.id, comment_id=comment.id).first()
    
    if like:
        db.session.delete(like)
        db.session.commit()
        return jsonify({'status': 'unliked', 'likes': len(comment.likes)})
    else:
        like = CommentLike(user=current_user, comment=comment)
        db.session.add(like)
        db.session.commit()
        return jsonify({'status': 'liked', 'likes': len(comment.likes)})

@app.route("/comment/<int:comment_id>/reply", methods=['POST'])
@login_required
def reply_to_comment(comment_id):
    if not current_user.is_authenticated:
        return jsonify({'error': 'Yanıt vermek için giriş yapmalısınız.'}), 401
        
    parent_comment = Comment.query.get_or_404(comment_id)
    data = request.get_json()
    
    if not data or 'content' not in data:
        return jsonify({'error': 'Yanıt içeriği gerekli.'}), 400
        
    reply = Comment(
        content=data['content'],
        author=current_user,
        post=parent_comment.post,
        parent_id=parent_comment.id
    )
    
    db.session.add(reply)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'reply': {
            'id': reply.id,
            'content': reply.content,
            'user_name': reply.author.name,
            'date': reply.date.strftime('%d-%m-%Y %H:%M')
        }
    })

@app.route("/contact", methods=['GET','POST'])
def contact():
    form = ContactForm()
    if form.validate_on_submit():
        msg = Message(form.name.data, 
                     recipients=['info@sanalmuhasebem.net'])
        msg.html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f8f9fa; border-radius: 10px;">
            <div style="text-align: center; margin-bottom: 30px;">
                <h2 style="color: #0d6efd; margin: 0; font-size: 24px;">📧 Yeni İletişim Formu Mesajı</h2>
                <p style="color: #6c757d; margin: 10px 0 0 0; font-size: 16px;">Müşteri iletişim talebi</p>
            </div>
            
            <div style="background-color: white; padding: 25px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                <div style="background: linear-gradient(135deg, #0d6efd 0%, #0b5ed7 100%); color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
                    <h3 style="margin: 0; font-size: 18px; font-weight: 600;">👤 Müşteri Bilgileri</h3>
                </div>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 20px;">
                    <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid #0d6efd;">
                        <h4 style="margin: 0 0 8px 0; color: #0d6efd; font-size: 14px; font-weight: 600;">👤 Ad Soyad</h4>
                        <p style="margin: 0; color: #495057; font-size: 16px; font-weight: 500;">{form.name.data}</p>
                    </div>
                    <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid #198754;">
                        <h4 style="margin: 0 0 8px 0; color: #198754; font-size: 14px; font-weight: 600;">📧 E-posta</h4>
                        <p style="margin: 0; color: #495057; font-size: 16px; font-weight: 500;">{form.email.data}</p>
                    </div>
                </div>
                
                <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid #ffc107; margin-bottom: 20px;">
                    <h4 style="margin: 0 0 8px 0; color: #856404; font-size: 14px; font-weight: 600;">📞 Telefon</h4>
                    <p style="margin: 0; color: #495057; font-size: 16px; font-weight: 500;">{form.phone.data}</p>
                </div>
                
                <div style="background: #e8f5e9; padding: 20px; border-radius: 8px; border-left: 4px solid #198754;">
                    <h4 style="margin: 0 0 15px 0; color: #198754; font-size: 16px; font-weight: 600;">💬 Mesaj İçeriği</h4>
                    <div style="background: white; padding: 15px; border-radius: 6px; border: 1px solid #dee2e6;">
                        <p style="margin: 0; color: #495057; font-size: 14px; line-height: 1.6; white-space: pre-line;">{form.message.data}</p>
                    </div>
                </div>
            </div>
            
            {get_email_signature()}
        </div>
        """
        mail.send(msg)
        flash('Mesajınız gönderildi!', 'success')
        return redirect(url_for('contact'))
    return render_template('contact.html', title='İLETİŞİM', form=form)

@app.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    users_page = request.args.get('users_page', 1, type=int)
    posts_page = request.args.get('posts_page', 1, type=int)
    comments_page = request.args.get('comments_page', 1, type=int)
    per_page = 5

    users = User.query.order_by(User.id.desc()).paginate(page=users_page, per_page=per_page, error_out=False)
    posts = Post.query.order_by(Post.id.desc()).paginate(page=posts_page, per_page=per_page, error_out=False)
    comments = Comment.query.order_by(Comment.id.desc()).paginate(page=comments_page, per_page=per_page, error_out=False)

    return render_template('admin/dashboard.html', 
                         title='Admin Paneli',
                         users=users,
                         posts=posts,
                         comments=comments)

@app.route('/admin/post/<int:post_id>/toggle-status', methods=['POST'])
@login_required
@admin_required
def toggle_post_status(post_id):
    post = Post.query.get_or_404(post_id)
    post.is_active = not post.is_active
    db.session.commit()
    return jsonify({'success': True, 'is_active': post.is_active})

@app.route('/admin/user/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    form = EditUserForm(obj=user)
    if form.validate_on_submit():
        user.name = form.name.data
        user.email = form.email.data
        user.is_admin = form.is_admin.data
        db.session.commit()
        flash('Kullanıcı başarıyla güncellendi.', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template('edit_user.html', form=form, user=user)

@app.route('/admin/search/users')
@login_required
@admin_required
def search_users():
    query = request.args.get('query', '')
    if not query:
        users = User.query.all()
    else:
        users = User.query.filter(User.name.ilike(f'%{query}%')).all()
    return jsonify([{
        'id': user.id,
        'name': user.name,
        'email': user.email,
        'is_admin': user.is_admin
    } for user in users])

@app.route('/admin/search/posts')
@login_required
@admin_required
def search_posts():
    query = request.args.get('query', '')
    if not query:
        posts = Post.query.all()
    else:
        posts = Post.query.filter(Post.title.ilike(f'%{query}%')).all()
    return jsonify([{
        'id': post.id,
        'title': post.title,
        'author': post.user.name,
        'date': post.post_date.strftime('%d-%m-%Y'),
        'is_active': post.is_active
    } for post in posts])

@app.route('/admin/search/comments')
@login_required
@admin_required
def search_comments():
    query = request.args.get('query', '')
    if not query:
        comments = Comment.query.all()
    else:
        comments = Comment.query.filter(Comment.content.ilike(f'%{query}%')).all()
    return jsonify([{
        'id': comment.id,
        'user': comment.author.name,
        'post': comment.post.title,
        'content': comment.content[:50] + '...',
        'date': comment.date.strftime('%d-%m-%Y')
    } for comment in comments])

@app.route("/analytics")
@login_required
@admin_required
def analytics():
    # Post istatistikleri
    post_stats = db.session.execute('''
        SELECT 
            p.id,
            p.title,
            COUNT(DISTINCT c.id) as comment_count,
            COUNT(DISTINCT l.id) as like_count,
            p.post_date
        FROM post p
        LEFT JOIN comment c ON p.id = c.post_id
        LEFT JOIN "like" l ON p.id = l.post_id
        GROUP BY p.id, p.title, p.post_date
        ORDER BY p.post_date DESC
    ''').fetchall()

    # Kullanıcı aktivite analizi
    user_stats = db.session.execute('''
        SELECT 
            u.id,
            u.name,
            COUNT(DISTINCT p.id) as post_count,
            COUNT(DISTINCT c.id) as comment_count,
            COUNT(DISTINCT l.id) as like_count
        FROM "user" u
        LEFT JOIN post p ON u.id = p.user_id
        LEFT JOIN comment c ON u.id = c.user_id
        LEFT JOIN "like" l ON u.id = l.user_id
        GROUP BY u.id, u.name
        ORDER BY post_count DESC
    ''').fetchall()

    return render_template('analytics.html', title='Analitik', post_stats=post_stats, user_stats=user_stats)

@app.route("/danismanlik", methods=['GET', 'POST'])
def danismanlik():
    form = DanismanlikForm()
    # Form için minimum ve maksimum tarihleri ayarla
    today = date.today()
    min_date = today
    max_date = today + timedelta(days=14)  # 2 hafta
    
    if form.validate_on_submit():
        # Randevu tarihini ve saatini birleştir
        appointment_date = form.appointment_date.data
        appointment_time = datetime.strptime(form.appointment_time.data, '%H:%M').time()
        
        # Tarih kontrolü
        if appointment_date < today or appointment_date > max_date:
            flash('Randevu tarihi bugün ile önümüzdeki 2 hafta arasında olmalıdır.', 'danger')
            return render_template('danismanlik.html', title='Danışmanlık', form=form, min_date=min_date, max_date=max_date, messages=get_flashed_messages(with_categories=True))
        
        appointment_datetime = datetime.combine(appointment_date, appointment_time)
        
        # Aynı tarih ve saatte başka bir randevu var mı kontrol et
        existing_appointment = Appointment.query.filter_by(
            appointment_datetime=appointment_datetime,
            status='pending'
        ).first()
        
        if existing_appointment:
            flash('Bu saat için başka bir randevu bulunmaktadır. Lütfen başka bir saat seçin.', 'danger')
            return render_template('danismanlik.html', title='Danışmanlık', form=form, min_date=min_date, max_date=max_date, messages=get_flashed_messages(with_categories=True))
        
        # Yeni randevu oluştur
        appointment = Appointment(
            email=form.email.data,
            appointment_datetime=appointment_datetime,
            purpose=form.purpose.data,
            status='pending'
        )
        
        db.session.add(appointment)
        db.session.commit()

        # Türkçe ay isimleri
        aylar = {
            'January': 'Ocak',
            'February': 'Şubat',
            'March': 'Mart',
            'April': 'Nisan',
            'May': 'Mayıs',
            'June': 'Haziran',
            'July': 'Temmuz',
            'August': 'Ağustos',
            'September': 'Eylül',
            'October': 'Ekim',
            'November': 'Kasım',
            'December': 'Aralık'
        }

        # Tarihi Türkçe formata çevir
        tarih = appointment_datetime.strftime('%d %B %Y')
        for eng, tr in aylar.items():
            tarih = tarih.replace(eng, tr)

        # Randevu onay e-postası gönder
        msg = Message("Randevu Talebiniz Alındı", 
                     recipients=[appointment.email])
        
        msg.html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f8f9fa; border-radius: 10px;">
            <div style="text-align: center; margin-bottom: 30px;">
                <h2 style="color: #0d6efd; margin: 0; font-size: 24px;">Randevu Talebiniz Alındı</h2>
                <p style="color: #6c757d; margin: 10px 0 0 0; font-size: 16px;">Sanal Muhasebecim Danışmanlık</p>
            </div>
            
            <div style="background-color: white; padding: 25px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                <p style="margin: 0 0 15px 0; font-size: 16px; line-height: 1.6;">Sayın Danışanımız,</p>
                <p style="margin: 0 0 20px 0; font-size: 16px; line-height: 1.6;">Randevu talebiniz başarıyla alınmıştır. Talebiniz incelendikten sonra size bilgilendirme yapılacaktır.</p>
                
                <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px; margin-bottom: 20px; border: 1px solid #e9ecef;">
                    <p style="margin: 0 0 15px 0; font-size: 18px; font-weight: 600; color: #212529;">Randevu Detayları</p>
                    <div style="display: flex; margin-bottom: 10px;">
                        <div style="width: 120px; color: #6c757d;">Tarih:</div>
                        <div style="flex: 1; font-weight: 500;">{tarih}</div>
                    </div>
                    <div style="display: flex; margin-bottom: 10px;">
                        <div style="width: 120px; color: #6c757d;">Saat:</div>
                        <div style="flex: 1; font-weight: 500;">{appointment_datetime.strftime('%H:%M')}</div>
                    </div>
                    <div style="display: flex;">
                        <div style="width: 120px; color: #6c757d;">Durum:</div>
                        <div style="flex: 1;">
                            <span style="color: #ffc107; font-weight: 600; padding: 4px 12px; border-radius: 4px; background-color: #ffc10715;">
                                BEKLEMEDE
                            </span>
                        </div>
                    </div>
                </div>
                
                <div style="background-color: #fff3cd; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #ffc107;">
                    <p style="margin: 0 0 10px 0; color: #856404; font-weight: 600;">Bilgilendirme:</p>
                    <p style="margin: 0 0 10px 0; color: #856404;">Randevunuz onaylandığında, görüşme Google Meet üzerinden gerçekleşecektir. Görüşme linki, randevu saatinden önce e-posta adresinize gönderilecektir.</p>
                </div>
                
                <p style="margin: 0 0 20px 0; font-size: 16px; line-height: 1.6;">Randevunuzla ilgili herhangi bir sorunuz olursa bizimle iletişime geçebilirsiniz.</p>
                
                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e9ecef;">
                    <p style="margin: 0 0 5px 0; font-size: 16px; font-weight: 600;">Saygılarımızla,</p>
                    <p style="margin: 0; font-size: 16px; color: #0d6efd;">Sanal Muhasebecim Ekibi</p>
                </div>
            </div>
            
            <div style="text-align: center; margin-top: 20px; padding-top: 20px; border-top: 1px solid #e9ecef;">
                <p style="margin: 0; color: #6c757d; font-size: 13px;">Bu e-posta Sanal Muhasebecim randevu sistemi tarafından otomatik olarak gönderilmiştir.</p>
                <p style="margin: 5px 0 0 0; color: #6c757d; font-size: 13px;">© 2025 Sanal Muhasebecim. Tüm hakları saklıdır.</p>
            </div>
        </div>
        """
        
        try:
            mail.send(msg)
            flash('Randevunuz başarıyla alındı! Onay durumu e-posta ile bildirilecektir.', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            flash('Randevu alındı fakat e-posta gönderilemedi. Lütfen daha sonra tekrar deneyin.', 'warning')
            return render_template('danismanlik.html', title='Danışmanlık', form=form, min_date=min_date, max_date=max_date, messages=get_flashed_messages(with_categories=True))
    
    return render_template('danismanlik.html', title='Danışmanlık', form=form, min_date=min_date, max_date=max_date, messages=get_flashed_messages(with_categories=True))

@app.route('/admin/appointments')
@login_required
@admin_required
def admin_appointments():
    appointments = Appointment.query.order_by(Appointment.appointment_datetime.desc()).all()
    return render_template('admin/appointments.html', title='Randevular', appointments=appointments)

@app.route('/admin/appointment/<int:appointment_id>/update-status', methods=['POST'])
@login_required
@admin_required
def update_appointment_status(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    new_status = request.form.get('status')
    
    if new_status in ['pending', 'confirmed', 'cancelled']:
        appointment.status = new_status
        db.session.commit()
        
        # Durum değişikliğini e-posta ile bildir
        msg = Message("Randevu Durumu Güncellendi", 
                     recipients=[appointment.email])
        
        status_text = {
            'pending': 'beklemede',
            'confirmed': 'onaylandı',
            'cancelled': 'iptal edildi'
        }
        
        status_color = {
            'pending': '#ffc107',
            'confirmed': '#198754',
            'cancelled': '#dc3545'
        }

        # Türkçe ay isimleri
        aylar = {
            'January': 'Ocak',
            'February': 'Şubat',
            'March': 'Mart',
            'April': 'Nisan',
            'May': 'Mayıs',
            'June': 'Haziran',
            'July': 'Temmuz',
            'August': 'Ağustos',
            'September': 'Eylül',
            'October': 'Ekim',
            'November': 'Kasım',
            'December': 'Aralık'
        }

        # Tarihi Türkçe formata çevir
        tarih = appointment.appointment_datetime.strftime('%d %B %Y')
        for eng, tr in aylar.items():
            tarih = tarih.replace(eng, tr)

        # Duruma göre ekstra mesaj
        extra_message = ""
        if new_status == 'confirmed':
            extra_message = """
                <div style="background-color: #e8f5e9; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #198754;">
                    <p style="margin: 0 0 10px 0; color: #198754; font-weight: 600;">Önemli Bilgilendirme:</p>
                    <p style="margin: 0 0 10px 0;">Görüşmemiz Google Meet üzerinden gerçekleşecektir. Görüşme linki, randevu saatinden önce e-posta adresinize gönderilecektir.</p>
                    <p style="margin: 0;">Lütfen görüşme saatinden 5 dakika önce hazır olunuz.</p>
                </div>
            """
        elif new_status == 'cancelled':
            extra_message = """
                <div style="background-color: #fbe9e7; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #dc3545;">
                    <p style="margin: 0 0 10px 0; color: #dc3545; font-weight: 600;">Randevu İptal Edildi</p>
                    <p style="margin: 0 0 10px 0;">Randevunuz iptal edilmiştir. Yeni bir randevu almak için lütfen web sitemizi ziyaret ediniz.</p>
                    <p style="margin: 0;">İptal nedeniyle oluşan herhangi bir sorunuz varsa bizimle iletişime geçebilirsiniz.</p>
                </div>
            """
        elif new_status == 'pending':
            extra_message = """
                <div style="background-color: #fff3cd; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #ffc107;">
                    <p style="margin: 0 0 10px 0; color: #856404; font-weight: 600;">Randevu Talebiniz İnceleniyor</p>
                    <p style="margin: 0 0 10px 0;">Randevu talebiniz alınmıştır. Talebiniz en kısa sürede incelenecek ve size bilgilendirme yapılacaktır.</p>
                    <p style="margin: 0;">Randevunuz onaylandığında, görüşme Google Meet üzerinden gerçekleşecektir.</p>
                </div>
            """

        msg.html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f8f9fa; border-radius: 10px;">
            <div style="text-align: center; margin-bottom: 30px;">
                <h2 style="color: #0d6efd; margin: 0; font-size: 24px;">Randevu Durumu Güncellendi</h2>
                <p style="color: #6c757d; margin: 10px 0 0 0; font-size: 16px;">Sanal Muhasebecim Danışmanlık</p>
            </div>
            
            <div style="background-color: white; padding: 25px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                <p style="margin: 0 0 15px 0; font-size: 16px; line-height: 1.6;">Sayın Danışanımız,</p>
                <p style="margin: 0 0 20px 0; font-size: 16px; line-height: 1.6;">Randevunuzun durumu güncellenmiştir. Aşağıda randevu detaylarını bulabilirsiniz.</p>
                
                <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px; margin-bottom: 20px; border: 1px solid #e9ecef;">
                    <p style="margin: 0 0 15px 0; font-size: 18px; font-weight: 600; color: #212529;">Randevu Detayları</p>
                    <div style="display: flex; margin-bottom: 10px;">
                        <div style="width: 120px; color: #6c757d;">Tarih:</div>
                        <div style="flex: 1; font-weight: 500;">{tarih}</div>
                    </div>
                    <div style="display: flex; margin-bottom: 10px;">
                        <div style="width: 120px; color: #6c757d;">Saat:</div>
                        <div style="flex: 1; font-weight: 500;">{appointment.appointment_datetime.strftime('%H:%M')}</div>
                    </div>
                    <div style="display: flex;">
                        <div style="width: 120px; color: #6c757d;">Durum:</div>
                        <div style="flex: 1;">
                            <span style="color: {status_color[new_status]}; font-weight: 600; padding: 4px 12px; border-radius: 4px; background-color: {status_color[new_status]}15;">
                                {status_text[new_status].upper()}
                            </span>
                        </div>
                    </div>
                </div>
                
                {extra_message}
                
                <p style="margin: 0 0 20px 0; font-size: 16px; line-height: 1.6;">Randevunuzla ilgili herhangi bir sorunuz olursa bizimle iletişime geçebilirsiniz.</p>
                
                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e9ecef;">
                    <p style="margin: 0 0 5px 0; font-size: 16px; font-weight: 600;">Saygılarımızla,</p>
                    <p style="margin: 0; font-size: 16px; color: #0d6efd;">Sanal Muhasebecim Ekibi</p>
                </div>
            </div>
            
            <div style="text-align: center; margin-top: 20px; padding-top: 20px; border-top: 1px solid #e9ecef;">
                <p style="margin: 0; color: #6c757d; font-size: 13px;">Bu e-posta Sanal Muhasebecim randevu sistemi tarafından otomatik olarak gönderilmiştir.</p>
                <p style="margin: 5px 0 0 0; color: #6c757d; font-size: 13px;">© 2025 Sanal Muhasebecim. Tüm hakları saklıdır.</p>
            </div>
        </div>
        """
        
        try:
            mail.send(msg)
            flash('Randevu durumu güncellendi ve kullanıcıya bilgilendirme e-postası gönderildi.', 'success')
        except Exception as e:
            flash('E-posta gönderilirken bir hata oluştu.', 'danger')
    
    return redirect(url_for('admin_appointments'))

@app.route('/admin/appointment/<int:appointment_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_appointment(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    db.session.delete(appointment)
    db.session.commit()
    flash('Randevu başarıyla silindi.', 'success')
    return redirect(url_for('admin_appointments'))

@app.route('/admin/search/appointments')
@login_required
@admin_required
def search_appointments():
    query = request.args.get('query', '')
    if not query:
        appointments = Appointment.query.all()
    else:
        appointments = Appointment.query.filter(
            (Appointment.email.ilike(f'%{query}%')) |
            (Appointment.status.ilike(f'%{query}%'))
        ).all()
    return jsonify([{
        'id': appointment.id,
        'email': appointment.email,
        'date': appointment.appointment_datetime.strftime('%d-%m-%Y'),
        'time': appointment.appointment_datetime.strftime('%H:%M'),
        'status': appointment.status
    } for appointment in appointments])

@app.route("/user-activity-summary")
@login_required
@admin_required
def user_activity_summary():
    result = db.session.execute(text("SELECT * FROM UserActivitySummary")).fetchall()
    return render_template('user_activity_summary.html', result=result)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = UpdatePasswordForm()
    if form.validate_on_submit():
        if form.old_password.data != current_user.password:
            flash('Eski şifreniz yanlış!', 'danger')
        elif form.new_password.data != form.confirm_new_password.data:
            flash('Yeni şifreler eşleşmiyor!', 'danger')
        else:
            current_user.password = form.new_password.data
            db.session.commit()
            flash('Şifreniz başarıyla güncellendi.', 'success')
            return redirect(url_for('profile'))
    return render_template('profile.html', form=form)

@app.route('/delete-account', methods=['POST'])
@login_required
def delete_account():
    password = request.form.get('password')
    
    if not check_password_hash(current_user.password, password):
        flash('Şifre yanlış!', 'danger')
        return redirect(url_for('profile'))
    
    try:
        # Önce kullanıcının beğenilerini sil
        db.session.execute(text('DELETE FROM "like" WHERE user_id = :user_id'), {'user_id': current_user.id})
        db.session.execute(text('DELETE FROM comment_like WHERE user_id = :user_id'), {'user_id': current_user.id})
        
        # Sonra kullanıcının yorumlarını sil
        db.session.execute(text('DELETE FROM comment WHERE user_id = :user_id'), {'user_id': current_user.id})
        
        # En son kullanıcının postlarını sil
        db.session.execute(text('DELETE FROM post WHERE user_id = :user_id'), {'user_id': current_user.id})
        
        # Son olarak kullanıcıyı sil
        db.session.delete(current_user)
        db.session.commit()
        
        logout_user()
        flash('Hesabınız başarıyla silindi.', 'success')
        return redirect(url_for('index'))
    except Exception as e:
        db.session.rollback()
        flash('Hesap silinirken bir hata oluştu.', 'danger')
        return redirect(url_for('profile'))

@app.route('/resend-confirmation')
@login_required
def resend_confirmation():
    if current_user.email_confirmed:
        flash('E-posta adresiniz zaten onaylanmış.', 'info')
        return redirect(url_for('index'))
    
    send_confirmation_email(current_user)
    flash('Yeni bir onay e-postası gönderildi. Lütfen gelen kutunuzu kontrol edin.', 'success')
    return redirect(url_for('index'))

@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    try:
        user = User.query.get_or_404(user_id)
        if user.id == current_user.id:
            return jsonify({'success': False, 'error': 'Kendinizi silemezsiniz!'})
        
        # Önce kullanıcının beğenilerini sil
        db.session.execute(text('DELETE FROM "like" WHERE user_id = :user_id'), {'user_id': user.id})
        db.session.execute(text('DELETE FROM comment_like WHERE user_id = :user_id'), {'user_id': user.id})
        
        # Sonra kullanıcının yorumlarını sil
        db.session.execute(text('DELETE FROM comment WHERE user_id = :user_id'), {'user_id': user.id})
        
        # En son kullanıcının postlarını sil
        db.session.execute(text('DELETE FROM post WHERE user_id = :user_id'), {'user_id': user.id})
        
        # Son olarak kullanıcıyı sil
        db.session.delete(user)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Kullanıcı başarıyla silindi'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/comment/<int:comment_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    db.session.delete(comment)
    db.session.commit()
    return jsonify({'success': True})

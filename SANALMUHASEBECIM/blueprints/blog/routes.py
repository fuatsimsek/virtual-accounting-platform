from flask import render_template, flash, redirect, url_for, request, abort, jsonify
from flask_login import current_user, login_required
from functools import wraps
from . import bp
from SANALMUHASEBECIM.models import Post, Comment, Like, CommentLike, User, Tag, Subscriber
from SANALMUHASEBECIM.forms import PostForm, CommentForm
from SANALMUHASEBECIM.extensions import db, limiter
from datetime import datetime
from SANALMUHASEBECIM.utils import send_email
from sqlalchemy.orm import load_only, joinedload
from sqlalchemy import func


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Bu sayfaya erişim yetkiniz yok.', 'danger')
            return redirect(url_for('public.index'))
        return f(*args, **kwargs)
    return decorated_function


def is_spam(text: str) -> bool:
    if not text:
        return True
    lower = text.lower()
    blacklisted = ["http://", "https://", "viagra", "casino", "buy now"]
    return any(k in lower for k in blacklisted)


@bp.route("/")
def index():
    page = request.args.get('page', 1, type=int)
    per_page = 6
    # Bazı ortamlarda henüz migration uygulanmamış olabilir. Güvenli alanlarda kal.
    base_query = (
        Post.query.options(
            load_only(
                Post.id,
                Post.title,
                Post.subtitle,
                Post.slug,
                Post.excerpt,
                Post.post_date,
                Post.post_text,
                Post.is_active,
                Post.status,
                Post.published_at,
                Post.seo_title,
                Post.seo_desc,
                Post.cover_id,
                Post.user_id,
            ),
            joinedload(Post.author)
        ).filter(Post.is_active == True)
    )

    # Önce yayınlanmışlara göre dene; hata olursa post_date'e göre basit bir sorguya düş.
    items = []
    total = 0
    order_q = None
    try:
        order_q = base_query.filter(Post.status == 'published').order_by(Post.published_at.desc())
        items = order_q.limit(per_page).offset((page - 1) * per_page).all()
        # COUNT'u güvenli şekilde sadece id ile yap
        total = db.session.query(func.count(Post.id)).filter(Post.is_active == True, Post.status == 'published').scalar() or 0
    except Exception:
        order_q = base_query.order_by(Post.post_date.desc())
        items = order_q.limit(per_page).offset((page - 1) * per_page).all()
        total = db.session.query(func.count(Post.id)).filter(Post.is_active == True).scalar() or 0

    # Basit pagination objesi
    class _Pagination:
        def __init__(self, items, page, per_page, total):
            self.items = items
            self.page = page
            self.per_page = per_page
            self.total = total
            self.pages = max(1, (total + per_page - 1) // per_page)
            self.has_prev = page > 1
            self.has_next = page < self.pages
            self.prev_num = page - 1 if self.has_prev else None
            self.next_num = page + 1 if self.has_next else None

    posts = _Pagination(items, page, per_page, total)
    return render_template('blog/index.html', title='Blog', posts=posts)


@bp.route("/tag/<slug>")
def by_tag(slug):
    tag = Tag.query.filter_by(slug=slug).first_or_404()
    page = request.args.get('page', 1, type=int)
    posts_query = Post.query.filter(Post.tags.any(Tag.id == tag.id), Post.is_active == True)
    posts = posts_query.order_by(Post.published_at.desc().nullslast(), Post.post_date.desc()).paginate(page=page, per_page=6)
    return render_template('blog/index.html', title=f"#{tag.name}", posts=posts, active_tag=tag)


@bp.route("/<slug>")
def post_detail(slug):
    post = Post.query.filter_by(slug=slug, is_active=True, status='published').first_or_404()
    form = CommentForm()
    comments = Comment.query.filter_by(post_id=post.id, parent_id=None).filter(Comment.is_approved == True).order_by(Comment.date.desc()).all()
    return render_template('blog/post_detail.html', title=post.title, post=post, form=form, comments=comments)


@bp.route("/<slug>/comment", methods=['POST'])
@login_required
@limiter.limit("30 per minute")
def add_comment(slug):
    post = Post.query.filter_by(slug=slug, is_active=True).first_or_404()
    form = CommentForm()
    
    if form.validate_on_submit():
        content = form.content.data.strip()
        
        if not content:
            flash('Yorum içeriği boş olamaz.', 'danger')
            return redirect(url_for('blog.post_detail', slug=slug))
            
        if is_spam(content):
            flash('Yorum içeriği uygunsuz bulundu.', 'danger')
            return redirect(url_for('blog.post_detail', slug=slug))
            
        try:
            comment = Comment(
                content=content,
                user_id=current_user.id,
                post_id=post.id
            )
            # Moderasyon: admin değilse onay beklesin
            comment.is_approved = current_user.is_admin
            db.session.add(comment)
            db.session.commit()
            
            if current_user.is_admin:
                flash('Yorum yayınlandı.', 'success')
            else:
                flash('Yorumunuz alındı, onaylandıktan sonra yayınlanacaktır.', 'info')
                
        except Exception as e:
            db.session.rollback()
            flash('Yorum gönderilirken bir hata oluştu. Lütfen tekrar deneyin.', 'danger')
            print(f"Comment error: {e}")
    else:
        # Form validation hatalarını göster
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{getattr(form, field).label.text}: {error}', 'danger')
    
    return redirect(url_for('blog.post_detail', slug=slug))


@bp.route("/new", methods=['GET','POST'])
@login_required
@admin_required
def new_post():
    form = PostForm()
    if form.validate_on_submit():
        # Önce kaydet, sonra slug üret
        post = Post(
            title=form.title.data,
            subtitle=form.subtitle.data,
            post_text=form.post_text.data,
            user=current_user,
        )
        db.session.add(post)
        db.session.commit()

        # Basit slug üretimi ve yayınlama
        import re
        def slugify(value: str) -> str:
            value = value.strip().lower()
            value = re.sub(r"[^a-z0-9\s-]", "", value)
            value = re.sub(r"[\s-]+", "-", value)
            return value

        base_slug = slugify(form.title.data or f"post-{post.id}")
        post.slug = f"{base_slug}-{post.id}"
        post.status = 'published'
        post.published_at = datetime.utcnow()
        db.session.commit()

        # Yeni gönderi bildirimi: abone listesine gönder
        try:
            subs = Subscriber.query.filter_by(is_active=True).all()
            if subs:
                emails = [s.email for s in subs if s.email]
                post_url = url_for('blog.post_detail', slug=post.slug, _external=True)
                subject = f"Yeni Yazı: {post.title}"
                html_body = f"<p>Yeni bir yazı yayınladık: <strong>{post.title}</strong></p><p><a href='{post_url}'>Yazıyı okumak için tıklayın</a></p>"
                text_body = f"Yeni bir yazı yayınladık: {post.title}\n{post_url}"
                # Büyük listeler için basit bölme (50'lik gruplar)
                for i in range(0, len(emails), 50):
                    send_email(subject=subject, recipients=emails[i:i+50], text_body=text_body, html_body=html_body)
        except Exception:
            pass

        flash('Gönderi başarıyla oluşturuldu!', 'success')
        return redirect(url_for('blog.post_detail', slug=post.slug))
    return render_template('blog/create_post.html', title='Yeni Gönderi', form=form)


@bp.route("/<int:post_id>/edit", methods=['GET','POST'])
@login_required
@admin_required
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)
    form = PostForm()
    if form.validate_on_submit():
        post.title = form.title.data
        post.subtitle = form.subtitle.data
        post.post_text = form.post_text.data
        db.session.commit()
        flash('Gönderi başarıyla güncellendi!', 'success')
        return redirect(url_for('blog.post_detail', slug=post.slug or post.id))
    elif request.method == 'GET':
        form.title.data = post.title
        form.subtitle.data = post.subtitle
        form.post_text.data = post.post_text
    return render_template('blog/edit_post.html', title='Gönderi Düzenle', form=form, post=post)


@bp.route("/<int:post_id>/delete", methods=['POST'])
@login_required
@admin_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    flash('Gönderi başarıyla silindi!', 'success')
    return redirect(url_for('blog.index'))


@bp.route("/<int:post_id>/like", methods=['POST'])
@login_required
def like_post(post_id):
    post = Post.query.get_or_404(post_id)
    existing_like = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    
    if existing_like:
        db.session.delete(existing_like)
        flash('Beğeniniz kaldırıldı.', 'info')
    else:
        like = Like(user_id=current_user.id, post_id=post_id)
        db.session.add(like)
        flash('Gönderi beğenildi!', 'success')
    
    db.session.commit()
    return redirect(url_for('blog.post_detail', slug=post.slug or post.id))


@bp.route("/comment/<int:comment_id>/like", methods=['POST'])
@login_required
def like_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    existing_like = CommentLike.query.filter_by(user_id=current_user.id, comment_id=comment_id).first()
    
    if existing_like:
        db.session.delete(existing_like)
        comment.like_count -= 1
        flash('Beğeniniz kaldırıldı.', 'info')
    else:
        like = CommentLike(user_id=current_user.id, comment_id=comment_id)
        db.session.add(like)
        comment.like_count += 1
        flash('Yorum beğenildi!', 'success')
    
    db.session.commit()
    return redirect(url_for('blog.post_detail', slug=comment.post.slug or comment.post.id))


@bp.route("/comment/<int:comment_id>/reply", methods=['POST'])
@login_required
@limiter.limit("30 per minute")
def reply_comment(comment_id):
    parent_comment = Comment.query.get_or_404(comment_id)
    content = request.form.get('content')
    
    if not content or is_spam(content):
        flash('Yorum içeriği boş veya uygunsuz.', 'danger')
        return redirect(url_for('blog.post_detail', slug=parent_comment.post.slug or parent_comment.post.id))
    
    reply = Comment(
        content=content,
        user_id=current_user.id,
        post_id=parent_comment.post_id,
        parent_id=comment_id
    )
    # Moderasyon: admin değilse onay beklesin
    reply.is_approved = current_user.is_admin
    
    db.session.add(reply)
    db.session.commit()
    if current_user.is_admin:
        flash('Yanıt yayınlandı!', 'success')
    else:
        flash('Yanıtınız alındı, onaylandıktan sonra yayınlanacaktır.', 'info')
    return redirect(url_for('blog.post_detail', slug=parent_comment.post.slug or parent_comment.post.id))


@bp.route("/like_post/<int:post_id>", methods=['POST'])
@login_required
def like_post_ajax(post_id):
    post = Post.query.get_or_404(post_id)
    existing_like = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    
    if existing_like:
        db.session.delete(existing_like)
        liked = False
    else:
        like = Like(user_id=current_user.id, post_id=post_id)
        db.session.add(like)
        liked = True
    
    db.session.commit()
    
    # Post'un toplam beğeni sayısını al
    total_likes = Like.query.filter_by(post_id=post_id).count()
    
    return jsonify({
        'success': True,
        'liked': liked,
        'likes': total_likes
    })


@bp.route("/like_comment/<int:comment_id>", methods=['POST'])
@login_required
def like_comment_ajax(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    existing_like = CommentLike.query.filter_by(user_id=current_user.id, comment_id=comment_id).first()
    
    if existing_like:
        db.session.delete(existing_like)
        liked = False
    else:
        like = CommentLike(user_id=current_user.id, comment_id=comment_id)
        db.session.add(like)
        liked = True
    
    db.session.commit()
    
    # Comment'in toplam beğeni sayısını al
    total_likes = CommentLike.query.filter_by(comment_id=comment_id).count()
    
    return jsonify({
        'success': True,
        'liked': liked,
        'likes': total_likes
    })


@bp.route("/reply_comment/<int:comment_id>", methods=['POST'])
@login_required
@limiter.limit("30 per minute")
def reply_comment_ajax(comment_id):
    parent_comment = Comment.query.get_or_404(comment_id)
    data = request.get_json()
    content = data.get('content', '').strip()
    
    if not content or is_spam(content):
        return jsonify({
            'success': False,
            'message': 'Yorum içeriği boş veya uygunsuz.'
        })
    
    reply = Comment(
        content=content,
        user_id=current_user.id,
        post_id=parent_comment.post_id,
        parent_id=comment_id
    )
    # Moderasyon: admin değilse onay beklesin
    reply.is_approved = current_user.is_admin
    
    db.session.add(reply)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Yanıt yayınlandı!' if current_user.is_admin else 'Yanıtınız alındı, onaylandıktan sonra yayınlanacaktır.'
    })

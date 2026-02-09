from flask import render_template, flash, redirect, url_for, request, current_app, session
from flask_login import current_user, login_required
from datetime import datetime
from . import bp
from SANALMUHASEBECIM.models import Ticket, TicketMessage, Service, Media
from SANALMUHASEBECIM.extensions import db
from SANALMUHASEBECIM.utils import send_telegram_message, send_email
import os
from werkzeug.utils import secure_filename
from SANALMUHASEBECIM.models import User

@bp.route("/")
@login_required
def index():
    tickets = Ticket.query.filter_by(user_id=current_user.id).filter(Ticket.status.notin_(['closed', 'completed'])).order_by(Ticket.created_at.desc()).all()
    # Unread mapping per ticket (admin mesajları ve diğer kullanıcı mesajları)
    last_seen_map = session.get('ticket_last_seen', {}) or {}
    unread_map = {}
    for t in tickets:
        seen_iso = last_seen_map.get(str(t.id))
        seen_dt = None
        if seen_iso:
            try:
                from datetime import datetime as _dt
                seen_dt = _dt.fromisoformat(seen_iso)
            except Exception:
                seen_dt = None
        q = TicketMessage.query.filter(
            TicketMessage.ticket_id == t.id,
            TicketMessage.user_id != current_user.id
        )
        if seen_dt:
            q = q.filter(TicketMessage.created_at > seen_dt)
        unread_map[t.id] = q.count()
    return render_template('helpdesk/index.html', title='Yardım Merkezi', tickets=tickets, unread_map=unread_map)

@bp.route("/new", methods=['GET', 'POST'])
@login_required
def new_ticket():
    # Kullanıcının kapatılmamış ticket'ı varsa yeni oluşturmayı engelle
    existing = Ticket.query.filter_by(user_id=current_user.id).filter(Ticket.status.notin_(['closed', 'completed'])).order_by(Ticket.created_at.desc()).first()
    if existing and request.method == 'GET':
        flash('Açık bir ticketınız varken yeni ticket oluşturamazsınız. Lütfen mevcut ticketı tamamlayın.', 'warning')
        return redirect(url_for('helpdesk.ticket_detail', ticket_id=existing.id))
    if request.method == 'POST':
        existing = Ticket.query.filter_by(user_id=current_user.id).filter(Ticket.status.notin_(['closed', 'completed'])).first()
        if existing:
            flash('Açık bir ticketınız varken yeni ticket oluşturamazsınız. Mevcut ticket sayfasına yönlendirildiniz.', 'warning')
            return redirect(url_for('helpdesk.ticket_detail', ticket_id=existing.id))
        topic = request.form.get('topic')
        subject = request.form.get('subject')
        message = request.form.get('message')
        priority = request.form.get('priority', 'normal')
        file = request.files.get('attachment')
        
        if not topic:
            flash('Lütfen konu seçimi yapın.', 'danger')
            return redirect(url_for('helpdesk.new_ticket'))
        if not subject or not message:
            flash('Konu ve mesaj alanları zorunludur.', 'danger')
            return redirect(url_for('helpdesk.new_ticket'))
        
        # Türkçe konu normalizasyonu
        try:
            tmap = {
                'diger': 'Diğer', 'diğer': 'Diğer', 'Diğer': 'Diğer',
                'odeme & fiyatlandirma': 'Ödeme & Fiyatlandırma', 'Ödeme & Fiyatlandırma': 'Ödeme & Fiyatlandırma',
                'randevu & gorusme': 'Randevu & Görüşme', 'Randevu & Görüşme': 'Randevu & Görüşme',
                'fatura & muhasebe': 'Fatura & Muhasebe', 'Fatura & Muhasebe': 'Fatura & Muhasebe',
                'teknik destek': 'Teknik Destek', 'Teknik Destek': 'Teknik Destek',
                'hizmet talebi': 'Hizmet Talebi', 'Hizmet Talebi': 'Hizmet Talebi',
            }
            topic_key = (topic or '').lower()
            topic = tmap.get(topic_key, topic)
        except Exception:
            pass

        ticket = Ticket(
            user_id=current_user.id,
            subject=f"[{topic}] {subject}",
            status='new',  # Varsayılan olarak 'new' durumu
            priority=priority
        )
        db.session.add(ticket)
        db.session.commit()
        
        # İlk mesajı ekle
        ticket_message = TicketMessage(
            ticket_id=ticket.id,
            user_id=current_user.id,
            content=message
        )

        # Opsiyonel dosya yükleme
        if file and file.filename:
            allowed = set(current_app.config.get('ALLOWED_EXTENSIONS') or [])
            ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
            if allowed and ext not in allowed:
                flash('Dosya tipi desteklenmiyor.', 'danger')
                return redirect(url_for('helpdesk.new_ticket'))
            upload_folder = current_app.config['UPLOAD_FOLDER']
            os.makedirs(upload_folder, exist_ok=True)
            safe_name = secure_filename(f"ticket_{current_user.id}_{int(datetime.utcnow().timestamp())}.{ext}" if ext else file.filename)
            filepath = os.path.join(upload_folder, safe_name)
            file.save(filepath)
            try:
                rel_path = os.path.relpath(filepath, os.path.join(current_app.root_path, 'static'))
                url = url_for('static', filename=rel_path.replace('\\', '/'))
            except Exception:
                url = None
            media = Media(
                file_name=safe_name,
                url=url or '',
                mime=file.mimetype,
                size=os.path.getsize(filepath),
                user_id=current_user.id,
            )
            db.session.add(media)
            db.session.commit()
            ticket_message.attachment_id = media.id

        db.session.add(ticket_message)
        db.session.commit()
        
        # Telegram bildirimi
        send_telegram_message(f"Yeni ticket: {subject}\nKullanıcı: {current_user.name} ({current_user.email})\nÖncelik: {priority}")
        
        flash('Ticket başarıyla oluşturuldu!', 'success')
        return redirect(url_for('helpdesk.ticket_detail', ticket_id=ticket.id))
    # GET
    allowed = list(current_app.config.get('ALLOWED_EXTENSIONS') or [])
    allowed.sort()
    accept_attr = ','.join(['.' + e.strip().lower() for e in allowed if e]) if allowed else ''
    allowed_text = ', '.join(allowed).upper() if allowed else 'PDF, JPG, PNG, DOCX'
    # Prefill support via query params
    pre_topic = request.args.get('topic', '')
    pre_subject = request.args.get('subject', '')
    pre_message = request.args.get('message', '')

    # Türkçe karakter normalizasyonu (sık karşılaşılan dönüşümler)
    def fix_tr(text: str) -> str:
        if not text:
            return text
        repl = [
            ('Iptal', 'İptal'), ('Itiraz', 'İtiraz'), ('Itirazi', 'İtirazı'),
            ('hakkinda', 'hakkında'), ('Aylik', 'Aylık'), ('Adi', 'Adı'),
            ('Olusturulma', 'Oluşturulma'), ('Odem', 'Ödem'), ('Ode', 'Öde'),
            ('kaldirilmasini', 'kaldırılmasını'), ('degerlendirir', 'değerlendirir'),
        ]
        for a,b in repl:
            text = text.replace(a, b)
        return text
    pre_subject = fix_tr(pre_subject)
    pre_message = fix_tr(pre_message)
    pre_priority = request.args.get('priority', '')
    return render_template(
        'helpdesk/new_ticket.html',
        title='Yeni Ticket',
        accept_attr=accept_attr,
        allowed_text=allowed_text,
        pre_topic=pre_topic,
        pre_subject=pre_subject,
        pre_message=pre_message,
        pre_priority=pre_priority
    )

@bp.route("/<int:ticket_id>")
@login_required
def ticket_detail(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    
    # Sadece kendi ticket'ını görebilir (admin hariç)
    if ticket.user_id != current_user.id and not current_user.is_admin:
        flash('Bu ticket\'a erişim yetkiniz yok.', 'danger')
        return redirect(url_for('helpdesk.index'))
    
    # Kullanıcı sohbete girdi: tüm ticket'ları görülmüş say → navbar ve Yardım rozetleri sıfırlansın
    try:
        last_seen_map = session.get('ticket_last_seen', {}) or {}
        from datetime import datetime as _dt
        now_iso = _dt.utcnow().isoformat()
        if not current_user.is_admin:
            user_ticket_ids = [t.id for t in Ticket.query.filter_by(user_id=current_user.id).filter(Ticket.status.notin_(['closed', 'completed'])).all()]
            for tid in user_ticket_ids:
                last_seen_map[str(tid)] = now_iso
        else:
            # admin için sadece bu ticket'ı güncelle
            last_seen_map[str(ticket.id)] = now_iso
        session['ticket_last_seen'] = last_seen_map
    except Exception:
        pass
    return render_template('helpdesk/ticket_detail.html', title=ticket.subject, ticket=ticket)

@bp.route("/<int:ticket_id>/open", methods=["POST"])
@login_required
def open_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    # Only admin can open chat
    if not current_user.is_admin:
        flash('Bu işlem için yetkiniz yok.', 'danger')
        return redirect(url_for('helpdesk.ticket_detail', ticket_id=ticket.id))
    if ticket.status != 'new':
        flash('Sohbet zaten açık veya kapalı.', 'info')
        return redirect(url_for('helpdesk.ticket_detail', ticket_id=ticket.id))
    ticket.status = 'open'
    # Visible notice to user
    msg = TicketMessage(
        ticket_id=ticket.id,
        user_id=current_user.id,
        content=f"Destek uzmanımız {current_user.name} talebinizi değerlendiriyor.")
    db.session.add(msg)
    db.session.commit()
    try:
        # Notify user by email
        if ticket.owner and ticket.owner.email:
            send_email(
                subject=f"Ticket Güncellendi - {ticket.subject}",
                recipients=[ticket.owner.email],
                text_body=f"Talebiniz destek uzmanımız {current_user.name} tarafından ele alındı.",
                html_body=f"<p>Talebiniz destek uzmanımız <strong>{current_user.name}</strong> tarafından ele alındı.</p>"
            )
    except Exception:
        pass
    flash('Sohbet açıldı ve kullanıcı bilgilendirildi.', 'success')
    return redirect(url_for('helpdesk.ticket_detail', ticket_id=ticket.id))

@bp.route("/unread-count")
@login_required
def unread_count():
    """Return total unread ticket messages for current user."""
    if current_user.is_admin:
        return {"count": 0}
    tickets = Ticket.query.filter_by(user_id=current_user.id).filter(Ticket.status.notin_(['closed', 'completed'])).all()
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
    return {"count": total}

@bp.route("/<int:ticket_id>/stream")
@login_required
def stream_messages(ticket_id):
    """Return messages newer than given last_id for a ticket."""
    ticket = Ticket.query.get_or_404(ticket_id)
    if ticket.user_id != current_user.id and not current_user.is_admin:
        return {"messages": []}
    
    # Don't stream messages for completed tickets
    if ticket.status in ['closed', 'completed']:
        return {"messages": []}
        
    try:
        last_id = int(request.args.get('last_id') or 0)
    except Exception:
        last_id = 0
    msgs = TicketMessage.query.filter(
        TicketMessage.ticket_id == ticket.id,
        TicketMessage.id > last_id
    ).order_by(TicketMessage.id.asc()).all()
    data = []
    for m in msgs:
        # Author name'i doğru şekilde al
        author_name = 'Sistem'
        if m.author:
            if m.author.id == current_user.id:
                author_name = current_user.name
            else:
                author_name = m.author.name
        
        data.append({
            "id": m.id,
            "content": m.content,
            "author_name": author_name,
            "is_admin": bool(m.author and m.author.is_admin),
            "is_me": bool(current_user.is_authenticated and m.author and m.author.id == current_user.id),
            "created_at": m.created_at.strftime('%d.%m.%Y %H:%M'),
            "date": m.created_at.strftime('%d.%m.%Y'),
            "attachment_url": (m.attachment.url if m.attachment else None),
            "attachment_name": (m.attachment.file_name if m.attachment else None),
        })
    return {"messages": data}

@bp.route("/<int:ticket_id>/seen", methods=["POST"])
@login_required
def mark_seen(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    if ticket.user_id != current_user.id and not current_user.is_admin:
        return {"ok": False}
    
    # Don't mark seen for completed tickets
    if ticket.status in ['closed', 'completed']:
        return {"ok": False}
        
    try:
        last_seen_map = session.get('ticket_last_seen', {}) or {}
        from datetime import datetime as _dt
        now_iso = _dt.utcnow().isoformat()
        if not current_user.is_admin:
            user_ticket_ids = [t.id for t in Ticket.query.filter_by(user_id=current_user.id).filter(Ticket.status.notin_(['closed', 'completed'])).all()]
            for tid in user_ticket_ids:
                last_seen_map[str(tid)] = now_iso
        else:
            last_seen_map[str(ticket.id)] = now_iso
        session['ticket_last_seen'] = last_seen_map
        return {"ok": True}
    except Exception:
        return {"ok": False}

@bp.route("/<int:ticket_id>/message", methods=['POST'])
@login_required
def add_message(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    
    # Sadece kendi ticket'ına mesaj ekleyebilir (admin hariç)
    if ticket.user_id != current_user.id and not current_user.is_admin:
        flash('Bu ticket\'a mesaj ekleme yetkiniz yok.', 'danger')
        return redirect(url_for('helpdesk.index'))
    
    # Block messaging based on status
    if ticket.status in ['closed', 'completed']:
        flash('Bu sohbet tamamlanmıştır.', 'warning')
        return redirect(url_for('helpdesk.ticket_detail', ticket_id=ticket.id))
    if ticket.status == 'new':
        if current_user.is_admin:
            flash('Mesaj göndermeden önce sohbeti açın.', 'warning')
        else:
            flash('Yetkili talebinizi inceliyor. Lütfen yanıtı bekleyin.', 'warning')
        return redirect(url_for('helpdesk.ticket_detail', ticket_id=ticket.id))

    message_content = request.form.get('message')
    if not message_content:
        flash('Mesaj içeriği boş olamaz.', 'danger')
        return redirect(url_for('helpdesk.ticket_detail', ticket_id=ticket.id))
    
    # Remove auto-open on first admin message (now explicit via /open)
    is_admin_first_message = False
    
    # Normal mesaj ekle
    message = TicketMessage(
        ticket_id=ticket.id,
        user_id=current_user.id,
        content=message_content
    )
    
    db.session.add(message)
    db.session.commit()
    
    # Telegram bildirimi
    if not current_user.is_admin:
        send_telegram_message(f"Ticket yanıtı: {ticket.subject}\nKullanıcı: {current_user.name}\nMesaj: {message_content[:120]}")
    
    flash('Mesajınız eklendi.', 'success')
    return redirect(url_for('helpdesk.ticket_detail', ticket_id=ticket.id))

@bp.route("/<int:ticket_id>/complete", methods=["POST"])
@login_required
def complete_ticket(ticket_id):
    """Ticket'ı tamamla ve sohbeti sonlandır"""
    ticket = Ticket.query.get_or_404(ticket_id)
    
    # Sadece kendi ticket'ını veya atanan yetkili tamamlayabilir
    if ticket.user_id != current_user.id and not current_user.is_admin:
        flash('Bu ticket\'ı tamamlama yetkiniz yok.', 'danger')
        return redirect(url_for('helpdesk.index'))
    
    # Ticket durumunu güncelle
    ticket.status = 'completed'
    ticket.completed_at = datetime.utcnow()
    ticket.completed_by = current_user.id
    
    # Sistem mesajı ekle
    if current_user.is_admin:
        system_message = "Müşteri temsilcimiz tarafından tamamlandı."
    else:
        system_message = "Görüşmeyi sonlandırdınız."
    
    sysmsg = TicketMessage(
        ticket_id=ticket.id,
        user_id=current_user.id,
        content=system_message
    )
    
    db.session.add(sysmsg)
    db.session.commit()
    
    # E-posta bildirimi gönder
    try:
        if ticket.owner and ticket.owner.email:
            send_email(
                subject=f"Ticket Tamamlandı - {ticket.subject}",
                recipients=[ticket.owner.email],
                text_body=f"Ticket'ınız tamamlandı.\n\nKonu: {ticket.subject}\nTamamlanma: {ticket.completed_at.strftime('%d.%m.%Y %H:%M')}",
                html_body=f"<p>Ticket'ınız <strong>tamamlandı</strong>.</p><p><strong>Konu:</strong> {ticket.subject}</p><p><strong>Tamamlanma:</strong> {ticket.completed_at.strftime('%d.%m.%Y %H:%M')}</p>"
            )
    except Exception:
        pass
    
    # Admin'e bildirim gönder (eğer kullanıcı tamamladıysa)
    if not current_user.is_admin:
        try:
            # Tüm admin kullanıcılarına e-posta gönder
            admin_users = User.query.filter_by(is_admin=True).all()
            admin_emails = [admin.email for admin in admin_users if admin.email]
            
            if admin_emails:
                send_email(
                    subject=f"Ticket Kullanıcı Tarafından Tamamlandı - #{ticket.id}",
                    recipients=admin_emails,
                    text_body=f"Ticket kullanıcı tarafından tamamlandı.\n\nTicket ID: {ticket.id}\nKonu: {ticket.subject}\nKullanıcı: {current_user.name} ({current_user.email})\nTamamlanma: {ticket.completed_at.strftime('%d.%m.%Y %H:%M')}\n\nAdmin panelinden kontrol edebilirsiniz: {url_for('admin.tickets', _external=True)}",
                    html_body=f"<p><strong>Ticket kullanıcı tarafından tamamlandı.</strong></p><p><strong>Ticket ID:</strong> {ticket.id}</p><p><strong>Konu:</strong> {ticket.subject}</p><p><strong>Kullanıcı:</strong> {current_user.name} ({current_user.email})</p><p><strong>Tamamlanma:</strong> {ticket.completed_at.strftime('%d.%m.%Y %H:%M')}</p><p><br>Admin panelinden kontrol edebilirsiniz: <a href='{url_for('admin.tickets', _external=True)}'>Admin Paneli</a></p>"
                )
            
            # Telegram bildirimi
            send_telegram_message(f"🎯 TICKET TAMAMLANDI!\n\nTicket ID: #{ticket.id}\nKonu: {ticket.subject}\nKullanıcı: {current_user.name}\nTamamlanma: {ticket.completed_at.strftime('%d.%m.%Y %H:%M')}\n\nAdmin panelinden kontrol edin!")
            
        except Exception:
            pass
    
    flash('Ticket tamamlandı ve sohbet sonlandırıldı.', 'success')
    
    # Admin ise admin paneline, kullanıcı ise helpdesk ana sayfasına yönlendir
    if current_user.is_admin:
        return redirect(url_for('admin.tickets'))
    else:
        return redirect(url_for('helpdesk.index'))

@bp.route("/<int:ticket_id>/close", methods=["POST"])
@login_required
def close_ticket(ticket_id):
    """Eski close fonksiyonu - artık kullanılmıyor"""
    return redirect(url_for('helpdesk.complete_ticket', ticket_id=ticket_id))

@bp.route("/<int:ticket_id>/status")
@login_required
def ticket_status(ticket_id):
    """JSON endpoint to check ticket status"""
    ticket = Ticket.query.get_or_404(ticket_id)
    
    # Sadece kendi ticket'ını görebilir (admin hariç)
    if ticket.user_id != current_user.id and not current_user.is_admin:
        return {'error': 'Unauthorized'}, 403
    
    return {
        'id': ticket.id,
        'status': ticket.status,
        'is_completed': ticket.status in ['closed', 'completed'],
        'completed_at': ticket.completed_at.isoformat() if ticket.completed_at else None
    }

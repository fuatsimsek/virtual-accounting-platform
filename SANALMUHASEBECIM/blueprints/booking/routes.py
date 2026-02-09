from flask import render_template, flash, redirect, url_for, request
from flask_login import current_user, login_required
from datetime import datetime, timedelta, date
from . import bp
from SANALMUHASEBECIM.models import Appointment
from sqlalchemy import or_, and_
from SANALMUHASEBECIM.forms import DanismanlikForm
from SANALMUHASEBECIM.extensions import db
from SANALMUHASEBECIM.utils import (
    send_telegram_message,
    create_gcal_event,
    send_email_sync,
    generate_appointment_token,
    verify_appointment_token,
    delete_gcal_event,
)

@bp.route("/")
def index():
    return render_template('booking/index.html', title='Randevu Al')

@bp.route("/new", methods=['GET', 'POST'])
@bp.route("/new/<int:service_request_id>", methods=['GET', 'POST'])
@login_required
def new_appointment(service_request_id=None):
    form = DanismanlikForm()
    # Aktif aylık hizmet varsa yeni randevu engeli
    try:
        from SANALMUHASEBECIM.models import Lead
        active_monthly = Lead.query \
            .filter(Lead.user_id == current_user.id) \
            .filter(Lead.lead_type == 'monthly') \
            .filter(Lead.status.in_(['paid', 'completed'])) \
            .first()
        if active_monthly:
            flash('Aktif aylık hizmetiniz varken yeni randevu alamazsınız. Lütfen mevcut hizmet üzerinden ilerleyin.', 'warning')
            return redirect(url_for('account.my_services'))
    except Exception:
        pass
    
    # Service request varsa, formu doldur
    service_request = None
    selected_service = None
    services = []
    # Hizmet detayından gelebilecek isteğe bağlı service_id
    incoming_service_id = request.args.get('service_id', type=int)
    if service_request_id:
        from SANALMUHASEBECIM.models import ServiceRequest
        service_request = ServiceRequest.query.filter_by(
            id=service_request_id, 
            user_id=current_user.id
        ).first_or_404()
        
        # Formu otomatik doldur
        if request.method == 'GET':
            try:
                form.email.data = current_user.email
                form.purpose.data = f"{service_request.service.name} - Ön Görüşme\n\nEkstra Detaylar:\n{service_request.additional_details or 'Belirtilmedi'}"
            except Exception:
                pass
    # ServiceRequest yoksa ama service_id ile geldiyse, formu önceden doldur
    if not service_request_id and request.method == 'GET':
        if incoming_service_id:
            # Belirli bir hizmet seçildiyse
            try:
                from SANALMUHASEBECIM.models import Service
                s = Service.query.get(incoming_service_id)
                if s:
                    form.email.data = current_user.email
                    form.purpose.data = f"{s.name} - Ön Görüşme"
                    selected_service = s
            except Exception:
                pass
        else:
            # Hizmet seçilmediyse (opsiyonel seçili) - tek hizmet olarak algıla
            try:
                from SANALMUHASEBECIM.models import Service
                # İlk aktif hizmeti al
                first_service = Service.query.filter_by(is_active=True).order_by(Service.order_index.asc(), Service.id.asc()).first()
                if first_service:
                    form.email.data = current_user.email
                    form.purpose.data = f"{first_service.name} - Ön Görüşme"
                    selected_service = first_service
            except Exception:
                pass
    
    # Aktif hizmetleri yükle
    try:
        from SANALMUHASEBECIM.models import Service
        services = Service.query.filter_by(is_active=True).order_by(Service.order_index.asc(), Service.id.asc()).all()
    except Exception:
        services = []
    
    # Mevcut onaylanmış randevuları yükle (randevu durumu göstermek için)
    try:
        confirmed_appointments = Appointment.query \
            .filter(Appointment.user_id == current_user.id) \
            .filter(Appointment.status == 'confirmed') \
            .filter(Appointment.appointment_datetime >= datetime.utcnow()) \
            .order_by(Appointment.appointment_datetime.asc()) \
            .all()
    except Exception:
        confirmed_appointments = []
    
    if form.validate_on_submit():
        # Tekrarlı randevuları engelle: Gelecekte tarihi olan ve aktif durumdaki randevu varsa yenisini oluşturma
        try:
            now_guard = datetime.utcnow()
            existing_active = Appointment.query \
                .filter(Appointment.user_id == current_user.id) \
                .filter(Appointment.appointment_datetime >= now_guard) \
                .filter(Appointment.status.in_(['pending', 'email_confirmed', 'confirmed'])) \
                .order_by(Appointment.appointment_datetime.desc()) \
                .first()
            if existing_active:
                flash('Mevcut bir randevu talebiniz bulunuyor. Lütfen mevcut talebi sonuçlandırın veya iptal edin.', 'warning')
                return redirect(url_for('booking.new_appointment'))
        except Exception:
            pass
        # Tarih ve saati birleştir
        appointment_datetime = datetime.combine(
            form.appointment_date.data,
            datetime.strptime(form.appointment_time.data, '%H:%M').time()
        )
        
        from SANALMUHASEBECIM.utils import ensure_appointment_platform_column
        ensure_appointment_platform_column()

        # Eğer mevcut bir service_request yoksa ve hizmetten gelindiyse yeni bir ServiceRequest oluştur
        if not service_request_id:
            # form üzerinden de gelebilir
            svc_id = incoming_service_id
            if not svc_id:
                try:
                    svc_id = int(request.form.get('service_id')) if request.form.get('service_id') else None
                except Exception:
                    svc_id = None
            
            # Eğer hizmet seçilmediyse (opsiyonel seçili) - ilk aktif hizmeti kullan
            if not svc_id:
                try:
                    from SANALMUHASEBECIM.models import Service
                    first_service = Service.query.filter_by(is_active=True).order_by(Service.order_index.asc(), Service.id.asc()).first()
                    if first_service:
                        svc_id = first_service.id
                except Exception:
                    pass
            
            if svc_id:
                try:
                    from SANALMUHASEBECIM.models import ServiceRequest
                    new_req = ServiceRequest(
                        user_id=current_user.id,
                        service_id=svc_id,
                        additional_details=None,
                        status='pending'
                    )
                    db.session.add(new_req)
                    db.session.flush()
                    service_request_id = new_req.id
                except Exception:
                    service_request_id = None
        appointment = Appointment(
            email=form.email.data or current_user.email,
            appointment_datetime=appointment_datetime,
            purpose=form.purpose.data,
            user=current_user,
            service_request_id=service_request_id,
            status='pending'
        )
        try:
            # platform may not exist yet in DB; handled by ensure function above
            setattr(appointment, 'platform', form.platform.data)
        except Exception:
            pass
        
        db.session.add(appointment)
        db.session.commit()
        
        # Telegram bildirimi
        send_telegram_message(f"Yeni randevu talebi: {appointment.email} - {appointment.appointment_datetime:%d.%m.%Y %H:%M}\nAmaç: {appointment.purpose}")
        
        # Google Calendar ekleme: Kullanıcı talebinde değil, admin kesin onayında yapılacak
        # Kullanıcıya e-posta onayı gönder (formdaki e-posta adresine)
        try:
            dt_str = appointment.appointment_datetime.strftime('%d.%m.%Y %H:%M')
            subject = "Randevu Talebinizi Aldık"
            text_body = (
                f"Merhaba,\n\n"
                f"{dt_str} tarihli ücretsiz ön görüşme talebinizi aldık.\n"
                f"Onay için aşağıdaki bağlantıya tıklayın. Onay sonrası görüşme linki oluşturulacaktır.\n\n"
                f"Onay Bağlantısı: {url_for('booking.confirm', token=generate_appointment_token(appointment.id, appointment.created_at), _external=True)}\n\n"
                f"İptal Bağlantısı: {url_for('booking.cancel_appointment_email', token=generate_appointment_token(appointment.id, appointment.created_at), _external=True)}\n\n"
                f"Sanal Muhasebecim"
            )
            html_body = (
                f"<div style='font-family:Arial,sans-serif'>"
                f"<h3>Randevu Talebinizi Aldık</h3>"
                f"<p><b>Tarih/Saat:</b> {dt_str}</p>"
                f"<p>Talebiniz alınmıştır. Onaylamak için aşağıdaki butona tıklayın.</p>"
                f"<div style='margin:20px 0'>"
                f"<a href='{url_for('booking.confirm', token=generate_appointment_token(appointment.id, appointment.created_at), _external=True)}' style='background:#0ea5e9;color:white;padding:10px 16px;border-radius:8px;text-decoration:none'>Randevumu Onayla</a>"
                f"</div>"
                f"<div style='margin:20px 0;border-top:1px solid #e5e7eb;padding-top:20px'>"
                f"<p style='color:#64748b;font-size:14px'>Eğer randevuyu iptal etmek istiyorsanız:</p>"
                f"<a href='{url_for('booking.cancel_appointment_email', token=generate_appointment_token(appointment.id, appointment.created_at), _external=True)}' style='background:#ef4444;color:white;padding:8px 12px;border-radius:6px;text-decoration:none;font-size:14px'>Randevumu İptal Et</a>"
                f"</div>"
                f"<p style='color:#64748b'>Bu e-posta bilgilendirme amaçlıdır.</p>"
                f"</div>"
            )
            recipient_email = form.email.data or appointment.email
            send_email_sync(subject=subject, recipients=[recipient_email], text_body=text_body, html_body=html_body)
            flash('Onay için e-posta adresinize bir bağlantı gönderdik. Lütfen onaylayın.', 'info')
        except Exception as e:
            flash(f'E-posta gönderilemedi: {e}', 'warning')
        
        flash('Randevu talebiniz alındı. Lütfen e-posta onayı yapın.', 'success')
        return redirect(url_for('booking.new_appointment', email_sent=1))
    
    # Form hatalarını göster
    if request.method == 'POST' and form.errors:
        for field, errors in form.errors.items():
            for err in errors:
                flash(f"{field}: {err}", 'danger')
    
    # Determine UI step state for progress view (persistent without query params)
    ui_step = 1
    email_sent = request.args.get('email_sent') == '1'
    confirmed_param = request.args.get('confirmed') == '1'
    force_reset = request.args.get('reset') == '1'
    last_appt = None
    try:
        if current_user.is_authenticated:
            # Sadece aktif sayılabilecek randevuları dikkate al (iptal/tamamlananları hariç tut)
            active_statuses = ['pending', 'awaiting_payment', 'email_confirmed', 'confirmed']
            last_appt = Appointment.query \
                .filter(Appointment.user_id == current_user.id) \
                .filter(Appointment.status.in_(active_statuses)) \
                .order_by(Appointment.appointment_datetime.desc()) \
                .first()
    except Exception:
        last_appt = None

    now = datetime.utcnow()
    if force_reset:
        last_appt = None
        ui_step = 1
    # Eğer son randevu iptal/bitmiş ise doğrudan yeni randevu akışını aç
    if last_appt and last_appt.status in ['cancelled', 'completed']:
        ui_step = 1
    elif last_appt and last_appt.meeting_link and last_appt.status == 'confirmed':
        ui_step = 3
    elif last_appt and last_appt.status in ['confirmed','email_confirmed']:
        ui_step = 2
    elif last_appt and last_appt.appointment_datetime and last_appt.appointment_datetime >= now and last_appt.status in ['pending', 'awaiting_payment']:
        ui_step = 1
    elif confirmed_param or (last_appt and last_appt.status == 'email_confirmed'):
        # E-posta onayı tamamlandı => adım 2
        ui_step = 2
    elif email_sent:
        # E-posta gönderildi ama onaylanmadı => adım 1
        ui_step = 1

    return render_template('booking/new_appointment.html', title='Yeni Randevu', form=form, service_request=service_request, selected_service=selected_service, services=services, ui_step=ui_step, last_appointment=last_appt, email_sent=email_sent, confirmed_appointments=confirmed_appointments)


@bp.route('/confirm/<token>')
def confirm(token):
    appointment_id = verify_appointment_token(token)
    if not appointment_id:
        flash('Onay bağlantısı geçersiz veya süresi dolmuş.', 'danger')
        return redirect(url_for('booking.index'))
    appt = Appointment.query.get_or_404(appointment_id)
    # Kullanıcı e-posta onayını yaptı; durum email_confirmed olsun (yetkili onayı bekleniyor)
    if appt.status in ['confirmed','email_confirmed']:
        flash('E-posta onayınız zaten alınmış.', 'info')
        return redirect(url_for('booking.new_appointment', confirmed=1))
    
    # Randevu durumunu email_confirmed yap (yetkili onayı bekleniyor)
    appt.status = 'email_confirmed'
    db.session.commit()
    
    flash('E-posta onayınız alındı. Yetkili onayı bekleniyor; onaylanınca link e-posta ile gönderilecek.', 'success')
    return redirect(url_for('booking.new_appointment', confirmed=1))

@bp.route('/cancel/<token>')
def cancel_appointment_email(token):
    appointment_id = verify_appointment_token(token)
    if not appointment_id:
        flash('İptal bağlantısı geçersiz veya süresi dolmuş.', 'danger')
        return redirect(url_for('booking.index'))
    
    appt = Appointment.query.get_or_404(appointment_id)
    
    # Randevuyu iptal et
    appt.status = 'cancelled'
    try:
        # İlgili lead'i iptal durumuna çek
        if appt.service_request and appt.service_request.lead:
            appt.service_request.lead.status = 'cancelled'
    except Exception:
        pass
    db.session.commit()
    
    flash('Randevunuz iptal edildi. Yeni bir randevu oluşturabilirsiniz.', 'success')
    return redirect(url_for('booking.new_appointment'))

@bp.route("/my-appointments")
@login_required
def my_appointments():
    appointments = Appointment.query.filter_by(user_id=current_user.id).order_by(Appointment.appointment_datetime.desc()).all()
    return render_template('booking/my_appointments.html', title='Randevularım', appointments=appointments, now_utc=datetime.utcnow())

@bp.route("/<int:appointment_id>/cancel", methods=['POST'])
@login_required
def cancel_appointment(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    
    # Sadece kendi randevusunu iptal edebilir
    if appointment.user_id != current_user.id:
        flash('Bu randevuyu iptal etme yetkiniz yok.', 'danger')
        return redirect(url_for('booking.my_appointments'))
    
    # 5 saat kuralı: randevu saatine 5 saatten az kaldıysa iptal edilemez
    now = datetime.utcnow()
    if appointment.appointment_datetime - now < timedelta(hours=5):
        flash('Randevu saatine 5 saatten az kaldığı için iptal edilemez.', 'warning')
        return redirect(url_for('booking.my_appointments'))

    # İptal et, kullanıcı tarafından iptal edildi bilgisini notlara işle
    appointment.status = 'cancelled'
    try:
        # İlgili lead'i iptal durumuna çek
        if appointment.service_request and appointment.service_request.lead:
            appointment.service_request.lead.status = 'cancelled'
    except Exception:
        pass
    try:
        appointment.notes = (appointment.notes or '').strip()
        tag = 'kullanici_iptal'
        if tag not in (appointment.notes or ''):
            appointment.notes = (appointment.notes + ' ' + tag).strip() if appointment.notes else tag
        # İptal sebebi ve kullanıcı notu ekle
        reason = (request.form.get('cancel_reason') or '').strip()
        note = (request.form.get('cancel_note') or '').strip()
        parts = []
        if reason:
            reason_map = {
                'plan_change': 'Plan değişikliği',
                'not_available': 'Belirtilen saatte uygun değil',
                'other': 'Diğer'
            }
            reason_text = reason_map.get(reason, reason)
            parts.append(f"reason={reason_text}")
        if note:
            # limit note length to avoid overflow
            safe_note = note[:500]
            parts.append(f"note={safe_note}")
        if parts:
            extra = ' [' + '; '.join(parts) + ']'
            appointment.notes = (appointment.notes + extra).strip() if appointment.notes else extra
    except Exception:
        pass
    db.session.commit()

    # Takvimden sil (best-effort)
    try:
        delete_gcal_event(
            summary=f"Danışmanlık - {appointment.email}",
            starts_at=appointment.appointment_datetime,
            ends_at=appointment.appointment_datetime + timedelta(minutes=30),
            attendee_email=appointment.email
        )
    except Exception:
        pass

    # E-posta bildirimleri
    try:
        dt_str = appointment.appointment_datetime.strftime('%d.%m.%Y %H:%M')
        subject_user = 'Randevunuz İptal Edildi'
        text_user = f"{dt_str} tarihli randevunuz talebiniz üzerine iptal edilmiştir."
        html_user = f"""
        <div style='font-family:Arial,sans-serif'>
          <h3>Randevunuz İptal Edildi</h3>
          <p><b>Tarih/Saat:</b> {dt_str}</p>
          <p>Talebiniz üzerine randevunuz iptal edilmiştir.</p>
        </div>
        """
        send_email_sync(subject=subject_user, recipients=[appointment.email], text_body=text_user, html_body=html_user)

        subject_admin = 'Kullanıcı Tarafından Randevu İptali'
        # Admin'e sebep ve not bilgisini de gönder
        reason = (request.form.get('cancel_reason') or '').strip()
        note = (request.form.get('cancel_note') or '').strip()
        reason_map = {
            'plan_change': 'Plan değişikliği',
            'not_available': 'Belirtilen saatte uygun değil',
            'other': 'Diğer'
        }
        reason_text = reason_map.get(reason, '-') if reason else '-'
        text_admin = (
            f"Kullanıcı ({appointment.email}) {dt_str} tarihli randevusunu iptal etti.\n"
            f"Sebep: {reason_text}\n"
            f"Not: {note or '-'}"
        )
        html_admin = f"""
        <div style='font-family:Arial,sans-serif'>
          <h3>Kullanıcı Tarafından Randevu İptali</h3>
          <p><b>Kullanıcı:</b> {appointment.email}</p>
          <p><b>Tarih/Saat:</b> {dt_str}</p>
          <p><b>Etiket:</b> Kullanıcı tarafından iptal</p>
          <p><b>Sebep:</b> {reason_text}</p>
          <p><b>Kullanıcı Notu:</b> {(note or '-')}</p>
        </div>
        """
        send_email_sync(subject=subject_admin, recipients=['info@sanalmuhasebem.net'], text_body=text_admin, html_body=html_admin)
    except Exception:
        pass

    flash('Randevunuz iptal edildi.', 'success')
    return redirect(url_for('booking.my_appointments'))


@bp.route('/availability')
@login_required
def availability():
    """Return confirmed appointment times for a given date (YYYY-MM-DD)."""
    day_str = request.args.get('date')
    if not day_str:
        return {"times": []}
    try:
        day = datetime.strptime(day_str, '%Y-%m-%d').date()
    except ValueError:
        return {"times": []}
    start = datetime.combine(day, datetime.min.time())
    end = datetime.combine(day, datetime.max.time())
    taken = Appointment.query.filter(
        Appointment.status == 'confirmed',
        Appointment.appointment_datetime >= start,
        Appointment.appointment_datetime <= end,
    ).all()
    times = [a.appointment_datetime.strftime('%H:%M') for a in taken]
    return {"times": times}

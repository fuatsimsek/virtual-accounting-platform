from flask import current_app, url_for, has_request_context
from flask_mail import Message
from threading import Thread
from SANALMUHASEBECIM.extensions import mail
from SANALMUHASEBECIM.extensions import db
import requests
import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os


def _build_static_url(filename: str) -> str:
	"""Return absolute static URL usable outside request context.
	If no request context, uses BASE_URL config (e.g., https://www.sanalmuhasebem.net).
	"""
	base_url = current_app.config.get('BASE_URL') or current_app.config.get('SITE_BASE_URL')
	if has_request_context():
		try:
			return url_for('static', filename=filename, _external=True)
		except Exception:
			pass
	# Fallback to BASE_URL + /static/...
	if base_url:
		return f"{base_url.rstrip('/')}/static/{filename}"
	# Last resort: relative path (some clients may not fetch)
	return f"/static/{filename}"


def get_email_header():
	"""Karizmatik mail header'ı oluşturur"""
	return f"""
	<div style="background: linear-gradient(135deg, #0d6efd 0%, #0b5ed7 100%); color: white; padding: 20px; border-radius: 16px 16px 0 0; text-align: center; margin-bottom: 0;">
		<h1 style="margin: 0; font-size: 22px; font-weight: 800; text-transform: uppercase; letter-spacing: .5px; text-shadow: 0 2px 4px rgba(0,0,0,0.2); line-height: 1.15;">Sanal Muhasebecim</h1>
		<p style="margin: 6px 0 0 0; font-size: 12px; font-style: italic; opacity: 0.95; text-shadow: 0 1px 2px rgba(0,0,0,0.2); line-height: 1.2;">Güvenilir Finansal Çözüm Ortağınız</p>
	</div>
	"""


def get_email_signature():
	"""Karizmatik mail imzası oluşturur"""
	return f"""
	<div style="margin-top: 24px; padding-top: 16px; border-top: 2px solid #0d6efd; background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); border-radius: 12px; padding: 16px;">
		<h3 style="margin: 0 0 6px 0; color: #0d6efd; font-size: 16px; font-weight: 800; text-transform: uppercase; letter-spacing: .3px; line-height: 1.1; text-align: center;">Sanal Muhasebecim</h3>
		<p style="margin: 0 0 10px 0; color: #6c757d; font-size: 11px; font-style: italic; font-weight: 500; line-height: 1.2; text-align: center;">Güvenilir Finansal Çözüm Ortağınız</p>
		<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 10px 0;">
			<div style="background: white; padding: 12px; border-radius: 8px; border-left: 4px solid #0d6efd; box-shadow: 0 1px 6px rgba(0,0,0,0.06);">
				<h4 style="margin: 0 0 6px 0; color: #0d6efd; font-size: 12px; font-weight: 700;">📧 İletişim</h4>
				<p style="margin: 0; color: #495057; font-size: 12px;">info@sanalmuhasebem.net</p>
			</div>
			<div style="background: white; padding: 12px; border-radius: 8px; border-left: 4px solid #198754; box-shadow: 0 1px 6px rgba(0,0,0,0.06);">
				<h4 style="margin: 0 0 6px 0; color: #198754; font-size: 12px; font-weight: 700;">🌐 Web Sitesi</h4>
				<p style="margin: 0; color: #495057; font-size: 12px;">www.sanalmuhasebem.net</p>
			</div>
		</div>
		<div style="text-align: center; padding: 8px; background: white; border-radius: 8px; border: 1px solid #e9ecef;">
			<p style="margin: 0; color: #6c757d; font-size: 11px; font-weight: 600;">💼 Profesyonel Muhasebe Hizmetleri</p>
		</div>
		<div style="text-align: center; margin-top: 12px; padding-top: 8px; border-top: 1px solid #dee2e6;">
			        <p style="margin: 0; color: #6c757d; font-size: 10px;">© 2025 Sanal Muhasebecim. Tüm hakları saklıdır.</p>
		</div>
	</div>
	"""


def _wrap_html_email(html_inner: str) -> str:
	"""Verilen HTML içeriğini standart header + signature ile sarar.
	İçerik zaten tam sayfa bir şablon ise (header ve signature içeriyorsa) olduğu gibi döner.
	"""
	try:
		# Basit sezgisel kontrol: zaten header veya signature fonksiyonlarının çıktısından parça içeriyorsa sarmalama.
		if 'Güvenilir Finansal Çözüm Ortağınız' in html_inner or 'Profesyonel Muhasebe Hizmetleri' in html_inner:
			return html_inner
	except Exception:
		pass
	return f"""
	<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 15px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1);">
		{get_email_header()}
		<div style="padding: 30px; background-color: white;">
			{html_inner}
		</div>
		{get_email_signature()}
	</div>
	"""


def create_multipart_email(subject: str, recipients: List[str], html_content: str, 
						  text_content: str = None, attachments: List[Dict[str, Any]] = None,
						  reply_to: str = None, cc: List[str] = None, bcc: List[str] = None) -> Message:
	"""
	Multipart mail oluşturur (HTML + Text + Attachments)
	
	Args:
		subject: Mail konusu
		recipients: Alıcılar listesi
		html_content: HTML içerik
		text_content: Düz metin içerik (opsiyonel)
		attachments: Ek dosyalar listesi [{'filename': 'file.pdf', 'content': bytes, 'content_type': 'application/pdf'}]
		reply_to: Yanıt adresi
		cc: CC alıcıları
		bcc: BCC alıcıları
	"""
	msg = Message(subject, recipients=recipients, charset='utf-8')
	
	# HTML içerik - UTF-8 encoding ile
	msg.html = html_content.encode('utf-8').decode('utf-8')
	
	# Düz metin içerik (HTML'den otomatik oluşturulur)
	if text_content:
		msg.body = text_content.encode('utf-8').decode('utf-8')
	else:
		# HTML'den basit metin oluştur
		import re
		text_content = re.sub(r'<[^>]+>', '', html_content)
		text_content = re.sub(r'\s+', ' ', text_content).strip()
		msg.body = text_content.encode('utf-8').decode('utf-8')
	
	# Reply-to ayarla
	if reply_to:
		msg.reply_to = reply_to
	
	# CC ve BCC ayarla
	if cc:
		msg.cc = cc
	if bcc:
		msg.bcc = bcc
	
	# Ek dosyalar
	if attachments:
		for attachment in attachments:
			filename = attachment.get('filename')
			content = attachment.get('content')
			content_type = attachment.get('content_type', 'application/octet-stream')
			
			if filename and content:
				msg.attach(filename, content_type, content)
	
	return msg


def send_async_email(app, msg):
	with app.app_context():
		try:
			mail.send(msg)
		except Exception as e:
			# Log but don't raise in async path
			try:
				current_app.logger.error(f"Async email send failed: {e}")
			except Exception:
				pass


def send_email(subject, recipients, text_body, html_body, attachments=None, reply_to=None, cc=None, bcc=None):
	"""Gelişmiş mail gönderme fonksiyonu"""
	# HTML gövdeyi standart şablon ile sar
	html_body = _wrap_html_email(html_body or "")
	msg = create_multipart_email(
		subject=subject,
		recipients=recipients,
		html_content=html_body,
		text_content=text_body,
		attachments=attachments,
		reply_to=reply_to,
		cc=cc,
		bcc=bcc
	)
	Thread(target=send_async_email,
	       args=(current_app._get_current_object(), msg)).start()


def send_email_sync(subject, recipients, text_body, html_body, attachments=None, reply_to=None, cc=None, bcc=None):
	"""Send email synchronously so caller can catch errors."""
	# HTML gövdeyi standart şablon ile sar
	html_body = _wrap_html_email(html_body or "")
	msg = create_multipart_email(
		subject=subject,
		recipients=recipients,
		html_content=html_body,
		text_content=text_body,
		attachments=attachments,
		reply_to=reply_to,
		cc=cc,
		bcc=bcc
	)
	mail.send(msg)


def _get_serializer() -> URLSafeTimedSerializer:
	secret = current_app.config.get('SECRET_KEY')
	return URLSafeTimedSerializer(secret_key=secret, salt='appointment-confirm')


def generate_appointment_token(appointment_id: int, created_at: datetime) -> str:
	s = _get_serializer()
	return s.dumps({'id': appointment_id, 'ts': int(created_at.timestamp())})


def verify_appointment_token(token: str, max_age_seconds: int = 86400) -> Optional[int]:
	s = _get_serializer()
	try:
		data = s.loads(token, max_age=max_age_seconds)
		return int(data.get('id'))
	except (BadSignature, SignatureExpired):
		return None


def ensure_appointment_platform_column() -> None:
	"""Ensure Appointments.platform column exists (MSSQL safe)."""
	try:
		with db.engine.begin() as conn:
			conn.execute(db.text("""
				IF COL_LENGTH('Appointments', 'platform') IS NULL
				BEGIN
					ALTER TABLE Appointments ADD platform VARCHAR(20) NULL;
				END
			"""))
	except Exception:
		# Best effort; ignore if cannot alter in this environment
		pass


def send_telegram_message(text: str) -> bool:
	"""Send a simple text notification via Telegram bot if configured."""
	token = current_app.config.get('TELEGRAM_BOT_TOKEN')
	chat_id = current_app.config.get('TELEGRAM_CHAT_ID')
	if not token or not chat_id:
		return False
	try:
		resp = requests.post(
			f"https://api.telegram.org/bot{token}/sendMessage",
			json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
			timeout=10,
		)
		return resp.ok
	except Exception:
		return False


def create_gcal_event(summary: str,
					description: str,
					starts_at: datetime,
					ends_at: datetime,
					attendees_emails: Optional[List[str]] = None) -> Optional[str]:
	"""Create a Google Calendar event using a service account.
	Returns htmlLink on success, None otherwise.
	"""
	service_json_path = current_app.config.get('GOOGLE_SERVICE_ACCOUNT_JSON')
	calendar_id = current_app.config.get('GOOGLE_CALENDAR_ID')
	if not service_json_path or not calendar_id:
		return None
	try:
		from google.oauth2 import service_account
		from googleapiclient.discovery import build
		creds = service_account.Credentials.from_service_account_file(
			service_json_path,
			scopes=['https://www.googleapis.com/auth/calendar']
		)
		service = build('calendar', 'v3', credentials=creds)
		event_body = {
			'summary': summary,
			'description': description,
			'start': {'dateTime': starts_at.isoformat(), 'timeZone': 'Europe/Istanbul'},
			'end': {'dateTime': ends_at.isoformat(), 'timeZone': 'Europe/Istanbul'},
		}
		if attendees_emails:
			event_body['attendees'] = [{'email': e} for e in attendees_emails]
		event = service.events().insert(calendarId=calendar_id, body=event_body, sendUpdates='all').execute()
		return event.get('htmlLink')
	except Exception:
		return None


def delete_gcal_event(summary: Optional[str] = None,
					  starts_at: Optional[datetime] = None,
					  ends_at: Optional[datetime] = None,
					  attendee_email: Optional[str] = None) -> bool:
	"""Find and delete Google Calendar events best-effort.
	If event id is unknown, filters by time range, optional summary text and attendee email.
	Returns True if call attempted (even if none found)."""
	service_json_path = current_app.config.get('GOOGLE_SERVICE_ACCOUNT_JSON')
	calendar_id = current_app.config.get('GOOGLE_CALENDAR_ID')
	if not service_json_path or not calendar_id:
		return False
	try:
		from google.oauth2 import service_account
		from googleapiclient.discovery import build
		creds = service_account.Credentials.from_service_account_file(
			service_json_path,
			scopes=['https://www.googleapis.com/auth/calendar']
		)
		service = build('calendar', 'v3', credentials=creds)
		list_kwargs = { 'calendarId': calendar_id, 'singleEvents': True, 'orderBy': 'startTime', 'maxResults': 50 }
		if starts_at:
			list_kwargs['timeMin'] = starts_at.isoformat()
		if ends_at:
			list_kwargs['timeMax'] = ends_at.isoformat()
		if summary:
			list_kwargs['q'] = summary
		resp = service.events().list(**list_kwargs).execute()
		items = resp.get('items', [])
		for ev in items:
			if attendee_email:
				emails = [a.get('email') for a in (ev.get('attendees') or []) if a.get('email')]
				if attendee_email not in emails:
					continue
			if summary and summary.lower() not in (ev.get('summary') or '').lower():
				continue
			try:
				service.events().delete(calendarId=calendar_id, eventId=ev.get('id')).execute()
			except Exception:
				pass
		return True
	except Exception:
		return False


def send_confirmation_email(user):
	token = user.generate_confirmation_token()
	subject = "E-posta Adresinizi Onaylayın - Sanal Muhasebecim"
	
	html_content = f"""
	<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 15px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1);">
		{get_email_header()}
		
		<div style="padding: 30px; background-color: white;">
		<div style="text-align: center; margin-bottom: 30px;">
				<div style="width: 80px; height: 80px; background: linear-gradient(135deg, #0d6efd 0%, #0b5ed7 100%); border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 20px; box-shadow: 0 4px 15px rgba(13, 110, 253, 0.3);">
					<span style="color: white; font-size: 32px;">👋</span>
				</div>
				<h2 style="color: #0d6efd; margin: 0; font-size: 24px; font-weight: 700;">Hoş Geldiniz!</h2>
			<p style="color: #6c757d; margin: 10px 0 0 0; font-size: 16px;">Sanal Muhasebecim'e Kayıt Olduğunuz İçin Teşekkür Ederiz</p>
		</div>
		
			<div style="background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); padding: 25px; border-radius: 12px; margin-bottom: 25px;">
				<p style="margin: 0 0 15px 0; font-size: 16px; line-height: 1.6;">Sayın <strong>{user.name}</strong>,</p>
			<p style="margin: 0 0 20px 0; font-size: 16px; line-height: 1.6;">Sanal Muhasebecim'e kayıt olduğunuz için teşekkür ederiz. Hesabınızı aktifleştirmek için lütfen aşağıdaki butona tıklayarak e-posta adresinizi onaylayın.</p>
			
			<div style="text-align: center; margin: 30px 0;">
				<a href="{url_for('account.confirm_email', token=token, _external=True)}" 
					   style="background: linear-gradient(135deg, #0d6efd 0%, #0b5ed7 100%); color: white; padding: 15px 35px; text-decoration: none; border-radius: 8px; font-weight: 600; display: inline-block; box-shadow: 0 4px 15px rgba(13, 110, 253, 0.3);">
						✅ E-posta Adresimi Onayla
				</a>
				</div>
			</div>
			
			<div style="background: #e8f5e9; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #198754;">
				<h4 style="margin: 0 0 10px 0; color: #198754; font-weight: 600; font-size: 16px;">⚠️ Önemli Bilgilendirme:</h4>
				<p style="margin: 0 0 10px 0; color: #198754;">Bu onay bağlantısı <strong>24 saat</strong> geçerlidir. Süre dolduğunda yeni bir onay bağlantısı talep edebilirsiniz.</p>
			</div>
			
			<div style="background: #fff3cd; padding: 15px; border-radius: 8px; border-left: 4px solid #ffc107;">
				<p style="margin: 0; color: #856404; font-size: 14px;">Eğer bu hesabı siz oluşturmadıysanız, lütfen bu e-postayı dikkate almayın.</p>
			</div>
		</div>
		
		{get_email_signature()}
	</div>
	"""
	
	text_content = f"""
	Hoş Geldiniz!
	
	Sayın {user.name},
	
	Sanal Muhasebecim'e kayıt olduğunuz için teşekkür ederiz. Hesabınızı aktifleştirmek için lütfen aşağıdaki bağlantıya tıklayarak e-posta adresinizi onaylayın:
	
	{url_for('account.confirm_email', token=token, _external=True)}
	
	Bu onay bağlantısı 24 saat geçerlidir.
	
	Saygılarımızla,
	Sanal Muhasebecim Ekibi
	"""
	
	send_email(
		subject=subject,
		recipients=[user.email],
		text_body=text_content,
		html_body=html_content,
		reply_to='info@sanalmuhasebem.net'
	)


def send_password_reset_email(user):
	token = user.generate_reset_token()
	subject = "Şifre Sıfırlama Talebi - Sanal Muhasebecim"
	
	html_content = f"""
	<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 15px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1);">
		{get_email_header()}
		
		<div style="padding: 30px; background-color: white;">
		<div style="text-align: center; margin-bottom: 30px;">
				<div style="width: 80px; height: 80px; background: linear-gradient(135deg, #dc3545 0%, #b02a37 100%); border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 20px; box-shadow: 0 4px 15px rgba(220, 53, 69, 0.3);">
					<span style="color: white; font-size: 32px;">🔐</span>
				</div>
				<h2 style="color: #dc3545; margin: 0; font-size: 24px; font-weight: 700;">Şifre Sıfırlama</h2>
			<p style="color: #6c757d; margin: 10px 0 0 0; font-size: 16px;">Hesabınız için şifre sıfırlama talebinde bulundunuz</p>
		</div>
		
			<div style="background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); padding: 25px; border-radius: 12px; margin-bottom: 25px;">
				<p style="margin: 0 0 15px 0; font-size: 16px; line-height: 1.6;">Sayın <strong>{user.name}</strong>,</p>
			<p style="margin: 0 0 20px 0; font-size: 16px; line-height: 1.6;">Hesabınız için şifre sıfırlama talebinde bulundunuz. Yeni şifrenizi belirlemek için aşağıdaki butona tıklayın.</p>
			
			<div style="text-align: center; margin: 30px 0;">
				<a href="{url_for('account.reset_password', token=token, _external=True)}" 
					   style="background: linear-gradient(135deg, #dc3545 0%, #b02a37 100%); color: white; padding: 15px 35px; text-decoration: none; border-radius: 8px; font-weight: 600; display: inline-block; box-shadow: 0 4px 15px rgba(220, 53, 69, 0.3);">
						🔐 Şifremi Sıfırla
				</a>
				</div>
			</div>
			
			<div style="background: #fff3cd; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #ffc107;">
				<h4 style="margin: 0 0 10px 0; color: #856404; font-weight: 600; font-size: 16px;">⚠️ Güvenlik Uyarısı:</h4>
				<p style="margin: 0 0 10px 0; color: #856404;">Bu bağlantı <strong>1 saat</strong> geçerlidir. Eğer şifre sıfırlama talebinde bulunmadıysanız, lütfen bu e-postayı dikkate almayın.</p>
			</div>
			
			<div style="background: #f8d7da; padding: 15px; border-radius: 8px; border-left: 4px solid #dc3545;">
				<p style="margin: 0; color: #721c24; font-size: 14px;">Eğer bu talebi siz yapmadıysanız, hesabınızın güvenliği için lütfen hemen şifrenizi değiştirin.</p>
			</div>
		</div>
		
		{get_email_signature()}
	</div>
	"""
	
	text_content = f"""
	Şifre Sıfırlama Talebi
	
	Sayın {user.name},
	
	Hesabınız için şifre sıfırlama talebinde bulundunuz. Yeni şifrenizi belirlemek için aşağıdaki bağlantıya tıklayın:
	
	{url_for('account.reset_password', token=token, _external=True)}
	
	Bu bağlantı 1 saat geçerlidir. Eğer şifre sıfırlama talebinde bulunmadıysanız, lütfen bu e-postayı dikkate almayın.
	
	Saygılarımızla,
	Sanal Muhasebecim Ekibi
	"""
	
	send_email(
		subject=subject,
		recipients=[user.email],
		text_body=text_content,
		html_body=html_content,
		reply_to='info@sanalmuhasebem.net'
	)


def send_iban_payment_email(to_email: str, amount_try: float, description: str):
	iban = current_app.config.get('IBAN')
	acc = current_app.config.get('IBAN_ACCOUNT_HOLDER')
	bank = current_app.config.get('IBAN_BANK_NAME')
	note = current_app.config.get('IBAN_PAYMENT_NOTE')
	subject = "Ödeme Bilgileri (IBAN) - Sanal Muhasebecim"
	
	text_content = f"""
	Ödeme Bilgileri (IBAN)
	
	Tutar: {amount_try:.2f} TL
	Açıklama: {description}
	Banka: {bank}
	IBAN: {iban}
	Hesap Sahibi: {acc}
	Not: {note}
	
	Sanal Muhasebecim
	"""
	
	html_content = f"""
	<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 15px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1);">
		{get_email_header()}
		
		<div style="padding: 30px; background-color: white;">
		<div style="text-align: center; margin-bottom: 30px;">
				<div style="width: 80px; height: 80px; background: linear-gradient(135deg, #198754 0%, #146c43 100%); border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 20px; box-shadow: 0 4px 15px rgba(25, 135, 84, 0.3);">
					<span style="color: white; font-size: 32px;">💳</span>
				</div>
				<h2 style="color: #198754; margin: 0; font-size: 24px; font-weight: 700;">💳 Ödeme Bilgileri</h2>
			<p style="color: #6c757d; margin: 10px 0 0 0; font-size: 16px;">IBAN ile Güvenli Ödeme</p>
		</div>
		
			<div style="background: linear-gradient(135deg, #198754 0%, #146c43 100%); color: white; padding: 25px; border-radius: 12px; margin-bottom: 25px; text-align: center; box-shadow: 0 4px 15px rgba(25, 135, 84, 0.3);">
				<h3 style="margin: 0 0 15px 0; font-size: 20px; font-weight: 600;">💰 Ödeme Tutarı</h3>
				<p style="margin: 0; font-size: 32px; font-weight: bold;">{amount_try:.2f} TL</p>
			</div>
			
			<div style="background: #e8f5e9; padding: 25px; border-radius: 8px; margin-bottom: 25px; border-left: 4px solid #198754;">
				<h4 style="margin: 0 0 20px 0; color: #198754; font-size: 18px; font-weight: 600;">📋 Ödeme Detayları</h4>
				<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 20px;">
					<div style="background: white; padding: 15px; border-radius: 8px; border-left: 4px solid #198754;">
						<h5 style="margin: 0 0 8px 0; color: #198754; font-size: 14px; font-weight: 600;">📝 Açıklama</h5>
						<p style="margin: 0; color: #495057; font-size: 16px; font-weight: 500;">{description}</p>
					</div>
					<div style="background: white; padding: 15px; border-radius: 8px; border-left: 4px solid #0d6efd;">
						<h5 style="margin: 0 0 8px 0; color: #0d6efd; font-size: 14px; font-weight: 600;">🏦 Banka</h5>
						<p style="margin: 0; color: #495057; font-size: 16px; font-weight: 500;">{bank}</p>
					</div>
				</div>
				
				<div style="background: white; padding: 20px; border-radius: 8px; border-left: 4px solid #6f42c1; margin-bottom: 20px;">
					<h5 style="margin: 0 0 8px 0; color: #6f42c1; font-size: 14px; font-weight: 600;">👤 Hesap Sahibi</h5>
					<p style="margin: 0; color: #495057; font-size: 16px; font-weight: 500;">{acc}</p>
				</div>
				
				<div style="background: white; padding: 20px; border-radius: 8px; border-left: 4px solid #ffc107;">
					<h5 style="margin: 0 0 8px 0; color: #856404; font-size: 14px; font-weight: 600;">💳 IBAN</h5>
					<code style="background: #f8f9fa; padding: 10px 15px; border-radius: 6px; font-family: monospace; font-size: 16px; font-weight: 600; color: #495057; display: block; text-align: center; letter-spacing: 1px;">{iban}</code>
				</div>
			</div>
			
			<div style="background: #fff3cd; padding: 20px; border-radius: 8px; border-left: 4px solid #ffc107;">
				<h4 style="margin: 0 0 10px 0; color: #856404; font-weight: 600; font-size: 16px;">💡 Önemli Not:</h4>
				<p style="margin: 0; color: #856404; font-size: 14px;">{note}</p>
			</div>
		</div>
		
		{get_email_signature()}
	</div>
	"""
	
	send_email(
		subject=subject,
		recipients=[to_email],
		text_body=text_content,
		html_body=html_content,
		reply_to='info@sanalmuhasebem.net'
	)
 

def send_contact_confirmation_email(contact_data: Dict[str, str]):
    """Contact formu için kullanıcıya otomatik teşekkür maili gönderir"""
    subject = "Mesajınız Alındı - Sanal Muhasebecim"
    
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 15px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1);">
        {get_email_header()}
        
        <div style="padding: 30px; background-color: white;">
            <div style="text-align: center; margin-bottom: 30px;">
                <div style="width: 80px; height: 80px; background: linear-gradient(135deg, #198754 0%, #146c43 100%); border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 20px; box-shadow: 0 4px 15px rgba(25, 135, 84, 0.3);">
                    <span style="color: white; font-size: 32px;">✓</span>
                </div>
                <h2 style="color: #198754; margin: 0; font-size: 24px; font-weight: 700;">Mesajınız Başarıyla Alındı!</h2>
                <p style="color: #6c757d; margin: 10px 0 0 0; font-size: 16px;">Teşekkür ederiz, en kısa sürede size dönüş yapacağız</p>
            </div>
            
            <div style="background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); padding: 25px; border-radius: 12px; margin-bottom: 25px;">
                <h3 style="margin: 0 0 20px 0; color: #0d6efd; font-size: 18px; font-weight: 600;">📋 Mesaj Detaylarınız</h3>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 20px;">
                    <div style="background: white; padding: 15px; border-radius: 8px; border-left: 4px solid #0d6efd;">
                        <h4 style="margin: 0 0 8px 0; color: #0d6efd; font-size: 14px; font-weight: 600;">👤 Ad Soyad</h4>
                        <p style="margin: 0; color: #495057; font-size: 16px; font-weight: 500;">{contact_data.get('name', '')}</p>
                    </div>
                    <div style="background: white; padding: 15px; border-radius: 8px; border-left: 4px solid #198754;">
                        <h4 style="margin: 0 0 8px 0; color: #198754; font-size: 14px; font-weight: 600;">📧 E-posta</h4>
                        <p style="margin: 0; color: #495057; font-size: 16px; font-weight: 500;">{contact_data.get('email', '')}</p>
                    </div>
                </div>
                
                <div style="background: white; padding: 15px; border-radius: 8px; border-left: 4px solid #ffc107; margin-bottom: 20px;">
                    <h4 style="margin: 0 0 8px 0; color: #856404; font-size: 14px; font-weight: 600;">📞 Telefon</h4>
                    <p style="margin: 0; color: #495057; font-size: 16px; font-weight: 500;">{contact_data.get('phone', '')}</p>
                </div>
                
                <div style="background: white; padding: 15px; border-radius: 8px; border-left: 4px solid #6f42c1;">
                    <h4 style="margin: 0 0 8px 0; color: #6f42c1; font-size: 14px; font-weight: 600;">📝 Konu</h4>
                    <p style="margin: 0; color: #495057; font-size: 16px; font-weight: 500;">{contact_data.get('subject', '')}</p>
                </div>
            </div>
            
            <div style="background: #e8f5e9; padding: 20px; border-radius: 8px; border-left: 4px solid #198754; margin-bottom: 25px;">
                <h4 style="margin: 0 0 15px 0; color: #198754; font-size: 16px; font-weight: 600;">💬 Mesajınız</h4>
                <div style="background: white; padding: 15px; border-radius: 6px; border: 1px solid #dee2e6;">
                    <p style="margin: 0; color: #495057; font-size: 14px; line-height: 1.6; white-space: pre-line;">{contact_data.get('message', '')}</p>
                </div>
            </div>
            
            <div style="background: #fff3cd; padding: 20px; border-radius: 8px; border-left: 4px solid #ffc107; margin-bottom: 25px;">
                <h4 style="margin: 0 0 10px 0; color: #856404; font-size: 16px; font-weight: 600;">⏰ Sonraki Adımlar</h4>
                <ul style="margin: 0; padding-left: 20px; color: #856404;">
                    <li style="margin-bottom: 8px;">Mesajınız ekibimiz tarafından incelenecek</li>
                    <li style="margin-bottom: 8px;">En kısa sürede size dönüş yapılacak</li>
                    <li style="margin-bottom: 8px;">Gerekirse telefon ile de iletişime geçeceğiz</li>
                </ul>
            </div>
            
            <div style="text-align: center; margin-top: 30px;">
                <a href="{url_for('public.contact', _external=True)}" 
                   style="background: linear-gradient(135deg, #0d6efd 0%, #0b5ed7 100%); color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px; font-weight: 600; display: inline-block; box-shadow: 0 4px 15px rgba(13, 110, 253, 0.3);">
                    📧 Yeni Mesaj Gönder
                </a>
            </div>
        </div>
        
        {get_email_signature()}
    </div>
    """
    
    text_content = f"""
    Mesajınız Başarıyla Alındı!
    
    Sayın {contact_data.get('name', '')},
    
    Mesajınız başarıyla alınmıştır. En kısa sürede size dönüş yapacağız.
    
    Mesaj Detaylarınız:
    - Ad Soyad: {contact_data.get('name', '')}
    - E-posta: {contact_data.get('email', '')}
    - Telefon: {contact_data.get('phone', '')}
    - Konu: {contact_data.get('subject', '')}
    - Mesaj: {contact_data.get('message', '')}
    
    Teşekkür ederiz.
    Sanal Muhasebecim Ekibi
    """
    
    send_email(
        subject=subject,
        recipients=[contact_data.get('email', '')],
        text_body=text_content,
        html_body=html_content,
        reply_to='info@sanalmuhasebem.net'
    )


def send_contact_notification_email(contact_data: Dict[str, str]):
    """Contact formu için admin'e bildirim maili gönderir"""
    subject = f"Yeni İletişim Formu Mesajı - {contact_data.get('name', '')}"
    
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 15px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1);">
        {get_email_header()}
        
        <div style="padding: 30px; background-color: white;">
            <div style="text-align: center; margin-bottom: 30px;">
                <div style="width: 80px; height: 80px; background: linear-gradient(135deg, #dc3545 0%, #b02a37 100%); border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 20px; box-shadow: 0 4px 15px rgba(220, 53, 69, 0.3);">
                    <span style="color: white; font-size: 32px;">📧</span>
                </div>
                <h2 style="color: #dc3545; margin: 0; font-size: 24px; font-weight: 700;">Yeni İletişim Formu Mesajı</h2>
                <p style="color: #6c757d; margin: 10px 0 0 0; font-size: 16px;">Müşteri iletişim talebi alındı</p>
            </div>
            
            <div style="background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); padding: 25px; border-radius: 12px; margin-bottom: 25px;">
                <h3 style="margin: 0 0 20px 0; color: #0d6efd; font-size: 18px; font-weight: 600;">👤 Müşteri Bilgileri</h3>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 20px;">
                    <div style="background: white; padding: 15px; border-radius: 8px; border-left: 4px solid #0d6efd;">
                        <h4 style="margin: 0 0 8px 0; color: #0d6efd; font-size: 14px; font-weight: 600;">👤 Ad Soyad</h4>
                        <p style="margin: 0; color: #495057; font-size: 16px; font-weight: 500;">{contact_data.get('name', '')}</p>
                    </div>
                    <div style="background: white; padding: 15px; border-radius: 8px; border-left: 4px solid #198754;">
                        <h4 style="margin: 0 0 8px 0; color: #198754; font-size: 14px; font-weight: 600;">📧 E-posta</h4>
                        <p style="margin: 0; color: #495057; font-size: 16px; font-weight: 500;">{contact_data.get('email', '')}</p>
                    </div>
                </div>
                
                <div style="background: white; padding: 15px; border-radius: 8px; border-left: 4px solid #ffc107; margin-bottom: 20px;">
                    <h4 style="margin: 0 0 8px 0; color: #856404; font-size: 14px; font-weight: 600;">📞 Telefon</h4>
                    <p style="margin: 0; color: #495057; font-size: 16px; font-weight: 500;">{contact_data.get('phone', '')}</p>
                </div>
                
                <div style="background: white; padding: 15px; border-radius: 8px; border-left: 4px solid #6f42c1;">
                    <h4 style="margin: 0 0 8px 0; color: #6f42c1; font-size: 14px; font-weight: 600;">📝 Konu</h4>
                    <p style="margin: 0; color: #495057; font-size: 16px; font-weight: 500;">{contact_data.get('subject', '')}</p>
                </div>
            </div>
            
            <div style="background: #e8f5e9; padding: 20px; border-radius: 8px; border-left: 4px solid #198754; margin-bottom: 25px;">
                <h4 style="margin: 0 0 15px 0; color: #198754; font-size: 16px; font-weight: 600;">💬 Mesaj İçeriği</h4>
                <div style="background: white; padding: 15px; border-radius: 6px; border: 1px solid #dee2e6;">
                    <p style="margin: 0; color: #495057; font-size: 14px; line-height: 1.6; white-space: pre-line;">{contact_data.get('message', '')}</p>
                </div>
			</div>
			
            <div style="background: #d1ecf1; padding: 20px; border-radius: 8px; border-left: 4px solid #0dcaf0; margin-bottom: 25px;">
                <h4 style="margin: 0 0 10px 0; color: #055160; font-size: 16px; font-weight: 600;">📅 Mesaj Bilgileri</h4>
                <p style="margin: 0 0 5px 0; color: #055160;"><strong>Gönderim Tarihi:</strong> {datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
                <p style="margin: 0; color: #055160;"><strong>IP Adresi:</strong> {contact_data.get('ip_address', 'Bilinmiyor')}</p>
			</div>
			
            <div style="text-align: center; margin-top: 30px;">
                <a href="mailto:{contact_data.get('email', '')}" 
                   style="background: linear-gradient(135deg, #198754 0%, #146c43 100%); color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px; font-weight: 600; display: inline-block; margin-right: 10px; box-shadow: 0 4px 15px rgba(25, 135, 84, 0.3);">
                    📧 Yanıtla
                </a>
                <a href="tel:{contact_data.get('phone', '')}" 
                   style="background: linear-gradient(135deg, #0dcaf0 0%, #0aa2c0 100%); color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px; font-weight: 600; display: inline-block; box-shadow: 0 4px 15px rgba(13, 202, 240, 0.3);">
                    📞 Ara
                </a>
			</div>
		</div>
		
		{get_email_signature()}
	</div>
	"""
    
    text_content = f"""
    Yeni İletişim Formu Mesajı
    
    Müşteri Bilgileri:
    - Ad Soyad: {contact_data.get('name', '')}
    - E-posta: {contact_data.get('email', '')}
    - Telefon: {contact_data.get('phone', '')}
    - Konu: {contact_data.get('subject', '')}
    - Mesaj: {contact_data.get('message', '')}
    - Tarih: {datetime.now().strftime('%d.%m.%Y %H:%M')}
    
    En kısa sürede müşteriye dönüş yapın.
    """
    
    send_email(
        subject=subject,
        recipients=['info@sanalmuhasebem.net'],
        text_body=text_content,
        html_body=html_content,
        reply_to=contact_data.get('email', '')
    )
 
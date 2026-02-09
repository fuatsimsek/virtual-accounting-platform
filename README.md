# Virtual Accounting Platform

A full-featured accounting and consultancy web platform built with Flask.

This project combines CRM-like lead tracking, appointment management, helpdesk workflows, content management (blog), and role-based access control in a single web application.

---

## Project Purpose

The platform is designed to help accounting and consultancy teams manage:

- client onboarding and service requests
- lead and payment lifecycle
- appointment scheduling and follow-up
- support tickets and communication
- content publishing and user engagement

It targets a practical, business-ready workflow where admins and clients can use the same system with different permissions.

---

## Technology Stack

### Backend
- Python 3
- Flask
- Flask-SQLAlchemy
- Flask-Login
- Flask-WTF (CSRF protection)
- Flask-Migrate / Alembic
- Flask-Mail
- Flask-Limiter
- Flask-Caching
- Authlib (OAuth integrations)

### Database
- Production deployments in this project were run on Microsoft SQL Server (MSSQL)
- Default local setup in this repository is SQLite (`app.db`) for quick onboarding
- ORM layer: SQLAlchemy
- Migration support: Alembic

### Frontend
- Jinja2 templates
- HTML/CSS/JS
- Admin and user dashboards
- TinyMCE integration for rich text editing

### Integrations
- SMTP email workflow
- Google OAuth / Facebook OAuth (optional)
- Google Calendar integration (optional)
- Telegram notifications (optional)

---

## Architecture Overview

The application follows a modular Flask blueprint structure:

- `SANALMUHASEBECIM/blueprints/public` -> landing pages, public routes, contact/lead intake
- `SANALMUHASEBECIM/blueprints/account` -> register/login/profile/account workflows
- `SANALMUHASEBECIM/blueprints/admin` -> admin dashboard, users, posts, services, tickets, analytics, payments
- `SANALMUHASEBECIM/blueprints/blog` -> post listing/details/comments/likes
- `SANALMUHASEBECIM/blueprints/booking` -> appointment and scheduling flows
- `SANALMUHASEBECIM/blueprints/helpdesk` -> ticket and support messaging

Core layers:
- `models.py` -> data models and relationships
- `forms.py` -> form validation and security checks
- `utils.py` -> mail utilities, token helpers, integration helpers
- `extensions.py` -> Flask extension initialization

---

## API / Route Usage (Practical)

This project is primarily server-rendered (Jinja + Flask routes), but also includes action endpoints used by forms and AJAX.

Common route groups:

- Public pages: `/`
- Account: `/account/*`
- Admin panel: `/admin/*`
- Blog: `/blog/*`
- Booking: `/booking/*`
- Helpdesk: `/helpdesk/*`

Examples of action endpoints in use:

- post like/comment actions (`/blog/...`)
- admin status toggles and management actions (`/admin/...`)
- lead and payment state updates (`/admin/lead/...`)
- subscriber management (`/admin/subscriber/...`)

---

## Setup and Run

### 1) Install dependencies

```bash
pip install -r requirements.txt
```

### 2) Create environment file

Copy `.env.example` to `.env` and fill values if needed.

If you leave database settings empty, the project uses local SQLite.
If you want MSSQL for production/staging, set `DATABASE_URL` accordingly.

### 3) Initialize database

```bash
python init_db.py
```

This creates:
- SQLite database (`app.db`)
- required tables
- demo admin and user accounts

MSSQL note:
- For production MSSQL usage, configure `DATABASE_URL` in `.env` and run your migration/init flow on SQL Server.

### 4) Start application

```bash
python start.py
```

Open:
- `http://127.0.0.1:5000`

---

## Demo Accounts

| Role  | Email             | Password |
|-------|-------------------|----------|
| Admin | `admin@example.com` | `admin` |
| User  | `user@example.com`  | `user` |

Admin panel URL:
- `/admin`

Testing shortcut:
- `/auto-login/admin`
- `/auto-login/user`

These helper routes are kept for local testing and screenshot flow. Remove them in production deployments.

---

## Screenshots

The product flow below follows a realistic user journey from first visit to admin operations.

### 1) First Contact and Onboarding

**Homepage**  
Main landing experience where users understand services and platform value.

![Homepage](assets/homepage.png)

**Homepage (Alternative UI)**  
An alternative homepage layout used during UI iteration.

![Homepage New Layout](assets/homepage-new-layout.png)

**Register Page**  
New users create an account and enter the client flow.

![Register Page](assets/register-page.png)

**Login Page**  
Standard user authentication entry point.

![Login Page](assets/login-page.png)

### 2) User Experience After Login

**Profile Page**  
Users manage personal and account-related details.

![Profile Page](assets/profile-page.png)

**My Services Page**  
Users can view assigned services and service lifecycle status.

![My Services Page](assets/my-services-page.png)

**Service Detail Page**  
Detailed operational/service-level view for a selected service.

![User Service Detail Page](assets/user-service-detail-page.png)

**User Service Status Check**  
Quick status visibility for active service requests.

![User Service Status Check](assets/user-service-status-check.png)

### 3) Booking and Support Workflow

**Schedule Meeting (Step 1)**  
User starts appointment booking flow.

![Schedule Meeting Step 1](assets/schedule-meeting-step-1.png)

**Schedule Meeting (Step 2)**  
User finalizes booking details and submission.

![Schedule Meeting Step 2](assets/schedule-meeting-step-2.png)

**Open Ticket**  
Support issue creation for operational helpdesk process.

![Open Ticket Page](assets/open-ticket-page.png)

**Ticket List**  
Users track open/closed ticket history.

![Ticket List Page](assets/ticket-list-page.png)

**Helpdesk Chat**  
Ticket conversation and back-and-forth support messaging.

![Helpdesk Chat](assets/helpdesk-chat.png)

### 4) Admin Operations and Control

**Admin Login**  
Dedicated entry for admin-level access.

![Admin Login](assets/admin-login.png)

**Admin Dashboard**  
Top-level overview of platform activity and navigation.

![Admin Dashboard](assets/admin-dashboard.png)

**Admin Control Panel**  
Central management area for operational actions.

![Admin Control Panel](assets/admin-control-panel.png)

**Leads Management**  
Admin tracking for lead pipeline and conversion state.

![Leads Management](assets/leads-management.png)

**Admin Analytics**  
User activity and engagement metrics for decision support.

![Admin Analytics](assets/admin-analytics-page.png)

**Admin Ticket Management**  
Support queue control and resolution monitoring.

![Admin Ticket Management](assets/admin-ticket-management.png)

### 5) Content and Communication Layer

**Create Post (Step 1)**  
Initial stage of content creation in admin blog workflow.

![Create Post Step 1](assets/create-post-step-1.png)

**Create Post (Step 2)**  
Completion stage before publication/update.

![Create Post Step 2](assets/create-post-step-2.png)

**Post Management**  
Editorial list and update controls for published content.

![Admin Post Management](assets/admin-post-management.png)

**Email Template Preview**  
Transactional email style used in account and workflow notifications.

![Email Template Preview](assets/email-template-preview.png)

### 6) Additional UI States and Workflow Screens

**Admin Appointment Check**  
Admin-side review state for appointment processing.

![Admin Appointment Check](assets/admin-appointment-check.png)

**Admin Created New Service**  
Operational screen after creating a new service offering.

![Admin Created New Service](assets/admin-created-new-service.png)

**Post Management (Alternative State)**  
Alternative content state in blog management flow.

![Admin Post Management Alternative](assets/admin-post-management-alt.png)

**Appointment Confirmation**  
Confirmation state shown after appointment-related action.

![Appointment Confirmation](assets/appointment-confirmation.png)

**Comment System**  
User interaction layer for content engagement.

![Comment System](assets/comment-system.png)

**Consultancy Page Details**  
Detailed consultancy/service explanation page.

![Consultancy Page Details](assets/consultancy-page-details.png)

**Dynamic Notification**  
In-app notification behavior example.

![Dynamic Notification](assets/dynamic-notification.png)

**Footer Section**  
Global footer area and informational links block.

![Footer Section](assets/footer-section.png)

**New Service Requires Initial Email Confirmation**  
State where email confirmation is required before service progression.

![New Service Requires Initial Email Confirmation](assets/new-service-requires-initial-email-confirmation.png)

**Single Service Application Submitted**  
Submission state for single-service application flow.

![Single Service Application Submitted](assets/single-service-application-submitted.png)

**Subscription Alert**  
Subscription feedback/alert interface example.

![Subscription Alert](assets/subscription-alert.png)

---

## Email Templates

Email templates are generated in:
- `SANALMUHASEBECIM/utils.py`

Main template workflows:
- account confirmation email
- password reset email
- payment info email

---

## Contact

- Name: Fuat Şimşek
- Email: fuatsiimsek@gmail.com
- LinkedIn: [linkedin.com/in/fuatsimsek](https://linkedin.com/in/fuatsims)

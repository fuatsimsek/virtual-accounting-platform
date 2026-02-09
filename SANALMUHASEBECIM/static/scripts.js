/*!
* Start Bootstrap - Clean Blog v6.0.9 (https://startbootstrap.com/theme/clean-blog)
* Copyright 2013-2023 Start Bootstrap
* Licensed under MIT (https://github.com/StartBootstrap/startbootstrap-clean-blog/blob/master/LICENSE)
*/

// Utility functions
const showNotification = (message, type = 'success', duration = 3000) => {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
            <span>${message}</span>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    // Animate in
    setTimeout(() => notification.classList.add('show'), 100);
    
    // Auto remove
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 300);
    }, duration);
};

const setLoadingState = (button, isLoading, originalText) => {
    if (isLoading) {
        button.disabled = true;
        button.innerHTML = `
            <div class="loading-spinner">
                <div class="spinner"></div>
            </div>
            <span>Gönderiliyor...</span>
        `;
    } else {
        button.disabled = false;
        button.innerHTML = originalText;
    }
};

window.addEventListener('DOMContentLoaded', () => {
    let scrollPos = 0;
    const mainNav = document.getElementById('mainNav');
    const headerHeight = mainNav.clientHeight;
    
    window.addEventListener('scroll', function() {
        const currentTop = document.body.getBoundingClientRect().top * -1;
        if ( currentTop < scrollPos) {
            // Scrolling Up
            if (currentTop > 0 && mainNav.classList.contains('is-fixed')) {
                mainNav.classList.add('is-visible');
            } else {
                mainNav.classList.remove('is-visible', 'is-fixed');
            }
        } else {
            // Scrolling Down
            mainNav.classList.remove(['is-visible']);
            if (currentTop > headerHeight && !mainNav.classList.contains('is-fixed')) {
                mainNav.classList.add('is-fixed');
            }
        }
        scrollPos = currentTop;
    });

    // Enhanced Post Like System
    const likeButtons = document.querySelectorAll('.btn-like');
    likeButtons.forEach(button => {
        button.addEventListener('click', function() {
            const postId = this.dataset.postId;
            const likeCount = this.querySelector('.like-count');
            const likeText = this.querySelector('.like-text');
            const heartIcon = this.querySelector('.like-icon i');
            
            // Add click animation
            this.classList.add('clicking');
            setTimeout(() => this.classList.remove('clicking'), 200);
            
            fetch(`/blog/like_post/${postId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || ''
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Smooth count animation
                    const currentCount = parseInt(likeCount.textContent);
                    const targetCount = data.likes;
                    animateCount(likeCount, currentCount, targetCount);
                    
                    if (data.liked) {
                        this.classList.add('liked');
                        likeText.textContent = 'Beğenildi';
                        heartIcon.classList.add('heart-beat');
                        setTimeout(() => heartIcon.classList.remove('heart-beat'), 600);
                        showNotification('Gönderi beğenildi!', 'success', 2000);
                    } else {
                        this.classList.remove('liked');
                        likeText.textContent = 'Beğen';
                        showNotification('Beğeni kaldırıldı', 'info', 2000);
                    }
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showNotification('Bir hata oluştu', 'error');
            });
        });
    });

    // Enhanced Comment Like System
    const commentLikeButtons = document.querySelectorAll('.like-comment');
    commentLikeButtons.forEach(button => {
        button.addEventListener('click', function() {
            const commentId = this.dataset.commentId;
            const likeCount = this.querySelector('.like-count');
            const heartIcon = this.querySelector('i');
            
            // Add click animation
            this.classList.add('clicking');
            setTimeout(() => this.classList.remove('clicking'), 200);
            
            fetch(`/blog/like_comment/${commentId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || ''
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Smooth count animation
                    const currentCount = parseInt(likeCount.textContent);
                    const targetCount = data.likes;
                    animateCount(likeCount, currentCount, targetCount);
                    
                    if (data.liked) {
                        this.classList.add('liked');
                        heartIcon.classList.add('heart-beat');
                        setTimeout(() => heartIcon.classList.remove('heart-beat'), 600);
                        showNotification('Yorum beğenildi!', 'success', 2000);
                    } else {
                        this.classList.remove('liked');
                        showNotification('Beğeni kaldırıldı', 'info', 2000);
                    }
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showNotification('Bir hata oluştu', 'error');
            });
        });
    });

    // Enhanced Comment Form Submission
    const commentForm = document.querySelector('.comment-form');
    if (commentForm) {
        commentForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const submitButton = this.querySelector('.btn-submit');
            const originalButtonText = submitButton.innerHTML;
            const textarea = this.querySelector('.comment-input');
            const content = textarea.value.trim();
            
            if (!content) {
                showNotification('Lütfen bir yorum yazın', 'error');
                textarea.focus();
                return;
            }
            
            // Set loading state
            setLoadingState(submitButton, true, originalButtonText);
            
            // Get form data
            const formData = new FormData(this);
            
            fetch(this.action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || ''
                }
            })
            .then(response => {
                if (response.redirected) {
                    window.location.href = response.url;
                    return;
                }
                return response.text();
            })
            .then(html => {
                if (html) {
                    // Check if there's a success message in the response
                    const parser = new DOMParser();
                    const doc = parser.parseFromString(html, 'text/html');
                    const alerts = doc.querySelectorAll('.alert');
                    
                    if (alerts.length > 0) {
                        alerts.forEach(alert => {
                            const message = alert.textContent.trim();
                            const isSuccess = alert.classList.contains('alert-success') || alert.classList.contains('alert-info');
                            showNotification(message, isSuccess ? 'success' : 'error');
                        });
                    }
                    
                    // Clear form and reload comments
                    textarea.value = '';
                    setTimeout(() => {
                        location.reload();
                    }, 1500);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showNotification('Yorum gönderilirken bir hata oluştu', 'error');
            })
            .finally(() => {
                setLoadingState(submitButton, false, originalButtonText);
            });
        });
    }

    // Enhanced Comment Reply System
    const replyButtons = document.querySelectorAll('.reply-comment');
    replyButtons.forEach(button => {
        button.addEventListener('click', function() {
            const commentId = this.dataset.commentId;
            const replyForm = document.getElementById(`reply-form-${commentId}`);
            
            // Smooth toggle animation
            if (replyForm.style.display === 'none' || !replyForm.style.display) {
                replyForm.style.display = 'block';
                replyForm.style.opacity = '0';
                replyForm.style.transform = 'translateY(-10px)';
                
                setTimeout(() => {
                    replyForm.style.opacity = '1';
                    replyForm.style.transform = 'translateY(0)';
                }, 10);
                
                replyForm.querySelector('textarea').focus();
            } else {
                replyForm.style.opacity = '0';
                replyForm.style.transform = 'translateY(-10px)';
                
                setTimeout(() => {
                    replyForm.style.display = 'none';
                }, 300);
            }
        });
    });

    const cancelReplyButtons = document.querySelectorAll('.cancel-reply');
    cancelReplyButtons.forEach(button => {
        button.addEventListener('click', function() {
            const commentId = this.dataset.commentId;
            const replyForm = document.getElementById(`reply-form-${commentId}`);
            
            replyForm.style.opacity = '0';
            replyForm.style.transform = 'translateY(-10px)';
            
            setTimeout(() => {
                replyForm.style.display = 'none';
                replyForm.querySelector('textarea').value = '';
            }, 300);
        });
    });

    const submitReplyButtons = document.querySelectorAll('.submit-reply');
    submitReplyButtons.forEach(button => {
        button.addEventListener('click', function() {
            const commentId = this.dataset.commentId;
            const replyForm = document.getElementById(`reply-form-${commentId}`);
            const textarea = replyForm.querySelector('textarea');
            const content = textarea.value.trim();
            const originalButtonText = this.innerHTML;
            
            if (!content) {
                showNotification('Lütfen bir yanıt yazın', 'error');
                textarea.focus();
                return;
            }
            
            // Set loading state
            setLoadingState(this, true, originalButtonText);
            
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
            
            fetch(`/blog/reply_comment/${commentId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ content: content })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showNotification(data.message, 'success');
                    
                    // Clear form and hide
                    textarea.value = '';
                    replyForm.style.opacity = '0';
                    replyForm.style.transform = 'translateY(-10px)';
                    
                    setTimeout(() => {
                        replyForm.style.display = 'none';
                        location.reload();
                    }, 1500);
                } else {
                    showNotification(data.message || 'Yanıt gönderilirken bir hata oluştu', 'error');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showNotification('Yanıt gönderilirken bir hata oluştu', 'error');
            })
            .finally(() => {
                setLoadingState(this, false, originalButtonText);
            });
        });
    });

    // Post Delete Confirmation
    const deleteBtn = document.getElementById('deleteBtn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', function() {
            if (confirm('Bu gönderiyi silmek istediğinizden emin misiniz? Bu işlem geri alınamaz.')) {
                document.getElementById('deleteForm').submit();
            }
        });
    }

    // Smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // Auto-hide alerts after 5 seconds (skip sticky alerts)
    const alerts = document.querySelectorAll('.alert:not(.alert-sticky)');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });
});

// Animation functions
const animateCount = (element, start, end) => {
    const duration = 500;
    const startTime = performance.now();
    
    const updateCount = (currentTime) => {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        const current = Math.floor(start + (end - start) * progress);
        element.textContent = current;
        
        if (progress < 1) {
            requestAnimationFrame(updateCount);
        }
    };
    
    requestAnimationFrame(updateCount);
};

// Add CSS for animations
const style = document.createElement('style');
style.textContent = `
    /* Notification System */
    .notification {
        position: fixed;
        top: 20px;
        right: 20px;
        background: white;
        border-radius: 10px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
        padding: 1rem 1.5rem;
        z-index: 9999;
        transform: translateX(100%);
        transition: transform 0.3s ease;
        border-left: 4px solid #667eea;
    }
    
    .notification.show {
        transform: translateX(0);
    }
    
    .notification-content {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        font-weight: 500;
    }
    
    .notification-success {
        border-left-color: #48bb78;
    }
    
    .notification-error {
        border-left-color: #e53e3e;
    }
    
    .notification-info {
        border-left-color: #667eea;
    }
    
    /* Loading Spinner */
    .loading-spinner {
        display: inline-flex;
        align-items: center;
        margin-right: 0.5rem;
    }
    
    .spinner {
        width: 16px;
        height: 16px;
        border: 2px solid transparent;
        border-top: 2px solid currentColor;
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }
    
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    
    /* Button Animations */
    .btn-like.clicking,
    .like-comment.clicking {
        transform: scale(0.95);
        transition: transform 0.1s ease;
    }
    
    .heart-beat {
        animation: heartBeat 0.6s ease;
    }
    
    @keyframes heartBeat {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.3); }
    }
    
    /* Reply Form Animations */
    .reply-form {
        transition: opacity 0.3s ease, transform 0.3s ease;
    }
    
    /* Enhanced Like Button States */
    .btn-like.liked {
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        border-color: #667eea;
        transform: scale(1.05);
        transition: all 0.3s ease;
    }
    
    .like-comment.liked {
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        border-color: #667eea;
    }
    
    /* Smooth transitions for all interactive elements */
    .btn-like,
    .like-comment,
    .btn-submit,
    .btn-action {
        transition: all 0.3s ease;
    }
    
    .btn-like:hover,
    .like-comment:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(102, 126, 234, 0.3);
    }
`;
document.head.appendChild(style);

// Modern loading animation
window.addEventListener('load', function() {
    document.body.classList.add('loaded');
});

// FAQ Functionality
document.addEventListener('DOMContentLoaded', function() {
    // Admin dashboard stat counters
    document.querySelectorAll('.stat-value[data-count]').forEach(el => {
        const target = parseInt(el.getAttribute('data-count') || '0', 10);
        let current = 0;
        const inc = Math.max(1, Math.floor(target / 40));
        const timer = setInterval(() => {
            current += inc;
            if (current >= target) { current = target; clearInterval(timer); }
            el.textContent = String(current);
        }, 25);
        el.parentElement?.parentElement?.addEventListener('mousemove', (e) => {
            const card = el.closest('.stat-card');
            if (card) {
                const rect = card.getBoundingClientRect();
                card.style.setProperty('--mx', `${((e.clientX - rect.left)/rect.width)*100}%`);
            }
        });
    });
    // Admin users quick filter
    const userFilter = document.getElementById('userFilter');
    const usersTable = document.getElementById('usersTable');
    if (userFilter && usersTable) {
        userFilter.addEventListener('input', () => {
            const q = userFilter.value.toLowerCase();
            usersTable.querySelectorAll('tbody tr').forEach(tr => {
                const text = tr.textContent.toLowerCase();
                tr.style.display = text.includes(q) ? '' : 'none';
            });
        });
    }

    // Admin comments filter
    const commentFilter = document.getElementById('commentFilter');
    const commentsTable = document.getElementById('commentsTable');
    if (commentFilter && commentsTable) {
        commentFilter.addEventListener('input', () => {
            const q = commentFilter.value.toLowerCase();
            commentsTable.querySelectorAll('tbody tr').forEach(tr => {
                const text = tr.textContent.toLowerCase();
                tr.style.display = text.includes(q) ? '' : 'none';
            });
        });
    }

    // Admin posts filter
    const postFilter = document.getElementById('postFilter');
    const postsTable = document.getElementById('postsTable');
    if (postFilter && postsTable) {
        postFilter.addEventListener('input', () => {
            const q = postFilter.value.toLowerCase();
            postsTable.querySelectorAll('tbody tr').forEach(tr => {
                const text = tr.textContent.toLowerCase();
                tr.style.display = text.includes(q) ? '' : 'none';
            });
        });
    }
    const faqItems = document.querySelectorAll('.faq-item');
    
    faqItems.forEach(item => {
        const question = item.querySelector('.faq-question');
        
        question.addEventListener('click', function() {
            const isActive = item.classList.contains('active');
            
            // Close all other FAQ items
            faqItems.forEach(otherItem => {
                otherItem.classList.remove('active');
            });
            
            // Toggle current item
            if (!isActive) {
                item.classList.add('active');
            }
        });
    });
});

// Enhanced Booking Page Interactions
document.addEventListener('DOMContentLoaded', function() {
    // Process step animations
    const processSteps = document.querySelectorAll('.process-step');
    
    const observerOptions = {
        threshold: 0.3,
        rootMargin: '0px 0px -50px 0px'
    };
    
    const stepObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);
    
    processSteps.forEach((step, index) => {
        step.style.opacity = '0';
        step.style.transform = 'translateY(30px)';
        step.style.transition = `all 0.6s ease ${index * 0.2}s`;
        stepObserver.observe(step);
    });
    
    // Service card hover effects
    const serviceCards = document.querySelectorAll('.service-card');
    
    serviceCards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-10px) scale(1.02)';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0) scale(1)';
        });
    });
    
    // Testimonial card animations
    const testimonialCards = document.querySelectorAll('.testimonial-card');
    
    testimonialCards.forEach((card, index) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = `all 0.6s ease ${index * 0.1}s`;
        
        setTimeout(() => {
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, 500 + (index * 100));
    });
    
    // Hero stats counter animation
    const statNumbers = document.querySelectorAll('.stat-number');
    
    const animateCounter = (element, target) => {
        // normalize target
        if (!Number.isFinite(target)) {
            target = 0;
        }
        let current = 0;
        const increment = Math.max(1, Math.floor(target / 50));
        const original = element.textContent.trim();
        const hasPlus = /\+$/.test(original) || target >= 10; // show + for big numbers
        const isSupport = /Hızlı|Kısa|Destek/i.test(original) || /Destek/i.test(element.nextElementSibling?.textContent || '');
        const isCustomers = /500\+/.test(original) || target >= 100;
        const timer = setInterval(() => {
            current += increment;
            if (current >= target) {
                current = target;
                clearInterval(timer);
            }
            let suffix = '';
            if (isCustomers || hasPlus) {
                suffix = '+';
            }
            element.textContent = String(Math.floor(current)) + suffix;
        }, 30);
    };
    
    const statsObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const target = entry.target;
                const text = target.textContent;
                const numMatch = text.match(/\d+/);
                if (!numMatch) {
                    // Non-numeric label (e.g., Hızlı). Do not animate.
                    statsObserver.unobserve(target);
                    return;
                }
                let number = parseInt(numMatch[0], 10);
                if (text.includes('500')) number = 500;
                if (text.includes('20')) number = 20;
                
                animateCounter(target, number);
                statsObserver.unobserve(target);
            }
        });
    }, { threshold: 0.5 });
    
    statNumbers.forEach(stat => {
        statsObserver.observe(stat);
    });
    
    // Floating elements parallax effect
    const floatingIcons = document.querySelectorAll('.floating-icon');
    
    window.addEventListener('scroll', () => {
        const scrolled = window.pageYOffset;
        
        floatingIcons.forEach(icon => {
            const speed = icon.getAttribute('data-speed') || 1;
            const yPos = -(scrolled * speed * 0.5);
            icon.style.transform = `translateY(${yPos}px) rotate(${scrolled * 0.1}deg)`;
        });
    });
    
    // Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
    
    // Enhanced button hover effects
    const heroButtons = document.querySelectorAll('.btn-hero-modern');
    
    heroButtons.forEach(button => {
        button.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-4px) scale(1.05)';
            this.style.boxShadow = '0 20px 40px rgba(102, 126, 234, 0.4)';
        });
        
        button.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0) scale(1)';
            this.style.boxShadow = '0 8px 30px rgba(102, 126, 234, 0.3)';
        });
    });
    
    // Trust badges animation
    const trustBadges = document.querySelectorAll('.trust-badge');
    
    trustBadges.forEach((badge, index) => {
        badge.style.opacity = '0';
        badge.style.transform = 'translateY(20px)';
        badge.style.transition = `all 0.6s ease ${index * 0.2}s`;
        
        setTimeout(() => {
            badge.style.opacity = '1';
            badge.style.transform = 'translateY(0)';
        }, 1000 + (index * 200));
    });
    
    // Booking card pulse animation
    const bookingCard = document.querySelector('.booking-card');
    if (bookingCard) {
        setInterval(() => {
            bookingCard.style.transform = 'scale(1.02)';
            setTimeout(() => {
                bookingCard.style.transform = 'scale(1)';
            }, 200);
        }, 3000);
    }
});

// Enhanced Booking Form Functionality
document.addEventListener('DOMContentLoaded', function() {
    // Copy link functionality
    const copyButtons = document.querySelectorAll('.copy-link-btn');
    copyButtons.forEach(button => {
        button.addEventListener('click', function() {
            const link = this.getAttribute('data-link');
            navigator.clipboard.writeText(link).then(() => {
                const originalText = this.innerHTML;
                this.innerHTML = '<i class="fas fa-check"></i> Kopyalandı';
                this.style.background = 'linear-gradient(135deg, #10b981, #059669)';
                this.style.color = 'white';
                this.style.borderColor = '#10b981';
                
                setTimeout(() => {
                    this.innerHTML = originalText;
                    this.style.background = '';
                    this.style.color = '';
                    this.style.borderColor = '';
                }, 2000);
            });
        });
    });
    const bookingForm = document.getElementById('bookingForm');
    const submitBtn = document.getElementById('submitBtn');
    
    if (bookingForm) {
        // Form validation and enhancement
        const formInputs = bookingForm.querySelectorAll('.form-control.enhanced');
        
        formInputs.forEach(input => {
            // Add focus effects
            input.addEventListener('focus', function() {
                this.parentElement.classList.add('focused');
            });
            
            input.addEventListener('blur', function() {
                this.parentElement.classList.remove('focused');
                validateField(this);
            });
            
            // Real-time validation
            input.addEventListener('input', function() {
                validateField(this);
            });
        });
        
        // Form submission: let server handle and show flash + redirect
        bookingForm.addEventListener('submit', function(e) {
            if (!validateForm()) {
                e.preventDefault();
            }
        });
        
        // Date and time validation
        const dateInput = bookingForm.querySelector('input[type="date"]');
        const timeInput = bookingForm.querySelector('input[type="time"]');
        
        if (dateInput) {
            // Set minimum date to 2 days from today (yarına alamazsın kuralı)
            const today = new Date();
            const minDate = new Date(today);
            minDate.setDate(today.getDate() + 2); // En az 2 gün sonrası
            const minDateString = minDate.toISOString().split('T')[0];
            dateInput.setAttribute('min', minDateString);
            
            dateInput.addEventListener('change', function() {
                validateDateTime();
                // Fetch availability for the selected date
                const val = this.value;
                if (!val) return;
                fetch(`/booking/availability?date=${val}`)
                  .then(r => r.json())
                  .then(data => {
                      const timeInput = bookingForm.querySelector('input[type="time"]');
                      if (!timeInput) return;
                      const wrapper = timeInput.closest('.input-group') || timeInput.parentElement;
                      // Show taken badge next to time input
                      let badge = wrapper.querySelector('.taken-badge');
                      if (!badge) {
                          badge = document.createElement('div');
                          badge.className = 'taken-badge';
                          badge.style.cssText = 'margin-top:6px;color:#ef4444;font-size:12px;';
                          wrapper.appendChild(badge);
                      }
                      // If the UI has a list of preset time buttons, disable taken ones
                      const presetButtons = bookingForm.querySelectorAll('[data-time-slot]');
                      presetButtons.forEach(btn => {
                          const slot = btn.getAttribute('data-time-slot');
                          if (data.times.includes(slot)) {
                              btn.classList.add('disabled');
                              btn.setAttribute('aria-disabled', 'true');
                              btn.innerHTML = `<span style="margin-right:6px">✕</span>${slot}`;
                          } else {
                              btn.classList.remove('disabled');
                              btn.removeAttribute('aria-disabled');
                              btn.textContent = slot;
                          }
                      });
                      if (data.times.length > 0) {
                          badge.textContent = `Dolu saatler: ${data.times.join(', ')}`;
                          // If selected time is taken, clear it
                          if (data.times.includes(timeInput.value)) {
                              timeInput.value = '';
                          }
                      } else {
                          badge.textContent = '';
                      }
                  })
                  .catch(() => {});
            });
        }
        
        if (timeInput) {
            timeInput.addEventListener('change', function() {
                validateDateTime();
            });
        }
        
        // Character counter for textarea
        const textarea = bookingForm.querySelector('textarea');
        if (textarea) {
            const charCounter = document.createElement('div');
            charCounter.className = 'char-counter';
            charCounter.style.cssText = 'text-align: right; font-size: 0.8rem; color: #64748b; margin-top: 0.5rem;';
            textarea.parentElement.appendChild(charCounter);
            
            textarea.addEventListener('input', function() {
                const maxLength = 1000;
                const currentLength = this.value.length;
                charCounter.textContent = `${currentLength}/${maxLength}`;
                
                if (currentLength > maxLength * 0.9) {
                    charCounter.style.color = '#ef4444';
                } else {
                    charCounter.style.color = '#64748b';
                }
            });
        }
    }
    
    // Validation functions
    function validateField(field) {
        const wrapper = field.parentElement;
        const errorElement = wrapper.parentElement.querySelector('.error-message');
        
        // Remove existing error styling
        wrapper.classList.remove('error');
        
        let isValid = true;
        let errorMessage = '';
        
        // Email validation
        if (field.type === 'email') {
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(field.value)) {
                isValid = false;
                errorMessage = 'Geçerli bir e-posta adresi giriniz';
            }
        }
        
        // Required field validation
        if (field.hasAttribute('required') && !field.value.trim()) {
            isValid = false;
            errorMessage = 'Bu alan zorunludur';
        }
        
        // Date validation
        if (field.type === 'date') {
            const selectedDate = new Date(field.value);
            const today = new Date();
            const minDate = new Date(today);
            minDate.setDate(today.getDate() + 2); // En az 2 gün sonrası
            minDate.setHours(0, 0, 0, 0);
            
            if (selectedDate < minDate) {
                isValid = false;
                errorMessage = 'En az 2 gün sonrası için randevu alabilirsiniz';
            }
        }
        
        // Time validation
        if (field.type === 'time') {
            const selectedTime = field.value;
            const [hours, minutes] = selectedTime.split(':').map(Number);
            
            if (hours < 9 || hours > 18) {
                isValid = false;
                errorMessage = 'Görüşme saatleri 09:00-18:00 arasındadır';
            }
        }
        
        // Apply validation result
        if (!isValid) {
            wrapper.classList.add('error');
            if (errorElement) {
                errorElement.textContent = errorMessage;
                errorElement.style.display = 'flex';
            }
        } else {
            if (errorElement) {
                errorElement.style.display = 'none';
            }
        }
        
        return isValid;
    }
    
    function validateDateTime() {
        const dateInput = bookingForm.querySelector('input[type="date"]');
        const timeInput = bookingForm.querySelector('input[type="time"]');
        
        if (dateInput && timeInput && dateInput.value && timeInput.value) {
            const selectedDateTime = new Date(`${dateInput.value}T${timeInput.value}`);
            const now = new Date();
            const minDateTime = new Date(now);
            minDateTime.setDate(now.getDate() + 2); // En az 2 gün sonrası
            
            if (selectedDateTime <= minDateTime) {
                showNotification('En az 2 gün sonrası için randevu alabilirsiniz', 'error');
                timeInput.value = '';
            }
        }
    }
    
    function validateForm() {
        let isValid = true;
        const formInputs = bookingForm.querySelectorAll('.form-control.enhanced');
        
        formInputs.forEach(input => {
            if (!validateField(input)) {
                isValid = false;
            }
        });
        
        return isValid;
    }
    
    function setLoadingState(button, isLoading) {
        if (isLoading) {
            button.disabled = true;
            button.innerHTML = `
                <i class="fas fa-spinner fa-spin"></i>
                <span>Gönderiliyor...</span>
            `;
        } else {
            button.disabled = false;
            button.innerHTML = `
                <i class="fas fa-calendar-check"></i>
                <span>Ön Görüşme Planla</span>
                <i class="fas fa-arrow-right"></i>
            `;
        }
    }
    
    function showSuccessMessage() {
        // Scroll to success preview section
        const successSection = document.querySelector('.success-preview');
        if (successSection) {
            successSection.scrollIntoView({ behavior: 'smooth' });
        }
        
        // Show notification
        showNotification('Randevunuz başarıyla alındı! E-posta adresinizi kontrol edin.', 'success');
        
        // Update progress indicator
        updateProgress(2);
    }
    
    function updateProgress(step) {
        const progressSteps = document.querySelectorAll('.progress-step');
        
        progressSteps.forEach((stepElement, index) => {
            if (index < step) {
                stepElement.classList.add('active');
            } else {
                stepElement.classList.remove('active');
            }
        });
    }
    
    // Auto-fill current user email if available
    const emailInput = bookingForm?.querySelector('input[type="email"]');
    if (emailInput && window.currentUserEmail) {
        emailInput.value = window.currentUserEmail;
    }
    
    // Form field animations
    const formSections = document.querySelectorAll('.form-section');
    
    const formObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, { threshold: 0.3 });
    
    formSections.forEach((section, index) => {
        section.style.opacity = '0';
        section.style.transform = 'translateY(30px)';
        section.style.transition = `all 0.6s ease ${index * 0.2}s`;
        formObserver.observe(section);
    });
    
    // Sidebar animations
    const sidebarCards = document.querySelectorAll('.sidebar-card');
    
    sidebarCards.forEach((card, index) => {
        card.style.opacity = '0';
        card.style.transform = 'translateX(30px)';
        card.style.transition = `all 0.6s ease ${index * 0.3}s`;
        
        setTimeout(() => {
            card.style.opacity = '1';
            card.style.transform = 'translateX(0)';
        }, 500 + (index * 300));
    });
    
    // Info item hover effects
    const infoItems = document.querySelectorAll('.info-item');
    
    infoItems.forEach(item => {
        item.addEventListener('mouseenter', function() {
            this.style.transform = 'translateX(10px) scale(1.02)';
        });
        
        item.addEventListener('mouseleave', function() {
            this.style.transform = 'translateX(0) scale(1)';
        });
    });
});

/**
 * Main JavaScript file for the catalog website
 */

document.addEventListener('DOMContentLoaded', function() {
    // Mobile menu
    initMobileMenu();
    
    // Lazy loading images
    initLazyLoading();
    
    // Smooth scroll
    initSmoothScroll();
    
    // Cart functionality
    initCart();
    updateCartCount();
    
    // Email selection
    initEmailSelection();
    
    // Mega menu (two-column categories menu)
    initMegaMenu();
    
    // Promotions carousel
    initPromotionsCarousel();
});

/**
 * Mobile menu functionality
 */
function initMobileMenu() {
    const burgerBtn = document.getElementById('burgerBtn');
    const mobileMenu = document.getElementById('mobileMenu');
    
    if (!burgerBtn || !mobileMenu) return;
    
    burgerBtn.addEventListener('click', function() {
        mobileMenu.classList.toggle('is-open');
        document.body.style.overflow = mobileMenu.classList.contains('is-open') ? 'hidden' : '';
        
        // Animate burger
        this.classList.toggle('is-active');
    });
    
    // Close menu on link click
    const menuLinks = mobileMenu.querySelectorAll('a');
    menuLinks.forEach(function(link) {
        link.addEventListener('click', function() {
            mobileMenu.classList.remove('is-open');
            document.body.style.overflow = '';
            burgerBtn.classList.remove('is-active');
        });
    });
    
    // Close on escape
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && mobileMenu.classList.contains('is-open')) {
            mobileMenu.classList.remove('is-open');
            document.body.style.overflow = '';
            burgerBtn.classList.remove('is-active');
        }
    });
}

/**
 * Lazy loading for images
 */
function initLazyLoading() {
    if ('loading' in HTMLImageElement.prototype) {
        // Native lazy loading supported
        const images = document.querySelectorAll('img[loading="lazy"]');
        images.forEach(function(img) {
            if (img.dataset.src) {
                img.src = img.dataset.src;
            }
        });
    } else {
        // Fallback for older browsers
        const lazyImages = document.querySelectorAll('img[loading="lazy"]');
        
        if ('IntersectionObserver' in window) {
            const imageObserver = new IntersectionObserver(function(entries, observer) {
                entries.forEach(function(entry) {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        if (img.dataset.src) {
                            img.src = img.dataset.src;
                        }
                        img.classList.add('loaded');
                        observer.unobserve(img);
                    }
                });
            });
            
            lazyImages.forEach(function(img) {
                imageObserver.observe(img);
            });
        }
    }
}

/**
 * Smooth scroll for anchor links
 */
function initSmoothScroll() {
    const links = document.querySelectorAll('a[href^="#"]');
    
    links.forEach(function(link) {
        link.addEventListener('click', function(e) {
            const targetId = this.getAttribute('href');
            if (targetId === '#') return;
            
            const target = document.querySelector(targetId);
            if (target) {
                e.preventDefault();
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
}

/**
 * AJAX filter for catalog
 */
function filterProducts(page) {
    const form = document.getElementById('filterForm');
    const productsGrid = document.getElementById('productsGrid');
    
    if (!form || !productsGrid) return;
    
    const formData = new FormData(form);
    if (page) {
        formData.set('page', page);
    }
    
    const params = new URLSearchParams(formData);
    
    // Show loading
    productsGrid.style.opacity = '0.5';
    
    fetch('/catalog/filter/?' + params.toString(), {
        method: 'GET',
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(function(response) {
        return response.json();
    })
    .then(function(data) {
        productsGrid.innerHTML = data.html;
        
        const paginationContainer = document.querySelector('.pagination');
        if (paginationContainer) {
            paginationContainer.outerHTML = data.pagination;
        }
        
        // Update count
        const countEl = document.querySelector('.catalog-count strong');
        if (countEl) {
            countEl.textContent = data.count;
        }
        
        productsGrid.style.opacity = '1';
        
        // Update URL
        const newUrl = window.location.pathname + '?' + params.toString();
        window.history.pushState({}, '', newUrl);
    })
    .catch(function(error) {
        console.error('Filter error:', error);
        productsGrid.style.opacity = '1';
    });
}

/**
 * Debounce function for search input
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = function() {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Format price with thousands separator
 */
function formatPrice(price) {
    return new Intl.NumberFormat('ru-RU').format(price);
}

/**
 * Cart functionality
 */
function initCart() {
    // Добавление в корзину
    document.querySelectorAll('.btn-add-cart, .product-card__add-cart').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            const productId = this.dataset.productId;
            addToCart(productId);
        });
    });
}

function addToCart(productId) {
    fetch('/orders/cart/add/' + productId + '/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'X-Requested-With': 'XMLHttpRequest',
        },
    })
    .then(function(response) {
        return response.json();
    })
    .then(function(data) {
        if (data.success) {
            // Обновляем счётчик
            const cartCountEl = document.getElementById('cartCount');
            if (cartCountEl) {
                const currentCount = parseInt(cartCountEl.textContent || '0');
                const newCount = data.cart_count || (currentCount + 1);
                cartCountEl.textContent = newCount;
                cartCountEl.style.display = 'block';
                localStorage.setItem('cartCount', newCount.toString());
            }
            showNotification(data.message || 'Товар добавлен в корзину', 'success');
        }
    })
    .catch(function(error) {
        console.error('Cart error:', error);
        showNotification('Ошибка при добавлении в корзину', 'error');
    });
}

function updateCartCount() {
    fetch('/orders/cart/count/', {
        method: 'GET',
    })
    .then(function(response) {
        return response.json();
    })
    .then(function(data) {
        const cartCountEl = document.getElementById('cartCount');
        if (cartCountEl) {
            const count = data.count || 0;
            if (count > 0) {
                cartCountEl.textContent = count;
                cartCountEl.style.display = 'block';
            } else {
                cartCountEl.style.display = 'none';
            }
        }
    })
    .catch(function() {
        // При ошибке скрываем счётчик
        const cartCountEl = document.getElementById('cartCount');
        if (cartCountEl) {
            cartCountEl.style.display = 'none';
        }
    });
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

/**
 * Email selection and mail service opening
 */
function initEmailSelection() {
    // Находим все ссылки с классом email-link или data-email
    const emailLinks = document.querySelectorAll('a[href^="mailto:"], a.email-link, a[data-email]');
    
    emailLinks.forEach(function(link) {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const email = this.getAttribute('href')?.replace('mailto:', '') || 
                         this.getAttribute('data-email') || 
                         this.textContent.trim();
            openEmailComposer(email);
        });
    });
}

/**
 * Открывает форму отправки письма на соответствующем почтовом сервисе
 */
function openEmailComposer(email) {
    if (!email) return;
    
    // Получаем список email адресов из данных страницы
    const emailsData = window.SITE_EMAILS || [];
    
    // Если есть несколько email адресов, показываем выбор
    if (emailsData && emailsData.length > 1) {
        showEmailSelector(emailsData);
    } else {
        // Если только один email или нет данных, используем переданный email
        const targetEmail = (emailsData && emailsData.length > 0) ? emailsData[0].email : email;
        openMailService(targetEmail);
    }
}

/**
 * Показывает модальное окно выбора email
 */
function showEmailSelector(emails) {
    // Создаем модальное окно
    const modal = document.createElement('div');
    modal.className = 'email-selector-modal';
    modal.innerHTML = `
        <div class="email-selector-modal__overlay"></div>
        <div class="email-selector-modal__content">
            <div class="email-selector-modal__header">
                <h3>Выберите email для отправки письма</h3>
                <button class="email-selector-modal__close" aria-label="Закрыть">&times;</button>
            </div>
            <div class="email-selector-modal__list">
                ${emails.map(function(item) {
                    const email = item.email || item;
                    const label = item.label || item.email || item;
                    return `
                        <button class="email-selector-modal__item" data-email="${email}">
                            <i class="bi bi-envelope"></i>
                            <span>${label}</span>
                        </button>
                    `;
                }).join('')}
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Показываем модальное окно
    setTimeout(function() {
        modal.classList.add('is-visible');
    }, 10);
    
    // Обработчики событий
    const closeBtn = modal.querySelector('.email-selector-modal__close');
    const overlay = modal.querySelector('.email-selector-modal__overlay');
    const items = modal.querySelectorAll('.email-selector-modal__item');
    
    function closeModal() {
        modal.classList.remove('is-visible');
        setTimeout(function() {
            modal.remove();
        }, 300);
    }
    
    closeBtn.addEventListener('click', closeModal);
    overlay.addEventListener('click', closeModal);
    
    items.forEach(function(item) {
        item.addEventListener('click', function() {
            const selectedEmail = this.getAttribute('data-email');
            closeModal();
            openMailService(selectedEmail);
        });
    });
    
    // Закрытие по Escape
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && modal.classList.contains('is-visible')) {
            closeModal();
        }
    });
}

/**
 * Открывает форму отправки письма на соответствующем почтовом сервисе
 */
function openMailService(email) {
    if (!email) return;
    
    // Определяем почтовый сервис по домену
    const domain = email.split('@')[1]?.toLowerCase();
    
    let mailUrl = '';
    
    if (domain === 'mail.ru' || domain === 'inbox.ru' || domain === 'list.ru' || domain === 'bk.ru') {
        // Mail.ru
        mailUrl = `https://e.mail.ru/compose/?to=${encodeURIComponent(email)}`;
    } else if (domain === 'gmail.com' || domain === 'googlemail.com') {
        // Gmail
        mailUrl = `https://mail.google.com/mail/?view=cm&to=${encodeURIComponent(email)}`;
    } else if (domain === 'yandex.ru' || domain === 'ya.ru' || domain === 'yandex.com') {
        // Yandex Mail
        mailUrl = `https://mail.yandex.ru/compose?to=${encodeURIComponent(email)}`;
    } else if (domain === 'outlook.com' || domain === 'hotmail.com' || domain === 'live.com' || domain === 'msn.com') {
        // Outlook
        mailUrl = `https://outlook.live.com/mail/0/deeplink/compose?to=${encodeURIComponent(email)}`;
    } else if (domain === 'icloud.com' || domain === 'me.com' || domain === 'mac.com') {
        // iCloud Mail
        mailUrl = `https://www.icloud.com/mail/compose?to=${encodeURIComponent(email)}`;
    } else {
        // Для остальных используем стандартный mailto
        mailUrl = `mailto:${email}`;
    }
    
    // Открываем в новой вкладке
    window.open(mailUrl, '_blank');
}

/**
 * Show notification
 */
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = 'notification notification--' + type;
    notification.innerHTML = `
        <span>${message}</span>
        <button class="notification__close">&times;</button>
    `;
    
    document.body.appendChild(notification);
    
    // Show with animation
    setTimeout(function() {
        notification.classList.add('is-visible');
    }, 10);
    
    // Auto hide
    setTimeout(function() {
        notification.classList.remove('is-visible');
        setTimeout(function() {
            notification.remove();
        }, 300);
    }, 5000);
    
    // Close on click
    notification.querySelector('.notification__close').addEventListener('click', function() {
        notification.classList.remove('is-visible');
        setTimeout(function() {
            notification.remove();
        }, 300);
    });
}

/**
 * Mega menu (two-column categories menu) functionality
 */
function initMegaMenu() {
    const megaMenu = document.querySelector('.mega-menu');
    if (!megaMenu) return;
    
    const categories = megaMenu.querySelectorAll('.mega-menu__category');
    const subcategoryGroups = megaMenu.querySelectorAll('.mega-menu__subcategory-group');
    
    categories.forEach(function(category) {
        category.addEventListener('mouseenter', function() {
            const categoryId = this.getAttribute('data-category-id');
            
            // Убираем активный класс у всех категорий
            categories.forEach(function(cat) {
                cat.classList.remove('is-active');
            });
            
            // Добавляем активный класс текущей категории
            this.classList.add('is-active');
            
            // Скрываем все группы подкатегорий
            subcategoryGroups.forEach(function(group) {
                group.classList.remove('is-active');
            });
            
            // Показываем группу подкатегорий для текущей категории
            const targetGroup = megaMenu.querySelector(`.mega-menu__subcategory-group[data-category-id="${categoryId}"]`);
            if (targetGroup) {
                targetGroup.classList.add('is-active');
            }
        });
    });
}

/**
 * Promotions carousel functionality
 */
let promotionsCarouselInitialized = false;

function initPromotionsCarousel() {
    // Защита от повторной инициализации
    if (promotionsCarouselInitialized) {
        return;
    }
    
    const carousel = document.querySelector('.promotions-carousel');
    if (!carousel) return;
    
    const slides = carousel.querySelectorAll('.promotions-carousel__slide');
    const indicators = carousel.querySelectorAll('.promotions-carousel__indicator');
    const prevBtn = carousel.querySelector('.promotions-carousel__btn--prev');
    const nextBtn = carousel.querySelector('.promotions-carousel__btn--next');
    
    if (slides.length <= 1) return;
    
    // Помечаем как инициализированную
    promotionsCarouselInitialized = true;
    
    // Определяем текущий активный слайд из HTML (который уже помечен как is-active)
    let currentSlide = 0;
    slides.forEach(function(slide, index) {
        if (slide.classList.contains('is-active')) {
            currentSlide = index;
        }
    });
    
    // Убеждаемся, что только один слайд активен (синхронизируем состояние)
    slides.forEach(function(slide, index) {
        if (index === currentSlide) {
            slide.classList.add('is-active');
        } else {
            slide.classList.remove('is-active');
        }
    });
    indicators.forEach(function(indicator, index) {
        if (index === currentSlide) {
            indicator.classList.add('is-active');
        } else {
            indicator.classList.remove('is-active');
        }
    });
    
    let autoplayInterval = null;
    const AUTOPLAY_DELAY = 5000; // Строго 5 секунд (5000 миллисекунд)
    let isAutoplayActive = false;
    
    // Функция для переключения слайда
    function showSlide(index) {
        // Убираем активный класс у всех слайдов и индикаторов
        slides.forEach(function(slide) {
            slide.classList.remove('is-active');
        });
        indicators.forEach(function(indicator) {
            indicator.classList.remove('is-active');
        });
        
        // Добавляем активный класс текущему слайду и индикатору
        if (slides[index]) {
            slides[index].classList.add('is-active');
        }
        if (indicators[index]) {
            indicators[index].classList.add('is-active');
        }
        
        currentSlide = index;
    }
    
    // Функция для следующего слайда
    function nextSlide() {
        const next = (currentSlide + 1) % slides.length;
        showSlide(next);
    }
    
    // Функция для предыдущего слайда
    function prevSlide() {
        const prev = (currentSlide - 1 + slides.length) % slides.length;
        showSlide(prev);
    }
    
    // Автопрокрутка - строго контролируем интервал
    function startAutoplay() {
        // Всегда останавливаем предыдущий интервал перед созданием нового
        stopAutoplay();
        
        // Создаем новый интервал строго на 5 секунд
        autoplayInterval = setInterval(function() {
            nextSlide();
        }, AUTOPLAY_DELAY);
        
        isAutoplayActive = true;
    }
    
    function stopAutoplay() {
        if (autoplayInterval !== null) {
            clearInterval(autoplayInterval);
            autoplayInterval = null;
        }
        isAutoplayActive = false;
    }
    
    function resetAutoplay() {
        // Полностью останавливаем и перезапускаем с нуля
        stopAutoplay();
        // Небольшая задержка перед перезапуском для корректного сброса
        setTimeout(function() {
            if (!isAutoplayActive) {
                startAutoplay();
            }
        }, 100);
    }
    
    // Обработчики для кнопок
    if (nextBtn) {
        nextBtn.addEventListener('click', function() {
            nextSlide();
            resetAutoplay();
        });
    }
    
    if (prevBtn) {
        prevBtn.addEventListener('click', function() {
            prevSlide();
            resetAutoplay();
        });
    }
    
    // Обработчики для индикаторов
    indicators.forEach(function(indicator, index) {
        indicator.addEventListener('click', function() {
            showSlide(index);
            resetAutoplay();
        });
    });
    
    // Останавливаем автопрокрутку при наведении
    carousel.addEventListener('mouseenter', function() {
        stopAutoplay();
    });
    
    carousel.addEventListener('mouseleave', function() {
        if (!isAutoplayActive) {
            startAutoplay();
        }
    });
    
    // Запускаем автопрокрутку с небольшой задержкой после загрузки
    setTimeout(function() {
        startAutoplay();
    }, 500);
    
    // Обработка свайпов на мобильных устройствах
    let touchStartX = 0;
    let touchEndX = 0;
    
    carousel.addEventListener('touchstart', function(e) {
        touchStartX = e.changedTouches[0].screenX;
    }, { passive: true });
    
    carousel.addEventListener('touchend', function(e) {
        touchEndX = e.changedTouches[0].screenX;
        handleSwipe();
    }, { passive: true });
    
    function handleSwipe() {
        const swipeThreshold = 50;
        const diff = touchStartX - touchEndX;
        
        if (Math.abs(diff) > swipeThreshold) {
            if (diff > 0) {
                // Свайп влево - следующий слайд
                nextSlide();
            } else {
                // Свайп вправо - предыдущий слайд
                prevSlide();
            }
            resetAutoplay();
        }
    }
}

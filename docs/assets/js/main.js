/**
 * REAG Fraud Investigation Toolkit
 * Main JavaScript File
 */

// DOM Elements
const navToggle = document.getElementById('navToggle');
const navMenu = document.getElementById('navMenu');
const backToTop = document.getElementById('backToTop');
const navbar = document.getElementById('navbar');

// Mobile Navigation Toggle
if (navToggle && navMenu) {
    navToggle.addEventListener('click', () => {
        navMenu.classList.toggle('active');
        navToggle.classList.toggle('active');
    });

    // Close menu when clicking on a link
    const navLinks = navMenu.querySelectorAll('a');
    navLinks.forEach(link => {
        link.addEventListener('click', () => {
            navMenu.classList.remove('active');
            navToggle.classList.remove('active');
        });
    });

    // Close menu when clicking outside
    document.addEventListener('click', (e) => {
        if (!navMenu.contains(e.target) && !navToggle.contains(e.target)) {
            navMenu.classList.remove('active');
            navToggle.classList.remove('active');
        }
    });
}

// Back to Top Button
if (backToTop) {
    window.addEventListener('scroll', () => {
        if (window.pageYOffset > 300) {
            backToTop.classList.add('show');
        } else {
            backToTop.classList.remove('show');
        }
    });

    backToTop.addEventListener('click', () => {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    });
}

// Smooth Scrolling for Anchor Links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        const href = this.getAttribute('href');
        if (href !== '#' && href !== '') {
            e.preventDefault();
            const target = document.querySelector(href);
            if (target) {
                const navbarHeight = navbar ? navbar.offsetHeight : 70;
                const targetPosition = target.offsetTop - navbarHeight;
                window.scrollTo({
                    top: targetPosition,
                    behavior: 'smooth'
                });
            }
        }
    });
});

// Active Navigation Link on Scroll
const sections = document.querySelectorAll('section[id]');
const navLinks = document.querySelectorAll('.nav-menu a[href^="#"]');

function setActiveNav() {
    const scrollY = window.pageYOffset;

    sections.forEach(section => {
        const sectionHeight = section.offsetHeight;
        const sectionTop = section.offsetTop - 100;
        const sectionId = section.getAttribute('id');

        if (scrollY > sectionTop && scrollY <= sectionTop + sectionHeight) {
            navLinks.forEach(link => {
                link.classList.remove('active');
                if (link.getAttribute('href') === `#${sectionId}`) {
                    link.classList.add('active');
                }
            });
        }
    });
}

if (sections.length > 0 && navLinks.length > 0) {
    window.addEventListener('scroll', setActiveNav);
}

// Intersection Observer for Fade-in Animations
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
        }
    });
}, observerOptions);

// Observe cards and method items for animations
document.querySelectorAll('.card, .method-item, .feature-item, .impact-card').forEach(el => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(20px)';
    el.style.transition = 'opacity 0.6s ease-out, transform 0.6s ease-out';
    observer.observe(el);
});

// Copy Code to Clipboard
function createCopyButtons() {
    const codeBlocks = document.querySelectorAll('pre code');

    codeBlocks.forEach((codeBlock) => {
        const pre = codeBlock.parentElement;
        const button = document.createElement('button');
        button.className = 'copy-code-btn';
        button.innerHTML = '<i class="fas fa-copy"></i>';
        button.title = 'Copiar código';

        pre.style.position = 'relative';
        pre.appendChild(button);

        button.addEventListener('click', () => {
            const code = codeBlock.textContent;
            navigator.clipboard.writeText(code).then(() => {
                button.innerHTML = '<i class="fas fa-check"></i>';
                button.style.backgroundColor = 'var(--success-color)';

                setTimeout(() => {
                    button.innerHTML = '<i class="fas fa-copy"></i>';
                    button.style.backgroundColor = '';
                }, 2000);
            }).catch(err => {
                console.error('Failed to copy code:', err);
                button.innerHTML = '<i class="fas fa-times"></i>';
                button.style.backgroundColor = 'var(--danger-color)';

                setTimeout(() => {
                    button.innerHTML = '<i class="fas fa-copy"></i>';
                    button.style.backgroundColor = '';
                }, 2000);
            });
        });
    });
}

// Add copy buttons after DOM is loaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', createCopyButtons);
} else {
    createCopyButtons();
}

// Add CSS for copy button dynamically
const style = document.createElement('style');
style.textContent = `
    .copy-code-btn {
        position: absolute;
        top: 8px;
        right: 8px;
        padding: 6px 10px;
        background-color: rgba(255, 255, 255, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 4px;
        color: white;
        cursor: pointer;
        font-size: 14px;
        transition: all 0.2s ease;
        z-index: 10;
    }

    .copy-code-btn:hover {
        background-color: rgba(255, 255, 255, 0.2);
    }

    .copy-code-btn i {
        pointer-events: none;
    }
`;
document.head.appendChild(style);

// Stats Counter Animation
function animateCounter(element, target, duration = 2000) {
    const start = 0;
    const increment = target / (duration / 16);
    let current = start;

    const timer = setInterval(() => {
        current += increment;
        if (current >= target) {
            element.textContent = target;
            clearInterval(timer);
        } else {
            element.textContent = Math.floor(current);
        }
    }, 16);
}

// Animate stat numbers when they come into view
const statObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting && !entry.target.dataset.animated) {
            const text = entry.target.textContent.trim();
            const number = parseInt(text.replace(/\D/g, ''));

            if (number && !isNaN(number)) {
                entry.target.dataset.animated = 'true';
                entry.target.textContent = '0';

                setTimeout(() => {
                    animateCounter(entry.target, number);
                }, 200);
            }
        }
    });
}, { threshold: 0.5 });

document.querySelectorAll('.stat-number').forEach(stat => {
    // Only animate if it contains a number
    if (/\d/.test(stat.textContent)) {
        statObserver.observe(stat);
    }
});

// Search Functionality (for documentation pages)
function initSearch() {
    const searchInput = document.getElementById('searchInput');
    const searchResults = document.getElementById('searchResults');

    if (!searchInput || !searchResults) return;

    let searchData = [];

    // Build search index from page content
    const sections = document.querySelectorAll('section[id], article[id]');
    sections.forEach(section => {
        const id = section.getAttribute('id');
        const title = section.querySelector('h1, h2, h3')?.textContent || '';
        const content = section.textContent || '';

        if (id && title) {
            searchData.push({
                id,
                title,
                content: content.toLowerCase(),
                url: `#${id}`
            });
        }
    });

    // Search function
    function performSearch(query) {
        if (!query || query.length < 2) {
            searchResults.innerHTML = '';
            searchResults.style.display = 'none';
            return;
        }

        const lowerQuery = query.toLowerCase();
        const results = searchData.filter(item =>
            item.title.toLowerCase().includes(lowerQuery) ||
            item.content.includes(lowerQuery)
        ).slice(0, 5);

        if (results.length === 0) {
            searchResults.innerHTML = '<div class="search-no-results">Nenhum resultado encontrado</div>';
            searchResults.style.display = 'block';
            return;
        }

        searchResults.innerHTML = results.map(result => `
            <a href="${result.url}" class="search-result-item">
                <strong>${highlightMatch(result.title, query)}</strong>
            </a>
        `).join('');
        searchResults.style.display = 'block';
    }

    function highlightMatch(text, query) {
        const regex = new RegExp(`(${query})`, 'gi');
        return text.replace(regex, '<mark>$1</mark>');
    }

    // Event listeners
    searchInput.addEventListener('input', (e) => {
        performSearch(e.target.value);
    });

    // Close search results when clicking outside
    document.addEventListener('click', (e) => {
        if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
            searchResults.style.display = 'none';
        }
    });
}

initSearch();

// Load external charts library if needed
function loadChartsLibrary() {
    if (document.querySelector('[data-chart]')) {
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js';
        script.onload = () => {
            console.log('Chart.js loaded');
            initCharts();
        };
        document.head.appendChild(script);
    }
}

function initCharts() {
    // Initialize charts if Chart.js is available
    if (typeof Chart === 'undefined') return;

    // This will be expanded in charts.js
    console.log('Charts initialized');
}

// Call on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadChartsLibrary);
} else {
    loadChartsLibrary();
}

// Accessibility: Skip to main content
const skipLink = document.createElement('a');
skipLink.href = '#main';
skipLink.className = 'skip-link';
skipLink.textContent = 'Pular para o conteúdo principal';
document.body.insertBefore(skipLink, document.body.firstChild);

const skipStyle = document.createElement('style');
skipStyle.textContent = `
    .skip-link {
        position: absolute;
        top: -40px;
        left: 0;
        background: var(--primary-color);
        color: white;
        padding: 8px 16px;
        text-decoration: none;
        z-index: 10000;
    }

    .skip-link:focus {
        top: 0;
    }
`;
document.head.appendChild(skipStyle);

// Keyboard navigation improvements
document.addEventListener('keydown', (e) => {
    // ESC to close mobile menu
    if (e.key === 'Escape' && navMenu && navMenu.classList.contains('active')) {
        navMenu.classList.remove('active');
        navToggle.classList.remove('active');
    }
});

// Performance: Lazy load images
function lazyLoadImages() {
    const images = document.querySelectorAll('img[data-src]');

    const imageObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                img.src = img.dataset.src;
                img.removeAttribute('data-src');
                imageObserver.unobserve(img);
            }
        });
    });

    images.forEach(img => imageObserver.observe(img));
}

lazyLoadImages();

// Console message
console.log('%c🔍 REAG Fraud Investigation Toolkit', 'font-size: 20px; font-weight: bold; color: #1e3a8a;');
console.log('%cOpen Source • Educational Purpose • MIT License', 'font-size: 12px; color: #6b7280;');
console.log('%cGitHub: https://github.com/PedroDnT/REAG', 'font-size: 12px; color: #3b82f6;');

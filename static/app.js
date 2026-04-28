(() => {
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    function animateCounter(element) {
        if (!element || element.dataset.counterDone === 'true') {
            return;
        }

        const rawValue = element.dataset.count;
        if (rawValue === undefined) {
            return;
        }

        const targetValue = Number(rawValue);
        if (Number.isNaN(targetValue)) {
            return;
        }

        const initialText = (element.textContent || '').trim();
        const isCurrency = initialText.startsWith('$') || element.dataset.format === 'currency';
        const formatter = isCurrency
            ? new Intl.NumberFormat(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
            : new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });

        element.dataset.counterDone = 'true';

        if (reduceMotion) {
            element.textContent = formatter.format(targetValue);
            return;
        }

        const duration = 900;
        const startTime = performance.now();
        const startValue = 0;

        function frame(now) {
            const progress = Math.min((now - startTime) / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            const currentValue = Math.round(startValue + (targetValue - startValue) * eased);
            element.textContent = formatter.format(currentValue);
            if (progress < 1) {
                window.requestAnimationFrame(frame);
            }
        }

        window.requestAnimationFrame(frame);
    }

    function revealElements() {
        const revealNodes = Array.from(document.querySelectorAll('.reveal, .glass-panel, .premium-panel'));
        if (!revealNodes.length) {
            return;
        }

        revealNodes.forEach((node, index) => {
            node.style.setProperty('--reveal-delay', `${Math.min(index * 60, 420)}ms`);
            node.classList.add('is-ready');
        });
    }

    function setupCounters() {
        document.querySelectorAll('[data-count]').forEach(animateCounter);
    }

    function setupStaggerGroups() {
        document.querySelectorAll('.stagger-grid, .premium-job-list').forEach((container) => {
            const items = Array.from(container.children || []);
            items.forEach((item, index) => {
                item.style.setProperty('--item-delay', `${index * 70}ms`);
            });
        });
    }

    function setupButtons() {
        document.querySelectorAll('.button, .icon-button, .nav-link, .quick-filter, .profile-trigger').forEach((node) => {
            node.addEventListener('pointerenter', () => node.classList.add('is-hovered'));
            node.addEventListener('pointerleave', () => node.classList.remove('is-hovered'));
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        revealElements();
        setupCounters();
        setupStaggerGroups();
        setupButtons();
    });
})();

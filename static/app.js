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

    function setupServiceChipSelectors() {
        document.querySelectorAll('[data-service-chip-selector]').forEach((container) => {
            const inputs = Array.from(container.querySelectorAll('input[type="checkbox"][name="service_type"]'));
            if (!inputs.length) {
                return;
            }

            const previewId = container.dataset.previewId;
            const preview = previewId ? document.getElementById(previewId) : null;
            const otherValue = container.dataset.otherValue || 'Other';
            const otherWrapperId = container.dataset.otherWrapperId;
            const otherInputId = container.dataset.otherInputId;
            const otherWrapper = otherWrapperId ? document.getElementById(otherWrapperId) : null;
            const otherInput = otherInputId ? document.getElementById(otherInputId) : null;

            const updateState = () => {
                const selectedInputs = inputs.filter((input) => input.checked);
                const selectedValues = selectedInputs.map((input) => input.value);

                if (preview) {
                    preview.innerHTML = '';
                    selectedValues.forEach((value) => {
                        const chip = document.createElement('button');
                        chip.type = 'button';
                        chip.className = 'service-chip-selected';
                        chip.textContent = `${value} ×`;
                        chip.addEventListener('click', () => {
                            const matchedInput = inputs.find((input) => input.value === value);
                            if (matchedInput) {
                                matchedInput.checked = false;
                                matchedInput.dispatchEvent(new Event('change', { bubbles: true }));
                            }
                        });
                        preview.appendChild(chip);
                    });
                }

                const showOther = selectedValues.includes(otherValue);
                if (otherWrapper) {
                    otherWrapper.hidden = !showOther;
                }
                if (otherInput) {
                    if (!showOther) {
                        otherInput.value = '';
                    }
                }
            };

            inputs.forEach((input) => {
                input.addEventListener('change', updateState);
            });
            updateState();
        });
    }

    function setupIcons() {
        if (window.lucide && typeof window.lucide.createIcons === 'function') {
            window.lucide.createIcons();
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        revealElements();
        setupCounters();
        setupStaggerGroups();
        setupButtons();
        setupServiceChipSelectors();
        setupIcons();
    });
})();

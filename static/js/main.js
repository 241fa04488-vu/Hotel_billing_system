// JavaScript Core for Premium Hotel Billing System

document.addEventListener('DOMContentLoaded', () => {
    // 1. Theme Toggle System
    const themeToggleBtn = document.getElementById('theme-toggle');
    const themeIcon = document.getElementById('theme-icon');
    
    // Check local storage or system preferences
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);

    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            updateThemeIcon(newTheme);
        });
    }

    function updateThemeIcon(theme) {
        if (!themeIcon) return;
        if (theme === 'dark') {
            // Sun icon for switching to light mode
            themeIcon.innerHTML = `<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.364 17.636l-.707.707M6.364 6.364l.707.707m12.728 12.728l.707.707M12 8a4 4 0 100 8 4 4 0 000-8z" />`;
        } else {
            // Moon icon for switching to dark mode
            themeIcon.innerHTML = `<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />`;
        }
    }

    // 2. Room Management Drawer
    const btnOpenDrawer = document.getElementById('btn-open-drawer');
    const btnCloseDrawer = document.getElementById('btn-close-drawer');
    const addRoomDrawer = document.getElementById('add-room-drawer');

    if (btnOpenDrawer && addRoomDrawer) {
        btnOpenDrawer.addEventListener('click', () => {
            addRoomDrawer.style.display = 'flex';
        });
    }

    if (btnCloseDrawer && addRoomDrawer) {
        btnCloseDrawer.addEventListener('click', () => {
            addRoomDrawer.style.display = 'none';
        });
        
        // Close on clicking outside the drawer
        addRoomDrawer.addEventListener('click', (e) => {
            if (e.target === addRoomDrawer) {
                addRoomDrawer.style.display = 'none';
            }
        });
    }

    // 3. Dynamic Live Invoice Calculator
    initInvoiceCalculator();

    // 4. Play notification sound on successful room booking or check-in
    const successMessages = document.querySelectorAll('.messages-container .badge-success span');
    let triggerChime = false;
    successMessages.forEach(msg => {
        const text = msg.textContent.toLowerCase();
        if (text.includes('booked successfully') || text.includes('created successfully')) {
            triggerChime = true;
        }
    });
    if (triggerChime) {
        playSuccessChime();
    }

    // 5. Play notification sound when clicking any "Print Receipt" button/link
    document.addEventListener('click', (e) => {
        const target = e.target.closest('a, button');
        if (target) {
            const text = target.textContent.toLowerCase();
            const href = target.getAttribute('href') || '';
            if (text.includes('print receipt') || href.includes('/print/')) {
                playSuccessChime();
            }
        }
    });
});

function initInvoiceCalculator() {
    const checkInInput = document.getElementById('check_in_date');
    const checkOutInput = document.getElementById('check_out_date');
    const roomSelect = document.getElementById('room_select');
    const roomPriceDisplay = document.getElementById('room_price_per_night');
    const nightsDisplay = document.getElementById('stay_nights');
    
    // Total fields
    const roomChargesInput = document.getElementById('calc_room_charges');
    const extraChargesInput = document.getElementById('calc_extra_charges');
    const discountInput = document.getElementById('discount_input');
    const taxRateInput = document.getElementById('tax_rate_input');
    
    const summaryRoomCharges = document.getElementById('summary_room_charges');
    const summaryExtraCharges = document.getElementById('summary_extra_charges');
    const summaryTaxAmount = document.getElementById('summary_tax_amount');
    const summaryTotalAmount = document.getElementById('summary_total_amount');
    
    const addItemBtn = document.getElementById('btn-add-item');
    const itemsTableBody = document.getElementById('invoice-items-body');

    if (!checkInInput || !checkOutInput) return; // Not on the invoice form page

    // Listeners for stay recalculation
    checkInInput.addEventListener('change', calculateNightsAndRoomCharges);
    checkOutInput.addEventListener('change', calculateNightsAndRoomCharges);
    roomSelect.addEventListener('change', (e) => {
        const selectedOption = e.target.options[e.target.selectedIndex];
        const price = selectedOption.getAttribute('data-price') || 0.00;
        if (roomPriceDisplay) {
            roomPriceDisplay.textContent = parseFloat(price).toFixed(2);
        }
        calculateNightsAndRoomCharges();
    });

    if (discountInput) discountInput.addEventListener('input', calculateInvoiceTotals);
    if (taxRateInput) taxRateInput.addEventListener('input', calculateInvoiceTotals);

    // Dynamic Items addition
    if (addItemBtn && itemsTableBody) {
        addItemBtn.addEventListener('click', () => {
            const rowId = 'row-' + Date.now();
            const tr = document.createElement('tr');
            tr.id = rowId;
            tr.className = 'item-row';
            
            tr.innerHTML = `
                <td>
                    <input type="text" name="item_description[]" placeholder="e.g. Room Service, Laundry" required>
                </td>
                <td style="width: 150px;">
                    <input type="number" name="item_amount[]" class="item-amount-input" placeholder="0.00" step="0.01" min="0" required>
                </td>
                <td style="width: 80px; text-align: center;">
                    <button type="button" class="btn btn-danger btn-delete-row" style="padding: 0.4rem 0.8rem;">
                        <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                    </button>
                </td>
            `;
            
            itemsTableBody.appendChild(tr);
            
            // Focus on new input
            tr.querySelector('input').focus();

            // Hook up delete listener
            tr.querySelector('.btn-delete-row').addEventListener('click', () => {
                tr.remove();
                calculateExtraCharges();
            });

            // Hook up amount change listener
            tr.querySelector('.item-amount-input').addEventListener('input', calculateExtraCharges);
        });
    }

    function calculateNightsAndRoomCharges() {
        const checkInVal = checkInInput.value;
        const checkOutVal = checkOutInput.value;
        
        if (checkInVal && checkOutVal) {
            const date1 = new Date(checkInVal);
            const date2 = new Date(checkOutVal);
            
            // Calculate difference in milliseconds
            const diffTime = date2 - date1;
            // Calculate nights
            let nights = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
            
            if (nights <= 0) {
                nights = 1; // Minimum 1 night
            }
            
            if (nightsDisplay) nightsDisplay.textContent = nights;

            const selectedOption = roomSelect.options[roomSelect.selectedIndex];
            const price = parseFloat(selectedOption.getAttribute('data-price') || 0.00);
            
            const roomCharges = price * nights;
            if (roomChargesInput) roomChargesInput.value = roomCharges.toFixed(2);
            if (summaryRoomCharges) summaryRoomCharges.textContent = roomCharges.toFixed(2);
            
            calculateInvoiceTotals();
        }
    }

    function calculateExtraCharges() {
        let extraTotal = 0;
        const amountInputs = document.querySelectorAll('.item-amount-input');
        
        amountInputs.forEach(input => {
            const val = parseFloat(input.value) || 0;
            extraTotal += val;
        });
        
        if (extraChargesInput) extraChargesInput.value = extraTotal.toFixed(2);
        if (summaryExtraCharges) summaryExtraCharges.textContent = extraTotal.toFixed(2);
        
        calculateInvoiceTotals();
    }

    function calculateInvoiceTotals() {
        const roomCharges = parseFloat(roomChargesInput ? roomChargesInput.value : 0) || 0;
        const extraCharges = parseFloat(extraChargesInput ? extraChargesInput.value : 0) || 0;
        const discount = parseFloat(discountInput ? discountInput.value : 0) || 0;
        const taxRate = parseFloat(taxRateInput ? taxRateInput.value : 12) || 0;
        
        const subtotal = (roomCharges + extraCharges) - discount;
        const taxAmount = subtotal * (taxRate / 100);
        const grandTotal = subtotal + taxAmount;
        
        if (summaryTaxAmount) summaryTaxAmount.textContent = taxAmount.toFixed(2);
        if (summaryTotalAmount) summaryTotalAmount.textContent = grandTotal.toFixed(2);
    }
}

function playSuccessChime() {
    try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        
        const playTone = (freq, startTime, duration) => {
            const osc = audioCtx.createOscillator();
            const gainNode = audioCtx.createGain();
            
            osc.type = 'sine';
            osc.frequency.setValueAtTime(freq, startTime);
            
            // Soft envelope: attack, sustain, decay
            gainNode.gain.setValueAtTime(0, startTime);
            gainNode.gain.linearRampToValueAtTime(0.15, startTime + 0.04);
            gainNode.gain.exponentialRampToValueAtTime(0.001, startTime + duration);
            
            osc.connect(gainNode);
            gainNode.connect(audioCtx.destination);
            
            osc.start(startTime);
            osc.stop(startTime + duration);
        };
        
        const now = audioCtx.currentTime;
        // Luxury triad arpeggio: E5 -> A5 -> C#6
        playTone(659.25, now, 0.4);       // E5
        playTone(880.00, now + 0.1, 0.4); // A5
        playTone(1108.73, now + 0.2, 0.5); // C#6
    } catch (e) {
        console.warn("Web Audio API notification chime blocked or unsupported:", e);
    }
}

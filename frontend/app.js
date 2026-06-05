const API_BASE_URL = (
    window.location.protocol === 'file:' || 
    window.location.hostname === 'localhost' || 
    window.location.hostname === '127.0.0.1' || 
    window.location.hostname === ''
) ? 'http://localhost:5000/api' : '/api';

const AUTH_TOKEN_KEY = 'pathradar_auth_token';
/** Session IDs from analyses not yet linked to an account (survives refresh; claimed on login/init). */
const PENDING_CLAIM_KEY = 'pathradar_pending_claim_sessions';

function addPendingClaimSession(sessionId) {
    if (sessionId == null || sessionId === '') return;
    const id = Number(sessionId);
    if (!Number.isFinite(id)) return;
    let ids = [];
    try {
        ids = JSON.parse(localStorage.getItem(PENDING_CLAIM_KEY) || '[]');
    } catch { /* ignore */ }
    if (!Array.isArray(ids)) ids = [];
    ids.push(id);
    const uniq = [...new Set(ids.map(Number).filter(Number.isFinite))].slice(-25);
    localStorage.setItem(PENDING_CLAIM_KEY, JSON.stringify(uniq));
}

/** Try to link pending analyses to the current account (Bearer token must already be in storage). */
async function claimAllPendingSessions() {
    let ids = [];
    try {
        ids = JSON.parse(localStorage.getItem(PENDING_CLAIM_KEY) || '[]');
    } catch { /* ignore */ }
    if (!Array.isArray(ids) || !ids.length) return;
    const remaining = [];
    for (const raw of ids) {
        const sid = Number(raw);
        if (!Number.isFinite(sid)) continue;
        try {
            const res = await apiFetch(`${API_BASE_URL}/claim-session`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: sid }),
            });
            if (!res.ok) remaining.push(sid);
        } catch (e) {
            console.error('Claim failed for session', sid, e);
            remaining.push(sid);
        }
    }
    if (remaining.length) localStorage.setItem(PENDING_CLAIM_KEY, JSON.stringify(remaining));
    else localStorage.removeItem(PENDING_CLAIM_KEY);
}

/** Adds Bearer token when present so history works even if session cookies are not sent (cross-origin). */
function apiFetch(input, init = {}) {
    const opt = { credentials: 'include', ...init };
    const headers = new Headers(opt.headers || {});
    const t = localStorage.getItem(AUTH_TOKEN_KEY);
    if (t) headers.set('Authorization', `Bearer ${t}`);
    opt.headers = headers;
    return fetch(input, opt);
}



// Global store to avoid embedding JSON in HTML attributes (fixes the broken button bug)
const roleStore = new Map();
const learnedSkills = new Set();
let currentBaseScore = 0;
let lastSessionId = null; // Track most recent analysis session ID
let skillChart = null; // Global reference for Chart.js
let _progressTimers = []; // Track all progress simulation timers

// =========================================================
// AUTH MANAGER
// =========================================================
const AuthManager = {
    user: null,

    async init() {
        try {
            const res = await apiFetch(`${API_BASE_URL}/user`);
            const data = await res.json();
            if (res.ok && data.status === 'success') {
                this.user = data.user;
                this.updateUI();
                await claimAllPendingSessions();
            } else if (res.status === 401 || (data && data.status === 'guest')) {
                localStorage.removeItem(AUTH_TOKEN_KEY);
            }
        } catch (err) {
            console.error('Auth Init Error:', err);
        }
    },

    updateUI() {
        const navAuth = document.getElementById('nav-auth');
        const navUser = document.getElementById('nav-user');
        const userEmail = document.getElementById('user-email-display');
        const userInitials = document.getElementById('user-initials');
        const btnSaveAccount = document.getElementById('btn-save-account');

        if (this.user) {
            if (navAuth) navAuth.classList.add('hidden');
            if (navUser) navUser.classList.remove('hidden');
            if (userEmail) userEmail.textContent = this.user.email;
            if (userInitials) {
                const name = this.user.full_name || this.user.email;
                userInitials.textContent = name.substring(0, 2).toUpperCase();
            }
            if (btnSaveAccount) btnSaveAccount.classList.add('hidden');
        } else {
            if (navAuth) navAuth.classList.remove('hidden');
            if (navUser) navUser.classList.add('hidden');
        }
    },

    async login(email, password) {
        const res = await apiFetch(`${API_BASE_URL}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
        });
        const data = await res.json();
        if (res.ok) {
            if (data.token) localStorage.setItem(AUTH_TOKEN_KEY, data.token);
            this.user = data.user;
            this.updateUI();
            if (lastSessionId != null) addPendingClaimSession(lastSessionId);
            await claimAllPendingSessions();
            lastSessionId = null;
            return { success: true };
        }
        return { success: false, error: data.error };
    },

    async signup(full_name, email, password) {
        const res = await apiFetch(`${API_BASE_URL}/signup`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ full_name, email, password }),
        });
        const data = await res.json();
        if (res.ok) {
            return { success: true };
        }
        return { success: false, error: data.error };
    },

    async logout() {
        try {
            await apiFetch(`${API_BASE_URL}/logout`, { method: 'POST' });
        } catch (err) {
            console.error('Logout request failed:', err);
        } finally {
            localStorage.removeItem(AUTH_TOKEN_KEY);
            this.user = null;
            this.updateUI();
            window.location.href = `${window.location.pathname}#landing`;
            window.location.reload(); // Reset state
        }
    }
};

// =========================================================
// PROGRESS SIMULATION
// =========================================================
const PROGRESS_STEPS = [
    { pct: 10, title: '📄 Reading your resume...',           sub: 'Extracting text from your document' },
    { pct: 22, title: '🧠 Extracting your skills...',        sub: 'Running NLP analysis on your experience' },
    { pct: 36, title: '🔍 Detecting best-fit roles...',      sub: 'Mapping your skills to 500+ career paths' },
    { pct: 52, title: '🌐 Fetching live job listings...',    sub: 'Pulling real-time openings from LinkedIn & Indeed' },
    { pct: 66, title: '⚡ Running AI skill gap analysis...', sub: 'Comparing your profile against job requirements' },
    { pct: 80, title: '📊 Scoring role compatibility...',    sub: 'Calculating match percentages for each role' },
    { pct: 92, title: '💾 Saving your results...',           sub: 'Storing analysis in your personal history' },
    { pct: 99, title: '✅ Almost done...',                   sub: 'Preparing your personalised dashboard' },
];

function startProgressSimulation() {
    _progressTimers.forEach(t => clearTimeout(t));
    _progressTimers = [];

    const fillEl  = document.getElementById('progress-bar-fill');
    const pctEl   = document.getElementById('progress-pct');
    const titleEl = document.getElementById('loading-text');
    const subEl   = document.getElementById('loading-sub');

    if (!fillEl) return;

    // Reset to first step immediately
    fillEl.style.width = `${PROGRESS_STEPS[0].pct}%`;
    if (pctEl)   pctEl.textContent   = `${PROGRESS_STEPS[0].pct}%`;
    if (titleEl) titleEl.textContent = PROGRESS_STEPS[0].title;
    if (subEl)   subEl.textContent   = PROGRESS_STEPS[0].sub;

    // Each step gets an equal slice of a 28-second window
    const stepInterval = 28000 / PROGRESS_STEPS.length;

    PROGRESS_STEPS.slice(1).forEach((step, i) => {
        const delay = (i + 1) * stepInterval;
        const t = setTimeout(() => {
            // Fade out → update → fade in
            if (titleEl) titleEl.style.opacity = '0';
            if (subEl)   subEl.style.opacity   = '0';

            setTimeout(() => {
                if (fillEl)  fillEl.style.width    = `${step.pct}%`;
                if (pctEl)   pctEl.textContent     = `${step.pct}%`;
                if (titleEl) { titleEl.textContent = step.title; titleEl.style.opacity = '1'; }
                if (subEl)   { subEl.textContent   = step.sub;   subEl.style.opacity   = '1'; }
            }, 200);
        }, delay);
        _progressTimers.push(t);
    });
}

function stopProgressSimulation() {
    _progressTimers.forEach(t => clearTimeout(t));
    _progressTimers = [];

    const fillEl  = document.getElementById('progress-bar-fill');
    const pctEl   = document.getElementById('progress-pct');
    const titleEl = document.getElementById('loading-text');
    const subEl   = document.getElementById('loading-sub');

    if (fillEl) fillEl.style.width = '100%';
    if (pctEl)  pctEl.textContent  = '100%';
    if (titleEl) titleEl.textContent = '🎉 Analysis Complete!';
    if (subEl)   subEl.textContent   = 'Loading your results...';
}

// =========================================================
// GLOBAL HELPERS
// =========================================================
window.redirectToYouTube = async (skill) => {
    const loadingOverlay = document.getElementById('loading-overlay');
    const loadingText = document.getElementById('loading-text');
    if (loadingOverlay && loadingText) {
        loadingText.textContent = `Finding video for ${skill}...`;
        loadingOverlay.classList.remove('hidden');
    }

    try {
        const res = await apiFetch(`${API_BASE_URL}/course-links?skill=${encodeURIComponent(skill)}&t=${Date.now()}`);
        const data = await res.json();
        if (res.ok && data.links && data.links.youtube_tutorials && data.links.youtube_tutorials.length > 0) {
            window.open(data.links.youtube_tutorials[0].url, '_blank');
        } else {
            window.open(`https://www.youtube.com/results?search_query=${encodeURIComponent(skill)}+tutorial`, '_blank');
        }
    } catch (err) {
        window.open(`https://www.youtube.com/results?search_query=${encodeURIComponent(skill)}+tutorial`, '_blank');
    } finally {
        if (loadingOverlay) loadingOverlay.classList.add('hidden');
    }
};

function resetChart(id) {
    const img = document.getElementById(id);
    const ph = document.getElementById(`${id}-placeholder`);
    if (img && ph) {
        img.src = '';
        img.classList.add('hidden');
        ph.textContent = 'Generating chart...';
        ph.classList.remove('hidden');
    }
}

// Catch global errors to help debugging
window.addEventListener('error', (event) => {
    console.error('PathRadar Error:', event.message);
});

document.addEventListener('DOMContentLoaded', () => {

    // --- Elements ---
    const form = document.getElementById('analyze-form');
    const fileDropArea = document.getElementById('file-drop-area');
    const resumeInput = document.getElementById('resume');
    const fileMsg = document.querySelector('.file-msg');

    if (!form || !fileDropArea || !resumeInput) {
        alert('Critical UI Error: Could not find upload form elements. Check if index.html is modified.');
        return;
    }

    // ... rest of the code ...

    const submitBtn = document.getElementById('submit-btn');
    const submitSpinner = document.getElementById('submit-spinner');
    const loadingOverlay = document.getElementById('loading-overlay');
    const loadingText = document.getElementById('loading-text');

    const analyzerSection = document.getElementById('analyzer');
    const resultsSection = document.getElementById('results');
    const dashboardSection = document.getElementById('dashboard');

    const navDashboard = document.getElementById('nav-dashboard');

    const jobModal = document.getElementById('job-modal');
    const closeJobModalBtn = document.getElementById('close-job-modal');
    const roleModal = document.getElementById('role-modal');
    const closeRoleModalBtn = document.getElementById('close-role-modal');
    const skillModal = document.getElementById('skill-modal');
    const closeSkillModalBtn = document.getElementById('close-skill-modal');
    const imageModal = document.getElementById('image-modal');
    const closeImageModalBtn = document.getElementById('close-image-modal');
    const fullScreenImage = document.getElementById('full-screen-image');

    const authModal = document.getElementById('auth-modal');
    const btnLoginOpen = document.getElementById('btn-login-open');
    const closeAuthModalBtn = document.getElementById('close-auth-modal');
    const authTabs = document.querySelectorAll('.auth-tab');
    const loginForm = document.getElementById('login-form');
    const signupForm = document.getElementById('signup-form');
    const btnLogout = document.getElementById('btn-logout');
    const btnSaveAccount = document.getElementById('btn-save-account');

    // Multi-Screen Elements
    const landingScreen = document.getElementById('landing-screen');
    const accessScreen = document.getElementById('access-screen');
    const featuresScreen = document.getElementById('features-screen');
    const workspaceScreen = document.getElementById('workspace-screen');
    const btnGetStarted = document.getElementById('btn-get-started');
    const btnExploreFeatures = document.getElementById('btn-explore-features');
    const btnFeaturesBack = document.getElementById('btn-features-back');
    const btnGateLogin = document.getElementById('btn-gate-login');
    const btnGateGuest = document.getElementById('btn-gate-guest');
    const btnGateTriggers = document.querySelectorAll('.btn-gate-trigger');

    // Screen Management
    const ScreenManager = {
        current: 'landing',
        
        show(screenId, pushHistory = true) {
            if (landingScreen) landingScreen.classList.toggle('hidden', screenId !== 'landing');
            if (accessScreen) accessScreen.classList.toggle('hidden', screenId !== 'access');
            if (featuresScreen) featuresScreen.classList.toggle('hidden', screenId !== 'features');
            if (workspaceScreen) workspaceScreen.classList.toggle('hidden', screenId !== 'workspace');
            
            this.current = screenId;
            
            // SECURITY: Only block dashboard/history for non-logged-in users
            // Workspace and results are accessible to guests
            if (!AuthManager.user && screenId === 'dashboard') {
                console.log('Blocking guest access to dashboard');
                this.show('access', false);
                return;
            }

            this.updateNavbar();
            window.scrollTo({ top: 0, behavior: 'smooth' });

            if (pushHistory) {
                history.pushState({ screenId }, '', `#${screenId}`);
            }
        },

        updateNavbar() {
            const nav = document.querySelector('nav');
            const navDashboard = document.getElementById('nav-dashboard');
            
            if (this.current === 'landing' || this.current === 'access' || this.current === 'features') {
                if (nav) nav.classList.add('hidden');
            } else {
                if (nav) nav.classList.remove('hidden');
                // Hide history link for guests (or based on their category)
                if (navDashboard) {
                    if (!AuthManager.user) {
                        navDashboard.classList.add('hidden');
                    } else {
                        navDashboard.classList.remove('hidden');
                    }
                }
            }
        }
    };

    // Handle Browser Back/Forward
    window.addEventListener('popstate', (event) => {
        if (event.state && event.state.screenId) {
            ScreenManager.show(event.state.screenId, false);
        } else {
            ScreenManager.show('landing', false);
        }
    });

    // Initialize Auth
    AuthManager.init().then(() => {
        const hash = window.location.hash.replace('#', '') || null;
        if (AuthManager.user) {
            // Logged in: go to workspace unless a specific hash like #features is present
            if (!hash || hash === 'landing' || hash === 'access') {
                ScreenManager.show('workspace');
            } else {
                ScreenManager.show(hash);
            }
        } else {
            // Not logged in: Show landing page first (as requested)
            if (!hash || hash === 'landing' || hash === 'workspace' || hash === 'access') {
                ScreenManager.show('landing');
            } else {
                ScreenManager.show(hash);
            }
        }
    });

    // Landing Buttons
    if (btnGetStarted) {
        btnGetStarted.addEventListener('click', () => {
            ScreenManager.show('access'); // Go to the dedicated Auth Page
        });
    }

    if (btnExploreFeatures) {
        btnExploreFeatures.addEventListener('click', () => {
            ScreenManager.show('features');
        });
    }

    if (btnFeaturesBack) {
        btnFeaturesBack.addEventListener('click', () => {
            ScreenManager.show('landing');
        });
    }

    // Gate Buttons
    if (btnGateLogin) {
        btnGateLogin.addEventListener('click', () => {
            authModal.classList.remove('hidden');
        });
    }

    if (btnGateGuest) {
        btnGateGuest.addEventListener('click', () => {
            ScreenManager.show('workspace');
        });
    }

    btnGateTriggers.forEach(btn => {
        btn.addEventListener('click', () => {
            ScreenManager.show('access');
        });
    });

    // =========================================================
    // NAVIGATION
    // =========================================================
    const homeSelectors = ['#analyzer', '#features', '.benefits-section', '.how-it-works'];

    function setHomeVisibility(visible) {
        homeSelectors.forEach(selector => {
            const el = document.querySelector(selector);
            if (el) el.classList.toggle('hidden', !visible);
        });
    }

    if (navDashboard) {
        navDashboard.addEventListener('click', e => {
            e.preventDefault();
            setHomeVisibility(false);
            if (resultsSection) resultsSection.classList.add('hidden');
            if (dashboardSection) dashboardSection.classList.remove('hidden');
            loadDashboardHistory();
            document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
            navDashboard.classList.add('active');
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }

    const navAnLink = document.querySelector('a[href="#analyzer"]');
    if (navAnLink) {
        navAnLink.addEventListener('click', e => {
            e.preventDefault();
            if (dashboardSection) dashboardSection.classList.add('hidden');
            if (resultsSection) resultsSection.classList.add('hidden');
            setHomeVisibility(true);
            document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
            navAnLink.classList.add('active');
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }

    // =========================================================
    // AUTH PAGE LOGIC (NEW)
    // =========================================================
    const pageAuthTabs = document.querySelectorAll('.page-auth-tabs .auth-tab');
    const pageLoginForm = document.getElementById('page-login-form');
    const pageSignupForm = document.getElementById('page-signup-form');

    pageAuthTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            pageAuthTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            const target = tab.dataset.tab;
            if (target === 'login') {
                pageLoginForm.classList.remove('hidden');
                pageSignupForm.classList.add('hidden');
            } else {
                pageLoginForm.classList.add('hidden');
                pageSignupForm.classList.remove('hidden');
            }
        });
    });

    if (pageLoginForm) {
        pageLoginForm.addEventListener('submit', async e => {
            e.preventDefault();
            const formData = new FormData(pageLoginForm);
            const res = await AuthManager.login(formData.get('email'), formData.get('password'));
            if (res.success) {
                ScreenManager.show('workspace');
            } else {
                const errEl = document.getElementById('page-login-error');
                errEl.textContent = res.error;
                errEl.classList.remove('hidden');
            }
        });
    }

    if (pageSignupForm) {
        pageSignupForm.addEventListener('submit', async e => {
            e.preventDefault();
            const formData = new FormData(pageSignupForm);
            const res = await AuthManager.signup(
                formData.get('full_name'),
                formData.get('email'),
                formData.get('password')
            );
            if (res.success) {
                await AuthManager.login(formData.get('email'), formData.get('password'));
                ScreenManager.show('workspace');
            } else {
                const errEl = document.getElementById('page-signup-error');
                errEl.textContent = res.error;
                errEl.classList.remove('hidden');
            }
        });
    }

    // =========================================================
    // AUTH MODAL LOGIC (Existing - for in-app popups)
    // =========================================================
    if (btnLoginOpen) {
        btnLoginOpen.addEventListener('click', () => {
            ScreenManager.show('access'); // Go to dedicated page instead of modal
        });
    }

    if (closeAuthModalBtn) {
        closeAuthModalBtn.addEventListener('click', () => {
            authModal.classList.add('hidden');
        });
    }

    if (btnSaveAccount) {
        btnSaveAccount.addEventListener('click', () => {
            authModal.classList.remove('hidden');
            // Switch to signup by default for saving
            const signupTab = document.querySelector('.modal [data-tab="signup"]');
            if (signupTab) signupTab.click();
        });
    }

    const modalAuthTabs = document.querySelectorAll('.modal .auth-tab');
    modalAuthTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            modalAuthTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            const target = tab.dataset.tab;
            if (target === 'login') {
                loginForm.classList.remove('hidden');
                signupForm.classList.add('hidden');
            } else {
                loginForm.classList.add('hidden');
                signupForm.classList.remove('hidden');
            }
        });
    });

    if (loginForm) {
        loginForm.addEventListener('submit', async e => {
            e.preventDefault();
            const formData = new FormData(loginForm);
            const res = await AuthManager.login(formData.get('email'), formData.get('password'));
            if (res.success) {
                authModal.classList.add('hidden');
                ScreenManager.show('workspace');
                if (!dashboardSection.classList.contains('hidden')) {
                    loadDashboardHistory();
                }
            } else {
                const errEl = document.getElementById('login-error');
                errEl.textContent = res.error;
                errEl.classList.remove('hidden');
            }
        });
    }

    if (signupForm) {
        signupForm.addEventListener('submit', async e => {
            e.preventDefault();
            const formData = new FormData(signupForm);
            const res = await AuthManager.signup(
                formData.get('full_name'),
                formData.get('email'),
                formData.get('password')
            );
            if (res.success) {
                // Auto login after signup
                await AuthManager.login(formData.get('email'), formData.get('password'));
                authModal.classList.add('hidden');
                ScreenManager.show('workspace');
            } else {
                const errEl = document.getElementById('signup-error');
                errEl.textContent = res.error;
                errEl.classList.remove('hidden');
            }
        });
    }

    if (btnLogout) {
        btnLogout.addEventListener('click', () => AuthManager.logout());
    }

    // =========================================================
    // DRAG & DROP
    // =========================================================

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(ev =>
        fileDropArea.addEventListener(ev, e => { e.preventDefault(); e.stopPropagation(); }, false)
    );
    ['dragenter', 'dragover'].forEach(ev =>
        fileDropArea.addEventListener(ev, () => fileDropArea.classList.add('dragover'))
    );
    ['dragleave', 'drop'].forEach(ev =>
        fileDropArea.addEventListener(ev, () => fileDropArea.classList.remove('dragover'))
    );
    fileDropArea.addEventListener('drop', e => {
        const files = e.dataTransfer.files;
        if (files && files.length > 0) {
            
            // Programmatically assign the dropped file to our hidden input
            const dt = new DataTransfer();
            dt.items.add(files[0]);
            resumeInput.files = dt.files;
            

            
            // Update the UI message
            updateFileMsg();
            
            // Trigger a change event so other listeners know a file was added
            resumeInput.dispatchEvent(new Event('change', { bubbles: true }));
        }
    });

    resumeInput.addEventListener('change', updateFileMsg);

    function updateFileMsg() {
        if (resumeInput.files && resumeInput.files[0]) {
            fileMsg.innerHTML = `<span style="color:var(--primary); font-weight:bold;">Selected:</span> ${resumeInput.files[0].name}`;
            fileDropArea.style.borderColor = 'var(--primary)';
        }
    }

    // =========================================================
    // CITY AUTOCOMPLETE
    // =========================================================
    const CITIES = [
        // India
        'Mumbai', 'Delhi', 'Bengaluru', 'Hyderabad', 'Ahmedabad', 'Chennai', 'Kolkata', 'Surat', 'Pune',
        'Jaipur', 'Lucknow', 'Kanpur', 'Nagpur', 'Indore', 'Thane', 'Bhopal', 'Visakhapatnam', 'Pimpri-Chinchwad',
        'Patna', 'Vadodara', 'Ghaziabad', 'Ludhiana', 'Agra', 'Nashik', 'Faridabad', 'Meerut', 'Rajkot',
        'Kalyan-Dombivli', 'Vasai-Virar', 'Varanasi', 'Srinagar', 'Aurangabad', 'Dhanbad', 'Amritsar',
        'Navi Mumbai', 'Allahabad', 'Ranchi', 'Howrah', 'Coimbatore', 'Jabalpur', 'Gwalior', 'Vijayawada',
        'Jodhpur', 'Madurai', 'Raipur', 'Kota', 'Chandigarh', 'Guwahati', 'Solapur', 'Hubballi-Dharwad',
        'Mysuru', 'Tiruchirappalli', 'Bareilly', 'Aligarh', 'Tiruppur', 'Gurgaon', 'Noida', 'Mangaluru',
        'Dehradun', 'Bhubaneswar', 'Jammu', 'Warangal', 'Puducherry', 'Kochi', 'Kozhikode', 'Thiruvananthapuram',
        'Remote', 'Pan India', 'Work From Home',
        // International
        'New York', 'San Francisco', 'London', 'Berlin', 'Singapore', 'Dubai', 'Toronto', 'Sydney',
        'Tokyo', 'Paris', 'Amsterdam', 'Zurich', 'Seattle', 'Austin', 'Boston', 'Chicago', 'Los Angeles',
        'Vancouver', 'Melbourne', 'Bangalore Remote', 'Hyderabad Remote',
    ];

    const locationInput = document.getElementById('location');
    const cityDropdown = document.createElement('div');
    cityDropdown.className = 'city-dropdown hidden';
    locationInput.parentElement.style.position = 'relative';
    locationInput.parentElement.appendChild(cityDropdown);

    locationInput.addEventListener('input', () => {
        const val = locationInput.value.trim().toLowerCase();
        cityDropdown.innerHTML = '';
        if (!val || val.length < 1) { cityDropdown.classList.add('hidden'); return; }

        const matches = CITIES.filter(c => c.toLowerCase().includes(val)).slice(0, 8);
        if (!matches.length) { cityDropdown.classList.add('hidden'); return; }

        matches.forEach(city => {
            const item = document.createElement('div');
            item.className = 'city-item';
            // Bold the matching part
            const idx = city.toLowerCase().indexOf(val);
            item.innerHTML = city.slice(0, idx)
                + `<strong>${city.slice(idx, idx + val.length)}</strong>`
                + city.slice(idx + val.length);
            item.addEventListener('mousedown', e => {
                e.preventDefault(); // Prevent input blur before click registers
                locationInput.value = city;
                cityDropdown.classList.add('hidden');
            });
            cityDropdown.appendChild(item);
        });
        cityDropdown.classList.remove('hidden');
    });

    locationInput.addEventListener('blur', () => {
        setTimeout(() => cityDropdown.classList.add('hidden'), 150);
    });

    locationInput.addEventListener('keydown', e => {
        if (e.key === 'Escape') cityDropdown.classList.add('hidden');
        if (e.key === 'Enter' && !cityDropdown.classList.contains('hidden')) {
            const first = cityDropdown.querySelector('.city-item');
            if (first) { locationInput.value = first.textContent; cityDropdown.classList.add('hidden'); e.preventDefault(); }
        }
    });

    // =========================================================
    // FORM SUBMIT
    // =========================================================
    form.addEventListener('submit', async e => {
        e.preventDefault();

        if (!resumeInput.files || !resumeInput.files[0]) { 
            alert('Please select a resume file.'); 
            return; 
        }

        const formData = new FormData(form);
        submitBtn.disabled = true;
        submitSpinner.classList.remove('hidden');
        loadingOverlay.classList.remove('hidden');
        startProgressSimulation();

        try {
            const res = await apiFetch(`${API_BASE_URL}/analyze`, { method: 'POST', body: formData });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Analysis failed.');

            setHomeVisibility(false); // Hide landing page sections
            lastSessionId = data.session_id;
            addPendingClaimSession(data.session_id);
            renderResults(data);

            if (analyzerSection) analyzerSection.classList.add('hidden');
            if (dashboardSection) dashboardSection.classList.add('hidden');
            if (resultsSection) resultsSection.classList.remove('hidden');
            window.scrollTo({ top: 0, behavior: 'smooth' });
        } catch (err) {
            alert(`Error: ${err.message}`);
        } finally {
            stopProgressSimulation();
            await new Promise(r => setTimeout(r, 600)); // brief pause to show 100%
            if (submitBtn) submitBtn.disabled = false;
            if (submitSpinner) submitSpinner.classList.add('hidden');
            if (loadingOverlay) loadingOverlay.classList.add('hidden');
        }
    });

    // =========================================================
    // RENDER RESULTS  (shared by fresh analysis + history load)
    // =========================================================
    function renderResults(data) {
        if (!data || !data.role_results) return;

        // Store the top match score as our base for progression simulation
        if (data.role_results.length > 0) {
            currentBaseScore = data.role_results[0].match_percentage;
            const scoreVal = document.querySelector('.score-value');
            if (scoreVal) scoreVal.textContent = `${currentBaseScore.toFixed(1)}%`;
        }
        learnedSkills.clear();

        // Show "Save to Account" if guest
        if (!AuthManager.user) {
            btnSaveAccount.classList.remove('hidden');
        }

        const sessionId = data.session_id;
        roleStore.clear();

        // --- Skills ---
        const skillsContainer = document.getElementById('user-skills-container');
        skillsContainer.innerHTML = '';
        const clusters = data.skill_clusters || {};
        (data.resume_skills || []).slice(0, 20).forEach(skill => {
            const span = document.createElement('span');
            span.className = 'tag skill-tag';
            span.textContent = skill;

            // Map skill to its cluster for Tableau-style highlight
            let clusterName = 'Other';
            const skillLower = skill.toLowerCase();
            for (const [cName, cData] of Object.entries(clusters)) {
                if (cData.skills && cData.skills.some(s => s.toLowerCase() === skillLower)) {
                    clusterName = cName;
                    break;
                }
            }
            span.dataset.cluster = clusterName;
            skillsContainer.appendChild(span);
        });

        // --- Industries ---
        const industriesList = document.getElementById('user-industries-list');
        industriesList.innerHTML = '';
        const industries = data.best_industries || data.industries_detected || [];
        industries.slice(0, 5).forEach(ind => {
            const li = document.createElement('li');
            li.className = 'clickable-industry';
            const industryName = typeof ind === 'object' ? ind.industry : ind;
            const industryScore = typeof ind === 'object' ? (ind.match_score || 0).toFixed(1) : null;

            li.innerHTML = `
                <div style="display:flex; align-items:center; width:100%;">
                    <strong>${industryName}</strong>
                    ${industryScore ? `<span style="margin-left:auto;color:var(--primary)">${industryScore}% Match</span>` : ''}
                </div>
            `;

            li.addEventListener('click', () => {
                const explorer = document.getElementById('industry-skills-table');
                if (explorer) {
                    explorer.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    // Try to find the row in the table
                    setTimeout(() => {
                        const rows = document.querySelectorAll('.industry-row');
                        rows.forEach(row => {
                            if (row.textContent.includes(industryName)) {
                                row.click(); // Expand it
                                row.style.backgroundColor = 'rgba(14, 165, 233, 0.2)';
                                setTimeout(() => row.style.backgroundColor = '', 2000);
                            }
                        });
                    }, 800);
                }
            });
            industriesList.appendChild(li);
        });

        // --- Interactive Skill Chart (Chart.js) ---
        renderSkillChart(data.skill_clusters);

        // --- Role Cards ---
        const rolesContainer = document.getElementById('roles-container');
        rolesContainer.innerHTML = '';

        (data.role_results || []).forEach((role, idx) => {
            // Store full role object by index — avoids JSON-in-attribute bugs
            roleStore.set(idx, role);

            const card = document.createElement('div');
            card.className = 'role-card';
            card.dataset.roleIdx = idx;

            const matchPct = (role.match_percentage || 0).toFixed(1);
            const matchColor = role.match_percentage >= 70 ? 'var(--accent)' :
                role.match_percentage >= 50 ? 'var(--primary)' : '#f59e0b';

            const matchedHtml = (role.matched_skills || []).slice(0, 4)
                .map(s => `<span class="tag match">${s}</span>`).join('') || '<span class="tag">None</span>';

            const missingHtml = (role.missing_skills || []).slice(0, 5)
                .map(s => `<span class="tag missing skill-tag" data-skill="${s}" data-session="${sessionId}">${s}</span>`).join('')
                || '<span class="tag">None</span>';

            // Show up to 3 job companies (backend field: employer_name, job_city)
            const jobs = (role.apply_at || []).slice(0, 3);
            const jobPreviewHtml = jobs.length
                ? jobs.map(j => `<div class="job-preview-item">
                    <span class="job-dot"></span>
                    <div>
                        <span class="job-co">${j.company || j.employer_name || 'Company'}</span>
                        ${(j.location || j.job_city) ? `<span class="job-loc">📍 ${j.location || j.job_city}</span>` : ''}
                    </div>
                  </div>`).join('')
                : '<p style="color:var(--text-muted);font-size:0.85rem">No live listings fetched</p>';

            card.innerHTML = `
                <div class="role-header">
                    <div>
                        <div class="role-title">${role.role || role.job_role}</div>
                        <div class="role-industry">${role.industry || '—'}</div>
                    </div>
                    <div class="match-badge" style="background:${matchColor}">${matchPct}% Match</div>
                </div>

                <div class="role-skills">
                    <p>✅ Matched Skills</p>
                    <div class="tags-container">${matchedHtml}</div>
                </div>
                <div class="role-skills">
                    <p>📚 Missing Skills <span style="font-size:0.75rem;color:var(--text-muted)">(click a skill for roadmap)</span></p>
                    <div class="tags-container missing-skills-row">${missingHtml}</div>
                </div>

                <div class="job-preview-section">
                    <p style="font-size:0.85rem;color:var(--text-muted);margin-bottom:0.5rem">🏢 Hiring Companies</p>
                    ${jobPreviewHtml}
                </div>

                <div class="role-actions">
                    <button class="btn-secondary btn-role-detail" data-role-idx="${idx}">View Full Detail</button>
                    <button class="btn-apply btn-job-links" data-role-idx="${idx}">View Job Links →</button>
                </div>
            `;
            rolesContainer.appendChild(card);
        });

        // Bind role action buttons (safe — using data-role-idx, not JSON in attribute)
        rolesContainer.querySelectorAll('.btn-job-links').forEach(btn => {
            btn.addEventListener('click', e => {
                e.stopPropagation();
                const role = roleStore.get(parseInt(btn.dataset.roleIdx));
                openJobModal(role);
            });
        });

        rolesContainer.querySelectorAll('.btn-role-detail').forEach(btn => {
            btn.addEventListener('click', e => {
                e.stopPropagation();
                const role = roleStore.get(parseInt(btn.dataset.roleIdx));
                openRoleModal(role, sessionId);
            });
        });

        // Bind missing skill tags → roadmap
        rolesContainer.querySelectorAll('.skill-tag').forEach(tag => {
            tag.addEventListener('click', e => {
                e.stopPropagation();
                openSkillRoadmap(tag.dataset.skill, tag.dataset.session);
            });
        });

        // Industry Skills Explorer
        renderIndustrySkillsExplorer();
    }

    function renderSkillChart(clusters) {
        if (!clusters) clusters = {};
        const canvas = document.getElementById('cluster-chart-canvas');
        const ctx = canvas.getContext('2d');
        const labels = Object.keys(clusters);
        const scores = Object.values(clusters).map(c => (c && typeof c === 'object') ? (c.count || 0) : 0);

        if (skillChart) skillChart.destroy();

        const colors = [
            '#0ea5e9', '#6366f1', '#8b5cf6', '#ec4899', '#f43f5e',
            '#f59e0b', '#10b981', '#06b6d4', '#3b82f6', '#14b8a6'
        ];

        skillChart = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: labels,
                datasets: [{
                    data: scores,
                    backgroundColor: colors.map(c => c + 'bb'),
                    borderColor: '#1e293b',
                    borderWidth: 2,
                    hoverOffset: 0 // DISABLE MOVING/OFFSET to prevent layout shifts
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: {
                    padding: 10
                },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: '#94a3b8', font: { size: 10 }, padding: 10 }
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const cluster = labels[context.dataIndex];
                                const data = clusters[cluster];
                                return ` ${cluster}: ${data.count} Skills (${data.coverage_pct}% coverage)`;
                            }
                        }
                    }
                },
                onClick: (evt, activeElements) => {
                    if (activeElements.length > 0) {
                        const idx = activeElements[0].index;
                        const cluster = labels[idx];
                        highlightSkillsByCluster(cluster);
                    } else {
                        // Clicked background: Toggle Fullscreen like before
                        const imageModal = document.getElementById('image-modal');
                        const fullScreenImage = document.getElementById('full-screen-image');
                        if (imageModal && fullScreenImage) {
                            fullScreenImage.src = canvas.toDataURL('image/png');
                            imageModal.classList.remove('hidden');
                        }
                        highlightSkillsByCluster(null);
                    }
                }
            }
        });
    }

    function highlightSkillsByCluster(clusterName) {
        const skillTags = document.querySelectorAll('#user-skills-container .skill-tag');
        if (!clusterName) {
            skillTags.forEach(t => t.style.opacity = '1');
            return;
        }

        // Find which skills belong to this cluster
        // We can get this from the clusters object or just assume
        skillTags.forEach(tag => {
            // This is a bit tricky since we don't have the cluster name on the tag
            // I'll update renderResults to add a data-cluster attribute to tags
            const tagCluster = tag.dataset.cluster;
            if (tagCluster === clusterName) {
                tag.style.opacity = '1';
                tag.style.transform = 'scale(1.1)';
                tag.style.boxShadow = '0 0 15px var(--primary)';
            } else {
                tag.style.opacity = '0.3';
                tag.style.transform = 'scale(0.9)';
                tag.style.boxShadow = 'none';
            }
        });
    }

    // =========================================================
    // CHART FETCH (KEEP FOR BACKWARDS COMPATIBILITY IF NEEDED OR REMOVE)
    // =========================================================
    async function fetchAndSetChart(url, imgId) {
        // Obsolete with Chart.js, but keeping skeleton to avoid breakage if called
    }

    // =========================================================
    // LOAD HISTORY SESSION
    // =========================================================
    async function loadSessionById(sessionId) {
        loadingText.textContent = 'Loading Session...';
        loadingOverlay.classList.remove('hidden');
        try {
            const res = await apiFetch(`${API_BASE_URL}/result/${sessionId}`);
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Failed to load session.');

            const mapped = {
                session_id: data.session.id,
                resume_skills: data.session.resume_skills || [],
                best_industries: data.session.industries_detected || [],
                skill_clusters: data.session.skill_cluster_distribution || {}, // RESTORE CLUSTERS
                role_results: (data.role_results || []).map(r => ({
                    ...r,
                    role: r.job_role,
                    matched_skills: Array.isArray(r.matched_skills) ? r.matched_skills
                        : (r.matched_skills || '').split(', ').filter(Boolean),
                    missing_skills: Array.isArray(r.missing_skills) ? r.missing_skills
                        : (r.missing_skills || '').split(', ').filter(Boolean),
                    apply_at: Array.isArray(r.apply_at) ? r.apply_at : [],
                }))
            };

            setHomeVisibility(false); // Hide landing page
            renderResults(mapped);
            if (dashboardSection) dashboardSection.classList.add('hidden');
            if (analyzerSection) analyzerSection.classList.add('hidden');
            if (resultsSection) resultsSection.classList.remove('hidden');
            window.scrollTo({ top: 0, behavior: 'smooth' });
        } catch (err) {
            alert(`Error loading session: ${err.message}`);
        } finally {
            loadingOverlay.classList.add('hidden');
        }
    }

    // =========================================================
    // DASHBOARD HISTORY
    // =========================================================
    async function loadDashboardHistory() {
        const hc = document.getElementById('history-container');
        hc.innerHTML = '<div class="loader-content"><div class="spinner"></div><p style="margin-top:1rem">Loading history...</p></div>';
        try {
            const res = await apiFetch(`${API_BASE_URL}/dashboard`);
            const data = await res.json();
            if (!res.ok) throw new Error(data.error);

            if (data.data && data.data.length > 0) {
                hc.innerHTML = '';
                data.data.forEach(session => {
                    const card = document.createElement('div');
                    card.className = 'glass-panel stat-card clickable-card';
                    const date = new Date(session.created_at).toLocaleString();
                    const bm = session.best_match;
                    const skillsHtml = (session.resume_skills || []).slice(0, 5)
                        .map(s => `<span class="tag" style="font-size:0.75rem">${s}</span>`).join('');

                    card.innerHTML = `
                        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:0.75rem">
                            <div>
                                <strong style="font-size:1.05rem">${session.filename}</strong>
                                <p style="font-size:0.8rem;color:var(--text-muted);margin-top:0.2rem">${date}</p>
                            </div>
                            <span class="match-badge" style="flex-shrink:0">${bm ? bm.match_percentage.toFixed(0) + '% Match' : 'N/A'}</span>
                        </div>
                        <p style="font-size:0.85rem;color:var(--text-muted);margin-bottom:0.5rem">
                            Best Role: <span style="color:var(--primary);font-weight:600">${bm ? bm.job_role : 'N/A'}</span>
                        </p>
                        <div class="tags-container" style="margin-bottom:0.75rem">${skillsHtml}</div>
                        <div style="display:flex;justify-content:flex-end">
                            <button class="btn-apply open-session-btn" data-session-id="${session.id}">Open Full Analysis →</button>
                        </div>
                    `;
                    hc.appendChild(card);
                });

                hc.querySelectorAll('.open-session-btn').forEach(btn =>
                    btn.addEventListener('click', e => { e.stopPropagation(); loadSessionById(btn.dataset.sessionId); })
                );
                hc.querySelectorAll('.clickable-card').forEach(card =>
                    card.addEventListener('click', () => {
                        const btn = card.querySelector('.open-session-btn');
                        if (btn) loadSessionById(btn.dataset.sessionId);
                    })
                );
            } else {
                if (!AuthManager.user) {
                    hc.innerHTML = `
                        <div class="empty-state-card glass-panel">
                            <h3>History is Locked 🔒</h3>
                            <p>Create an account or login to save your resume analysis history and track your progress over time.</p>
                            <button class="btn-primary" onclick="document.getElementById('btn-login-open').click()" style="max-width:200px; margin: 0 auto;">Login / Sign Up</button>
                        </div>
                    `;
                } else {
                    hc.innerHTML = `
                        <div class=\"empty-state-card glass-panel\">
                            <h3>No Analysis Found 🔍</h3>
                            <p>You haven\'t analyzed any resumes yet. Head over to the Analyzer to get started!</p>
                            <button class=\"btn-primary\" onclick=\"document.querySelector(\'a[href=\\\"#analyzer\\\"]\').click()\" style=\"max-width:200px; margin: 0 auto;\">Go to Analyzer</button>
                        </div>
                    `;
                }
            }
        } catch (err) {
            // Check if error is authentication related or simply empty
            if (err.message && (err.message.includes('401') || err.message.includes('Unauthorized'))) {
                AuthManager.logout();
                return;
            }
            hc.innerHTML = `
                <div class=\"empty-state-card glass-panel\">
                    <h3>No Resumes Analyzed Yet</h3>
                    <p>Start your career journey by uploading your resume in the Analyzer section.</p>
                </div>
            `;
        }
    }

    // =========================================================
    // JOB LINKS MODAL
    // =========================================================
    function openJobModal(role) {
        document.getElementById('modal-role-title').textContent = `Job Listings — ${role.role || role.job_role}`;
        const container = document.getElementById('job-links-container');
        container.innerHTML = '';

        const jobs = role.apply_at || [];
        if (jobs.length > 0) {
            jobs.forEach(job => {
                // Backend returns: job_title, employer_name, job_city, job_state, job_country, job_apply_link
                // Mapped version may also have: title, company, location, url
                const title = job.job_title || job.title || 'Job Opening';
                const company = job.employer_name || job.company || '';
                const city = job.job_city || '';
                const country = job.job_country || '';
                const location = job.location || [city, country].filter(Boolean).join(', ') || '';
                const applyUrl = job.job_apply_link || job.apply_link || job.url || '';
                const jobType = job.job_employment_type || '';

                container.innerHTML += `
                    <div class="job-link-item">
                        <div style="flex:1;min-width:0">
                            <div class="job-link-title">${title}</div>
                            <div class="job-link-company">
                                ${company ? `<strong>${company}</strong>` : ''}
                                ${location ? `&nbsp;·&nbsp; 📍 ${location}` : ''}
                                ${jobType ? `&nbsp;·&nbsp; <span style="color:var(--accent);font-size:0.75rem">${jobType}</span>` : ''}
                            </div>
                        </div>
                        ${applyUrl
                        ? `<a href="${applyUrl}" target="_blank" rel="noopener" class="btn-apply">Apply →</a>`
                        : `<span class="btn-apply" style="opacity:0.4;cursor:default">No Link</span>`}
                    </div>
                `;
            });
        } else {
            container.innerHTML = '<p style="color:var(--text-muted)">No live job links were fetched for this role.</p>';
        }
        jobModal.classList.remove('hidden');
    }

    // =========================================================
    // ROLE DETAIL MODAL
    // =========================================================
    function openRoleModal(role, sessionId) {
        const modal = roleModal;
        document.getElementById('role-modal-title').textContent = role.role || role.job_role;
        document.getElementById('role-modal-industry').textContent = role.industry || '—';

        const matchPct = (role.match_percentage || 0).toFixed(1);
        const aiPct = (role.ai_semantic_similarity || 0).toFixed(1);
        document.getElementById('role-modal-match').textContent = `${matchPct}%`;
        document.getElementById('role-modal-ai').textContent = `${aiPct}%`;

        // Recommendations
        const recs = Array.isArray(role.recommendations) ? role.recommendations
            : (role.recommendations || '').split(' | ').filter(Boolean);
        const recList = document.getElementById('role-modal-recs');
        recList.innerHTML = recs.length
            ? recs.map(r => `<li>${r}</li>`).join('')
            : '<li>No specific recommendations.</li>';

        // Matched skills
        const mContainer = document.getElementById('role-modal-matched');
        mContainer.innerHTML = (role.matched_skills || [])
            .map(s => `<span class="tag match">${s}</span>`).join('') || 'None';

        // Missing skills (clickable → roadmap)
        const misContainer = document.getElementById('role-modal-missing');
        misContainer.innerHTML = '';
        (role.missing_skills || []).forEach(s => {
            const span = document.createElement('span');
            span.className = 'tag missing skill-tag';
            span.textContent = s;
            span.title = 'Click for learning roadmap';
            span.dataset.skill = s;
            span.dataset.session = sessionId;
            span.addEventListener('click', () => openSkillRoadmap(s, sessionId));
            misContainer.appendChild(span);
        });

        // Job listings inside role modal (fix field names)
        const jobsSection = document.getElementById('role-modal-jobs');
        const jobs = role.apply_at || [];
        jobsSection.innerHTML = jobs.length
            ? jobs.map(j => {
                const title = j.job_title || j.title || 'Job Opening';
                const company = j.employer_name || j.company || '';
                const city = j.job_city || '';
                const country = j.job_country || '';
                const location = j.location || [city, country].filter(Boolean).join(', ') || '';
                const applyUrl = j.job_apply_link || j.apply_link || j.url || '';
                return `
                    <div class="job-link-item">
                        <div style="flex:1;min-width:0">
                            <div class="job-link-title">${title}</div>
                            <div class="job-link-company">
                                ${company ? `<strong>${company}</strong>` : ''}
                                ${location ? `&nbsp;·&nbsp; 📍 ${location}` : ''}
                            </div>
                        </div>
                        ${applyUrl
                        ? `<a href="${applyUrl}" target="_blank" rel="noopener" class="btn-apply">Apply →</a>`
                        : `<span class="btn-apply" style="opacity:0.4;cursor:default">No Link</span>`}
                    </div>`;
            }).join('')
            : '<p style="color:var(--text-muted)">No live listings available.</p>';

        modal.classList.remove('hidden');
    }

    // =========================================================
    // SKILL ROADMAP MODAL
    // =========================================================
    async function openSkillRoadmap(skill, sessionId) {
        document.getElementById('skill-modal-title').textContent = `🗺 Learning Roadmap: ${skill}`;
        const roadmapEl = document.getElementById('skill-roadmap');
        const coursesEl = document.getElementById('skill-courses');

        roadmapEl.innerHTML = '<div class="loader-content"><div class="spinner"></div><p style="margin-top:1rem">Building roadmap...</p></div>';
        coursesEl.innerHTML = '';
        skillModal.classList.remove('hidden');

        try {
            // Fetch learning path for this specific role's session
            const res = await apiFetch(`${API_BASE_URL}/learning-path/${sessionId}`);
            const data = await res.json();

            // Find this skill in the path clusters
            let skillData = null;
            if (data.learning_path) {
                for (const cluster of Object.values(data.learning_path)) {
                    const found = (cluster.skills || []).find(
                        s => (s.skill || s.name || '').toLowerCase() === skill.toLowerCase()
                    );
                    if (found) { skillData = found; break; }
                }
            }

            // ---- Render pictorial roadmap ----
            renderRoadmap(roadmapEl, skill, skillData);

            // ---- Render course links (async — fetches real YouTube video) ----
            await renderCourseLinks(coursesEl, skill);

        } catch (err) {
            roadmapEl.innerHTML = `<p style="color:red">Could not load roadmap: ${err.message}</p>`;
        }
    }

    // =========================================================
    // INDUSTRY SKILLS EXPLORER
    // =========================================================
    async function renderIndustrySkillsExplorer() {
        const body = document.getElementById('industry-skills-body');
        body.innerHTML = '<tr><td colspan="2" style="text-align:center;padding:2rem"><div class="spinner"></div></td></tr>';

        try {
            const res = await apiFetch(`${API_BASE_URL}/industry-skills`);
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Failed to load industry skills');

            const { industry_clusters, skill_clusters } = data;
            body.innerHTML = '';

            Object.entries(industry_clusters).forEach(([industry, clusters]) => {
                // Collect a few skills for preview
                let allSkills = [];
                clusters.forEach(c => {
                    if (skill_clusters[c]) allSkills.push(...skill_clusters[c]);
                });
                const preview = allSkills.slice(0, 4).join(', ') + '...';

                // Main row
                const row = document.createElement('tr');
                row.className = 'industry-row';
                row.innerHTML = `
                    <td class="industry-name-cell">
                        <span class="chevron-icon">▶</span>
                        ${industry}
                    </td>
                    <td class="preview-skills">${preview}</td>
                `;

                // Expanded row (hidden by default)
                const expandedRow = document.createElement('tr');
                expandedRow.className = 'skills-row';
                const skillsHtml = clusters.map(c => {
                    const skills = skill_clusters[c] || [];
                    return `
                        <div style="margin-bottom:1rem">
                            <h5 style="color:var(--primary);margin-bottom:0.75rem;font-size:0.85rem;text-transform:uppercase">${c}</h5>
                            <div class="industry-skills-grid">
                                ${skills.map(s => `
                                    <div class="skill-link-tag" ondblclick="window.redirectToYouTube('${s.replace(/'/g, "\\'")}')" title="Double click to play tutorial">
                                        ${s}
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    `;
                }).join('');

                expandedRow.innerHTML = `
                    <td colspan="2">
                        <div class="skills-expanded-content">
                            ${skillsHtml}
                        </div>
                    </td>
                `;

                row.addEventListener('click', () => {
                    const isActive = row.classList.contains('active');
                    // Close all others
                    body.querySelectorAll('.industry-row').forEach(r => r.classList.remove('active'));
                    if (!isActive) row.classList.add('active');
                });

                body.appendChild(row);
                body.appendChild(expandedRow);
            });
        } catch (err) {
            body.innerHTML = `<tr><td colspan="2" style="color:red;padding:2rem">${err.message}</td></tr>`;
        }
    }


    function renderRoadmap(container, skill, skillData) {
        const steps = skillData && skillData.steps ? skillData.steps : getDefaultSteps(skill);
        const learnedKey = `${skill}_steps`;
        const currentLearned = JSON.parse(localStorage.getItem(learnedKey) || '[]');

        // Progress bar for the modal
        const progressPct = Math.round((currentLearned.length / steps.length) * 100);

        let html = `
            <div class="roadmap-header-actions" style="margin-bottom:2rem;display:flex;flex-direction:column;gap:1rem;align-items:center;">
                <button class="btn-primary" id="btn-watch-masterclass" style="width:100%;padding:1.25rem;font-size:1.1rem;background:linear-gradient(135deg, #ef4444, #b91c1c);border:none;box-shadow:0 10px 20px rgba(239, 68, 68, 0.2)">
                    <span style="font-size:1.4rem;margin-right:0.5rem">📺</span> Watch Masterclass (Top Rated)
                </button>
                <div style="width:100%;background:rgba(255,255,255,0.05);height:8px;border-radius:4px;overflow:hidden">
                    <div id="roadmap-progress-fill" style="width:${progressPct}%;height:100%;background:var(--primary);transition:width 0.3s ease"></div>
                </div>
            </div>

            <div class="roadmap-wrapper">
                <div class="roadmap-node goal-node">🎯 Goal: ${skill}</div>
                <div class="roadmap-arrow">↓</div>
        `;

        steps.forEach((step, i) => {
            const isLast = i === steps.length - 1;
            const isOptional = i >= 3;
            const isChecked = currentLearned.includes(i);

            html += `
                <div class="roadmap-node step-node step-${i % 3} ${isChecked ? 'completed' : ''}" data-step="${i}">
                    <div style="display:flex;align-items:center;gap:1rem;width:100%">
                        <input type="checkbox" class="step-checkbox" ${isChecked ? 'checked' : ''} onchange="window.toggleStep('${skill}', ${i}, ${steps.length})">
                        <div style="flex:1">
                            <div><strong>${step}</strong></div>
                            ${isOptional ? '<div style="font-size:0.6rem;color:var(--text-muted);font-weight:700">OPTIONAL</div>' : ''}
                        </div>
                    </div>
                </div>
                ${!isLast ? '<div class="roadmap-arrow">↓</div>' : ''}
            `;
        });
        html += `
                <div class="roadmap-arrow">↓</div>
                <div class="roadmap-node done-node">✅ Complete: ${skill}</div>
            </div>
        `;
        container.innerHTML = html;

        // Bind the masterclass button to the top video
        const watchBtn = document.getElementById('btn-watch-masterclass');
        if (watchBtn) {
            watchBtn.addEventListener('click', () => {
                window.redirectToYouTube(skill);
            });
        }
    }

    // Progression Helpers
    window.toggleStep = (skill, stepIdx, totalSteps) => {
        const learnedKey = `${skill}_steps`;
        let learned = JSON.parse(localStorage.getItem(learnedKey) || '[]');

        if (learned.includes(stepIdx)) {
            learned = learned.filter(i => i !== stepIdx);
        } else {
            learned.push(stepIdx);
        }

        localStorage.setItem(learnedKey, JSON.stringify(learned));

        // Update Modal Progress Bar
        const fill = document.getElementById('roadmap-progress-fill');
        if (fill) fill.style.width = `${Math.round((learned.length / totalSteps) * 100)}%`;

        // Update Dashboard Score (Simulated)
        if (learned.length === totalSteps) {
            learnedSkills.add(skill);
        } else {
            learnedSkills.delete(skill);
        }
        updateDashboardScore();
    };

    function updateDashboardScore() {
        const scoreElement = document.querySelector('.score-value');
        if (!scoreElement) return;

        // Simulate a +2% boost for each fully learned skill
        const boost = learnedSkills.size * 2.5;
        const finalScore = Math.min(100, currentBaseScore + boost);

        scoreElement.textContent = `${finalScore.toFixed(1)}%`;
        scoreElement.style.color = 'var(--accent)';
        scoreElement.classList.add('pulse');
        setTimeout(() => scoreElement.classList.remove('pulse'), 1000);
    }

    function getDefaultSteps(skill) {
        return [
            "Fundamentals & Syntax",
            "Core Libraries",
            "Advanced Concepts",
            "Project Implementation",
            "Best Practices"
        ];
    }

    async function renderCourseLinks(container, skill) {
        const q = encodeURIComponent(skill);

        // Show a loading state first
        container.innerHTML = `
            <h4 style="margin-bottom:1rem;color:var(--text-muted);font-size:0.95rem">📖 Learning Resources for <strong style="color:var(--text-main)">${skill}</strong></h4>
            <div style="color:var(--text-muted);font-size:0.9rem">Finding best resources...</div>
        `;

        // Fallback URLs (used if API call fails or has no result)
        let ytUrl = `https://www.youtube.com/results?search_query=${q}+full+course+tutorial`;
        let ytTitle = 'Search YouTube';
        let ytChannel = '';
        let ytThumb = '';
        let udemyUrl = `https://www.udemy.com/courses/search/?q=${q}`;
        let courseraUrl = `https://www.coursera.org/search?query=${q}`;
        let fccUrl = `https://www.freecodecamp.org/news/search/?query=${q}`;

        try {
            const res = await apiFetch(`${API_BASE_URL}/course-links?skill=${encodeURIComponent(skill)}&t=${Date.now()}`);
            const data = await res.json();

            if (res.ok && data.links) {
                const { youtube_tutorials, udemy, coursera, freecodecamp } = data.links;

                // YouTube — use the real video URL from the API
                if (youtube_tutorials && youtube_tutorials.length > 0) {
                    const yt = youtube_tutorials[0];
                    ytUrl = yt.url;       // Real watch?v= or playlist URL
                    ytTitle = yt.title || 'Top Tutorial';
                    ytChannel = yt.channel || '';
                    ytThumb = yt.thumbnail || '';
                }
                if (udemy) udemyUrl = udemy;
                if (coursera) courseraUrl = coursera;
                if (freecodecamp) fccUrl = freecodecamp;
            }
        } catch (err) {
            console.warn('Course links API error:', err);
        }

        // Determine if it's a real video or just a search fallback
        const isRealVideo = ytUrl.includes('watch?v=') || ytUrl.includes('playlist?list=');
        const ytBadge = isRealVideo
            ? `<span style="background:rgba(255,0,0,0.15);color:#f87171;font-size:0.7rem;padding:0.15rem 0.4rem;border-radius:4px;margin-left:0.4rem">VIDEO</span>`
            : '';

        container.innerHTML = `
            <h4 style="margin-bottom:1rem;color:var(--text-muted);font-size:0.95rem">
                📖 Learning Resources for <strong style="color:var(--text-main)">${skill}</strong>
            </h4>
            <div class="course-links-grid">

                <a href="${ytUrl}" target="_blank" class="course-link-card yt ${isRealVideo ? 'yt-video' : ''}">
                    ${ytThumb ? `<img src="${ytThumb}" alt="thumbnail" class="yt-thumb">` : '<div class="course-icon">▶</div>'}
                    <div style="min-width:0">
                        <div class="course-name">YouTube ${ytBadge}</div>
                        <div class="course-desc" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:130px" title="${ytTitle}">${ytTitle}</div>
                        ${ytChannel ? `<div style="font-size:0.7rem;color:var(--text-muted);margin-top:0.1rem">${ytChannel}</div>` : ''}
                    </div>
                </a>

                <a href="${udemyUrl}" target="_blank" class="course-link-card udemy">
                    <div class="course-icon">🎓</div>
                    <div>
                        <div class="course-name">Udemy</div>
                        <div class="course-desc">Paid in-depth courses</div>
                    </div>
                </a>

                <a href="${courseraUrl}" target="_blank" class="course-link-card coursera">
                    <div class="course-icon">🏛</div>
                    <div>
                        <div class="course-name">Coursera</div>
                        <div class="course-desc">University-level courses</div>
                    </div>
                </a>

            </div>
            <a href="${fccUrl}" target="_blank" class="course-link-card" style="margin-top:0.75rem;display:flex;align-items:center;gap:0.75rem;">
                <div class="course-icon">🔥</div>
                <div>
                    <div class="course-name">freeCodeCamp</div>
                    <div class="course-desc">Free community-driven articles & videos</div>
                </div>
            </a>
        `;
    }


    // =========================================================
    // MODAL CLOSE HANDLERS
    // =========================================================
    [
        [closeJobModalBtn, jobModal],
        [closeRoleModalBtn, roleModal],
        [closeSkillModalBtn, skillModal],
        [closeImageModalBtn, imageModal],
    ].forEach(([btn, modal]) => {
        if (btn && modal) {
            btn.addEventListener('click', () => modal.classList.add('hidden'));
            modal.addEventListener('click', e => { if (e.target === modal) modal.classList.add('hidden'); });
        }
    });
});

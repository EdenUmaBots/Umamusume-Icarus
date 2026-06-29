(() => {
const state = {
    needs2fa: false,
    isLoading: false,
    account: null,
    isDeletingCareer: false,
    isFetchingFriends: false,
    isStartingCareer: false,
    presets: [],
    selectedPreset: "",
    runnerTimer: 0,
    isSavingPreset: false,
    raceData: [],
    selectedRaces: [],
    scenarioType: "Mant",
    burnClocks: false,
    finalizeSingleRuns: (localStorage.getItem('uma_finalize_single_runs') === 'true'),
    displayedClocksUsed: 0,
    caratsEnabled: (localStorage.getItem('uma_retry_carats') === 'true'),
    maxClocksPerCareer: Number(localStorage.getItem('uma_retry_max_clocks') ?? '0') || 0,
    skillConfigActiveZone: 'plan',
    devEnabled: true,
    // v7.6.2: career loop mode is ON by default (∞ = run until stopped). A
    // saved preference still wins; only a brand-new user with no stored choice
    // gets the looping default.
    runCount: Number(localStorage.getItem('sweepy_run_count') ?? '0'),
    consecutiveRunnerFails: 0,
    v4Timer: 0,
    trackblazerPlan: null,
    manualRaceSelectionActive: false,
    racePlannerMode: localStorage.getItem('sweepy_race_planner_mode') || 'smart',
    autoPlanBeforeRun: false,
    lastHealth: null,
    lastDiagnostics: null,
    lastAiStatus: null,
    accounts: [],
    traineeProfileCache: {},
    selectedTraineeProfile: null,
    trackblazerEpithets: [],
    weightedSkillPreview: null,
    skillConfig: null,
    smartSolverConfig: null,
    tpRecoveryMode: localStorage.getItem('sweepy_tp_recovery_mode') || 'potion_first',
    selectedReasonKey: null,
    reasonSelectionLocked: false,
    localLlmFormDirty: false,
    localLlmFormSaving: false,
    localLlmLastUserEditMs: 0
};
const els = {
    loadingScreen: document.getElementById('loading-screen'),
    navbar: document.querySelector('.navbar'),
    themeToggle: document.getElementById('theme-toggle'),
    brandMark: document.querySelector('.title span'),
    loginBtn: document.getElementById('login-btn'),
    logoutBtn: document.getElementById('logout-btn'),
    turnDelayMin: document.getElementById('turn-delay-min'),
    turnDelayMax: document.getElementById('turn-delay-max'),
    temptFateBtn: document.getElementById('tempt-fate-btn'),
    temptFatePanel: document.getElementById('tempt-fate-panel'),
    burnClocksBtn: document.getElementById('burn-clocks-btn'),
    finalizeRunsBtn: document.getElementById('finalize-runs-btn'),
    retryOptionsBtn: document.getElementById('retry-options-btn'),
    retryOptionsPanel: document.getElementById('retry-options-panel'),
    retryCaratsToggle: document.getElementById('retry-carats-toggle'),
    retryMaxClocks: document.getElementById('retry-max-clocks'),
    devBtn: document.getElementById('dev-career-btn'),
    runCountInput: document.getElementById('run-count-input'),
    loginView: document.getElementById('login-view'),
    dashboardView: document.getElementById('dashboard-view'),
    errorMsg: document.getElementById('error-msg'),
    standardFields: document.getElementById('standard-fields'),
    faFields: document.getElementById('2fa-fields'),
    umaGrid: document.getElementById('uma-grid'),
    cardGrid: document.getElementById('card-grid'),
    cardGridWrapper: document.getElementById('card-grid-wrapper'),
    cardsToggle: document.getElementById('cards-toggle'),
    cardsChevron: document.getElementById('cards-chevron'),
    parentGrid: document.getElementById('parent-grid'),
    friendGrid: document.getElementById('friend-grid'),
    deckList: document.getElementById('deck-list'),
    umaCount: document.getElementById('uma-count'),
    cardCount: document.getElementById('card-count'),
    parentCount: document.getElementById('parent-count'),
    friendCount: document.getElementById('friend-count'),
    friendStatus: document.getElementById('friend-status'),
    friendRefreshBtn: document.getElementById('friend-refresh-btn'),
    presetSelect: document.getElementById('settings-preset-select') || document.getElementById('preset-select'),
    startCareerBtn: document.getElementById('start-career-btn'),
    startStatus: document.getElementById('start-status'),
    accountStrip: document.getElementById('account-strip'),
    careerModal: document.getElementById('career-modal'),
    careerModalCopy: document.getElementById('career-modal-copy'),
    careerCancelBtn: document.getElementById('career-cancel-btn'),
    careerDeleteBtn: document.getElementById('career-delete-btn'),
    raceToggle: document.getElementById('race-toggle'),
    raceChevron: document.getElementById('race-chevron'),
    raceBody: document.getElementById('race-body'),
    saveRacesBtn: document.getElementById('save-races-btn'),
    raceOptionsContent: document.getElementById('race-options-content'),
    racePopupOverlay: document.getElementById('race-slot-popup-overlay'),
    racePopupTitle: document.getElementById('race-slot-popup-title'),
    racePopupBody: document.getElementById('race-slot-popup-body'),
    racePopupClose: document.getElementById('race-slot-popup-close'),
    masterDataPath: document.getElementById('master-data-path'),
    masterDataSaveBtn: document.getElementById('master-data-save-btn'),
    masterDataStatus: document.getElementById('master-data-status'),
    presetSection: document.getElementById('settings-preset-section') || document.getElementById('preset-section'),
    presetAddBtn: document.getElementById('settings-preset-add-btn') || document.getElementById('preset-add-btn'),
    presetSaveBtn: document.getElementById('settings-preset-save-btn') || document.getElementById('preset-save-btn'),
    presetLoadBtn: document.getElementById('settings-preset-load-btn'),
    presetDelBtn: document.getElementById('settings-preset-del-btn') || document.getElementById('preset-del-btn'),
    presetSkillThreshold: document.getElementById('preset-skill-threshold'),
    presetEditSkillsBtn: document.getElementById('skill-config-open-btn') || document.getElementById('preset-edit-skills-btn'),
    skillModal: document.getElementById('skill-modal'),
    skillSearch: document.getElementById('skill-search'),
    skillList: document.getElementById('skill-list'),
    skillTiersContainer: document.getElementById('skill-tiers-container'),
    skillBlacklistContainer: document.getElementById('skill-blacklist-container'),
    skillAddTierBtn: document.getElementById('skill-add-tier-btn'),
    skillModalClose: document.getElementById('skill-modal-close'),
    skillConfigBody: document.getElementById('skill-config-body'),
    v4Health: document.getElementById('v4-health'),
    v4Analytics: document.getElementById('v4-analytics'),
    v4Diagnostics: document.getElementById('v4-diagnostics'),
    v515SetupBtn: document.getElementById('v515-setup-btn'),
    v515SetupModal: document.getElementById('v515-setup-modal'),
    v515SetupDoneBtn: document.getElementById('v515-setup-done-btn'),
    v515SetupBody: document.getElementById('v515-setup-body'),
    v516DiagnosticsBtn: document.getElementById('v516-diagnostics-btn'),
    v535AiLearningBtn: document.getElementById('v535-ai-learning-btn'),
    v535AiLearningModal: document.getElementById('v535-ai-learning-modal'),
    v535AiLearningDoneBtn: document.getElementById('v535-ai-learning-done-btn'),
    v535AiLearningBody: document.getElementById('v535-ai-learning-body'),
    v543CareerHistoryBtn: document.getElementById('v543-career-history-btn'),
    v543CareerHistoryModal: document.getElementById('v543-career-history-modal'),
    v543CareerHistoryDoneBtn: document.getElementById('v543-career-history-done-btn'),
    v543CareerHistorySummary: document.getElementById('v543-career-history-summary'),
    v543CareerHistoryBody: document.getElementById('v543-career-history-body'),
    v516DiagnosticsModal: document.getElementById('v516-diagnostics-modal'),
    v516DiagnosticsDoneBtn: document.getElementById('v516-diagnostics-done-btn'),
    v516DiagnosticsBody: document.getElementById('v516-diagnostics-body'),
    v4DiagBundleBtn: document.getElementById('v4-diag-bundle-btn'),
    v525RescueBtn: document.getElementById('v525-rescue-btn'),
    v525RescueStatus: document.getElementById('v525-rescue-status'),
    v532AiStatus: document.getElementById('v532-ai-status'),
    v532AiRebuildBtn: document.getElementById('v532-ai-rebuild-btn'),
    v532AiAdvisorBtn: document.getElementById('v532-ai-advisor-btn'),
    v532AiDownloadBtn: document.getElementById('v532-ai-download-btn'),
    v532AiAdvisor: document.getElementById('v532-ai-advisor'),
    v533AiTrainNowBtn: document.getElementById('v533-ai-train-now-btn'),
    v533AiReportBtn: document.getElementById('v533-ai-report-btn'),
    v533AiAutoToggle: document.getElementById('v533-ai-auto-toggle'),
    v533AiAutoStatus: document.getElementById('v533-ai-auto-status'),
    v539AiLivePolicyToggle: document.getElementById('v539-ai-live-policy-toggle'),
    v539AiLivePolicyState: document.getElementById('v539-ai-live-policy-state'),
    v539AiLivePolicyRecommendation: document.getElementById('v539-ai-live-policy-recommendation'),
    v543LocalLlmEnabled: document.getElementById('v543-local-llm-enabled'),
    v543LocalLlmProvider: document.getElementById('v543-local-llm-provider'),
    v543LocalLlmMode: document.getElementById('v543-local-llm-mode'),
    v543LocalLlmBaseUrl: document.getElementById('v543-local-llm-base-url'),
    v543LocalLlmModel: document.getElementById('v543-local-llm-model'),
    v543LocalLlmApiKey: document.getElementById('v543-local-llm-api-key'),
    v543LocalLlmSaveBtn: document.getElementById('v543-local-llm-save-btn'),
    v543LocalLlmTestBtn: document.getElementById('v543-local-llm-test-btn'),
    v543LocalLlmAnalyzeBtn: document.getElementById('v543-local-llm-analyze-btn'),
    v543LocalLlmShadowBtn: document.getElementById('v543-local-llm-shadow-btn'),
    v543LocalLlmStatus: document.getElementById('v543-local-llm-status'),
    v543LocalLlmOutput: document.getElementById('v543-local-llm-output'),
    v534AiHealth: document.getElementById('v534-ai-health'),
    v537AiImportPath: document.getElementById('v537-ai-import-path'),
    v537AiImportBtn: document.getElementById('v537-ai-import-btn'),
    v537AiImportStatus: document.getElementById('v537-ai-import-status'),
    v536AiDashboard: document.getElementById('v536-ai-dashboard'),
    v536AiConfidence: document.getElementById('v536-ai-confidence'),
    v536AiCareers: document.getElementById('v536-ai-careers'),
    v536AiTurns: document.getElementById('v536-ai-turns'),
    v536AiRaces: document.getElementById('v536-ai-races'),
    v536AiShadow: document.getElementById('v536-ai-shadow'),
    v536AiBacktest: document.getElementById('v536-ai-backtest'),
    v536AiRisk: document.getElementById('v536-ai-risk'),
    v536AiSuggestions: document.getElementById('v536-ai-suggestions'),
    v536AiConfidenceDetail: document.getElementById('v536-ai-confidence-detail'),
    v542StyleAdaptationMode: document.getElementById('v542-style-adaptation-mode'),
    v542StyleAdaptationSaveBtn: document.getElementById('v542-style-adaptation-save-btn'),
    v542StyleAdaptationStatus: document.getElementById('v542-style-adaptation-status'),
    v542StyleAdaptationReport: document.getElementById('v542-style-adaptation-report'),
    v534AiSafeBundleBtn: document.getElementById('v534-ai-safe-bundle-btn'),
    v53SolverBackendStatus: document.getElementById('v53-solver-backend-status'),
    v4TrackblazerStatus: document.getElementById('v4-trackblazer-status'),
    v4TrackblazerPlan: document.getElementById('v4-trackblazer-plan'),
    v4SyncTrackblazerBtn: document.getElementById('v4-sync-trackblazer-btn'),
    v4PlanBtn: document.getElementById('v4-plan-btn'),
    v47SmartModeBtn: document.getElementById('v47-smart-mode-btn'),
    v47ManualModeBtn: document.getElementById('v47-manual-mode-btn'),
    v47ApplyManualBtn: document.getElementById('v47-apply-manual-btn'),
    v4ApplyPlanBtn: document.getElementById('v4-apply-plan-btn'),
    v4ResetPlanBtn: document.getElementById('v4-reset-plan-btn'),
    v56SolverSettingsBtn: document.getElementById('v56-solver-settings-btn'),
    v56SolverSettingsModal: document.getElementById('smart-solver-settings-modal'),
    v56SolverSettingsBody: document.getElementById('smart-solver-settings-body'),
    v4AutoPlan: document.getElementById('v4-auto-plan'),
    v4IncludeOp: document.getElementById('v4-include-op'),
    v4FanBonus: document.getElementById('v4-fan-bonus'),
    v4MaxStreak: document.getElementById('v4-max-streak'),
    v4SnapshotTimeline: document.getElementById('v4-snapshot-timeline'),
    v5DecisionTrace: document.getElementById('v5-decision-trace'),
    v53RunBadge: document.getElementById('v53-run-badge'),
    v53CurrentCareer: document.getElementById('v53-current-career'),
    v53CareerPortrait: document.getElementById('v53-career-portrait'),
    v53CareerName: document.getElementById('v53-career-name'),
    v53HpFill: document.getElementById('v53-hp-fill'),
    v53HpText: document.getElementById('v53-hp-text'),
    v53MoodIcon: document.getElementById('v53-mood-icon'),
    v53MoodText: document.getElementById('v53-mood-text'),
    v53StatSpeed: document.getElementById('v53-stat-speed'),
    v53StatStamina: document.getElementById('v53-stat-stamina'),
    v53StatPower: document.getElementById('v53-stat-power'),
    v53StatGuts: document.getElementById('v53-stat-guts'),
    v53StatWit: document.getElementById('v53-stat-wit'),
    v53StatSp: document.getElementById('v53-stat-sp'),
    v53LatestDecision: document.getElementById('v53-latest-decision'),
    v53ActionLog: document.getElementById('v53-action-log'),
    v547DecisionReasoning: document.getElementById('v547-decision-reasoning'),
    v547ReasonTurn: document.getElementById('v547-reason-turn'),
    v520StopRunnerBtn: document.getElementById('v520-stop-runner-btn'),
    v526PauseRunnerBtn: document.getElementById('v526-pause-runner-btn'),
    v520SetupShortcutBtn: document.getElementById('v520-setup-shortcut-btn'),
    v53TurnCount: document.getElementById('v53-turn-count'),
    v53TotalFans: document.getElementById('v53-total-fans'),
    v53Fph: document.getElementById('v53-fph'),
    v53Runtime: document.getElementById('v53-runtime'),
    v53Careers: document.getElementById('v53-careers'),
    v53CareerFans: document.getElementById('v53-career-fans'),
    v525AccountsBtn: document.getElementById('v525-accounts-btn'),
    v525AccountsModal: document.getElementById('v525-accounts-modal'),
    v525AccountsDoneBtn: document.getElementById('v525-accounts-done-btn'),
    v525AccountsList: document.getElementById('v525-accounts-list'),
    v525AccountsStatus: document.getElementById('v525-accounts-status'),
    v525AddAccountBtn: document.getElementById('v525-add-account-btn'),
    v525SaveAccountsBtn: document.getElementById('v525-save-accounts-btn'),
    v525RefreshAccountsBtn: document.getElementById('v525-refresh-accounts-btn'),
    v525LaunchManagerBtn: document.getElementById('v525-launch-manager-btn'),
    eventChoicesOpenBtn: document.getElementById('event-choices-open'),
    eventChoicesModal: document.getElementById('event-choices-modal'),
    eventChoicesRefreshBtn: document.getElementById('event-choices-refresh-btn'),
    eventChoicesStatus: document.getElementById('event-choices-status'),
    eventChoicesList: document.getElementById('event-choices-list'),
    eventChoicesSearch: document.getElementById('event-choices-search'),
    eventChoicesDeckFilter: document.getElementById('event-choices-deck-filter'),
    discordWebhookUrl: document.getElementById('discord-webhook-url'),
    discordWebhookSaveBtn: document.getElementById('discord-webhook-save-btn'),
    discordWebhookTestBtn: document.getElementById('discord-webhook-test-btn'),
    discordWebhookStatus: document.getElementById('discord-webhook-status')
};
        const delaySettingsStorageKey = 'uma_turn_delay_settings';
        const burnClocksStorageKey = 'uma_burn_clocks';
        const devStorageKey = 'uma_dev_career';
        const runCountStorageKey = 'sweepy_run_count';
        // v5.5: expose the old hidden DEV loop mode as a normal Loop button.
        // Keep the storage key for backwards compatibility with existing browsers.
        const v4AutoPlanStorageKey = 'uma_v4_auto_plan';
        function normalizeRunCount(value) {
            const n = Number.parseInt(value, 10);
            if (!Number.isFinite(n) || n < 0) return 1;
            return Math.min(999, n);
        }
        function syncRunCountControls() {
            state.runCount = normalizeRunCount(state.runCount);
            state.devEnabled = state.runCount !== 1;
            if (els.runCountInput) els.runCountInput.value = String(state.runCount);
            syncDevControls();
        }
        function syncDevControls() {
            if (!els.devBtn) return;
            const enabled = state.runCount !== 1;
            const label = state.runCount === 0 ? '∞' : `${state.runCount}x`;
            els.devBtn.classList.toggle('is-active', enabled);
            els.devBtn.innerText = enabled ? `LOOP: ${label}` : 'LOOP: OFF';
            els.devBtn.title = enabled
                ? `Career looping is enabled (${state.runCount === 0 ? 'until stopped' : `${state.runCount} total career(s)`})`
                : 'Career looping is disabled';
        }
        function setRunCount(value, options = {}) {
            state.runCount = normalizeRunCount(value);
            state.devEnabled = state.runCount !== 1;
            syncRunCountControls();
            if (options.persist) {
                localStorage.setItem(runCountStorageKey, String(state.runCount));
                localStorage.setItem(devStorageKey, String(state.devEnabled));
            }
        }
        function setDevEnabled(value, options = {}) {
            const next = Boolean(value);
            if (next) {
                const existing = normalizeRunCount(els.runCountInput?.value ?? state.runCount);
                setRunCount(existing === 1 ? 0 : existing, options);
            } else {
                setRunCount(1, options);
            }
        }


        window.addEventListener('storage', event => {
            if (event.key === runCountStorageKey && event.newValue !== null) {
                setRunCount(event.newValue, { persist: false });
            } else if (event.key === devStorageKey && event.newValue !== null && localStorage.getItem(runCountStorageKey) === null) {
                setDevEnabled(event.newValue === 'true', { persist: false });
            }
        });
        const storedRunCount = localStorage.getItem(runCountStorageKey);
        const storedDev = localStorage.getItem(devStorageKey);
        if (storedRunCount !== null) setRunCount(storedRunCount, { persist: false });
        else if (storedDev !== null) setDevEnabled(storedDev === 'true', { persist: false });
        else syncRunCountControls();

        if (els.devBtn) {
            els.devBtn.addEventListener('click', () => {
                setDevEnabled(!state.devEnabled, { persist: true });
            });
        }
        if (els.runCountInput) {
            els.runCountInput.addEventListener('change', () => setRunCount(els.runCountInput.value, { persist: true }));
            els.runCountInput.addEventListener('input', () => { state.runCount = normalizeRunCount(els.runCountInput.value); syncDevControls(); });
        }

        function setLoadingScreen(visible) {
            if (!els.loadingScreen) return;
            els.loadingScreen.classList.toggle('hidden', !visible);
        }
        function hideNavbar() {
            document.body.classList.add('pre-login');
            if (els.brandMark) els.brandMark.classList.remove('is-entrance');
        }
        function showNavbar() {
            document.body.classList.remove('pre-login');
        }
        function playBrandIntro() {
            if (!els.brandMark) return;
            els.brandMark.classList.remove('is-entrance');
            void els.brandMark.offsetWidth;
            els.brandMark.classList.add('is-entrance');
            window.setTimeout(() => els.brandMark.classList.remove('is-entrance'), 950);
        }
        hideNavbar();
        function syncDashboardHeight() {
            const navbar = document.querySelector('.navbar');
            const navbarHeight = navbar ? navbar.getBoundingClientRect().height : 0;
            const availableHeight = Math.max(360, Math.floor(window.innerHeight - navbarHeight));
            document.documentElement.style.setProperty('--dashboard-height', `${availableHeight}px`);
            syncDashboardCollapseState(false);
        }
        window.addEventListener('resize', syncDashboardHeight);
        window.addEventListener('orientationchange', syncDashboardHeight);
        syncDashboardHeight();
        const panelToggleSyncers = [];
        const dashboardMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
        let dashboardLayoutAnimation = 0;
        const dashboardAnimationMs = 420;
        function isCompactDashboard() {
            return window.matchMedia('(max-width: 850px)').matches;
        }
        function getPanelLayoutTarget(setupCollapsed, contentCollapsed) {
            const compact = isCompactDashboard();
            const gutter = document.querySelector('.split-gutter-controls');
            const dashboardRect = els.dashboardView.getBoundingClientRect();
            const gutterRect = gutter.getBoundingClientRect();
            const gutterSize = compact ? gutterRect.height : gutterRect.width;
            const available = Math.max(0, (compact ? dashboardRect.height : dashboardRect.width) - gutterSize);
            if (compact) {
                const setupSize = setupCollapsed ? 0 : contentCollapsed ? available : available * 0.34;
                const contentSize = contentCollapsed ? 0 : setupCollapsed ? available : Math.max(340, available - setupSize);
                return { compact, gutterSize, setupSize, contentSize };
            }
            const setupSize = setupCollapsed ? 0 : contentCollapsed ? available : Math.min(available * 0.62, available - 340);
            const contentSize = contentCollapsed ? 0 : setupCollapsed ? available : Math.max(340, available - setupSize);
            return { compact, gutterSize, setupSize, contentSize };
        }
        function setDashboardTemplate(layout, setupSize, contentSize) {
            const safeSetup = Math.max(0, setupSize);
            const safeContent = Math.max(0, contentSize);
            if (layout.compact) {
                els.dashboardView.style.gridTemplateColumns = '';
                els.dashboardView.style.gridTemplateRows = `${safeSetup}px ${layout.gutterSize}px ${safeContent}px`;
            } else {
                els.dashboardView.style.gridTemplateRows = '';
                els.dashboardView.style.gridTemplateColumns = `${safeSetup}px ${layout.gutterSize}px ${safeContent}px`;
            }
        }
        function easeDashboardLayout(t) {
            return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
        }
        function syncDashboardCollapseState(animate = false) {
            const setupPanel = document.getElementById('setup-panel');
            const contentPanel = document.getElementById('content-panel');
            if (!setupPanel || !contentPanel || !els.dashboardView) return;
            if (setupPanel.classList.contains('collapsed') && contentPanel.classList.contains('collapsed')) {
                contentPanel.classList.remove('collapsed');
            }
            const setupCollapsed = setupPanel.classList.contains('collapsed');
            const contentCollapsed = contentPanel.classList.contains('collapsed');
            els.dashboardView.classList.toggle('setup-collapsed', setupCollapsed);
            els.dashboardView.classList.toggle('content-collapsed', contentCollapsed);
            if (!els.dashboardView.classList.contains('active')) return;
            const layout = getPanelLayoutTarget(setupCollapsed, contentCollapsed);
            if (dashboardLayoutAnimation) {
                cancelAnimationFrame(dashboardLayoutAnimation);
                dashboardLayoutAnimation = 0;
            }
            els.dashboardView.style.transition = 'none';
            if (!animate || dashboardMotion.matches) {
                setDashboardTemplate(layout, layout.setupSize, layout.contentSize);
                return;
            }
            const compact = layout.compact;
            const setupRect = setupPanel.getBoundingClientRect();
            const contentRect = contentPanel.getBoundingClientRect();
            const startSetup = compact ? setupRect.height : setupRect.width;
            const startContent = compact ? contentRect.height : contentRect.width;
            const targetSetup = layout.setupSize;
            const targetContent = layout.contentSize;
            if (Math.abs(startSetup - targetSetup) < 0.5 && Math.abs(startContent - targetContent) < 0.5) {
                setDashboardTemplate(layout, targetSetup, targetContent);
                return;
            }
            const startedAt = performance.now();
            const step = now => {
                const t = Math.min(1, (now - startedAt) / dashboardAnimationMs);
                const eased = easeDashboardLayout(t);
                setDashboardTemplate(
                    layout,
                    startSetup + (targetSetup - startSetup) * eased,
                    startContent + (targetContent - startContent) * eased
                );
                if (t < 1) {
                    dashboardLayoutAnimation = requestAnimationFrame(step);
                } else {
                    setDashboardTemplate(layout, targetSetup, targetContent);
                    dashboardLayoutAnimation = 0;
                }
            };
            setDashboardTemplate(layout, startSetup, startContent);
            dashboardLayoutAnimation = requestAnimationFrame(step);
        }
        function syncPanelToggleButtons() {
            panelToggleSyncers.forEach(sync => sync());
        }
        function makePanelToggle(panelId, btnId, collapseIcon, expandIcon) {
            const panel = document.getElementById(panelId);
            const btn = document.getElementById(btnId);
            const label = (btn.dataset.panelLabel || 'panel').toLowerCase();
            const renderChevrons = icon => `
                <span class="panel-collapse-btn-chevron-stack" aria-hidden="true">
                    <span>${icon}</span>
                    <span>${icon}</span>
                    <span>${icon}</span>
                </span>
            `;
            const syncButton = () => {
                const isCollapsed = panel.classList.contains('collapsed');
                const icon = isCollapsed ? expandIcon : collapseIcon;
                btn.classList.toggle('is-collapsed', isCollapsed);
                btn.innerHTML = renderChevrons(icon);
                btn.setAttribute('title', `${isCollapsed ? 'Expand' : 'Collapse'} ${label}`);
                btn.setAttribute('aria-label', `${isCollapsed ? 'Expand' : 'Collapse'} ${label}`);
                btn.setAttribute('aria-expanded', String(!isCollapsed));
            };
            panelToggleSyncers.push(syncButton);
            btn.addEventListener('click', () => {
                panel.classList.toggle('collapsed');
                syncDashboardCollapseState(true);
                syncPanelToggleButtons();
            });
            syncDashboardCollapseState(false);
            syncButton();
        }
        makePanelToggle('setup-panel',   'setup-collapse-btn',   '&lt;', '&gt;');
        makePanelToggle('content-panel', 'content-collapse-btn', '&gt;', '&lt;');
        function makeSectionToggle(toggleId, chevronId, bodyId, startExpanded) {
            const toggle  = document.getElementById(toggleId);
            const chevron = document.getElementById(chevronId);
            const body    = document.getElementById(bodyId);
            if (!toggle || !body) return;
            const setInitial = () => {
                const expanded = body.classList.contains('expanded');
                body.style.height = expanded ? 'auto' : '0px';
                chevron.classList.toggle('expanded', expanded);
            };
            const expand = () => {
                body.classList.add('expanded');
                chevron.classList.add('expanded');
                body.style.height = '0px';
                body.offsetHeight;
                body.style.height = `${body.scrollHeight}px`;
            };
            const collapse = () => {
                body.style.height = `${body.scrollHeight}px`;
                body.offsetHeight;
                body.classList.remove('expanded');
                chevron.classList.remove('expanded');
                body.style.height = '0px';
            };
            body.addEventListener('transitionend', event => {
                if (event.propertyName === 'height' && body.classList.contains('expanded')) body.style.height = 'auto';
            });
            toggle.addEventListener('click', () => {
                if (body.classList.contains('expanded')) collapse();
                else expand();
            });
            setInitial();
        }
        // v2.1: the Library is now a tab bar (Trainees / Parents / Guest Parents /
        // Decks / Friend Supports / Owned Cards) instead of collapsible sections.
        // Deck Bonuses shares the "decks" tab (pinned above the deck list). Section
        // bodies are forced open via CSS; the tab controls which section shows.
        function showLibraryTab(name) {
            if (!name) name = 'trainees';
            document.querySelectorAll('#lib-tabs .lib-tab').forEach(function (b) {
                b.classList.toggle('is-active', b.dataset.libTab === name);
            });
            if (name === 'guests' && typeof renderGuestParentsSection === 'function') {
                try { renderGuestParentsSection(); } catch (e) {}
            }
            document.querySelectorAll('[data-lib-section]').forEach(function (sec) {
                sec.style.display = (sec.dataset.libSection === name) ? '' : 'none';
            });
            try { localStorage.setItem('sweepy_lib_tab', name); } catch (e) {}
        }
        window.showLibraryTab = showLibraryTab;
        document.querySelectorAll('#lib-tabs .lib-tab').forEach(function (b) {
            b.addEventListener('click', function () { showLibraryTab(b.dataset.libTab); });
        });
        showLibraryTab((function () { try { return localStorage.getItem('sweepy_lib_tab'); } catch (e) { return null; } })() || 'trainees');
        makeSectionToggle('v4-toggle',       'v4-chevron',       'v4-body', true);
        const dashboardThemeStorageKey = 'sweepy_dashboard_theme';
        const ICARUS_THEMES = ['icarus', 'icarus-alt', 'neon', 'blue', 'clean-dark'];
        const normalizeTheme = t => {
            let req = String(t || '').toLowerCase();
            if (req === 'pink') req = 'neon';
            return ICARUS_THEMES.includes(req) ? req : 'icarus';
        };
        const legacyThemeFor = req => (req === 'blue' ? 'blue' : (req === 'neon' ? 'pink' : req));
        const applyTheme = theme => {
            const req = normalizeTheme(theme);
            const isCleanDark = req === 'clean-dark';
            const isBlue = req === 'blue';
            document.documentElement.dataset.theme = legacyThemeFor(req);
            document.documentElement.dataset.sweepyTheme = req;
            document.documentElement.classList.toggle('theme-blue', isBlue);
            document.body.classList.toggle('theme-blue', isBlue);
            document.documentElement.classList.toggle('theme-clean-dark', isCleanDark);
            document.body.classList.toggle('theme-clean-dark', isCleanDark);
            const selector = document.getElementById('sweepy-theme-select');
            if (selector) selector.value = req;
            return req;
        };
        const persistTheme = req => {
            localStorage.setItem(dashboardThemeStorageKey, req);
            localStorage.setItem('theme', legacyThemeFor(req));
            // Persist server-side too so the theme survives across browsers /
            // origins and server restarts (localStorage alone is per-origin).
            fetch('/api/settings/theme', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ theme: req }),
            }).catch(() => {});
        };
        function initThemeSelector(activeTheme) {
            const meta = document.querySelector('.navbar-meta');
            if (!meta || document.getElementById('sweepy-theme-select')) return;
            const wrap = document.createElement('label');
            wrap.className = 'theme-select-wrap';
            wrap.innerHTML = '<span>THEME</span><select id="sweepy-theme-select" aria-label="Dashboard theme">'
                + '<option value="icarus">Icarus</option>'
                + '<option value="icarus-alt">Icarus Alt</option>'
                + '<option value="neon">Neon Cockpit</option>'
                + '<option value="blue">Midnight</option>'
                + '<option value="clean-dark">Clean Dark</option>'
                + '</select>';
            meta.insertBefore(wrap, els.logoutBtn || null);
            const selector = wrap.querySelector('select');
            selector.value = normalizeTheme(activeTheme);
            selector.addEventListener('change', () => {
                const value = normalizeTheme(selector.value);
                persistTheme(value);
                applyTheme(value);
            });
        }
        const initialDashboardTheme = localStorage.getItem(dashboardThemeStorageKey) || localStorage.getItem('theme');
        const activeDashboardTheme = applyTheme(initialDashboardTheme);
        initThemeSelector(activeDashboardTheme);
        // The server-persisted theme is the source of truth; once it loads it
        // overrides the localStorage fast-path so the choice follows the user.
        fetch('/api/settings/theme').then(r => (r.ok ? r.json() : null)).then(d => {
            if (d && d.theme) {
                const t = applyTheme(d.theme);
                localStorage.setItem(dashboardThemeStorageKey, t);
                localStorage.setItem('theme', legacyThemeFor(t));
            }
        }).catch(() => {});
        const savedUsername = localStorage.getItem('saved_username');
        const savedPassword = localStorage.getItem('saved_password');
        if (savedUsername) document.getElementById('username').value = savedUsername;
        if (savedPassword) document.getElementById('password').value = savedPassword;
        let themeToggleClicks = 0;
        els.themeToggle.addEventListener('click', () => {
            // Clicking the logo cycles through the available themes (Icarus default).
            const current = normalizeTheme(document.documentElement.dataset.sweepyTheme);
            const next = ICARUS_THEMES[(ICARUS_THEMES.indexOf(current) + 1) % ICARUS_THEMES.length];
            applyTheme(next);
            persistTheme(next);
            themeToggleClicks++;
        });
        window.iwillnotabusethis = function() {
            setDevEnabled(true, { persist: true });
        };
        const sleep = ms => new Promise(resolve => window.setTimeout(resolve, ms));
        const nextFrame = () => new Promise(resolve => requestAnimationFrame(resolve));
        async function waitForDomPaint(frames = 2) {
            for (let i = 0; i < frames; i++) await nextFrame();
        }
        async function apiJson(url, options = {}) {
            // v2.1: abort a hung request so a stalled fetch can't wedge the UI.
            const ctrl = (typeof AbortController !== 'undefined') ? new AbortController() : null;
            const timer = ctrl ? setTimeout(() => { try { ctrl.abort(); } catch (e) {} }, options.timeoutMs || 15000) : null;
            let res;
            try {
                res = await fetch(url, ctrl ? { ...options, signal: ctrl.signal } : options);
            } finally {
                if (timer) clearTimeout(timer);
            }
            let data = {};
            try {
                data = await res.json();
            } catch (e) {
                data = {};
            }
            if (!res.ok) {
                const detail = data && (data.detail || data.message || data.error);
                throw new Error(typeof detail === 'string' ? detail : `HTTP ${res.status}`);
            }
            return data;
        }
        function setMasterDataStatus(message, stateName = '') {
            if (!els.masterDataStatus) return;
            els.masterDataStatus.textContent = message || '';
            els.masterDataStatus.className = `master-data-status ${stateName}`.trim();
        }
        function applyMasterDataStatus(data) {
            if (!data) return;
            if (els.masterDataPath && data.master_mdb_path) {
                els.masterDataPath.value = data.master_mdb_path;
            }
            if (els.masterDataPath) {
                els.masterDataPath.classList.toggle('needs-action', !data.exists);
            }
            if (data.exists) {
                if (data.generation_error) {
                    setMasterDataStatus(data.generation_error, 'needs-action');
                } else if (data.generated) {
                    setMasterDataStatus('master.mdb found; data generated', 'ok');
                } else {
                    setMasterDataStatus('master.mdb found', 'ok');
                }
            } else {
                setMasterDataStatus(data.access_error || 'master.mdb not found; update the path', 'needs-action');
            }
        }
        async function loadMasterDataStatus() {
            if (!els.masterDataPath) return;
            try {
                applyMasterDataStatus(await apiJson('/api/master-data/status'));
            } catch (e) {
                setMasterDataStatus('Unable to read master data status', 'needs-action');
            }
        }
        async function saveMasterDataPath() {
            if (!els.masterDataPath) return null;
            const master_mdb_path = els.masterDataPath.value.trim();
            if (!master_mdb_path) {
                setMasterDataStatus('Enter the full path to master.mdb', 'needs-action');
                els.masterDataPath.classList.add('needs-action');
                return null;
            }
            if (els.masterDataSaveBtn) els.masterDataSaveBtn.disabled = true;
            setMasterDataStatus('Saving path and generating data...', 'working');
            const data = await apiJson('/api/master-data/path', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ master_mdb_path })
            });
            applyMasterDataStatus(data);
            if (data.exists && !data.generation_error) {
                await loadRaceData();
            }
            if (els.masterDataSaveBtn) els.masterDataSaveBtn.disabled = false;
            return data;
        }
        function bindMasterDataControls() {
            if (!els.masterDataPath) return;
            if (els.masterDataSaveBtn) {
                els.masterDataSaveBtn.addEventListener('click', async () => {
                    try {
                        await saveMasterDataPath();
                    } catch (e) {
                        setMasterDataStatus(e.message || 'Unable to save master.mdb path', 'needs-action');
                        if (els.masterDataPath) els.masterDataPath.classList.add('needs-action');
                    } finally {
                        if (els.masterDataSaveBtn) els.masterDataSaveBtn.disabled = false;
                    }
                });
            }
            els.masterDataPath.addEventListener('input', () => {
                els.masterDataPath.classList.remove('needs-action');
            });
            loadMasterDataStatus();
        }
        function writeLocalSetting(key, value) {
            try {
                localStorage.setItem(key, JSON.stringify(value));
            } catch (e) {}
        }
        function readLocalSetting(value, fallback = null) {
            if (!value) return fallback;
            try {
                return JSON.parse(value);
            } catch (e) {
                return fallback;
            }
        }
        function escapeHtml(value) {
            return String(value ?? '').replace(/[&<>"']/g, char => ({
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#39;'
            }[char]));
        }
        function escapeAttr(value) {
            return escapeHtml(value);
        }
        function normalizeDelayBounds(min, max, disabled = false, restoreMin = null, restoreMax = null) {
            const fallbackMin = Number.isFinite(Number(restoreMin)) ? Number(restoreMin) : 1.6;
            const fallbackMax = Number.isFinite(Number(restoreMax)) ? Number(restoreMax) : 3.7;
            if (disabled) return { min: 0, max: 0, restoreMin: fallbackMin, restoreMax: fallbackMax, disabled: true };
            const left = Math.max(0, Number.isFinite(Number(min)) ? Number(min) : fallbackMin);
            let right = Math.max(0, Number.isFinite(Number(max)) ? Number(max) : fallbackMax);
            if (left > right) right = left;
            return { min: left, max: right, restoreMin: left, restoreMax: right, disabled: false };
        }
        function setDelayControls(settings) {
            if (!els.turnDelayMin || !els.turnDelayMax) return;
            const disabled = Boolean(settings.disabled);
            const restoreMin = Number.isFinite(Number(settings.restoreMin)) ? Number(settings.restoreMin) : Number(settings.restore_min);
            const restoreMax = Number.isFinite(Number(settings.restoreMax)) ? Number(settings.restoreMax) : Number(settings.restore_max);
            els.turnDelayMin.value = String(settings.min);
            els.turnDelayMax.value = String(settings.max);
            els.turnDelayMin.dataset.restoreValue = String(Number.isFinite(restoreMin) ? restoreMin : settings.min);
            els.turnDelayMax.dataset.restoreValue = String(Number.isFinite(restoreMax) ? restoreMax : settings.max);
            // Non-safe speed levels disable inter-turn pacing -> grey out the inputs.
            els.turnDelayMin.disabled = disabled;
            els.turnDelayMax.disabled = disabled;
        }
        // Highlights the active speed option inside the Tempt Fate popover.
        function markActiveSpeed(level) {
            state.speedLevel = level || 'safe';
            document.querySelectorAll('#tempt-fate-panel .speed-option').forEach(btn => {
                btn.classList.toggle('is-active', btn.dataset.speed === level);
            });
            // v3: TEMPT FATE button is green on Safe, red on every other speed
            // (the green-base / red-.is-active styling for these buttons already
            // exists in styles.css).
            if (els.temptFateBtn) {
                els.temptFateBtn.classList.toggle('is-active', state.speedLevel !== 'safe');
            }
        }
        // Speed options (inside the Tempt Fate popover; replaces the old dropdown).
        // Posts the level to the backend, which sets both inter-turn pacing and the
        // client call floor.
        async function applySpeed(level) {
            try {
                const data = await apiJson('/api/settings/speed', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ level })
                });
                markActiveSpeed(data.level || level);
                const restoreMin = Number(els.turnDelayMin?.dataset.restoreValue || 1.6);
                const restoreMax = Number(els.turnDelayMax?.dataset.restoreValue || 3.7);
                setDelayControls(data.disabled
                    ? normalizeDelayBounds(0, 0, true, restoreMin, restoreMax)
                    : normalizeDelayBounds(restoreMin, restoreMax, false));
            } catch (e) {}
        }
        async function loadSpeed() {
            try {
                const data = await apiJson('/api/settings/speed');
                markActiveSpeed(data.level || 'safe');
            } catch (e) {}
        }
        async function saveDelaySettings(settings) {
            setDelayControls(settings);
            const data = await apiJson('/api/settings/turn-delay', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });
            const normalized = normalizeDelayBounds(data.min, data.max, data.disabled, data.restore_min, data.restore_max);
            setDelayControls(normalized);
            writeLocalSetting(delaySettingsStorageKey, normalized);
        }
        async function loadDelaySettings() {
            if (!els.turnDelayMin || !els.turnDelayMax) return;
            try {
                const data = await apiJson('/api/settings/turn-delay');
                setDelayControls(normalizeDelayBounds(data.min, data.max, data.disabled, data.restore_min, data.restore_max));
            } catch (e) {
                setDelayControls({ min: 1.6, max: 3.7, restoreMin: 1.6, restoreMax: 3.7, disabled: false });
            }
        }
        // Retry options (carats + max clocks/career) — the Burn-Clocks button is the
        // single source of truth for retries; these two sub-controls live under it.
        function syncRetryOptionControls() {
            if (els.retryCaratsToggle) els.retryCaratsToggle.checked = !!state.caratsEnabled;
            if (els.retryMaxClocks) els.retryMaxClocks.value = String(state.maxClocksPerCareer || 0);
        }
        function bindRetryOptions() {
            if (els.retryOptionsBtn && els.retryOptionsPanel) {
                els.retryOptionsBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const open = els.retryOptionsPanel.style.display !== 'none';
                    els.retryOptionsPanel.style.display = open ? 'none' : 'flex';
                });
                els.retryOptionsPanel.addEventListener('click', (e) => e.stopPropagation());
                document.addEventListener('click', () => {
                    if (els.retryOptionsPanel) els.retryOptionsPanel.style.display = 'none';
                });
            }
            if (els.retryCaratsToggle) {
                els.retryCaratsToggle.addEventListener('change', () => {
                    state.caratsEnabled = !!els.retryCaratsToggle.checked;
                    localStorage.setItem('uma_retry_carats', String(state.caratsEnabled));
                });
            }
            if (els.retryMaxClocks) {
                els.retryMaxClocks.addEventListener('input', () => {
                    state.maxClocksPerCareer = Math.max(0, Number(els.retryMaxClocks.value) || 0);
                    localStorage.setItem('uma_retry_max_clocks', String(state.maxClocksPerCareer));
                });
            }
            syncRetryOptionControls();
        }
        function bindDelayControls() {
            if (!els.turnDelayMin || !els.turnDelayMax) return;
            const sync = () => {
                saveDelaySettings(normalizeDelayBounds(els.turnDelayMin.value, els.turnDelayMax.value, false));
            };
            els.turnDelayMin.addEventListener('input', sync);
            els.turnDelayMax.addEventListener('input', sync);
            // Tempt Fate popover: toggles the speed + custom-delay panel below the button.
            if (els.temptFateBtn && els.temptFatePanel) {
                els.temptFateBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const open = els.temptFatePanel.style.display !== 'none';
                    els.temptFatePanel.style.display = open ? 'none' : 'flex';
                    if (!open) loadSpeed();
                });
                els.temptFatePanel.addEventListener('click', (e) => e.stopPropagation());
                document.querySelectorAll('#tempt-fate-panel .speed-option').forEach(btn => {
                    btn.addEventListener('click', () => {
                        const level = btn.dataset.speed;
                        markActiveSpeed(level);
                        applySpeed(level);
                    });
                });
                document.addEventListener('click', () => {
                    if (els.temptFatePanel) els.temptFatePanel.style.display = 'none';
                });
                loadSpeed();
            }
            bindRetryOptions();
            loadDelaySettings();
        }
        window.addEventListener('storage', event => {
            if (event.key !== delaySettingsStorageKey || !event.newValue) return;
            const settings = readLocalSetting(event.newValue);
            if (settings) setDelayControls(normalizeDelayBounds(settings.min, settings.max, settings.disabled, settings.restoreMin, settings.restoreMax));
        });
        window.addEventListener('storage', event => {
            if (event.key !== burnClocksStorageKey || !event.newValue) return;
            setBurnClocks(readLocalSetting(event.newValue, false));
        });
        let _loginCooldownTimer = null;
        let _loginCooldownActive = false;
        // After a failed login/2FA attempt, briefly lock the button so rapid retries
        // don't deepen Steam's own rate limit (which is what triggers RateLimitExceeded).
        function applyLoginCooldown(seconds) {
            seconds = Math.max(0, Math.floor(Number(seconds) || 0));
            if (!seconds) return;
            if (_loginCooldownTimer) clearInterval(_loginCooldownTimer);
            const btn = els.loginBtn;
            const label = state.needs2fa ? 'VALIDATE' : 'LOGIN';
            let remaining = seconds;
            _loginCooldownActive = true;
            btn.disabled = true;
            const tick = () => {
                if (remaining <= 0) {
                    clearInterval(_loginCooldownTimer);
                    _loginCooldownTimer = null;
                    _loginCooldownActive = false;
                    btn.disabled = false;
                    btn.innerText = label;
                    return;
                }
                btn.innerText = 'WAIT ' + remaining + 's';
                remaining--;
            };
            tick();
            _loginCooldownTimer = setInterval(tick, 1000);
        }
        function resetLoginState() {
            state.isLoading = false;
            if (!_loginCooldownActive) els.loginBtn.innerText = state.needs2fa ? 'VALIDATE' : 'LOGIN';
        }
        function showLoginError(message, cooldownSeconds) {
            setLoadingScreen(false);
            // Show the real server/exception detail (was uppercased + defaulted to
            // "FAIL", which hid the actual reason on the most failure-prone screen).
            els.errorMsg.innerText = String(message || 'Login failed — please retry');
            els.errorMsg.style.display = 'block';
            resetLoginState();
            applyLoginCooldown(cooldownSeconds);
        }
        function showTwoFactorPrompt() {
            setLoadingScreen(false);
            state.needs2fa = true;
            state.isLoading = false;
            els.standardFields.style.display = 'none';
            els.faFields.style.display = 'block';
            els.loginBtn.innerText = 'VALIDATE';
            els.errorMsg.innerText = 'Enter your authenticator code';
            els.errorMsg.style.display = 'block';
            // Auto-focus the 2FA code input so the user can type immediately.
            const _codeInput = document.getElementById('code');
            if (_codeInput) { _codeInput.focus(); try { _codeInput.select(); } catch (e) {} }
        }
        function readLoginPayload() {
            return {
                username: document.getElementById('username').value,
                password: document.getElementById('password').value,
                code: document.getElementById('code').value
            };
        }
        function resetSelection() {
            selection.deck = null;
            selection.friend = null;
            selection.trainee = null;
            selection.veterans = [];
            selection.guestParents = [];
            state.selectedTraineeProfile = null;
            state.trackblazerPlan = null;
        }

        function clearFinishedSetupState({ clearSelection = true, syncServer = true } = {}) {
            if (state.account) {
                state.account = { ...state.account, career: null };
            }
            if (dashData && dashData.account) {
                dashData.account = { ...dashData.account, career: null };
            }

            if (clearSelection) {
                resetSelection();
                document
                    .querySelectorAll('.deck-container.selected, #uma-grid .grid-card.selected, #parent-grid .grid-card.selected, #friend-grid .grid-card.selected, #parent-grid .grid-card.vet-disabled, #guest-parent-grid .guest-parent-card.selected')
                    .forEach(el => el.classList.remove('selected', 'vet-disabled'));
                if (syncServer) syncSelectionToServer();
            }

            renderTeamPanel();
            renderAccountStrip(state.account);
            syncStartButton();

            if (els.friendRefreshBtn) {
                els.friendRefreshBtn.disabled = false;
            }
            if (els.friendStatus) {
                els.friendStatus.classList.remove('error');
                els.friendStatus.innerText = clearSelection
                    ? 'Career finished. Setup unlocked; refresh friends to choose a new support.'
                    : 'Career finished. Waiting for next loop start.';
            }
        }
        function hideBrokenImage(img) {
            img.onerror = null;
            img.style.display = 'none';
        }
        const loginForm = document.getElementById('login-form');
        loginForm.addEventListener('submit', async event => {
            event.preventDefault();
            if (state.isLoading || _loginCooldownActive) return;
            state.isLoading = true;
            setLoadingScreen(true);
            els.loginBtn.innerText = 'WORKING...';
            els.errorMsg.style.display = 'none';
            const payload = readLoginPayload();
            try {
                const data = await apiJson('/api/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                if (data.needs_2fa) {
                    showTwoFactorPrompt();
                } else if (data.success) {
                    localStorage.setItem('saved_username', payload.username);
                    localStorage.setItem('saved_password', payload.password);
                    await renderDashboard(data, { animateIntro: true, waitForIntro: true });
                    state.isLoading = false;
                } else {
                    showLoginError(data.detail || 'Login failed', data.cooldown_seconds);
                }
            } catch (e) {
                showLoginError('Network error: ' + ((e && e.message) ? e.message : 'could not reach the server'), 5);
            }
        });

        els.logoutBtn.addEventListener('click', async () => {
            setLoadingScreen(false);
            try {
                await apiJson('/api/logout', { method: 'POST' });
            } catch (e) {}
            document.body.classList.remove('dashboard-mode');
            hideNavbar();
            els.loginView.style.display = 'flex';
            els.dashboardView.style.display = 'none';
            els.dashboardView.classList.remove('active');
            els.logoutBtn.style.display = 'none';
            els.standardFields.style.display = 'block';
            els.faFields.style.display = 'none';
            els.loginBtn.innerText = 'LOGIN';
            els.accountStrip.style.display = 'none';
            els.accountStrip.innerHTML = '';
            state.account = null;
            state.needs2fa = false;
            dashData = null;
            resetSelection();
            syncDashboardHeight();
            loginForm.reset();
        });

        const formatNumber = value => Number(value || 0).toLocaleString();

        // Compact formatter for large navbar resources (e.g. GOLD):
        // >= 1,000,000 -> "1M" / "1.1M"  |  >= 100,000 -> "100k"  |  else full with commas.
        const formatCompact = value => {
            const n = Number(value || 0);
            if (n >= 1000000) {
                const m = Math.round((n / 1000000) * 10) / 10;
                return (m % 1 === 0 ? m.toFixed(0) : m.toFixed(1)) + 'M';
            }
            if (n >= 100000) {
                return Math.floor(n / 1000) + 'k';
            }
            return Number(value || 0).toLocaleString();
        };

        function formatHistoryTime(value) {
            if (!value) return '';
            try {
                return new Date(Number(value) * 1000).toLocaleString();
            } catch (e) {
                return '';
            }
        }

        function formatHistoryStats(stats = {}) {
            const pairs = [
                ['SPD', stats.speed],
                ['STA', stats.stamina],
                ['PWR', stats.power],
                ['GUT', stats.guts],
                ['WIT', stats.wit],
                ['SP', stats.skill_point],
            ];
            return pairs.map(([label, value]) => `<span><b>${label}</b> ${escapeHtml(formatNumber(value || 0))}</span>`).join('');
        }

        const HISTORY_STAT_LABELS = [
            ['speed', 'Speed', 'SPD'],
            ['stamina', 'Stamina', 'STA'],
            ['power', 'Power', 'POW'],
            ['guts', 'Guts', 'GUT'],
            ['wit', 'Wit', 'WIT'],
        ];
        const HISTORY_APTITUDE_GROUPS = [
            ['track', 'Track', [['turf', 'Turf'], ['dirt', 'Dirt']]],
            ['distance', 'Distance', [['sprint', 'Sprint'], ['mile', 'Mile'], ['medium', 'Medium'], ['long', 'Long']]],
            ['style', 'Style', [['front', 'Front'], ['pace', 'Pace'], ['late', 'Late'], ['end', 'End']]],
        ];
        const HISTORY_GRADE_ORDER = ['G', 'F', 'E', 'D', 'C', 'C+', 'B', 'B+', 'A', 'A+', 'S', 'S+', 'SS', 'SS+'];

        function historyGradeClass(value) {
            const clean = String(value || '').toUpperCase().replace(/[^A-Z+]/g, '') || 'G';
            return `grade-${clean.toLowerCase().replace('+', 'plus')}`;
        }

        function historyStatGrade(value) {
            const n = Number(value || 0);
            if (n >= 1200) return 'SS';
            if (n >= 1100) return 'S';
            if (n >= 1000) return 'A+';
            if (n >= 900) return 'A';
            if (n >= 800) return 'B+';
            if (n >= 700) return 'B';
            if (n >= 600) return 'C+';
            if (n >= 500) return 'C';
            if (n >= 400) return 'D+';
            if (n >= 300) return 'D';
            if (n >= 200) return 'E';
            if (n >= 100) return 'F';
            return 'G';
        }

        function historyRankFromRating(row = {}) {
            const explicit = row.career_rank || row.rank || row.evaluation_rank || row.rating_rank || '';
            if (explicit) return String(explicit).toUpperCase();
            const rating = Number(row.rating || 0);
            if (!rating) return '—';
            if (rating >= 30000) return 'UF';
            if (rating >= 24000) return 'UE';
            if (rating >= 20000) return 'UG';
            if (rating >= 17000) return 'SS+';
            if (rating >= 14500) return 'SS';
            if (rating >= 13000) return 'S+';
            if (rating >= 12000) return 'A+';
            if (rating >= 10000) return 'A';
            if (rating >= 8000) return 'B+';
            if (rating >= 6500) return 'B';
            if (rating >= 5000) return 'C+';
            if (rating >= 3500) return 'C';
            return 'D';
        }

        function historyGradeBadge(value, extraClass = '') {
            const text = value === undefined || value === null || value === '' ? '—' : String(value).toUpperCase();
            return `<span class="v58-grade-badge ${historyGradeClass(text)} ${extraClass}">${escapeHtml(text)}</span>`;
        }

        function historySparkStars(count = 0) {
            const n = Math.max(0, Math.min(3, Number(count || 0)));
            return `<span class="v58-spark-stars" aria-label="${n} of 3 stars">${[1,2,3].map(i => `<span class="${i <= n ? 'filled' : 'empty'}">★</span>`).join('')}</span>`;
        }

        function historySparkCategoryClass(category = '') {
            const clean = String(category || '').toLowerCase();
            if (clean.includes('stat')) return 'spark-stat';
            if (clean.includes('aptitude')) return 'spark-aptitude';
            if (clean.includes('unique') || clean.includes('scenario')) return 'spark-unique';
            if (clean.includes('skill')) return 'spark-skill';
            if (clean.includes('race')) return 'spark-race';
            return 'spark-other';
        }

        function historyPortraitUrl(row = {}) {
            const explicit = row.portrait_url || row.image_url || '';
            if (explicit) return explicit;
            const card = row.card_id || row.trainee_card_id || '';
            return card ? `/api/images/${encodeURIComponent(String(card))}.png` : '/sweep.png';
        }

        function renderHistoryStatsBadges(stats = {}, compact = false) {
            return HISTORY_STAT_LABELS.map(([key, label, short]) => {
                const raw = stats[key] || 0;
                const grade = historyStatGrade(raw);
                return `<div class="v58-stat-pill ${compact ? 'compact' : ''}">
                    <span class="stat-name">${escapeHtml(compact ? short : label)}</span>
                    ${historyGradeBadge(grade)}
                    <span class="stat-value">${escapeHtml(formatNumber(raw || 0))}</span>
                </div>`;
            }).join('');
        }

        function renderHistoryAptitudeRows(aptitudes = {}, compact = false) {
            return HISTORY_APTITUDE_GROUPS.map(([groupKey, groupLabel, items]) => {
                const group = aptitudes[groupKey] || {};
                const chips = items.map(([key, label]) => {
                    const value = group[key] || '—';
                    return `<span class="v58-apt-chip ${compact ? 'compact' : ''}"><b>${escapeHtml(label)}</b>${historyGradeBadge(value)}</span>`;
                }).join('');
                return `<div class="v58-apt-row"><span class="apt-group">${escapeHtml(groupLabel)}</span><div>${chips}</div></div>`;
            }).join('');
        }

        function renderHistorySparkChips(sparks = [], limit = 6) {
            if (!Array.isArray(sparks) || !sparks.length) return '<span class="muted">No spark data recorded</span>';
            const shown = sparks.slice(0, limit);
            const hidden = sparks.length - shown.length;
            return shown.map(spark => `<span class="v58-spark-chip ${historySparkCategoryClass(spark.category)}">
                <span>${escapeHtml(spark.name || 'Unknown Spark')}</span>
                ${historySparkStars(spark.stars)}${spark.initial_points ? `<small class="v58-spark-points">+${escapeHtml(spark.initial_points)} pts</small>` : ''}
            </span>`).join('') + (hidden > 0 ? `<span class="v58-spark-more">+${hidden} more</span>` : '');
        }

        function historySkillGroups(row = {}) {
            const groups = row.skills_grouped || row.skills || {};
            if (Array.isArray(groups)) return { Skills: groups };
            if (groups && typeof groups === 'object') return groups;
            return {};
        }

        function renderHistorySkillGroups(row = {}) {
            const groups = historySkillGroups(row);
            const entries = Object.entries(groups).filter(([, skills]) => Array.isArray(skills) && skills.length);
            if (!entries.length) return '<div class="v58-empty-panel">No skill snapshot recorded.</div>';
            return entries.map(([groupName, skills]) => `<section class="v58-skill-group">
                <h4>${escapeHtml(groupName)}</h4>
                <div class="v58-skill-list">
                    ${skills.map(skill => {
                        const name = typeof skill === 'string' ? skill : (skill.name || `Skill ${skill.skill_id || ''}`);
                        const rarity = typeof skill === 'object' ? (skill.rarity || '') : '';
                        return `<span class="v58-skill-pill ${rarity ? `rarity-${escapeAttr(rarity)}` : ''}">${escapeHtml(name)}</span>`;
                    }).join('')}
                </div>
            </section>`).join('');
        }

        function renderHistoryMetaRows(row = {}) {
            const fields = [
                ['Career Record', `${formatNumber(row.races || row.race_count || 0)} races / ${formatNumber(row.wins || 0)} wins`],
                ['Career Grade', row.career_grade || row.chara_grade || 'Unknown'],
                ['Fans Earned', formatNumber(row.fans_gained || 0)],
                ['Final Fans', formatNumber(row.fans_final || 0)],
                ['Major Wins', row.major_wins || row.major_win_summary || 'Unknown'],
                ['Career Scenario', row.scenario || row.career_scenario || 'Unknown'],
                ['Rating', row.rating ? formatNumber(row.rating) : 'Unknown'],
                ['Date Acquired', row.date_acquired || row.finished_date || formatHistoryTime(row.finished_at) || 'Unknown'],
            ];
            return fields.map(([label, value]) => `<div class="v58-info-row"><span>${escapeHtml(label)}</span><b>${escapeHtml(value)}</b></div>`).join('');
        }

        function historySearchBlob(row = {}) {
            const chunks = [row.trainee, row.title, row.scenario, row.career_rank, row.rating, row.major_wins, row.career_grade];
            (row.sparks || []).forEach(s => chunks.push(s.name, s.category));
            Object.values(historySkillGroups(row)).forEach(list => (list || []).forEach(skill => chunks.push(typeof skill === 'string' ? skill : skill.name)));
            return chunks.filter(Boolean).join(' ').toLowerCase();
        }

        function sortedCareerHistoryRows(rows = []) {
            const h = getCareerHistoryEls();
            const sort = h.sort ? h.sort.value : 'newest';
            const query = h.search ? h.search.value.trim().toLowerCase() : '';
            let filtered = query ? rows.filter(row => historySearchBlob(row).includes(query)) : [...rows];
            const num = (row, key) => Number(row[key] || 0);
            filtered.sort((a, b) => {
                if (sort === 'rating') return num(b, 'rating') - num(a, 'rating');
                if (sort === 'fans') return num(b, 'fans_gained') - num(a, 'fans_gained');
                if (sort === 'wins') return num(b, 'wins') - num(a, 'wins');
                if (sort === 'name') return String(a.trainee || '').localeCompare(String(b.trainee || ''));
                return Number(b.finished_at || 0) - Number(a.finished_at || 0);
            });
            return filtered;
        }

        function renderCareerHistoryCards(rows = []) {
            const h = getCareerHistoryEls();
            const careers = sortedCareerHistoryRows(rows);
            if (!h.body) return;
            if (!careers.length) {
                h.body.innerHTML = `<div class="v543-history-empty">${rows.length ? 'No careers match the current search.' : 'No completed careers recorded this session.'}</div>`;
                return;
            }
            h.body.innerHTML = careers.map((row, idx) => {
                const rank = historyRankFromRating(row);
                const title = row.title ? `[${row.title}] ` : '';
                return `<article class="v58-career-card" data-run-id="${escapeAttr(row.run_id || row.index || idx)}">
                    <div class="v58-career-portrait"><img src="${escapeAttr(historyPortraitUrl(row))}" alt="${escapeAttr(row.trainee || 'Trainee')}" onerror="this.src='/sweep.png'"></div>
                    <div class="v58-career-main">
                        <div class="v58-card-title-row">
                            <div><h3>${escapeHtml(title)}${escapeHtml(row.trainee || 'Unknown Trainee')}</h3><p>${escapeHtml(row.scenario || row.career_scenario || 'Scenario unknown')} · ${escapeHtml(formatHistoryTime(row.finished_at) || '')}</p></div>
                            <div class="v58-rank-stack"><span class="v58-rank-badge ${historyGradeClass(rank)}">${escapeHtml(rank)}</span><small>Rating ${escapeHtml(row.rating ? formatNumber(row.rating) : 'Unknown')}</small></div>
                        </div>
                        <div class="v58-card-metrics">
                            <span><b>${escapeHtml(formatNumber(row.fans_gained || 0))}</b> fans</span>
                            <span><b>${escapeHtml(formatNumber(row.races || row.race_count || 0))}</b> races</span>
                            <span><b>${escapeHtml(formatNumber(row.wins || 0))}</b> wins</span>
                            <span><b>${escapeHtml(row.career_grade || 'Unknown')}</b> career grade</span>
                            <span><b>${escapeHtml(row.major_wins || 'Unknown')}</b> major wins</span>
                        </div>
                        <div class="v58-card-grid">
                            <div><h4>Final Stats</h4><div class="v58-stat-grid compact">${renderHistoryStatsBadges(row.stats || {}, true)}</div></div>
                            <div><h4>Aptitudes</h4><div class="v58-apt-grid compact">${renderHistoryAptitudeRows(row.aptitudes || {}, true)}</div></div>
                        </div>
                        <div class="v58-spark-strip"><h4>Sparks</h4><div>${renderHistorySparkChips(row.sparks || [], 8)}</div></div>
                    </div>
                    <button class="btn btn-sm v58-view-career-btn" type="button" data-run-id="${escapeAttr(row.run_id || row.index || idx)}">VIEW DETAILS</button>
                </article>`;
            }).join('');
            h.body.querySelectorAll('.v58-career-card, .v58-view-career-btn').forEach(el => {
                el.addEventListener('click', event => {
                    const runId = el.dataset.runId || el.closest('.v58-career-card')?.dataset.runId;
                    if (runId) openCareerDetail(runId);
                    event.stopPropagation();
                });
            });
        }

        async function loadCareerHistory() {
            const h = getCareerHistoryEls();
            if (!h.body) return;
            try {
                const data = await apiJson('/api/career/history');
                const careers = Array.isArray(data.careers) ? data.careers : [];
                state.careerHistoryRows = careers;
                if (h.summary) {
                    const totalFans = careers.reduce((sum, row) => sum + Number(row.fans_gained || 0), 0);
                    const best = careers.reduce((max, row) => Math.max(max, Number(row.rating || 0)), 0);
                    h.summary.textContent = careers.length
                        ? `${careers.length} completed career${careers.length === 1 ? '' : 's'} this session · ${formatNumber(totalFans)} fans gained · best rating ${best ? formatNumber(best) : 'unknown'}`
                        : 'No completed careers yet. This list is cleared when python main.py is restarted.';
                }
                renderCareerHistoryCards(careers);
            } catch (e) {
                h.body.innerHTML = `<div class="v543-history-empty">Failed to load career history: ${escapeHtml(e.message || e)}</div>`;
            }
        }

        function getCareerHistoryEls() {
            return {
                btn: els.v543CareerHistoryBtn || document.getElementById('v543-career-history-btn'),
                modal: els.v543CareerHistoryModal || document.getElementById('v543-career-history-modal'),
                done: els.v543CareerHistoryDoneBtn || document.getElementById('v543-career-history-done-btn'),
                summary: els.v543CareerHistorySummary || document.getElementById('v543-career-history-summary'),
                body: els.v543CareerHistoryBody || document.getElementById('v543-career-history-body'),
                search: document.getElementById('v543-career-history-search'),
                sort: document.getElementById('v543-career-history-sort'),
                detailModal: document.getElementById('v543-career-detail-modal'),
                detailBody: document.getElementById('v543-career-detail-body'),
                detailTitle: document.getElementById('v543-career-detail-title'),
                detailSubtitle: document.getElementById('v543-career-detail-subtitle'),
                detailBack: document.getElementById('v543-career-detail-back-btn'),
                detailDone: document.getElementById('v543-career-detail-done-btn'),
            };
        }

        function openCareerHistoryModal() {
            const h = getCareerHistoryEls();
            if (h.modal) h.modal.style.display = 'flex';
            loadCareerHistory();
            loadCareerReport();
        }

        async function loadCareerReport() {
            const el = document.getElementById('v543-career-report');
            if (!el) return;
            try {
                const r = await apiJson('/api/career/report?t=' + Date.now());
                if (!r || !r.success || (!r.turns && !(r.stat_curve || []).length)) { el.style.display = 'none'; return; }
                const c = r.action_counts || {};
                const fs = r.final_stats || {};
                const fmt = (n) => Number(n || 0).toLocaleString();
                const stat = (k) => (fs[k] == null ? '–' : fmt(fs[k]));
                const mins = Math.round((r.runtime_seconds || 0) / 60);
                const trainBits = Object.entries(r.training_by_facility || {}).sort((a, b) => b[1] - a[1]).map(([k, v]) => `${escapeHtml(k)} ${v}`).join('  ·  ');
                const lowE = (r.low_energy_turns || []).length;
                el.style.display = '';
                el.innerHTML = `
                    <div class="v543-report-head">LIVE RUN MONITOR ${r.running ? '<span class="v543-report-live">LIVE</span>' : ''}</div>
                    <div class="v543-report-grid">
                        <div><span>Turns</span><strong>${fmt(r.turns)}</strong></div>
                        <div><span>Fans gained</span><strong>${fmt(r.fans_gained)}</strong></div>
                        <div><span>Fans / hr</span><strong>${fmt(r.fans_per_hour)}</strong></div>
                        <div><span>Runtime</span><strong>${mins}m</strong></div>
                        <div><span>Races</span><strong>${fmt(r.race_count)}</strong></div>
                        <div><span>Trainings</span><strong>${fmt(c.train || 0)}</strong></div>
                        <div><span>Rest / Rec</span><strong>${fmt((c.rest || 0) + (c.recreation || 0))}</strong></div>
                        <div><span>Server waits</span><strong>${fmt(r.recoveries || 0)}</strong></div>
                    </div>
                    <div class="v543-report-finalstats">SPD ${stat('speed')} &nbsp;·&nbsp; STA ${stat('stamina')} &nbsp;·&nbsp; PWR ${stat('power')} &nbsp;·&nbsp; GUT ${stat('guts')} &nbsp;·&nbsp; WIT ${stat('wit')}</div>
                    ${trainBits ? `<div class="v543-report-line">Training mix — ${trainBits}</div>` : ''}
                    ${lowE ? `<div class="v543-report-warn">⚠ ${lowE} turn(s) acted below 30 HP</div>` : ''}
                `;
            } catch (e) { el.style.display = 'none'; }
        }

        function historyRaceGradeLabel(grade) {
            const g = String(grade || '').trim().toUpperCase();
            if (g === '900' || g === '901') return 'Debut';
            if (g.startsWith('G')) return g;            // G1/G2/G3 already labeled
            if (g.startsWith('92') && g.length >= 5) return 'EX'; // Twinkle Star Climax 9200xx
            if (g === '100') return 'G1';
            if (g === '200') return 'G2';
            if (g === '300') return 'G3';
            if (g === '400' || g === '500' || g === '700' || g === '800') return 'OP';
            return g || '—';
        }
        function historyRaceGradeClass(grade) {
            const lbl = historyRaceGradeLabel(grade);
            if (lbl === 'G1') return 'rg-g1';
            if (lbl === 'G2') return 'rg-g2';
            if (lbl === 'G3') return 'rg-g3';
            if (lbl === 'EX') return 'rg-ex';
            if (lbl === 'Debut') return 'rg-debut';
            return 'rg-op';
        }
        function historyDistanceCategory(r) {
            const hint = r.performance_hint || {};
            if (hint.distance_label) return hint.distance_label;
            const m = Number(r.distance_m || 0);
            if (!m) return '';
            if (m <= 1400) return 'Sprint';
            if (m <= 1800) return 'Mile';
            if (m <= 2400) return 'Medium';
            return 'Long';
        }
        function historyOrdinal(rank) {
            const n = Number(rank || 0);
            if (!n) return '—';
            const v = n % 100;
            const s = ['th', 'st', 'nd', 'rd'];
            return n + (s[(v - 20) % 10] || s[v] || s[0]);
        }
        function renderHistoryRaceList(row) {
            const races = Array.isArray(row.race_results) ? [...row.race_results] : [];
            if (!races.length) return '<div class="v543-history-empty">No per-race data recorded for this career. (Older logs from before v6.7.23 may not include it.)</div>';
            races.sort((a, b) => Number(b.turn || 0) - Number(a.turn || 0)); // newest first, like the game
            const wins = races.filter(r => Number(r.rank || 99) === 1).length;
            const totalFans = races.reduce((s, r) => s + Number(r.fans || 0), 0);
            const winRate = races.length ? Math.round((wins / races.length) * 100) : 0;
            const zeroHp = races.filter(r => { const s = r.stat_snapshot || {}; return s.hp !== undefined && Number(s.hp) <= 0; }).length;
            const head = `<div class="v58-race-summary">
                <span><b>${races.length}</b> races</span>
                <span><b>${wins}</b> wins</span>
                <span><b>${winRate}%</b> win rate</span>
                <span><b>${formatNumber(totalFans)}</b> race fans</span>
                ${zeroHp ? `<span class="v58-race-warn">⚠ <b>${zeroHp}</b> raced at 0 energy</span>` : ''}
            </div>`;
            const cards = races.map(r => {
                const won = Number(r.rank || 99) === 1;
                const grade = historyRaceGradeLabel(r.grade);
                const gradeCls = historyRaceGradeClass(r.grade);
                const md = r.master_metadata || {};
                const hint = r.performance_hint || {};
                const snap = r.stat_snapshot || {};
                const venue = md.venue || '';
                const terrain = r.terrain || hint.surface_label || '';
                const dist = Number(r.distance_m || 0);
                const cat = historyDistanceCategory(r);
                const trackBits = [terrain, dist ? `${dist}m` : '', cat ? `(${cat})` : ''].filter(Boolean).join(' ');
                const trackLine = [venue, trackBits].filter(Boolean).join(' · ') || '—';
                const date = md.date || `Turn ${r.turn || '?'}`;
                const style = hint.running_style_label || '';
                const typeLabel = r.race_type === 'mandatory' ? 'mandatory'
                    : (r.race_type === 'solver_planned' ? 'solver-planned' : (r.race_type || ''));
                const hp = Number(snap.hp);
                const maxHp = Number(snap.max_hp || 100);
                const hasHp = snap.hp !== undefined && !isNaN(hp);
                const hpCls = hasHp ? (hp <= 0 ? 'hp-zero' : (hp <= 20 ? 'hp-low' : '')) : '';
                const hpHtml = hasHp ? `<span class="v58-race-hp ${hpCls}">HP ${hp}/${maxHp}</span>` : '';
                const statline = (snap.speed || snap.stamina || snap.power)
                    ? `SPD ${snap.speed || 0} · STA ${snap.stamina || 0} · PWR ${snap.power || 0} · GUT ${snap.guts || 0} · WIT ${snap.wit || 0}` : '';
                const placeCls = won ? 'place-win' : (Number(r.rank || 99) <= 3 ? 'place-podium' : 'place-loss');
                const clockHtml = Number(r.clocks_used || 0) > 0 ? `<span class="v58-race-clock">⏱ clock used</span>` : '';
                return `<div class="v58-race-card ${won ? 'is-win' : 'is-loss'}">
                    <div class="v58-race-head">
                        <span class="v58-grade-badge ${gradeCls}">${escapeHtml(grade)}</span>
                        <span class="v58-race-name">${escapeHtml(r.name || 'Unknown Race')}</span>
                        <span class="v58-race-place ${placeCls}">${escapeHtml(historyOrdinal(r.rank))}</span>
                    </div>
                    <div class="v58-race-track">${escapeHtml(trackLine)}</div>
                    <div class="v58-race-meta">
                        <span>${escapeHtml(date)}</span>
                        ${style ? `<span>${escapeHtml(style)}</span>` : ''}
                        ${typeLabel ? `<span class="v58-race-type">${escapeHtml(typeLabel)}</span>` : ''}
                        ${clockHtml}
                    </div>
                    <div class="v58-race-stats">
                        ${hpHtml}
                        ${statline ? `<span class="v58-race-statline">${escapeHtml(statline)}</span>` : ''}
                        <span class="v58-race-fans">${formatNumber(Number(r.fans || 0))} fans</span>
                    </div>
                </div>`;
            }).join('');
            return head + `<div class="v58-race-list">${cards}</div>`;
        }

        function openCareerDetail(runId) {
            const h = getCareerHistoryEls();
            const rows = state.careerHistoryRows || [];
            const row = rows.find(item => String(item.run_id || item.index) === String(runId));
            if (!row || !h.detailModal || !h.detailBody) return;
            const rank = historyRankFromRating(row);
            const title = row.title ? `[${row.title}] ` : '';
            if (h.detailTitle) h.detailTitle.textContent = `${title}${row.trainee || 'Unknown Trainee'}`;
            if (h.detailSubtitle) h.detailSubtitle.textContent = `${row.scenario || row.career_scenario || 'Scenario unknown'} · ${formatHistoryTime(row.finished_at) || 'Finished time unknown'}`;
            h.detailBody.innerHTML = `<div class="v58-detail-overview">
                <div class="v58-detail-portrait"><img src="${escapeAttr(historyPortraitUrl(row))}" alt="${escapeAttr(row.trainee || 'Trainee')}" onerror="this.src='/sweep.png'"></div>
                <div class="v58-detail-summary-card">
                    <div class="v58-detail-title-line"><div><h3>${escapeHtml(title)}${escapeHtml(row.trainee || 'Unknown Trainee')}</h3><p>${escapeHtml(row.card_id ? `Card ${row.card_id}` : '')}</p></div><span class="v58-rank-badge big ${historyGradeClass(rank)}">${escapeHtml(rank)}</span></div>
                    ${renderHistoryMetaRows(row)}
                </div>
            </div>
            <div class="v58-detail-two-col">
                <section class="v58-detail-panel"><h3>Final Stats</h3><div class="v58-stat-grid">${renderHistoryStatsBadges(row.stats || {}, false)}</div></section>
                <section class="v58-detail-panel"><h3>Aptitudes</h3><div class="v58-apt-grid">${renderHistoryAptitudeRows(row.aptitudes || {}, false)}</div></section>
            </div>
            <section class="v58-detail-panel"><h3>Race History</h3>${renderHistoryRaceList(row)}</section>
            <section class="v58-detail-panel"><h3>Sparks</h3><div class="v58-spark-detail-list">${renderHistorySparkChips(row.sparks || [], 999)}</div></section>
            <section class="v58-detail-panel"><h3>Skills</h3>${renderHistorySkillGroups(row)}</section>`;
            h.detailModal.style.display = 'flex';
        }

        function closeCareerDetail() {
            const h = getCareerHistoryEls();
            if (h.detailModal) h.detailModal.style.display = 'none';
        }

        function bindCareerHistoryControls() {
            const h = getCareerHistoryEls();
            if (h.btn && !h.btn.dataset.v543Bound) {
                h.btn.addEventListener('click', openCareerHistoryModal);
                h.btn.dataset.v543Bound = '1';
            }
            if (h.done && !h.done.dataset.v543Bound) {
                h.done.addEventListener('click', () => {
                    const current = getCareerHistoryEls();
                    if (current.modal) current.modal.style.display = 'none';
                    closeCareerDetail();
                });
                h.done.dataset.v543Bound = '1';
            }
            if (h.search && !h.search.dataset.v58Bound) {
                h.search.addEventListener('input', () => renderCareerHistoryCards(state.careerHistoryRows || []));
                h.search.dataset.v58Bound = '1';
            }
            if (h.sort && !h.sort.dataset.v58Bound) {
                h.sort.addEventListener('change', () => renderCareerHistoryCards(state.careerHistoryRows || []));
                h.sort.dataset.v58Bound = '1';
            }
            if (h.detailBack && !h.detailBack.dataset.v58Bound) {
                h.detailBack.addEventListener('click', closeCareerDetail);
                h.detailBack.dataset.v58Bound = '1';
            }
            if (h.detailDone && !h.detailDone.dataset.v58Bound) {
                h.detailDone.addEventListener('click', () => {
                    closeCareerDetail();
                    const current = getCareerHistoryEls();
                    if (current.modal) current.modal.style.display = 'none';
                });
                h.detailDone.dataset.v58Bound = '1';
            }
            if (h.detailModal && !h.detailModal.dataset.v58Bound) {
                h.detailModal.addEventListener('click', event => {
                    if (event.target === h.detailModal) closeCareerDetail();
                });
                h.detailModal.dataset.v58Bound = '1';
            }
            if (h.modal && !h.modal.dataset.v543Bound) {
                h.modal.addEventListener('click', event => {
                    if (event.target === h.modal) {
                        h.modal.style.display = 'none';
                        closeCareerDetail();
                    }
                });
                h.modal.dataset.v543Bound = '1';
            }
        }


        const TP_RECOVERY_LABELS = {
            potion_first: 'Items → Carrots',
            potion_only: 'Items Only',
            jewels_only: 'Carrots Only'
        };

        function normalizeTpRecoveryMode(mode) {
            return ['potion_first', 'potion_only', 'jewels_only'].includes(mode) ? mode : 'potion_first';
        }

        function tpRecoveryModeLabel(mode) {
            return TP_RECOVERY_LABELS[normalizeTpRecoveryMode(mode)] || TP_RECOVERY_LABELS.potion_first;
        }

        function setTpRecoveryModeLocal(mode, { persist = true } = {}) {
            state.tpRecoveryMode = normalizeTpRecoveryMode(mode);
            if (persist) localStorage.setItem('sweepy_tp_recovery_mode', state.tpRecoveryMode);
            const select = document.getElementById('tp-recovery-mode-select');
            if (select) select.value = state.tpRecoveryMode;
            const status = document.getElementById('tp-recovery-status');
            if (status) status.innerHTML = `<b>${escapeHtml(tpRecoveryModeLabel(state.tpRecoveryMode))}</b>`;
        }

        async function loadTpRecoveryMode() {
            try {
                const data = await apiJson('/api/settings/tp-recovery');
                if (data && data.mode) setTpRecoveryModeLocal(data.mode, { persist: true });
                const count = document.getElementById('tp-recovery-potion-count');
                if (count && data && data.potions !== null && data.potions !== undefined) count.textContent = formatNumber(data.potions || 0);
            } catch (e) {
                setTpRecoveryModeLocal(state.tpRecoveryMode, { persist: false });
            }
        }

        async function setTpRecoveryMode(mode) {
            const next = normalizeTpRecoveryMode(mode);
            setTpRecoveryModeLocal(next, { persist: true });
            try {
                const data = await apiJson('/api/settings/tp-recovery', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mode: next })
                });
                if (data && data.mode) setTpRecoveryModeLocal(data.mode, { persist: true });
            } catch (e) {
                console.warn('Failed to save TP recovery mode', e);
                if (els.startStatus) {
                    els.startStatus.innerText = `Failed to save TP recovery mode: ${e.message || e}`;
                    els.startStatus.classList.add('error');
                }
            }
        }

        function bindTopTpRecoveryControls() {
            const select = document.getElementById('tp-recovery-mode-select');
            if (select && !select.dataset.bound) {
                select.value = normalizeTpRecoveryMode(state.tpRecoveryMode);
                select.addEventListener('change', () => setTpRecoveryMode(select.value));
                select.dataset.bound = '1';
            }
            setTpRecoveryModeLocal(state.tpRecoveryMode, { persist: false });
        }

        loadTpRecoveryMode();

        function closeCareerModal() {
            els.careerModal.style.display = 'none';
            els.careerModalCopy.innerText = 'This will force-delete the ongoing career.';
            els.careerDeleteBtn.innerText = 'DELETE';
            state.isDeletingCareer = false;
        }
        function openCareerModal() {
            const career = state.account && state.account.career;
            if (!career || !career.active) return;
            els.careerModalCopy.innerText = 'This will force-delete the ongoing career.';
            els.careerModal.style.display = 'flex';
        }
        async function deleteCareer() {
            const career = state.account && state.account.career;
            if (!career || !career.active || state.isDeletingCareer) return;
            state.isDeletingCareer = true;
            els.careerDeleteBtn.innerText = 'DELETING';
            els.careerModalCopy.innerText = 'Deleting ongoing career...';
            try {
                const data = await apiJson('/api/career/delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ current_turn: career.turn || 0 })
                });
                if (!data.success) throw new Error(data.detail || 'Delete failed');
                renderAccountStrip(data.account);
                closeCareerModal();
            } catch (e) {
                els.careerModalCopy.innerText = e.message || 'Delete failed';
                els.careerDeleteBtn.innerText = 'RETRY';
                state.isDeletingCareer = false;
            }
        }
        els.careerCancelBtn.addEventListener('click', closeCareerModal);
        els.careerDeleteBtn.addEventListener('click', deleteCareer);
        els.careerModal.addEventListener('click', event => {
            if (event.target === els.careerModal) closeCareerModal();
        });
        function syncBurnClocksControls() {
            if (!els.burnClocksBtn) return;
            const clocks = state.account ? Number(state.account.clocks || 0) : 0;
            const disabled = clocks <= 11;

            if (disabled) {
                state.burnClocks = false;
                els.burnClocksBtn.disabled = true;
                els.burnClocksBtn.classList.remove('is-active');
                els.burnClocksBtn.innerText = `BURN CLOCKS: LOW (${clocks})`;
            } else {
                els.burnClocksBtn.disabled = false;
                els.burnClocksBtn.classList.toggle('is-active', state.burnClocks);
                els.burnClocksBtn.innerText = `BURN CLOCKS: ${state.burnClocks ? 'ON' : 'OFF'}`;
            }
        }
        function setBurnClocks(value, options = {}) {
            state.burnClocks = Boolean(value);
            syncBurnClocksControls();
            if (options.persist) writeLocalSetting(burnClocksStorageKey, state.burnClocks);
        }
        function loadStoredBurnClocks() {
            if (state.runner && state.runner.running) return;
            const stored = readLocalSetting(localStorage.getItem(burnClocksStorageKey));
            if (stored !== null) setBurnClocks(stored);
        }
        function syncFinalizeRunsBtn() {
            if (!els.finalizeRunsBtn) return;
            els.finalizeRunsBtn.classList.toggle('is-active', !!state.finalizeSingleRuns);
            els.finalizeRunsBtn.innerText = `FINISH RUN: ${state.finalizeSingleRuns ? 'ON' : 'OFF'}`;
        }
        function setFinalizeSingleRuns(value, options = {}) {
            state.finalizeSingleRuns = Boolean(value);
            syncFinalizeRunsBtn();
            if (options.persist) localStorage.setItem('uma_finalize_single_runs', String(state.finalizeSingleRuns));
        }
        els.finalizeRunsBtn?.addEventListener('click', () => setFinalizeSingleRuns(!state.finalizeSingleRuns, { persist: true }));
        syncFinalizeRunsBtn();

        function renderAccountStrip(account) {
            state.account = account || null;
            if (!account) {
                els.accountStrip.style.display = 'none';
                els.accountStrip.innerHTML = '';
                state._accountStripKey = null;
                return;
            }
            const tp = account.tp || {};
            const career = account.career;
            const careerHtml = career && career.active ? `
                <div id="career-pill" class="account-pill pill-career account-pill-clickable">
                    <span class="label">CAREER</span>
                    <strong>ONGOING</strong>
                </div>
            ` : `<div class="account-pill" style="opacity: 0.25;">
                    <span class="label">CAREER</span>
                    <strong>NONE</strong>
                </div>`;
            const carrots = account.carrots || {};
            const tpRecoveryMode = normalizeTpRecoveryMode((account.tp_recovery && account.tp_recovery.mode) || state.tpRecoveryMode);
            state.tpRecoveryMode = tpRecoveryMode;
            // Dirty-check (runs every 1.5s poll): skip the full innerHTML rebuild
            // when nothing affecting the strip changed, so the TP-recovery <select>
            // isn't wiped mid-selection. Mirrors renderMainActionLog's guard.
            const _stripKey = `${tp.current}|${tp.max}|${account.potions || 0}|${carrots.total}|${account.gold}|${account.clocks}|${career && career.active ? 1 : 0}|${tpRecoveryMode}`;
            if (_stripKey === state._accountStripKey) return;
            state._accountStripKey = _stripKey;
            const tpRecoveryOptions = [
                ['potion_first', 'Items → Carrots'],
                ['potion_only', 'Items Only'],
                ['jewels_only', 'Carrots Only']
            ].map(([value, label]) => `<option value="${value}" ${tpRecoveryMode === value ? 'selected' : ''}>${label}</option>`).join('');
            const tpRecoveryCard = `
                <div id="tp-recovery-toggle" class="account-pill pill-potion account-pill-tp-recovery" title="Umabot TP recovery: use item 32 first, item only, or Carrots only.">
                    <span class="label">TP POTIONS</span>
                    <strong id="tp-recovery-potion-count">${formatNumber(account.potions || 0)}</strong>
                    <select id="tp-recovery-mode-select" class="tp-recovery-mode-select" aria-label="TP recovery mode">${tpRecoveryOptions}</select>
                    <small id="tp-recovery-status"><b>${escapeHtml(tpRecoveryModeLabel(tpRecoveryMode))}</b></small>
                </div>`;
            els.accountStrip.innerHTML = `
                <div class="account-pill pill-tp">
                    <span class="label">TP</span>
                    <strong>${tp.current || 0}/${tp.max || 0}</strong>
                </div>
                ${tpRecoveryCard}
                <div class="account-pill pill-carrots">
                    <span class="label">CARROTS</span>
                    <strong>${formatNumber(carrots.total)}</strong>
                    <small>Fallback recovery</small>
                </div>
                <div class="account-pill pill-gold">
                    <span class="label">GOLD</span>
                    <strong>${formatCompact(account.gold)}</strong>
                </div>
                <div class="account-pill pill-clk">
                    <span class="label">CLOCKS</span>
                    <strong>${formatNumber(account.clocks)}</strong>
                </div>
                ${careerHtml}
            `;
            els.accountStrip.style.display = 'flex';
            const careerPill = document.getElementById('career-pill');
            if (careerPill) careerPill.addEventListener('click', openCareerModal);
            bindTopTpRecoveryControls();
            loadTpRecoveryMode();
            loadStoredBurnClocks();
            syncBurnClocksControls();
        }

        var _exportLogsBtn = document.getElementById('export-logs-btn');
        if (_exportLogsBtn) {
            _exportLogsBtn.addEventListener('click', () => {
                // GET endpoint returns the zip as an attachment -> browser downloads it.
                window.location.href = '/api/logs/export';
            });
        }
        els.burnClocksBtn.addEventListener('click', async () => {
            setBurnClocks(!state.burnClocks, { persist: true });
            if (state.runner && state.runner.running) {
                try {
                    const data = await apiJson('/api/career/runner/burn_clocks', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ burn_clocks: state.burnClocks })
                    });
                    if (!data.success) throw new Error(data.detail || 'Failed to update burn_clocks');
                    if (data.runner) applyRunnerSnapshot(data.runner);
                } catch (e) {
                    console.error("Failed to update burn_clocks mid-run", e);
                    if (state.runner && state.runner.burn_clocks !== undefined) {
                        setBurnClocks(state.runner.burn_clocks, { persist: true });
                    }
                }
            }
        });

        const rankMap = {
            1: 'G', 2: 'G+', 3: 'F', 4: 'F+', 5: 'E', 6: 'E+',
            7: 'D', 8: 'D+', 9: 'C', 10: 'C+', 11: 'B', 12: 'B+',
            13: 'A', 14: 'A+', 15: 'S', 16: 'S+', 17: 'SS', 18: 'SS+',
            19: 'UG', 20: 'UF', 21: 'UE', 22: 'UD'
        };
        let dashData = null;
        const selection = { deck: null, friend: null, trainee: null, veterans: [], guestParents: [] };

        function compactDeckForPreset(deck) {
            if (!deck) return null;
            return {
                id: deck.id,
                name: deck.name || (deck.id ? `Deck ${deck.id}` : ''),
                cards: (deck.cards || []).map(card => ({
                    id: card.id || card.support_card_id || card.card_id,
                    name: card.name || card.support_name || '',
                    type: card.type || '',
                    rarity: card.rarity || ''
                })).filter(card => card.id)
            };
        }

        function compactFriendForPreset(friend) {
            if (!friend) return null;
            return {
                viewer_id: friend.viewer_id,
                support_card_id: friend.support_card_id,
                support_name: friend.support_name || friend.name || '',
                type: friend.type || '',
                limit_break_count: friend.limit_break_count ?? friend.lb ?? null
            };
        }

        function compactTraineeForPreset(trainee) {
            if (!trainee) return null;
            return { id: trainee.id || trainee.card_id, name: trainee.name || trainee.chara_name || '' };
        }

        function compactOwnParentForPreset(parent) {
            if (!parent) return null;
            return {
                instance_id: parent.instance_id || parent.id,
                card_id: parent.card_id,
                name: parent.name || '',
                rank: parent.rank || ''
            };
        }

        function compactGuestParentForPreset(parent) {
            if (!parent) return null;
            return {
                viewer_id: parent.viewer_id,
                instance_id: parent.instance_id || parent.id || parent.trained_chara_id,
                id: parent.id || parent.instance_id || parent.trained_chara_id,
                card_id: parent.card_id,
                name: parent.name || '',
                trainer_name: parent.trainer_name || '',
                rank: parent.rank || '',
                source: parent.source || 'preset'
            };
        }

        function buildSelectionPresetSnapshot() {
            return {
                deck: compactDeckForPreset(selection.deck),
                friend: compactFriendForPreset(selection.friend),
                trainee: compactTraineeForPreset(selection.trainee),
                veterans: (selection.veterans || []).map(compactOwnParentForPreset).filter(Boolean),
                guestParents: (selection.guestParents || []).map(compactGuestParentForPreset).filter(Boolean)
            };
        }

        async function syncSelectionToServer() {
            try {
                const payload = {
                    deck: selection.deck,
                    friend: selection.friend,
                    trainee: selection.trainee,
                    veterans: selection.veterans,
                    guestParents: selection.guestParents || []
                };
                await apiJson('/api/selection', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ selection: payload })
                });
            } catch (e) {}
        }

        function deselect(action, idx) {
            if (action === 'deck') {
                document.querySelectorAll('.deck-container.selected').forEach(el => el.classList.remove('selected'));
                selection.deck = null;
            } else if (action === 'friend') {
                document.querySelectorAll('#friend-grid .grid-card.selected').forEach(el => el.classList.remove('selected'));
                selection.friend = null;
            } else if (action === 'trainee') {
                document.querySelectorAll('#uma-grid .grid-card.selected').forEach(el => el.classList.remove('selected'));
                selection.trainee = null;
            } else if (action === 'vet') {
                const vet = selection.veterans[idx];
                if (vet != null) {
                    const card = document.querySelectorAll('#parent-grid .grid-card')[vet._gridIdx];
                    if (card) card.classList.remove('selected');
                }
                selection.veterans.splice(idx, 1);
                updateVetSelectability();
            } else if (action === 'guest') {
                selection.guestParents = [];
                document.querySelectorAll('#guest-parent-grid .guest-parent-card.selected').forEach(el => el.classList.remove('selected'));
                updateVetSelectability();
                renderGuestParentsSection();
            }
            renderTeamPanel();
            updateTrackblazerPlanGate();
            syncSelectionToServer();
        }
        function selectedParentTotal() {
            return (selection.veterans || []).length + (selection.guestParents || []).filter(Boolean).length;
        }

        function parentSelectionRuleText() {
            return 'Choose either 2 own parents, or 1 own parent + 1 guest parent.';
        }

        function parentSelectionComboError() {
            const own = (selection.veterans || []).length;
            const guest = (selection.guestParents || []).filter(Boolean).length;
            if (own === 2 && guest === 0) return '';
            if (own === 1 && guest === 1) return '';
            if (own === 0 && guest === 0) return 'Select parents: 2 own, or 1 own + 1 guest';
            if (own === 1 && guest === 0) return 'Select one more parent: own or guest';
            if (own === 0 && guest === 1) return 'Guest parent requires one own parent';
            if (own === 0 && guest >= 2) return 'Select one own parent and only one guest parent';
            if (own >= 2 && guest > 0) return 'Guest parent cannot be combined with two own parents';
            if (own > 2) return 'Only two parents can be selected';
            if (guest > 1) return 'Only one guest parent can be selected';
            return parentSelectionRuleText();
        }

        function getStartMissingReason() {
            const activeCareer = state.account && state.account.career && state.account.career.active;
            if (!state.selectedPreset) return 'Select a preset';
            if (activeCareer) return '';
            if (!selection.deck) return 'Select a deck';
            if (!selection.friend) return 'Select a friend support';
            if (!selection.trainee) return 'Select a trainee';
            const comboError = parentSelectionComboError();
            if (comboError) return comboError;
            const parentPayload = selectedParentStartPayload();
            if (parentPayload.parent_selection_mode === 'own_guest' && (!parentPayload.rental_viewer_id || !parentPayload.rental_trained_chara_id)) {
                return 'Guest parent is missing viewer or trained character id. Refresh guest parents and select a full guest entry.';
            }
            if (parentPayload.parent_selection_mode === 'own_own' && (!parentPayload.parent_id_1 || !parentPayload.parent_id_2)) {
                return 'Select parents: 2 own, or 1 own + 1 guest';
            }
            const parentError = getParentSelectionError();
            if (parentError) return parentError;
            const hasGeneratedPlan = Boolean(state.trackblazerPlan && state.trackblazerPlan.extra_race_list && state.trackblazerPlan.extra_race_list.length);
            const hasManualRaces = Boolean((state.selectedRaces || []).length);
            if (!hasGeneratedPlan && !hasManualRaces && !state.autoPlanBeforeRun) return 'Generate a race plan or manually select at least one race';
            const tp = state.account && state.account.tp ? Number(state.account.tp.current || 0) : 0;
            if (state.account && tp < 30 && !state.devEnabled) return `Not enough TP: ${tp}/30`;
            return '';
        }
        function getParentLineageCards(parent) {
            if (!parent || !parent.tree) return [];
            return ['self', 'p1', 'p2', 'gp1', 'gp2', 'gp3', 'gp4']
                .map(key => Number(parent.tree[key] && parent.tree[key].card_id))
                .filter(Boolean);
        }
        function getParentSelectionError() {
            if (!selection.trainee) return '';
            const traineeId = Number(selection.trainee.id);
            const lineages = [...(selection.veterans || []), ...((selection.guestParents || []).filter(Boolean))].map(getParentLineageCards);
            if (lineages.length < 2) return '';
            if (lineages.some(cards => cards[0] === traineeId)) return 'Direct parent is trainee';
            return '';
        }
        function syncStartButton() {
            const reason = getStartMissingReason();
            els.startCareerBtn.disabled = Boolean(reason) || state.isStartingCareer;
            if (state.isStartingCareer) {
                els.startCareerBtn.innerText = 'RUNNING...';
                els.startStatus.innerText = 'Starting runner...';
                els.startStatus.classList.remove('error');
            } else {
                const activeCareer = state.account && state.account.career && state.account.career.active;
                els.startCareerBtn.innerText = activeCareer ? 'RESUME CAREER' : 'RUN CAREER';
                els.startStatus.innerText = reason;
                els.startStatus.classList.toggle('error', false);
            }
        }
        function selectedParentLineup() {
            const own = (selection.veterans || []).filter(Boolean).map((parent, idx) => ({ ...parent, _selectionKind: 'vet', _selectionIdx: idx }));
            const guest = (selection.guestParents || []).filter(Boolean).slice(0, 1).map((parent, idx) => ({ ...parent, _selectionKind: 'guest', _selectionIdx: idx }));
            if (guest.length) return own.slice(0, 1).concat(guest);
            return own.slice(0, 2);
        }

        function selectedParentStartPayload() {
            const own = (selection.veterans || []).filter(Boolean);
            const guest = (selection.guestParents || []).filter(Boolean)[0] || null;
            if (guest && own[0]) {
                return {
                    parent_id_1: Number(own[0].instance_id || 0),
                    parent_id_2: 0,
                    rental_viewer_id: Number(guest.viewer_id || 0),
                    rental_trained_chara_id: Number(guest.instance_id || guest.id || 0),
                    rental_card_id: Number(guest.card_id || 0),
                    parent_selection_mode: 'own_guest'
                };
            }
            return {
                parent_id_1: Number((own[0] || {}).instance_id || 0),
                parent_id_2: Number((own[1] || {}).instance_id || 0),
                rental_viewer_id: 0,
                rental_trained_chara_id: 0,
                rental_card_id: 0,
                parent_selection_mode: 'own_own'
            };
        }

        function renderTeamPanel() {
            document.getElementById('dashboard-view').classList.add('active');
            function setSlot(id, role, content, action, idx, emptyText = 'select') {
                const el = document.getElementById(id);
                el.className = content ? 'team-item filled' : 'team-item';
                el.onclick = content ? () => deselect(action, idx) : null;
                const clear = content ? '<span class="team-item-clear">clear</span>' : '';
                const empty = `<div class="team-item-empty">${emptyText}</div>`;
                el.innerHTML = `
                    <div class="team-item-head">
                        <span class="team-item-role">${role}</span>
                        ${clear}
                    </div>
                    ${content || empty}
                `;
            }
            if (selection.deck) {
                const thumbs = selection.deck.cards.map(c =>
                    `<img class="team-item-thumb" src="/api/images/${c.id || '10001'}.png" onerror="hideBrokenImage(this)">`
                ).join('');
                setSlot('team-slot-deck', 'Deck', `
                    <div class="team-item-body">
                        <div class="team-item-thumbs">${thumbs}</div>
                        <div class="team-item-text">
                            <span class="team-item-name">${selection.deck.name}</span>
                            <span class="team-item-sub">Slot ${selection.deck.id}</span>
                        </div>
                    </div>
                `, 'deck', null, 'select deck');
            } else {
                setSlot('team-slot-deck', 'Deck', null, 'deck', null, 'select deck');
            }
            if (selection.friend) {
                setSlot('team-slot-friend', 'Friend', `
                    <div class="team-item-body">
                        <img class="team-item-portrait" src="/api/images/${selection.friend.support_card_id || '10001'}.png" onerror="hideBrokenImage(this)">
                        <div class="team-item-text">
                            <span class="team-item-name">${selection.friend.support_name || 'Unknown'}</span>
                            <span class="team-item-sub">${selection.friend.type || '?'} | LB${selection.friend.limit_break_count ?? '?'}</span>
                        </div>
                    </div>
                `, 'friend', null, 'select friend');
            } else {
                setSlot('team-slot-friend', 'Friend', null, 'friend', null, 'select friend');
            }
            if (selection.trainee) {
                setSlot('team-slot-trainee', 'Trainee', `
                    <div class="team-item-body">
                        <img class="team-item-portrait" src="/api/images/${selection.trainee.id || '100101'}.png" onerror="hideBrokenImage(this)">
                        <div class="team-item-text">
                            <span class="team-item-name">${selection.trainee.name || 'Unknown'}</span>
                        </div>
                    </div>
                `, 'trainee', null, 'select trainee');
            } else {
                setSlot('team-slot-trainee', 'Trainee', null, 'trainee', null, 'select trainee');
            }
            const parentSlots = selectedParentLineup();
            ['team-slot-vet1', 'team-slot-vet2'].forEach((id, i) => {
                const parent = parentSlots[i];
                if (parent) {
                    const isGuest = parent._selectionKind === 'guest';
                    const action = isGuest ? 'guest' : 'vet';
                    const actionIdx = isGuest ? parent._selectionIdx : parent._selectionIdx;
                    const sub = isGuest
                        ? `Guest ${rankMap[parent.rank] || parent.rank || '??'}${parent.trainer_name ? ' | ' + escapeHtml(parent.trainer_name) : ''}`
                        : `${rankMap[parent.rank] || '??'}`;
                    setSlot(id, `Parent ${i + 1}`, `
                        <div class="team-item-body">
                            <img class="team-item-portrait" src="/api/images/${parent.card_id || '100101'}.png" onerror="hideBrokenImage(this)">
                            <div class="team-item-text">
                                <span class="team-item-name">${escapeHtml(parent.name || 'Unknown')}</span>
                                <span class="team-item-sub">${sub}</span>
                            </div>
                        </div>
                    `, action, actionIdx, 'select parent');
                } else {
                    setSlot(id, `Parent ${i + 1}`, null, 'vet', i, 'select parent');
                }
            });
            syncStartButton();
        }

        function guestParentKey(parent, idx = 0) {
            return String(parent.viewer_id || '') + ':' + String(parent.instance_id || parent.id || parent.card_id || idx);
        }

        function guestParentSelected(parent, idx = 0) {
            const key = guestParentKey(parent, idx);
            return (selection.guestParents || []).some((p, pIdx) => p && guestParentKey(p, pIdx) === key);
        }

        async function refreshGuestParents({ force = false } = {}) {
            const status = document.getElementById('guest-parent-status');
            const btn = document.getElementById('guest-parent-refresh-btn');
            if (!force && dashData.guestParentsLoaded) {
                renderGuestParentsSection();
                return;
            }
            if (status) status.textContent = 'Loading followed guest parents...';
            if (btn) {
                btn.disabled = true;
                btn.textContent = 'LOADING...';
            }
            // Force refresh starts from the first page. Reusing stale exclude ids can
            // request a later/empty page and make the button appear broken.
            const exclude = force ? [] : (dashData.guestParentExcludeIds || dashData.friendExcludeIds || []);
            try {
                const data = await apiJson('/api/career/guest_parents', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ exclude_viewer_ids: exclude, force_refresh: Boolean(force) })
                });
                if (!data.success) throw new Error(data.detail || 'Guest parent refresh failed');
                dashData.guestParents = data.guestParents || [];
                dashData.guestParentExcludeIds = data.exclude_viewer_ids || [];
                dashData.guestParentsLoaded = true;
                if (status) status.textContent = dashData.guestParents.length
                    ? `Loaded ${dashData.guestParents.length} guest/follow entries. Sources: ${((data.debug && data.debug.guest_paths_used) || []).slice(0, 3).join(', ') || 'auto-detected'}. ${parentSelectionRuleText()}`
                    : `No guest entries found. ${data.debug ? 'Searched keys: ' + (data.debug.top_level_keys || []).slice(0, 8).join(', ') : ''}`;
            } catch (e) {
                console.warn('Guest parent refresh failed', e);
                if (status) status.textContent = `Guest parent refresh failed: ${e.message || e}`;
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.textContent = 'REFRESH';
                }
            }
            renderGuestParentsSection();
        }

        function renderGuestParentCard(parent, idx) {
            const imgId = parent.card_id || '100101';
            const selected = guestParentSelected(parent, idx);
            const trainer = parent.trainer_name ? `<span class="grid-card-sub">${escapeHtml(parent.trainer_name)}</span>` : '';
            const incomplete = parent.incomplete ? '<span class="guest-incomplete-badge">FOLLOW</span>' : '';
            const source = parent.source ? `<span class="grid-card-sub source">${escapeHtml(String(parent.source).split(':')[0])}</span>` : '';
            return `<div class="grid-card guest-parent-card ${selected ? 'selected' : ''} ${parent.incomplete ? 'incomplete' : ''}" data-guest-index="${idx}" tabindex="0" aria-haspopup="dialog" aria-expanded="false">
                <div class="rank-badge">${parent.incomplete ? 'F' : (rankMap[parent.rank] || '??')}</div>
                ${incomplete}
                <img src="/api/images/${imgId}.png" onerror="hideBrokenImage(this)">
                <div class="sparks-tooltip" style="--spark-bg: url('/api/images/${imgId}.png')">
                    <div class="sparks-tooltip-title"></div>
                    <div class="sparks-tooltip-scroll">
                        <div class="sparks-lineage-grid">
                            ${renderParentSparks(parent, imgId)}
                        </div>
                    </div>
                </div>
                <div class="grid-card-overlay">
                    <span class="grid-card-kicker">ID: ${escapeHtml(parent.instance_id || parent.card_id || '?')}</span>
                    <span class="grid-card-name">${escapeHtml(parent.name || 'Unknown')}</span>
                    ${trainer}
                    ${source}
                </div>
            </div>`;
        }

        function selectGuestParent(parent, idx) {
            selection.guestParents = selection.guestParents || [];
            const key = guestParentKey(parent, idx);
            const existing = selection.guestParents.findIndex((p, pIdx) => p && guestParentKey(p, pIdx) === key);
            const status = document.getElementById('guest-parent-status');
            if (existing >= 0) {
                selection.guestParents.splice(existing, 1);
            } else {
                if ((selection.veterans || []).length >= 2) {
                    if (status) status.textContent = 'Guest parent cannot be selected with two own parents. Remove one own parent first.';
                    return;
                }
                if ((selection.veterans || []).length < 1) {
                    if (status) status.textContent = 'Select one own parent before choosing a guest parent.';
                    return;
                }
                const viewerId = Number(parent && parent.viewer_id || 0);
                const trainedId = Number(parent && (parent.instance_id || parent.id) || 0);
                if (!viewerId || !trainedId) {
                    if (status) status.textContent = 'This guest parent is missing the viewer/trained character ids needed to start a career. Click Refresh and choose a full guest entry.';
                    return;
                }
                selection.guestParents = [parent];
            }
            updateVetSelectability();
            renderGuestParentsSection();
            renderTeamPanel();
            syncSelectionToServer();
        }

        function renderGuestParentsSection() {
            const libraryGroup = document.getElementById('v516-library-group')
                || document.querySelector('.v516-library-group')
                || document.querySelector('#content-panel .panel-body')
                || document.querySelector('.panel-body');
            if (!libraryGroup) return;
            let section = document.getElementById('guest-parents-section');
            if (!section) {
                section = document.createElement('section');
                section.id = 'guest-parents-section';
                section.className = 'dashboard-section guest-parents-section';
                section.dataset.libSection = 'guests';
                section.innerHTML = `
                    <h2 class="dashboard-section-title section-title-toggle" id="guest-parents-toggle">
                        <span class="collapse-chevron expanded" id="guest-parents-chevron">&#9658;</span>
                        GUEST PARENTS
                        <button id="guest-parent-refresh-btn" class="btn btn-sm section-title-action" type="button">REFRESH</button>
                    </h2>
                    <div id="guest-parents-body" class="collapsible-body expanded">
                        <div id="guest-parent-grid" class="grid guest-parent-grid"></div>
                        <div id="guest-parent-status" class="guest-parent-status">Select up to two followed guest parents.</div>
                    </div>
                `;
                const parentHeader = Array.from(libraryGroup.querySelectorAll('h2,h3,.dashboard-section-title')).find(el => /parent/i.test(el.textContent || ''));
                const parentSection = parentHeader ? parentHeader.closest('section') || parentHeader.parentElement : null;
                if (parentSection) parentSection.insertAdjacentElement('afterend', section);
                else libraryGroup.appendChild(section);
                // v2.1: shown via the Library "Guest Parents" tab (no collapse).
                var _activeLibTab = document.querySelector('#lib-tabs .lib-tab.is-active');
                section.style.display = (_activeLibTab && _activeLibTab.dataset.libTab === 'guests') ? '' : 'none';
            }
            const grid = document.getElementById('guest-parent-grid');
            const status = document.getElementById('guest-parent-status');
            const guests = dashData.guestParents || [];
            if (!grid) return;

            if (!guests.length) {
                grid.innerHTML = `<div class="guest-parent-empty">No guest/follow entries loaded yet. Click Refresh to search guest, rental, follow, friend, and succession sources.</div>`;
            } else {
                grid.innerHTML = guests.map((parent, idx) => renderGuestParentCard(parent, idx)).join('');
                grid.querySelectorAll('.guest-parent-card').forEach(card => {
                    card.addEventListener('click', () => {
                        const idx = Number(card.dataset.guestIndex || 0);
                        selectGuestParent(guests[idx], idx);
                    });
                });
                bindSparkTooltips();
            }

            const selected = (selection.guestParents || []).filter(Boolean);
            if (status) {
                const own = (selection.veterans || []).length;
                status.textContent = selected.length
                    ? `Selected ${own} own + ${selected.length} guest parent. ${parentSelectionRuleText()}`
                    : `${parentSelectionRuleText()} Select one own parent before selecting a guest parent.`;
            }
            document.getElementById('guest-parent-refresh-btn')?.addEventListener('click', () => refreshGuestParents({ force: true }));
        }

                function updateVetSelectability() {
            const guestCount = (selection.guestParents || []).filter(Boolean).length;
            const ownLimit = guestCount > 0 ? 1 : 2;
            const full = selection.veterans.length >= ownLimit;
            document.querySelectorAll('#parent-grid .grid-card, #guest-parent-grid .guest-parent-card').forEach(card => {
                if (card.classList.contains('selected')) {
                    card.classList.remove('vet-full');
                } else {
                    card.classList.toggle('vet-full', full);
                }
            });
            syncStartButton();
        }
        function clampValue(value, min, max) {
            return Math.min(Math.max(value, min), max);
        }
        let activeSparkCard = null;
        let activeSparkTooltip = null;
        function positionSparkTooltip(card, tooltip = card.querySelector('.sparks-tooltip')) {
            if (!card || !tooltip) return;
            const rect = card.getBoundingClientRect();
            const tooltipRect = tooltip.getBoundingClientRect();
            const tooltipWidth = Math.min(tooltipRect.width || 620, window.innerWidth - 16);
            const tooltipHeight = tooltipRect.height || 320;
            const x = clampValue(rect.left + rect.width / 2, tooltipWidth / 2 + 8, window.innerWidth - tooltipWidth / 2 - 8);
            // v6.7.25 — flip-below when above doesn't fit, instead of clamping the tooltip
            // on top of the card it describes (and the surrounding cards in the grid).
            const viewportH = window.innerHeight;
            const aboveY = rect.top - tooltipHeight - 10;
            const belowY = rect.bottom + 10;
            let y;
            if (aboveY >= 8) {
                y = aboveY;
            } else if (belowY + tooltipHeight <= viewportH - 8) {
                y = belowY;
            } else {
                // Neither side has room for the full tooltip — pick the larger half and
                // let the tooltip's internal scroll handle overflow, but never land on the card.
                const roomAbove = rect.top - 8;
                const roomBelow = viewportH - rect.bottom - 8;
                y = roomBelow >= roomAbove ? belowY : Math.max(8, aboveY);
            }
            tooltip.style.setProperty('--tooltip-left', `${x}px`);
            tooltip.style.setProperty('--tooltip-top', `${y}px`);
        }
        function bindSparkTooltips() {
            document.querySelectorAll('body > .sparks-tooltip').forEach(tooltip => tooltip.remove());
            document.querySelectorAll('#parent-grid .grid-card, #guest-parent-grid .guest-parent-card').forEach(card => {
                const tooltip = card.querySelector('.sparks-tooltip');
                if (!tooltip) return;
                card.classList.add('has-sparks');
                const show = () => {
                    if (tooltip.parentElement !== document.body) document.body.appendChild(tooltip);
                    // v7.2 — Forward data-guest-index from the card so the
                    // body-level CSS width cap (styles.css for
                    // body > .sparks-tooltip[data-guest-index]) keeps the
                    // tooltip narrow for guest parents. Without this, the
                    // tooltip springs back to the default ~620px width and
                    // covers the surrounding parent cards.
                    if (card.matches && card.matches('#guest-parent-grid .guest-parent-card')) {
                        tooltip.dataset.guestIndex = card.dataset.guestIndex || '';
                    }
                    activeSparkCard = card;
                    activeSparkTooltip = tooltip;
                    positionSparkTooltip(card, tooltip);
                    tooltip.classList.add('is-visible');
                    card.setAttribute('aria-expanded', 'true');
                };
                const hide = () => {
                    if (activeSparkCard === card) {
                        activeSparkCard = null;
                        activeSparkTooltip = null;
                    }
                    tooltip.classList.remove('is-visible');
                    card.setAttribute('aria-expanded', 'false');
                };
                tooltip.addEventListener('click', event => event.stopPropagation());
                tooltip.addEventListener('mousedown', event => event.stopPropagation());
                card.addEventListener('mouseenter', show);
                card.addEventListener('mouseleave', hide);
                card.addEventListener('focusin', show);
                card.addEventListener('focusout', hide);
            });
            bindGuestSparkHoverDelegates();
        }

        function bindGuestSparkHoverDelegates() {
            const grid = document.getElementById('guest-parent-grid');
            if (!grid || grid.dataset.guestSparkDelegated === '1') return;
            grid.dataset.guestSparkDelegated = '1';
            const showFor = card => {
                if (!card) return;
                let tooltip = card.querySelector('.sparks-tooltip') || document.querySelector(`body > .sparks-tooltip[data-guest-index="${card.dataset.guestIndex || ''}"]`);
                if (!tooltip) return;
                card.classList.add('has-sparks');
                if (tooltip.parentElement !== document.body) document.body.appendChild(tooltip);
                tooltip.dataset.guestIndex = card.dataset.guestIndex || '';
                activeSparkCard = card;
                activeSparkTooltip = tooltip;
                positionSparkTooltip(card, tooltip);
                tooltip.classList.add('is-visible');
                card.setAttribute('aria-expanded', 'true');
            };
            const hideFor = card => {
                if (!card) return;
                const tooltip = activeSparkCard === card ? activeSparkTooltip : null;
                if (tooltip) tooltip.classList.remove('is-visible');
                if (activeSparkCard === card) {
                    activeSparkCard = null;
                    activeSparkTooltip = null;
                }
                card.setAttribute('aria-expanded', 'false');
            };
            grid.addEventListener('mouseover', event => {
                const card = event.target.closest('.guest-parent-card');
                if (!card || !grid.contains(card)) return;
                const from = event.relatedTarget;
                if (from && card.contains(from)) return;
                showFor(card);
            });
            grid.addEventListener('mouseout', event => {
                const card = event.target.closest('.guest-parent-card');
                if (!card || !grid.contains(card)) return;
                const to = event.relatedTarget;
                if (to && (card.contains(to) || (activeSparkTooltip && activeSparkTooltip.contains(to)))) return;
                hideFor(card);
            });
            grid.addEventListener('focusin', event => {
                const card = event.target.closest('.guest-parent-card');
                if (card) showFor(card);
            });
            grid.addEventListener('focusout', event => {
                const card = event.target.closest('.guest-parent-card');
                if (card) hideFor(card);
            });
        }

        document.addEventListener('scroll', () => {
            if (activeSparkCard && activeSparkTooltip) positionSparkTooltip(activeSparkCard, activeSparkTooltip);
        }, true);
        window.addEventListener('resize', () => {
            if (activeSparkCard && activeSparkTooltip) positionSparkTooltip(activeSparkCard, activeSparkTooltip);
        });
        function friendKey(friend) {
            return `${friend.viewer_id}:${friend.support_card_id}`;
        }
        function normalizedCardName(value) {
            return String(value || '').toLowerCase().replace(/\([^)]*\)/g, '').replace(/[^a-z0-9]+/g, '');
        }
        function friendAllowed(friend) {
            if (!friend) return false;
            const friendId = String(friend.support_card_id || '');
            const friendName = normalizedCardName(friend.support_name);
            if (selection.deck) {
                const deckIds = new Set(selection.deck.cards.map(card => String(card.id || '')));
                if (deckIds.has(friendId)) return false;
                const deckNames = new Set(selection.deck.cards.map(card => normalizedCardName(card.name)));
                if (friendName && deckNames.has(friendName)) return false;
            }
            if (selection.trainee && friendName && normalizedCardName(selection.trainee.name) === friendName) return false;
            return true;
        }
        function getVisibleFriends() {
            const friends = (dashData && dashData.friends) || [];
            return friends.filter(friendAllowed);
        }
        function clearInvalidFriendSelection() {
            if (selection.friend && !friendAllowed(selection.friend)) {
                selection.friend = null;
            }
        }
        function syncFriendSelection() {
            const visibleFriends = (dashData && dashData.visibleFriends) || [];
            document.querySelectorAll('#friend-grid .grid-card').forEach((el, i) => {
                const friend = visibleFriends[i];
                el.classList.toggle('selected', Boolean(selection.friend && friend && friendKey(selection.friend) === friendKey(friend)));
            });
        }
        function findDeckIndexForCareer(activeCareer) {
            const decks = (dashData && dashData.validDecks) || [];
            if (!activeCareer || !decks.length) return -1;
            if (activeCareer.deck_id) {
                const deckIdx = decks.findIndex(d => Number(d.id) === Number(activeCareer.deck_id));
                if (deckIdx >= 0) return deckIdx;
            }
            const supportIds = (activeCareer.support_card_ids || []).map(id => String(id)).filter(Boolean);
            if (!supportIds.length) return -1;
            const careerSet = new Set(supportIds);
            return decks.findIndex(deck => {
                const deckIds = (deck.cards || []).map(card => String(card.id || '')).filter(Boolean);
                return deckIds.length === careerSet.size && deckIds.every(id => careerSet.has(id));
            });
        }
        function selectCareerDeck(activeCareer) {
            const deckIdx = findDeckIndexForCareer(activeCareer);
            if (deckIdx >= 0) {
                selection.deck = dashData.validDecks[deckIdx];
                const deckEls = document.querySelectorAll('.deck-container');
                if (deckEls[deckIdx]) deckEls[deckIdx].classList.add('selected');
                return;
            }
            const supportCards = (activeCareer && activeCareer.support_cards) || [];
            if (supportCards.length) {
                selection.deck = {
                    id: activeCareer.deck_id || 'active',
                    name: activeCareer.deck_id ? `Deck ${activeCareer.deck_id}` : 'Active career deck',
                    cards: supportCards
                };
            }
        }
        function selectCareerFriend(activeCareer) {
            if (!activeCareer || !activeCareer.friend_viewer_id || !activeCareer.friend_card_id) return;
            state.pendingFriendSelection = {
                viewer_id: String(activeCareer.friend_viewer_id),
                support_card_id: String(activeCareer.friend_card_id)
            };
            if (activeCareer.friend) {
                selection.friend = {
                    ...activeCareer.friend,
                    viewer_id: String(activeCareer.friend_viewer_id),
                    support_card_id: String(activeCareer.friend_card_id)
                };
            }
        }
        async function loadRaceData() {
            try {
                const raceRes = await fetch('/assets/data/uma_race_data.json');
                const data = await raceRes.json();
                state.raceData = Array.isArray(data.races) ? data.races : [];
                syncSelectedPresetRaces();
                renderRaces();
            } catch (e) {}
        }

        function getCurrentPreset() {
            return (state.presets || []).find(p => p.name === state.selectedPreset);
        }

        function getSkillConfig() {
            state.skillConfig = state.skillConfig || {};
            state.skillConfig.skill_strategy = state.skillConfig.skill_strategy || {};
            return state.skillConfig;
        }

        async function loadSkillConfig() {
            try {
                // v7.6 — skill config is per-preset; load the selected preset's.
                const p = state.selectedPreset ? `&preset=${encodeURIComponent(state.selectedPreset)}` : '';
                const res = await apiJson('/api/skill-config?t=' + Date.now() + p);
                state.skillConfig = res.config || {};
            } catch (e) {
                state.skillConfig = state.skillConfig || {};
            }
            return getSkillConfig();
        }

        async function saveSkillConfig(patch = {}) {
            const current = getSkillConfig();
            state.skillConfig = { ...current, ...(patch || {}) };
            try {
                const res = await apiJson('/api/skill-config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    // v7.6 — write to the selected preset.
                    body: JSON.stringify({ config: state.skillConfig, preset: state.selectedPreset || '' })
                });
                if (res.config) state.skillConfig = res.config;
            } catch (e) {
                console.warn('Failed to save skill config', e);
            }
            return getSkillConfig();
        }

        function currentSmartSolverConfig() {
            state.smartSolverConfig = state.smartSolverConfig || {};
            return state.smartSolverConfig;
        }

        async function loadSmartSolverConfig() {
            try {
                const res = await apiJson('/api/smart-solver/config?t=' + Date.now());
                state.smartSolverConfig = res.config || {};
                // v2.1: restore the planner mode from the PERSISTED source so a
                // reload (or a different browser, or cleared storage) can't silently
                // drop a manual schedule back to "smart". The saved preset is the
                // runtime authority the engine reads (extra_race_list_source); match
                // the visible mode to it. Only act on an explicit saved source.
                const savedSource = String(res.source || '').trim().toLowerCase();
                if (savedSource === 'manual' || savedSource === 'smart') {
                    setRacePlannerMode(savedSource, { persist: true, render: false });
                }
            } catch (e) {
                state.smartSolverConfig = state.smartSolverConfig || {};
            }
            return currentSmartSolverConfig();
        }

        async function saveSmartSolverConfig(patch = {}) {
            state.smartSolverConfig = { ...currentSmartSolverConfig(), ...(patch || {}) };
            try {
                const res = await apiJson('/api/smart-solver/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ config: state.smartSolverConfig })
                });
                if (res.config) state.smartSolverConfig = res.config;
            } catch (e) {
                console.warn('Failed to save smart solver config', e);
            }
            return currentSmartSolverConfig();
        }

        function normalizePresetName(value) {
            return String(value || '').trim().replace(/[^a-zA-Z0-9._ -]+/g, '').replace(/\s+/g, ' ').trim();
        }

        function presetNameExists(name) {
            const normalized = normalizePresetName(name).toLowerCase();
            return Boolean(normalized && (state.presets || []).some(p => p.name.toLowerCase() === normalized));
        }

        function syncSelectedPresetRaces() {
            const solverCfg = currentSmartSolverConfig();
            state.selectedRaces = (solverCfg?.extra_race_list || [])
                .map(id => parseInt(id, 10))
                .filter(id => Number.isFinite(id));
            state.manualRaceSelectionActive = Boolean(state.selectedRaces.length);
        }

        function getYearSlots(yearIdx) {
            const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
            const periods = ['Early', 'Late'];
            const yearLabels = ['Junior Year', 'Classic Year', 'Senior Year'];
            const slots = [];
            for (const month of months) {
                for (const period of periods) {
                    const label = period + ' ' + month;
                    const datePrefix = yearLabels[yearIdx] + ' ' + label;
                    const races = state.raceData.filter(r => r.date.includes(datePrefix));
                    slots.push({ period: label, races: races, yearIdx: yearIdx });
                }
            }
            return slots;
        }

        function raceKeys(race) {
            const keys = [race.id, race.program_id, ...(race.legacy_ids || [])];
            return keys.map(id => parseInt(id, 10)).filter(id => Number.isFinite(id));
        }

        function normalizeRaceName(value) {
            return String(value || '')
                .toLowerCase()
                .replace(/[^a-z0-9]+/g, '');
        }

        function raceTurnFromDate(race) {
            const yearOffset = String(race.date || '').includes('Classic Year') ? 24
                : String(race.date || '').includes('Senior Year') ? 48
                : 0;
            const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
            const monthIdx = months.findIndex(m => String(race.date || '').includes(m));
            const isLate = String(race.date || '').includes('Late');
            if (monthIdx < 0) return 0;
            return yearOffset + monthIdx * 2 + (isLate ? 2 : 1);
        }

        function localRaceIdForRace(race) {
            const id = parseInt(race?.id, 10);
            const programId = parseInt(race?.program_id, 10);
            if (Number.isFinite(id)) return id;
            if (Number.isFinite(programId)) return programId;
            const keys = raceKeys(race || {});
            return keys.length ? keys[0] : 0;
        }

        function resolveTrackblazerRaceToLocalRace(planRace, fallbackId = 0) {
            if (!planRace && !fallbackId) return null;
            const wantedIds = [
                fallbackId,
                planRace?.program_id,
                planRace?.id,
                planRace?.race_id,
                ...(planRace?.legacy_ids || [])
            ].map(id => parseInt(id, 10)).filter(id => Number.isFinite(id));

            if (wantedIds.length) {
                const exact = state.raceData.find(r => raceKeys(r).some(id => wantedIds.includes(id)));
                if (exact) return exact;
            }

            const planName = normalizeRaceName(planRace?.name);
            const planTurn = parseInt(planRace?.turn || planRace?.date_turn || 0, 10);
            const planGrade = String(planRace?.grade || '').toUpperCase();
            const planDistance = String(planRace?.distance || '').toLowerCase();

            if (planName) {
                const nameMatches = state.raceData.filter(r => normalizeRaceName(r.name) === planName);
                if (nameMatches.length === 1) return nameMatches[0];

                if (nameMatches.length > 1 && planTurn) {
                    const byTurn = nameMatches.find(r => raceTurnFromDate(r) === planTurn);
                    if (byTurn) return byTurn;
                }

                if (nameMatches.length > 1) {
                    const byMeta = nameMatches.find(r => {
                        const gradeOk = !planGrade || String(r.type || r.grade || '').toUpperCase() === planGrade;
                        const distanceText = String(r.distance || r.category || '').toLowerCase();
                        const distanceOk = !planDistance || distanceText.includes(planDistance) || planDistance.includes(distanceText);
                        return gradeOk && distanceOk;
                    });
                    if (byMeta) return byMeta;
                }

                if (nameMatches.length) return nameMatches[0];
            }

            return null;
        }

        function resolveTrackblazerPlanRaceIds(plan) {
            const schedule = Array.isArray(plan?.schedule) ? plan.schedule : [];
            const rawIds = (plan?.extra_race_list || []).map(id => parseInt(id, 10)).filter(id => Number.isFinite(id));
            const resolved = [];
            const misses = [];

            const maxLen = Math.max(schedule.length, rawIds.length);
            for (let i = 0; i < maxLen; i += 1) {
                const row = schedule[i] || null;
                const fallbackId = rawIds[i] || 0;
                const localRace = resolveTrackblazerRaceToLocalRace(row, fallbackId);
                if (localRace) {
                    const localId = localRaceIdForRace(localRace);
                    if (localId && !resolved.includes(localId)) resolved.push(localId);
                } else if (fallbackId) {
                    misses.push({ id: fallbackId, name: row?.name || '' });
                }
            }

            return { ids: resolved, misses };
        }

        function selectedTraineeForPlanner() {
            const current = getCurrentPreset() || {};
            const selected = selection.trainee || current.trainee || current.chara || current.selected_trainee || {};
            const skillCfg = getSkillConfig();
            const skillProfile = state.selectedTraineeProfile || skillCfg.skill_profile || current.skill_profile || current.skillProfile || selected.skill_profile || {};
            const strategy = (skillCfg && skillCfg.skill_strategy) || current.skill_strategy || current.skillPolicy || {};
            const traineeName = selected.name || current.trainee_name || current.chara_name || current.character_name || '';
            const traineeId = selected.id || selected.card_id || current.card_id || '';
            return { selected, skillProfile, strategy, current, traineeName, traineeId };
        }

        function hasTrackblazerTraineeSelected() {
            const { traineeName, traineeId, selected } = selectedTraineeForPlanner();
            return Boolean(selection.trainee && (traineeName || traineeId || selected.id || selected.card_id));
        }

        function updateTrackblazerPlanGate() {
            if (!els.v4PlanBtn) return;
            const ready = hasTrackblazerTraineeSelected();
            els.v4PlanBtn.disabled = !ready;
            if (els.v4ApplyPlanBtn && !state.trackblazerPlan) els.v4ApplyPlanBtn.disabled = true;
            if (els.v4ResetPlanBtn && !state.trackblazerPlan) els.v4ResetPlanBtn.disabled = !state.manualRaceSelectionActive;
            if (!ready && els.v4TrackblazerPlan && !state.trackblazerPlan) {
                els.v4TrackblazerPlan.innerHTML = '<div class="v4-warn">Select a trainee before generating a Trackblazer plan.</div>';
            }
        }

        function selectedTraineeKey() {
            const { traineeName, traineeId } = selectedTraineeForPlanner();
            return `${traineeId || ''}|${traineeName || ''}`;
        }

        async function loadSelectedTraineeProfile({ force = false } = {}) {
            const { traineeName, traineeId } = selectedTraineeForPlanner();
            if (!traineeName && !traineeId) {
                state.selectedTraineeProfile = null;
                return null;
            }
            const key = selectedTraineeKey();
            if (!force && state.traineeProfileCache[key]) {
                state.selectedTraineeProfile = state.traineeProfileCache[key];
                return state.selectedTraineeProfile;
            }
            const profile = await apiJson('/api/trainee/profile', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ trainee_name: traineeName, trainee_id: String(traineeId || '') })
            });
            if (!profile.success) throw new Error(profile.detail || 'Unable to load trainee profile');
            state.traineeProfileCache[key] = profile;
            state.selectedTraineeProfile = profile;
            return profile;
        }

        function inferTrackblazerAptitudes() {
            const { skillProfile, strategy, current } = selectedTraineeForPlanner();
            const aptitudes = {};

            const fromProfile = skillProfile && typeof skillProfile === 'object' ? skillProfile : {};
            const directAptitudes = fromProfile.aptitudes || {};
            const distance = fromProfile.distance_aptitude || strategy.aptitudes || current.aptitudes || {};
            const track = fromProfile.track_aptitude || {};
            const style = fromProfile.style_aptitude || {};

            const map = {
                sprint: 'Sprint',
                mile: 'Mile',
                medium: 'Medium',
                middle: 'Medium',
                long: 'Long',
                turf: 'Turf',
                dirt: 'Dirt',
                front: 'Front',
                pace: 'Pace',
                late: 'Late',
                end: 'End'
            };

            for (const [key, value] of Object.entries({ ...directAptitudes, ...distance, ...track, ...style })) {
                const mapped = map[String(key).toLowerCase()] || key;
                if (value) aptitudes[mapped] = value;
            }

            const primary = fromProfile.primary_distances || strategy.primary_distances || [];
            const secondary = fromProfile.secondary_distances || strategy.secondary_distances || [];
            const avoid = fromProfile.avoid_distances || strategy.avoid_distances || [];
            primary.forEach(d => { aptitudes[map[String(d).toLowerCase()] || d] = aptitudes[map[String(d).toLowerCase()] || d] || 'A'; });
            secondary.forEach(d => { aptitudes[map[String(d).toLowerCase()] || d] = aptitudes[map[String(d).toLowerCase()] || d] || 'B'; });
            avoid.forEach(d => { aptitudes[map[String(d).toLowerCase()] || d] = aptitudes[map[String(d).toLowerCase()] || d] || 'E'; });

            const recommendedStyle = fromProfile.recommended_style || fromProfile.running_style || strategy.running_style || current.running_style;
            if (recommendedStyle && typeof recommendedStyle === 'string') {
                const mapped = map[recommendedStyle.toLowerCase()] || recommendedStyle;
                aptitudes[mapped] = aptitudes[mapped] || 'A';
            }

            return aptitudes;
        }

        function raceSelected(race) {
            return raceKeys(race).some(id => state.selectedRaces.includes(id));
        }

        function renderRaces() {
            if (!els.raceOptionsContent) return;
            els.raceOptionsContent.innerHTML = `
                <div class="race-plan-mode-banner ${state.trackblazerPlan ? 'generated' : ((state.selectedRaces || []).length ? 'manual' : 'empty')}">
                    <strong>${escapeHtml(currentRacePlanStateLabel())}</strong>
                    <span>${state.racePlannerMode === 'manual' ? 'Manual picks are staged until you click Apply Manual.' : (state.trackblazerPlan ? 'Apply the Smart Race Solver result, reset it, or switch to Manual Selection.' : 'Smart Race Solver mode. Switch to Manual Selection to hand-pick races.')}</span>
                </div>`;

            const yearLabels = ['Junior Year', 'Classic Year', 'Senior Year'];
            yearLabels.forEach((label, yi) => {
                const block = document.createElement('div');
                block.className = 'race-year-block';
                block.innerHTML = `<div class="race-year-title">${label}</div>`;

                const grid = document.createElement('div');
                grid.className = 'race-time-grid';

                const slots = getYearSlots(yi);
                slots.forEach((slot, si) => {
                    const cell = document.createElement('div');
                    cell.className = 'race-time-cell';

                    const slotIds = slot.races.flatMap(r => raceKeys(r));
                    const selectedInSlot = state.selectedRaces.filter(id => slotIds.includes(id));
                    const mainRaceId = selectedInSlot[0];
                    const selected = slot.races.find(r => raceKeys(r).includes(mainRaceId));

                    let html = `<div class="race-time-label">${slot.period}</div>`;
                    if (selected) {
                        html += `
                            <div class="race-cell-selected-img">
                                <img src="/races/${encodeURIComponent(selected.name)}.png" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex'">
                                <div class="race-image-fallback" style="display:none">${selected.type}</div>
                                <span class="race-cell-selected-grade badge-${selected.type.toLowerCase().replace('-', '')}">${selected.type}</span>
                            </div>
                            <div class="race-cell-selected-name">${escapeHtml(selected.name)}</div>
                        `;
                    } else {
                        html += `<div class="race-time-plus">+</div>`;
                    }

                    cell.innerHTML = html;
                    cell.onclick = () => openSlotPopup(slot, yi);
                    grid.appendChild(cell);
                });

                block.appendChild(grid);
                els.raceOptionsContent.appendChild(block);
            });
        }

        function openSlotPopup(slot, yearIdx) {
            const yearLabels = ['Junior Year', 'Classic Year', 'Senior Year'];
            els.racePopupTitle.textContent = `${yearLabels[yearIdx]} - ${slot.period}`;
            els.racePopupBody.innerHTML = '';

            if (slot.races.length === 0) {
                els.racePopupBody.innerHTML = '<div class="race-slot-popup-empty">No races available</div>';
            } else {
                const list = document.createElement('div');
                list.className = 'race-slot-popup-list';

                const slotIds = slot.races.flatMap(r => raceKeys(r));

                slot.races.forEach(race => {
                    const myIds = raceKeys(race);
                    const selectedInSlot = state.selectedRaces.filter(id => slotIds.includes(id));
                    const selIndex = selectedInSlot.findIndex(id => myIds.includes(id));
                    const isSelected = selIndex !== -1;

                    let badgeHtml = '<div class="race-slot-popup-check">✓</div>';
                    if (isSelected && state.scenarioType === "Mant" && selectedInSlot.length > 0) {
                        if (selIndex === 0) {
                            badgeHtml = '<div class="race-slot-popup-check main-race" style="font-size: 0.7rem; font-weight: bold; width: auto; padding: 0 8px; border-radius: 12px; background: rgba(255,255,255,0.2);">MAIN</div>';
                        } else {
                            badgeHtml = `<div class="race-slot-popup-check overwrite-race" style="font-size: 0.7rem; font-weight: bold; width: auto; padding: 0 8px; border-radius: 12px; background: rgba(255,255,255,0.1);">RIVAL OVERWRITE ${selIndex}</div>`;
                        }
                    }

                    const item = document.createElement('div');
                    item.className = `race-slot-popup-item ${isSelected ? 'on' : ''}`;
                    item.innerHTML = `
                        <div class="race-slot-popup-img">
                            <img src="/races/${encodeURIComponent(race.name)}.png" onerror="this.src='/broom.png'">
                        </div>
                        <div class="race-slot-popup-info">
                            <div class="race-slot-popup-name-row">
                                <span class="race-slot-popup-grade badge-${race.type.toLowerCase().replace('-', '')}">${race.type}</span>
                                <span class="race-slot-popup-name">${escapeHtml(race.name)}</span>
                            </div>
                            <div class="race-slot-popup-meta">
                                <span class="race-slot-popup-terrain ${race.terrain.toLowerCase()}">${race.terrain}</span>
                                <span class="race-slot-popup-distance">${race.distance}</span>
                            </div>
                        </div>
                        ${badgeHtml}
                    `;
                    item.onclick = async () => {
                        const isMant = state.scenarioType === "Mant";

                        if (state.trackblazerPlan) {
                            state.trackblazerPlan = null;
                            if (els.v4TrackblazerPlan) {
                                els.v4TrackblazerPlan.innerHTML = '<div class="v4-warn">Generated plan disabled because you manually edited the race schedule.</div>';
                            }
                            if (els.v4ApplyPlanBtn) els.v4ApplyPlanBtn.disabled = true;
                        }

                        if (isSelected) {
                            state.selectedRaces = state.selectedRaces.filter(id => !myIds.includes(id));
                        } else {
                            if (!isMant) {
                                state.selectedRaces = state.selectedRaces.filter(id => !slotIds.includes(id));
                            }
                            const raceId = parseInt(race.id);
                            if (!state.selectedRaces.includes(raceId)) state.selectedRaces.push(raceId);
                        }

                        state.trackblazerPlan = null;
                        setRacePlannerMode('manual', { persist: true, render: false });
                        state.manualRaceSelectionActive = Boolean(state.selectedRaces.length);
                        if (els.v4ResetPlanBtn) els.v4ResetPlanBtn.disabled = !state.manualRaceSelectionActive;
                        if (els.v47ApplyManualBtn) els.v47ApplyManualBtn.disabled = !state.selectedRaces.length;
                        openSlotPopup(slot, yearIdx);
                        renderRaces();
                        syncStartButton();
                        autoSaveRaces().catch(() => {}); // v2.1 auto-persist manual pick
                    };
                    list.appendChild(item);
                });
                els.racePopupBody.appendChild(list);
            }
            els.racePopupOverlay.style.display = 'flex';
        }

        async function autoSaveRaces({ force = false } = {}) {
            try {
                // v2.1: manual picks now auto-persist (no separate "Apply Manual"
                // click required). This used to bail in manual mode unless forced,
                // so manual picks stayed "staged" and the preset's
                // extra_race_list_source could drift to "smart" on a reload -> the
                // Smart Race Solver silently took over a manual schedule. Persist in
                // either mode; the saved `source` (below) always matches the mode.
                void force;
                const solverCfg = currentSmartSolverConfig();
                state.manualRaceSelectionActive = !state.trackblazerPlan && Boolean((state.selectedRaces || []).length);
                solverCfg.extra_race_list = [...state.selectedRaces];
                await saveSmartSolverConfig();
                await apiJson('/api/presets/save_races', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        preset_name: state.selectedPreset,
                        races: state.selectedRaces,
                        source: state.racePlannerMode === 'manual' ? 'manual' : 'smart'
                    })
                });
            } catch (e) {}
        }

        function getTurnFromDate(dateStr) {
            const match = dateStr.match(/(\d+)年(\d+)月(前|後)半/);
            if (!match) return 0;
            const year = parseInt(match[1]);
            const month = parseInt(match[2]);
            const half = match[3] === '前' ? 0 : 1;
            return (year - 1) * 24 + (month - 1) * 2 + half + 1;
        }

        function bindRaceHandlers() {
            els.racePopupClose?.addEventListener('click', () => {
                els.racePopupOverlay.style.display = 'none';
            });
            els.racePopupOverlay?.addEventListener('click', (e) => {
                if (e.target === els.racePopupOverlay) els.racePopupOverlay.style.display = 'none';
            });

            makeSectionToggle('race-toggle', 'race-chevron', 'race-body', false);
        }

        let skillDataCache = null;
        let activeEditTier = null;
        let activeSkillFilter = null;
        let activeColorFilter = null;
        let weightedSkillListScrollTop = 0;
        let skillListScrollTop = 0;

        const SKILL_FILTERS = [
            { id: 101, label: 'Front' },
            { id: 102, label: 'Pace' },
            { id: 103, label: 'Late' },
            { id: 104, label: 'End' },
            { id: 201, label: 'Short' },
            { id: 202, label: 'Mile' },
            { id: 203, label: 'Medium' },
            { id: 204, label: 'Long' },
            { id: 502, label: 'Dirt' },
            { id: 'turf', label: 'Turf' }
        ];

        const COLOR_FILTERS = [
            { id: 'green', label: 'Green', color: '#4ade80', iconPrefixes: ['1001', '1002', '1003', '1004', '1005', '1006'] },
            { id: 'blue', label: 'Blue', color: '#60a5fa', iconPrefixes: ['2002'] },
            { id: 'yellow', label: 'Yellow', color: '#fbbf24', iconPrefixes: ['2001', '2004', '2005', '2006', '2009'] },
            { id: 'red', label: 'Red', color: '#f87171', iconPrefixes: ['3001', '3002', '3004', '3005', '3007'] }
        ];

        async function loadSkillData() {
            if (skillDataCache) return skillDataCache;
            try {
                const res = await apiJson('/api/skills');
                if (res.success && res.skills) {
                    const uniqueMap = new Map();
                    Object.entries(res.skills).forEach(([id, s]) => {
                        if (!uniqueMap.has(s.name)) {
                            uniqueMap.set(s.name, { id, ...s, tags: new Set(s.tags || []) });
                        } else {
                            const existing = uniqueMap.get(s.name);
                            if (s.rarity > existing.rarity) existing.rarity = s.rarity;
                            (s.tags || []).forEach(t => existing.tags.add(t));
                        }
                    });
                    skillDataCache = Array.from(uniqueMap.values()).map(s => ({ ...s, tags: Array.from(s.tags) }));
                    skillDataCache.sort((a, b) => a.name.localeCompare(b.name));
                    return skillDataCache;
                }
            } catch (e) {}
            return [];
        }

        function renderSkillFilters() {
            const container = document.getElementById('skill-filters');
            if (!container) return;
            
            let html = '<div style="display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 4px;">';
            for (const filter of SKILL_FILTERS) {
                const isActive = activeSkillFilter === filter.id;
                const bg = isActive ? 'rgba(var(--accent-primary-rgb), 0.2)' : 'rgba(255,255,255,0.05)';
                const border = isActive ? 'var(--accent-primary)' : 'transparent';
                const color = isActive ? 'var(--text-main)' : '#a1a1aa';
                html += `<div class="skill-filter-chip affinity-filter" data-id="${filter.id}" style="padding: 0.35rem 0.75rem; border-radius: 1rem; font-size: 0.75rem; cursor: pointer; background: ${bg}; border: 1px solid ${border}; color: ${color}; font-weight: bold; transition: all 0.1s;">${filter.label}</div>`;
            }
            html += '</div><div style="display: flex; flex-wrap: wrap; gap: 4px;">';
            
            for (const filter of COLOR_FILTERS) {
                const isActive = activeColorFilter === filter.id;
                const bg = isActive ? `${filter.color}33` : 'rgba(255,255,255,0.05)';
                const border = isActive ? filter.color : 'transparent';
                const color = isActive ? 'var(--text-main)' : filter.color;
                html += `<div class="skill-filter-chip color-filter" data-color="${filter.id}" style="padding: 0.35rem 0.75rem; border-radius: 1rem; font-size: 0.75rem; cursor: pointer; background: ${bg}; border: 1px solid ${border}; color: ${color}; font-weight: bold; transition: all 0.1s;">${filter.label}</div>`;
            }
            html += '</div>';
            
            container.innerHTML = html;
            
            container.querySelectorAll('.affinity-filter').forEach(el => {
                el.addEventListener('click', () => {
                    let tagId = el.getAttribute('data-id');
                    if (tagId !== 'turf') tagId = Number(tagId);
                    
                    if (activeSkillFilter === tagId) activeSkillFilter = null;
                    else activeSkillFilter = tagId;
                    
                    renderSkillFilters();
                    renderSkillList();
                });
            });

            container.querySelectorAll('.color-filter').forEach(el => {
                el.addEventListener('click', () => {
                    const colorId = el.getAttribute('data-color');
                    
                    if (activeColorFilter === colorId) activeColorFilter = null;
                    else activeColorFilter = colorId;
                    
                    renderSkillFilters();
                    renderSkillList();
                });
            });
        }

        function renderSkillList() {
            const query = (els.skillSearch?.value || '').toLowerCase();
            const skills = skillDataCache || [];
            
            let count = 0;
            let html = '';
            for (const s of skills) {
                if (query && !s.name.toLowerCase().includes(query)) continue;
                
                if (activeSkillFilter !== null) {
                    const skillTags = s.tags || [];
                    if (activeSkillFilter === 'turf') {
                        if (skillTags.includes(502)) continue;
                    } else {
                        if (!skillTags.includes(activeSkillFilter)) continue;
                    }
                }
                
                if (activeColorFilter !== null) {
                    const iconId = String(s.icon_id || '');
                    const colorFilter = COLOR_FILTERS.find(filter => filter.id === activeColorFilter);
                    const skillColor = colorFilter && colorFilter.iconPrefixes.some(prefix => iconId.startsWith(prefix)) ? activeColorFilter : 'none';
                    
                    if (skillColor !== activeColorFilter) continue;
                }
                
                count++;
                
                html += `<div class="skill-list-item" data-name="${escapeAttr(s.name)}" style="padding: 0.5rem; background: rgba(255,255,255,0.03); border-radius: 4px; cursor: pointer; display: flex; align-items: center; gap: 8px; transition: background 0.1s;">
                    <span style="flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text-main); font-size: 0.85rem;">${escapeHtml(s.name)}</span>
                </div>`;
            }
            
            if (els.skillList) {
                skillListScrollTop = els.skillList.scrollTop || skillListScrollTop || 0;
                if (count === 0) {
                    els.skillList.innerHTML = `<div style="padding: 1rem; color: #a1a1aa; font-size: 0.85rem;">No skills found.</div>`;
                } else {
                    els.skillList.innerHTML = html;
                    requestAnimationFrame(() => { if (els.skillList) els.skillList.scrollTop = skillListScrollTop || 0; });
                    els.skillList.querySelectorAll('.skill-list-item').forEach(el => {
                        el.addEventListener('click', () => {
                            const name = el.getAttribute('data-name');
                            addSkillToFocusedArea(name);
                            el.classList.add('is-selected');
                        });
                        el.addEventListener('mouseenter', () => el.style.background = 'rgba(255,255,255,0.1)');
                        el.addEventListener('mouseleave', () => el.style.background = 'rgba(255,255,255,0.03)');
                    });
                }
            }
        }

        function renderSkillEditorRightSide() {
            const current = getCurrentPreset();
            if (!current) {
                if (els.skillTiersContainer) els.skillTiersContainer.innerHTML = '';
                if (els.skillBlacklistContainer) els.skillBlacklistContainer.innerHTML = '';
                return;
            }

            let tiersHtml = '';
            const storedTiers = current.learn_skill_list || [];
            const tiers = storedTiers.length > 0 ? storedTiers : [[]];
            tiers.forEach((tier, i) => {
                const isActive = activeEditTier === i;
                const itemsHtml = tier.map(s =>
                    `<div class="skill-tag">
                        ${escapeHtml(s)} <span class="skill-tag-del" data-tier="${i}" data-skill="${escapeAttr(s)}">&times;</span>
                    </div>`
                ).join('');

                tiersHtml += `
                <div class="skill-tier-dropzone ${isActive ? 'is-active' : ''}" data-tier="${i}">
                    <div class="skill-tier-header">
                        <span class="skill-tier-label">TIER ${i+1}</span>
                        <button class="btn btn-sm btn-danger-soft skill-editor-action tier-del-btn" data-tier="${i}">DEL</button>
                    </div>
                    <div class="skill-tag-list">
                        ${itemsHtml}
                    </div>
                </div>`;
            });
            if (els.skillTiersContainer) els.skillTiersContainer.innerHTML = tiersHtml;

            if (els.skillBlacklistContainer) {
                const isBlActive = activeEditTier === null;
                els.skillBlacklistContainer.classList.toggle('is-active', isBlActive);

                const blacklist = current.learn_skill_blacklist || [];
                els.skillBlacklistContainer.innerHTML = blacklist.map(s =>
                    `<div class="skill-tag blacklist">
                        ${escapeHtml(s)} <span class="skill-tag-del" data-blacklist="true" data-skill="${escapeAttr(s)}">&times;</span>
                    </div>`
                ).join('');
            }

            els.skillTiersContainer?.querySelectorAll('.skill-tier-dropzone').forEach(el => {
                el.addEventListener('click', (e) => {
                    if (e.target.classList.contains('tier-del-btn') || e.target.classList.contains('skill-tag-del')) return;
                    activeEditTier = parseInt(el.getAttribute('data-tier'));
                    renderSkillEditorRightSide();
                });
            });
            if (els.skillBlacklistContainer) {
                els.skillBlacklistContainer.onclick = (e) => {
                    if (e.target.classList.contains('skill-tag-del')) return;
                    activeEditTier = null;
                    renderSkillEditorRightSide();
                };
            }

            els.skillTiersContainer?.querySelectorAll('.tier-del-btn').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const idx = parseInt(btn.getAttribute('data-tier'));
                    current.learn_skill_list = current.learn_skill_list || [];
                    current.learn_skill_list.splice(idx, 1);
                    if (activeEditTier === idx) activeEditTier = null;
                    else if (activeEditTier > idx) activeEditTier--;
                    await savePresetConfig();
                    renderSkillEditorRightSide();
                });
            });

            document.querySelectorAll('.skill-tag-del').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const skillName = btn.getAttribute('data-skill');
                    if (btn.hasAttribute('data-blacklist')) {
                        current.learn_skill_blacklist = current.learn_skill_blacklist.filter(s => s !== skillName);
                    } else {
                        const tierIdx = parseInt(btn.getAttribute('data-tier'));
                        current.learn_skill_list[tierIdx] = current.learn_skill_list[tierIdx].filter(s => s !== skillName);
                    }
                    await savePresetConfig();
                    renderSkillEditorRightSide();
                });
            });
        }

        async function addSkillToFocusedArea(name) {
            const current = getCurrentPreset();
            if (!current) return;

            if (activeEditTier === null) {
                if (!current.learn_skill_blacklist) current.learn_skill_blacklist = [];
                if (!current.learn_skill_blacklist.includes(name)) {
                    current.learn_skill_blacklist.push(name);
                }
            } else {
                if (!current.learn_skill_list) current.learn_skill_list = [];
                if (!current.learn_skill_list[activeEditTier]) current.learn_skill_list[activeEditTier] = [];
                if (!current.learn_skill_list[activeEditTier].includes(name)) {
                    current.learn_skill_list[activeEditTier].push(name);
                }
            }
            await savePresetConfig();
            renderSkillEditorRightSide();
        }

        function getSkillStrategy(current) {
            current = current || getSkillConfig();
            const source = getSkillConfig() || current || {};
            const strategy = source.skill_strategy || {};
            strategy.weights = strategy.weights || {};
            strategy.forced_skills = strategy.forced_skills || ((source.learn_skill_list || [])[0] || []);
            strategy.blacklist = strategy.blacklist || source.learn_skill_blacklist || [];
            strategy.manual_skill_weights = strategy.manual_skill_weights || {};
            strategy.running_style = strategy.running_style || 'auto';
            strategy.primary_distances = strategy.primary_distances || ['auto'];
            strategy.secondary_distances = strategy.secondary_distances || [];
            strategy.track = strategy.track || 'auto';
            strategy.max_green_per_purchase = Number.isFinite(Number(strategy.max_green_per_purchase)) ? Number(strategy.max_green_per_purchase) : Number(source.smart_skill_max_green_per_purchase ?? 1);
            strategy.weights.recommended = Number(strategy.weights.recommended ?? source.smart_skill_recommended_weight ?? 190);
            strategy.weights.community = Number(strategy.weights.community ?? source.smart_skill_community_multiplier ?? 1.0);
            strategy.weights.yellow = Number(strategy.weights.yellow ?? source.smart_skill_yellow_bonus ?? 100);
            strategy.weights.green_penalty = Number(strategy.weights.green_penalty ?? source.smart_skill_green_penalty ?? 90);
            strategy.weights.style = Number(strategy.weights.style ?? 70);
            strategy.weights.distance = Number(strategy.weights.distance ?? 75);
            return strategy;
        }

        function selectedValues(selector) {
            return Array.from(document.querySelectorAll(selector)).filter(el => el.checked).map(el => el.value);
        }

        async function saveWeightedSkillStrategy() {
            const current = getSkillConfig();
            const strategy = getSkillStrategy(current);
            const forced = Array.from(document.querySelectorAll('#weighted-forced-skills .skill-tag')).map(el => el.dataset.skill).filter(Boolean);
            const blacklist = Array.from(document.querySelectorAll('#weighted-blacklist .skill-tag')).map(el => el.dataset.skill).filter(Boolean);
            strategy.running_style = 'auto';
            strategy.primary_distances = selectedValues('.weighted-distance-primary');
            if (!strategy.primary_distances.length) strategy.primary_distances = ['auto'];
            strategy.secondary_distances = selectedValues('.weighted-distance-secondary');
            strategy.track = document.getElementById('weighted-track')?.value || 'auto';
            strategy.forced_skills = forced;
            strategy.blacklist = blacklist;
            const manualWeights = {};
            document.querySelectorAll('#weighted-manual-weights .weighted-manual-row').forEach(row => {
                const skill = row.dataset.skill;
                const value = Number(row.querySelector('.weighted-manual-weight-input')?.value || 0);
                if (skill && value !== 0) manualWeights[skill] = value;
            });
            strategy.manual_skill_weights = { ...(strategy.manual_skill_weights || {}), ...manualWeights };
            Object.keys(strategy.manual_skill_weights).forEach(skill => {
                if (Number(strategy.manual_skill_weights[skill] || 0) === 0) delete strategy.manual_skill_weights[skill];
            });
            strategy.max_green_per_purchase = Number(document.getElementById('weighted-max-green')?.value ?? 1);
            strategy.weights = {
                recommended: Number(document.getElementById('weighted-w-recommended')?.value ?? 190),
                community: Number(document.getElementById('weighted-w-community')?.value ?? 1),
                yellow: Number(document.getElementById('weighted-w-yellow')?.value ?? 100),
                green_penalty: Number(document.getElementById('weighted-w-green')?.value ?? 90),
                style: Number(document.getElementById('weighted-w-style')?.value ?? 70),
                distance: Number(document.getElementById('weighted-w-distance')?.value ?? 75)
            };
            await saveSkillConfig({
                skill_strategy: strategy,
                skill_profile: document.getElementById('weighted-profile')?.value || 'auto',
                learn_skill_list: forced.length ? [forced] : [],
                learn_skill_blacklist: blacklist,
                smart_skill_max_green_per_purchase: strategy.max_green_per_purchase,
                smart_skill_yellow_bonus: strategy.weights.yellow,
                smart_skill_green_penalty: strategy.weights.green_penalty
            });
            renderWeightedSkillEditorLists();
            refreshWeightedSkillPreview({ force: true });
        }

        function weightedSkillTag(skill, zoneId, className = '') {
            return `<div class="skill-tag ${className}" data-skill="${escapeAttr(skill)}">${escapeHtml(skill)} <span class="skill-tag-del weighted-skill-del" data-zone="${zoneId}" data-skill="${escapeAttr(skill)}">&times;</span></div>`;
        }

        function weightedManualWeightRow(skill, weight) {
            return `<div class="weighted-manual-row" data-skill="${escapeAttr(skill)}">
                <span>${escapeHtml(skill)}</span>
                <input class="weighted-manual-weight-input" type="number" step="5" value="${escapeAttr(weight)}" aria-label="Manual weight for ${escapeAttr(skill)}">
                <button class="btn btn-sm btn-danger-soft weighted-manual-remove" type="button">REMOVE</button>
            </div>`;
        }

        function renderManualSkillWeights() {
            const current = getCurrentPreset();
            const container = document.getElementById('weighted-manual-weights');
            if (!current || !container) return;
            const strategy = getSkillStrategy(current);
            const entries = Object.entries(strategy.manual_skill_weights || {}).sort((a, b) => a[0].localeCompare(b[0]));
            container.innerHTML = entries.length ? entries.map(([skill, weight]) => weightedManualWeightRow(skill, weight)).join('') : '<div class="weighted-empty">Use BOOST in the Skill Library to tweak individual skill scores.</div>';
            container.querySelectorAll('.weighted-manual-weight-input').forEach(input => {
                input.addEventListener('change', async () => {
                    const skill = input.closest('.weighted-manual-row')?.dataset.skill;
                    if (!skill) return;
                    const value = Number(input.value || 0);
                    if (!strategy.manual_skill_weights) strategy.manual_skill_weights = {};
                    if (value === 0) delete strategy.manual_skill_weights[skill];
                    else strategy.manual_skill_weights[skill] = value;
                    await saveWeightedSkillStrategy();
                });
            });
            container.querySelectorAll('.weighted-manual-remove').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const skill = btn.closest('.weighted-manual-row')?.dataset.skill;
                    if (!skill) return;
                    delete strategy.manual_skill_weights[skill];
                    await saveWeightedSkillStrategy();
                });
            });
        }

        function addManualSkillWeight(skill, delta = 50) {
            const current = getCurrentPreset();
            if (!current || !skill) return;
            const strategy = getSkillStrategy(current);
            strategy.manual_skill_weights = strategy.manual_skill_weights || {};
            strategy.manual_skill_weights[skill] = Number(strategy.manual_skill_weights[skill] || 0) + Number(delta || 0);
        }

        function renderWeightedSkillEditorLists() {
            const current = getCurrentPreset();
            if (!current) return;
            const strategy = getSkillStrategy(current);
            const forcedEl = document.getElementById('weighted-forced-skills');
            const blackEl = document.getElementById('weighted-blacklist');
            if (forcedEl) forcedEl.innerHTML = (strategy.forced_skills || []).map(s => weightedSkillTag(s, 'forced')).join('') || '<div class="weighted-empty">Click a skill on the right to pin it as a must-buy.</div>';
            if (blackEl) blackEl.innerHTML = (strategy.blacklist || []).map(s => weightedSkillTag(s, 'blacklist', 'blacklist')).join('') || '<div class="weighted-empty">Blacklist wrong-style, Dirt-only, or trap skills here.</div>';
            renderManualSkillWeights();
            document.querySelectorAll('.weighted-skill-del').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const zone = btn.dataset.zone;
                    const skill = btn.dataset.skill;
                    const current = getCurrentPreset();
                    const strategy = getSkillStrategy(current);
                    if (zone === 'forced') strategy.forced_skills = (strategy.forced_skills || []).filter(s => s !== skill);
                    if (zone === 'blacklist') strategy.blacklist = (strategy.blacklist || []).filter(s => s !== skill);
                    await saveWeightedSkillStrategy();
                });
            });
        }

        function renderWeightedSkillList() {
            const query = (document.getElementById('weighted-skill-search')?.value || '').toLowerCase();
            const skills = skillDataCache || [];
            const current = getCurrentPreset();
            const strategy = current ? getSkillStrategy(current) : { forced_skills: [], blacklist: [], manual_skill_weights: {} };
            let html = '';
            for (const s of skills) {
                if (!s || !s.name) continue;
                if (query && !s.name.toLowerCase().includes(query)) continue;
                const tags = s.tags || [];
                const tagText = [];
                if (tags.includes(101)) tagText.push('Front');
                if (tags.includes(102)) tagText.push('Pace');
                if (tags.includes(103)) tagText.push('Late');
                if (tags.includes(104)) tagText.push('End');
                if (tags.includes(201)) tagText.push('Sprint');
                if (tags.includes(202)) tagText.push('Mile');
                if (tags.includes(203)) tagText.push('Medium');
                if (tags.includes(204)) tagText.push('Long');
                if (tags.includes(502)) tagText.push('Dirt');
                const forced = (strategy.forced_skills || []).includes(s.name);
                const blacklisted = (strategy.blacklist || []).includes(s.name);
                const manual = Number((strategy.manual_skill_weights || {})[s.name] || 0);
                html += `<div class="weighted-skill-row ${forced ? 'is-forced' : ''} ${blacklisted ? 'is-blacklisted' : ''}" data-skill="${escapeAttr(s.name)}">
                    <div><strong>${escapeHtml(s.name)}</strong><span>${escapeHtml(tagText.join(' · ') || 'General')} ${manual ? `· manual ${manual > 0 ? '+' : ''}${manual}` : ''}</span></div>
                    <button class="btn btn-sm weighted-force-btn" type="button">${forced ? 'UNFORCE' : 'FORCE'}</button>
                    <button class="btn btn-sm weighted-boost-btn" type="button">BOOST</button>
                    <button class="btn btn-sm btn-danger-soft weighted-blacklist-btn" type="button">${blacklisted ? 'UNBLOCK' : 'BLACKLIST'}</button>
                </div>`;
            }
            const list = document.getElementById('weighted-skill-list');
            if (!list) return;
            weightedSkillListScrollTop = list.scrollTop || weightedSkillListScrollTop || 0;
            list.innerHTML = html || '<div class="weighted-empty">No skills found. Check /api/skills or skill_data.json.</div>';
            requestAnimationFrame(() => { const latest = document.getElementById('weighted-skill-list'); if (latest) latest.scrollTop = weightedSkillListScrollTop || 0; });

            list.querySelectorAll('.weighted-force-btn').forEach(btn => btn.addEventListener('click', async () => {
                const name = btn.closest('.weighted-skill-row')?.dataset.skill;
                const current = getCurrentPreset();
                const strategy = getSkillStrategy(current);
                if (!name) return;
                if (strategy.forced_skills.includes(name)) strategy.forced_skills = strategy.forced_skills.filter(s => s !== name);
                else strategy.forced_skills.push(name);
                await saveWeightedSkillStrategy();
                renderWeightedSkillList();
            }));
            list.querySelectorAll('.weighted-boost-btn').forEach(btn => btn.addEventListener('click', async () => {
                const name = btn.closest('.weighted-skill-row')?.dataset.skill;
                if (!name) return;
                addManualSkillWeight(name, 50);
                await saveWeightedSkillStrategy();
                renderWeightedSkillList();
            }));
            list.querySelectorAll('.weighted-blacklist-btn').forEach(btn => btn.addEventListener('click', async () => {
                const name = btn.closest('.weighted-skill-row')?.dataset.skill;
                const current = getCurrentPreset();
                const strategy = getSkillStrategy(current);
                if (!name) return;
                if (strategy.blacklist.includes(name)) strategy.blacklist = strategy.blacklist.filter(s => s !== name);
                else strategy.blacklist.push(name);
                await saveWeightedSkillStrategy();
                renderWeightedSkillList();
            }));
        }

        function selectedTraineeDisplayName() {
            const { traineeName, traineeId } = selectedTraineeForPlanner();
            return traineeName || (traineeId ? `Card ${traineeId}` : 'No trainee selected');
        }

        async function loadWeightedSkillPreview({ force = false } = {}) {
            const { traineeName, traineeId } = selectedTraineeForPlanner();
            if (!traineeName && !traineeId) {
                state.weightedSkillPreview = null;
                return null;
            }
            if (!force && state.weightedSkillPreview && state.weightedSkillPreview._key === `${traineeId}|${traineeName}|${state.selectedPreset}`) {
                return state.weightedSkillPreview;
            }
            const data = await apiJson('/api/skills/weighted-preview', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    trainee_name: traineeName,
                    trainee_id: String(traineeId || ''),
                    preset_name: state.selectedPreset || '',
                    limit: 40
                })
            });
            data._key = `${traineeId}|${traineeName}|${state.selectedPreset}`;
            state.weightedSkillPreview = data;
            return data;
        }

        function renderWeightedSkillPreviewBox() {
            const box = document.getElementById('weighted-live-preview');
            if (!box) return;
            const preview = state.weightedSkillPreview;
            if (!preview) {
                box.innerHTML = `<div class="weighted-preview-empty">Select a trainee to view their live weighted skill profile.</div>`;
                return;
            }
            const profile = preview.profile || {};
            const style = profile.recommended_style || profile.running_style || 'auto';
            const primary = (profile.primary_distances || []).join(', ') || 'auto';
            const secondary = (profile.secondary_distances || []).join(', ') || 'none';
            const source = profile.profile_source || profile.source || 'profile';
            const skills = (preview.ranked_skills || []).slice(0, 12).map(row => {
                const reasons = (row.reasons || []).slice(0, 3).join(' · ');
                const skillName = row.skill || row.name || '';
                return `<div class="weighted-preview-skill ${row.color === 'green' ? 'green' : 'yellow'}" data-skill="${escapeAttr(skillName)}">
                    <div><strong>${escapeHtml(skillName)}</strong><span>${escapeHtml(reasons || row.tier || row.color || '')}</span></div>
                    <input class="weighted-preview-manual" type="number" step="5" value="${escapeAttr(row.manual_weight || 0)}" title="Manual score adjustment">
                    <em>${escapeHtml(row.score ?? 0)}</em>
                </div>`;
            }).join('');
            const weights = preview.logic?.weights || {};
            box.innerHTML = `
                <div class="weighted-preview-head">
                    <div><span>TRAINEE PROFILE</span><strong>${escapeHtml(profile.name || selectedTraineeDisplayName())}</strong></div>
                    <b>${escapeHtml(source)}</b>
                </div>
                <div class="weighted-preview-meta">
                    <span>Style: <strong>${escapeHtml(style)}</strong></span>
                    <span>Primary: <strong>${escapeHtml(primary)}</strong></span>
                    <span>Secondary: <strong>${escapeHtml(secondary)}</strong></span>
                    <span>Green cap: <strong>${escapeHtml(preview.logic?.green_cap ?? '-')}</strong></span>
                </div>
                <div class="weighted-preview-weights">
                    <span>Recommended ${escapeHtml(weights.character_recommended_bonus ?? weights.recommended ?? 'auto')}</span>
                    <span>Yellow ${escapeHtml(weights.yellow_skill_bonus ?? weights.yellow ?? 'auto')}</span>
                    <span>Style ${escapeHtml(weights.style_match_bonus ?? weights.style ?? 'auto')}</span>
                    <span>Distance ${escapeHtml(weights.distance_match_bonus ?? weights.distance ?? 'auto')}</span>
                </div>
                <div class="weighted-preview-title">LIVE TOP WEIGHTED SKILLS</div>
                <div class="weighted-preview-list">${skills || '<div class="weighted-preview-empty">No weighted skills available.</div>'}</div>
            `;

            box.querySelectorAll('.weighted-preview-manual').forEach(input => {
                input.addEventListener('change', async () => {
                    const skill = input.closest('.weighted-preview-skill')?.dataset.skill;
                    if (!skill) return;
                    const current = getCurrentPreset();
                    const strategy = getSkillStrategy(current);
                    strategy.manual_skill_weights = strategy.manual_skill_weights || {};
                    const value = Number(input.value || 0);
                    if (value === 0) delete strategy.manual_skill_weights[skill];
                    else strategy.manual_skill_weights[skill] = value;
                    await saveWeightedSkillStrategy();
                });
            });
        }

        async function refreshWeightedSkillPreview({ force = false } = {}) {
            const box = document.getElementById('weighted-live-preview');
            if (box) box.innerHTML = '<div class="weighted-preview-empty">Loading weighted preview...</div>';
            try {
                await loadSelectedTraineeProfile({ force });
                await loadWeightedSkillPreview({ force });
            } catch (e) {
                state.weightedSkillPreview = null;
                if (box) box.innerHTML = `<div class="weighted-preview-empty">Weighted preview unavailable: ${escapeHtml(e.message || e)}</div>`;
                return;
            }
            renderWeightedSkillPreviewBox();
        }

        function renderWeightedSkillEditor() {
            const current = getCurrentPreset();
            if (!current) return;
            const strategy = getSkillStrategy(current);
            const distChecked = value => (strategy.primary_distances || []).includes(value) ? 'checked' : '';
            const secChecked = value => (strategy.secondary_distances || []).includes(value) ? 'checked' : '';
            const modalBody = els.skillModal.querySelector('.skill-editor-body');
            if (!modalBody) return;
            modalBody.innerHTML = `
                <div class="skill-editor-panel skill-editor-panel-left weighted-skill-panel">
                    <div class="skill-editor-panel-head"><div class="skill-editor-section-title">WEIGHTED STRATEGY</div></div>
                    <div id="weighted-live-preview" class="weighted-live-preview">
                        <div class="weighted-preview-empty">Select a trainee to view their live weighted skill profile.</div>
                    </div>
                    <div class="weighted-grid">
                        <label><span>Profile</span><select id="weighted-profile" class="form-input"><option value="auto">Auto from selected trainee</option><option value="manual">Manual preset override</option></select></label>
                        <label><span>Track</span><select id="weighted-track" class="form-input"><option value="auto">Auto</option><option value="turf">Turf</option><option value="dirt">Dirt</option></select></label>
                        <label><span>Max Greens / Batch</span><input id="weighted-max-green" class="form-input" type="number" min="0" max="5" value="${escapeAttr(strategy.max_green_per_purchase)}"></label>
                    </div>
                    <div class="weighted-checks"><strong>Primary distance</strong>
                        ${['sprint','mile','medium','long'].map(d => `<label><input class="weighted-distance-primary" type="checkbox" value="${d}" ${distChecked(d)}> ${d}</label>`).join('')}
                    </div>
                    <div class="weighted-checks muted"><strong>Secondary distance</strong>
                        ${['sprint','mile','medium','long'].map(d => `<label><input class="weighted-distance-secondary" type="checkbox" value="${d}" ${secChecked(d)}> ${d}</label>`).join('')}
                    </div>
                    <div class="weighted-weight-box">
                        <div class="skill-editor-section-title">SCORING WEIGHTS</div>
                        <label>Character recommended <input id="weighted-w-recommended" type="number" value="${escapeAttr(strategy.weights.recommended)}"></label>
                        <label>Community tier multiplier <input id="weighted-w-community" type="number" step="0.1" value="${escapeAttr(strategy.weights.community)}"></label>
                        <label>Yellow skill bonus <input id="weighted-w-yellow" type="number" value="${escapeAttr(strategy.weights.yellow)}"></label>
                        <label>Green penalty <input id="weighted-w-green" type="number" value="${escapeAttr(strategy.weights.green_penalty)}"></label>
                        <label>Style match <input id="weighted-w-style" type="number" value="${escapeAttr(strategy.weights.style)}"></label>
                        <label>Distance match <input id="weighted-w-distance" type="number" value="${escapeAttr(strategy.weights.distance)}"></label>
                    </div>
                    <div class="weighted-zone-title">MANUAL SKILL WEIGHT OVERRIDES</div>
                    <div id="weighted-manual-weights" class="weighted-manual-weights"></div>
                    <div class="weighted-zone-title">FORCED / MUST-BUY SKILLS</div>
                    <div id="weighted-forced-skills" class="weighted-skill-zone"></div>
                    <div class="weighted-zone-title danger">BLACKLIST</div>
                    <div id="weighted-blacklist" class="weighted-skill-zone"></div>
                    <button id="weighted-save-btn" class="btn btn-primary weighted-save" type="button">SAVE STRATEGY</button>
                </div>
                <div class="skill-editor-panel skill-editor-panel-right weighted-skill-panel">
                    <div class="skill-editor-panel-head stack">
                        <div class="skill-editor-section-title">SKILL LIBRARY</div>
                        <input id="weighted-skill-search" class="form-input skill-editor-search" placeholder="Search skills to force or blacklist...">
                        <div class="weighted-help">Buying order: character recommended first, then community tier list, then yellow skills, with green skills capped.</div>
                    </div>
                    <div id="weighted-skill-list" class="skill-editor-scroll weighted-skill-list"></div>
                </div>`;
            document.getElementById('weighted-profile').value = current.skill_profile || 'auto';
            document.getElementById('weighted-track').value = strategy.track || 'auto';
            modalBody.querySelectorAll('input,select').forEach(el => el.addEventListener('change', saveWeightedSkillStrategy));
            document.getElementById('weighted-save-btn')?.addEventListener('click', saveWeightedSkillStrategy);
            document.getElementById('weighted-skill-search')?.addEventListener('input', renderWeightedSkillList);
            renderWeightedSkillEditorLists();
            renderWeightedSkillPreviewBox();
            refreshWeightedSkillPreview({ force: true });
            loadSkillData().then(() => renderWeightedSkillList());
        }

        function skillReadonlyRow(title, description, badge) {
            return `<div class="skill-style-row"><div><strong>${escapeHtml(title)}</strong><span>${escapeHtml(description)}</span></div><em>${escapeHtml(badge)}</em></div>`;
        }
        function skillToggleRow(title, description, key, checked) {
            return `<label class="skill-toggle-row"><div><strong>${escapeHtml(title)}</strong><span>${escapeHtml(description)}</span></div><input class="skill-config-toggle" data-key="${escapeAttr(key)}" type="checkbox" ${checked ? 'checked' : ''}></label>`;
        }
        function skillSelectRow(title, key, value, options) {
            return `<label class="skill-select-row"><strong>${escapeHtml(title)}</strong><select class="form-input skill-config-select" data-key="${escapeAttr(key)}">${options.map(([v, label]) => `<option value="${escapeAttr(v)}" ${String(v) === String(value) ? 'selected' : ''}>${escapeHtml(label)}</option>`).join('')}</select></label>`;
        }
        function skillIconPath(skill) {
            const icon = skill && (skill.icon || skill.icon_id || skill.iconId);
            // Skill icons use a dedicated namespace; /api/images is for card
            // portraits and its ids collide with skill icon_ids (e.g. 20013).
            return icon ? `/api/skill-icons/${encodeURIComponent(icon)}.png` : '/sweep.png';
        }
        function skillCategoryLabel(skill) {
            const tags = Array.isArray(skill?.tags) ? skill.tags : Array.from(skill?.tags || []);
            const bits = [];
            if (tags.includes(101)) bits.push('Front');
            if (tags.includes(102)) bits.push('Pace');
            if (tags.includes(103)) bits.push('Late');
            if (tags.includes(104)) bits.push('End');
            if (tags.includes(201)) bits.push('Sprint');
            if (tags.includes(202)) bits.push('Mile');
            if (tags.includes(203)) bits.push('Medium');
            if (tags.includes(204)) bits.push('Long');
            if (tags.includes(502)) bits.push('Dirt');
            return bits.join(' · ') || 'General';
        }
        async function renderSkillConfig() {
            const cfg = await loadSkillConfig();
            const strategy = getSkillStrategy(cfg);
            const body = els.skillConfigBody;
            if (!body) return;
            body.innerHTML = `
                <section class="skill-info-card"><button class="skill-info-toggle" type="button">ⓘ How skill spending works <span>⌃</span></button><div class="skill-info-body"><p>Allows configuration of automated skill point spending.</p><p>This feature buys skills automatically once the Skill Point Threshold is reached. Use it to make rank-farming runs less of a hassle.</p></div></section>
                <section class="skill-settings-section"><h3>OPTIMIZE SP SPEND</h3><div class="skill-card">
                    <div class="skill-optimizer-desc">
                        <p><strong>What it does:</strong> spends your skill points to squeeze out the most total skill value per point — a value-for-money optimizer — instead of buying strictly top-to-bottom in your priority order.</p>
                        <p><strong>How it works:</strong> at every purchase point it ranks each affordable skill by its value &divide; SP cost and fills your available SP with the best-value picks first. You usually come away with more useful skills overall, rather than a couple of expensive top-priority skills draining the whole budget.</p>
                        <p><strong>Turning it off:</strong> leave it off (the default) to keep the standard priority-order buying. You can flip it any time, and the change applies to your next run.</p>
                    </div>
                    <label class="skill-optimizer-row"><span class="skill-optimizer-row-label"><strong>Optimize SP spend</strong><em>Value-per-point buying (off = priority order)</em></span><input type="checkbox" id="skill-optimizer-toggle"></label>
                </div></section>
                <section class="skill-settings-section"><h3>STYLE</h3><div class="skill-card">
                    ${skillReadonlyRow('Running Style', 'Dictates which skills are considered for purchase based on the preferred running style.', 'FROM RACING')}
                    ${skillReadonlyRow('Track Distance', 'Dictates which skills are considered for purchase based on the track distance.', 'FROM TRAINING')}
                    ${skillReadonlyRow('Track Surface', 'Dictates which skills are considered for purchase based on the terrain.', strategy.track && strategy.track !== 'auto' ? String(strategy.track).toUpperCase() : 'ANY')}
                </div></section>
                <section class="skill-info-card"><button class="skill-info-toggle" type="button">ⓘ How Running Style affects skill picks <span>⌃</span></button><div class="skill-info-body"><p>Running Style is inherited from Racing Settings. Configure Skills only filters and weights skill purchases; it does not own race strategy.</p></div></section>
                <section class="skill-settings-section"><h3>SKILL PLANS</h3><div class="skill-plan-tabs"><button class="skill-plan-tab is-active" data-plan="skill_point_check">Skill Point Check</button><button class="skill-plan-tab" data-plan="pre_finals">Pre-Finals</button><button class="skill-plan-tab" data-plan="career_complete">Career Complete</button></div><div id="skill-plan-body"></div></section>
                <section class="skill-settings-section"><h3>SKILL TYPE FILTERS</h3><div class="skill-card">
                    ${skillToggleRow('Skip Green Skills', 'Exclude green stat-trigger skills', 'skip_green_skills', !!cfg.skip_green_skills)}
                    ${skillToggleRow('Skip Red Skills', 'Exclude red debuff skills', 'skip_red_skills', !!cfg.skip_red_skills)}
                    ${skillToggleRow('Skip Unique Skills', 'Exclude inherited unique legacy skills', 'skip_unique_skills', !!cfg.skip_unique_skills)}
                </div></section>
                <section class="skill-settings-section"><h3>STRATEGY & PLANNED SKILLS</h3><div class="skill-card">
                    ${skillSelectRow('Automated Skill Point Spending Strategy', 'skill_spending_strategy', cfg.skill_spending_strategy || 'best_skills_first', [['best_skills_first','Best Skills First'], ['optimize_rank','Optimize Rank']])}
                    <div class="planned-skills-head"><div><strong>Planned Skills</strong><span>Selected ${(strategy.forced_skills || []).length} / ${(skillDataCache || []).length} skills</span></div><button id="skill-clear-planned-btn" class="btn btn-sm btn-danger-soft" type="button">Clear</button></div>
                    <div class="skill-plan-blacklist-tabs"><button class="skill-subtab ${(state.skillConfigActiveZone || 'plan') === 'plan' ? 'is-active' : ''}" data-zone="plan">Plan (${(strategy.forced_skills || []).length})</button><button class="skill-subtab ${(state.skillConfigActiveZone || 'plan') === 'blacklist' ? 'is-active' : ''}" data-zone="blacklist">Blacklist (${(strategy.blacklist || []).length})</button></div>
                    ${skillToggleRow('Show Only Selected Skills', 'Filter the list to only currently selected skills', 'show_only_selected_skills', !!cfg.show_only_selected_skills)}
                    <input id="skill-config-search" class="form-input skill-config-search" placeholder="Search skills by name...">
                    <div id="skill-config-list" class="skill-config-list"></div>
                </div></section>
                <section class="skill-settings-section v73-manual-tier-section"><h3>MANUAL SKILL TIERS <span class="v73-section-mode-badge" id="v73-manual-tier-mode-badge"></span></h3><div class="skill-card v73-manual-tier-card">
                    <div class="v73-manual-tier-intro">
                        Build a tier list of the skills you want the bot to buy. Whenever any tier has skills, this list <strong>drives purchasing</strong> — the bot buys these by tier (T1 first), and manually-listed skills are bought even if they're off-distance/off-style. Within a tier, smart score / cost breaks ties.
                        <span class="v73-manual-tier-fallback-note">If all tiers are empty, the bot uses the automatic skill-point plan instead. The plan now hard-filters off-distance and off-style skills so it never buys skills that don't fit the trainee.</span>
                    </div>
                                        <label class="v73-manual-tier-toggle" for="v73-dont-spend-extra" title="Off (default): buy only the listed skills, then stop. On: once every listed skill is owned, switch to the automatic plan and spend remaining skill points on it.">
                        <input type="checkbox" id="v73-dont-spend-extra">
                        <span><strong>After selected skills are bought, switch to AUTO purchasing</strong> - off (default) buys only the skills in these tiers then stops, leaving remaining SP unspent; turn on to let the automatic plan spend the rest once your listed skills are all owned.</span>
                    </label>
                    <div id="v73-manual-tier-rows" class="v73-manual-tier-rows"></div>
                    <div class="v73-manual-tier-search-row">
                        <input id="v73-manual-tier-search" class="form-input" placeholder="Search skills to add to a tier...">
                        <select id="v73-manual-tier-target" class="form-input v73-manual-tier-target">
                            <option value="1">Add to Tier 1 (S)</option>
                            <option value="2">Add to Tier 2 (A)</option>
                            <option value="3" selected>Add to Tier 3 (B)</option>
                            <option value="4">Add to Tier 4 (C)</option>
                            <option value="5">Add to Tier 5 (D)</option>
                        </select>
                    </div>
                    <div id="v73-manual-tier-results" class="v73-manual-tier-results"></div>
                </div></section>
                <section class="skill-settings-section"><h3>CONFIGURATION SUMMARY</h3><div id="skill-config-summary" class="skill-config-summary"></div></section>`;
            body.querySelectorAll('.skill-plan-tab').forEach(btn => btn.addEventListener('click', () => {
                body.querySelectorAll('.skill-plan-tab').forEach(b => b.classList.remove('is-active'));
                btn.classList.add('is-active');
                renderSkillPlanBody(btn.dataset.plan || 'skill_point_check');
            }));
            body.querySelectorAll('.skill-subtab').forEach(btn => btn.addEventListener('click', () => {
                state.skillConfigActiveZone = btn.dataset.zone || 'plan';
                body.querySelectorAll('.skill-subtab').forEach(b => b.classList.remove('is-active'));
                btn.classList.add('is-active');
                renderSkillConfigList();
            }));
            bindSkillConfigControls(body);
            renderSkillPlanBody('skill_point_check');
            await loadSkillData();
            renderSkillConfigList();
            renderSkillConfigSummary();
            // v7.3 — Manual skill tiers section.
            renderManualTierSection();
            bindManualTierControls();
            loadSkillOptimizer();
        }
        function renderSkillPlanBody(plan) {
            const cfg = getSkillConfig();
            const body = document.getElementById('skill-plan-body');
            if (!body) return;
            if (plan !== 'skill_point_check') {
                body.innerHTML = `<div class="skill-card"><p class="muted">This plan uses the same weighted purchase rules when triggered by ${escapeHtml(plan.replaceAll('_', ' '))}.</p>${skillToggleRow('Enable Plan', `Purchase skills during ${plan.replaceAll('_', ' ')}.`, `${plan}_enabled`, !!cfg[`${plan}_enabled`])}</div>`;
                bindSkillConfigControls(body);
                return;
            }
            body.innerHTML = `<div class="skill-card">
                ${skillToggleRow('Enable Skill Point Check', 'Allow automatic skill spending once the threshold is reached.', 'enable_skill_point_check', cfg.enable_skill_point_check !== false)}
                <label class="skill-slider-row"><div><strong>Skill Point Threshold</strong><span>The number of skill points to accumulate before purchasing skills.</span></div><input class="skill-config-number" data-key="learn_skill_threshold" type="number" min="100" max="2000" step="10" value="${escapeAttr(cfg.learn_skill_threshold ?? 888)}"></label>
                ${skillToggleRow('Enable Skill Point Check Plan (Beta)', 'Purchase skills based on this plan configuration.', 'enable_skill_point_check_plan', cfg.enable_skill_point_check_plan !== false)}
                ${skillToggleRow('Purchase All Negative Skills', 'Attempt to buy all negative skills when available.', 'purchase_negative_skills', !!cfg.purchase_negative_skills)}
            </div>`;
            bindSkillConfigControls(body);
        }
        async function saveCurrentSkillStrategyPatch(patch = {}) {
            const cfg = getSkillConfig();
            const strategy = getSkillStrategy(cfg);
            await saveSkillConfig({ ...patch, skill_strategy: strategy, learn_skill_list: (strategy.forced_skills || []).length ? [strategy.forced_skills] : [], learn_skill_blacklist: strategy.blacklist || [] });
        }
        function updateSkillSubtabCounts() {
            const cfg = getSkillConfig();
            const strategy = getSkillStrategy(cfg);
            const planTab = document.querySelector('.skill-subtab[data-zone="plan"]');
            const blTab = document.querySelector('.skill-subtab[data-zone="blacklist"]');
            if (planTab) planTab.textContent = `Plan (${(strategy.forced_skills || []).length})`;
            if (blTab) blTab.textContent = `Blacklist (${(strategy.blacklist || []).length})`;
            const head = document.querySelector('.planned-skills-head span');
            if (head) head.textContent = `Selected ${(strategy.forced_skills || []).length} / ${(skillDataCache || []).length} skills`;
        }
        function renderSkillConfigList() {
            const list = document.getElementById('skill-config-list');
            if (!list) return;
            const cfg = getSkillConfig();
            const strategy = getSkillStrategy(cfg);
            const query = (document.getElementById('skill-config-search')?.value || '').toLowerCase();
            const activeZone = state.skillConfigActiveZone || document.querySelector('.skill-subtab.is-active')?.dataset.zone || 'plan';
            const forced = new Set(strategy.forced_skills || []);
            const blacklist = new Set(strategy.blacklist || []);
            const onlySelected = !!cfg.show_only_selected_skills;
            const rows = (skillDataCache || []).filter(s => {
                if (!s || !s.name) return false;
                if (query && !String(s.name).toLowerCase().includes(query)) return false;
                if (!onlySelected) return true;
                return forced.has(s.name) || blacklist.has(s.name);
            }).slice(0, 500);
            list.innerHTML = rows.map(s => {
                const planned = forced.has(s.name);
                const blocked = blacklist.has(s.name);
                const active = activeZone === 'plan' ? planned : blocked;
                return `<button type="button" class="skill-config-row ${active ? 'is-active' : ''} ${blocked ? 'is-blacklisted' : ''}" data-skill="${escapeAttr(s.name)}"><img src="${escapeAttr(skillIconPath(s))}" onerror="this.src='/sweep.png'" alt=""><span><strong>${escapeHtml(s.name)}</strong><em>${escapeHtml(s.description || s.desc || '')}</em><b>ID: ${escapeHtml(s.id || '')}</b></span></button>`;
            }).join('') || '<div class="weighted-empty">No skills match the current filters.</div>';
            list.querySelectorAll('.skill-config-row').forEach(row => row.addEventListener('click', async () => {
                const name = row.dataset.skill;
                if (!name) return;
                const cfg = getSkillConfig();
                const strategy = getSkillStrategy(cfg);
                if (activeZone === 'blacklist') {
                    strategy.blacklist = (strategy.blacklist || []).includes(name) ? strategy.blacklist.filter(v => v !== name) : [...(strategy.blacklist || []), name];
                } else {
                    strategy.forced_skills = (strategy.forced_skills || []).includes(name) ? strategy.forced_skills.filter(v => v !== name) : [...(strategy.forced_skills || []), name];
                }
                await saveCurrentSkillStrategyPatch();
                // Targeted refresh: do NOT call renderSkillConfig() here — a full
                // rebuild blows away the live search input (and its typed text) and
                // resets the active subtab. Re-read the live list, refresh the summary,
                // and update the Plan(n)/Blacklist(n) labels in place.
                renderSkillConfigList();
                renderSkillConfigSummary();
                updateSkillSubtabCounts();
            }));
            // v7.6 — right-click a shown skill to drop it straight into a manual tier.
            list.querySelectorAll('.skill-config-row').forEach(row => row.addEventListener('contextmenu', (e) => {
                const name = row.dataset.skill;
                if (name) _v73ShowTierMenu(e, name);
            }));
        }
        // v7.3 — Manual skill tiers.
        // Reads/writes skill_config.manual_skill_tiers, a dict of "1".."5" →
        // array of skill names. Used by the bot only when
        // enable_skill_point_check_plan is false.
        const _v73TierLabels = {
            '1': { label: 'S', desc: 'Buy first when available' },
            '2': { label: 'A', desc: 'Buy after S' },
            '3': { label: 'B', desc: 'Buy after A' },
            '4': { label: 'C', desc: 'Buy after B' },
            '5': { label: 'D', desc: 'Buy last, only if SP remains' },
        };
        function _v73GetTiers() {
            const cfg = getSkillConfig();
            const raw = cfg.manual_skill_tiers || {};
            const out = {};
            for (const k of ['1','2','3','4','5']) {
                out[k] = Array.isArray(raw[k]) ? raw[k].slice() : [];
            }
            return out;
        }
        function _v73TierAssignmentOf(tiers, name) {
            for (const k of ['1','2','3','4','5']) {
                if ((tiers[k] || []).includes(name)) return k;
            }
            return null;
        }
        function _v73TotalAssigned(tiers) {
            return ['1','2','3','4','5'].reduce((n, k) => n + (tiers[k] || []).length, 0);
        }
        async function _v73SaveTiers(tiers) {
            await saveSkillConfig({ manual_skill_tiers: tiers });
        }
        // v7.6 — shared assign helper used by the search box, the right-click
        // context menu, and tier-to-tier drag. Pass an empty/falsey targetTier
        // to just remove the skill from all tiers. Skills are unique across
        // tiers, so we always strip from every tier before (re)assigning.
        async function _v73AssignToTier(name, targetTier) {
            if (!name) return;
            const t = _v73GetTiers();
            for (const k of ['1','2','3','4','5']) {
                t[k] = (t[k] || []).filter(n => n !== name);
            }
            if (targetTier && _v73TierLabels[targetTier]) {
                t[targetTier] = [...(t[targetTier] || []), name];
            }
            await _v73SaveTiers(t);
            renderManualTierSection();
            if (typeof renderSkillConfigList === 'function') renderSkillConfigList();
            renderManualTierSearchResults();
        }
        // v7.6 — lightweight floating context menu (no such pattern existed
        // before). Right-clicking a shown skill or a tier chip offers
        // "Move to Tier X" actions.
        let _v73Menu = null;
        function _v73MenuKey(e) { if (e.key === 'Escape') _v73CloseMenu(); }
        function _v73CloseMenu() {
            if (_v73Menu) { _v73Menu.remove(); _v73Menu = null; }
            document.removeEventListener('click', _v73CloseMenu);
            document.removeEventListener('keydown', _v73MenuKey);
        }
        function _v73ShowTierMenu(evt, name) {
            evt.preventDefault();
            _v73CloseMenu();
            if (!name) return;
            const tiers = _v73GetTiers();
            const current = _v73TierAssignmentOf(tiers, name);
            const menu = document.createElement('div');
            menu.className = 'v73-tier-context-menu';
            const items = ['1','2','3','4','5'].map(k => {
                const lbl = _v73TierLabels[k];
                const isCur = current === k;
                return `<button type="button" class="v73-ctx-item ${isCur ? 'is-current' : ''}" data-tier="${k}">Move to Tier ${lbl.label} <em>(T${k})</em>${isCur ? ' ✓' : ''}</button>`;
            }).join('');
            const removeItem = current ? `<button type="button" class="v73-ctx-item v73-ctx-remove" data-tier="">Remove from tiers</button>` : '';
            menu.innerHTML = `<div class="v73-ctx-head">${escapeHtml(name)}</div>${items}${removeItem}`;
            document.body.appendChild(menu);
            const rect = menu.getBoundingClientRect();
            const px = Math.max(8, Math.min(evt.clientX, window.innerWidth - rect.width - 8));
            const py = Math.max(8, Math.min(evt.clientY, window.innerHeight - rect.height - 8));
            menu.style.left = px + 'px';
            menu.style.top = py + 'px';
            menu.querySelectorAll('.v73-ctx-item').forEach(it => {
                it.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    const tier = it.dataset.tier;
                    _v73CloseMenu();
                    await _v73AssignToTier(name, tier);
                });
            });
            _v73Menu = menu;
            setTimeout(() => {
                document.addEventListener('click', _v73CloseMenu);
                document.addEventListener('keydown', _v73MenuKey);
            }, 0);
        }
        function renderManualTierSection() {
            const rows = document.getElementById('v73-manual-tier-rows');
            if (!rows) return;
            const cfg = getSkillConfig();
            const tiers = _v73GetTiers();
            const totalAssigned = _v73TotalAssigned(tiers);
            const autoFallback = cfg.skill_manual_auto_fallback === true;
            // Keep the toggle's checked state in sync with the saved config.
            const toggle = document.getElementById('v73-dont-spend-extra');
            if (toggle) toggle.checked = autoFallback;
            // Mode badge — make it clear when this section is active. Manual tiers
            // now drive purchasing whenever any tier has skills, regardless of the
            // Plan Check (Beta) toggle.
            const badge = document.getElementById('v73-manual-tier-mode-badge');
            if (badge) {
                if (totalAssigned === 0) {
                    badge.textContent = 'INACTIVE — no tiers set (auto plan in use)';
                    badge.className = 'v73-section-mode-badge is-inactive';
                } else if (!autoFallback) {
                    badge.textContent = 'ACTIVE — buying listed skills only, then stopping';
                    badge.className = 'v73-section-mode-badge is-active';
                } else {
                    badge.textContent = 'ACTIVE — listed skills first, then auto plan';
                    badge.className = 'v73-section-mode-badge is-active';
                }
            }
            rows.innerHTML = ['1','2','3','4','5'].map(k => {
                const lbl = _v73TierLabels[k];
                const chips = (tiers[k] || []).map(name => (
                    `<button type="button" class="v73-tier-chip" draggable="true" data-tier="${k}" data-skill="${escapeAttr(name)}" title="Drag to another tier · right-click for options · click × to remove">${escapeHtml(name)} <span class="v73-tier-chip-x">×</span></button>`
                )).join('');
                const emptyMsg = (tiers[k] || []).length === 0 ? `<span class="v73-tier-empty">No skills in Tier ${lbl.label} yet — drag a chip here or right-click a skill.</span>` : '';
                return `<div class="v73-tier-row v73-tier-${k}" data-tier="${k}">
                    <div class="v73-tier-row-head">
                        <div class="v73-tier-row-title"><span class="v73-tier-badge">T${k}</span> Tier ${lbl.label} <em>${escapeHtml(lbl.desc)}</em></div>
                        <div class="v73-tier-row-count">${(tiers[k] || []).length} skill(s)</div>
                    </div>
                    <div class="v73-tier-chips">${chips}${emptyMsg}</div>
                </div>`;
            }).join('');
            // Wire chip remove + drag + right-click (v7.6)
            rows.querySelectorAll('.v73-tier-chip').forEach(chip => {
                chip.addEventListener('click', async () => {
                    const k = chip.dataset.tier, name = chip.dataset.skill;
                    if (!k || !name) return;
                    const t = _v73GetTiers();
                    t[k] = (t[k] || []).filter(n => n !== name);
                    await _v73SaveTiers(t);
                    renderManualTierSection();
                });
                chip.addEventListener('dragstart', (e) => {
                    chip.classList.add('is-dragging');
                    try {
                        e.dataTransfer.setData('text/plain', JSON.stringify({ name: chip.dataset.skill, from: chip.dataset.tier }));
                        e.dataTransfer.effectAllowed = 'move';
                    } catch (_) {}
                });
                chip.addEventListener('dragend', () => chip.classList.remove('is-dragging'));
                chip.addEventListener('contextmenu', (e) => {
                    if (chip.dataset.skill) _v73ShowTierMenu(e, chip.dataset.skill);
                });
            });
            // Tier rows are drop targets for chips dragged from other tiers.
            rows.querySelectorAll('.v73-tier-row').forEach(rowEl => {
                rowEl.addEventListener('dragover', (e) => {
                    e.preventDefault();
                    if (e.dataTransfer) e.dataTransfer.dropEffect = 'move';
                    rowEl.classList.add('is-drop-target');
                });
                rowEl.addEventListener('dragleave', () => rowEl.classList.remove('is-drop-target'));
                rowEl.addEventListener('drop', async (e) => {
                    e.preventDefault();
                    rowEl.classList.remove('is-drop-target');
                    const targetTier = rowEl.dataset.tier;
                    let payload = {};
                    try { payload = JSON.parse((e.dataTransfer && e.dataTransfer.getData('text/plain')) || '{}'); } catch (_) {}
                    if (payload.name && targetTier && String(payload.from) !== String(targetTier)) {
                        await _v73AssignToTier(payload.name, targetTier);
                    }
                });
            });
        }
        function renderManualTierSearchResults() {
            const out = document.getElementById('v73-manual-tier-results');
            if (!out) return;
            const q = ((document.getElementById('v73-manual-tier-search')?.value) || '').toLowerCase().trim();
            if (!q) {
                out.innerHTML = '';
                return;
            }
            const tiers = _v73GetTiers();
            const rows = (skillDataCache || []).filter(s => s && s.name && String(s.name).toLowerCase().includes(q)).slice(0, 80);
            if (!rows.length) {
                out.innerHTML = '<div class="weighted-empty">No skills match.</div>';
                return;
            }
            out.innerHTML = rows.map(s => {
                const assigned = _v73TierAssignmentOf(tiers, s.name);
                const assignedLabel = assigned ? `<span class="v73-result-assigned">In Tier ${_v73TierLabels[assigned].label}</span>` : '';
                return `<button type="button" class="v73-tier-search-result ${assigned ? 'is-assigned' : ''}" data-skill="${escapeAttr(s.name)}">
                    <img src="${escapeAttr(skillIconPath(s))}" onerror="this.src='/sweep.png'" alt="">
                    <span><strong>${escapeHtml(s.name)}</strong><em>${escapeHtml(s.description || s.desc || '')}</em></span>
                    ${assignedLabel}
                </button>`;
            }).join('');
            out.querySelectorAll('.v73-tier-search-result').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const name = btn.dataset.skill;
                    if (!name) return;
                    const targetTier = String(document.getElementById('v73-manual-tier-target')?.value || '3');
                    const t = _v73GetTiers();
                    // Remove from any existing tier first to enforce uniqueness across tiers.
                    for (const k of ['1','2','3','4','5']) {
                        t[k] = (t[k] || []).filter(n => n !== name);
                    }
                    t[targetTier] = [...(t[targetTier] || []), name];
                    await _v73SaveTiers(t);
                    renderManualTierSection();
                    renderManualTierSearchResults();
                });
            });
        }
        function bindManualTierControls() {
            const search = document.getElementById('v73-manual-tier-search');
            if (search && !search.dataset.v73Bound) {
                search.dataset.v73Bound = '1';
                let debounce;
                search.addEventListener('input', () => {
                    clearTimeout(debounce);
                    debounce = setTimeout(renderManualTierSearchResults, 120);
                });
            }
            // When plan-check toggle changes, refresh the badge.
            document.querySelectorAll('.skill-config-toggle[data-key="enable_skill_point_check_plan"]').forEach(el => {
                if (el.dataset.v73Bound) return;
                el.dataset.v73Bound = '1';
                el.addEventListener('change', () => setTimeout(renderManualTierSection, 80));
            });
            // "Don't spend extra skill points" toggle.
            const dontSpend = document.getElementById('v73-dont-spend-extra');
            if (dontSpend && !dontSpend.dataset.v73Bound) {
                dontSpend.dataset.v73Bound = '1';
                dontSpend.addEventListener('change', async () => {
                    await saveSkillConfig({ skill_manual_auto_fallback: dontSpend.checked });
                    renderManualTierSection();
                    renderSkillConfigSummary();
                });
            }
        }
        function renderSkillConfigSummary() {
            const box = document.getElementById('skill-config-summary');
            if (!box) return;
            const cfg = getSkillConfig();
            const strategy = getSkillStrategy(cfg);
            // v7.3 — include manual tier totals so the summary reflects all relevant config in one place.
            const tiers = cfg.manual_skill_tiers || {};
            const tierCounts = ['1','2','3','4','5'].map(k => (Array.isArray(tiers[k]) ? tiers[k].length : 0));
            const totalTiered = tierCounts.reduce((a, b) => a + b, 0);
            const tierSummary = totalTiered === 0
                ? '(none)'
                : `${totalTiered} total · ` + tierCounts.map((n, i) => `T${i+1}:${n}`).filter((_, i) => tierCounts[i] > 0).join(' ');
            const tierActive = totalTiered > 0;
            box.innerHTML = `<div class="skill-summary-grid"><span>STRATEGY</span><strong>${escapeHtml(cfg.skill_spending_strategy === 'optimize_rank' ? 'Optimize Rank' : 'Best Skills First')}</strong><span>THRESHOLD</span><strong>${escapeHtml(cfg.learn_skill_threshold ?? 888)}</strong><span>NEGATIVE</span><strong>${cfg.purchase_negative_skills ? 'Yes' : 'No'}</strong><span>EXCLUDED</span><strong>${[cfg.skip_green_skills?'Green':'', cfg.skip_red_skills?'Red':'', cfg.skip_unique_skills?'Unique':''].filter(Boolean).join(', ') || '(none)'}</strong><span>PLANNED</span><strong>${(strategy.forced_skills || []).join(', ') || '(none)'}</strong><span>BLACKLISTED</span><strong>${(strategy.blacklist || []).join(', ') || '(none)'}</strong><span>MANUAL TIERS${tierActive ? ' <em class="v73-summary-active">(active)</em>' : ''}</span><strong>${tierSummary}</strong></div>`;
        }
        function bindSkillConfigControls(root = document) {
            root.querySelectorAll('.skill-config-toggle').forEach(input => input.addEventListener('change', async () => {
                await saveSkillConfig({ [input.dataset.key]: input.checked });
                renderSkillConfigSummary();
                renderSkillConfigList();
            }));
            root.querySelectorAll('.skill-config-number').forEach(input => input.addEventListener('change', async () => {
                const min = Number(input.min || 0), max = Number(input.max || 99999);
                const value = Math.max(min, Math.min(max, Number(input.value || 0)));
                input.value = String(value);
                await saveSkillConfig({ [input.dataset.key]: value });
                renderSkillConfigSummary();
            }));
            root.querySelectorAll('.skill-config-select').forEach(select => select.addEventListener('change', async () => {
                await saveSkillConfig({ [select.dataset.key]: select.value });
                renderSkillConfigSummary();
            }));
            root.querySelector('#skill-config-search')?.addEventListener('input', renderSkillConfigList);
            root.querySelector('#skill-clear-planned-btn')?.addEventListener('click', async () => {
                const cfg = getSkillConfig();
                const strategy = getSkillStrategy(cfg);
                strategy.forced_skills = [];
                await saveCurrentSkillStrategyPatch();
                await renderSkillConfig();
            });
        }
        async function initSkillEditor() {
            if (els.skillModal) els.skillModal.style.display = 'flex';
            await renderSkillConfig();
        }

        async function loadSkillOptimizer() {
            const t = document.getElementById('skill-optimizer-toggle');
            if (!t) return;
            try {
                const r = await apiJson('/api/skills/optimizer?t=' + Date.now());
                t.checked = !!(r && r.enabled);
            } catch (e) { /* leave as-is */ }
            if (!t.dataset.wired) {
                t.dataset.wired = '1';
                t.addEventListener('change', async () => {
                    try {
                        await apiJson('/api/skills/optimizer', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ enabled: t.checked })
                        });
                    } catch (e) { /* non-fatal */ }
                });
            }
        }

        async function savePresetConfig() {
            if (!state.selectedPreset || !state.presets) return;
            const current = getCurrentPreset();
            if (!current) return;
            current.selection = buildSelectionPresetSnapshot();

            try {
                const res = await apiJson('/api/settings-presets', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ preset: current })
                });
                if (res?.preset?.name) {
                    const idx = (state.presets || []).findIndex(p => p.name === res.preset.name);
                    if (idx >= 0) state.presets[idx] = res.preset;
                    state.selectedPreset = res.preset.name;
                    localStorage.setItem('uma_selected_preset', state.selectedPreset);
                    if (els.presetSelect) els.presetSelect.value = state.selectedPreset;
                }
            } catch (e) {}
        }

        function populatePresetUI() {
            if (!state.selectedPreset || !state.presets) return;
            const current = getCurrentPreset();
            if (!current) return;
            // Re-sync derived UI state and refresh any open settings panels so
            // they reflect the active preset's freshly-loaded values (previously
            // an empty stub, so a loaded preset's solver/scenario panels could
            // keep showing the prior preset until reopened).
            try { syncSelectedPresetRaces(); } catch (_) {}
            const open = (id) => document.getElementById(id)?.style.display === 'flex';
            if (open('training-settings-modal')) renderTrainingSettings();
            if (open('racing-settings-modal')) renderRacingSettings();
            if (open('scenario-settings-modal')) renderScenarioSettings();
            if (open('smart-solver-settings-modal')) renderSmartSolverSettings();
        }


        // v4.9 Trackblazer settings windows: only exposes controls backed by native Pre Icarus logic.
        const SETTINGS_STATS = [
            ['speed', 'Speed'], ['power', 'Power'], ['wit', 'Wit'], ['stamina', 'Stamina'], ['guts', 'Guts']
        ];
        const SETTINGS_DISTANCE_VALUES = [
            ['sprint', 'Sprint'], ['mile', 'Mile'], ['medium', 'Medium'], ['long', 'Long']
        ];
        const SETTINGS_SURFACE_VALUES = [['turf', 'Turf'], ['dirt', 'Dirt']];
        const SETTINGS_GRADE_VALUES = [['G1', 'G1'], ['G2', 'G2'], ['G3', 'G3'], ['OP', 'OP'], ['PRE-OP', 'Pre-OP']];
        const SETTINGS_STYLE_VALUES = [
            ['0', 'Auto'], ['1', 'Front Runner'], ['2', 'Pace Chaser'], ['3', 'Late Surger'], ['4', 'End Closer']
        ];
        const SETTINGS_SHOP_ITEMS = [
            'Speed Notepad','Stamina Notepad','Power Notepad','Guts Notepad','Wit Notepad',
            'Speed Manual','Stamina Manual','Power Manual','Guts Manual','Wit Manual',
            'Speed Scroll','Stamina Scroll','Power Scroll','Guts Scroll','Wit Scroll',
            'Vita 20','Vita 40','Vita 65','Royal Kale Juice','Energy Drink MAX','Energy Drink MAX EX',
            'Plain Cupcake','Berry Sweet Cupcake','Yummy Cat Food','Grilled Carrots','Pretty Mirror',
            "Reporter's Binoculars",'Master Practice Guide',"Scholar's Hat",'Fluffy Pillow','Pocket Planner',
            'Rich Hand Cream','Smart Scale','Aroma Diffuser','Practice Drills DVD','Miracle Cure',
            'Speed Training Application','Stamina Training Application','Power Training Application','Guts Training Application','Wit Training Application',
            'Reset Whistle','Coaching Megaphone','Motivating Megaphone','Empowering Megaphone',
            'Speed Ankle Weights','Stamina Ankle Weights','Power Ankle Weights','Guts Ankle Weights',
            'Good-Luck Charm','Artisan Cleat Hammer','Master Cleat Hammer','Glow Sticks'
        ];
        const DEFAULT_STAT_PRIORITY = SETTINGS_STATS.map(([value]) => value);
        const SOLVER_APTITUDE_ORDER = ['S', 'A', 'B', 'C', 'D', 'E', 'F', 'G'];
        const SOLVER_APTITUDE_KEYS = [
            ['Sprint', 'Sprint'], ['Mile', 'Mile'], ['Medium', 'Medium'], ['Long', 'Long'],
            ['Turf', 'Turf'], ['Dirt', 'Dirt']
        ];
        let SOLVER_DEFAULT_WEIGHTS = {
            raceValue: 1,
            epithetValue: 1,
            fanWeight: 0.001,
            hintRewardWeight: 8,
            consecutiveRacePenalty: 3,
            summerPenalty: 5,
            raceBonusPct: 50,
            raceCostPct: 100,
            forcedEpithetValue: 500
        };
        let solverDefaultsLoaded = false;
        let activePriorityModal = null;

        function currentPresetForSettings() {
            const current = getCurrentPreset();
            if (!current) {
                alert('Select or create a preset first.');
                return null;
            }
            current.mant_config = current.mant_config || {};
            return current;
        }
        function mantCfg(current) {
            current.mant_config = current.mant_config || {};
            return current.mant_config;
        }
        async function saveSettingsPreset(current, { refreshUI = true } = {}) {
            if (!current) return;
            current.selection = buildSelectionPresetSnapshot();
            try {
                const res = await apiJson('/api/settings-presets', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ preset: current })
                });
                if (res?.preset?.name) {
                    const idx = (state.presets || []).findIndex(p => p.name === res.preset.name);
                    if (idx >= 0) state.presets[idx] = res.preset;
                }
                // refreshUI:false skips the full panel rebuild (populatePresetUI ->
                // renderScenarioSettings -> body.innerHTML), which otherwise resets
                // the scroll position. Used by in-place toggles (e.g. shop-exclude
                // checkboxes) that need no re-render -- the control + in-memory
                // state are already updated and the POST already persisted.
                if (refreshUI) populatePresetUI();
            } catch (e) {
                console.warn('Failed to save settings preset', e);
            }
        }
        function engineMode(value) {
            // Normalize stored decision_mode (incl. legacy aliases) to the two UI
            // choices: "android" is a legacy alias for Trackblazer; "classic" maps
            // to "legacy"; anything else (incl. unset) defaults to Trackblazer.
            const v = String(value || '').trim().toLowerCase();
            if (v === 'legacy' || v === 'classic') return 'legacy';
            return 'trackblazer';
        }
        function getSetting(current, target, key, fallback) {
            const source = target === 'preset' ? current : mantCfg(current);
            return source[key] === undefined || source[key] === null ? fallback : source[key];
        }
        function setSettingValue(current, target, key, value) {
            if (target === 'mant_nested') {
                const parts = String(key || '').split('.');
                const root = parts.shift();
                const leaf = parts.join('.');
                const c = mantCfg(current);
                if (!c[root] || typeof c[root] !== 'object' || Array.isArray(c[root])) c[root] = {};
                c[root][leaf] = value;
                return;
            }
            const source = target === 'preset' ? current : mantCfg(current);
            source[key] = value;
        }
        function rowShell(title, desc, controlHtml) {
            return `<div class="settings-row"><div><strong>${escapeHtml(title)}</strong>${desc ? `<span>${escapeHtml(desc)}</span>` : ''}</div><div>${controlHtml}</div></div>`;
        }
        function toggleSetting(title, desc, key, value, target = 'mant') {
            return rowShell(title, desc, `<div class="settings-toggle-wrap"><input type="checkbox" class="settings-control" data-control="toggle" data-target="${target}" data-key="${escapeAttr(key)}" ${value ? 'checked' : ''}></div>`);
        }
        function sliderSetting(title, desc, key, value, min, max, step = 1, target = 'mant') {
            return rowShell(title, desc, `<div class="settings-slider-wrap"><input type="range" class="settings-control settings-range" data-control="number" data-target="${target}" data-key="${escapeAttr(key)}" min="${min}" max="${max}" step="${step}" value="${escapeAttr(value)}"><input type="number" class="settings-control settings-number-input" data-control="number" data-target="${target}" data-key="${escapeAttr(key)}" min="${min}" max="${max}" step="${step}" value="${escapeAttr(value)}"></div>`);
        }
        function selectSetting(title, desc, key, value, choices, target = 'mant') {
            const options = choices.map(([v, label]) => `<option value="${escapeAttr(v)}" ${String(value) === String(v) ? 'selected' : ''}>${escapeHtml(label)}</option>`).join('');
            return rowShell(title, desc, `<select class="settings-control settings-select" data-control="select" data-target="${target}" data-key="${escapeAttr(key)}">${options}</select>`);
        }
        function chipsSetting(title, desc, key, value, choices, mode = 'priority', target = 'mant') {
            const arr = Array.isArray(value) ? value.map(v => String(v)) : String(value || '').split(',').map(v => v.trim()).filter(Boolean);
            const chips = choices.map(([v, label]) => `<button type="button" class="settings-chip ${arr.includes(String(v)) ? 'is-active' : ''}" data-value="${escapeAttr(v)}">${escapeHtml(label)}</button>`).join('');
            return rowShell(title, desc, `<div class="settings-chip-row" data-control="chips" data-target="${target}" data-key="${escapeAttr(key)}" data-mode="${escapeAttr(mode)}">${chips}</div>`);
        }
        function statLabel(value) {
            const found = SETTINGS_STATS.find(([v]) => String(v) === String(value));
            return found ? found[1] : String(value || '');
        }
        function normalizeStatPriority(value) {
            const input = Array.isArray(value) ? value.map(String) : String(value || '').split(',').map(v => v.trim()).filter(Boolean);
            const valid = new Set(DEFAULT_STAT_PRIORITY);
            const ordered = [];
            input.forEach(v => { if (valid.has(v) && !ordered.includes(v)) ordered.push(v); });
            DEFAULT_STAT_PRIORITY.forEach(v => { if (!ordered.includes(v)) ordered.push(v); });
            return ordered;
        }
        function prioritySetting(title, desc, key, value, target = 'preset') {
            const order = normalizeStatPriority(value);
            const chips = order.map((v, idx) => `<span class="priority-preview-chip"><b>${idx + 1}</b>${escapeHtml(statLabel(v))}</span>`).join('');
            const html = `<button type="button" class="settings-priority-open settings-control" data-control="priority-open" data-target="${target}" data-key="${escapeAttr(key)}" data-title="${escapeAttr(title.toUpperCase())}">${chips}<span class="settings-priority-edit">Edit</span></button>`;
            return rowShell(title, desc, html);
        }
        async function savePriorityOrder() {
            if (!activePriorityModal) return;
            const current = getCurrentPreset();
            if (!current) return;
            const store = activePriorityModal.target === 'preset' ? current : mantCfg(current);
            store[activePriorityModal.key] = [...activePriorityModal.order];
            await saveSettingsPreset(current);
        }
        function renderPriorityModalList() {
            const list = document.getElementById('priority-settings-list');
            if (!list || !activePriorityModal) return;
            list.innerHTML = activePriorityModal.order.map((value, index) => `
                <div class="priority-stat-row" draggable="true" data-index="${index}">
                    <span class="priority-stat-rank">${index + 1}</span>
                    <span class="priority-stat-name">${escapeHtml(statLabel(value))}</span>
                    <span class="priority-stat-handle">☰</span>
                </div>
            `).join('');
            let draggedIndex = null;
            list.querySelectorAll('.priority-stat-row').forEach(row => {
                row.addEventListener('dragstart', event => {
                    draggedIndex = Number(row.dataset.index || 0);
                    row.classList.add('is-dragging');
                    event.dataTransfer.effectAllowed = 'move';
                    event.dataTransfer.setData('text/plain', String(draggedIndex));
                });
                row.addEventListener('dragend', () => row.classList.remove('is-dragging'));
                row.addEventListener('dragover', event => {
                    event.preventDefault();
                    row.classList.add('is-drop-target');
                });
                row.addEventListener('dragleave', () => row.classList.remove('is-drop-target'));
                row.addEventListener('drop', async event => {
                    event.preventDefault();
                    row.classList.remove('is-drop-target');
                    const from = draggedIndex ?? Number(event.dataTransfer.getData('text/plain') || -1);
                    const to = Number(row.dataset.index || 0);
                    if (from < 0 || from === to) return;
                    const order = [...activePriorityModal.order];
                    const [moved] = order.splice(from, 1);
                    order.splice(to, 0, moved);
                    activePriorityModal.order = order;
                    renderPriorityModalList();
                    await savePriorityOrder();
                    renderTrainingSettings();
                });
            });
        }
        function openPriorityModal({ title, key, target }) {
            const current = currentPresetForSettings();
            if (!current) return;
            const store = target === 'preset' ? current : mantCfg(current);
            activePriorityModal = { title, key, target, order: normalizeStatPriority(store[key]) };
            const titleNode = document.getElementById('priority-settings-title');
            if (titleNode) titleNode.textContent = title;
            renderPriorityModalList();
            const modal = document.getElementById('priority-settings-modal');
            if (modal) modal.style.display = 'flex';
        }
        async function resetPriorityModal() {
            if (!activePriorityModal) return;
            activePriorityModal.order = [...DEFAULT_STAT_PRIORITY];
            renderPriorityModalList();
            await savePriorityOrder();
            renderTrainingSettings();
        }
        async function selectAllPriorityModal() {
            if (!activePriorityModal) return;
            activePriorityModal.order = normalizeStatPriority(activePriorityModal.order);
            renderPriorityModalList();
            await savePriorityOrder();
            renderTrainingSettings();
        }
        function strategyByDistanceRows(current) {
            const c = mantCfg(current);
            const map = c.race_strategy_by_distance || {};
            return SETTINGS_DISTANCE_VALUES.map(([key, label]) => selectSetting(`${label} Strategy`, `Running style to use for ${label.toLowerCase()} races when per-distance strategy is enabled.`, `race_strategy_by_distance.${key}`, map[key] || '0', SETTINGS_STYLE_VALUES, 'mant_nested')).join('');
        }
        // v2.1: curated stamina-relevant marquee races for per-race style overrides.
        // Names are the EXACT race_planner_core.json names (matched case-insensitively
        // on the backend) so there is no name-mismatch footgun -- the backend matches
        // every program_id variant via the stable name.
        const PER_RACE_STYLE_RACES = [
            ['Kikuka Sho', '3000m · G1'],
            ['Tenno Sho (Spring)', '3200m · G1'],
            ['Tenno Sho (Autumn)', '2000m · G1'],
            ['Arima Kinen', '2500m · G1'],
            ['Niigata Junior Stakes', '1600m · G3'],
        ];
        function perRaceStyleRows(current) {
            const c = mantCfg(current);
            const list = Array.isArray(c.per_race_style_overrides) ? c.per_race_style_overrides : [];
            const byName = {};
            list.forEach(r => { if (r && r.match) byName[String(r.match).toLowerCase()] = r; });
            // Override style must be concrete (1-4); "" = no override for that race.
            const styleOpts = [['', 'No override'], ['1', 'Front Runner'], ['2', 'Pace Chaser'], ['3', 'Late Surger'], ['4', 'End Closer']];
            const rows = PER_RACE_STYLE_RACES.map(([race, meta]) => {
                const cur = byName[race.toLowerCase()] || {};
                const curStyle = String(cur.style || '');
                const curStamina = (cur.stamina_below === undefined || cur.stamina_below === null) ? '' : cur.stamina_below;
                const opts = styleOpts.map(([v, l]) => `<option value="${v}" ${v === curStyle ? 'selected' : ''}>${escapeHtml(l)}</option>`).join('');
                return `<div class="settings-row per-race-style-row" data-race="${escapeAttr(race)}">
                    <div><strong>${escapeHtml(race)}</strong><span>${escapeHtml(meta)}</span></div>
                    <div class="per-race-style-controls">
                        <label class="settings-muted">Stamina &lt; <input type="number" class="settings-control settings-text-input" data-control="per-race-style" data-field="stamina" min="0" max="2000" step="10" value="${escapeAttr(curStamina)}" placeholder="any"></label>
                        <select class="settings-control" data-control="per-race-style" data-field="style">${opts}</select>
                    </div>
                </div>`;
            }).join('');
            return rowShell('Per-Race Style Overrides', 'Override the running style for specific races, optionally only when Stamina is below a threshold (blank = always). Applies even in Manual mode and reverts to your main style on the next race. Requires a concrete Original Strategy (not Auto).', `<div class="per-race-style-list">${rows}</div>`);
        }
        function statTargetGrid(current) {
            const c = mantCfg(current);
            const targets = c.stat_targets_by_distance || {};
            const defaults = {
                sprint: [1200, 450, 1000, 500, 1000],
                mile: [1200, 600, 1000, 500, 1000],
                medium: [1200, 800, 1000, 600, 900],
                long: [1200, 1000, 900, 700, 900],
            };
            const heads = ['Distance','Speed','Stamina','Power','Guts','Wit'];
            const header = `<div class="settings-target-row settings-muted">${heads.map(h => `<strong>${escapeHtml(h)}</strong>`).join('')}</div>`;
            const rows = SETTINGS_DISTANCE_VALUES.map(([distance, label]) => {
                const vals = Array.isArray(targets[distance]) ? targets[distance] : defaults[distance];
                const inputs = vals.map((v, idx) => `<input type="number" class="settings-control settings-text-input" data-control="target-grid" data-distance="${distance}" data-stat-index="${idx}" min="1" max="1800" step="1" value="${escapeAttr(v)}">`).join('');
                return `<div class="settings-target-row"><strong>${escapeHtml(label)}</strong>${inputs}</div>`;
            }).join('');
            return rowShell('Stat Targets by Distance', 'Native stat target table used by the training scorer.', `<div class="settings-target-grid">${header}${rows}</div>`);
        }
        function renderTrainingSettings() {
            const current = currentPresetForSettings();
            if (!current) return;
            const c = mantCfg(current);
            const body = document.getElementById('training-settings-body');
            if (!body) return;
            body.innerHTML = `
                <section class="settings-card"><h3>Priorities</h3>
                    ${chipsSetting('Blacklist', 'Stats excluded from training unless the skill-hint override is enabled.', 'training_blacklist', c.training_blacklist || [], SETTINGS_STATS, 'checkbox', 'mant')}
                    ${prioritySetting('Prioritization', 'Main stat order used by the native training scorer.', 'training_stat_priority', current.training_stat_priority || DEFAULT_STAT_PRIORITY, 'preset')}
                    ${prioritySetting('Event Choice Prioritization', 'Stat order used when scoring event choices.', 'event_choice_stat_priority', current.event_choice_stat_priority || current.training_stat_priority || DEFAULT_STAT_PRIORITY, 'preset')}
                    ${prioritySetting('Summer Training Prioritization', 'Stat order used during Summer Training.', 'summer_stat_priority', current.summer_stat_priority || current.training_stat_priority || DEFAULT_STAT_PRIORITY, 'preset')}
                </section>
                <section class="settings-card"><h3>Behavior</h3>
                    ${selectSetting('Decision Engine', 'Trackblazer Engine (default) is the modern training/race decision core. Classic is the original legacy engine.', 'decision_mode', engineMode(getSetting(current,'mant','decision_mode','trackblazer')), [['trackblazer','Trackblazer Engine'], ['legacy','Classic']])}
                    ${selectSetting('Stat Focus', 'Balanced spreads training evenly toward targets (default). Capped concentrates priority stats toward the cap (steeper priority, flatter completion curve, trains past the buffer).', 'stat_focus_mode', String(getSetting(current,'mant','stat_focus_mode','balanced')), [['balanced','Balanced (even spread)'], ['capped','Capped (max priority stats)']])}
                    ${sliderSetting('Set Maximum Failure Chance', 'Trainings above this failure rate are rejected unless Riskier Training allows them.', 'maximum_failure_chance', getSetting(current,'mant','maximum_failure_chance',20), 5, 95, 5)}
                    ${toggleSetting('Disable Training on Maxed Stats', 'Skip stats that have reached their active target/cap buffer.', 'disable_training_on_maxed_stats', getSetting(current,'mant','disable_training_on_maxed_stats',true))}
                    ${toggleSetting('Enable Riskier Training', 'Allow high-gain trainings to pass a separate higher failure limit.', 'enable_risky_training', getSetting(current,'mant','enable_risky_training',false))}
                    ${sliderSetting('Minimum Main Stat Gain Threshold', 'Minimum main-stat gain required for Riskier Training.', 'risky_training_min_stat_gain', getSetting(current,'mant','risky_training_min_stat_gain',20), 20, 100, 5)}
                    ${sliderSetting('Risky Training Maximum Failure Chance', 'Maximum failure rate accepted for Riskier Training.', 'risky_training_max_failure_chance', getSetting(current,'mant','risky_training_max_failure_chance',30), 5, 95, 5)}
                    ${toggleSetting('Prioritize Skill Hints', 'Boost trainings with skill hints and allow hint turns through the blacklist.', 'enable_prioritize_skill_hints', getSetting(current,'mant','enable_prioritize_skill_hints',false))}
                    ${toggleSetting('Must Rest before Summer', 'Use the pre-summer conservation rule before Summer Training.', 'must_rest_before_summer', getSetting(current,'mant','must_rest_before_summer',true))}
                    ${toggleSetting('Train Wit During Finale', 'Use Wit instead of pure recovery in Finale when possible.', 'train_wit_during_finale', getSetting(current,'mant','train_wit_during_finale',false))}
                </section>
                <section class="settings-card"><h3>Scoring</h3>
                    ${toggleSetting('Weight Score by Training Level', 'Boost top-priority stats when native training level fields are present.', 'enable_training_level_weighting', getSetting(current,'mant','enable_training_level_weighting',true))}
                    ${toggleSetting('Rainbow Training Bonus', 'Apply the friendship/rainbow multiplier in training scoring.', 'enable_rainbow_training_bonus', getSetting(current,'mant','enable_rainbow_training_bonus',true))}
                    ${toggleSetting('Attenuate Rainbow on Capped Stats', 'Scale the rainbow bonus down as the trained stat fills toward its cap, so the bot stops chasing rainbows on already-finished stats. Off = flat 2.0x as before.', 'rainbow_attenuate_by_usefulness', getSetting(current,'mant','rainbow_attenuate_by_usefulness',true))}
                    ${sliderSetting('Rainbow Attenuation Floor', 'Minimum fraction of the rainbow bonus kept even on a fully-capped stat, so a real friendship turn is still valued.', 'rainbow_attenuate_floor', getSetting(current,'mant','rainbow_attenuate_floor',0.25), 0, 1, 0.05)}
                    ${toggleSetting('Near-Max Friendship Boost', 'Reward near-rainbow bond stacks without outranking true rainbow turns.', 'enable_near_rainbow_bonus', getSetting(current,'mant','enable_near_rainbow_bonus',true))}
                    ${sliderSetting('Low-Bond Training Value', 'How much an un-bonded (orange, <60) support partner is worth to train near. Higher = the bot bond-rushes harder in Junior so off-priority cards (e.g. a Stamina SSR like Super Creek) actually reach rainbow. 0 = legacy (ignores low bonds).', 'bond_value_orange', getSetting(current,'mant','bond_value_orange',0.4), 0, 2, 0.1)}
                    ${sliderSetting('Bond-to-Rainbow Push', 'Extra weight for finishing a green (60-79) bond up to rainbow (80). Higher = the bot pushes partial bonds to max instead of abandoning them for raw stats.', 'bond_finish_push_cap', getSetting(current,'mant','bond_finish_push_cap',1.0), 0, 2, 0.1)}
                    ${sliderSetting('Bond Priority Weight', 'How heavily bond/friendship counts vs raw stat gain in the training score (stat weight is ~0.6). Higher favors bond-building.', 'bond_weight', getSetting(current,'mant','bond_weight',0.15), 0, 1, 0.05)}
                </section>
                <section class="settings-card"><h3>Distance</h3>
                    ${selectSetting('Preferred Distance', 'Used to resolve stat targets when Auto is not desired.', 'preferred_distance', getSetting(current,'mant','preferred_distance','auto'), [['auto','Auto'], ...SETTINGS_DISTANCE_VALUES])}
                    ${toggleSetting('Disable Stat Targets', 'Treat every stat as live instead of tapering at per-distance targets.', 'disable_stat_targets', getSetting(current,'mant','disable_stat_targets',false))}
                    ${statTargetGrid(current)}
                    ${sliderSetting('End of Classic Year Milestone', 'Percent of final targets to aim for by the end of Classic Year.', 'classic_year_milestone_pct', getSetting(current,'mant','classic_year_milestone_pct', getSetting(current,'mant','junior_milestone_pct',33)), 0, 100, 1)}
                    ${sliderSetting('End of Senior Year Milestone', 'Percent of final targets to aim for by the end of Senior Year.', 'senior_year_milestone_pct', getSetting(current,'mant','senior_year_milestone_pct', getSetting(current,'mant','classic_milestone_pct',66)), 0, 100, 1)}
                </section>`;
            bindSettingsControls(body, current, renderTrainingSettings);
        }
        function renderRacingSettings() {
            const current = currentPresetForSettings();
            if (!current) return;
            const c = mantCfg(current);
            const body = document.getElementById('racing-settings-body');
            if (!body) return;
            body.innerHTML = `
                <section class="settings-card"><h3>Race Behavior</h3>
                    ${toggleSetting('Enable Farming Fans', 'Run extra races on matching turns when no smart-solver train lock blocks them.', 'enable_farming_fans', getSetting(current,'mant','enable_farming_fans',false))}
                    ${sliderSetting('Days to Run Extra Races', 'Extra-race interval used by fan farming.', 'days_to_run_extra_races', getSetting(current,'mant','days_to_run_extra_races',5), 1, 15, 1)}
                    ${toggleSetting('Ignore Consecutive Race Warning', 'Disable the Trackblazer race-chain safety break.', 'ignore_consecutive_race_warning', getSetting(current,'mant','ignore_consecutive_race_warning',false))}
                    ${toggleSetting('Ignore Low Energy Racing Block', 'Do not block voluntary racing due to critical HP during a race streak.', 'ignore_low_energy_racing_block', getSetting(current,'mant','ignore_low_energy_racing_block',false))}
                    ${toggleSetting('Complete Career on Failure', 'Continue after failed mandatory races once retry policy is exhausted.', 'complete_career_on_failure', getSetting(current,'mant','complete_career_on_failure',true))}
                    ${toggleSetting('Stop on Mandatory Races', 'Stop the runner before entering mandatory races.', 'stop_on_mandatory_races', getSetting(current,'mant','stop_on_mandatory_races',false))}
                    ${toggleSetting('Force Racing', 'Choose an available race whenever possible.', 'force_racing', getSetting(current,'mant','force_racing',false))}
                </section>
                <section class="settings-card"><h3>Outcome Risk</h3>
                    ${toggleSetting('Enable Outcome-Risk Avoidance', 'Penalize races the bot has historically lost (learned from past careers) so the Smart Race Solver avoids them. Turn OFF to pick races purely by value (more reference-like) — this does not affect which races are winnable, only scheduling.', 'enable_outcome_risk', getSetting(current,'mant','enable_outcome_risk',true))}
                    ${sliderSetting('Outcome-Risk Weight', 'How strongly past-loss history deprioritizes a race in the schedule (0 = ignore, higher = avoid risky races more). Only applies when the toggle above is on.', 'outcome_risk_weight', getSetting(current,'mant','outcome_risk_weight',1), 0, 5, 0.5)}
                </section>
                <section class="settings-card"><h3>Strategy</h3>
                    ${toggleSetting('Per-Distance Strategy', 'Use separate running styles by race distance.', 'enable_per_distance_strategy', getSetting(current,'mant','enable_per_distance_strategy',false))}
                    ${selectSetting('Junior Year Strategy', 'Running style used during Junior Year races.', 'junior_running_style', getSetting(current,'mant','junior_running_style','0'), SETTINGS_STYLE_VALUES)}
                    ${selectSetting('Original Strategy', 'Default running style for Year 2+ and fallback races.', 'running_style', current.running_style || '1', SETTINGS_STYLE_VALUES.filter(([v]) => v !== '0'), 'preset')}
                    ${strategyByDistanceRows(current)}
                    ${perRaceStyleRows(current)}
                </section>`;
            bindSettingsControls(body, current, renderRacingSettings);
        }
        function renderScenarioSettings() {
            const current = currentPresetForSettings();
            if (!current) return;
            const c = mantCfg(current);
            const excluded = c.exclude_shop_items || [];
            const shopList = `<div class="settings-shop-list">${SETTINGS_SHOP_ITEMS.map(name => `<label class="settings-muted"><input type="checkbox" class="settings-control" data-control="shop-exclude" data-item="${escapeAttr(name)}" ${excluded.includes(name) ? 'checked' : ''}> ${escapeHtml(name)}</label>`).join('')}</div>`;
            const body = document.getElementById('scenario-settings-body');
            if (!body) return;
            body.innerHTML = `
                <section class="settings-card"><h3>Racing</h3>
                    ${sliderSetting('Consecutive Races Limit', 'Maximum race streak before Trackblazer safety logic intervenes.', 'race_chain_target', getSetting(current,'mant','race_chain_target',3), 3, 30, 1)}
                    ${chipsSetting('Preferred Track Distances', 'Matching races are prioritized during Trackblazer race sorting.', 'preferred_distances', c.preferred_distances || current.preferred_distances || [], SETTINGS_DISTANCE_VALUES, 'checkbox', 'mant')}
                    ${chipsSetting('Preferred Track Surfaces', 'Matching race surfaces are prioritized during Trackblazer race sorting.', 'preferred_surfaces', c.preferred_surfaces || current.preferred_surfaces || [], SETTINGS_SURFACE_VALUES, 'checkbox', 'mant')}
                </section>
                <section class="settings-card"><h3>Energy & Resources</h3>
                    ${sliderSetting('Energy Threshold to use Energy Items', 'HP threshold below which recovery items may be used.', 'energy_recovery_threshold', getSetting(current,'mant','energy_recovery_threshold',40), 0, 100, 1)}
                    ${sliderSetting('Force-Train Energy Floor', 'During Summer/Finale, fall back to recovery at or below this HP.', 'force_train_energy_floor', getSetting(current,'mant','force_train_energy_floor',20), 0, 50, 1)}
                    ${sliderSetting('Skip Items During Bad Mood Below Stat Gain', 'Conserve Charm/Megaphone/Whistle on low-mood low-gain turns.', 'trackblazer_skip_bad_mood_items_below_gain', getSetting(current,'mant','trackblazer_skip_bad_mood_items_below_gain',15), 0, 50, 1)}
                    ${toggleSetting('Skip Energy Items on Year-End Races', 'Do not spend energy/recovery items chaining into a year-end race (Hopeful Stakes, Arima Kinen, finale) - the year/career ends right after, so the energy can never be used. (The bot already will not REST over these races regardless of this setting.)', 'skip_energy_items_year_end', getSetting(current,'mant','skip_energy_items_year_end',false))}
                </section>
                <section class="settings-card"><h3>Training</h3>
                    ${sliderSetting('Skip Risky Charm Training Below Stat Gain', 'Minimum main gain before Charm protects a risky training.', 'charm_min_main_gain', getSetting(current,'mant','charm_min_main_gain',20), 20, 100, 1)}
                    ${toggleSetting('Enable Irregular Training', 'Allow high-value training to hijack planned voluntary races.', 'enable_irregular_training', getSetting(current,'mant','enable_irregular_training',true))}
                    ${sliderSetting('Minimum Main Stat Gain for Irregular Training', 'Required main-stat gain to skip racing for irregular training.', 'irregular_training_min_main_gain', getSetting(current,'mant','irregular_training_min_main_gain',30), 20, 100, 1)}
                    ${toggleSetting('Reset Whistle Forces Training', 'Allow Reset Whistle rescue on unsafe-failure dead turns.', 'whistle_forces_training', getSetting(current,'mant','whistle_forces_training',true))}
                </section>
                <section class="settings-card"><h3>Shop & Items</h3>
                    ${sliderSetting('Shop Check Frequency', '1 = every shop opportunity, 2 = every other eligible opportunity, etc.', 'trackblazer_shop_check_frequency', getSetting(current,'mant','trackblazer_shop_check_frequency',1), 1, 4, 1)}
                    ${chipsSetting('Race Grades to check Shop Afterwards', 'Eligible race grades for shop-check frequency logic.', 'trackblazer_shop_check_grades', c.trackblazer_shop_check_grades || ['G1','G2','G3'], SETTINGS_GRADE_VALUES, 'checkbox', 'mant')}
                    ${rowShell('Items to Exclude from Shop', 'Checked items will never be purchased by the shop logic.', shopList)}
                </section>
                <section class="settings-card"><h3>Shop Purchase Logic</h3>
                    ${sliderSetting('Coin Reserve Override', 'Coins always kept unspent in the shop. 0 = automatic (a finale-aware reserve curve). Set a value to force a flat reserve every turn.', 'mant_coin_reserve', getSetting(current,'mant','mant_coin_reserve',0), 0, 300, 5)}
                    ${sliderSetting('BBQ Buy Threshold (unmaxxed cards)', 'Buy Grilled Carrots (BBQ) more aggressively when more than this many support cards are still below max friendship. Lower = start buying BBQ sooner.', 'bbq_unmaxxed_cards', getSetting(current,'mant','bbq_unmaxxed_cards',3), 0, 6, 1)}
                    ${toggleSetting('Fast Learner Shop Boost', "Prioritize Scholar's Hat early so the Fast Learner skill stacks sooner. Off by default (the race/economy kit comes first).", 'enable_fast_learner_shop_boost', getSetting(current,'mant','enable_fast_learner_shop_boost',false))}
                    ${toggleSetting('Preemptive Cure Reserve', 'Keep one Cure-All / Rich Hand Cream on hand before any condition appears. Off by default — cures are only bought when a bad condition is actually active.', 'preemptive_cure_reserve', getSetting(current,'mant','preemptive_cure_reserve',false))}
                </section>
                <section class="settings-card"><h3>Item Conservation</h3>
                    ${toggleSetting('Save Items for Late Game', 'When OFF (default), after turn 64 the bot dumps every remaining item (megaphones, anklets, charms, cupcakes, Vita/Kale) on any slightly-useful training — summer is over and finale races pay zero coins, so an unspent item is pure waste. It also stops hoarding coins for finals (keeps only ~60 for the turn-71 Master Cleat Hammer). Turn ON to keep the conservative reserve / finale priority-stat behavior instead.', 'save_items_lategame', getSetting(current,'mant','save_items_lategame',false))}
                    ${sliderSetting('Energy Item Emergency Reserve', 'Lowest-tier Vita copies reserved for emergency race recovery.', 'trackblazer_energy_item_reserve', getSetting(current,'mant','trackblazer_energy_item_reserve',1), 0, 3, 1)}
                    ${sliderSetting('Cupcake Reserve for Kale Juice Synergy', 'Cupcakes preserved for Royal Kale mood repair.', 'trackblazer_cupcake_reserve', getSetting(current,'mant','trackblazer_cupcake_reserve',1), 0, 3, 1)}
                    ${sliderSetting('Master Cleat Hammer Finale Reserve', 'Master Hammers saved for Finale race windows.', 'trackblazer_master_hammer_finale_reserve', getSetting(current,'mant','trackblazer_master_hammer_finale_reserve',3), 0, 3, 1)}
                    ${sliderSetting('Artisan Hammer Min Stock for G3', 'Minimum Artisan stock before spending one on G3 races.', 'trackblazer_artisan_hammer_min_stock_for_g3', getSetting(current,'mant','trackblazer_artisan_hammer_min_stock_for_g3',0), 0, 3, 1)}
                    ${sliderSetting('Artisan Hammer Min Stock for G2', 'Minimum Artisan stock before spending one on G2 races.', 'trackblazer_artisan_hammer_min_stock_for_g2', getSetting(current,'mant','trackblazer_artisan_hammer_min_stock_for_g2',0), 0, 3, 1)}
                    ${sliderSetting('Glow Stick Final-Day Reserve', 'Glow Sticks saved for the final Trackblazer race.', 'trackblazer_glow_stick_final_reserve', getSetting(current,'mant','trackblazer_glow_stick_final_reserve',1), 0, 3, 1)}
                    ${sliderSetting('Glow Stick Minimum Fans', 'Minimum projected fan gain before spending Glow Sticks.', 'trackblazer_glow_stick_min_fans', getSetting(current,'mant','trackblazer_glow_stick_min_fans',20000), 0, 30000, 1000)}
                    ${sliderSetting('Late Whistle Lackluster Threshold', 'Past turn 64, use a Reset Whistle when the best training\'s total stat gain is below this.', 'late_whistle_lackluster_threshold', getSetting(current,'mant','late_whistle_lackluster_threshold',30), 0, 80, 1)}
                    <div class="settings-row"><div><strong>Reset Trackblazer to Defaults</strong><span>Clears Trackblazer-specific override values from this preset.</span></div><div><button id="settings-reset-trackblazer" class="btn btn-sm settings-reset-btn" type="button">RESET TRACKBLAZER TO DEFAULTS</button></div></div>
                </section>`;
            bindSettingsControls(body, current, renderScenarioSettings);
            document.getElementById('settings-reset-trackblazer')?.addEventListener('click', async () => {
                if (!confirm('Reset Trackblazer override settings on this preset?')) return;
                current.mant_config = {};
                await saveSettingsPreset(current);
                renderScenarioSettings();
            });
        }
        function bindSettingsControls(root, current, rerender) {
            root.querySelectorAll('.settings-control').forEach(control => {
                const type = control.dataset.control;
                if (type === 'number') {
                    control.addEventListener('input', () => {
                        root.querySelectorAll(`.settings-control[data-key="${control.dataset.key}"]`).forEach(peer => { if (peer !== control && peer.dataset.control === 'number') peer.value = control.value; });
                    });
                    control.addEventListener('change', async () => {
                        setSettingValue(current, control.dataset.target, control.dataset.key, Number(control.value));
                        await saveSettingsPreset(current);
                    });
                } else if (type === 'toggle') {
                    control.addEventListener('change', async () => {
                        setSettingValue(current, control.dataset.target, control.dataset.key, Boolean(control.checked));
                        await saveSettingsPreset(current);
                    });
                } else if (type === 'select') {
                    control.addEventListener('change', async () => {
                        let value = control.value;
                        if (/running_style$/.test(control.dataset.key) || control.dataset.key === 'running_style') value = Number(value);
                        setSettingValue(current, control.dataset.target, control.dataset.key, value);
                        await saveSettingsPreset(current);
                    });
                } else if (type === 'priority-open') {
                    control.addEventListener('click', () => openPriorityModal({
                        title: control.dataset.title || 'PRIORITIZATION',
                        key: control.dataset.key,
                        target: control.dataset.target || 'preset'
                    }));
                } else if (type === 'shop-exclude') {
                    control.addEventListener('change', async () => {
                        const c = mantCfg(current);
                        const item = control.dataset.item;
                        const arr = Array.isArray(c.exclude_shop_items) ? [...c.exclude_shop_items] : [];
                        c.exclude_shop_items = control.checked ? Array.from(new Set([...arr, item])) : arr.filter(v => v !== item);
                        // refreshUI:false -> don't rebuild the panel (keeps the
                        // blacklist list from scrolling back to the top on toggle).
                        await saveSettingsPreset(current, { refreshUI: false });
                    });
                } else if (type === 'per-race-style') {
                    control.addEventListener('change', async () => {
                        const c = mantCfg(current);
                        // Rebuild the whole override list from the current rows.
                        const list = [];
                        root.querySelectorAll('.per-race-style-row').forEach(row => {
                            const race = row.dataset.race;
                            const style = parseInt(row.querySelector('select[data-field="style"]')?.value || '', 10);
                            if (!(style >= 1 && style <= 4)) return; // no override for this race
                            const entry = { match: race, style };
                            const thr = parseInt(row.querySelector('input[data-field="stamina"]')?.value || '', 10);
                            if (Number.isFinite(thr) && thr > 0) entry.stamina_below = thr;
                            list.push(entry);
                        });
                        c.per_race_style_overrides = list;
                        // refreshUI:false -> keep scroll position (same as shop list).
                        await saveSettingsPreset(current, { refreshUI: false });
                    });
                } else if (type === 'target-grid') {
                    control.addEventListener('change', async () => {
                        const c = mantCfg(current);
                        c.stat_targets_by_distance = c.stat_targets_by_distance || {};
                        const distance = control.dataset.distance;
                        const idx = Number(control.dataset.statIndex || 0);
                        const defaults = { sprint:[1200,450,1000,500,1000], mile:[1200,600,1000,500,1000], medium:[1200,800,1000,600,900], long:[1200,1000,900,700,900] };
                        const row = Array.isArray(c.stat_targets_by_distance[distance]) ? [...c.stat_targets_by_distance[distance]] : [...defaults[distance]];
                        row[idx] = Number(control.value || 0);
                        c.stat_targets_by_distance[distance] = row;
                        // refreshUI:false -> keep scroll position (same as the shop
                        // list); a number input editing its own value needs no rebuild.
                        await saveSettingsPreset(current, { refreshUI: false });
                    });
                }
            });
            root.querySelectorAll('.settings-chip-row').forEach(row => {
                row.querySelectorAll('.settings-chip').forEach(chip => {
                    chip.addEventListener('click', async () => {
                        const target = row.dataset.target;
                        const key = row.dataset.key;
                        const mode = row.dataset.mode;
                        const store = target === 'preset' ? current : mantCfg(current);
                        const value = chip.dataset.value;
                        let arr = Array.isArray(store[key]) ? [...store[key].map(String)] : String(store[key] || '').split(',').map(v => v.trim()).filter(Boolean);
                        if (mode === 'checkbox') {
                            arr = arr.includes(value) ? arr.filter(v => v !== value) : [...arr, value];
                        } else {
                            arr = arr.filter(v => v !== value);
                            arr.push(value);
                        }
                        store[key] = arr;
                        await saveSettingsPreset(current);
                        if (typeof rerender === 'function') rerender();
                    });
                });
            });
        }

        function solverSettings(current) {
            current.trackblazer_solver_settings = current.trackblazer_solver_settings || {};
            const s = current.trackblazer_solver_settings;
            if (s.include_op === undefined) s.include_op = false;
            if (s.allow_summer_racing === undefined) s.allow_summer_racing = false;
            if (s.fan_bonus === undefined) s.fan_bonus = 0;
            if (s.max_races_in_row === undefined) s.max_races_in_row = 2;
            if (s.disable_schedule_replan_on_race_loss === undefined) s.disable_schedule_replan_on_race_loss = false;
            if (s.replan_on_events_only === undefined) s.replan_on_events_only = true;
            if (s.enable_live_smart_replan === undefined) s.enable_live_smart_replan = true;
            if (!s.min_aptitude_floor) s.min_aptitude_floor = 'C';
            if (!s.optimization_mode) s.optimization_mode = 'fans_epithets';
            if (!s.distance_preference_mode) s.distance_preference_mode = 'balanced';
            return s;
        }
        function solverWeights(current) {
            current.trackblazer_weights = current.trackblazer_weights || {};
            const out = current.trackblazer_weights;
            Object.entries(SOLVER_DEFAULT_WEIGHTS).forEach(([key, value]) => {
                if (out[key] === undefined || out[key] === null || out[key] === '') out[key] = value;
            });
            return out;
        }
        function aptitudeRank(letter) {
            const map = { S: 8, A: 7, B: 6, C: 5, D: 4, E: 3, F: 2, G: 1 };
            return map[String(letter || 'C').toUpperCase()] || 5;
        }
        function normalizeSolverAptitude(value, fallback = 'G') {
            const grade = String(value || fallback).toUpperCase().replace(/\+$/, '');
            return SOLVER_APTITUDE_ORDER.includes(grade) ? grade : fallback;
        }
        async function loadSolverDefaults() {
            if (solverDefaultsLoaded) return SOLVER_DEFAULT_WEIGHTS;
            try {
                const data = await apiJson('/api/trackblazer/solver/defaults?t=' + Date.now());
                if (data?.defaults && typeof data.defaults === 'object') {
                    SOLVER_DEFAULT_WEIGHTS = { ...SOLVER_DEFAULT_WEIGHTS, ...data.defaults };
                }
            } catch (e) {
                console.warn('Using bundled solver defaults', e);
            }
            solverDefaultsLoaded = true;
            return SOLVER_DEFAULT_WEIGHTS;
        }
        function solverTraineeKey() {
            const key = selectedTraineeKey ? selectedTraineeKey() : '';
            return key && key !== '|' ? key : '__default__';
        }
        function aptitudeIndex(letter) {
            const idx = SOLVER_APTITUDE_ORDER.indexOf(normalizeSolverAptitude(letter, 'G'));
            return idx < 0 ? SOLVER_APTITUDE_ORDER.length - 1 : idx;
        }
        function aptitudeFromIndex(index) {
            const clamped = Math.max(0, Math.min(SOLVER_APTITUDE_ORDER.length - 1, Number(index) || 0));
            return SOLVER_APTITUDE_ORDER[clamped];
        }
        function aptitudeNameToKey(name) {
            const text = String(name || '').toLowerCase();
            if (text.includes('sprint')) return 'Sprint';
            if (text.includes('mile')) return 'Mile';
            if (text.includes('medium') || text.includes('middle')) return 'Medium';
            if (text.includes('long')) return 'Long';
            if (text.includes('turf')) return 'Turf';
            if (text.includes('dirt')) return 'Dirt';
            if (text.includes('front')) return 'Front';
            if (text.includes('pace')) return 'Pace';
            if (text.includes('late')) return 'Late';
            if (text.includes('end')) return 'End';
            return '';
        }
        function estimateParentSparkBonuses() {
            const starsByKey = {};
            const parents = [...(selection.veterans || []), ...((selection.guestParents || []).filter(Boolean))];
            parents.forEach(parent => {
                const tree = parent?.tree || {};
                ['self', 'p1', 'p2', 'gp1', 'gp2', 'gp3', 'gp4'].forEach(nodeKey => {
                    const node = tree[nodeKey];
                    (node?.factors || []).forEach(factor => {
                        const key = aptitudeNameToKey(factor.name);
                        if (!key) return;
                        starsByKey[key] = (starsByKey[key] || 0) + Math.max(0, Number(factor.stars || 0));
                    });
                });
            });
            const bonuses = {};
            Object.entries(starsByKey).forEach(([key, stars]) => {
                // Spark outcomes are probabilistic; use a conservative preview: any
                // aptitude spark can matter, and roughly every three stars adds a grade.
                bonuses[key] = Math.max(1, Math.min(3, Math.ceil(Number(stars || 0) / 3)));
            });
            return bonuses;
        }
        function applySparkBonuses(starting, bonuses) {
            const out = { ...starting };
            Object.entries(bonuses || {}).forEach(([key, bonus]) => {
                const current = normalizeSolverAptitude(out[key] || 'G', 'G');
                out[key] = aptitudeFromIndex(aptitudeIndex(current) - Math.max(0, Number(bonus || 0)));
            });
            return out;
        }
        function clampNumber(value, min, max, fallback) {
            const n = Number(value);
            if (!Number.isFinite(n)) return fallback;
            return Math.max(min, Math.min(max, n));
        }
        function solverManualAptitudes(current) {
            current.trackblazer_manual_aptitudes_by_trainee = current.trackblazer_manual_aptitudes_by_trainee || {};
            const key = solverTraineeKey();
            if (!current.trackblazer_manual_aptitudes_by_trainee[key]) {
                const legacy = current.trackblazer_manual_aptitudes;
                current.trackblazer_manual_aptitudes_by_trainee[key] = (legacy && typeof legacy === 'object' && !Array.isArray(legacy)) ? { ...legacy } : {};
            }
            return current.trackblazer_manual_aptitudes_by_trainee[key];
        }
        function startingSolverAptitudes(current) {
            const base = inferTrackblazerAptitudes();
            const manual = solverManualAptitudes(current);
            const out = {};
            SOLVER_APTITUDE_KEYS.forEach(([key]) => {
                out[key] = normalizeSolverAptitude(manual[key] || base[key] || (key === 'Dirt' ? 'G' : 'C'));
            });
            ['Front','Pace','Late','End'].forEach(key => {
                if (manual[key] || base[key]) out[key] = normalizeSolverAptitude(manual[key] || base[key]);
            });
            return out;
        }
        function effectiveSolverAptitudes(current) {
            return applySparkBonuses(startingSolverAptitudes(current), estimateParentSparkBonuses());
        }
        function baseSolverAptitudes() {
            const base = inferTrackblazerAptitudes();
            const out = {};
            SOLVER_APTITUDE_KEYS.forEach(([key]) => { out[key] = normalizeSolverAptitude(base[key] || (key === 'Dirt' ? 'G' : 'C')); });
            return out;
        }
        async function saveSolverSetting(current) {
            state.smartSolverConfig = current || state.smartSolverConfig || {};
            await saveSmartSolverConfig();
            markTrackblazerPlanStale();
        }
        function markTrackblazerPlanStale() {
            if (els.v4TrackblazerPlan && state.trackblazerPlan) {
                els.v4TrackblazerPlan.innerHTML = '<div class="v4-warn">Smart Race Solver settings changed. Click Solve Smart to refresh the route.</div>';
            }
            state.trackblazerPlan = null;
            if (els.v4ApplyPlanBtn) els.v4ApplyPlanBtn.disabled = true;
            syncStartButton();
        }
        function solverNumberInput(label, key, value, description = '', step = 1, min = 0, max = 1000) {
            return `<label class="solver-number-field"><span>${escapeHtml(label)}</span><input class="solver-settings-control" data-control="solver-weight" data-key="${escapeAttr(key)}" data-min="${escapeAttr(min)}" data-max="${escapeAttr(max)}" type="number" min="${escapeAttr(min)}" max="${escapeAttr(max)}" step="${escapeAttr(step)}" value="${escapeAttr(value)}"><em>${escapeHtml(description)}</em></label>`;
        }
        function renderSolverAptitudeGrid(current) {
            const base = baseSolverAptitudes();
            const manual = solverManualAptitudes(current);
            const starting = startingSolverAptitudes(current);
            const sparks = estimateParentSparkBonuses();
            const effective = effectiveSolverAptitudes(current);
            return `<div class="solver-aptitude-grid">
                <div class="solver-aptitude-note">Manual Start replaces the trainee preset for solver planning. Estimated Parent Sparks are added on top, and Solver Final is sent to the route solver.</div>
                ${SOLVER_APTITUDE_KEYS.map(([key, label]) => `
                    <div class="solver-aptitude-row" data-aptitude="${escapeAttr(key)}">
                        <div class="solver-aptitude-label"><strong>${escapeHtml(label)}</strong><span>Base ${escapeHtml(base[key] || 'G')} · Manual Start ${escapeHtml(starting[key] || 'G')} · Sparks +${escapeHtml(sparks[key] || 0)} · Solver Final ${escapeHtml(effective[key] || 'G')}</span></div>
                        <div class="solver-grade-row">
                            ${SOLVER_APTITUDE_ORDER.map(grade => `<button type="button" class="solver-grade-btn ${starting[key] === grade ? 'is-active' : ''} ${manual[key] === grade ? 'is-manual' : ''}" data-control="solver-aptitude" data-key="${escapeAttr(key)}" data-grade="${grade}">${grade}</button>`).join('')}
                            <button type="button" class="solver-grade-reset" data-control="solver-aptitude-reset" data-key="${escapeAttr(key)}">Base</button>
                        </div>
                    </div>`).join('')}
            </div>`;
        }
        async function loadTrackblazerEpithets() {
            if (state.trackblazerEpithets && state.trackblazerEpithets.length) return state.trackblazerEpithets;
            try {
                const data = await apiJson('/api/trackblazer/epithets?t=' + Date.now());
                state.trackblazerEpithets = data.epithets || [];
            } catch (e) {
                state.trackblazerEpithets = [];
            }
            return state.trackblazerEpithets;
        }
        function renderEpithetPicker(current, mode) {
            const key = mode === 'forced' ? 'trackblazer_forced_epithets' : 'trackblazer_target_epithets';
            const selected = new Set((current[key] || []).map(String));
            const epithets = (state.trackblazerEpithets || []);
            const title = mode === 'forced' ? 'Forced Epithets' : 'Target Epithets';
            const help = mode === 'forced'
                ? 'Forced epithets are hard constraints: every selected forced epithet must have at least one matching scheduled race under the native matcher.'
                : 'Target epithets bias the route toward races named in their conditions.';
            return `<section class="settings-card solver-epithet-card"><h3>${escapeHtml(title)}</h3>
                <div class="solver-epithet-head"><div><strong>Selected ${selected.size} / ${epithets.length}</strong><span>${escapeHtml(help)}</span></div><button type="button" class="btn btn-sm settings-reset-btn" data-control="solver-epithet-clear" data-mode="${mode}">Clear</button></div>
                <input class="solver-epithet-search" data-control="solver-epithet-search" data-mode="${mode}" type="search" placeholder="Search ${escapeAttr(epithets.length)} epithets...">
                <div class="solver-epithet-grid" data-mode="${mode}">
                    ${epithets.map(ep => {
                        const name = String(ep.name || '');
                        const active = selected.has(name);
                        return `<button type="button" class="solver-epithet-card-btn ${active ? 'is-active' : ''}" data-control="solver-epithet" data-mode="${mode}" data-name="${escapeAttr(name)}" data-search="${escapeAttr((name + ' ' + (ep.condition_text || '') + ' ' + (ep.reward_text || '')).toLowerCase())}">
                            <strong>${escapeHtml(name)}</strong>
                            <span>${escapeHtml(ep.condition_text || 'No structured matcher text available.')}</span>
                            <em>${escapeHtml(ep.reward_text || '')}</em>
                        </button>`;
                    }).join('') || '<div class="settings-muted">No epithet data loaded. Click Sync Data, then reopen this window.</div>'}
                </div>
            </section>`;
        }
        function solverSchedulePreview() {
            const plan = state.trackblazerPlan;
            if (!plan || !(plan.schedule || []).length) return '<div class="settings-muted">No active solver preview. Click Solve Preview or Solve Smart after changing settings.</div>';
            const schedule = (plan.schedule || []).slice(0, 12).map(row => `<div class="v4-plan-row"><span>T${escapeHtml(row.turn || '?')}</span><strong>${escapeHtml(row.name || row.program_id)}</strong><em>${escapeHtml(row.grade || '')} · ${escapeHtml(row.distance || '')} · ${formatCompactNumber(row.est_fans || row.fans || 0)}</em></div>`).join('');
            return `<div class="v4-plan-summary">${escapeHtml(plan.solver || 'Smart Race Solver')} picked ${escapeHtml(plan.race_count || 0)} races · ${escapeHtml(formatCompactNumber(plan.estimated_fans || 0))} fans · score ${escapeHtml(plan.objective_score || 0)}</div>${schedule}`;
        }
        async function renderSmartSolverSettings() {
            const current = currentSmartSolverConfig();
            if (!current || !els.v56SolverSettingsBody) return;
            await loadSolverDefaults();
            const s = solverSettings(current);
            const w = solverWeights(current);
            await loadTrackblazerEpithets();
            const selectedTrainee = selectedTraineeForPlanner().traineeName || 'Select a trainee in Setup';
            els.v56SolverSettingsBody.innerHTML = `
                <section class="settings-card"><h3>Smart Race Solver</h3>
                    <div class="settings-row"><div><strong>Active Mode</strong><span>Use the compact Smart Race Solver / Manual Selection buttons on the Trackblazer card to switch modes.</span></div><div><strong class="solver-selected-trainee">${escapeHtml(state.racePlannerMode === 'manual' ? 'Manual Selection' : 'Smart Race Solver')}</strong></div></div>
                    <div class="settings-row"><div><strong>Character Preset</strong><span>Uses the trainee selected in Setup. Changing this list updates the active trainee selection.</span></div><div><strong class="solver-selected-trainee">${escapeHtml(selectedTrainee)}</strong><button type="button" class="btn btn-sm v4-small-btn" data-control="solver-refresh-profile">Refresh Profile</button></div></div>
                    <div class="solver-character-list-wrap">${renderSolverCharacterList()}</div>
                </section>
                <section class="settings-card"><h3>Aptitudes</h3>${renderSolverAptitudeGrid(current)}</section>
                <section class="settings-card"><h3>Aptitude Threshold</h3>
                    <div class="solver-threshold-copy">Minimum aptitude (distance AND surface) required for a race to be eligible.</div>
                    <div class="solver-threshold-row">${SOLVER_APTITUDE_ORDER.map(grade => `<button type="button" class="solver-threshold-btn ${String(s.min_aptitude_floor || 'C').toUpperCase() === grade ? 'is-active' : ''}" data-control="solver-threshold" data-grade="${grade}">${grade}</button>`).join('')}</div>
                    ${toggleSetting('Include OP / Pre-OP races', 'Also consider lower-grade races. Useful for weak characters or special routing.', 'include_op', s.include_op, 'solver')}
                    ${toggleSetting('Allow racing during Summer (Classic / Senior)', 'Allows solver races in the 4 summer-camp turns each year when a valuable target lands there.', 'allow_summer_racing', s.allow_summer_racing, 'solver')}
                    <div class="settings-row"><div><strong>Distance Preference Mode</strong><span>Controls how strongly Smart Race Solver follows selected/trainee distances.</span></div><select class="settings-control" data-target="solver" data-control="select" data-key="distance_preference_mode"><option value="strict" ${s.distance_preference_mode === 'strict' ? 'selected' : ''}>Strict</option><option value="balanced" ${s.distance_preference_mode !== 'strict' && s.distance_preference_mode !== 'loose' ? 'selected' : ''}>Balanced</option><option value="loose" ${s.distance_preference_mode === 'loose' ? 'selected' : ''}>Loose</option></select></div>
                    <div class="solver-mode-help" id="solver-distance-mode-help"><strong>Distance Preference Modes</strong><ul><li><b>Strict:</b> Only uses preferred distances unless a mandatory race or forced epithet requires otherwise.</li><li><b>Balanced:</b> Strongly prefers selected distances, but allows valuable safe exceptions.</li><li><b>Loose:</b> Treats distance preference as a light scoring bonus only.</li></ul></div>
                </section>
                <section class="settings-card"><h3>Re-Planning</h3>
                    ${toggleSetting('Live Schedule Re-Planning', 'Master switch (smart mode only): when ON (default), the solver re-solves the remaining schedule live as the run unfolds (gated by the two options below). When OFF, the schedule solved at career start is locked in for the whole run — no live re-planning at all. Manual race mode ignores this.', 'enable_live_smart_replan', s.enable_live_smart_replan, 'solver')}
                    <div class="solver-mode-help"><span>This is the parent of the two settings below. With it OFF, "Re-Plan Only on Race Events" and "Disable Re-Plan Upon Race Loss" have no effect because no live re-planning happens.</span></div>
                    ${toggleSetting('Re-Plan Only on Race Events', 'Solve the schedule once and reuse it, re-planning only when a race is lost or a planned race becomes unavailable — instead of re-solving every turn. Prevents the per-turn churn that piled up race streaks and dropped winnable races. Defaults to ON.', 'replan_on_events_only', s.replan_on_events_only, 'solver')}
                    <div class="solver-mode-help"><span>When ON (recommended), the plan is computed once and stays stable through the run — winning a race keeps the plan, and only a loss or an unavailable planned race triggers a re-solve. Turn OFF to restore the old behavior of re-solving the remaining schedule every turn.</span></div>
                    ${toggleSetting('Disable Schedule Re-Plan Upon Race Loss', 'When a race is lost, keep the original schedule instead of re-planning the remaining turns. The loss is still recorded; epithets that depended on the lost race won\'t be re-routed. Defaults to off.', 'disable_schedule_replan_on_race_loss', s.disable_schedule_replan_on_race_loss, 'solver')}
                    <div class="solver-mode-help"><span>By default, losing a race re-plans the remaining turns (the lost race may be re-routed to a later turn and epithet branches re-evaluated). Turn this on to lock in the original schedule after a loss instead.</span></div>
                </section>
                <section class="settings-card"><h3>Set-Bonus Chasing</h3>
                    <label class="settings-row solver-weight-bool-row"><div><strong>Chase Achievable Set-Bonuses (Epithets)</strong><span>When ON, the solver adds a soft reward for completing every achievable race set/title (Triple Crowns, distance/regional/surface sets, etc.), re-prioritizing the route toward the +random-stat set bonuses (Triple Crowns, distance/regional/surface sets, and more). Soft, so it can never make the schedule infeasible. Costs some fans in exchange for stats. Defaults to OFF.</span></div><div class="settings-toggle-wrap"><input type="checkbox" class="solver-settings-control" data-control="solver-weight-bool" data-key="enableOpportunisticEpithets" ${w.enableOpportunisticEpithets ? 'checked' : ''}></div></label>
                    <div class="solver-mode-help"><span>The Target Epithets below bias the route only when this is ON. Forced Epithets are hard constraints and apply regardless of this toggle.</span></div>
                </section>
                ${renderEpithetPicker(current, 'target')}
                ${renderEpithetPicker(current, 'forced')}
                <section class="settings-card"><h3>Optimization Weight Preset</h3>
                    <div class="solver-mode-row"><button type="button" class="solver-mode-btn ${s.optimization_mode === 'stat_epithets' ? 'is-active' : ''}" data-control="solver-mode" data-mode="stat_epithets">Stat Epithets</button><button type="button" class="solver-mode-btn ${s.optimization_mode !== 'stat_epithets' ? 'is-active' : ''}" data-control="solver-mode" data-mode="fans_epithets">Fans + Epithets</button></div>
                    <p class="settings-muted">This is a UI macro that adjusts the solver scoring weights below; the backend consumes those weights, not this label directly.</p>
                </section>
                <section class="settings-card"><h3>Scoring Weights</h3>
                    <div class="solver-weight-grid">
                        ${solverNumberInput('Race Value Weight', 'raceValue', w.raceValue, 'Multiplier on race stat/SP reward.', 0.1, 0, 10)}
                        ${solverNumberInput('Epithet Value Weight', 'epithetValue', w.epithetValue, 'Bonus for races that progress target epithets.', 0.1, 0, 50)}
                        ${solverNumberInput('Fan Weight', 'fanWeight', w.fanWeight, 'Score per projected fan.', 0.001, 0, 0.05)}
                        ${solverNumberInput('Hint Reward Weight', 'hintRewardWeight', w.hintRewardWeight, 'Bonus for skill-hint epithets.', 0.5, 0, 100)}
                        ${solverNumberInput('Consecutive Race Penalty', 'consecutiveRacePenalty', w.consecutiveRacePenalty, 'Penalty after 3+ race streaks.', 0.5, 0, 50)}
                        ${solverNumberInput('Summer Block Penalty', 'summerPenalty', w.summerPenalty, 'Penalty for summer camp racing.', 0.5, 0, 100)}
                        ${solverNumberInput('Race Bonus %', 'raceBonusPct', w.raceBonusPct, 'Projected race reward uplift.', 1, 0, 300)}
                        ${solverNumberInput('Race Cost %', 'raceCostPct', w.raceCostPct, 'Cost subtracted from each race.', 1, 0, 300)}
                        ${solverNumberInput('Fan Bonus %', 'fan_bonus', s.fan_bonus, 'Projected in-game fan bonus applied to fan rewards.', 1, 0, 300)}
                        ${solverNumberInput('Max Streak', 'max_races_in_row', s.max_races_in_row, 'Maximum planned consecutive race streak.', 1, 1, 10)}
                    </div>
                </section>
                <section class="settings-card"><h3>Schedule Preview</h3>
                    <div class="solver-preview-actions"><button id="solver-settings-solve-preview" class="btn btn-sm v4-small-btn" type="button">SOLVE PREVIEW</button><button id="solver-settings-reset-aptitudes" class="btn btn-sm settings-reset-btn" type="button">RESET APTITUDES</button></div>
                    <div class="solver-settings-preview">${solverSchedulePreview()}</div>
                </section>`;
            bindSmartSolverSettingsControls(current);
        }
        function renderSolverCharacterList() {
            const rows = (dashData && dashData.umas ? dashData.umas : []).slice(0, 120);
            const selectedId = String(selection.trainee?.id || '');
            if (!rows.length) return '<div class="settings-muted">Trainee list is not loaded yet.</div>';
            return `<input class="solver-character-search" data-control="solver-character-search" type="search" placeholder="Search characters..."><div class="solver-character-list">${rows.map(uma => `<button type="button" class="solver-character-row ${String(uma.id || '') === selectedId ? 'is-active' : ''}" data-control="solver-character" data-id="${escapeAttr(uma.id || '')}" data-name="${escapeAttr(uma.name || '')}" data-search="${escapeAttr(String(uma.name || '').toLowerCase())}"><strong>${escapeHtml(uma.name || 'Unknown')}</strong><span>ID ${escapeHtml(uma.id || '?')}</span></button>`).join('')}</div>`;
        }
        function bindSmartSolverSettingsControls(current) {
            const root = els.v56SolverSettingsBody;
            if (!root) return;
            root.querySelectorAll('.settings-control[data-target="solver"]').forEach(control => {
                control.addEventListener('change', async () => {
                    const s = solverSettings(current);
                    s[control.dataset.key] = control.dataset.control === 'toggle' ? Boolean(control.checked) : control.value;
                    await saveSolverSetting(current);
                    await renderSmartSolverSettings();
                });
            });
            root.querySelectorAll('[data-control="solver-weight"]').forEach(input => {
                input.addEventListener('change', async () => {
                    const key = input.dataset.key;
                    const min = Number(input.dataset.min || 0);
                    const max = Number(input.dataset.max || 1000);
                    const value = clampNumber(input.value, min, max, Number(input.value || 0));
                    input.value = String(value);
                    if (key === 'fan_bonus' || key === 'max_races_in_row') solverSettings(current)[key] = value;
                    else solverWeights(current)[key] = value;
                    await saveSolverSetting(current);
                });
            });
            root.querySelectorAll('[data-control="solver-weight-bool"]').forEach(input => {
                input.addEventListener('change', async () => {
                    solverWeights(current)[input.dataset.key] = Boolean(input.checked);
                    await saveSolverSetting(current);
                    await renderSmartSolverSettings();
                });
            });
            // Plain <button> elements have no native pressed state, so their
            // "active" look depends entirely on the class-driven re-render.  Flip
            // the class SYNCHRONOUSLY on click (optimistic) so the UI updates
            // instantly even if the async re-render is delayed/fails -- this is
            // the fix for "buttons don't change until I reopen the page".
            root.querySelectorAll('[data-control="solver-aptitude"]').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const row = btn.closest('.solver-grade-row');
                    if (row) row.querySelectorAll('.solver-grade-btn').forEach(b => b.classList.remove('is-active', 'is-manual'));
                    btn.classList.add('is-active', 'is-manual');
                    solverManualAptitudes(current)[btn.dataset.key] = btn.dataset.grade;
                    await saveSolverSetting(current);
                    try { await renderSmartSolverSettings(); } catch (_) {}
                });
            });
            root.querySelectorAll('[data-control="solver-aptitude-reset"]').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const key = btn.dataset.key;
                    delete solverManualAptitudes(current)[key];
                    const row = btn.closest('.solver-grade-row');
                    if (row) {
                        const baseGrade = baseSolverAptitudes()[key];
                        row.querySelectorAll('.solver-grade-btn').forEach(b => {
                            b.classList.remove('is-manual');
                            b.classList.toggle('is-active', b.dataset.grade === baseGrade);
                        });
                    }
                    await saveSolverSetting(current);
                    try { await renderSmartSolverSettings(); } catch (_) {}
                });
            });
            root.querySelectorAll('[data-control="solver-threshold"]').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const row = btn.closest('.solver-threshold-row');
                    if (row) row.querySelectorAll('.solver-threshold-btn').forEach(b => b.classList.remove('is-active'));
                    btn.classList.add('is-active');
                    solverSettings(current).min_aptitude_floor = btn.dataset.grade;
                    await saveSolverSetting(current);
                    try { await renderSmartSolverSettings(); } catch (_) {}
                });
            });
            root.querySelectorAll('[data-control="solver-mode"]').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const s = solverSettings(current);
                    const w = solverWeights(current);
                    s.optimization_mode = btn.dataset.mode;
                    if (btn.dataset.mode === 'stat_epithets') {
                        w.fanWeight = 0;
                        w.raceValue = 1;
                        w.epithetValue = Math.max(Number(w.epithetValue || 1), 1);
                    } else {
                        w.fanWeight = 0.001;
                        w.raceValue = 1;
                        w.epithetValue = Math.max(Number(w.epithetValue || 1), 1);
                    }
                    await saveSolverSetting(current);
                    await renderSmartSolverSettings();
                });
            });
            root.querySelectorAll('[data-control="solver-epithet"]').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const key = btn.dataset.mode === 'forced' ? 'trackblazer_forced_epithets' : 'trackblazer_target_epithets';
                    const name = btn.dataset.name;
                    const arr = Array.isArray(current[key]) ? [...current[key]] : [];
                    current[key] = arr.includes(name) ? arr.filter(v => v !== name) : [...arr, name];
                    await saveSolverSetting(current);
                    await renderSmartSolverSettings();
                });
            });
            root.querySelectorAll('[data-control="solver-epithet-clear"]').forEach(btn => {
                btn.addEventListener('click', async () => {
                    current[btn.dataset.mode === 'forced' ? 'trackblazer_forced_epithets' : 'trackblazer_target_epithets'] = [];
                    await saveSolverSetting(current);
                    await renderSmartSolverSettings();
                });
            });
            root.querySelectorAll('[data-control="solver-epithet-search"]').forEach(input => {
                input.addEventListener('input', () => {
                    const q = String(input.value || '').toLowerCase();
                    const mode = input.dataset.mode;
                    root.querySelectorAll(`.solver-epithet-grid[data-mode="${mode}"] .solver-epithet-card-btn`).forEach(card => {
                        card.style.display = !q || String(card.dataset.search || '').includes(q) ? '' : 'none';
                    });
                });
            });
            root.querySelector('[data-control="solver-character-search"]')?.addEventListener('input', event => {
                const q = String(event.target.value || '').toLowerCase();
                root.querySelectorAll('.solver-character-row').forEach(row => row.style.display = !q || String(row.dataset.search || '').includes(q) ? '' : 'none');
            });
            root.querySelectorAll('[data-control="solver-character"]').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const id = String(btn.dataset.id || '');
                    const idx = (dashData?.umas || []).findIndex(uma => String(uma.id || '') === id);
                    if (idx >= 0) {
                        document.querySelectorAll('#uma-grid .grid-card.selected').forEach(el => el.classList.remove('selected'));
                        selection.trainee = dashData.umas[idx];
                        const umaEls = document.querySelectorAll('#uma-grid .grid-card');
                        if (umaEls[idx]) umaEls[idx].classList.add('selected');
                        state.selectedTraineeProfile = null;
                        await syncSelectionToServer();
                        await loadSelectedTraineeProfile({ force: true }).catch(() => null);
                        renderTeamPanel();
                        updateTrackblazerPlanGate();
                        await renderSmartSolverSettings();
                    }
                });
            });
            root.querySelector('[data-control="solver-refresh-profile"]')?.addEventListener('click', async () => {
                await loadSelectedTraineeProfile({ force: true }).catch(() => null);
                await renderSmartSolverSettings();
            });
            root.querySelector('#solver-settings-reset-aptitudes')?.addEventListener('click', async () => {
                const byTrainee = current.trackblazer_manual_aptitudes_by_trainee || {};
                byTrainee[solverTraineeKey()] = {};
                current.trackblazer_manual_aptitudes_by_trainee = byTrainee;
                current.trackblazer_manual_aptitudes = {};
                await saveSolverSetting(current);
                await renderSmartSolverSettings();
            });
            root.querySelector('#solver-settings-solve-preview')?.addEventListener('click', async () => {
                await generateTrackblazerPlan({ apply: false }).catch(() => {});
                await renderSmartSolverSettings();
            });
        }
        function bindBotSettingsControls() {
            const openers = [
                ['training-settings-open', 'training-settings-modal', renderTrainingSettings],
                ['racing-settings-open', 'racing-settings-modal', renderRacingSettings],
                ['scenario-settings-open', 'scenario-settings-modal', renderScenarioSettings],
                ['v56-solver-settings-btn', 'smart-solver-settings-modal', renderSmartSolverSettings],
            ];
            openers.forEach(([buttonId, modalId, render]) => {
                const btn = document.getElementById(buttonId);
                const modal = document.getElementById(modalId);
                if (!btn || !modal || btn.dataset.bound) return;
                btn.addEventListener('click', async () => {
                    modal.style.display = 'flex';
                    // Smart Race Solver settings show the trainee's aptitudes, which
                    // are only accurate after inheritance is applied at career start.
                    // Force a fresh profile fetch on open so the grid isn't stale.
                    if (modalId === 'smart-solver-settings-modal') {
                        await loadSelectedTraineeProfile({ force: true }).catch(() => null);
                    }
                    await render();
                });
                btn.dataset.bound = '1';
                modal.addEventListener('click', (event) => { if (event.target === modal) modal.style.display = 'none'; });
            });
            const goalToggle = document.getElementById('goal-lookahead-toggle');
            if (goalToggle && !goalToggle.dataset.wired) {
                goalToggle.dataset.wired = '1';
                apiJson('/api/training/goal-lookahead?t=' + Date.now())
                    .then(r => { goalToggle.checked = !!(r && r.enabled); }).catch(() => {});
                goalToggle.addEventListener('change', async () => {
                    try {
                        await apiJson('/api/training/goal-lookahead', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ enabled: goalToggle.checked })
                        });
                    } catch (e) { /* non-fatal */ }
                });
            }
            document.querySelectorAll('.settings-window-close').forEach(btn => {
                if (btn.dataset.bound) return;
                btn.addEventListener('click', () => {
                    const modal = document.getElementById(btn.dataset.close);
                    if (modal) modal.style.display = 'none';
                });
                btn.dataset.bound = '1';
            });
            const priorityModal = document.getElementById('priority-settings-modal');
            if (priorityModal && !priorityModal.dataset.bound) {
                const closePriority = () => { priorityModal.style.display = 'none'; activePriorityModal = null; };
                document.getElementById('priority-settings-close')?.addEventListener('click', closePriority);
                priorityModal.addEventListener('click', event => { if (event.target === priorityModal) closePriority(); });
                document.getElementById('priority-settings-reset')?.addEventListener('click', () => resetPriorityModal());
                document.getElementById('priority-settings-select-all')?.addEventListener('click', () => selectAllPriorityModal());
                priorityModal.dataset.bound = '1';
            }
        }

        function bindPresetHandlers() {
            if (els.presetSelect) {
                els.presetSelect.addEventListener('change', async (e) => {
                    state.selectedPreset = e.target.value;
                    localStorage.setItem('uma_selected_preset', state.selectedPreset);
                    // v7.6 — skill/solver config is per-preset: point the server
                    // at the new preset and reload its skill config.
                    try {
                        await apiJson('/api/settings-presets/active', {
                            method: 'POST', headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ name: state.selectedPreset })
                        });
                    } catch (_) {}
                    try {
                        // Reload BOTH skill and smart-solver/manual-schedule config
                        // for the now-active preset. The solver config was not
                        // reloaded on switch before, so the race schedule/aptitudes
                        // stayed on the previous preset's values until a full reload.
                        await Promise.all([loadSkillConfig(), loadSmartSolverConfig()]);
                        if (els.skillModal && els.skillModal.style.display === 'flex' && typeof renderSkillConfig === 'function') renderSkillConfig();
                    } catch (_) {}
                    syncSelectedPresetRaces();
                    populatePresetUI();
                    renderRaces();
                    applyPresetSelection(getCurrentPreset(), { sync: true, quiet: false });
                    if (document.getElementById('training-settings-modal')?.style.display === 'flex') renderTrainingSettings();
                    if (document.getElementById('racing-settings-modal')?.style.display === 'flex') renderRacingSettings();
                    if (document.getElementById('scenario-settings-modal')?.style.display === 'flex') renderScenarioSettings();
                    if (document.getElementById('smart-solver-settings-modal')?.style.display === 'flex') renderSmartSolverSettings();
                });
            }

            const saveHandler = () => savePresetConfig();
            els.presetSkillThreshold?.addEventListener('change', saveHandler);
            els.presetSaveBtn?.addEventListener('click', saveHandler);

            // LOAD: re-read the active preset's saved values from disk, discarding
            // any unsaved in-memory edits, then refresh the whole UI to match.
            els.presetLoadBtn?.addEventListener('click', async () => {
                await loadPresets();
                try {
                    await Promise.all([loadSkillConfig(), loadSmartSolverConfig()]);
                    if (els.skillModal && els.skillModal.style.display === 'flex' && typeof renderSkillConfig === 'function') renderSkillConfig();
                } catch (_) {}
                syncSelectedPresetRaces();
                populatePresetUI();
                renderRaces();
                applyPresetSelection(getCurrentPreset(), { sync: true, quiet: false });
                if (document.getElementById('training-settings-modal')?.style.display === 'flex') renderTrainingSettings();
                if (document.getElementById('racing-settings-modal')?.style.display === 'flex') renderRacingSettings();
                if (document.getElementById('scenario-settings-modal')?.style.display === 'flex') renderScenarioSettings();
                if (document.getElementById('smart-solver-settings-modal')?.style.display === 'flex') renderSmartSolverSettings();
            });

            els.presetEditSkillsBtn?.addEventListener('click', () => initSkillEditor());
            els.skillModalClose?.addEventListener('click', () => { els.skillModal.style.display = 'none'; });

            els.skillSearch?.addEventListener('input', renderSkillList);

            els.skillAddTierBtn?.addEventListener('click', async () => {
                const current = getCurrentPreset();
                if (!current) return;
                if (!current.learn_skill_list) current.learn_skill_list = [];
                current.learn_skill_list.push([]);
                activeEditTier = current.learn_skill_list.length - 1;
                await savePresetConfig();
                renderSkillEditorRightSide();
            });

            document.getElementById('skill-select-all-btn')?.addEventListener('click', async () => {
                const current = getCurrentPreset();
                if (!current) return;
                const visibleNodes = els.skillList?.querySelectorAll('.skill-list-item') || [];
                let changed = false;

                visibleNodes.forEach(node => {
                    const name = node.getAttribute('data-name');
                    if (activeEditTier === null) {
                        if (!current.learn_skill_blacklist) current.learn_skill_blacklist = [];
                        if (!current.learn_skill_blacklist.includes(name)) {
                            current.learn_skill_blacklist.push(name);
                            changed = true;
                        }
                    } else {
                        if (!current.learn_skill_list) current.learn_skill_list = [];
                        if (!current.learn_skill_list[activeEditTier]) current.learn_skill_list[activeEditTier] = [];
                        if (!current.learn_skill_list[activeEditTier].includes(name)) {
                            current.learn_skill_list[activeEditTier].push(name);
                            changed = true;
                        }
                    }
                });
                if (changed) {
                    await savePresetConfig();
                    renderSkillEditorRightSide();
                }
            });

            document.getElementById('skill-deselect-all-btn')?.addEventListener('click', async () => {
                const current = getCurrentPreset();
                if (!current) return;
                const visibleNodes = els.skillList?.querySelectorAll('.skill-list-item') || [];
                let changed = false;

                const namesToRemove = Array.from(visibleNodes).map(node => node.getAttribute('data-name'));

                if (activeEditTier === null) {
                    if (current.learn_skill_blacklist) {
                        const originalLen = current.learn_skill_blacklist.length;
                        current.learn_skill_blacklist = current.learn_skill_blacklist.filter(s => !namesToRemove.includes(s));
                        if (current.learn_skill_blacklist.length !== originalLen) changed = true;
                    }
                } else {
                    if (current.learn_skill_list && current.learn_skill_list[activeEditTier]) {
                        const originalLen = current.learn_skill_list[activeEditTier].length;
                        current.learn_skill_list[activeEditTier] = current.learn_skill_list[activeEditTier].filter(s => !namesToRemove.includes(s));
                        if (current.learn_skill_list[activeEditTier].length !== originalLen) changed = true;
                    }
                }

                if (changed) {
                    await savePresetConfig();
                    renderSkillEditorRightSide();
                }
            });

            document.getElementById('skill-blacklist-all-btn')?.addEventListener('click', async () => {
                const current = getCurrentPreset();
                if (!current) return;
                const visibleNodes = els.skillList?.querySelectorAll('.skill-list-item') || [];
                let changed = false;

                if (!current.learn_skill_blacklist) current.learn_skill_blacklist = [];
                visibleNodes.forEach(node => {
                    const name = node.getAttribute('data-name');
                    if (!current.learn_skill_blacklist.includes(name)) {
                        current.learn_skill_blacklist.push(name);
                        changed = true;
                    }
                });

                if (changed) {
                    await savePresetConfig();
                    renderSkillEditorRightSide();
                }
            });
            document.getElementById('skill-clear-blacklist-btn')?.addEventListener('click', async () => {
                const current = getCurrentPreset();
                if (!current) return;
                if (current.learn_skill_blacklist && current.learn_skill_blacklist.length > 0) {
                    current.learn_skill_blacklist = [];
                    await savePresetConfig();
                    renderSkillEditorRightSide();
                }
            });

            els.presetAddBtn?.addEventListener('click', async () => {
                const newName = prompt("Enter new preset name:");
                if (!newName || !newName.trim()) return;
                const normalizedName = normalizePresetName(newName);
                if (!normalizedName) {
                    alert("Preset name cannot be empty.");
                    return;
                }
                if (presetNameExists(normalizedName)) {
                    alert("A preset with that name already exists.");
                    return;
                }

                const newPreset = {
                    name: normalizedName,
                    running_style: 1,
                    learn_skill_list: [],
                    learn_skill_blacklist: [],
                    extra_race_list: [],
                    learn_skill_threshold: 888,
                    selection: buildSelectionPresetSnapshot()
                };

                try {
                    const res = await apiJson('/api/settings-presets', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ preset: newPreset })
                    });
                    if (!res.success || !res.preset?.name) {
                        alert(res.detail || "Failed to save new preset.");
                        return;
                    }
                    state.selectedPreset = res.preset.name;
                    localStorage.setItem('uma_selected_preset', state.selectedPreset);
                    await loadSkillConfig();
            await loadSmartSolverConfig();
            await loadPresets();
                    if (els.presetSelect) els.presetSelect.value = state.selectedPreset;
                    syncSelectedPresetRaces();
                    populatePresetUI();
                    renderRaces();
                } catch (e) { alert("Failed to save new preset."); }
            });

            els.presetDelBtn?.addEventListener('click', async () => {
                if (!state.selectedPreset) return;
                const deletedName = state.selectedPreset;
                if (!confirm(`Are you sure you want to delete preset '${deletedName}'?`)) return;

                try {
                    const res = await apiJson('/api/settings-presets/delete', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ name: deletedName })
                    });
                    if (!res.success) {
                        alert(res.detail || "Failed to delete preset.");
                        return;
                    }
                    await loadSkillConfig();
            await loadSmartSolverConfig();
            await loadPresets();
                } catch (e) { alert("Failed to delete preset."); }
            });
        }

        async function loadPresets() {
            try {
                const res = await apiJson('/api/settings-presets?t=' + Date.now());
                if (res.success && res.presets && res.presets.length > 0) {
                    state.presets = res.presets;
                    if (els.presetSelect) {
                        els.presetSelect.innerHTML = state.presets.map(p => `<option value="${escapeAttr(p.name)}">${escapeHtml(p.name)}</option>`).join('');
                    }
                    const saved = localStorage.getItem('uma_selected_preset');
                    const serverActive = res.active || "";
                    if (saved && state.presets.some(p => p.name === saved)) {
                        state.selectedPreset = saved;
                    } else if (serverActive && state.presets.some(p => p.name === serverActive)) {
                        state.selectedPreset = serverActive;
                    } else {
                        state.selectedPreset = state.presets[0].name;
                    }
                    localStorage.setItem('uma_selected_preset', state.selectedPreset);
                    if (els.presetSelect) els.presetSelect.value = state.selectedPreset;
                    populatePresetUI();
                    if (!isCareerCurrentlyActive()) applyPresetSelection(getCurrentPreset(), { sync: true, quiet: true });
                } else {
                    state.presets = [];
                    state.selectedPreset = "";
                    localStorage.removeItem('uma_selected_preset');
                    if (els.presetSelect) els.presetSelect.innerHTML = "";
                    populatePresetUI();
                }
            } catch(e) {
                state.presets = [];
                state.selectedPreset = "";
                localStorage.removeItem('uma_selected_preset');
                populatePresetUI();
            }
            syncStartButton();
            await loadRaceData();
        }

        function renderFriends() {
            const friends = (dashData && dashData.friends) || [];
            clearInvalidFriendSelection();
            const visibleFriends = getVisibleFriends();
            if (dashData) dashData.visibleFriends = visibleFriends;

            if (state.pendingFriendSelection) {
                const f = visibleFriends.find(v =>
                    String(v.viewer_id) === state.pendingFriendSelection.viewer_id &&
                    String(v.support_card_id) === state.pendingFriendSelection.support_card_id
                );
                if (f) {
                    selection.friend = f;
                    state.pendingFriendSelection = null;
                }
            }

            els.friendCount.innerText = `(${visibleFriends.length}/${friends.length})`;
            els.friendGrid.innerHTML = visibleFriends.map(friend => {
                const imgId = friend.support_card_id || '10001';
                const lb = friend.limit_break_count ?? '?';
                return `<div class="grid-card friend-card">
                    <img src="/api/images/${imgId}.png" onerror="hideBrokenImage(this)">
                    <div class="grid-card-overlay">
                        <span class="grid-card-name">${friend.support_name || 'Unknown'}</span>
                        <span class="grid-card-kicker">${friend.type || '?'} | LB${lb}</span>
                    </div>
                </div>`;
            }).filter(Boolean).join('');
            attachFriendHandlers();
            syncFriendSelection();
            renderTeamPanel();
        }
        function appendSeenFriendIds(ids) {
            if (!dashData) return;
            const seen = new Set(dashData.friendExcludeIds || []);
            (ids || []).forEach(id => {
                if (id) seen.add(id);
            });
            dashData.friendExcludeIds = Array.from(seen);
        }
        async function loadFriends(refresh = false) {
            if (!dashData || state.isFetchingFriends) return;
            const isCareerActive = dashData.account && dashData.account.career && dashData.account.career.active;
            if (isCareerActive) {
                els.friendRefreshBtn.disabled = true;
                els.friendStatus.classList.remove('error');
                els.friendStatus.innerText = 'Active career, endpoint blocked';
                return;
            }
            state.isFetchingFriends = true;
            els.friendRefreshBtn.disabled = true;
            els.friendStatus.classList.remove('error');
            els.friendStatus.innerText = refresh ? 'Refreshing friends...' : 'Loading friends...';
            const excludeIds = refresh ? (dashData.friendExcludeIds || []) : [];
            try {
                const data = await apiJson('/api/career/friends', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ exclude_viewer_ids: excludeIds })
                });
                if (!data.success) throw new Error(data.detail || 'Friend load failed');
                dashData.friends = data.friends || [];
                appendSeenFriendIds(data.exclude_viewer_ids || []);
                renderFriends();
                if (data.source === 'Active Career (Skip)') {
                    els.friendStatus.innerText = 'Active career, endpoint blocked';
                    return;
                }
                const source = data.source === 'initial' ? 'initial' : 'refresh';
                const visibleCount = ((dashData && dashData.visibleFriends) || []).length;
                els.friendStatus.innerText = `${source} list: ${visibleCount}/${dashData.friends.length} cards`;
            } catch (e) {
                els.friendStatus.innerText = e.message || 'Friend load failed';
                els.friendStatus.classList.add('error');
            } finally {
                state.isFetchingFriends = false;
                const stillActive = dashData.account && dashData.account.career && dashData.account.career.active;
                els.friendRefreshBtn.disabled = !!stillActive;
            }
        }
        function attachFriendHandlers() {
            const visibleFriends = (dashData && dashData.visibleFriends) || [];
            document.querySelectorAll('#friend-grid .grid-card').forEach((el, i) => {
                el.classList.add('selectable');
                el.addEventListener('click', () => {
                    const friend = visibleFriends[i];
                    const already = selection.friend && friendKey(selection.friend) === friendKey(friend);
                    document.querySelectorAll('#friend-grid .grid-card').forEach(c => c.classList.remove('selected'));
                    selection.friend = already ? null : friend;
                    if (!already) el.classList.add('selected');
                    renderTeamPanel();
                    syncSelectionToServer();
                });
            });
        }

        function formatCompactNumber(value) {
            const n = Number(value || 0);
            if (Math.abs(n) >= 1000000000) return (n / 1000000000).toFixed(2).replace(/\.00$/, '') + 'B';
            if (Math.abs(n) >= 1000000) return (n / 1000000).toFixed(2).replace(/\.00$/, '') + 'M';
            if (Math.abs(n) >= 1000) return (n / 1000).toFixed(1).replace(/\.0$/, '') + 'K';
            return String(Math.round(n));
        }
        function formatDurationSeconds(value) {
            const seconds = Math.max(0, Number(value || 0));
            const h = Math.floor(seconds / 3600);
            const m = Math.floor((seconds % 3600) / 60);
            const s = Math.floor(seconds % 60);
            if (h) return `${h}h ${m}m`;
            if (m) return `${m}m ${s}s`;
            return `${s}s`;
        }
        function kvRows(rows) {
            return rows.map(([k, v]) => `<div class="v4-kv-row"><span>${escapeHtml(k)}</span><strong>${escapeHtml(v)}</strong></div>`).join('');
        }

        function setElText(el, value) {
            if (el) el.textContent = String(value ?? '');
        }
        function pickSnapshotStat(row, names) {
            const stats = row && row.stats ? row.stats : {};
            for (const name of names) {
                if (stats[name] !== undefined) return stats[name];
                const lower = String(name).toLowerCase();
                if (stats[lower] !== undefined) return stats[lower];
            }
            return '-';
        }
        function moodMeta(value) {
            const mood = Number(value || 0);
            const map = {
                5: ['✦', 'Great'],
                4: ['●', 'Good'],
                3: ['◆', 'Normal'],
                2: ['▲', 'Bad'],
                1: ['▼', 'Awful']
            };
            return map[mood] || ['◇', 'Unknown'];
        }

        function moodClass(value) {
            const mood = Number(value || 0);
            if (mood >= 5) return 'mood-great';
            if (mood === 4) return 'mood-good';
            if (mood === 3) return 'mood-normal';
            if (mood === 2) return 'mood-bad';
            if (mood === 1) return 'mood-awful';
            return 'mood-unknown';
        }
        function colorizeActionDetail(value, options = {}) {
            const text = String(value ?? '');
            const escaped = escapeHtml(text);
            // Only colorize actual stat readouts, never plain words inside race names
            // such as "Stakes" or "Sprinters". A stat token must be followed by a number.
            const allowSkillPoint = options.allowSkillPoint === true;
            const statPattern = /\b(HP|SPD|STA|PWR|GUT|WIT|Speed|Stamina|Power|Guts|Wit|Wisdom)\s+([+-]?\d+(?:\.\d+)?(?:\/\d+)?)/gi;
            let out = escaped.replace(statPattern, (match, label, number) => {
                const keyMap = { speed: 'spd', stamina: 'sta', power: 'pwr', guts: 'gut', wisdom: 'wit' };
                const key = keyMap[String(label).toLowerCase()] || String(label).toLowerCase();
                return `<span class="v57-stat-chip stat-${key}">${escapeHtml(String(label).toUpperCase())} <b>${escapeHtml(number)}</b></span>`;
            });
            if (allowSkillPoint) {
                out = out.replace(/\bSP\s+([+-]?\d+(?:\.\d+)?)/gi, (match, number) =>
                    `<span class="v57-stat-chip stat-sp">SP <b>${escapeHtml(number)}</b></span>`
                );
            }
            return out;
        }
        function setPortrait(cardId) {
            if (!els.v53CareerPortrait) return;
            const id = String(cardId || '').trim();
            els.v53CareerPortrait.src = id ? `/api/images/${encodeURIComponent(id)}.png` : '/broom.png';
            els.v53CareerPortrait.onerror = function() { this.onerror = null; this.src = '/broom.png'; };
        }
        function buildLiveCareerFromRunner(runner) {
            const live = runner && runner.current_chara;
            if (!live || !Number(live.turn || 0)) return null;
            const existing = state.account && state.account.career ? state.account.career : {};
            return {
                active: Boolean(runner.running || existing.active),
                card_id: live.card_id || existing.card_id,
                name: existing.name || 'Current Career',
                turn: live.turn || existing.turn || 0,
                fans: live.fans || existing.fans || 0,
                vital: live.vital ?? existing.vital,
                max_vital: live.max_vital ?? existing.max_vital,
                motivation: live.motivation ?? existing.motivation,
                stats: live.stats || {},
            };
        }
        function getMainActionRows(runner = state.runner) {
            if (!runner) return [];
            const rows = (runner.action_history && runner.action_history.length)
                ? runner.action_history
                : deriveActionHistory(runner.log || []);
            return rows || [];
        }
        function formatMainActionDetail(row) {
            const stats = row && row.stats ? row.stats : {};
            const keys = Object.keys(stats || {});
            if (keys.length) {
                return [
                    `HP ${stats.hp ?? 0}/${stats.max_hp ?? 100}`,
                    `MOOD ${stats.motivation ?? 0}`,
                    `SPD ${stats.speed ?? 0} STA ${stats.stamina ?? 0} PWR ${stats.power ?? 0} GUT ${stats.guts ?? 0} WIT ${stats.wit ?? 0}`
                ].join(' | ');
            }
            return row.detail || '';
        }
        const ACTION_LOG_MAX_ROWS = 500;
        function isActionLogNearBottom(el) {
            if (!el) return true;
            const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
            return distanceFromBottom < 96;
        }
        function stickActionLogToBottom(el) {
            if (!el) return;
            requestAnimationFrame(() => {
                el.scrollTop = el.scrollHeight;
            });
        }
        // MANT/Trackblazer shop-item icons (game8 source), keyed by the exact
        // in-game item name as it appears in decision-reasoning text. Served
        // locally from /api/item-icons/<id>.<ext>.
        const ITEM_ICON_MAP = {
            "Speed Notepad": "/api/item-icons/1001.jpg", "Stamina Notepad": "/api/item-icons/1002.png",
            "Power Notepad": "/api/item-icons/1003.png", "Guts Notepad": "/api/item-icons/1004.png",
            "Wit Notepad": "/api/item-icons/1005.png",
            "Speed Manual": "/api/item-icons/1101.png", "Stamina Manual": "/api/item-icons/1102.png",
            "Power Manual": "/api/item-icons/1103.png", "Guts Manual": "/api/item-icons/1104.png",
            "Wit Manual": "/api/item-icons/1105.jpg",
            "Speed Scroll": "/api/item-icons/1201.png", "Stamina Scroll": "/api/item-icons/1202.png",
            "Power Scroll": "/api/item-icons/1203.jpg", "Guts Scroll": "/api/item-icons/1204.png",
            "Wit Scroll": "/api/item-icons/1205.png",
            "Vita 20": "/api/item-icons/2001.png", "Vita 40": "/api/item-icons/2002.png",
            "Vita 65": "/api/item-icons/2003.png", "Royal Kale Juice": "/api/item-icons/2101.png",
            "Energy Drink MAX": "/api/item-icons/2201.png", "Energy Drink MAX EX": "/api/item-icons/2202.png",
            "Plain Cupcake": "/api/item-icons/2301.jpg", "Berry Sweet Cupcake": "/api/item-icons/2302.png",
            "Yummy Cat Food": "/api/item-icons/3001.png", "Grilled Carrots": "/api/item-icons/3101.jpg",
            "Pretty Mirror": "/api/item-icons/4001.jpg", "Reporter's Binoculars": "/api/item-icons/4002.png",
            "Master Practice Guide": "/api/item-icons/4003.png", "Scholar's Hat": "/api/item-icons/4004.png",
            "Fluffy Pillow": "/api/item-icons/4101.png", "Pocket Planner": "/api/item-icons/4102.png",
            "Rich Hand Cream": "/api/item-icons/4103.png", "Smart Scale": "/api/item-icons/4104.png",
            "Aroma Diffuser": "/api/item-icons/4105.png", "Practice Drills DVD": "/api/item-icons/4106.png",
            "Miracle Cure": "/api/item-icons/4201.png",
            "Speed Training Application": "/api/item-icons/5001.png", "Stamina Training Application": "/api/item-icons/5002.png",
            "Power Training Application": "/api/item-icons/5003.png", "Guts Training Application": "/api/item-icons/5004.png",
            "Wit Training Application": "/api/item-icons/5005.png",
            "Reset Whistle": "/api/item-icons/7001.png",
            "Coaching Megaphone": "/api/item-icons/8001.png", "Motivating Megaphone": "/api/item-icons/8002.png",
            "Empowering Megaphone": "/api/item-icons/8003.png",
            "Speed Ankle Weights": "/api/item-icons/9001.png", "Stamina Ankle Weights": "/api/item-icons/9002.png",
            "Power Ankle Weights": "/api/item-icons/9003.png", "Guts Ankle Weights": "/api/item-icons/9004.png",
            "Good-Luck Charm": "/api/item-icons/10001.png",
            "Artisan Cleat Hammer": "/api/item-icons/11001.png", "Master Cleat Hammer": "/api/item-icons/11002.png",
            "Glow Sticks": "/api/item-icons/11003.png"
        };
        let _itemIconRegex = null;
        const _itemIconByEscaped = {};
        function _ensureItemIconRegex() {
            if (_itemIconRegex) return;
            // Match against HTML-escaped names (reason text is escapeHtml'd first),
            // longest-first so e.g. "Energy Drink MAX EX" wins over "Energy Drink MAX".
            const names = Object.keys(ITEM_ICON_MAP).sort((a, b) => b.length - a.length);
            const alts = names.map(n => {
                const esc = escapeHtml(n);
                _itemIconByEscaped[esc] = { name: n, path: ITEM_ICON_MAP[n] };
                return esc.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            });
            _itemIconRegex = new RegExp('(' + alts.join('|') + ')', 'g');
        }
        // Given already-escaped reason text, prepend each shop item's icon before
        // its name. Single pass, so inserted <img> tags are never re-matched.
        function decorateItemIcons(escapedText) {
            if (!escapedText) return escapedText;
            _ensureItemIconRegex();
            return escapedText.replace(_itemIconRegex, (m) => {
                const hit = _itemIconByEscaped[m];
                if (!hit) return m;
                return `<img class="reason-item-icon" src="${hit.path}" alt="" title="${m}" loading="lazy" onerror="this.style.display='none'">${m}`;
            });
        }

        function buildDecisionReasoning(normalized) {
            const stats = normalized.stats || {};
            const action = String(normalized.action || '').toLowerCase();
            const facility = normalized.facility || '';
            const reasonList = Array.isArray(normalized.reasoning) ? normalized.reasoning.filter(Boolean) : [];
            if (reasonList.length) return reasonList;
            const hp = Number(stats.hp ?? 0);
            const maxHp = Number(stats.max_hp ?? 100) || 100;
            const mood = Number(stats.motivation ?? 0);
            const base = normalized.reason || normalized.detail || '';
            const out = [];
            if (base) out.push(String(base));
            if (action === 'train') {
                out.push(`${facility || 'Training'} was chosen because it scored highest among the available commands.`);
                out.push(hp < maxHp * 0.35 ? `HP is low (${hp}/${maxHp}), so this training needed strong value to beat recovery.` : `HP is workable (${hp}/${maxHp}), allowing training.`);
                if (mood >= 4) out.push('Mood is favorable, improving training value.');
            } else if (action === 'race') {
                out.push(`${facility || 'This race'} was selected from the active race/fan route.`);
                out.push(hp <= maxHp * 0.15 ? `HP is critical (${hp}/${maxHp}), but the route/fan objective can still require racing.` : `HP is acceptable enough for the planned race (${hp}/${maxHp}).`);
                out.push('Race selection is influenced by preset goals, Trackblazer route value, and aptitude fit.');
            } else if (action === 'rest') {
                out.push(`Rest was selected to recover from ${hp}/${maxHp} HP.`);
                out.push('Recovery was higher value than a risky command this turn.');
            } else if (action === 'recreation') {
                out.push('Recreation was selected to improve mood and future turn value.');
                if (mood <= 2) out.push(`Mood is low (${mood}), so mood repair is important.`);
            } else if (action === 'medic') {
                out.push('Medic was selected to clear a bad condition before it snowballs.');
            } else if (action === 'finish') {
                out.push('Career completion flow was reached.');
            } else {
                out.push('The strategy engine selected this action from the current game state.');
            }
            return Array.from(new Set(out.filter(Boolean))).slice(0, 5);
        }

        function findDecisionTraceForRow(row) {
            const traces = state.decisionTraceRows || [];
            if (!row || !traces.length) return null;
            const turn = Number(row.turn || 0);
            const action = String(row.action || '').toLowerCase();
            return traces.slice().reverse().find(trace => {
                if (Number(trace.turn || 0) !== turn) return false;
                const traceAction = String(trace.action || trace.selected_action || trace.command || '').toLowerCase();
                return !action || !traceAction || traceAction === action || traceAction.includes(action) || action.includes(traceAction);
            }) || traces.slice().reverse().find(trace => Number(trace.turn || 0) === turn) || null;
        }

        function renderTraceReasonExtras(trace) {
            if (!trace) return '';
            const lines = [];
            if (trace.reason) lines.push(String(trace.reason));
            if (Array.isArray(trace.reasoning)) trace.reasoning.filter(Boolean).forEach(item => lines.push(String(item)));
            const bestTraining = Array.isArray(trace.training_candidates) ? trace.training_candidates[0] : null;
            if (bestTraining) {
                const name = bestTraining.name || bestTraining.facility || 'Best training';
                const score = bestTraining.score ?? bestTraining.total_score ?? '';
                const completion = bestTraining.target_completion_pct != null ? ` · target ${bestTraining.target_completion_pct}%` : '';
                const mainGain = bestTraining.main_gain != null ? ` · main +${bestTraining.main_gain}` : '';
                lines.push(`Top training candidate: ${name}${score !== '' ? ` (${score})` : ''}${completion}${mainGain}.`);
                if (Array.isArray(bestTraining.reason_flags) && bestTraining.reason_flags.length) {
                    lines.push(`Training factors: ${bestTraining.reason_flags.slice(0, 3).join(', ')}.`);
                }
            }
            const bestRace = Array.isArray(trace.race_candidates) ? trace.race_candidates[0] : null;
            if (bestRace) {
                const name = bestRace.name || bestRace.race_name || 'Best race';
                const score = bestRace.score ?? bestRace.objective_score ?? '';
                lines.push(`Top race candidate: ${name}${score !== '' ? ` (${score})` : ''}.`);
            }
            return Array.from(new Set(lines.filter(Boolean))).slice(0, 6).map(item => `<li>${decorateItemIcons(escapeHtml(item))}</li>`).join('');
        }

        function actionReasonKey(row) {
            const normalized = normalizeHistoryAction(row || {});
            return [
                normalized.turn ?? '',
                String(normalized.action || '').toLowerCase(),
                String(normalized.facility || ''),
                String(normalized.detail || formatMainActionDetail(normalized) || '')
            ].join('|');
        }

        function renderDecisionReasoning(rows, selectedIndex = null, opts = {}) {
            if (!els.v547DecisionReasoning) return;
            const safeRows = (rows || []).slice(-ACTION_LOG_MAX_ROWS);
            if (!safeRows.length) {
                els.v547DecisionReasoning.innerHTML = '<div class="v547-reason-empty">Decision explanations will appear here as the bot acts.</div>';
                if (els.v547ReasonTurn) els.v547ReasonTurn.textContent = 'WAITING';
                state.selectedReasonKey = null;
                state.reasonSelectionLocked = false;
                return;
            }
            let idx = selectedIndex == null ? safeRows.length - 1 : Math.max(0, Math.min(safeRows.length - 1, selectedIndex));
            if (state.reasonSelectionLocked && state.selectedReasonKey) {
                const lockedIndex = safeRows.findIndex(row => actionReasonKey(row) === state.selectedReasonKey);
                if (lockedIndex >= 0) {
                    idx = lockedIndex;
                } else {
                    state.selectedReasonKey = null;
                    state.reasonSelectionLocked = false;
                    idx = safeRows.length - 1;
                }
            }
            const previousScrollTop = els.v547DecisionReasoning.scrollTop;
            const wasNearBottom = isActionLogNearBottom(els.v547DecisionReasoning);
            const selected = normalizeHistoryAction(safeRows[idx]);
            if (els.v547ReasonTurn) els.v547ReasonTurn.textContent = `T${selected.turn ?? '?'}`;
            const rowsHtml = safeRows.map((raw, index) => {
                const row = normalizeHistoryAction(raw);
                const action = String(row.action || '').toLowerCase();
                const reasons = buildDecisionReasoning(row).slice(0, 3);
                const trace = findDecisionTraceForRow(row);
                const traceItems = renderTraceReasonExtras(trace);
                const statLine = Object.keys(row.stats || {}).length
                    ? `<div class="v547-reason-stats">${colorizeActionDetail(formatMainActionDetail(row))}</div>`
                    : '';
                return `<article class="v524-reason-turn ${index === idx ? 'is-active' : ''}" data-reason-index="${index}">
                    <header><span>T${escapeHtml(row.turn ?? '?')}</span><strong>${escapeHtml(row.facility || 'Decision')}</strong><em class="action-pill action-pill-${escapeAttr(action)}">${escapeHtml(String(action || '?').toUpperCase())}</em></header>
                    ${statLine}
                    <ul>${reasons.map(item => `<li>${decorateItemIcons(escapeHtml(item))}</li>`).join('')}${traceItems}</ul>
                </article>`;
            }).join('');
            els.v547DecisionReasoning.innerHTML = `<div class="v524-reason-intro">Turn-by-turn reasoning for the active career. Click a row in the Action Log or a card here to focus it.</div><div class="v524-reason-turn-list">${rowsHtml}</div>`;
            els.v547DecisionReasoning.querySelectorAll('.v524-reason-turn').forEach(card => {
                card.addEventListener('click', () => {
                    const index = Number(card.dataset.reasonIndex || 0);
                    const clickedKey = actionReasonKey(safeRows[index]);
                    // v6.7.25 — toggle focus: clicking the already-focused turn unlocks it
                    // so the panel resumes tail-following the live run.
                    if (state.reasonSelectionLocked && state.selectedReasonKey === clickedKey) {
                        state.selectedReasonKey = null;
                        state.reasonSelectionLocked = false;
                        renderDecisionReasoning(safeRows, safeRows.length - 1, { scrollActive: false });
                        els.v53ActionLog?.querySelectorAll('tbody tr.v547-log-selected').forEach(rowEl => {
                            rowEl.classList.remove('v547-log-selected');
                        });
                        if (isActionLogNearBottom(els.v547DecisionReasoning) || true) {
                            // Re-pin to bottom so tail-follow visibly resumes on the next snapshot.
                            stickActionLogToBottom(els.v547DecisionReasoning);
                        }
                        return;
                    }
                    state.selectedReasonKey = clickedKey;
                    state.reasonSelectionLocked = true;
                    renderDecisionReasoning(safeRows, index, { scrollActive: true });
                    els.v53ActionLog?.querySelectorAll('tbody tr[data-reason-index]').forEach(rowEl => {
                        rowEl.classList.toggle('v547-log-selected', Number(rowEl.dataset.reasonIndex || 0) === index);
                    });
                });
            });
            const active = els.v547DecisionReasoning.querySelector('.v524-reason-turn.is-active');
            if (active && opts.scrollActive) {
                active.scrollIntoView({ block: 'nearest' });
            } else if (wasNearBottom && !state.reasonSelectionLocked) {
                // Tail-follow: when the panel is scrolled to the bottom, keep it
                // pinned there as new turns stream in. Scrolling up pauses this;
                // manually scrolling back to the bottom resumes it.
                stickActionLogToBottom(els.v547DecisionReasoning);
            } else {
                els.v547DecisionReasoning.scrollTop = previousScrollTop;
            }
        }

        function renderMainActionLog(rows) {
            if (!els.v53ActionLog) return;
            const allRows = rows || [];
            const safeRows = allRows.slice(-ACTION_LOG_MAX_ROWS);
            const wasNearBottom = isActionLogNearBottom(els.v53ActionLog);
            if (!safeRows.length) {
                els.v53ActionLog.innerHTML = '<div class="v512-main-log-empty">No actions yet.</div>';
                renderDecisionReasoning([]);
                return;
            }
            const omitted = Math.max(0, allRows.length - safeRows.length);
            const latestIndex = safeRows.length - 1;
            const lockedIndex = state.reasonSelectionLocked && state.selectedReasonKey
                ? safeRows.findIndex(row => actionReasonKey(row) === state.selectedReasonKey)
                : -1;
            const activeIndex = lockedIndex >= 0 ? lockedIndex : latestIndex;
            // Perf: this runs on every 1.5s status poll. Skip the full <table>
            // innerHTML rebuild when nothing that affects the render changed
            // (mirrors the dirty-check pattern in monitor.js).
            const lastRow = safeRows[safeRows.length - 1];
            const dirtyKey = `${allRows.length}|${safeRows.length}|${activeIndex}|${lastRow ? lastRow.turn : ''}|${lastRow ? lastRow.action : ''}|${lastRow ? (lastRow.detail || '') : ''}`;
            if (dirtyKey === state._actionLogKey) return;
            state._actionLogKey = dirtyKey;
            const body = safeRows.map((row, index) => {
                const normalized = normalizeHistoryAction(row);
                const action = String(normalized.action || '').toLowerCase();
                const facility = normalized.facility ?? '';
                const detail = formatMainActionDetail(normalized);
                const active = index === activeIndex ? ' class="v547-log-selected"' : '';
                return `
                    <tr${active} data-reason-index="${index}">
                        <td class="v512-turn-cell">${escapeHtml(normalized.turn ?? '?')}</td>
                        <td><span class="action-pill action-pill-${escapeAttr(action)}">${escapeHtml(String(action || '?').toUpperCase())}</span></td>
                        <td class="v512-facility-cell">${escapeHtml(facility)}</td>
                        <td class="v512-detail-cell">${colorizeActionDetail(detail)}</td>
                    </tr>`;
            }).join('');
            const bufferNotice = omitted > 0
                ? `<caption class="v512-main-log-buffer-note">Showing latest ${safeRows.length.toLocaleString()} of ${allRows.length.toLocaleString()} actions. Full history remains in runtime reports.</caption>`
                : '';
            els.v53ActionLog.innerHTML = `
                <table class="v512-main-log-table">
                    ${bufferNotice}
                    <thead>
                        <tr>
                            <th>Turn</th>
                            <th>Action</th>
                            <th>Facility</th>
                            <th>Detail</th>
                        </tr>
                    </thead>
                    <tbody>${body}</tbody>
                </table>`;
            els.v53ActionLog.querySelectorAll('tbody tr[data-reason-index]').forEach(rowEl => {
                rowEl.addEventListener('click', () => {
                    const index = Number(rowEl.dataset.reasonIndex || 0);
                    const clickedKey = actionReasonKey(safeRows[index]);
                    // v6.7.25 — toggle focus: a second click on the same row unlocks
                    // selection so the decision reasoning panel resumes tail-following.
                    if (state.reasonSelectionLocked && state.selectedReasonKey === clickedKey) {
                        state.selectedReasonKey = null;
                        state.reasonSelectionLocked = false;
                        els.v53ActionLog.querySelectorAll('tbody tr').forEach(el => el.classList.remove('v547-log-selected'));
                        renderDecisionReasoning(allRows, allRows.length - 1, { scrollActive: false });
                        return;
                    }
                    state.selectedReasonKey = clickedKey;
                    state.reasonSelectionLocked = true;
                    els.v53ActionLog.querySelectorAll('tbody tr').forEach(el => el.classList.remove('v547-log-selected'));
                    rowEl.classList.add('v547-log-selected');
                    renderDecisionReasoning(allRows, index, { scrollActive: true });
                });
            });
            renderDecisionReasoning(allRows, activeIndex, { scrollActive: false });
            if (wasNearBottom) stickActionLogToBottom(els.v53ActionLog);
        }
        function renderV53Cockpit({ runner = state.runner, snapshots = state.lastSnapshots || [] } = {}) {
            const liveCareer = buildLiveCareerFromRunner(runner);
            const career = liveCareer || (state.account && state.account.career);
            const latest = snapshots && snapshots.length ? snapshots[snapshots.length - 1] : null;
            const running = runner && runner.running;
            setElText(els.v53RunBadge, running ? 'RUNNING' : (runner && runner.finished ? 'FINISHED' : 'IDLE'));
            const statSource = (career && career.stats) || (latest && latest.stats) || {};
            const turn = (career && career.turn) || runner?.turn || latest?.turn || '?';
            const fans = (career && career.fans) || latest?.fans || 0;
            const hpNow = Number((career && career.vital) ?? (latest && latest.vital) ?? statSource.hp ?? 0);
            const hpMaxRaw = Number((career && career.max_vital) ?? (latest && latest.max_vital) ?? statSource.max_hp ?? 100);
            const hpMax = hpMaxRaw > 0 ? hpMaxRaw : 100;
            const hpPct = Math.max(0, Math.min(100, Math.round((hpNow / hpMax) * 100)));
            const motivationValue = (career && career.motivation) ?? (latest && latest.motivation) ?? statSource.motivation;
            const mood = moodMeta(motivationValue);
            if (career && career.active) {
                setElText(els.v53CareerName, career.name || 'Current Career');
                setElText(els.v53CurrentCareer, `Turn ${turn} · ${formatCompactNumber(fans)} fans`);
                setPortrait(career.card_id);
            } else if (latest) {
                setElText(els.v53CareerName, 'Latest snapshot');
                setElText(els.v53CurrentCareer, `Turn ${turn} · ${formatCompactNumber(fans)} fans`);
                setPortrait(career && career.card_id);
            } else {
                setElText(els.v53CareerName, 'No active career.');
                setElText(els.v53CurrentCareer, 'Waiting for signal...');
                setPortrait(null);
            }
            if (els.v53HpFill) els.v53HpFill.style.width = `${hpPct}%`;
            if (els.v53HpText) els.v53HpText.textContent = `HP ${Math.round(hpNow)}/${hpMax}`;
            if (els.v53MoodIcon) {
                els.v53MoodIcon.textContent = mood[0];
                els.v53MoodIcon.className = `v53-mood-icon ${moodClass(motivationValue)}`;
            }
            if (els.v53MoodText) {
                els.v53MoodText.textContent = mood[1];
                els.v53MoodText.className = `v53-mood-text ${moodClass(motivationValue)}`;
            }
            {
                const wrapped = { stats: statSource || {} };
                setElText(els.v53StatSpeed, pickSnapshotStat(wrapped, ['speed', 'Speed', 'spd', 'SPD']));
                setElText(els.v53StatStamina, pickSnapshotStat(wrapped, ['stamina', 'Stamina', 'sta', 'STA']));
                setElText(els.v53StatPower, pickSnapshotStat(wrapped, ['power', 'Power', 'pwr', 'PWR']));
                setElText(els.v53StatGuts, pickSnapshotStat(wrapped, ['guts', 'Guts', 'gut', 'GUT']));
                setElText(els.v53StatWit, pickSnapshotStat(wrapped, ['wiz', 'wit', 'Wisdom', 'Wit', 'intelligence']));
                setElText(els.v53StatSp, statSource.skill_point ?? latest?.skill_point ?? latest?.skillPoint ?? '-');
            }
            const trace = runner && runner.decision_trace ? runner.decision_trace : null;
            if (trace && (trace.action || trace.reason)) {
                setElText(els.v53LatestDecision, `T${trace.turn ?? '?'} · ${trace.action || 'decision'} · ${trace.reason || ''}`);
            } else if (runner && runner.last_action) {
                setElText(els.v53LatestDecision, runner.last_action);
            }
            const lifetime = (runner && runner.lifetime) || {};
            setElText(els.v53TotalFans, formatCompactNumber(lifetime.total_fans_gained_live || lifetime.total_fans_gained || runner?.fans_gained || 0));
            setElText(els.v53Fph, formatCompactNumber(lifetime.fans_per_hour_live || runner?.fans_per_hour || 0));
            setElText(els.v53Runtime, formatDurationSeconds(lifetime.total_runtime_seconds_live || lifetime.total_runtime_seconds || 0));
            setElText(els.v53Careers, lifetime.careers_completed || runner?.careers_completed || 0);
            // v7.6.2: fan gain for the CURRENT career (fans accumulate from 0
            // each career, so the running total is the gain). Shown alongside
            // the lifetime totals.
            setElText(els.v53CareerFans, formatCompactNumber(fans || 0));
            setElText(els.v53TurnCount, `${runner?.turn || latest?.turn || 0} TURNS`);
            if (els.v53ActionLog) {
                const rows = getMainActionRows(runner);
                renderMainActionLog(rows);
            }
        }
        function renderAiLearningStatus(ai = state.lastAiStatus) {
            if (!els.v532AiStatus) return;
            if (!ai || !ai.success) {
                els.v532AiStatus.textContent = 'AI dataset waiting for completed careers.';
                return;
            }
            const files = ai.files || {};
            const turns = files.turn_decisions?.rows ?? 0;
            const careers = files.career_summaries?.rows ?? 0;
            const synth = files.synthetic_scenarios?.rows ?? 0;
            const policy = ai.auto_training?.live_policy || {};
            const trained = ai.auto_training?.latest_training_run?.trained_at || '';
            const health = ai.health || ai.auto_training?.data_health || ai.auto_training?.latest_training_run?.data_health || {};
            const policyNote = policy.enabled ? ` · Live hints ${policy.race_adjustments || 0}` : ' · Live hints off';
            els.v532AiStatus.textContent = `Turns ${turns} · Careers ${careers} · Synthetic prompts ${synth}${policyNote}${trained ? ' · Trained ' + trained : ''}`;
            renderAiHealth(health);
            renderAiAutoStatus(ai.auto_training);
            renderAiLivePolicy(ai.auto_training, state.lastAiDashboard);
            renderStyleAdaptation(ai.auto_training?.style_adaptation || state.lastAiDashboard?.style_adaptation || {}, ai.auto_training);
            // Local LLM form/status must be hydrated only from /api/ai/local-llm/latest.
            // The AI dashboard can contain a stale local_llm summary from the last training run.
            // Applying that snapshot here made the Enable checkbox appear to undo itself after save.

        }

        function renderAiAutoStatus(auto) {
            if (!els.v533AiAutoStatus && !els.v533AiAutoToggle) return;
            const cfg = auto?.auto_config || {};
            if (els.v533AiAutoToggle && typeof cfg.enabled !== 'undefined') {
                els.v533AiAutoToggle.checked = Boolean(cfg.enabled);
            }
            const latest = auto?.latest_training_run || {};
            const live = auto?.live_policy || {};
            const bg = auto?.background || {};
            const text = cfg.enabled
                ? `Auto-training on · every ${cfg.interval_minutes || 60}m / ${cfg.train_after_completed_careers || 1} career(s) · ${live.enabled ? 'live hints on' : 'live hints off'}${latest.trained_at ? ' · last ' + latest.trained_at : ''}${bg.last_error ? ' · error: ' + bg.last_error : ''}`
                : 'Auto-training off. Manual rebuild/train still available.';
            if (els.v533AiAutoStatus) els.v533AiAutoStatus.textContent = text;
        }


        function renderAiLivePolicy(auto, dashboard) {
            if (!els.v539AiLivePolicyToggle && !els.v539AiLivePolicyRecommendation && !els.v539AiLivePolicyState) return;
            const cfg = auto?.auto_config || {};
            const live = auto?.live_policy || dashboard?.live_policy || {};
            const recommendation = live.recommendation || dashboard?.live_policy?.recommendation || auto?.latest_training_run?.live_policy_recommendation || {};
            const requested = typeof cfg.enable_live_policy_assistance !== 'undefined'
                ? Boolean(cfg.enable_live_policy_assistance)
                : Boolean(live.requested_enabled || live.enabled);
            const active = Boolean(live.enabled) && requested;
            if (els.v539AiLivePolicyToggle) {
                els.v539AiLivePolicyToggle.checked = requested;
            }
            if (els.v539AiLivePolicyState) {
                els.v539AiLivePolicyState.textContent = active ? 'ACTIVE' : (requested ? 'REQUESTED' : 'OFF');
                els.v539AiLivePolicyState.classList.toggle('is-active', active);
                els.v539AiLivePolicyState.classList.toggle('is-requested', requested && !active);
            }
            if (els.v539AiLivePolicyRecommendation) {
                const recommendEnable = Boolean(recommendation.recommend_enable);
                const msg = recommendation.message || (recommendEnable
                    ? 'Recommended: ENABLE. The model currently looks healthy enough for confidence-gated live hints.'
                    : 'Recommended: KEEP DISABLED until training produces enough safe, high-confidence model evidence.');
                const coverage = typeof recommendation.race_result_coverage !== 'undefined'
                    ? ` · race coverage ${Math.round(Number(recommendation.race_result_coverage || 0) * 100)}%`
                    : '';
                const adjustments = typeof recommendation.adjustment_count !== 'undefined'
                    ? ` · learned adjustments ${recommendation.adjustment_count || 0}`
                    : '';
                els.v539AiLivePolicyRecommendation.classList.toggle('is-enable', recommendEnable);
                els.v539AiLivePolicyRecommendation.classList.toggle('is-disable', !recommendEnable);
                els.v539AiLivePolicyRecommendation.textContent = `${msg}${coverage}${adjustments}`;
            }
        }

        function renderStyleAdaptation(stylePayload, auto) {
            const cfg = auto?.auto_config || {};
            if (els.v542StyleAdaptationMode && cfg.style_adaptation_mode) {
                els.v542StyleAdaptationMode.value = cfg.style_adaptation_mode;
            }
            const report = stylePayload?.report || stylePayload?.style_adaptation?.report || {};
            const modelSummary = stylePayload?.model_summary || stylePayload?.style_adaptation?.model_summary || {};
            if (els.v542StyleAdaptationStatus) {
                const mode = cfg.style_adaptation_mode || report.mode || 'shadow';
                const unlocked = Boolean(report.auto_apply_unlocked || report.safe_for_auto_apply);
                const completed = report.completed_experiences ?? modelSummary.completed_experiences ?? 0;
                const switches = report.style_change_outcomes ?? modelSummary.style_change_outcomes ?? 0;
                els.v542StyleAdaptationStatus.textContent = `Mode ${String(mode).toUpperCase()} · experiences ${completed} · style-change outcomes ${switches} · Auto Apply ${unlocked ? 'UNLOCKED' : 'LOCKED'}`;
                els.v542StyleAdaptationStatus.classList.toggle('is-unlocked', unlocked);
            }
            if (els.v542StyleAdaptationReport) {
                if (!report || !Object.keys(report).length) {
                    els.v542StyleAdaptationReport.textContent = 'No style model yet. Keep Shadow Only enabled, run races, then click Train Now.';
                    return;
                }
                const styles = report.styles || modelSummary.styles || {};
                const styleRows = Object.values(styles).slice(0, 4).map(row => `${escapeHtml(row.label || row.style || '?')}: win ${escapeHtml(Math.round(Number(row.win_rate || 0) * 100))}% · samples ${escapeHtml(row.samples || 0)}`).join(' · ');
                const rec = report.recommendation || 'Style adaptation report generated.';
                const bad = Math.round(Number(report.bad_switch_rate || 0) * 100);
                els.v542StyleAdaptationReport.innerHTML = `<div class="v536-ai-line">${escapeHtml(rec)} · bad switch rate ${escapeHtml(bad)}%</div>${styleRows ? `<div class="v536-ai-line">${styleRows}</div>` : ''}`;
            }
        }

        function renderAiHealth(health) {
            if (!els.v534AiHealth) return;
            if (!health || !Object.keys(health).length) {
                els.v534AiHealth.textContent = 'AI health checks pending.';
                els.v534AiHealth.classList.remove('is-warning');
                return;
            }
            const safe = health.safe_for_live_policy !== false;
            const coverage = Math.round(Number(health.race_result_coverage || 0) * 100);
            const warnings = (health.warnings || []).slice(0, 2).join(' · ');
            els.v534AiHealth.classList.toggle('is-warning', !safe);
            els.v534AiHealth.textContent = `Health: ${safe ? 'safe' : 'unsafe'} · races ${health.race_rows_with_result || 0}/${health.race_rows || 0} results (${coverage}%) · items ${health.item_records_parsed || health.item_attempt_records || 0} · events ${health.event_records_parsed || health.event_records || 0}${warnings ? ' · ' + warnings : ''}`;
        }


        function renderAiDashboard(dashboard) {
            if (!dashboard || !dashboard.success) {
                if (els.v536AiConfidence) els.v536AiConfidence.textContent = 'WAITING';
                if (els.v536AiShadow) els.v536AiShadow.textContent = dashboard?.detail || 'Click Train Now after completed careers to build the dashboard.';
                return;
            }
            const records = dashboard.records || {};
            const health = dashboard.health || {};
            const live = dashboard.live_policy || {};
            if (els.v536AiConfidence) els.v536AiConfidence.textContent = String(dashboard.confidence || 'low').toUpperCase();
            if (els.v536AiCareers) els.v536AiCareers.textContent = formatNumber(records.career_summaries || 0);
            if (els.v536AiTurns) els.v536AiTurns.textContent = formatNumber(records.turn_decisions || 0);
            if (els.v536AiRaces) els.v536AiRaces.textContent = `${formatNumber(health.race_rows_with_result || 0)}/${formatNumber(health.race_rows || 0)}`;
            if (els.v536AiShadow) {
                const sh = dashboard.shadow_mode || {};
                els.v536AiShadow.innerHTML = `<div class="v536-ai-line">Evaluated ${escapeHtml(sh.evaluated_races || 0)} race hints · useful warnings ${escapeHtml(sh.useful_warnings || 0)} · false alarms ${escapeHtml(sh.false_alarms || 0)} · precision ${escapeHtml(Math.round(Number(sh.precision || 0) * 100))}%</div>`;
            }
            if (els.v536AiBacktest) {
                const bt = dashboard.backtest || {};
                els.v536AiBacktest.innerHTML = `<div class="v536-ai-line">Captured ${escapeHtml(Math.round(Number(bt.capture_rate || 0) * 100))}% of historical failed races · warnings ${escapeHtml(bt.risk_warnings || 0)} · late Senior races ${escapeHtml(bt.late_senior_races || 0)}</div>`;
            }
            if (els.v536AiRisk) {
                const risky = (dashboard.top_risky_races || []).slice(0, 5);
                const items = (dashboard.top_item_values || []).slice(0, 3);
                const events = (dashboard.top_event_values || []).slice(0, 3);
                els.v536AiRisk.innerHTML = [
                    risky.length ? `<div class="v536-ai-line"><strong>Risky races:</strong> ${risky.map(r => `${escapeHtml(r.name || ('program ' + r.program_id))} ${Math.round(Number(r.win_rate || 0) * 100)}%`).join(' · ')}</div>` : '<div class="v536-ai-line">No risky races with enough samples yet.</div>',
                    items.length ? `<div class="v536-ai-line"><strong>Item values:</strong> ${items.map(i => `${escapeHtml(i.name || 'item')} ${Number(i.adjustment || 0).toFixed(1)}`).join(' · ')}</div>` : '',
                    events.length ? `<div class="v536-ai-line"><strong>Event values:</strong> ${events.map(e => `${escapeHtml(e.event || 'event')} ${escapeHtml(e.choice || '')}`).join(' · ')}</div>` : ''
                ].filter(Boolean).join('');
            }
            if (els.v536AiSuggestions) {
                const suggestions = (dashboard.suggestions || []).slice(0, 6);
                els.v536AiSuggestions.innerHTML = suggestions.map(sug => `<div class="v536-ai-tip"><strong>${escapeHtml(sug.setting || 'setting')}</strong><span>${escapeHtml(sug.reason || '')}</span></div>`).join('') || '<div class="v536-ai-line">No strong config suggestions yet.</div>';
            }
            if (els.v536AiConfidenceDetail) {
                const epithets = (dashboard.epithet_confidence || []).slice(0, 4).map(pair => `${escapeHtml(pair[0])} ${Math.round(Number(pair[1]?.completion_rate || 0) * 100)}%`).join(' · ');
                const groups = (dashboard.preset_trainee_confidence || []).slice(0, 3).map(g => `${escapeHtml(g.key || 'profile')} fans ${formatCompactNumber(g.avg_final_fans || 0)} conf ${Math.round(Number(g.confidence || 0) * 100)}%`).join(' · ');
                const policyText = `Live policy ${live.enabled ? 'ON' : 'OFF'} · race ${live.race_adjustments || 0} / item ${live.item_adjustments || 0} / event ${live.event_adjustments || 0}`;
                els.v536AiConfidenceDetail.innerHTML = `<div class="v536-ai-line">${escapeHtml(policyText)}</div>${epithets ? `<div class="v536-ai-line"><strong>Epithets:</strong> ${epithets}</div>` : ''}${groups ? `<div class="v536-ai-line"><strong>Profiles:</strong> ${groups}</div>` : ''}`;
            }
            renderAiLivePolicy(state.lastAiStatus?.auto_training, dashboard);
            // Do not hydrate the Local LLM card from dashboard.local_llm; it may be stale.
            // refreshAiLearningStatus fetches /api/ai/local-llm/latest separately as the source of truth.

            if (dashboard.warnings && dashboard.warnings.length && els.v532AiAdvisor) {
                // Keep the deeper dashboard content visible without replacing a user-requested advisor report.
                if (!els.v532AiAdvisor.innerHTML.trim()) {
                    els.v532AiAdvisor.innerHTML = dashboard.warnings.slice(0, 4).map(w => `<div class="v532-ai-tip"><strong>WARNING</strong><span>${escapeHtml(w)}</span></div>`).join('');
                }
            }
        }


        function localLlmTextFromValue(value) {
            if (!value) return '';
            if (typeof value === 'string') return value;
            if (typeof value === 'number' || typeof value === 'boolean') return String(value);
            if (typeof value === 'object') {
                return value.summary || value.headline || value.pattern || value.rule || value.suggested_rule || value.description || value.risk || value.recommendation || value.action || JSON.stringify(value);
            }
            return '';
        }

        function localLlmListSummary(values, limit = 3) {
            if (!Array.isArray(values)) return '';
            return values.slice(0, limit).map(localLlmTextFromValue).filter(Boolean).join(' · ');
        }

        function renderLocalLlmAnalysisCard(label, analysis, fallback = 'Analysis saved.') {
            const data = analysis || {};
            const headline = data.summary || data.headline || data.overall_assessment || data.recommendation || fallback;
            const patterns = localLlmListSummary(data.key_patterns || data.patterns, 3);
            const risks = localLlmListSummary(data.risk_flags || data.risks || data.risk_notes, 3);
            const rules = localLlmListSummary(data.repeatable_rules || data.candidate_rules || data.suggested_rules || data.rules, 3);
            const parts = [headline];
            if (patterns) parts.push('Patterns: ' + patterns);
            if (risks) parts.push('Risks: ' + risks);
            if (rules) parts.push('Rules: ' + rules);
            if (data.raw_text && parts.length === 1) parts.push(String(data.raw_text).slice(0, 500));
            return `<div class="v532-ai-tip"><strong>${escapeHtml(label)}</strong><span>${escapeHtml(parts.filter(Boolean).join(' · '))}</span></div>`;
        }

        function renderLocalLlmStatus(payload, opts = {}) {
            const cfg = payload?.config || payload || {};
            const localControls = [
                els.v543LocalLlmEnabled,
                els.v543LocalLlmProvider,
                els.v543LocalLlmMode,
                els.v543LocalLlmBaseUrl,
                els.v543LocalLlmModel,
                els.v543LocalLlmApiKey
            ].filter(Boolean);
            const localFormFocused = localControls.includes(document.activeElement);
            const recentUserEdit = state.localLlmLastUserEditMs && (Date.now() - state.localLlmLastUserEditMs < 15000);
            const shouldApplyForm = Boolean(opts.forceForm) || (!state.localLlmFormDirty && !localFormFocused && !recentUserEdit);
            if (shouldApplyForm) {
                if (els.v543LocalLlmEnabled && typeof cfg.enabled !== 'undefined') els.v543LocalLlmEnabled.checked = Boolean(cfg.enabled);
                if (els.v543LocalLlmProvider && cfg.provider) els.v543LocalLlmProvider.value = cfg.provider;
                if (els.v543LocalLlmMode && cfg.mode) els.v543LocalLlmMode.value = cfg.mode;
                if (els.v543LocalLlmBaseUrl && cfg.base_url) els.v543LocalLlmBaseUrl.value = cfg.base_url;
                if (els.v543LocalLlmModel && typeof cfg.model !== 'undefined') els.v543LocalLlmModel.value = cfg.model || '';
            }
            if (els.v543LocalLlmStatus) {
                const status = payload?.status || {};
                const summary = payload?.latest_summary || {};
                const advice = payload?.latest_advice || {};
                const bits = [
                    `Mode ${(cfg.mode || 'offline').toUpperCase()}`,
                    cfg.enabled ? 'enabled' : 'disabled',
                    cfg.model ? `model ${cfg.model}` : 'model not set',
                    status.checked_at ? `test ${status.success ? 'OK' : 'failed'} ${status.checked_at}` : 'not tested',
                    summary.created_at ? `last analysis ${summary.created_at}` : '',
                    advice.created_at ? `last shadow ${advice.created_at}` : ''
                ].filter(Boolean);
                els.v543LocalLlmStatus.textContent = bits.join(' · ');
            }
            if (els.v543LocalLlmOutput && payload?.latest_summary?.analysis) {
                els.v543LocalLlmOutput.innerHTML = renderLocalLlmAnalysisCard('LOCAL LLM', payload.latest_summary.analysis || {}, 'Local LLM analysis saved.');
            }
        }

        function collectLocalLlmConfig() {
            const payload = {
                enabled: Boolean(els.v543LocalLlmEnabled?.checked),
                provider: els.v543LocalLlmProvider?.value || 'lmstudio',
                mode: els.v543LocalLlmMode?.value || 'offline',
                base_url: (els.v543LocalLlmBaseUrl?.value || '').trim() || 'http://localhost:1234/v1',
                model: (els.v543LocalLlmModel?.value || '').trim(),
                allow_live_override: false
            };
            const apiKey = (els.v543LocalLlmApiKey?.value || '').trim();
            // Blank means "keep the saved key" so routine refreshes/saves do not erase it.
            if (apiKey) payload.api_key = apiKey;
            return payload;
        }

        async function saveLocalLlmConfig() {
            if (!els.v543LocalLlmSaveBtn) return;
            els.v543LocalLlmSaveBtn.disabled = true;
            state.localLlmFormSaving = true;
            if (els.v543LocalLlmStatus) els.v543LocalLlmStatus.textContent = 'Saving Local LLM settings...';
            try {
                const data = await apiJson('/api/ai/local-llm/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(collectLocalLlmConfig())
                });
                const latest = await apiJson('/api/ai/local-llm/latest?t=' + Date.now()).catch(() => data);
                state.localLlmFormDirty = false;
                state.localLlmLastUserEditMs = 0;
                renderLocalLlmStatus(latest, { forceForm: true });
            } catch (e) {
                if (els.v543LocalLlmStatus) els.v543LocalLlmStatus.textContent = `Local LLM save failed: ${e.message || e}`;
            } finally {
                state.localLlmFormSaving = false;
                els.v543LocalLlmSaveBtn.disabled = false;
            }
        }

        async function testLocalLlm() {
            if (!els.v543LocalLlmTestBtn) return;
            els.v543LocalLlmTestBtn.disabled = true;
            if (els.v543LocalLlmStatus) els.v543LocalLlmStatus.textContent = 'Testing Local LLM connection...';
            try {
                await saveLocalLlmConfig();
                const data = await apiJson('/api/ai/local-llm/test', { method: 'POST' });
                if (els.v543LocalLlmStatus) els.v543LocalLlmStatus.textContent = data.success ? `Local LLM ready · ${data.elapsed_ms || 0}ms · ${data.model || 'model'}` : `Local LLM test failed: ${data.detail || 'unknown error'}`;
                const latest = await apiJson('/api/ai/local-llm/latest?t=' + Date.now()).catch(() => null);
                if (latest) renderLocalLlmStatus(latest, { forceForm: true });
            } catch (e) {
                if (els.v543LocalLlmStatus) els.v543LocalLlmStatus.textContent = `Local LLM test failed: ${e.message || e}`;
            } finally {
                els.v543LocalLlmTestBtn.disabled = false;
            }
        }

        async function analyzeLatestRunWithLocalLlm() {
            if (!els.v543LocalLlmAnalyzeBtn) return;
            els.v543LocalLlmAnalyzeBtn.disabled = true;
            if (els.v543LocalLlmStatus) els.v543LocalLlmStatus.textContent = 'Asking Local LLM to analyze the latest run...';
            try {
                await saveLocalLlmConfig();
                const data = await apiJson('/api/ai/local-llm/analyze-latest-run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ force: true }) });
                if (!data.success) throw new Error(data.detail || 'analysis failed');
                const analysis = data.analysis || {};
                if (els.v543LocalLlmOutput) els.v543LocalLlmOutput.innerHTML = renderLocalLlmAnalysisCard('LOCAL LLM ANALYSIS', analysis, 'Analysis saved.');
                if (els.v543LocalLlmStatus) els.v543LocalLlmStatus.textContent = `Local LLM analysis complete · ${data.elapsed_ms || 0}ms · turns sent ${data.turns_sent || 0}`;
                await refreshAiDashboard();
            } catch (e) {
                if (els.v543LocalLlmStatus) els.v543LocalLlmStatus.textContent = `Local LLM analysis failed: ${e.message || e}`;
            } finally {
                els.v543LocalLlmAnalyzeBtn.disabled = false;
            }
        }

        async function shadowReviewWithLocalLlm() {
            if (!els.v543LocalLlmShadowBtn) return;
            els.v543LocalLlmShadowBtn.disabled = true;
            if (els.v543LocalLlmStatus) els.v543LocalLlmStatus.textContent = 'Running Local LLM shadow review...';
            try {
                await saveLocalLlmConfig();
                const data = await apiJson('/api/ai/local-llm/shadow-advice', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ force: true, limit: 12 }) });
                if (!data.success) throw new Error(data.detail || 'shadow review failed');
                const advice = data.advice || {};
                if (els.v543LocalLlmOutput) els.v543LocalLlmOutput.innerHTML = renderLocalLlmAnalysisCard('LOCAL LLM SHADOW', advice, 'Shadow advice saved.');
                if (els.v543LocalLlmStatus) els.v543LocalLlmStatus.textContent = `Shadow review complete · ${data.elapsed_ms || 0}ms · turns sent ${data.turns_sent || 0}`;
                await refreshAiDashboard();
            } catch (e) {
                if (els.v543LocalLlmStatus) els.v543LocalLlmStatus.textContent = `Shadow review failed: ${e.message || e}`;
            } finally {
                els.v543LocalLlmShadowBtn.disabled = false;
            }
        }

        async function refreshAiDashboard() {
            try {
                const dash = await apiJson('/api/ai/dashboard?t=' + Date.now());
                state.lastAiDashboard = dash;
                renderAiDashboard(dash);
            } catch (e) {
                renderAiDashboard({ success: false, detail: 'AI dashboard unavailable: ' + (e.message || e) });
            }
        }

        function markLocalLlmFormDirty() {
            state.localLlmLastUserEditMs = Date.now();
            if (!state.localLlmFormSaving) state.localLlmFormDirty = true;
        }

        function bindLocalLlmFormDirtyTracking() {
            [
                els.v543LocalLlmEnabled,
                els.v543LocalLlmProvider,
                els.v543LocalLlmMode,
                els.v543LocalLlmBaseUrl,
                els.v543LocalLlmModel,
                els.v543LocalLlmApiKey
            ].filter(Boolean).forEach(node => {
                node.addEventListener('pointerdown', markLocalLlmFormDirty);
                node.addEventListener('focus', markLocalLlmFormDirty);
                node.addEventListener('keydown', markLocalLlmFormDirty);
                node.addEventListener('input', markLocalLlmFormDirty);
                node.addEventListener('change', markLocalLlmFormDirty);
            });
        }

        async function refreshAiLearningStatus() {
            try {
                const [data, auto, dashboard, localLlm] = await Promise.all([
                    apiJson('/api/ai/status?t=' + Date.now()),
                    apiJson('/api/ai/auto-training/status?t=' + Date.now()).catch(() => null),
                    apiJson('/api/ai/dashboard?t=' + Date.now()).catch(() => null),
                    apiJson('/api/ai/local-llm/latest?t=' + Date.now()).catch(() => null)
                ]);
                if (auto && auto.success) data.auto_training = auto;
                if (data && data.success) state.lastAiStatus = data;
                renderAiLearningStatus(state.lastAiStatus);
                if (dashboard) {
                    state.lastAiDashboard = dashboard;
                    renderAiDashboard(dashboard);
                }
                if (localLlm) renderLocalLlmStatus(localLlm);
            } catch (e) {
                if (els.v532AiStatus) els.v532AiStatus.textContent = 'AI dataset status unavailable.';
            }
        }

        async function rebuildAiDataset() {
            if (!els.v532AiRebuildBtn) return;
            els.v532AiRebuildBtn.disabled = true;
            if (els.v532AiStatus) els.v532AiStatus.textContent = 'Rebuilding AI dataset from career logs...';
            try {
                const data = await apiJson('/api/ai/rebuild-dataset', { method: 'POST' });
                state.lastAiStatus = data;
                renderAiLearningStatus(data);
                if (els.v532AiAdvisor) {
                    els.v532AiAdvisor.textContent = `Rebuild complete: ${data.processed || 0} logs processed, ${data.skipped || 0} skipped.`;
                }
            } catch (e) {
                if (els.v532AiStatus) els.v532AiStatus.textContent = `AI rebuild failed: ${e.message || e}`;
            } finally {
                els.v532AiRebuildBtn.disabled = false;
            }
        }

        async function showAiAdvisor() {
            if (!els.v532AiAdvisor) return;
            els.v532AiAdvisor.textContent = 'Loading advisor report...';
            try {
                const data = await apiJson('/api/ai/advisor/latest?t=' + Date.now());
                const tips = data.tips || [];
                els.v532AiAdvisor.innerHTML = tips.map(tip => {
                    const examples = (tip.examples || []).slice(0, 3).map(ex => ` program ${escapeHtml(ex.program_id)} win ${escapeHtml(Math.round(Number(ex.win_rate || 0) * 100))}%`).join('; ');
                    return `<div class="v532-ai-tip"><strong>${escapeHtml((tip.priority || 'info').toUpperCase())} · ${escapeHtml(tip.area || 'AI')}</strong><span>${escapeHtml(tip.message || '')}${examples ? ' · ' + examples : ''}</span></div>`;
                }).join('') || '<div class="v532-ai-tip">No advisor notes yet.</div>';
            } catch (e) {
                els.v532AiAdvisor.textContent = `Advisor unavailable: ${e.message || e}`;
            }
        }



        async function importPreviousAiLogs() {
            if (!els.v537AiImportBtn) return;
            const sourcePath = (els.v537AiImportPath?.value || '').trim();
            if (!sourcePath) {
                if (els.v537AiImportStatus) els.v537AiImportStatus.textContent = 'Paste a previous Icarus folder, uma_runtime folder, bot_logs folder, or .zip path first.';
                return;
            }
            els.v537AiImportBtn.disabled = true;
            if (els.v537AiImportStatus) els.v537AiImportStatus.textContent = 'Importing previous logs and presets, rebuilding dataset, and training advisor...';
            if (els.v532AiStatus) els.v532AiStatus.textContent = 'Importing previous logs and presets into the current build...';
            try {
                const data = await apiJson('/api/ai/import-logs', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ source_path: sourcePath, rebuild_dataset: true, train_after_import: true, import_presets: true })
                });
                if (!data.success) {
                    const detail = data.detail || 'Import failed.';
                    if (els.v537AiImportStatus) els.v537AiImportStatus.textContent = detail;
                    if (els.v532AiStatus) els.v532AiStatus.textContent = detail;
                    return;
                }
                const rebuild = data.rebuild || {};
                const training = data.training || {};
                const presets = data.presets || {};
                const message = `Imported ${data.imported_logs || 0} logs · presets ${presets.imported_presets || 0} · preset duplicates ${presets.duplicate_presets || 0} · duplicates ${data.duplicates || 0} · skipped ${data.skipped || 0} · rebuilt ${rebuild.processed || 0} logs · turns ${training.records?.turn_decisions || 0}`;
                if (els.v537AiImportStatus) els.v537AiImportStatus.textContent = message;
                if (els.v532AiAdvisor) {
                    els.v532AiAdvisor.textContent = `${message}. Previous logs and presets are now available in this build.`;
                }
                await refreshAiLearningStatus();
            } catch (e) {
                const message = `Import failed: ${e.message || e}`;
                if (els.v537AiImportStatus) els.v537AiImportStatus.textContent = message;
                if (els.v532AiStatus) els.v532AiStatus.textContent = message;
            } finally {
                els.v537AiImportBtn.disabled = false;
            }
        }

        async function trainAiNow() {
            if (!els.v533AiTrainNowBtn) return;
            els.v533AiTrainNowBtn.disabled = true;
            if (els.v532AiStatus) els.v532AiStatus.textContent = 'Training local AI advisor models...';
            try {
                const data = await apiJson('/api/ai/train-now', { method: 'POST' });
                if (els.v532AiAdvisor) {
                    els.v532AiAdvisor.textContent = `Training complete: ${data.records?.turn_decisions || 0} turn records · live policy ${data.live_policy_enabled ? 'enabled' : 'disabled'}.`;
                }
                await refreshAiLearningStatus();
            } catch (e) {
                if (els.v532AiStatus) els.v532AiStatus.textContent = `AI training failed: ${e.message || e}`;
            } finally {
                els.v533AiTrainNowBtn.disabled = false;
            }
        }

        async function showAiPostRunReport() {
            if (!els.v532AiAdvisor) return;
            els.v532AiAdvisor.textContent = 'Loading latest post-run report...';
            try {
                const data = await apiJson('/api/ai/post-run/latest?t=' + Date.now());
                if (!data.success) {
                    els.v532AiAdvisor.textContent = data.detail || 'No post-run report yet.';
                    return;
                }
                const risky = (data.top_risky_races || []).slice(0, 5).map(row => `program ${escapeHtml(row.program_id)} win ${escapeHtml(Math.round(Number(row.win_rate || 0) * 100))}%`).join('; ');
                const tuning = (data.suggested_config_tuning || []).slice(0, 5).map(row => `<div class="v532-ai-tip"><strong>${escapeHtml(row.setting || 'setting')}</strong><span>${escapeHtml(row.reason || '')}</span></div>`).join('');
                els.v532AiAdvisor.innerHTML = `<div class="v532-ai-tip"><strong>POST-RUN REPORT</strong><span>${escapeHtml(data.summary || 'Report generated.')}${risky ? ' · Risky: ' + risky : ''}</span></div>${tuning}`;
            } catch (e) {
                els.v532AiAdvisor.textContent = `Post-run report unavailable: ${e.message || e}`;
            }
        }

        async function saveStyleAdaptationMode() {
            if (!els.v542StyleAdaptationMode) return;
            const mode = els.v542StyleAdaptationMode.value || 'shadow';
            if (els.v542StyleAdaptationStatus) els.v542StyleAdaptationStatus.textContent = 'Saving style adaptation mode...';
            try {
                const data = await apiJson('/api/ai/auto-training/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ style_adaptation_mode: mode })
                });
                renderStyleAdaptation({}, { auto_config: data.config || {} });
                await refreshAiLearningStatus();
            } catch (e) {
                if (els.v542StyleAdaptationStatus) els.v542StyleAdaptationStatus.textContent = `Style mode save failed: ${e.message || e}`;
            }
        }

        async function toggleAiAutoTraining() {
            if (!els.v533AiAutoToggle) return;
            const enabled = Boolean(els.v533AiAutoToggle.checked);
            try {
                const data = await apiJson('/api/ai/auto-training/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ enabled })
                });
                renderAiAutoStatus({ auto_config: data.config || {} });
            } catch (e) {
                els.v533AiAutoToggle.checked = !enabled;
                if (els.v533AiAutoStatus) els.v533AiAutoStatus.textContent = `Auto-training update failed: ${e.message || e}`;
            }
        }


        async function toggleAiLivePolicyAssistance() {
            if (!els.v539AiLivePolicyToggle) return;
            const enabled = Boolean(els.v539AiLivePolicyToggle.checked);
            const previous = !enabled;
            if (els.v539AiLivePolicyRecommendation) {
                els.v539AiLivePolicyRecommendation.textContent = `${enabled ? 'Enabling' : 'Disabling'} Live Policy Assistance...`;
            }
            try {
                const data = await apiJson('/api/ai/auto-training/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ enable_live_policy_assistance: enabled })
                });
                const auto = { auto_config: data.config || {} };
                renderAiLivePolicy(auto, state.lastAiDashboard);
                await refreshAiLearningStatus();
            } catch (e) {
                els.v539AiLivePolicyToggle.checked = previous;
                if (els.v539AiLivePolicyRecommendation) {
                    els.v539AiLivePolicyRecommendation.textContent = `Live Policy update failed: ${e.message || e}`;
                    els.v539AiLivePolicyRecommendation.classList.add('is-disable');
                }
            }
        }

        function downloadSafeAiBundle() {
            window.location.href = '/api/ai/safe-debug-bundle';
        }

        async function runStuckCareerRescue() {
            if (!els.v525RescueBtn) return;
            const status = els.v525RescueStatus;
            els.v525RescueBtn.disabled = true;
            if (status) status.textContent = 'Running rescue probes...';
            try {
                const data = await apiJson('/api/career/rescue', { method: 'POST' });
                const detail = data.detail || (data.success ? 'rescue completed' : 'rescue failed');
                if (status) status.textContent = detail;
                if (data.success) {
                    await syncSession();
                    refreshV4Status();
                }
            } catch (e) {
                if (status) status.textContent = `Rescue failed: ${e.message || e}`;
            } finally {
                els.v525RescueBtn.disabled = false;
            }
        }

        function renderV4PanelsFromData({ health = state.lastHealth, diagnostics = state.lastDiagnostics, runner = state.runner } = {}) {
            renderV53Cockpit({ runner });
            if (health && els.v4Health) {
                const status = health.logged_in ? 'Logged in' : 'Waiting for login';
                els.v4Health.innerHTML = kvRows([
                    ['Profile', health.profile || 'default'],
                    ['Port', health.port || '?'],
                    ['Status', status],
                    ['Runner', health.runner_running ? 'Running' : 'Idle'],
                    ['Recoveries', health.recoveries || 0],
                    ['Stale', `${Math.round(Number(health.runner_stale_seconds || 0))}s`]
                ]);
            }
            const career = state.account && state.account.career;
            if (els.v4Analytics) {
                const runSeconds = runner && runner.started_at ? Math.max(0, Date.now()/1000 - Number(runner.started_at || 0)) : 0;
                const fans = Number((career && career.fans) || (runner && runner.fans) || 0);
                const fansPerHour = runSeconds > 30 ? fans / (runSeconds / 3600) : 0;
                els.v4Analytics.innerHTML = kvRows([
                    ['Turn', (runner && runner.turn) || (career && career.turn) || '?'],
                    ['Fans', formatCompactNumber(fans)],
                    ['Fans/hr', fansPerHour ? formatCompactNumber(fansPerHour) : 'warming up'],
                    ['Steps', (runner && runner.steps) || 0],
                    ['Runtime', runSeconds ? formatDurationSeconds(runSeconds) : '0s'],
                    ['Last action', (runner && runner.last_action) || 'idle']
                ]);
            }
            if (diagnostics && els.v4Diagnostics) {
                const snap = diagnostics.snapshot || {};
                const summary = snap.summary || {};
                els.v4Diagnostics.innerHTML = kvRows([
                    ['Python', diagnostics.python || '?'],
                    ['Snapshots', snap.rows || 0],
                    ['Window turns', summary.unique_turns_in_window || 0],
                    ['Fan delta', formatCompactNumber(summary.fan_delta_in_window || 0)],
                    ['Latest report', diagnostics.latest_report ? 'yes' : 'none'],
                    ['Settings', diagnostics.settings_exists ? 'found' : 'missing'],
                    ['AI turns', state.lastAiStatus?.files?.turn_decisions?.rows ?? 0],
                    ['AI careers', state.lastAiStatus?.files?.career_summaries?.rows ?? 0]
                ]);
            }
        }

        async function refreshV4Status() {
            try {
                const [health, diagnostics, aiStatus] = await Promise.all([
                    apiJson('/api/health?t=' + Date.now()).catch(() => null),
                    apiJson('/api/diagnostics/summary?t=' + Date.now()).catch(() => null),
                    apiJson('/api/ai/status?t=' + Date.now()).catch(() => null)
                ]);
                if (health && health.success) state.lastHealth = health;
                if (diagnostics && diagnostics.success) state.lastDiagnostics = diagnostics;
                if (aiStatus && aiStatus.success) state.lastAiStatus = aiStatus;
                renderAiLearningStatus(state.lastAiStatus);
                renderV4PanelsFromData({ health: state.lastHealth, diagnostics: state.lastDiagnostics, runner: state.runner });
            } catch (e) {}
        }
        async function refreshDecisionTrace() {
            try {
                const data = await apiJson('/api/career/decision-trace/latest?limit=160&t=' + Date.now());
                if (!data.success || !data.rows || !data.rows.length) {
                    state.decisionTraceRows = [];
                    const trace = state.runner && state.runner.decision_trace;
                    if (els.v5DecisionTrace) {
                        if (trace && trace.action) {
                            els.v5DecisionTrace.innerHTML = `<div class="v4-timeline-row"><span>T${escapeHtml(trace.turn ?? '?')}</span><strong>${escapeHtml(trace.action)}</strong><em>${escapeHtml(trace.reason || '')}</em></div>`;
                        } else {
                            els.v5DecisionTrace.innerHTML = 'No decisions traced yet.';
                        }
                    }
                    renderDecisionReasoning(getMainActionRows(state.runner));
                    return;
                }
                state.decisionTraceRows = data.rows || [];
                renderDecisionReasoning(getMainActionRows(state.runner));
                if (!els.v5DecisionTrace) return;
                els.v5DecisionTrace.innerHTML = data.rows.slice(-6).map(row => {
                    const best = (row.training_candidates || [])[0];
                    const bestText = best ? ` · best ${best.name} ${best.score}` : '';
                    return `<div class="v4-timeline-row"><span>T${escapeHtml(row.turn ?? '?')}</span><strong>${escapeHtml(row.action || 'decision')}</strong><em>${escapeHtml((row.reason || '') + bestText)}</em></div>`;
                }).join('');
            } catch (e) {}
        }
        async function refreshSnapshotTimeline() {
            if (!els.v4SnapshotTimeline) return;
            try {
                const data = await apiJson('/api/career/snapshots/latest?limit=12&t=' + Date.now());
                if (!data.success || !data.rows || !data.rows.length) {
                    els.v4SnapshotTimeline.innerHTML = 'No snapshots yet.';
                    return;
                }
                state.lastSnapshots = data.rows || [];
                renderV53Cockpit({ runner: state.runner, snapshots: state.lastSnapshots });
                els.v4SnapshotTimeline.innerHTML = data.rows.slice(-8).map(row => {
                    const turn = row.turn ?? '?';
                    const fans = formatCompactNumber(row.fans || 0);
                    const vital = row.vital ?? row.hp ?? '?';
                    const action = row.last_action || row.action || row.command || 'snapshot';
                    return `<div class="v4-timeline-row"><span>T${escapeHtml(turn)}</span><strong>${escapeHtml(action)}</strong><em>HP ${escapeHtml(vital)} · ${escapeHtml(fans)} fans</em></div>`;
                }).join('');
            } catch (e) {}
        }
        function renderSolverBackendStatus(data) {
            if (!els.v53SolverBackendStatus) return;
            if (!data || !data.success) {
                els.v53SolverBackendStatus.className = 'solver-backend-status unknown';
                els.v53SolverBackendStatus.textContent = 'Solver backend: unavailable';
                return;
            }
            const backend = String(data.active_backend || '').toLowerCase();
            const label = data.active_backend_label || (backend === 'milp' ? 'MILP' : backend === 'beam' ? 'Beam' : 'Unknown');
            const detail = backend === 'milp'
                ? 'SciPy MILP active · Beam fallback ready'
                : data.milp_available
                    ? 'Beam selected manually'
                    : 'Beam active · SciPy MILP unavailable';
            els.v53SolverBackendStatus.className = `solver-backend-status ${backend === 'milp' ? 'milp' : backend === 'beam' ? 'beam' : 'unknown'}`;
            els.v53SolverBackendStatus.innerHTML = `<span>Solver backend</span><strong>${escapeHtml(label)}</strong><em>${escapeHtml(detail)}</em>`;
        }

        async function refreshTrackblazerStatus() {
            if (!els.v4TrackblazerStatus && !els.v53SolverBackendStatus) return;
            try {
                const data = await apiJson('/api/trackblazer/solver/status?t=' + Date.now());
                if (!data.success) throw new Error(data.detail || 'status failed');
                renderSolverBackendStatus(data);
                const cached = data.cached_data || {};
                if (els.v4TrackblazerStatus) {
                    els.v4TrackblazerStatus.innerHTML = kvRows([
                        ['Smart backend', data.active_backend_label || '?'],
                        ['MILP available', data.milp_available ? 'yes' : 'no'],
                        ['Beam fallback', data.beam_available ? 'ready' : 'missing'],
                        ['Races cache', cached.races || 0],
                        ['Epithets cache', cached.epithets || 0],
                        ['Source', 'race.daftuyda data']
                    ]);
                }
            } catch (e) {
                renderSolverBackendStatus({ success: false });
                if (els.v4TrackblazerStatus) {
                    els.v4TrackblazerStatus.innerHTML = `<div class="v4-error">${escapeHtml(e.message || 'Trackblazer unavailable')}</div>`;
                }
            }
        }
        function setRacePlannerMode(mode, { persist = true, render = true } = {}) {
            const next = mode === 'manual' ? 'manual' : 'smart';
            state.racePlannerMode = next;
            if (persist) localStorage.setItem('sweepy_race_planner_mode', next);
            if (els.v47SmartModeBtn) els.v47SmartModeBtn.classList.toggle('active', next === 'smart');
            if (els.v47ManualModeBtn) els.v47ManualModeBtn.classList.toggle('active', next === 'manual');
            document.querySelectorAll('.v47-smart-controls').forEach(el => el.style.display = next === 'smart' ? '' : 'none');
            document.querySelectorAll('.v47-manual-controls').forEach(el => el.style.display = next === 'manual' ? '' : 'none');
            state.manualRaceSelectionActive = next === 'manual' || Boolean((state.selectedRaces || []).length && !state.trackblazerPlan);
            if (els.v4TrackblazerPlan) {
                if (next === 'manual') {
                    els.v4TrackblazerPlan.innerHTML = '<div class="v4-warn">Manual Selection mode. Pick races from the calendar, then click Apply Manual.</div>';
                } else if (!state.trackblazerPlan) {
                    els.v4TrackblazerPlan.innerHTML = 'Smart Race Solver idle. Select a trainee, tune options, then click Solve Smart.';
                }
            }
            if (els.v4ApplyPlanBtn) els.v4ApplyPlanBtn.disabled = next !== 'smart' || !(state.trackblazerPlan && state.trackblazerPlan.extra_race_list && state.trackblazerPlan.extra_race_list.length);
            if (els.v47ApplyManualBtn) els.v47ApplyManualBtn.disabled = next !== 'manual' || !(state.selectedRaces || []).length;
            if (render) renderRaces();
            syncStartButton();
        }

        async function applyManualRaceSelection() {
            setRacePlannerMode('manual', { persist: true, render: false });
            state.trackblazerPlan = null;
            state.manualRaceSelectionActive = true;
            await autoSaveRaces({ force: true });
            if (els.v4TrackblazerPlan) {
                els.v4TrackblazerPlan.innerHTML = `<div class="v4-ok">Applied ${escapeHtml((state.selectedRaces || []).length)} manual races to preset ${escapeHtml(state.selectedPreset || 'current')}.</div>`;
            }
            renderRaces();
            syncStartButton();
        }

        function getTrackblazerOptions() {
            const { traineeName, traineeId, skillProfile, strategy } = selectedTraineeForPlanner();
            const current = currentSmartSolverConfig();
            const s = solverSettings(current);
            const weights = { ...solverWeights(current) };
            weights.allowSummerRacing = Boolean(s.allow_summer_racing);
            const aptitudes = effectiveSolverAptitudes(current);
            const profileDistances = (skillProfile && skillProfile.primary_distances) || (strategy && strategy.primary_distances) || [];
            const presetDistances = current && Array.isArray(current.preferred_distances) ? current.preferred_distances : [];
            const primaryDistances = [...new Set([...(presetDistances || []), ...(profileDistances || [])].filter(Boolean))];
            return {
                aptitudes,
                trainee_name: traineeName,
                trainee_id: traineeId,
                running_style: (skillProfile && (skillProfile.recommended_style || skillProfile.running_style)) || (strategy && strategy.running_style) || '',
                primary_distances: primaryDistances,
                distance_preference_mode: s.distance_preference_mode || 'balanced',
                fan_bonus: Number(s.fan_bonus || 0),
                max_races_in_row: Number(s.max_races_in_row || 2),
                replan_on_events_only: Boolean(s.replan_on_events_only !== false),
                disable_schedule_replan_on_race_loss: Boolean(s.disable_schedule_replan_on_race_loss),
                include_op: Boolean(s.include_op),
                min_aptitude_floor: aptitudeRank(s.min_aptitude_floor || 'C'),
                solver: 'smart',
                weights,
                target_epithets: current.trackblazer_target_epithets || [],
                forced_epithets: current.trackblazer_forced_epithets || [],
                training_blocks: current.training_blocks || [],
                manual_locks: current.manual_locks || {},
                timeout: 30
            };
        }
        function resetTrackblazerPlan({ clearRaces = false, render = true } = {}) {
            state.trackblazerPlan = null;
            if (clearRaces) state.selectedRaces = [];
            state.manualRaceSelectionActive = Boolean((state.selectedRaces || []).length);
            if (els.v4TrackblazerPlan) {
                els.v4TrackblazerPlan.innerHTML = state.manualRaceSelectionActive
                    ? '<div class="v4-warn">Smart solver reset. Manual Selection is active.</div>'
                    : 'No smart plan generated. Use Smart Race Solver or switch to Manual Selection.';
            }
            if (els.v4ApplyPlanBtn) els.v4ApplyPlanBtn.disabled = true;
            if (els.v4ResetPlanBtn) els.v4ResetPlanBtn.disabled = !state.manualRaceSelectionActive;
            if (render) renderRaces();
            syncStartButton();
        }

        function currentRacePlanStateLabel() {
            if (state.racePlannerMode === 'manual') return (state.selectedRaces || []).length ? 'Manual Selection active' : 'Manual Selection waiting for picks';
            if (state.trackblazerPlan && state.trackblazerPlan.extra_race_list && state.trackblazerPlan.extra_race_list.length) return 'Smart Race Solver plan active';
            if ((state.selectedRaces || []).length) return 'Manual race selection active';
            return 'No race plan selected';
        }


        function renderTrackblazerPlanDiff(previous, next) {
            if (!previous || !next) return '';
            const prevIds = new Set((previous.extra_race_list || []).map(String));
            const nextIds = new Set((next.extra_race_list || []).map(String));
            const added = [...nextIds].filter(id => !prevIds.has(id)).length;
            const removed = [...prevIds].filter(id => !nextIds.has(id)).length;
            const fanDelta = Number(next.estimated_fans || 0) - Number(previous.estimated_fans || 0);
            const scoreDelta = Number(next.objective_score || 0) - Number(previous.objective_score || 0);
            if (!added && !removed && !fanDelta && !scoreDelta) return '';
            const fanText = `${fanDelta >= 0 ? '+' : ''}${formatCompactNumber(fanDelta)}`;
            const scoreText = `${scoreDelta >= 0 ? '+' : ''}${Number(scoreDelta).toFixed(3)}`;
            return `<div class="v4-plan-diff">Route diff: +${escapeHtml(added)} races / -${escapeHtml(removed)} races · fan delta ${escapeHtml(fanText)} · score delta ${escapeHtml(scoreText)}</div>`;
        }
        function renderTrackblazerPlan(plan) {
            if (!els.v4TrackblazerPlan) return;
            if (!plan) {
                els.v4TrackblazerPlan.innerHTML = state.manualRaceSelectionActive
                    ? '<div class="v4-warn">Manual Selection is active. Click Apply Manual to confirm, or switch to Smart Race Solver.</div>'
                    : 'No smart plan generated. Use Smart Race Solver or switch to Manual Selection.';
                if (els.v4ApplyPlanBtn) els.v4ApplyPlanBtn.disabled = true;
                if (els.v4ResetPlanBtn) els.v4ResetPlanBtn.disabled = !state.manualRaceSelectionActive;
                syncStartButton();
                return;
            }
            const schedule = plan.schedule || [];
            const preview = schedule.slice(0, 10).map(r => {
                const why = [`score ${r.score ?? ''}`, `apt ${r.aptitude_weight ?? ''}`, (r.target_epithet_hits || []).length ? `targets ${(r.target_epithet_hits || []).join(', ')}` : '', (r.forced_epithet_hits || []).length ? `forced ${(r.forced_epithet_hits || []).join(', ')}` : ''].filter(Boolean).join(' · ');
                return `<div class="v4-plan-row" title="${escapeAttr(why)}"><span>T${escapeHtml(r.turn || '?')}</span><strong>${escapeHtml(r.name || r.program_id)}</strong><em>${escapeHtml(r.grade || '')} · ${escapeHtml(r.distance || '')} · ${formatCompactNumber(r.est_fans || r.fans || 0)}</em></div>`;
            }).join('');
            const diffHtml = renderTrackblazerPlanDiff(state.previousTrackblazerPlan, plan);
            const aptitudeText = plan.aptitudes_used ? Object.entries(plan.aptitudes_used).map(([k, v]) => `${k}:${v}`).join(' ') : '';
            const prefText = (plan.preferred_distances || []).length ? `Distance mode: ${plan.distance_preference_mode || 'balanced'} · preferred ${(plan.preferred_distances || []).join(', ')}` : '';
            const epithetText = (plan.projected_epithets || []).length ? `Projected epithets: ${(plan.projected_epithets || []).slice(0, 8).join(', ')}${(plan.projected_epithets || []).length > 8 ? '…' : ''}` : '';
            const ledgerText = (plan.epithet_ledger || []).length ? `Epithet ledger: ${(plan.epithet_ledger || []).filter(e => e.status && e.status !== 'untouched').slice(0, 6).map(e => `${e.name}:${e.status}`).join(', ')}` : '';
            const riskNoteText = (plan.notes || []).length ? (plan.notes || []).slice(0, 3).join(' · ') : '';
            const profile = state.selectedTraineeProfile || {};
            const profileLine = plan.trainee_name || profile.name ? `Trainee: ${plan.trainee_name || profile.name}${profile.profile_source ? ` · ${profile.profile_source}` : ''}` : '';
            els.v4TrackblazerPlan.innerHTML = `
                <div class="v4-plan-summary">${escapeHtml(plan.solver || 'Smart Race Solver')} picked <strong>${escapeHtml(plan.race_count || schedule.length || 0)}</strong> races, est. <strong>${escapeHtml(formatCompactNumber(plan.estimated_fans || 0))}</strong> fans${plan.objective_score ? ` · score ${escapeHtml(plan.objective_score)}` : ''}${plan.fallback_used ? ' <span class="v4-warn">fallback</span>' : ''}</div>
                ${profileLine ? `<div class="v4-plan-aptitudes">${escapeHtml(profileLine)}</div>` : ''}
                ${aptitudeText ? `<div class="v4-plan-aptitudes">Aptitudes: ${escapeHtml(aptitudeText)}</div>` : ''}
                ${prefText ? `<div class="v4-plan-aptitudes">${escapeHtml(prefText)}</div>` : ''}
                ${epithetText ? `<div class="v4-plan-aptitudes">${escapeHtml(epithetText)}</div>` : ''}
                ${ledgerText ? `<div class="v4-plan-aptitudes">${escapeHtml(ledgerText)}</div>` : ''}
                ${riskNoteText ? `<div class="v4-plan-aptitudes v4-plan-notes">${escapeHtml(riskNoteText)}</div>` : ''}
                ${diffHtml}
                ${preview || '<div>No race rows returned.</div>'}
            `;
            if (els.v4ApplyPlanBtn) els.v4ApplyPlanBtn.disabled = !(plan.extra_race_list && plan.extra_race_list.length);
            if (els.v4ResetPlanBtn) els.v4ResetPlanBtn.disabled = false;
            syncStartButton();
        }
        async function generateTrackblazerPlan({ apply = false } = {}) {
            if (!hasTrackblazerTraineeSelected()) {
                if (els.v4TrackblazerPlan) els.v4TrackblazerPlan.innerHTML = '<div class="v4-error">Select a trainee before generating a Trackblazer plan.</div>';
                updateTrackblazerPlanGate();
                return null;
            }
            if (els.v4PlanBtn) els.v4PlanBtn.disabled = true;
            if (els.v4TrackblazerPlan) els.v4TrackblazerPlan.innerHTML = 'Loading trainee profile...';
            try {
                await loadSelectedTraineeProfile({ force: true });
                if (els.v4TrackblazerPlan) els.v4TrackblazerPlan.innerHTML = 'Solving trainee-specific route...';
                const plan = await apiJson('/api/trackblazer/plan', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(getTrackblazerOptions())
                });
                if (!plan.success) throw new Error(plan.detail || 'planning failed');
                state.previousTrackblazerPlan = state.trackblazerPlan;
                state.trackblazerPlan = plan;
                state.manualRaceSelectionActive = false;
                renderTrackblazerPlan(plan);
                if (apply) await applyTrackblazerPlan();
                return plan;
            } catch (e) {
                if (els.v4TrackblazerPlan) els.v4TrackblazerPlan.innerHTML = `<div class="v4-error">${escapeHtml(e.message || 'Planner failed')}</div>`;
                throw e;
            } finally {
                if (els.v4PlanBtn) els.v4PlanBtn.disabled = !hasTrackblazerTraineeSelected();
            }
        }
        async function applyTrackblazerPlan() {
            const plan = state.trackblazerPlan;
            if (!plan || ((!plan.extra_race_list || !plan.extra_race_list.length) && (!plan.schedule || !plan.schedule.length))) return;
            const resolved = resolveTrackblazerPlanRaceIds(plan);
            state.selectedRaces = resolved.ids;
            state.racePlannerMode = 'smart';
            localStorage.setItem('sweepy_race_planner_mode', 'smart');
            state.manualRaceSelectionActive = false;
            const current = currentSmartSolverConfig();
            if (current) {
                current.extra_race_list = [...state.selectedRaces];
                current.trackblazer_last_plan = {
                    race_count: plan.race_count || state.selectedRaces.length,
                    estimated_fans: plan.estimated_fans || 0,
                    solver: plan.solver || '',
                    decisions: plan.decisions || {},
                    schedule: plan.schedule || [],
                    applied_at: Date.now(),
                    unresolved_count: resolved.misses.length
                };
                await saveSmartSolverConfig();
            }
            renderRaces();
            await autoSaveRaces();
            if (els.v4TrackblazerPlan) {
                const count = state.selectedRaces.length;
                const missText = resolved.misses.length ? ` <span class="v4-warn">${escapeHtml(resolved.misses.length)} unmatched</span>` : '';
                const statusClass = count ? 'v4-ok' : 'v4-error';
                const hint = count ? '' : ' Check local race data mapping.';
                els.v4TrackblazerPlan.insertAdjacentHTML('afterbegin', `<div class="${statusClass}">Applied ${escapeHtml(count)} matched races to preset ${escapeHtml(state.selectedPreset || 'current')}.${missText}${hint}</div>`);
            }
        }
        function normalizeAccountRows() {
            const rows = [];
            els.v525AccountsList?.querySelectorAll('.v525-account-row').forEach((row, idx) => {
                const name = row.querySelector('[data-field="name"]')?.value || `account${idx + 1}`;
                const port = Number(row.querySelector('[data-field="port"]')?.value || (1616 + idx));
                const autoRestart = row.querySelector('[data-field="auto_restart"]')?.checked ?? true;
                const stale = Number(row.querySelector('[data-field="stale_restart_seconds"]')?.value || 900);
                rows.push({ name, port, auto_restart: autoRestart, stale_restart_seconds: stale });
            });
            return rows;
        }
        function renderAccounts(accounts = state.accounts || []) {
            if (!els.v525AccountsList) return;
            if (!accounts.length) {
                els.v525AccountsList.innerHTML = '<div class="v525-account-empty">No accounts yet. Add one to begin.</div>';
                return;
            }
            els.v525AccountsList.innerHTML = accounts.map((account, idx) => {
                const health = account.health || {};
                const reachable = Boolean(health.reachable || health.process_running);
                const running = Boolean(health.runner_running);
                const waiting = Boolean(health.waiting_for_server);
                const logged = Boolean(health.logged_in);
                const hstate = health.state || (running ? 'running' : (logged ? 'logged-in' : (reachable ? 'booting' : 'offline')));
                const port = account.port || 1616 + idx;
                const healthAge = health.manager_last_health_age;
                const staleText = Number.isFinite(Number(healthAge)) ? ` · ${healthAge}s ago` : '';
                const statusClass = !reachable ? 'is-offline' : (waiting ? 'is-waiting' : (running ? 'is-running' : 'is-online'));
                const primary = !reachable ? 'OFFLINE' : (waiting ? 'WAITING' : (running ? 'RUNNING' : String(hstate).toUpperCase()));
                const secondary = !reachable
                    ? `unreachable · ${escapeHtml(health.detail || health.manager_error || 'waiting for health')}`
                    : (waiting
                        ? `server unavailable — riding it out${staleText}`
                        : `${logged ? 'logged in' : 'booted'} · ${running ? 'career running' : hstate}${staleText}`);
                const careerBits = [];
                if (reachable && (running || health.career_active)) {
                    if (health.turn != null) careerBits.push(`T${health.turn}`);
                    if (health.fans) careerBits.push(`${formatNumber(health.fans)} fans`);
                    if (health.fans_per_hour) careerBits.push(`${formatNumber(health.fans_per_hour)}/hr`);
                    if (health.vital != null && health.max_vital != null) careerBits.push(`HP ${health.vital}/${health.max_vital}`);
                    if (health.motivation != null) careerBits.push(`mood ${health.motivation}`);
                    if (health.loop_target) careerBits.push(`run ${health.loop_index || 0}/${health.loop_target}`);
                }
                const metricsLine = careerBits.length ? `<span class="v525-account-metrics">${escapeHtml(careerBits.join('  ·  '))}</span>` : '';
                return `<div class="v525-account-row" data-index="${idx}">
                    <div class="v525-account-status ${statusClass}"></div>
                    <label>Name<input data-field="name" value="${escapeAttr(account.name || `account${idx+1}`)}"></label>
                    <label>Port<input data-field="port" type="number" min="1000" max="65535" value="${escapeAttr(port)}"></label>
                    <label>Restart<input data-field="auto_restart" type="checkbox" ${account.auto_restart !== false ? 'checked' : ''}></label>
                    <label>Stale Sec<input data-field="stale_restart_seconds" type="number" min="60" step="60" value="${escapeAttr(account.stale_restart_seconds || 900)}"></label>
                    <div class="v525-account-health">
                        <strong>${escapeHtml(primary)}</strong>
                        <span>${secondary}</span>
                        ${metricsLine}
                        <em>${escapeHtml(health.runner_last_error || health.manager_error || '')}</em>
                    </div>
                    <button class="btn btn-sm v525-open-dashboard" type="button" data-port="${escapeAttr(port)}">OPEN</button>
                    <button class="btn btn-sm btn-danger-soft v525-remove-account" type="button">REMOVE</button>
                </div>`;
            }).join('');
            els.v525AccountsList.querySelectorAll('.v525-open-dashboard').forEach(btn => {
                btn.addEventListener('click', () => window.open(`http://127.0.0.1:${btn.dataset.port}`, '_blank'));
            });
            els.v525AccountsList.querySelectorAll('.v525-remove-account').forEach(btn => {
                btn.addEventListener('click', () => {
                    const row = btn.closest('.v525-account-row');
                    row?.remove();
                    state.accounts = normalizeAccountRows();
                });
            });
        }
        async function loadAccountsStatus() {
            if (!els.v525AccountsStatus) return;
            els.v525AccountsStatus.textContent = 'Refreshing account status...';
            try {
                const data = await apiJson('/api/accounts/status?t=' + Date.now());
                if (!data.success) throw new Error(data.detail || 'Account status failed');
                state.accounts = data.accounts || [];
                renderAccounts(state.accounts);
                const online = state.accounts.filter(a => a.health && (a.health.reachable || a.health.process_running)).length;
                const running = state.accounts.filter(a => a.health && a.health.runner_running).length;
                els.v525AccountsStatus.textContent = `${online}/${state.accounts.length} accounts online · ${running} running`;
            } catch (e) {
                els.v525AccountsStatus.textContent = e.message || 'Unable to load accounts.';
            }
        }
        async function saveAccounts() {
            if (!els.v525AccountsStatus) return;
            const accounts = normalizeAccountRows();
            els.v525AccountsStatus.textContent = 'Saving accounts.json...';
            try {
                const data = await apiJson('/api/accounts', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ accounts })
                });
                if (!data.success) throw new Error(data.detail || 'Save failed');
                state.accounts = data.accounts || accounts;
                renderAccounts(state.accounts);
                els.v525AccountsStatus.textContent = `Saved ${state.accounts.length} accounts.`;
                return true;
            } catch (e) {
                els.v525AccountsStatus.textContent = e.message || 'Unable to save accounts.';
                return false;
            }
        }
        async function launchAccountManager() {
            if (!els.v525AccountsStatus) return;
            const saved = await saveAccounts();
            if (saved === false) return;
            els.v525AccountsStatus.textContent = 'Launching manager.py...';
            try {
                const data = await apiJson('/api/accounts/manager/start', { method: 'POST' });
                if (!data.success) throw new Error(data.detail || 'Launch failed');
                els.v525AccountsStatus.textContent = data.already_running ? `Manager already running (PID ${data.pid}).` : `Manager launched (PID ${data.pid}).`;
                setTimeout(loadAccountsStatus, 1500);
            } catch (e) {
                els.v525AccountsStatus.textContent = e.message || 'Unable to launch manager.';
            }
        }
        function addAccountRow() {
            const accounts = normalizeAccountRows();
            const nextPort = accounts.reduce((max, a) => Math.max(max, Number(a.port || 1615)), 1615) + 1;
            accounts.push({ name: `account${accounts.length + 1}`, port: nextPort, auto_restart: true, stale_restart_seconds: 900 });
            state.accounts = accounts;
            renderAccounts(accounts);
        }
        function bindAccountsControls() {
            if (!els.v525AccountsBtn || els.v525AccountsBtn.dataset.bound) return;
            els.v525AccountsBtn.addEventListener('click', () => {
                if (els.v525AccountsModal) els.v525AccountsModal.style.display = 'flex';
                loadAccountsStatus();
            });
            els.v525AccountsDoneBtn?.addEventListener('click', () => { if (els.v525AccountsModal) els.v525AccountsModal.style.display = 'none'; });
            els.v525AccountsModal?.addEventListener('click', event => { if (event.target === els.v525AccountsModal) els.v525AccountsModal.style.display = 'none'; });
            els.v525AddAccountBtn?.addEventListener('click', addAccountRow);
            els.v525SaveAccountsBtn?.addEventListener('click', saveAccounts);
            els.v525RefreshAccountsBtn?.addEventListener('click', loadAccountsStatus);
            els.v525LaunchManagerBtn?.addEventListener('click', launchAccountManager);
            els.v525AccountsBtn.dataset.bound = '1';
        }
        function bindV4Controls() {
            bindAccountsControls();
            bindBotSettingsControls();
            if (els.v4AutoPlan) {
                els.v4AutoPlan.checked = localStorage.getItem(v4AutoPlanStorageKey) === 'true';
                state.autoPlanBeforeRun = els.v4AutoPlan.checked;
                els.v4AutoPlan.addEventListener('change', () => {
                    state.autoPlanBeforeRun = els.v4AutoPlan.checked;
                    localStorage.setItem(v4AutoPlanStorageKey, String(state.autoPlanBeforeRun));
                });
            }
            els.v4SyncTrackblazerBtn?.addEventListener('click', async () => {
                els.v4TrackblazerStatus.innerHTML = 'Syncing Trackblazer data...';
                try {
                    await apiJson('/api/trackblazer/sync?force=true', { method: 'POST' });
                    await refreshTrackblazerStatus();
                } catch (e) {
                    els.v4TrackblazerStatus.innerHTML = `<div class="v4-error">${escapeHtml(e.message || 'Sync failed')}</div>`;
                }
            });
            // v2.1: switching mode persists the source immediately, so "Manual
            // Selection" applies by default (matches the visible mode to the saved
            // authority the engine reads). No separate Apply Manual click required.
            els.v47SmartModeBtn?.addEventListener('click', () => { setRacePlannerMode('smart'); autoSaveRaces().catch(() => {}); });
            els.v47ManualModeBtn?.addEventListener('click', () => { setRacePlannerMode('manual'); autoSaveRaces().catch(() => {}); });
            els.v47ApplyManualBtn?.addEventListener('click', () => applyManualRaceSelection().catch(() => {}));
            setRacePlannerMode(state.racePlannerMode || 'smart', { persist: false, render: false });
            els.v4PlanBtn?.addEventListener('click', () => generateTrackblazerPlan({ apply: false }).catch(() => {}));
            els.v4ApplyPlanBtn?.addEventListener('click', () => applyTrackblazerPlan().catch(() => {}));
            els.v4ResetPlanBtn?.addEventListener('click', () => {
                resetTrackblazerPlan({ clearRaces: false, render: true });
                autoSaveRaces({ force: state.racePlannerMode !== 'manual' }).catch(() => {});
            });
            els.v4DiagBundleBtn?.addEventListener('click', () => { window.location.href = '/api/diagnostics/bundle'; });
            els.v525RescueBtn?.addEventListener('click', () => runStuckCareerRescue());
            els.v532AiRebuildBtn?.addEventListener('click', rebuildAiDataset);
            els.v533AiTrainNowBtn?.addEventListener('click', trainAiNow);
            els.v532AiAdvisorBtn?.addEventListener('click', showAiAdvisor);
            els.v533AiReportBtn?.addEventListener('click', showAiPostRunReport);
            els.v533AiAutoToggle?.addEventListener('change', toggleAiAutoTraining);
            els.v539AiLivePolicyToggle?.addEventListener('change', toggleAiLivePolicyAssistance);
            els.v532AiDownloadBtn?.addEventListener('click', () => { window.location.href = '/api/ai/dataset/download?kind=turn_decisions'; });
            bindLocalLlmFormDirtyTracking();
            els.v543LocalLlmSaveBtn?.addEventListener('click', saveLocalLlmConfig);
            els.v543LocalLlmTestBtn?.addEventListener('click', testLocalLlm);
            els.v543LocalLlmAnalyzeBtn?.addEventListener('click', analyzeLatestRunWithLocalLlm);
            els.v543LocalLlmShadowBtn?.addEventListener('click', shadowReviewWithLocalLlm);
            els.v534AiSafeBundleBtn?.addEventListener('click', downloadSafeAiBundle);
            els.v537AiImportBtn?.addEventListener('click', importPreviousAiLogs);
            if (els.v515SetupBody && els.v515SetupModal) {
                const setupGroups = [
                    '.team-slots',
                    '#bot-settings-section',
                    '#skill-config-launch-section',
                    '#settings-preset-section',
                    '#v516-trackblazer-card',
                    '#race-schedule-section'
                ];
                setupGroups.forEach(selector => {
                    const node = document.querySelector(selector);
                    if (node && !els.v515SetupBody.contains(node)) els.v515SetupBody.appendChild(node);
                });
                const libraryBody = document.querySelector('#content-panel .panel-body');
                if (libraryBody && !document.getElementById('v516-library-group')) {
                    const group = document.createElement('section');
                    group.id = 'v516-library-group';
                    group.className = 'dashboard-section v516-library-group';
                    group.innerHTML = '<h2 class="dashboard-section-title">LIBRARY</h2>';
                    while (libraryBody.firstElementChild) group.appendChild(libraryBody.firstElementChild);
                    els.v515SetupBody.appendChild(group);
                }
                renderGuestParentsSection();
                if (!dashData.guestParentsLoaded) refreshGuestParents({ force: false });
            }
            const cockpit = document.querySelector('.v53-cockpit');
            const careerCard = document.querySelector('.v53-career-card');
            const metricsCard = document.querySelector('.v53-metrics-card');
            const actionCard = document.querySelector('.v53-action-card');
            if (cockpit && !document.getElementById('v518-left-stack')) {
                const leftStack = document.createElement('div');
                leftStack.id = 'v518-left-stack';
                leftStack.className = 'v518-left-stack';
                const topActions = document.querySelector('.v516-top-actions');
                if (topActions && topActions.nextSibling) cockpit.insertBefore(leftStack, topActions.nextSibling);
                else cockpit.insertBefore(leftStack, actionCard || null);
                [careerCard, metricsCard].forEach(card => {
                    if (card) leftStack.appendChild(card);
                });
            } else {
                const leftStack = document.getElementById('v518-left-stack');
                if (leftStack) [careerCard, metricsCard].forEach(card => {
                    if (card && !leftStack.contains(card)) leftStack.appendChild(card);
                });
            }
            if (els.v516DiagnosticsBody) {
                const diagCard = document.getElementById('v516-diagnostics-card');
                if (diagCard && !els.v516DiagnosticsBody.contains(diagCard)) els.v516DiagnosticsBody.appendChild(diagCard);
                const masterSection = document.getElementById('master-data-section');
                if (masterSection && !els.v516DiagnosticsBody.contains(masterSection)) els.v516DiagnosticsBody.appendChild(masterSection);
            }
            const openSetupModal = () => {
                if (els.v515SetupModal) els.v515SetupModal.style.display = 'flex';
                renderTeamPanel();
                renderRaces();
                refreshTrackblazerStatus();
            };
            if (!els.v515SetupBtn?.dataset.v516Bound) {
                els.v515SetupBtn?.addEventListener('click', openSetupModal);
                if (els.v515SetupBtn) els.v515SetupBtn.dataset.v516Bound = '1';
            }
            if (!els.v515SetupDoneBtn?.dataset.v516Bound) {
                els.v515SetupDoneBtn?.addEventListener('click', () => {
                    if (els.v515SetupModal) els.v515SetupModal.style.display = 'none';
                    syncStartButton();
                });
                if (els.v515SetupDoneBtn) els.v515SetupDoneBtn.dataset.v516Bound = '1';
            }
            if (!els.v515SetupModal?.dataset.v516Bound) {
                els.v515SetupModal?.addEventListener('click', event => {
                    if (event.target === els.v515SetupModal) els.v515SetupModal.style.display = 'none';
                });
                if (els.v515SetupModal) els.v515SetupModal.dataset.v516Bound = '1';
            }
            if (!els.v516DiagnosticsBtn?.dataset.v516Bound) {
                els.v516DiagnosticsBtn?.addEventListener('click', () => {
                    if (els.v516DiagnosticsModal) els.v516DiagnosticsModal.style.display = 'flex';
                    refreshV4Status();
                });
                if (els.v516DiagnosticsBtn) els.v516DiagnosticsBtn.dataset.v516Bound = '1';
            }
            if (!els.v535AiLearningBtn?.dataset.v535Bound) {
                els.v535AiLearningBtn?.addEventListener('click', () => {
                    if (els.v535AiLearningModal) els.v535AiLearningModal.style.display = 'flex';
                    refreshAiLearningStatus();
                });
                if (els.v535AiLearningBtn) els.v535AiLearningBtn.dataset.v535Bound = '1';
            }
            bindCareerHistoryControls();
            if (!els.v516DiagnosticsDoneBtn?.dataset.v516Bound) {
                els.v516DiagnosticsDoneBtn?.addEventListener('click', () => {
                    if (els.v516DiagnosticsModal) els.v516DiagnosticsModal.style.display = 'none';
                });
                if (els.v516DiagnosticsDoneBtn) els.v516DiagnosticsDoneBtn.dataset.v516Bound = '1';
            }
            if (!els.v516DiagnosticsModal?.dataset.v516Bound) {
                els.v516DiagnosticsModal?.addEventListener('click', event => {
                    if (event.target === els.v516DiagnosticsModal) els.v516DiagnosticsModal.style.display = 'none';
                });
                if (els.v516DiagnosticsModal) els.v516DiagnosticsModal.dataset.v516Bound = '1';
            }
            if (!els.v542StyleAdaptationSaveBtn?.dataset.v542Bound) {
                els.v542StyleAdaptationSaveBtn?.addEventListener('click', saveStyleAdaptationMode);
                if (els.v542StyleAdaptationSaveBtn) els.v542StyleAdaptationSaveBtn.dataset.v542Bound = '1';
            }
            if (!els.v535AiLearningDoneBtn?.dataset.v535Bound) {
                els.v535AiLearningDoneBtn?.addEventListener('click', () => {
                    if (els.v535AiLearningModal) els.v535AiLearningModal.style.display = 'none';
                });
                if (els.v535AiLearningDoneBtn) els.v535AiLearningDoneBtn.dataset.v535Bound = '1';
            }
            if (!els.v535AiLearningModal?.dataset.v535Bound) {
                els.v535AiLearningModal?.addEventListener('click', event => {
                    if (event.target === els.v535AiLearningModal) els.v535AiLearningModal.style.display = 'none';
                });
                if (els.v535AiLearningModal) els.v535AiLearningModal.dataset.v535Bound = '1';
            }
            // v2.1: Diag/AI tabs — the Diagnostics and AI/Misc modals now act as
            // two tabs of one "Diag / AI" page. Switching a tab swaps which modal
            // is shown and refreshes that view.
            document.querySelectorAll('[data-diagai-tab]').forEach(btn => {
                if (btn.dataset.diagaiBound) return;
                btn.dataset.diagaiBound = '1';
                btn.addEventListener('click', () => {
                    var tab = btn.dataset.diagaiTab;
                    if (tab === 'ai') {
                        if (els.v516DiagnosticsModal) els.v516DiagnosticsModal.style.display = 'none';
                        if (els.v535AiLearningModal) els.v535AiLearningModal.style.display = 'flex';
                        if (typeof refreshAiLearningStatus === 'function') refreshAiLearningStatus();
                    } else {
                        if (els.v535AiLearningModal) els.v535AiLearningModal.style.display = 'none';
                        if (els.v516DiagnosticsModal) els.v516DiagnosticsModal.style.display = 'flex';
                        if (typeof refreshV4Status === 'function') refreshV4Status();
                    }
                    document.querySelectorAll('[data-diagai-tab]').forEach(function (b) {
                        b.classList.toggle('is-active', b.dataset.diagaiTab === tab);
                    });
                });
            });
        }
        function startV4Polling() {
            refreshTrackblazerStatus();
            refreshV4Status();
            refreshSnapshotTimeline();
            if (state.v4Timer) bgClearTimer(state.v4Timer);
            state.v4Timer = bgSetInterval(() => {
                refreshV4Status();
                refreshSnapshotTimeline();
            }, 5000);
        }

        function selectedDeckSupportIds() {
            try {
                return (selection.deck && Array.isArray(selection.deck.cards))
                    ? selection.deck.cards.map(card => card.id || card.support_card_id).filter(Boolean)
                    : [];
            } catch (e) { return []; }
        }
        function eventChoiceEffect(ev, i) {
            const out = (ev && ev.outcomes) || {};
            // v3: outcomes are keyed by the game's select_index, which is NOT always
            // sequential (borrowed/friend-card events use 1/2/4-style or gapped
            // numbering). Resolve the real select_index for choice position i from
            // choice_select_indices when present; fall back to i+1 only when absent.
            const idxList = Array.isArray(ev && ev.choice_select_indices) ? ev.choice_select_indices : null;
            const sel = idxList && i < idxList.length ? Number(idxList[i]) : (i + 1);
            const raw = out[String(sel)] ?? out[sel] ?? out[String(i + 1)] ?? out[i + 1] ?? '';
            return String(raw || '').trim();
        }
        function eventEffectClass(effect) {
            const e = String(effect || '').toLowerCase();
            if (e === 'bad' || /(^|[\s,])-\d|energy -|motivation -/.test(e)) return 'eff-bad';
            if (e === 'good' || /\+\d/.test(e)) return 'eff-good';
            return 'eff-neutral';
        }
        function eventChoiceOptions(ev) {
            const count = Math.max(0, Number(ev.num_choices || 0));
            // v7.6.2: guard against override == null. Number(null) === 0, so the
            // old `Number(ev.override) === i` test also matched Choice 1 (i=0)
            // when the event was on Auto — marking BOTH the Auto option and
            // Choice 1 as selected. The later option (Choice 1) won, so every
            // auto/cleared event showed "Choice 1". Only select a choice when an
            // override is actually set.
            const hasOverride = ev.override != null;
            let html = `<option value="-1"${hasOverride ? '' : ' selected'}>Auto (let the bot decide)</option>`;
            for (let i = 0; i < count; i++) {
                const eff = eventChoiceEffect(ev, i);
                const label = eff ? `Choice ${i + 1} — ${eff}` : `Choice ${i + 1}`;
                html += `<option value="${i}"${hasOverride && Number(ev.override) === i ? ' selected' : ''}>${escapeHtml(label)}</option>`;
            }
            return html;
        }
        // v7.4 — cache the fetched events so the search box can filter client-side
        // without re-hitting the network on every keystroke.
        let _eventChoicesCache = [];
        // v3 — Story vs Support Card event category filter. A row is a support-card
        // event when its `category` is "support_card" (the game8 tag — most events
        // are support-card events) OR it carries a real support_card_id (a seen
        // borrowed/rental-card event); otherwise it's a Story event.
        let _eventChoicesCategory = 'story';
        function _evIsSupport(e) {
            return !!(e && (e.category === 'support_card' || Number(e.support_card_id || 0) > 0));
        }
        // "Only my deck's events" view filter for the Support Card Events tab.
        // Persisted to the active preset (mant_config.event_choices_deck_filter)
        // so loading a preset restores the user's choice. Seen events carry a real
        // card id; catalog events (no card id) are hidden while this is on.
        let _eventChoicesDeckFilter = false;
        function _eventChoicesDeckIdSet() {
            const ids = new Set();
            (selectedDeckSupportIds() || []).forEach(id => { const n = Number(id); if (n) ids.add(n); });
            try {
                const friendId = selection.friend && selection.friend.support_card_id;
                if (friendId) ids.add(Number(friendId));
            } catch (e) {}
            return ids;
        }
        function syncEventChoicesDeckFilterFromPreset() {
            const current = getCurrentPreset();
            const on = current ? !!getSetting(current, 'mant', 'event_choices_deck_filter', false) : false;
            _eventChoicesDeckFilter = on;
            if (els.eventChoicesDeckFilter) els.eventChoicesDeckFilter.checked = on;
        }
        function setEventChoicesCategory(cat, { persist = true } = {}) {
            _eventChoicesCategory = cat;
            const sb = document.getElementById('event-cat-story');
            const ub = document.getElementById('event-cat-support');
            if (sb) sb.classList.toggle('active', cat === 'story');
            if (ub) ub.classList.toggle('active', cat === 'support');
            // The deck filter only applies to the Support Card Events tab.
            const wrap = els.eventChoicesDeckFilter?.parentElement;
            if (wrap) wrap.style.display = (cat === 'support') ? '' : 'none';
            applyEventChoicesFilter();
            if (persist) saveEventChoicesCategoryToPreset(cat);
        }
        async function saveEventChoicesCategoryToPreset(cat) {
            const current = getCurrentPreset();
            if (!current) return;
            setSettingValue(current, 'mant', 'event_choices_tab', cat);
            try { await saveSettingsPreset(current, { refreshUI: false }); }
            catch (e) { console.warn('Failed to save event-choices tab', e); }
        }
        function updateEventCategoryCounts() {
            const storyN = _eventChoicesCache.filter(e => !_evIsSupport(e)).length;
            const supN = _eventChoicesCache.length - storyN;
            const sb = document.getElementById('event-cat-story');
            const ub = document.getElementById('event-cat-support');
            if (sb) sb.textContent = `Story Events (${storyN})`;
            if (ub) ub.textContent = `Support Card Events (${supN})`;
        }
        function eventChoiceAutoLine(ev) {
            const n = Math.max(0, Number(ev.num_choices || 0));
            const hasOutcomes = ev.outcomes && Object.keys(ev.outcomes).length > 0;
            if (ev.override != null) {
                return `You forced <b>Choice ${Number(ev.override) + 1}</b> — the bot will always pick it.`;
            }
            if (n <= 1) return `Single choice — auto-confirmed.`;
            let line;
            if (hasOutcomes) {
                line = `Bot scores the effects below against your event stat priority.`;
            } else {
                line = `No effect data — bot falls back to Choice ${n > 1 ? 2 : 1}.`;
            }
            if (ev.auto_pick != null && String(ev.auto_source || '') !== 'override') {
                line += ` Last run picked Choice ${Number(ev.auto_pick) + 1}.`;
            }
            return line;
        }
        function eventChoiceRowHtml(ev) {
            const n = Math.max(0, Number(ev.num_choices || 0));
            const forced = ev.override != null;
            const effects = [];
            for (let i = 0; i < n; i++) {
                const eff = eventChoiceEffect(ev, i);
                effects.push(`<span class="event-choice-effect ${eventEffectClass(eff)}"><b>${i + 1}</b> ${escapeHtml(eff || 'effect not in database')}</span>`);
            }
            const effectsHtml = effects.length ? `<div class="event-choice-effects">${effects.join('')}</div>` : '';
            const metaBits = [];
            if (_evIsSupport(ev) && Number(ev.support_card_id || 0) > 0) {
                metaBits.push(`Support ${escapeHtml(ev.support_card_id)}`);
            } else if (_evIsSupport(ev)) {
                metaBits.push('Support Card');
            } else {
                metaBits.push(`Story ${escapeHtml(ev.story_id || '')}`);
            }
            if (ev.count) metaBits.push(`Seen ${escapeHtml(ev.count)}x`);
            return `
                <div class="event-choice-row ${forced ? 'has-override' : ''}" data-story-id="${escapeAttr(ev.story_id || '')}">
                    <div class="event-choice-head">
                        <span class="event-choice-badge ${forced ? 'badge-override' : 'badge-auto'}">${forced ? 'FORCED' : 'AUTO'}</span>
                        <strong class="event-choice-name">${escapeHtml(ev.event_name || `Story ${ev.story_id}`)}</strong>
                    </div>
                    <div class="event-choice-meta">${metaBits.join(' · ')}</div>
                    <div class="event-choice-auto">${eventChoiceAutoLine(ev)}</div>
                    ${effectsHtml}
                    <label class="event-choice-control">
                        <span class="event-choice-control-label">Force choice</span>
                        <select class="event-choice-select form-input" data-story-id="${escapeAttr(ev.story_id || '')}">${eventChoiceOptions(ev)}</select>
                    </label>
                </div>`;
        }
        function bindEventChoiceSelects() {
            // v6.7.25 — do not re-render the whole list after a save; that was destroying
            // the <select> the user was still interacting with and dropping clicks.
            // Update the row's state in place instead, and only refresh on REFRESH/RESET/search.
            els.eventChoicesList.querySelectorAll('.event-choice-select').forEach(select => {
                select.addEventListener('change', async () => {
                    const choice = Number(select.value);
                    const row = select.closest('.event-choice-row');
                    const storyId = select.dataset.storyId;
                    const badge = row && row.querySelector('.event-choice-badge');
                    const autoEl = row && row.querySelector('.event-choice-auto');
                    if (row) row.classList.toggle('has-override', choice >= 0);
                    if (badge) {
                        badge.classList.toggle('badge-override', choice >= 0);
                        badge.classList.toggle('badge-auto', choice < 0);
                        badge.textContent = choice >= 0 ? 'FORCED' : 'AUTO';
                    }
                    // keep the in-memory cache in sync so search re-renders stay correct
                    const cached = _eventChoicesCache.find(e => String(e.story_id || '') === String(storyId));
                    if (cached) cached.override = choice >= 0 ? choice : null;
                    if (autoEl && cached) autoEl.innerHTML = eventChoiceAutoLine(cached);
                    try {
                        await apiJson('/api/events/override', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ story_id: storyId, choice })
                        });
                        if (els.eventChoicesStatus) {
                            els.eventChoicesStatus.textContent = choice < 0
                                ? `Reset to Auto: ${storyId}`
                                : `Saved override: ${storyId} → Choice ${choice + 1}`;
                        }
                    } catch (e) {
                        if (row) row.classList.toggle('has-override', false);
                        if (els.eventChoicesStatus) els.eventChoicesStatus.textContent = e.message || 'Failed to save event override';
                    }
                });
            });
        }
        function renderEventChoiceList(events) {
            els.eventChoicesList.innerHTML = events.map(eventChoiceRowHtml).join('')
                || '<div class="event-choice-empty">No events match your search.</div>';
            bindEventChoiceSelects();
        }
        function applyEventChoicesFilter() {
            const q = (els.eventChoicesSearch?.value || '').trim().toLowerCase();
            const cat = _eventChoicesCategory || 'story';
            const inCat = (ev) => (cat === 'support') ? _evIsSupport(ev) : !_evIsSupport(ev);
            let filtered = _eventChoicesCache.filter(inCat);
            // "Only my deck's events": narrow the Support Card list to events whose
            // support card is in the selected deck. Seen events carry a real card id;
            // catalog events with no card id (0) are hidden while this is on.
            let deckFilterActive = false;
            if (cat === 'support' && _eventChoicesDeckFilter) {
                const deckIds = _eventChoicesDeckIdSet();
                deckFilterActive = deckIds.size > 0;
                if (deckFilterActive) {
                    filtered = filtered.filter(ev => deckIds.has(Number(ev.support_card_id || 0)));
                }
            }
            if (q) {
                filtered = filtered.filter(ev => {
                    return String(ev.event_name || '').toLowerCase().includes(q)
                        || String(ev.story_id || '').toLowerCase().includes(q)
                        || String(ev.support_card_id || '').toLowerCase().includes(q);
                });
            }
            renderEventChoiceList(filtered);
            if (els.eventChoicesStatus) {
                let txt;
                if (q) {
                    txt = `${filtered.length} of ${_eventChoicesCache.length} events match "${q}"`;
                } else {
                    txt = `${filtered.length} ${cat === 'support' ? 'support-card' : 'story'} events · AUTO = bot decides, FORCED = your locked choice.`;
                }
                if (_eventChoicesDeckFilter && cat === 'support') {
                    txt += deckFilterActive
                        ? ' · filtered to your selected deck.'
                        : ' · select a deck to filter by it.';
                }
                els.eventChoicesStatus.textContent = txt;
            }
        }
        async function loadEventChoices() {
            if (!els.eventChoicesList) return;
            const ids = selectedDeckSupportIds();
            if (els.eventChoicesStatus) els.eventChoicesStatus.textContent = 'Loading event choices...';
            try {
                const data = await apiJson('/api/events' + (ids.length ? `?cards=${encodeURIComponent(ids.join(','))}` : ''));
                _eventChoicesCache = (data && data.events) || [];
                if (!_eventChoicesCache.length) {
                    els.eventChoicesList.innerHTML = '<div class="event-choice-empty">No editable events found yet.</div>';
                    if (els.eventChoicesStatus) els.eventChoicesStatus.textContent = 'No events discovered yet. Run a career or refresh after selecting a deck.';
                    return;
                }
                const _sb = document.getElementById('event-cat-story');
                const _ub = document.getElementById('event-cat-support');
                if (_sb) _sb.onclick = () => setEventChoicesCategory('story');
                if (_ub) _ub.onclick = () => setEventChoicesCategory('support');
                syncEventChoicesDeckFilterFromPreset();
                const _preset = getCurrentPreset();
                const _savedTab = (_preset && getSetting(_preset, 'mant', 'event_choices_tab', 'story') === 'support') ? 'support' : 'story';
                setEventChoicesCategory(_savedTab, { persist: false });
                updateEventCategoryCounts();
                applyEventChoicesFilter();
            } catch (e) {
                if (els.eventChoicesStatus) els.eventChoicesStatus.textContent = e.message || 'Failed to load event choices';
            }
        }
        // v7.6 — bulk action: set every event to Auto by clearing all saved
        // overrides server-side. Reports the actual count cleared (from the
        // server), not the filtered DOM, so it works regardless of any active
        // search filter.
        async function setAllEventChoicesToAuto() {
            if (els.eventChoicesStatus) els.eventChoicesStatus.textContent = 'Setting all events to Auto…';
            try {
                const res = await apiJson('/api/events/overrides/clear', { method: 'POST' });
                const cleared = res && typeof res.cleared === 'number' ? res.cleared : null;
                await loadEventChoices();
                if (els.eventChoicesStatus) {
                    els.eventChoicesStatus.textContent = cleared !== null
                        ? `All events set to Auto · ${cleared} forced choice(s) cleared.`
                        : 'All events set to Auto.';
                }
            } catch (e) {
                if (els.eventChoicesStatus) els.eventChoicesStatus.textContent = e.message || 'Failed to set all events to Auto';
            }
        }
        function openEventChoices() {
            if (els.eventChoicesModal) els.eventChoicesModal.style.display = 'flex';
            loadEventChoices();
        }
        function setDiscordStatus(message, error = false) {
            if (!els.discordWebhookStatus) return;
            els.discordWebhookStatus.textContent = message || '';
            els.discordWebhookStatus.classList.toggle('error', Boolean(error));
        }
        async function loadDiscordWebhook() {
            if (!els.discordWebhookUrl) return;
            try {
                const data = await apiJson('/api/settings/discord-webhook');
                if (data.webhook_url) els.discordWebhookUrl.value = data.webhook_url;
                setDiscordStatus(data.configured ? `Discord notifications enabled (${data.webhook_url_redacted || 'saved'})` : 'Discord notifications disabled.');
            } catch (e) {
                setDiscordStatus('Could not load Discord settings', true);
            }
        }
        async function saveDiscordWebhook() {
            if (!els.discordWebhookUrl) return;
            els.discordWebhookSaveBtn.disabled = true;
            try {
                const data = await apiJson('/api/settings/discord-webhook', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ webhook_url: els.discordWebhookUrl.value.trim(), enabled: Boolean(els.discordWebhookUrl.value.trim()) })
                });
                setDiscordStatus(data.configured ? `Discord notifications enabled (${data.webhook_url_redacted || 'saved'})` : 'Discord notifications disabled.');
            } catch (e) {
                setDiscordStatus(e.message || 'Failed to save Discord webhook', true);
            } finally {
                els.discordWebhookSaveBtn.disabled = false;
            }
        }
        async function testDiscordWebhook() {
            if (!els.discordWebhookTestBtn) return;
            els.discordWebhookTestBtn.disabled = true;
            try {
                const data = await apiJson('/api/settings/discord-webhook/test', { method: 'POST' });
                setDiscordStatus(data.success ? 'Discord test sent.' : (data.detail || 'Discord test failed'), !data.success);
            } catch (e) {
                setDiscordStatus(e.message || 'Discord test failed', true);
            } finally {
                els.discordWebhookTestBtn.disabled = false;
            }
        }

        async function startCareer() {
            const reason = getStartMissingReason();
            if (reason || state.isStartingCareer) {
                syncStartButton();
                return;
            }
            state.isStartingCareer = true;
            syncStartButton();
            let finalMessage = '';
            let finalIsError = false;
            const activeCareer = state.account && state.account.career && state.account.career.active;
            const parentPayload = activeCareer ? {} : selectedParentStartPayload();
            const body = activeCareer ? {
                preset_name: state.selectedPreset,
                max_steps: 2500,
                burn_clocks: state.burnClocks,
                carats_enabled: !!state.caratsEnabled,
                max_clocks_per_career: Math.max(0, Number(state.maxClocksPerCareer) || 0),
                finalize_single_runs: !!state.finalizeSingleRuns,
                dev_mode: state.runCount !== 1,
                run_count: normalizeRunCount(state.runCount),
                race_planner_mode: state.racePlannerMode || 'smart',
                manual_race_ids: []
            } : {
                card_id: Number(selection.trainee.id),
                support_card_ids: selection.deck.cards.map(card => Number(card.id)),
                friend_viewer_id: Number(selection.friend.viewer_id),
                friend_card_id: Number(selection.friend.support_card_id),
                parent_id_1: parentPayload.parent_id_1,
                parent_id_2: parentPayload.parent_id_2,
                rental_viewer_id: parentPayload.rental_viewer_id,
                rental_trained_chara_id: parentPayload.rental_trained_chara_id,
                rental_card_id: parentPayload.rental_card_id,
                parent_selection_mode: parentPayload.parent_selection_mode,
                deck_id: Number(selection.deck.id) || 1,
                scenario_id: 4,
                use_tp: 30,
                difficulty_id: 0,
                difficulty: 0,
                is_boost: 0,
                boost_story_event_id: 0,
                preset_name: state.selectedPreset,
                max_steps: 2500,
                burn_clocks: state.burnClocks,
                carats_enabled: !!state.caratsEnabled,
                max_clocks_per_career: Math.max(0, Number(state.maxClocksPerCareer) || 0),
                finalize_single_runs: !!state.finalizeSingleRuns,
                dev_mode: state.runCount !== 1,
                run_count: normalizeRunCount(state.runCount),
                race_planner_mode: state.racePlannerMode || 'smart',
                manual_race_ids: state.racePlannerMode === 'manual' ? [...(state.selectedRaces || [])] : []
            };
            try {
                if (!activeCareer && state.racePlannerMode === 'manual' && (state.selectedRaces || []).length) {
                    els.startStatus.innerText = 'Applying manual race selection...';
                    state.trackblazerPlan = null;
                    state.manualRaceSelectionActive = true;
                    await autoSaveRaces({ force: true });
                } else if (!activeCareer && state.autoPlanBeforeRun) {
                    els.startStatus.innerText = 'Trackblazer is plotting the race route...';
                    await generateTrackblazerPlan({ apply: true });
                }
                if (!activeCareer) {
                    body.race_planner_mode = state.racePlannerMode || 'smart';
                    body.manual_race_ids = body.race_planner_mode === 'manual' ? [...(state.selectedRaces || [])] : [];
                }
                const data = await apiJson('/api/career/run', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body)
                });
                if (!data.success) throw new Error(data.detail || 'Start failed');
                state.displayedClocksUsed = Number(data.runner && data.runner.clocks_used || 0);
                renderAccountStrip(data.account);
                if (data.account && data.account.career && data.account.career.active) {
                    autoLoadCareerSelection();
                    renderFriends();
                }
                startRunnerPolling();
                finalMessage = 'Career runner started';
            } catch (e) {
                finalMessage = e.message || 'Start failed';
                finalIsError = true;
                if (state.devEnabled) {
                    setDevEnabled(false, { persist: true });
                }
            } finally {
                state.isStartingCareer = false;
                syncStartButton();
                if (finalMessage) {
                    els.startStatus.innerText = finalMessage;
                    els.startStatus.classList.toggle('error', finalIsError);
                }
            }
        }
        function applyRunnerSettings(runner) {
            if (runner.running && runner.burn_clocks !== undefined && state.burnClocks !== runner.burn_clocks) {
                setBurnClocks(runner.burn_clocks, { persist: true });
            }
        }
        function applyRunnerClockUsage(runner) {
            const clocksUsed = Number(runner.clocks_used || 0);
            if (state.account && clocksUsed > state.displayedClocksUsed) {
                const delta = clocksUsed - state.displayedClocksUsed;
                state.account = {
                    ...state.account,
                    clocks: Math.max(0, Number(state.account.clocks || 0) - delta)
                };
                state.displayedClocksUsed = clocksUsed;
                renderAccountStrip(state.account);
            } else if (clocksUsed < state.displayedClocksUsed) {
                state.displayedClocksUsed = clocksUsed;
            }
        }
        function updatePauseButton(runner) {
            if (!els.v526PauseRunnerBtn) return;
            const active = Boolean(runner && (runner.running || runner.loop_active));
            const paused = Boolean(runner && runner.paused);
            els.v526PauseRunnerBtn.disabled = !active;
            els.v526PauseRunnerBtn.textContent = paused ? 'RESUME' : 'PAUSE';
            els.v526PauseRunnerBtn.classList.toggle('paused', paused);
        }
        function setFooterStatus(message = '', opts = {}) {
            if (!els.startStatus) return;
            const text = String(message || '');
            els.startStatus.innerText = text;
            els.startStatus.classList.toggle('error', Boolean(opts.error));
            els.startStatus.classList.toggle('is-empty', !text);
            els.startStatus.classList.toggle('is-transient', Boolean(opts.transient));
        }

        function applyRunnerSnapshot(runner) {
            state.runner = runner;
            applyRunnerSettings(runner);
            applyRunnerClockUsage(runner);
            renderV4PanelsFromData({ runner });
            updatePauseButton(runner);
        }
        async function refreshRunnerStatus() {
            try {
                // Shared coalescer (see monitor.js): dedups the /api/career/runner
                // fetch across app.js + monitor.js pollers into one round-trip.
                const data = (window.SweepyRunnerFeed
                    ? await window.SweepyRunnerFeed.get()
                    : await apiJson('/api/career/runner'));
                if (!data.success || !data.runner) return;
                const runner = data.runner;
                // The poll endpoint now returns a fresh account (TP/carats/gold/
                // clocks) every cycle. Sync the optimistic clock-usage tracker
                // first so applyRunnerClockUsage (inside applyRunnerSnapshot)
                // does not re-subtract usage the server already reflects.
                if (data.account) state.displayedClocksUsed = Number(runner.clocks_used || 0);
                applyRunnerSnapshot(runner);
                if (data.account) {
                    if (dashData) dashData.account = data.account;
                    renderAccountStrip(data.account);
                }
                // Refresh the (heavy) career history+report ONCE when a run finishes
                // while the modal is open — not on every poll. A fresh run resets the
                // latch so the next finish refreshes again.
                if (runner.running) {
                    state.historyReloadedForFinish = false;
                    state.finishHandledForRun = false;
                } else if (runner.finished && !runner.last_error && !state.historyReloadedForFinish
                           && els.v543CareerHistoryModal?.style.display === 'flex') {
                    state.historyReloadedForFinish = true;
                    loadCareerHistory();
                    loadCareerReport();
                }

                const rows = getMainActionRows(runner);
                if (rows.length) renderMainActionLog(rows);
                if (runner.running) {
                    const loopSuffix = runner.loop_target !== 1 ? ` / Run ${runner.loop_index || 1}/${runner.loop_target === 0 ? '∞' : runner.loop_target}` : '';
                    if (runner.paused) {
                        setFooterStatus(`Paused at turn ${runner.turn || '?'}${loopSuffix}`, { transient: true });
                    } else {
                        // Surface server throttling when present (recent 208/5xx/394-shaped
                        // rejects + recovery count) so the owner can tell a throttled account
                        // from a healthy run. Empty otherwise.
                        const _rejects = Number(runner.recent_server_rejects || 0);
                        const _recoveries = Number(runner.recoveries || 0);
                        if (_rejects > 0 || _recoveries > 0) {
                            setFooterStatus(`Server throttling — ${_rejects} reject(s) in 10min · ${_recoveries} recoveries`, { transient: true });
                        } else {
                            setFooterStatus('');
                        }
                    }
                    return;
                }
                // v2.1: do NOT stop polling when a snapshot reports not-running.
                // running:false happens transiently (idle, startup, login, between
                // careers in a loop, and right after a single run finishes) -- killing
                // the timer here left the dashboard frozen on stale status until a
                // manual page refresh. Keep the poll alive at a steady cadence so the
                // live status always self-updates.
                if (runner.last_error) {
                    els.startStatus.classList.toggle('error', true);
                    if (!rows.length) els.startStatus.innerText = 'Career halted — ' + runner.last_error;
                    if (state.runCount !== 1) {
                        state.consecutiveRunnerFails++;
                        if (state.consecutiveRunnerFails >= 3) {
                            if (!rows.length) els.startStatus.innerText = 'Career halted — ' + runner.last_error + " (Loop disabled after repeated failures)";
                            setRunCount(1, { persist: true });
                        }
                    }
                } else if (runner.finished && !runner.last_error && !state.finishHandledForRun) {
                    // v2.1: one-shot per finished run. The poll now stays alive while
                    // idle (the live-status fix), so without this latch
                    // clearFinishedSetupState would re-fire a POST /api/selection +
                    // team-panel rebuild every 1.5s. Reset when a new run starts (above).
                    state.finishHandledForRun = true;
                    state.consecutiveRunnerFails = 0;
                    els.startStatus.classList.toggle('error', false);
                    if (state.runCount !== 1 && runner.loop_active) {
                        if (!rows.length) els.startStatus.innerText = `Career finished! Restarting...`;
                        clearFinishedSetupState({ clearSelection: false, syncServer: false });
                    } else {
                        if (!rows.length) els.startStatus.innerText = `Career finished. Setup unlocked.`;
                        clearFinishedSetupState({ clearSelection: true });
                    }
                } else if (runner.steps) {
                    els.startStatus.classList.toggle('error', false);
                    if (!rows.length) els.startStatus.innerText = `Runner stopped after ${runner.steps} steps`;
                    if (state.runCount !== 1) {
                        state.consecutiveRunnerFails++;
                        if (state.consecutiveRunnerFails >= 3) {
                            if (!rows.length) els.startStatus.innerText = `Runner stopped after ${runner.steps} steps (Loop disabled after repeated failures)`;
                            setRunCount(1, { persist: true });
                        }
                    }
                }
            } catch (e) {}
        }
        function renderActionHistory(rows) {
            renderMainActionLog(rows || []);
        }
        function deriveActionHistory(log) {
            return log.filter(item => ['command', 'race', 'race_progress', 'finish', 'api_delay', 'turn_delay', 'complex_delay'].includes(item.action)).map(item => {
                const detail = String(item.detail || '');
                let action = item.action;
                let facility = '';
                if (action === 'command') {
                    if (detail.startsWith('training ')) {
                        action = 'train';
                        facility = detail.replace('training ', '');
                    } else if (detail.startsWith('rest ')) {
                        action = 'rest';
                        facility = detail.replace('rest ', '');
                        if (['301', '302', '303', '304', '305', '390'].includes(facility)) action = 'recreation';
                    } else if (detail.startsWith('challenge ')) {
                        action = 'rest';
                        facility = detail.replace('challenge ', '');
                    } else if (detail.startsWith('recreation ')) {
                        action = 'recreation';
                        facility = detail.replace('recreation ', '');
                    } else if (detail.startsWith('command 8:')) {
                        action = 'medic';
                    }
                } else if (action === 'race_progress') {
                    action = 'race';
                }
                return { turn: item.turn, action, facility, detail };
            });
        }
        function normalizeHistoryAction(row) {
            const facility = String(row.facility ?? '');
            if (row.action === 'rest' && ['301', '302', '303', '304', '305', '390'].includes(facility)) {
                return { ...row, action: 'recreation' };
            }
            return row;
        }
        const timerWorkerBlob = new Blob([`
            let activeTimers = {};
            self.onmessage = function(e) {
                const { action, id, ms } = e.data;
                if (action === 'setInterval') {
                    activeTimers[id] = setInterval(() => postMessage({ id }), ms);
                } else if (action === 'setTimeout') {
                    activeTimers[id] = setTimeout(() => {
                        postMessage({ id });
                        delete activeTimers[id];
                    }, ms);
                } else if (action === 'clear') {
                    clearInterval(activeTimers[id]);
                    clearTimeout(activeTimers[id]);
                    delete activeTimers[id];
                }
            };
        `], {type: 'application/javascript'});
        const timerWorker = new Worker(URL.createObjectURL(timerWorkerBlob));
        let nextTimerId = 1;
        const timerCallbacks = {};
        timerWorker.onmessage = function(e) {
            if (timerCallbacks[e.data.id]) timerCallbacks[e.data.id]();
        };
        function bgSetInterval(cb, ms) {
            const id = nextTimerId++;
            timerCallbacks[id] = cb;
            timerWorker.postMessage({ action: 'setInterval', id, ms });
            return id;
        }
        function bgSetTimeout(cb, ms) {
            const id = nextTimerId++;
            timerCallbacks[id] = () => { delete timerCallbacks[id]; cb(); };
            timerWorker.postMessage({ action: 'setTimeout', id, ms });
            return id;
        }
        function bgClearTimer(id) {
            delete timerCallbacks[id];
            timerWorker.postMessage({ action: 'clear', id });
        }
        // v6.7 -- Character Profile is now a tab inside the Decision
        // Reasoning pane (clickable header buttons toggle between the two
        // views).  The old v6.5 standalone collapsible section was removed
        // from index.html because the dashboard layout didn't have the
        // sidebar-section container we assumed.  This IIFE wires the tab
        // buttons and renders profile content into #v66-character-profile-pane.
        (function setupCharacterProfilePanel() {
            const contentEl = document.getElementById('v66-character-profile-pane');
            const decisionPane = document.getElementById('v547-decision-reasoning');
            const turnPill = document.getElementById('v547-reason-turn');
            const tabButtons = document.querySelectorAll('.v66-tab-btn');
            if (!contentEl || !decisionPane || !tabButtons.length) return;

            let profileLoadedOnce = false;
            let lastTurnPillText = turnPill ? turnPill.textContent : 'WAITING';

            function escapeHtml(s) {
                return String(s == null ? '' : s)
                    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
            }

            function pillHtml(label, value, tone) {
                const cls = tone ? `cp-pill cp-pill-${tone}` : 'cp-pill';
                return `<span class="${cls}"><span class="cp-pill-label">${escapeHtml(label)}</span><span class="cp-pill-value">${escapeHtml(value)}</span></span>`;
            }

            function solverOverridesHtml(overrides) {
                const keys = Object.keys(overrides || {});
                if (!keys.length) return '<em>no solver overrides (scenario defaults)</em>';
                return keys.map(k => `<div class="cp-override-row"><span class="cp-override-key">${escapeHtml(k)}:</span> <span class="cp-override-value">${escapeHtml(JSON.stringify(overrides[k]))}</span></div>`).join('');
            }

            function epithetSourcePill(source) {
                const tone = {preset: 'override', profile: 'profile', auto: 'auto', none: 'muted'}[source] || 'muted';
                const label = {preset: 'User Preset', profile: 'Profile JSON', auto: 'Auto-picked', none: 'None'}[source] || source;
                return `<span class="cp-pill cp-pill-${tone}">${escapeHtml(label)}</span>`;
            }

            function suggestedPickerHtml(charFiltered, current) {
                if (!charFiltered || !charFiltered.length) return '<div class="cp-suggested-empty">No character-tagged epithets in catalog.</div>';
                const currentSet = new Set((current || []).map(s => String(s).trim()));
                return charFiltered.map(epi => {
                    const checked = currentSet.has(epi.name) ? 'checked' : '';
                    const bullets = (epi.bullet_points || []).slice(0, 6).map(b => `<li>${escapeHtml(b)}</li>`).join('');
                    return `<label class="cp-epithet-row">
                        <input type="checkbox" class="cp-epithet-cb" data-epithet="${escapeHtml(epi.name)}" ${checked}>
                        <div class="cp-epithet-detail">
                            <div class="cp-epithet-name">${escapeHtml(epi.name)}</div>
                            <ul class="cp-epithet-bullets">${bullets}</ul>
                        </div>
                    </label>`;
                }).join('');
            }

            async function persistEpithets(profileId, targets) {
                try {
                    const resp = await fetch('/api/character-profile/epithets', {
                        method: 'POST', headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({profile_id: profileId, target_epithets: targets}),
                    });
                    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
                    return await resp.json();
                } catch (e) { console.warn('epithet persist failed', e); return null; }
            }

            async function persistAutoPick(profileId, autoPick) {
                try {
                    const resp = await fetch('/api/character-profile/auto-pick', {
                        method: 'POST', headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({profile_id: profileId, auto_pick: !!autoPick}),
                    });
                    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
                    return await resp.json();
                } catch (e) { console.warn('auto-pick persist failed', e); return null; }
            }

            function render(data) {
                if (!data || !data.success) {
                    contentEl.innerHTML = `<div class="cp-error">Could not load profile: ${escapeHtml((data && data.detail) || 'no data')}</div>`;
                    return;
                }
                const p = data.profile || {};
                const effectiveTargets = (p.target_epithets && p.target_epithets.length) ? p.target_epithets
                    : (p.auto_pick_epithets ? (p.auto_picked_epithets || []) : []);
                const effectiveSource = (p.target_epithets && p.target_epithets.length) ? 'profile'
                    : (p.auto_pick_epithets && (p.auto_picked_epithets || []).length ? 'auto' : 'none');
                contentEl.innerHTML = `
                    <div class="cp-header">
                        <div class="cp-title">${escapeHtml(p.display_name || p.profile_id)}</div>
                        <div class="cp-pills">
                            ${pillHtml('Profile', p.profile_id, p.derivation === 'hand_curated' ? 'curated' : (p.derivation === 'auto_derived' ? 'auto' : 'muted'))}
                            ${pillHtml('Derivation', p.derivation, p.derivation === 'hand_curated' ? 'curated' : (p.derivation === 'auto_derived' ? 'auto' : 'muted'))}
                            ${pillHtml('Matched via', p.matched_via, 'info')}
                            ${pillHtml('Scenario', String(p.scenario_id), 'info')}
                        </div>
                    </div>

                    <div class="cp-section">
                        <div class="cp-section-title">Auto-pick Signature Epithets</div>
                        <div class="cp-mode-row">
                            <label class="cp-autopick-label">
                                <input type="checkbox" id="cp-autopick-cb" ${p.auto_pick_epithets ? 'checked' : ''}>
                                <span>Auto-pick this character's signature epithets when no explicit target is set</span>
                            </label>
                            <button type="button" id="cp-autopick-save" class="cp-btn">Save</button>
                            <span class="cp-mode-help">
                                When OFF (the v6.7.6 default), the smart race solver picks the best fan/epithet route without biasing toward any specific signature epithet.
                                When ON, the catalog's signature epithets for this character seed the solver's target_epithets list and protect those races from the irregular-training hijack.
                            </span>
                        </div>
                    </div>

                    <div class="cp-section">
                        <div class="cp-section-title">Solver Overrides (scenario ${escapeHtml(String(p.scenario_id))})</div>
                        <div class="cp-overrides">${solverOverridesHtml(p.solver_overrides)}</div>
                    </div>

                    <div class="cp-section">
                        <div class="cp-section-title">
                            Epithet Goals
                            ${epithetSourcePill(effectiveSource)}
                        </div>
                        <div class="cp-epithets-effective">
                            <strong>Active targets:</strong>
                            ${effectiveTargets.length ? effectiveTargets.map(e => `<span class="cp-epithet-chip">${escapeHtml(e)}</span>`).join('') : '<em>none</em>'}
                        </div>
                        ${p.auto_picked_epithets && p.auto_picked_epithets.length ? `<div class="cp-epithets-auto-row">
                            <strong>Auto-pickable (catalog signature):</strong>
                            ${p.auto_picked_epithets.map(e => `<span class="cp-epithet-chip cp-chip-auto">${escapeHtml(e)}</span>`).join('')}
                        </div>` : ''}
                        <div class="cp-section-subtitle">Pick from catalog (writes to profile.target_epithets)</div>
                        <div class="cp-epithet-picker">
                            ${suggestedPickerHtml(data.character_filtered_epithets, p.target_epithets)}
                        </div>
                        <div class="cp-epithet-actions">
                            <button type="button" id="cp-epithets-save" class="cp-btn">Save selections to profile</button>
                            <button type="button" id="cp-epithets-clear" class="cp-btn cp-btn-secondary">Clear (resume auto-pick)</button>
                        </div>
                    </div>

                    <div class="cp-footer">
                        <button type="button" id="cp-refresh" class="cp-btn cp-btn-secondary">Refresh</button>
                        <span class="cp-resolved-from">
                            card_id=${escapeHtml(data.resolved_from && data.resolved_from.card_id)},
                            chara_id=${escapeHtml(data.resolved_from && data.resolved_from.chara_id)},
                            catalog: ${escapeHtml(data.all_epithets_count)} entries
                        </span>
                    </div>
                `;

                document.getElementById('cp-autopick-save')?.addEventListener('click', async () => {
                    const cb = document.getElementById('cp-autopick-cb');
                    if (!cb) return;
                    await persistAutoPick(p.profile_id, cb.checked);
                    refresh();
                });
                document.getElementById('cp-epithets-save')?.addEventListener('click', async () => {
                    const picked = Array.from(document.querySelectorAll('.cp-epithet-cb:checked'))
                        .map(cb => cb.getAttribute('data-epithet'));
                    await persistEpithets(p.profile_id, picked);
                    refresh();
                });
                document.getElementById('cp-epithets-clear')?.addEventListener('click', async () => {
                    await persistEpithets(p.profile_id, []);
                    refresh();
                });
                document.getElementById('cp-refresh')?.addEventListener('click', refresh);
            }

            async function refresh() {
                try {
                    const resp = await fetch('/api/character-profile/active');
                    const data = await resp.json();
                    render(data);
                    profileLoadedOnce = true;
                } catch (e) {
                    contentEl.innerHTML = `<div class="cp-error">Fetch failed: ${escapeHtml(String(e))}</div>`;
                }
            }

            // Tab switching: hide one pane, show the other, update active
            // button.  When the profile tab opens we fetch fresh data (and
            // also poll every 30s while it's the active tab).
            let activeTab = 'decision';
            let profilePollTimer = null;

            function activateTab(tabName) {
                if (tabName === activeTab) return;
                activeTab = tabName;
                tabButtons.forEach(btn => {
                    const isActive = btn.getAttribute('data-tab') === tabName;
                    btn.classList.toggle('v66-tab-active', isActive);
                    btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
                });
                if (tabName === 'profile') {
                    decisionPane.style.display = 'none';
                    contentEl.style.display = '';
                    // Hide the WAITING / turn-N pill on profile tab so it
                    // doesn't suggest the profile is "waiting" for a turn
                    if (turnPill) {
                        lastTurnPillText = turnPill.textContent;
                        turnPill.style.display = 'none';
                    }
                    refresh();  // re-fetch on every tab open
                    if (profilePollTimer) clearInterval(profilePollTimer);
                    profilePollTimer = setInterval(refresh, 30000);
                } else {
                    contentEl.style.display = 'none';
                    decisionPane.style.display = '';
                    if (turnPill) {
                        turnPill.style.display = '';
                    }
                    if (profilePollTimer) { clearInterval(profilePollTimer); profilePollTimer = null; }
                }
            }

            tabButtons.forEach(btn => {
                btn.addEventListener('click', () => activateTab(btn.getAttribute('data-tab')));
            });

            // Don't auto-load the profile -- only fetch when the user
            // actually clicks the tab.  This keeps the dashboard quiet on
            // first paint and avoids one extra API call per session.
        })();

        function startRunnerPolling() {
            if (state.runnerTimer) bgClearTimer(state.runnerTimer);
            refreshRunnerStatus();
            state.runnerTimer = bgSetInterval(refreshRunnerStatus, 1500);
        }
        // v2.1: self-heal the live-status poll if it was ever torn down (older builds
        // cleared it on a not-running snapshot; a backgrounded tab can also drop a
        // worker timer). Re-arm on focus/visibility so status never stays stale
        // without a manual refresh.
        function ensureRunnerPolling() {
            if (!state.runnerTimer) startRunnerPolling();
            // v3: re-apply LOOP + TEMPT FATE visuals from state on refocus --
            // tabbing away and back could leave them showing the default green/OFF
            // even while the bot is looping / on a non-safe speed.
            syncDevControls();
            if (els.temptFateBtn) {
                els.temptFateBtn.classList.toggle('is-active', (state.speedLevel || 'safe') !== 'safe');
            }
        }
        document.addEventListener('visibilitychange', () => { if (!document.hidden) ensureRunnerPolling(); });
        window.addEventListener('focus', ensureRunnerPolling);
        window.addEventListener('pageshow', ensureRunnerPolling);
        els.friendRefreshBtn.addEventListener('click', event => {
            event.stopPropagation();
            loadFriends(true);
        });
        els.eventChoicesOpenBtn?.addEventListener('click', openEventChoices);
        els.eventChoicesRefreshBtn?.addEventListener('click', loadEventChoices);
        els.eventChoicesSearch?.addEventListener('input', applyEventChoicesFilter);
        els.eventChoicesDeckFilter?.addEventListener('change', async () => {
            _eventChoicesDeckFilter = !!(els.eventChoicesDeckFilter && els.eventChoicesDeckFilter.checked);
            const current = getCurrentPreset();
            if (current) {
                setSettingValue(current, 'mant', 'event_choices_deck_filter', _eventChoicesDeckFilter);
                try { await saveSettingsPreset(current, { refreshUI: false }); }
                catch (e) { console.warn('Failed to save deck-filter preference', e); }
            }
            applyEventChoicesFilter();
        });
        document.getElementById('event-choices-set-auto-btn')?.addEventListener('click', setAllEventChoicesToAuto);
        // v7.6 — custom deck builder controls (stopPropagation so the DECKS
        // section header toggle doesn't collapse when the button is clicked).
        document.getElementById('custom-deck-btn')?.addEventListener('click', (e) => { e.stopPropagation(); openCustomDeckBuilder(); });
        // v7.6.2 — Recommended Supports lives in a modal opened from the Deck
        // Bonuses panel header (stopPropagation so the header toggle doesn't fire).
        document.getElementById('rec-supports-btn')?.addEventListener('click', (e) => { e.stopPropagation(); openRecommendedSupports(); });
        document.getElementById('custom-deck-apply-btn')?.addEventListener('click', applyCustomDeck);
        document.getElementById('custom-deck-clear-btn')?.addEventListener('click', () => { _customDeckState.cards = []; renderCustomDeckBuilder(); });
        document.getElementById('custom-deck-search')?.addEventListener('input', renderCustomDeckOwned);
        document.getElementById('custom-deck-type-filter')?.addEventListener('change', renderCustomDeckOwned);
        els.discordWebhookSaveBtn?.addEventListener('click', saveDiscordWebhook);
        els.discordWebhookTestBtn?.addEventListener('click', testDiscordWebhook);
        loadDiscordWebhook();
        els.v526PauseRunnerBtn?.addEventListener('click', async () => {
            const paused = Boolean(state.runner && state.runner.paused);
            const endpoint = paused ? '/api/career/runner/resume' : '/api/career/runner/pause';
            els.v526PauseRunnerBtn.disabled = true;
            try {
                const data = await apiJson(endpoint, { method: 'POST' });
                if (data.runner) applyRunnerSnapshot(data.runner);
                if (els.startStatus) els.startStatus.innerText = paused ? 'Runner resumed' : 'Runner pause requested';
            } catch (e) {
                if (els.startStatus) { els.startStatus.innerText = e.message || 'Pause/resume failed'; els.startStatus.classList.add('error'); }
            } finally {
                updatePauseButton(state.runner);
            }
        });
        els.startCareerBtn?.addEventListener('click', startCareer);
        els.v520StopRunnerBtn?.addEventListener('click', async () => {
            els.v520StopRunnerBtn.disabled = true;
            if (els.startStatus) {
                els.startStatus.innerText = 'Stopping runner after the current safe point...';
                els.startStatus.classList.remove('error');
            }
            try {
                const data = await apiJson('/api/career/runner/stop', { method: 'POST' });
                if (data.account) {
                    if (dashData) dashData.account = data.account;
                    renderAccountStrip(data.account);
                }
                if (data.runner) applyRunnerSnapshot(data.runner);
                if (data.selection_cleared || (data.runner && data.runner.finished && !data.runner.running)) {
                    clearFinishedSetupState({ clearSelection: true });
                }
                if (els.startStatus) els.startStatus.innerText = data.selection_cleared ? 'Runner stopped; setup unlocked' : 'Runner stop requested';
            } catch (e) {
                if (els.startStatus) {
                    els.startStatus.innerText = e.message || 'Stop failed';
                    els.startStatus.classList.add('error');
                }
            } finally {
                els.v520StopRunnerBtn.disabled = false;
                syncStartButton();
            }
        });
        els.v520SetupShortcutBtn?.addEventListener('click', () => els.v515SetupBtn?.click());

        function selectDeck(index, element) {
            const alreadySelected = element.classList.contains('selected');
            document.querySelectorAll('.deck-container.selected').forEach(card => card.classList.remove('selected'));
            selection.deck = null;
            if (!alreadySelected) {
                element.classList.add('selected');
                selection.deck = dashData.validDecks[index];
            }
            renderFriends();
            renderTeamPanel();
            renderGuestParentsSection();
            renderDeckBonuses();
            syncSelectionToServer();
        }
        function selectTrainee(index, element) {
            const alreadySelected = element.classList.contains('selected');
            document.querySelectorAll('#uma-grid .grid-card.selected').forEach(card => card.classList.remove('selected'));
            selection.trainee = null;
            if (!alreadySelected) {
                element.classList.add('selected');
                selection.trainee = dashData.umas[index];
            }
            state.trackblazerPlan = null;
            state.selectedRaces = [];
            state.selectedTraineeProfile = null;
            state.weightedSkillPreview = null;
            renderFriends();
            updateVetSelectability();
            renderTeamPanel();
            updateTrackblazerPlanGate();
            renderRaces();
            if (selection.trainee) {
                loadSelectedTraineeProfile({ force: true })
                    .then(() => {
                        updateTrackblazerPlanGate();
                        if (els.skillModal && els.skillModal.style.display === 'flex') refreshWeightedSkillPreview({ force: true });
                        // Keep the Smart Race Solver aptitude grid in sync when the
                        // trainee changes while its settings modal is open.
                        if (document.getElementById('smart-solver-settings-modal')?.style.display === 'flex') renderSmartSolverSettings();
                    })
                    .catch(e => {
                        if (els.v4TrackblazerPlan) els.v4TrackblazerPlan.innerHTML = `<div class="v4-warn">${escapeHtml(e.message || 'Unable to load trainee profile')}</div>`;
                    });
            }
            // v7.6.2: Recommended Supports moved into a modal opened from the
            // Deck Bonuses panel. Only refresh it live if that modal is open;
            // otherwise it loads lazily when the user opens it.
            const recModal = document.getElementById('rec-supports-modal');
            if (recModal && recModal.style.display === 'flex') loadRecommendedSupports();
            renderDeckBonuses();
            syncSelectionToServer();
        }
        function selectParent(index, element) {
            if (element.classList.contains('vet-full')) return;
            if (element.classList.contains('selected')) {
                element.classList.remove('selected');
                selection.veterans = selection.veterans.filter(parent => parent._gridIdx !== index);
            } else {
                const guestCount = (selection.guestParents || []).filter(Boolean).length;
                const ownLimit = guestCount > 0 ? 1 : 2;
                if (selection.veterans.length >= ownLimit) {
                    const status = document.getElementById('guest-parent-status');
                    if (status) status.textContent = guestCount > 0 ? 'With a guest parent selected, only one own parent is allowed.' : parentSelectionRuleText();
                    return;
                }
                element.classList.add('selected');
                selection.veterans.push({ ...dashData.parents[index], _gridIdx: index });
            }
            updateVetSelectability();
            renderGuestParentsSection();
            renderTeamPanel();
            syncSelectionToServer();
        }
        function attachSelectionHandlers() {
            document.querySelectorAll('.deck-container').forEach((element, index) => {
                element.addEventListener('click', () => selectDeck(index, element));
            });
            document.querySelectorAll('#uma-grid .grid-card').forEach((element, index) => {
                element.classList.add('selectable');
                element.addEventListener('click', () => selectTrainee(index, element));
            });
            document.querySelectorAll('#parent-grid .grid-card').forEach((element, index) => {
                element.classList.add('selectable');
                element.addEventListener('click', () => selectParent(index, element));
            });
        }
        function isValidDeck(deck) {
            return deck.cards.every(card => {
                const id = card.id || '';
                const name = card.name || '';
                return !id.includes('{') && !id.includes('-') && !name.includes('Unknown');
            });
        }
        function renderCounts(data) {
            els.umaCount.innerText = `(${data.umas.length})`;
            els.cardCount.innerText = `(${data.supports.length})`;
            els.parentCount.innerText = `(${data.parents.length})`;
        }
        function renderDecks(decks) {
            els.deckList.innerHTML = decks.map((deck, deckIdx) => {
                const cards = deck.cards.map(card => {
                    const imgId = card.id || '10001';
                    return `<div class="grid-card deck-card">
                        <img src="/api/images/${imgId}.png" onerror="hideBrokenImage(this)">
                        <div class="grid-card-overlay">
                            <span class="grid-card-kicker">${card.type || '?'} | ${card.rarity || '?'}</span>
                            <span class="grid-card-name">${card.name || 'Unknown'}</span>
                        </div>
                    </div>`;
                }).join('');
                return `<div class="deck-container" data-deck-index="${deckIdx}">
                    <div class="deck-header">
                        <span>${deck.name.toUpperCase()}</span>
                        <span style="font-size:0.85rem; opacity:0.8">SLOT ${deck.id}</span>
                    </div>
                    <div class="deck-cards">${cards}</div>
                </div>`;
            }).join('');
            // v6.7.25 — wire deck-info hover tooltips after each render.
            bindDeckInfoTooltips();
        }
        // ---------------------------------------------------------------
        // v6.7.25 — Deck/support card hover info + deck-quality scorelet.
        // On hovering a .deck-container, fetch /api/supports/details for the
        // deck's cards, render a per-card breakdown (LB, type, real bonuses
        // at the LB-implied level from master data) plus a deck-quality
        // score and verdict computed against the selected trainee's growth.
        // ---------------------------------------------------------------
        const _deckInfoState = { cache: new Map(), tooltipEl: null, activeKey: null, hideTimer: null };

        function _ensureDeckInfoTooltipEl() {
            if (_deckInfoState.tooltipEl) return _deckInfoState.tooltipEl;
            const el = document.createElement('div');
            el.className = 'deck-info-tooltip';
            el.setAttribute('role', 'tooltip');
            document.body.appendChild(el);
            _deckInfoState.tooltipEl = el;
            return el;
        }

        function _positionDeckInfoTooltip(anchor) {
            const tooltip = _deckInfoState.tooltipEl;
            if (!tooltip || !anchor) return;
            const rect = anchor.getBoundingClientRect();
            const tRect = tooltip.getBoundingClientRect();
            const tw = Math.min(tRect.width || 380, window.innerWidth - 16);
            const th = tRect.height || 360;
            const x = clampValue(rect.left + rect.width / 2, tw / 2 + 8, window.innerWidth - tw / 2 - 8);
            const viewportH = window.innerHeight;
            const aboveY = rect.top - th - 10;
            const belowY = rect.bottom + 10;
            let y;
            if (aboveY >= 8) y = aboveY;
            else if (belowY + th <= viewportH - 8) y = belowY;
            else y = (viewportH - rect.bottom - 8) >= (rect.top - 8) ? belowY : Math.max(8, aboveY);
            tooltip.style.setProperty('--deck-tt-left', `${x}px`);
            tooltip.style.setProperty('--deck-tt-top', `${y}px`);
        }

        function _deckCacheKey(deckIdx, deck, traineeId) {
            const ids = (deck.cards || []).map(c => c.id || c.support_card_id || '').join(',');
            const lbs = (deck.cards || []).map(c => c.limit_break_count ?? 0).join(',');
            return `${deckIdx}|${ids}|${lbs}|${traineeId || 0}`;
        }

        function _typeChipClass(typeLabel) {
            const t = String(typeLabel || '').toLowerCase();
            if (t === 'friend') return 'tchip tchip-friend';
            if (t === 'speed') return 'tchip tchip-speed';
            if (t === 'stamina') return 'tchip tchip-stamina';
            if (t === 'power') return 'tchip tchip-power';
            if (t === 'guts') return 'tchip tchip-guts';
            if (t === 'wit') return 'tchip tchip-wit';
            return 'tchip';
        }

        function _scoreBandClass(score) {
            if (score >= 7.5) return 'deck-score-strong';
            if (score >= 5.5) return 'deck-score-solid';
            if (score >= 3.5) return 'deck-score-mid';
            return 'deck-score-weak';
        }

        function _formatDeckTooltipHtml(deck, payload) {
            if (!payload || !payload.success) {
                const detail = (payload && payload.detail) || 'Master data not loaded — run a master data sync to see card bonuses.';
                return `<div class="deck-info-empty">${escapeHtml(detail)}</div>`;
            }
            const score = Number(payload.deck_score || 0);
            const verdict = String(payload.deck_verdict || '');
            const breakdown = payload.deck_breakdown || {};
            const cards = payload.cards || [];
            const cardHtml = cards.map(card => {
                const lb = `LB${Math.max(0, Number(card.lb || 0))}`;
                const eff = (card.effects_ordered || []).slice(0, 4).map(e => {
                    const sign = e.value > 0 ? '+' : '';
                    return `<span class="deck-info-effect"><b>${escapeHtml(e.label)}</b> ${sign}${escapeHtml(String(e.value))}${escapeHtml(e.unit || '')}</span>`;
                }).join('');
                return `<div class="deck-info-card">
                    <div class="deck-info-card-head">
                        <span class="${_typeChipClass(card.type_label)}">${escapeHtml((card.type_label || '?').toUpperCase())}</span>
                        <span class="deck-info-rarity">${escapeHtml(card.rarity_label || '?')}</span>
                        <span class="deck-info-lb">${escapeHtml(lb)}</span>
                        <span class="deck-info-level">Lv ${escapeHtml(String(card.level || ''))}</span>
                    </div>
                    <div class="deck-info-name">${escapeHtml(card.name || '?')}</div>
                    <div class="deck-info-effects">${eff || '<span class="deck-info-effect deck-info-effect-empty">no bonuses at this level</span>'}</div>
                </div>`;
            }).join('');
            const typeCounts = breakdown.type_counts || {};
            const typeChips = Object.keys(typeCounts).sort().map(t => `<span class="${_typeChipClass(t)}">${escapeHtml(t)} ×${escapeHtml(String(typeCounts[t]))}</span>`).join('');
            const traineeLine = payload.trainee_name
                ? `<span class="deck-info-meta">Scored against ${escapeHtml(payload.trainee_name)} (${escapeHtml(breakdown.primary_growth_type || 'mixed')}-leaning growth)</span>`
                : `<span class="deck-info-meta">Select a trainee to refine the type-match score.</span>`;
            return `
                <div class="deck-info-head">
                    <div class="deck-info-title">${escapeHtml(deck.name || 'Deck')} <span class="deck-info-slot">SLOT ${escapeHtml(deck.id ?? '?')}</span></div>
                    <div class="deck-info-scorebar">
                        <span class="deck-info-score ${_scoreBandClass(score)}">${score.toFixed(1)}<span>/10</span></span>
                        <span class="deck-info-verdict">${escapeHtml(verdict)}</span>
                    </div>
                    <div class="deck-info-typechips">${typeChips}</div>
                    ${traineeLine}
                </div>
                <div class="deck-info-cards">${cardHtml}</div>
                <div class="deck-info-foot">
                    Total LB ${escapeHtml(String(breakdown.total_lb ?? '?'))}
                    · Type match ${(Number(breakdown.type_match || 0) * 100).toFixed(0)}%
                    · Bonus strength ${(Number(breakdown.effect_strength || 0) * 100).toFixed(0)}%
                    · LB density ${(Number(breakdown.lb_density || 0) * 100).toFixed(0)}%
                </div>`;
        }

        async function _fetchDeckInfo(deck, traineeId) {
            const ids = (deck.cards || []).map(c => c.id || c.support_card_id || '').filter(Boolean).join(',');
            const lbs = (deck.cards || []).map(c => Number(c.limit_break_count ?? 0)).join(',');
            const qs = new URLSearchParams({ ids, lbs });
            if (traineeId) qs.set('trainee_card_id', String(traineeId));
            return apiJson('/api/supports/details?' + qs.toString());
        }

        async function _showDeckTooltip(deckEl) {
            const idx = Number(deckEl.dataset.deckIndex || 0);
            const decks = (dashData && dashData.validDecks) || [];
            const deck = decks[idx];
            if (!deck) return;
            const traineeId = (selection.trainee && (selection.trainee.card_id || selection.trainee.id)) || 0;
            const key = _deckCacheKey(idx, deck, traineeId);
            const tooltip = _ensureDeckInfoTooltipEl();
            _deckInfoState.activeKey = key;
            tooltip.innerHTML = '<div class="deck-info-loading">Loading deck details…</div>';
            tooltip.classList.add('is-visible');
            _positionDeckInfoTooltip(deckEl);
            try {
                let payload = _deckInfoState.cache.get(key);
                if (!payload) {
                    payload = await _fetchDeckInfo(deck, traineeId);
                    _deckInfoState.cache.set(key, payload);
                }
                if (_deckInfoState.activeKey !== key) return; // user moved on
                tooltip.innerHTML = _formatDeckTooltipHtml(deck, payload);
                _positionDeckInfoTooltip(deckEl);
            } catch (e) {
                if (_deckInfoState.activeKey !== key) return;
                tooltip.innerHTML = `<div class="deck-info-empty">${escapeHtml(e.message || 'Failed to load deck details')}</div>`;
                _positionDeckInfoTooltip(deckEl);
            }
        }

        function _hideDeckTooltip() {
            if (!_deckInfoState.tooltipEl) return;
            _deckInfoState.activeKey = null;
            _deckInfoState.tooltipEl.classList.remove('is-visible');
        }

        function bindDeckInfoTooltips() {
            const list = els.deckList;
            if (!list || list.dataset.deckInfoBound === '1') return;
            list.dataset.deckInfoBound = '1';
            list.addEventListener('mouseover', event => {
                const deckEl = event.target.closest('.deck-container');
                if (!deckEl || !list.contains(deckEl)) return;
                const from = event.relatedTarget;
                if (from && deckEl.contains(from)) return;
                if (_deckInfoState.hideTimer) { clearTimeout(_deckInfoState.hideTimer); _deckInfoState.hideTimer = null; }
                _showDeckTooltip(deckEl);
            });
            list.addEventListener('mouseout', event => {
                const deckEl = event.target.closest('.deck-container');
                if (!deckEl || !list.contains(deckEl)) return;
                const to = event.relatedTarget;
                if (to && deckEl.contains(to)) return;
                // Small grace period so the user can move toward the tooltip without flicker.
                _deckInfoState.hideTimer = setTimeout(_hideDeckTooltip, 80);
            });
            window.addEventListener('scroll', () => {
                if (_deckInfoState.activeKey && _deckInfoState.tooltipEl?.classList.contains('is-visible')) {
                    // Re-anchor on whatever's currently hovered (best effort).
                    const hoveredDeck = list.querySelector('.deck-container:hover');
                    if (hoveredDeck) _positionDeckInfoTooltip(hoveredDeck);
                }
            }, true);
        }
        // v7.6 — always-visible "Deck Bonuses" panel at the top of the Library.
        // Reuses /api/supports/details (same data as the deck hover tooltip) to
        // sum each effect across the selected deck at every card's current
        // limit-break level.
        function _formatDeckBonusesHtml(payload) {
            const cards = payload.cards || [];
            const totals = {}, units = {};
            cards.forEach(card => {
                (card.effects_ordered || []).forEach(e => {
                    if (!e || !e.label) return;
                    totals[e.label] = (totals[e.label] || 0) + Number(e.value || 0);
                    if (e.unit) units[e.label] = e.unit;
                });
            });
            const entries = Object.keys(totals).map(label => ({ label, value: totals[label], unit: units[label] || '' }))
                .filter(x => x.value).sort((a, b) => b.value - a.value);
            const bonusGrid = entries.length ? entries.map(x => {
                const sign = x.value > 0 ? '+' : '';
                return `<div class="deck-bonus-row"><span class="deck-bonus-label">${escapeHtml(x.label)}</span><span class="deck-bonus-value">${sign}${escapeHtml(String(x.value))}${escapeHtml(x.unit)}</span></div>`;
            }).join('') : '<div class="friend-status">No combined bonuses at the current card levels.</div>';
            const breakdown = payload.deck_breakdown || {};
            const typeCounts = breakdown.type_counts || {};
            const typeChips = Object.keys(typeCounts).sort().map(t => `<span class="${_typeChipClass(t)}">${escapeHtml(t)} ×${escapeHtml(String(typeCounts[t]))}</span>`).join('');
            const score = Number(payload.deck_score || 0);
            const verdict = String(payload.deck_verdict || '');
            const scoreLine = score ? `<div class="deck-bonuses-score ${_scoreBandClass(score)}">Deck score ${score.toFixed(1)}/10${verdict ? ' — ' + escapeHtml(verdict) : ''}</div>` : '';
            const traineeLine = payload.trainee_name ? `<div class="deck-bonuses-meta">Scored vs ${escapeHtml(payload.trainee_name)}</div>` : '';
            return `${typeChips ? `<div class="deck-bonuses-head">${typeChips}</div>` : ''}${scoreLine}<div class="deck-bonus-grid">${bonusGrid}</div>${traineeLine}<div class="deck-bonuses-note">Combined effect values across the selected deck at each card's current limit-break level.</div>`;
        }
        async function renderDeckBonuses() {
            const el = document.getElementById('deck-bonuses-content');
            if (!el) return;
            const deck = selection.deck;
            if (!deck || !Array.isArray(deck.cards) || !deck.cards.length) {
                el.innerHTML = '<div class="friend-status">Select a deck to see its combined bonuses.</div>';
                return;
            }
            el.innerHTML = '<div class="friend-status">Calculating deck bonuses…</div>';
            const reqDeck = deck;
            const traineeId = (selection.trainee && (selection.trainee.card_id || selection.trainee.id)) || 0;
            try {
                const payload = await _fetchDeckInfo(deck, traineeId);
                if (selection.deck !== reqDeck) return; // selection changed mid-flight
                if (!payload || !payload.success) {
                    el.innerHTML = `<div class="friend-status">${escapeHtml((payload && payload.detail) || 'Master data not loaded — run a master data sync to see bonuses.')}</div>`;
                    return;
                }
                el.innerHTML = _formatDeckBonusesHtml(payload);
            } catch (e) {
                if (selection.deck !== reqDeck) return;
                el.innerHTML = `<div class="friend-status">${escapeHtml(e.message || 'Failed to compute deck bonuses')}</div>`;
            }
        }
        // v7.6 — Custom deck builder. Build a run deck from the support cards
        // the user owns (the game API has no deck-save endpoint, but a career
        // starts with an arbitrary support_card_ids list, so this feeds the run).
        const _customDeckState = { cards: [] };
        // A career deck is 5 of your OWN support cards + 1 borrowed friend (sent
        // separately as friend_support_card_info). So the owned-card picker caps
        // at 5 — sending 6 here plus the friend = 7 cards, which the game rejects
        // at single_mode_free/start with result_code 2511.
        const CUSTOM_DECK_MAX = 5;
        function _ownedSupportCards() {
            const list = (dashData && dashData.supports) || [];
            return list.filter(c => c && c.id && !String(c.id).includes('{') && !String(c.name || '').includes('Unknown'));
        }
        function _customDeckHas(id) {
            return _customDeckState.cards.some(c => String(c.id) === String(id));
        }
        function _toRunCard(c) {
            return { id: c.id, name: c.name, type: c.type, rarity: c.rarity, limit_break_count: Number(c.limit_break ?? c.limit_break_count ?? 0), exp: Number(c.exp ?? 0) };
        }
        function renderCustomDeckSlots() {
            const slots = document.getElementById('custom-deck-slots');
            const count = document.getElementById('custom-deck-count');
            if (!slots) return;
            if (count) count.textContent = `(${_customDeckState.cards.length}/${CUSTOM_DECK_MAX})`;
            let html = _customDeckState.cards.map(c => `
                <div class="custom-deck-slot filled" data-id="${escapeAttr(c.id)}" title="Click to remove ${escapeAttr(c.name)}">
                    <img src="/api/images/${escapeAttr(c.id)}.png" onerror="hideBrokenImage(this)">
                    <span class="custom-deck-slot-lb">LB${Math.max(0, Number(c.limit_break_count ?? c.limit_break ?? 0))}</span>
                </div>`).join('');
            for (let i = _customDeckState.cards.length; i < CUSTOM_DECK_MAX; i++) {
                html += `<div class="custom-deck-slot empty">+</div>`;
            }
            slots.innerHTML = html;
            slots.querySelectorAll('.custom-deck-slot.filled').forEach(el => {
                el.addEventListener('click', () => {
                    _customDeckState.cards = _customDeckState.cards.filter(c => String(c.id) !== String(el.dataset.id));
                    renderCustomDeckBuilder();
                });
            });
        }
        function renderCustomDeckOwned() {
            const grid = document.getElementById('custom-deck-owned');
            if (!grid) return;
            const q = (document.getElementById('custom-deck-search')?.value || '').toLowerCase().trim();
            const typeF = (document.getElementById('custom-deck-type-filter')?.value || '').toLowerCase();
            let rows = _ownedSupportCards();
            if (q) rows = rows.filter(c => String(c.name || '').toLowerCase().includes(q));
            if (typeF) rows = rows.filter(c => String(c.type || '').toLowerCase() === typeF);
            const status = document.getElementById('custom-deck-status');
            if (status) status.textContent = `${rows.length} owned card(s) shown · ${_customDeckState.cards.length}/${CUSTOM_DECK_MAX} selected`;
            grid.innerHTML = rows.slice(0, 500).map(c => {
                const sel = _customDeckHas(c.id) ? ' selected' : '';
                return `<div class="grid-card custom-owned-card${sel}" data-id="${escapeAttr(c.id)}" title="${escapeAttr(c.name)}">
                    <img src="/api/images/${escapeAttr(c.id)}.png" onerror="hideBrokenImage(this)">
                    <div class="grid-card-overlay">
                        <span class="grid-card-kicker">${escapeHtml(c.type || '?')} | ${escapeHtml(c.rarity || '?')} | LB${Math.max(0, Number(c.limit_break ?? 0))}</span>
                        <span class="grid-card-name">${escapeHtml(c.name || 'Unknown')}</span>
                    </div>
                </div>`;
            }).join('') || '<div class="friend-status">No owned cards match.</div>';
            grid.querySelectorAll('.custom-owned-card').forEach(el => {
                el.addEventListener('click', () => {
                    const id = el.dataset.id;
                    if (_customDeckHas(id)) {
                        _customDeckState.cards = _customDeckState.cards.filter(c => String(c.id) !== String(id));
                    } else {
                        if (_customDeckState.cards.length >= CUSTOM_DECK_MAX) {
                            const st = document.getElementById('custom-deck-status');
                            if (st) st.textContent = `Deck is full (${CUSTOM_DECK_MAX}). Remove a card first.`;
                            return;
                        }
                        const card = _ownedSupportCards().find(c => String(c.id) === String(id));
                        if (card) _customDeckState.cards.push(_toRunCard(card));
                    }
                    renderCustomDeckBuilder();
                });
            });
        }
        function renderCustomDeckBuilder() {
            renderCustomDeckSlots();
            renderCustomDeckOwned();
        }
        function openCustomDeckBuilder() {
            const modal = document.getElementById('custom-deck-modal');
            if (!modal) return;
            if (selection.deck && selection.deck.id === 'custom' && Array.isArray(selection.deck.cards)) {
                _customDeckState.cards = selection.deck.cards.slice(0, CUSTOM_DECK_MAX).map(c => ({ ...c }));
            }
            modal.style.display = 'flex';
            renderCustomDeckBuilder();
        }
        function applyCustomDeck() {
            if (!_customDeckState.cards.length) {
                const st = document.getElementById('custom-deck-status');
                if (st) st.textContent = 'Add at least one card first.';
                return;
            }
            document.querySelectorAll('.deck-container.selected').forEach(el => el.classList.remove('selected'));
            selection.deck = { id: 'custom', name: 'Custom Deck', cards: _customDeckState.cards.map(c => ({ ...c })) };
            renderFriends();
            renderTeamPanel();
            renderGuestParentsSection();
            renderDeckBonuses();
            syncSelectionToServer();
            const modal = document.getElementById('custom-deck-modal');
            if (modal) modal.style.display = 'none';
        }
        function renderFactors(factors) {
            const star = String.fromCharCode(9733);
            return factors.map(factor => `
                <div class="factor-badge f-${factor.category}">
                    ${factor.name} <span class="stars">${star.repeat(factor.stars)}</span>
                </div>
            `).join('');
        }
        function renderWins(wins) {
            if (!wins || !wins.total) return '<span class="spark-win-chip">Wins --</span>';
            return `
                <span class="spark-win-chip">G1 ${wins.g1 || 0}</span>
                <span class="spark-win-chip">G2 ${wins.g2 || 0}</span>
                <span class="spark-win-chip">G3 ${wins.g3 || 0}</span>
            `;
        }
        function renderParentSparks(parent, fallbackImgId) {
            const tree = parent.tree || {};
            const html = ['self', 'p1', 'p2'].map(key => {
                const node = tree[key];
                if (!node || !node.factors || node.factors.length === 0) return '';
                const nodeImg = node.card_id || fallbackImgId;
                const nodeClass = key === 'self' ? 'spark-node spark-node-self' : 'spark-node';
                return `<div class="${nodeClass}" style="--node-bg: url('/api/images/${nodeImg}.png')">
                    <div class="spark-node-header">
                        <img class="spark-node-portrait" src="/api/images/${nodeImg}.png" onerror="hideBrokenImage(this)">
                        <div class="spark-node-meta">
                            <div class="spark-node-title">${node.name || `Card ${node.card_id || '?'}`}</div>
                            <div class="spark-win-row">${renderWins(node.wins)}</div>
                        </div>
                    </div>
                    <div class="spark-factor-list">
                        ${renderFactors(node.factors)}
                    </div>
                </div>`;
            }).join('');
            if (html.trim()) return html;
            const self = tree.self || {};
            const nodeImg = self.card_id || parent.card_id || fallbackImgId;
            const sourceText = parent.incomplete
                ? 'Limited guest data was returned by the API. Full sparks will appear when rental succession details are available.'
                : 'No spark factors were returned for this guest parent.';
            return `<div class="spark-node spark-node-self guest-spark-fallback" style="--node-bg: url('/api/images/${nodeImg}.png')">
                <div class="spark-node-header">
                    <img class="spark-node-portrait" src="/api/images/${nodeImg}.png" onerror="hideBrokenImage(this)">
                    <div class="spark-node-meta">
                        <div class="spark-node-title">${escapeHtml(parent.name || self.name || `Card ${nodeImg || '?'}`)}</div>
                        <div class="spark-win-row">
                            <span class="spark-win-chip">Rank ${escapeHtml(rankMap[parent.rank] || parent.rank || '?')}</span>
                            ${parent.trainer_name ? `<span class="spark-win-chip">${escapeHtml(parent.trainer_name)}</span>` : ''}
                        </div>
                    </div>
                </div>
                <div class="guest-spark-fallback-note">${escapeHtml(sourceText)}</div>
            </div>`;
        }
        function renderParents(parents) {
            els.parentGrid.innerHTML = parents.map(parent => {
                const imgId = parent.card_id || '100101';
                const instanceId = parent.instance_id || '';
                const createDate = parent.create_date || parent.created_at || 0;
                return `<div class="grid-card" data-instance-id="${escapeHtml(instanceId)}" data-create-date="${escapeHtml(createDate)}">
                    <div class="rank-badge">${rankMap[parent.rank] || '??'}</div>
                    <img src="/api/images/${imgId}.png" onerror="hideBrokenImage(this)">
                    <div class="sparks-tooltip" style="--spark-bg: url('/api/images/${imgId}.png')">
                        <div class="sparks-tooltip-title"></div>
                        <div class="sparks-tooltip-scroll">
                            <div class="sparks-lineage-grid">
                                ${renderParentSparks(parent, imgId)}
                            </div>
                        </div>
                    </div>
                    <div class="grid-card-overlay">
                        <span class="grid-card-kicker">ID: ${parent.instance_id || '?'}</span>
                        <span class="grid-card-name">${parent.name || 'Unknown'}</span>
                    </div>
                </div>`;
            }).join('');
        }
        function renderTrainees(umas) {
            els.umaGrid.innerHTML = umas.map(uma => {
                const imgId = uma.id || '100101';
                return `<div class="grid-card">
                    <img src="/api/images/${imgId}.png" onerror="hideBrokenImage(this)">
                    <div class="grid-card-overlay"><span class="grid-card-name">${uma.name || 'Unknown'}</span></div>
                </div>`;
            }).join('');
        }
        function renderSupports(supports) {
            els.cardGrid.innerHTML = supports.map(card => {
                const imgId = card.id || '10001';
                return `<div class="grid-card support-card">
                    <img src="/api/images/${imgId}.png" onerror="hideBrokenImage(this)">
                    <div class="grid-card-overlay">
                        <span class="grid-card-kicker">${(card.rarity || '?') + ' | ' + (card.type || '?')}</span>
                        <span class="grid-card-name">${card.name || 'Unknown'}</span>
                    </div>
                </div>`;
            }).join('');
        }
        // v7.4 — recommend support cards from the player's owned cards for the selected trainee.
        // v7.6 — Recommended Supports now shows scraped Game8 Trackblazer
        // setups (multiple builds, budget, alternates) for the selected trainee,
        // marking which cards the player owns. Falls back to the owned-card
        // heuristic for the few trainees with no Game8 Trackblazer build.
        function _recSupportCardHtml(card) {
            const imgId = card.card_id || '10001';
            const ownedBadge = card.owned
                ? `<span class="rec-owned owned">OWNED${(card.owned_limit_break != null) ? ' LB' + Math.max(0, Number(card.owned_limit_break)) : ''}</span>`
                : `<span class="rec-owned missing">NOT OWNED</span>`;
            const ep = card.epithet ? ` <em>${escapeHtml(card.epithet)}</em>` : '';
            return `<div class="grid-card support-card rec-support-card ${card.owned ? 'is-owned' : 'is-missing'}" title="${escapeAttr((card.name || '') + (card.epithet ? ' — ' + card.epithet : ''))}">
                <img src="/api/images/${imgId}.png" onerror="hideBrokenImage(this)">
                <div class="grid-card-overlay">
                    <span class="grid-card-kicker">${escapeHtml((card.rarity || '?') + ' | ' + (card.type || '?'))}</span>
                    <span class="grid-card-name">${escapeHtml(card.name || 'Unknown')}${ep}</span>
                    ${ownedBadge}
                </div>
            </div>`;
        }
        function _recSetupBlockHtml(title, cards, raceBonus) {
            // v7.6.3 — show the Game8 "NN% Race Bonus (MLB)" caption under the row.
            const cap = raceBonus ? `<div class="rec-setup-racebonus">${escapeHtml(raceBonus)}</div>` : '';
            return `<div class="rec-setup-block"><div class="rec-setup-title">${escapeHtml(title)}</div><div class="data-grid rec-setup-grid">${(cards || []).map(_recSupportCardHtml).join('')}</div>${cap}</div>`;
        }
        // v7.6.2 — mirror Game8's "Alternate Cards" layout: group the alternates
        // by stat type into labeled rows (Speed / Stamina / Power / Guts / Wit).
        function _recAlternatesHtml(cards) {
            const order = ['Speed', 'Stamina', 'Power', 'Guts', 'Wit', 'Friend', 'Group'];
            const groups = {};
            (cards || []).forEach(c => { const t = c.type || 'Other'; (groups[t] = groups[t] || []).push(c); });
            const types = Object.keys(groups).sort((a, b) => {
                const ia = order.indexOf(a), ib = order.indexOf(b);
                return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
            });
            const rows = types.map(t =>
                `<div class="rec-alt-row"><div class="rec-alt-type">${escapeHtml(t)}</div><div class="data-grid rec-setup-grid">${groups[t].map(_recSupportCardHtml).join('')}</div></div>`
            ).join('');
            return `<div class="rec-setup-block"><div class="rec-setup-title">Alternate Cards</div>${rows}</div>`;
        }
        // v7.6.2 — open the Recommended Supports modal (button in Deck Bonuses)
        // and load the picks for the currently selected trainee.
        function openRecommendedSupports() {
            const modal = document.getElementById('rec-supports-modal');
            if (modal) modal.style.display = 'flex';
            loadRecommendedSupports();
        }
        async function loadRecommendedSupports() {
            const grid = document.getElementById('rec-supports-grid');
            const status = document.getElementById('rec-supports-status');
            const countEl = document.getElementById('rec-supports-count');
            if (!grid) return;
            const trainee = selection.trainee;
            if (!trainee) {
                grid.innerHTML = '';
                if (countEl) countEl.textContent = '';
                if (status) { status.style.display = ''; status.textContent = 'Select a trainee to see recommended support cards.'; }
                return;
            }
            if (status) { status.style.display = ''; status.textContent = `Finding Trackblazer supports for ${trainee.name || 'this trainee'}…`; }
            try {
                const data = await apiJson(`/api/trainee/support-setups?card_id=${encodeURIComponent(trainee.id || '')}`);
                if (!data || !data.found) {
                    return loadRecommendedSupportsFallback(trainee, 'No Game8 Trackblazer build for this trainee — showing best picks from your collection.');
                }
                const setups = data.setups || [];
                if (countEl) countEl.textContent = setups.length ? `(${setups.length} setup${setups.length > 1 ? 's' : ''})` : '';
                if (status) status.style.display = 'none';
                let html = '';
                setups.forEach((s, i) => { html += _recSetupBlockHtml(s.label || `Setup ${i + 1}`, s.cards, s.race_bonus); });
                if (data.budget && (data.budget.cards || []).length) html += _recSetupBlockHtml('Budget Build' + (data.budget.label ? ' — ' + data.budget.label : ''), data.budget.cards, data.budget.race_bonus);
                if ((data.alternates || []).length) html += _recAlternatesHtml(data.alternates);
                const srcLink = data.source_url ? `<a href="${escapeAttr(data.source_url)}" target="_blank" rel="noopener" class="rec-source">Game8 source ↗</a>` : '';
                const noteLine = (data.notes && data.notes.length) ? `<div class="rec-note">${escapeHtml(data.notes.join(' · '))}</div>` : '';
                grid.innerHTML = `<div class="rec-setups-subtitle">Trackblazer Build — recommended supports for ${escapeHtml(trainee.name || 'this trainee')}</div><div class="rec-setups-intro">Cards you own are marked <span class="rec-owned owned">OWNED</span>. ${srcLink}</div>${noteLine}${html}`;
            } catch (e) {
                return loadRecommendedSupportsFallback(trainee, e.message || 'Failed to load recommendations');
            }
        }
        async function loadRecommendedSupportsFallback(trainee, note) {
            const grid = document.getElementById('rec-supports-grid');
            const status = document.getElementById('rec-supports-status');
            const countEl = document.getElementById('rec-supports-count');
            if (!grid) return;
            try {
                const data = await apiJson(`/api/trainee/recommended-supports?card_id=${encodeURIComponent(trainee.id || '')}`);
                const recs = (data && data.recommended) || [];
                if (countEl) countEl.textContent = recs.length ? `(${recs.length})` : '';
                if (!recs.length) {
                    grid.innerHTML = '';
                    if (status) { status.style.display = ''; status.textContent = (data && data.owned_count === 0) ? 'No owned support cards loaded — log in and load your account first.' : 'No recommendations available for this trainee.'; }
                    return;
                }
                if (status) { status.style.display = ''; status.textContent = note || 'Best picks from your collection'; }
                grid.innerHTML = `<div class="rec-setup-block"><div class="data-grid rec-setup-grid">` + recs.map(card => {
                    const imgId = card.id || '10001';
                    return `<div class="grid-card support-card rec-support-card" title="${escapeAttr(card.reason || '')}"><img src="/api/images/${imgId}.png" onerror="hideBrokenImage(this)"><div class="grid-card-overlay"><span class="grid-card-kicker">${escapeHtml((card.rarity || '?') + ' | ' + (card.type || '?'))}</span><span class="grid-card-name">${escapeHtml(card.name || 'Unknown')}</span></div></div>`;
                }).join('') + `</div></div>`;
            } catch (e) {
                grid.innerHTML = '';
                if (status) { status.style.display = ''; status.textContent = e.message || 'Failed to load recommendations'; }
            }
        }
        function showDashboardView(data) {
            document.body.classList.add('dashboard-mode');
            els.loginView.style.display = 'none';
            els.dashboardView.style.display = '';
            els.dashboardView.classList.add('active');
            els.logoutBtn.style.display = 'block';
            showNavbar();
            renderAccountStrip(data.account);
            syncDashboardHeight();
        }

        function autoLoadCareerSelection() {
            const activeCareer = state.account && state.account.career && state.account.career.active ? state.account.career : null;
            if (!activeCareer) return;

            resetSelection();
            document.querySelectorAll('.deck-container.selected, #uma-grid .grid-card.selected, #parent-grid .grid-card.selected, #friend-grid .grid-card.selected')
                .forEach(el => el.classList.remove('selected'));

            selectCareerDeck(activeCareer);

            if (activeCareer.card_id && dashData.umas) {
                const umaIdx = dashData.umas.findIndex(u => String(u.id) === String(activeCareer.card_id));
                if (umaIdx >= 0) {
                    selection.trainee = dashData.umas[umaIdx];
                    const umaEls = document.querySelectorAll('#uma-grid .grid-card');
                    if (umaEls[umaIdx]) umaEls[umaIdx].classList.add('selected');
                }
            }

            if (dashData.parents) {
                const p1 = activeCareer.parent_id_1;
                const p2 = activeCareer.parent_id_2;

                if (p1 || p2) {
                    dashData.parents.forEach((p, idx) => {
                        const pId = Number(p.instance_id);
                        if ((p1 && pId === Number(p1)) || (p2 && pId === Number(p2))) {
                            if (selection.veterans.length < 2 && !selection.veterans.find(v => Number(v.instance_id) === pId)) {
                                p._gridIdx = idx;
                                selection.veterans.push(p);
                                const parentEls = document.querySelectorAll('#parent-grid .grid-card');
                                if (parentEls[idx]) parentEls[idx].classList.add('selected');
                            }
                        }
                    });
                    updateVetSelectability();
                }
            }

            selectCareerFriend(activeCareer);
            renderTeamPanel();
        }

        function applyServerSelection(serverSelection) {
            if (!serverSelection) return;
            if (serverSelection.deck && serverSelection.deck.id === 'custom' && Array.isArray(serverSelection.deck.cards) && serverSelection.deck.cards.length) {
                // v7.6 — a custom (owned-card) deck isn't an in-game slot, so
                // restore it directly instead of matching against validDecks.
                // Cap to 5 in case a deck was saved before the 5-card fix.
                selection.deck = { ...serverSelection.deck, cards: serverSelection.deck.cards.slice(0, CUSTOM_DECK_MAX) };
            } else if (serverSelection.deck && dashData.validDecks) {
                const deckIdx = dashData.validDecks.findIndex(d => Number(d.id) === Number(serverSelection.deck.id));
                if (deckIdx >= 0) {
                    selection.deck = dashData.validDecks[deckIdx];
                    const deckEls = document.querySelectorAll('.deck-container');
                    if (deckEls[deckIdx]) deckEls[deckIdx].classList.add('selected');
                }
            }
            if (serverSelection.trainee && dashData.umas) {
                const umaIdx = dashData.umas.findIndex(u => String(u.id) === String(serverSelection.trainee.id));
                if (umaIdx >= 0) {
                    selection.trainee = dashData.umas[umaIdx];
                    const umaEls = document.querySelectorAll('#uma-grid .grid-card');
                    if (umaEls[umaIdx]) umaEls[umaIdx].classList.add('selected');
                }
            }
            if (serverSelection.veterans && dashData.parents) {
                serverSelection.veterans.forEach(v => {
                    const pIdx = dashData.parents.findIndex(p => Number(p.instance_id) === Number(v.instance_id));
                    if (pIdx >= 0 && selection.veterans.length < 2) {
                        const parent = dashData.parents[pIdx];
                        parent._gridIdx = pIdx;
                        selection.veterans.push(parent);
                        const parentEls = document.querySelectorAll('#parent-grid .grid-card');
                        if (parentEls[pIdx]) parentEls[pIdx].classList.add('selected');
                    }
                });
                updateVetSelectability();
            }
            if (serverSelection.friend) {
                state.pendingFriendSelection = {
                    viewer_id: String(serverSelection.friend.viewer_id),
                    support_card_id: String(serverSelection.friend.support_card_id)
                };
            }
        }

        function clearSelectionClassesForPresetApply() {
            document
                .querySelectorAll('.deck-container.selected, #uma-grid .grid-card.selected, #parent-grid .grid-card.selected, #friend-grid .grid-card.selected, #guest-parent-grid .guest-parent-card.selected, #parent-grid .grid-card.vet-disabled')
                .forEach(el => el.classList.remove('selected', 'vet-disabled'));
        }

        function isCareerCurrentlyActive() {
            return Boolean(state.account && state.account.career && state.account.career.active);
        }

        function applyPresetSelection(preset, { sync = true, quiet = true } = {}) {
            const saved = preset && preset.selection;
            if (!saved || !dashData || isCareerCurrentlyActive()) return false;

            resetSelection();
            clearSelectionClassesForPresetApply();

            let applied = false;
            if (saved.deck && saved.deck.id === 'custom' && Array.isArray(saved.deck.cards) && saved.deck.cards.length) {
                // v7.6 — restore a saved custom (owned-card) deck directly,
                // capped to 5 in case it was saved before the 5-card fix.
                selection.deck = { ...saved.deck, cards: saved.deck.cards.slice(0, CUSTOM_DECK_MAX) };
                applied = true;
            } else if (saved.deck && dashData.validDecks) {
                const deckIdx = dashData.validDecks.findIndex(d => Number(d.id) === Number(saved.deck.id));
                if (deckIdx >= 0) {
                    selection.deck = dashData.validDecks[deckIdx];
                    const deckEls = document.querySelectorAll('.deck-container');
                    if (deckEls[deckIdx]) deckEls[deckIdx].classList.add('selected');
                    applied = true;
                }
            }

            if (saved.trainee && dashData.umas) {
                const umaIdx = dashData.umas.findIndex(u => String(u.id) === String(saved.trainee.id));
                if (umaIdx >= 0) {
                    selection.trainee = dashData.umas[umaIdx];
                    const umaEls = document.querySelectorAll('#uma-grid .grid-card');
                    if (umaEls[umaIdx]) umaEls[umaIdx].classList.add('selected');
                    state.selectedTraineeProfile = null;
                    applied = true;
                }
            }

            if (saved.veterans && dashData.parents) {
                saved.veterans.forEach(v => {
                    const pIdx = dashData.parents.findIndex(p => Number(p.instance_id) === Number(v.instance_id));
                    if (pIdx >= 0 && selection.veterans.length < 2) {
                        const parent = dashData.parents[pIdx];
                        parent._gridIdx = pIdx;
                        selection.veterans.push(parent);
                        const parentEls = document.querySelectorAll('#parent-grid .grid-card');
                        if (parentEls[pIdx]) parentEls[pIdx].classList.add('selected');
                        applied = true;
                    }
                });
            }

            if (saved.guestParents && saved.guestParents.length) {
                const savedGuest = saved.guestParents[0];
                let guest = null;
                if (dashData.guestParents && dashData.guestParents.length) {
                    guest = dashData.guestParents.find(p =>
                        String(p.viewer_id || '') === String(savedGuest.viewer_id || '') &&
                        String(p.instance_id || p.id || '') === String(savedGuest.instance_id || savedGuest.id || '')
                    );
                }
                selection.guestParents = [guest || savedGuest].filter(Boolean);
                applied = true;
            }

            if (saved.friend) {
                state.pendingFriendSelection = {
                    viewer_id: String(saved.friend.viewer_id || ''),
                    support_card_id: String(saved.friend.support_card_id || '')
                };
                if (dashData.visibleFriends && dashData.visibleFriends.length) {
                    const f = dashData.visibleFriends.find(v =>
                        String(v.viewer_id) === state.pendingFriendSelection.viewer_id &&
                        String(v.support_card_id) === state.pendingFriendSelection.support_card_id
                    );
                    if (f) {
                        selection.friend = f;
                        state.pendingFriendSelection = null;
                    }
                } else {
                    selection.friend = compactFriendForPreset(saved.friend);
                }
                applied = true;
            }

            updateVetSelectability();
            renderGuestParentsSection();
            renderFriends();
            renderTeamPanel();
            renderDeckBonuses();
            updateTrackblazerPlanGate();
            renderRaces();
            syncStartButton();
            if (sync) syncSelectionToServer();
            if (applied && !quiet && els.startStatus) {
                els.startStatus.innerText = 'Preset team selection restored.';
                els.startStatus.classList.remove('error');
            }
            return applied;
        }

        async function renderDashboard(data, options = {}) {
            dashData = data;
            dashData.validDecks = data.decks.filter(isValidDeck);
            dashData.friends = data.friends || [];
            dashData.friendExcludeIds = data.friendExcludeIds || [];
            showDashboardView(data);
            renderCounts(data);
            renderDecks(dashData.validDecks);
            renderParents(data.parents);
            renderTrainees(dashData.umas);
            renderSupports(data.supports);
            resetSelection();
            if (data.selection) applyServerSelection(data.selection);
            autoLoadCareerSelection();

            // These three config fetches are independent — run them concurrently
            // instead of three serial round-trips on the load path.
            await Promise.all([loadSkillConfig(), loadSmartSolverConfig(), loadPresets()]);
            if (!dashData.friends.length) {
                loadFriends(false);
            } else {
                renderFriends();
            }
            bindSparkTooltips();
            attachSelectionHandlers();
            updateTrackblazerPlanGate();
            bindRaceHandlers();
            bindPresetHandlers();
            bindV4Controls();
            renderTeamPanel();

            startRunnerPolling();
            startV4Polling();
            await waitForDomPaint(2);
            setLoadingScreen(false);
            await waitForDomPaint(2);
            if (options.animateIntro !== false) {
                playBrandIntro();
                if (options.waitForIntro) await sleep(780);
            }
            // v7.1.2 — Signal post-auth modules (e.g. the userdata setup
            // popup) that the dashboard is fully rendered and the user is
            // looking at it. Fired for both manual login and auto-login.
            try {
                document.dispatchEvent(new CustomEvent('sweepycl:dashboard-ready', { detail: { data: data, options: options } }));
            } catch (e) { /* CustomEvent unsupported is non-fatal */ }
        }

        async function restoreSession() {
            try {
                const data = await apiJson('/api/session?t=' + Date.now());
                if (data && data.success) await renderDashboard(data, { animateIntro: true, waitForIntro: false });
                else {
                    hideNavbar();
                    setLoadingScreen(false);
                }
            } catch (e) {
                hideNavbar();
                setLoadingScreen(false);
            }
        }
        bindDelayControls();
        bindMasterDataControls();
        setLoadingScreen(true);
        restoreSession();
})();

/* ============================================================
   v6.7.19 — Help & Documentation module (self-contained)
   Renders a sidebar-nav docs page into #v6719-help-modal and wires
   open/close, search filtering, and scroll-spy. Runs after the main
   app IIFE; does its own element lookups so it has no dependencies.
   ============================================================ */
(function () {
  "use strict";

  // -- Documentation content. Each section: { id, group, nav, eyebrow, html }
  var KW = function (t) { return '<span class="v6719-kw">' + t + '</span>'; };

  var SECTIONS = [
    {
      id: "overview", group: "Getting Started", nav: "Overview", eyebrow: "Start here",
      html:
        '<h2>What Icarus does</h2>' +
        '<p>Icarus plays Umamusume career mode for you. Each turn it reads the live career state from the game, decides the best action — train, race, rest, or recreation — handles story events, buys skills and uses items, and repeats until the career finishes. You set the strategy; the bot executes it the same way every time, without fatigue or misclicks.</p>' +
        '<h3>How a career run flows</h3>' +
        '<ol>' +
        '<li><strong>Connect</strong> — the bot attaches to the running game and reads your trainee, stats, and turn.</li>' +
        '<li><strong>Decide</strong> — each turn it scores the available actions against your training priorities and the race schedule, then picks one.</li>' +
        '<li><strong>Execute</strong> — it performs the action, resolves any event with the best choice, and spends skill points and items when useful.</li>' +
        '<li><strong>Adapt</strong> — the race plan re-solves as stats change, so the remaining schedule stays realistic.</li>' +
        '<li><strong>Finish</strong> — the run ends at the career finale and is saved to Career History.</li>' +
        '</ol>' +
        '<h3>The dashboard</h3>' +
        '<p>The row of buttons at the top is the control center: ' + KW('SETUP') + ', ' + KW('HELP') + ', ' + KW('ACCOUNTS') + ', ' + KW('DIAGNOSTICS') + ', ' + KW('AI / MISC') + ', ' + KW('USERDATA') + ', and ' + KW('CAREER HISTORY') + '. Each opens a focused panel. The center of the dashboard shows the live career, the action being taken, and the Decision Reasoning for that action.</p>' +
        '<div class="v6719-callout tip"><strong>The short version</strong>You configure the deck, training priorities, and race goals once. The bot turns those into consistent turn-by-turn decisions and tells you why it made each one.</div>'
    },
    {
      id: "quick-start", group: "Getting Started", nav: "Quick start", eyebrow: "Five steps",
      html:
        '<h2>Quick start</h2>' +
        '<p>From a fresh install, this is the fastest path to a running career.</p>' +
        '<ol class="v6719-steps">' +
        '<li><strong>Open ' + KW('SETUP') + '.</strong> Choose your character, build or import your six-card support deck, and select (or create) a preset to hold your settings.</li>' +
        '<li><strong>Sync master data</strong> if prompted. This downloads the latest race calendar and game data the solver needs.</li>' +
        '<li><strong>Open ' + KW('ACCOUNTS') + ' and log in.</strong> Authenticate with Steam once; the bot remembers it for next time.</li>' +
        '<li><strong>Set your strategy.</strong> Review Training Settings (stat priority, targets) and Smart Race Solver Settings (Max Streak, race goals) — or lean on the character profile defaults.</li>' +
        '<li><strong>Start the career</strong> from the dashboard. Watch the Decision Reasoning panel to confirm the bot is doing what you expect.</li>' +
        '</ol>' +
        '<div class="v6719-callout key"><strong>Most impactful setting</strong>If you only change one thing, set <strong>Max Streak</strong> in Smart Race Solver Settings to control how many races you run. It is the single biggest lever on race count.</div>'
    },
    {
      id: "setup", group: "Core Features", nav: "Setup & deck", eyebrow: "Build the run",
      html:
        '<h2>Setup &amp; support deck</h2>' +
        '<p>The ' + KW('SETUP') + ' panel defines what the run is built from. Three things matter most here.</p>' +
        '<h3>Character</h3>' +
        '<p>Pick the trainee you want to run. Her distance, track, and pace aptitudes are read live from the game during the career, so the bot always plans against your actual (post-inheritance) values, not a guess.</p>' +
        '<h3>Support card deck</h3>' +
        '<p>Your six support cards are the single biggest driver of stat gains. Rainbow and friendship training depend on which cards appear together, so the deck shapes how fast each stat climbs. Match the deck you would use in-game for the same character.</p>' +
        '<h3>Presets</h3>' +
        '<p>A <strong>preset</strong> is a saved bundle of everything: deck, training priorities, stat targets, race goals, and solver weights. Create one preset per strategy or character so you can switch between them without reconfiguring. The active preset is what the bot runs.</p>' +
        '<h3>Master data</h3>' +
        '<p>Master data is the game-side reference the bot reads — the race calendar, event tables, and similar. Keep it synced so the race solver is scheduling against the current calendar.</p>' +
        '<div class="v6719-callout warn"><strong>Same deck, different result?</strong>If a run underperforms a setup you use elsewhere with the same deck, the difference is usually <strong>parent sparks</strong> (inheritance), which add starting stats outside the deck. See Strategy &amp; tips.</div>'
    },
    {
      id: "accounts", group: "Core Features", nav: "Accounts & login", eyebrow: "Sign in",
      html:
        '<h2>Accounts &amp; login</h2>' +
        '<p>The ' + KW('ACCOUNTS') + ' panel handles authentication and lets you manage more than one game account.</p>' +
        '<h3>Signing in</h3>' +
        '<p>Authenticate with Steam once. The bot saves an obfuscated auth token so it can reconnect on its own (a <strong>headless bypass</strong>) without making you log in every time.</p>' +
        '<h3>Saved across upgrades</h3>' +
        '<p>Your authentication and settings live in the <code>Icarus_userdata</code> folder (legacy installs may have <code>SweepyCL_userdata</code> or <code>SweepyClaude_userdata</code> instead — all are still recognized), which sits outside the app folder. That means they survive version upgrades — install a new build and your login and presets carry over.</p>' +
        '<h3>Multiple accounts</h3>' +
        '<p>Add and switch between multiple game accounts from this panel, and refresh their status. Each account keeps its own saved authentication.</p>' +
        '<div class="v6719-callout tip"><strong>Credential safety</strong>Credentials are stored obfuscated, never in plain text. The bot never types your password into web forms or shares it.</div>'
    },
    {
      id: "race-solver", group: "Core Features", nav: "Smart Race Solver", eyebrow: "The race brain",
      html:
        '<h2>Smart Race Solver</h2>' +
        '<p>This is the heart of the bot: it decides <strong>which races to enter and when</strong> across the whole career, aiming to maximize fans and race accolades (epithets) while keeping the trainee competitive.</p>' +
        '<h3>Where the race data comes from</h3>' +
        '<p>The bot works from a calendar of every race in the game, kept in sync with a community-maintained race database. That calendar is the same pool for every trainee. What makes your schedule unique is the filtering: your live aptitudes, your character profile (epithet goals and overrides), and your past race outcomes all shape which races get picked from the pool.</p>' +
        '<h3>How it chooses</h3>' +
        '<p>Every candidate race is scored by its fan value, its epithet value, and its cost, then the solver picks the best set that fits the rules you have set. By default it solves the whole schedule <strong>once</strong> and reuses it, re-planning only when something real changes (see Re-planning below) so the plan stays stable instead of churning every turn.</p>' +
        '<h3>Key settings</h3>' +
        '<table class="v6719-help-table">' +
        '<tr><th>Setting</th><th>What it does</th></tr>' +
        '<tr><td>Max Streak</td><td>The most races allowed back-to-back. Higher means more total races. This is the biggest lever on race count.</td></tr>' +
        '<tr><td>Include OP races</td><td>Adds Open and Pre-OP races to the pool, giving more opportunities to fill the calendar.</td></tr>' +
        '<tr><td>Aptitude floor</td><td>The lowest aptitude grade a race may be and still be considered (for example C). Stricter means fewer but safer races.</td></tr>' +
        '<tr><td>Optimization weights</td><td>Fine-tune what the solver values — fan weight, epithet value, race cost, and related knobs.</td></tr>' +
        '</table>' +
        '<div class="v6719-callout key"><strong>Tuning race count</strong>For a typical Mile/Medium trainee, Max Streak 5 schedules roughly 37 races and Max Streak 8 reaches about 41. Set it to the number of races you actually want, then let the solver fill the calendar.</div>' +
        '<div class="v6719-callout warn"><strong>Races trade against training</strong>Every race uses a turn that could have been training. More races means higher fans but fewer training turns and therefore lower stats. Decide which you are optimizing for.</div>' +
        '<h3>Re-planning (when the schedule rebuilds)</h3>' +
        '<p>The solver follows an event-driven model. <strong>Re-Plan Only on Race Events</strong> (on by default) means the plan is built once and reused; it only rebuilds when a race is <strong>lost</strong> or a planned race becomes <strong>unavailable</strong>. Winning a race keeps the plan. <strong>Disable Schedule Re-Plan Upon Race Loss</strong> goes one step further and keeps the original plan even after a loss. Together these stop the constant re-solving that used to let race streaks pile up past your Max Streak. Leave both at their defaults unless you specifically want the older every-turn behavior (turn the event-only toggle off to restore it).</p>' +
        '<div class="v6719-callout warn"><strong>Energy and streaks</strong>The solver caps consecutive races at your Max Streak, but if you turn on <strong>Ignore Low Energy Racing Block</strong> and set the energy threshold to 0, the bot will keep racing at 0 energy — which loses races and wastes the schedule. For a high win rate, leave energy management on and set a sensible threshold (around 30); the bot rests when low, like a careful manual player would.</div>' +
        '<h3>Smart vs. Manual selection</h3>' +
        '<p>The race mode toggle offers two approaches. ' + KW('SMART RACE SOLVER') + ' is the automatic planner described above — it builds and re-solves the whole schedule for you. ' + KW('MANUAL SELECTION') + ' instead lets you pick exactly which races the bot will enter. Use Smart for hands-off optimization; use Manual when you want full control over the race list.</p>'
    },
    {
      id: "training", group: "Core Features", nav: "Training", eyebrow: "Stat decisions",
      html:
        '<h2>Training</h2>' +
        '<p>The Training Settings panel controls how the bot trains on non-race turns.</p>' +
        '<h3>Prioritization</h3>' +
        '<p>The <strong>stat priority</strong> is the order the bot prefers to train. On each turn it trains the highest-priority stat that is below target and has good conditions (mood, low failure risk, useful support cards present). This is the order the bot actually follows in the default scorer mode.</p>' +
        '<h3>Blacklist</h3>' +
        '<p>Stats on the blacklist are never trained, unless a skill-hint override is enabled. Use it to hard-exclude a stat you do not want touched.</p>' +
        '<h3>Stat targets</h3>' +
        '<p>Targets are per-stat goals that tell the bot what to prioritize. They are <strong>aspirational guides, not guarantees</strong> — if you race a lot, there may not be enough training turns to reach every target, and that is expected, not a malfunction.</p>' +
        '<h3>Event &amp; summer priorities</h3>' +
        '<p><strong>Event Choice Prioritization</strong> is the stat order used when scoring story-event options. <strong>Summer Training Prioritization</strong> is the order used during the summer camp, when training behaves differently.</p>' +
        '<h3>Failure tolerance</h3>' +
        '<p>Set the maximum failure chance the bot will accept on a training, and whether risky training is allowed at all.</p>' +
        '<h3>Energy, rest &amp; mood</h3>' +
        '<p>Training spends energy, and low energy raises failure chance and weakens races. Unless you have disabled the low-energy block, the bot will <strong>rest</strong> or take <strong>recreation</strong> when energy or mood is low rather than train into a likely failure. Keeping this behavior on is what lets it both train and race effectively — see the energy note under Smart Race Solver.</p>' +
        '<p>The controls for this live outside Training Settings: <strong>Ignore Low Energy Racing Block</strong> is in <strong>Racing Settings</strong>, and <strong>Energy Threshold to use Energy Items</strong> is in <strong>Scenario Settings</strong>.</p>' +
        '<div class="v6719-callout tip"><strong>Where priority lives</strong>In the default (hint) scorer mode, the priority you set <strong>here</strong> is what drives training. A character profile can carry its own separate priority that only takes over in authoritative mode — see Character profiles.</div>'
    },
    {
      id: "profiles", group: "Core Features", nav: "Character profiles", eyebrow: "Per-character",
      html:
        '<h2>Character profiles</h2>' +
        '<p>A character profile is per-character tuning that layers underneath your preset. It lets one character behave differently from your global settings without you reconfiguring everything.</p>' +
        '<h3>Scorer modes</h3>' +
        '<table class="v6719-help-table">' +
        '<tr><th>Mode</th><th>Who decides training</th></tr>' +
        '<tr><td>Hint</td><td>The profile suggests, but your Training Settings drive the actual picks. This is the default.</td></tr>' +
        '<tr><td>Authoritative</td><td>The profile scorer overrides your Training Settings for training decisions.</td></tr>' +
        '<tr><td>Disabled</td><td>The profile scorer is off entirely.</td></tr>' +
        '</table>' +
        '<h3>Epithets</h3>' +
        '<p>Profiles can carry epithet goals — specific race accolades the solver will try to earn for that character by routing the schedule toward the required races.</p>' +
        '<div class="v6719-callout tip"><strong>When to touch this</strong>Only edit a profile if you want behavior for one character that differs from your global settings. Otherwise the defaults are fine and your Training Settings remain in charge.</div>'
    },
    {
      id: "run-controls", group: "Core Features", nav: "Run controls & toggles", eyebrow: "The control bar",
      html:
        '<h2>Run controls &amp; toggles</h2>' +
        '<p>The small buttons along the top control bar govern how a run starts, stops, and paces itself. None of them change strategy — they change how the bot executes.</p>' +
        '<h3>Start, stop, pause</h3>' +
        '<p>' + KW('RUN CAREER') + ' begins a run on the active preset. ' + KW('STOP') + ' halts it cleanly, and ' + KW('PAUSE') + ' suspends it so you can resume where it left off — useful if you need to take manual control of the game for a moment.</p>' +
        '<h3>Turn delay &amp; Speed</h3>' +
        '<p>Between turns the bot waits a randomized amount of time (by default about 1.6–3.7 seconds) so its pacing looks human rather than instant and mechanical. You can set your own minimum and maximum delay. The ' + KW('SPEED') + ' dropdown picks how aggressive to be: <strong>Safe</strong> keeps the normal delays; <strong>Fast</strong> removes the inter-turn delay; <strong>Faster</strong> also trims the per-request spacing; <strong>Ludicrous</strong> removes all pacing for maximum speed. Higher speed = more careers per hour, but the less human-like the activity looks.</p>' +
        '<h3>Burn Clocks</h3>' +
        '<p>When a race finishes worse than first, the bot can retry it by spending <strong>clocks</strong>. Free continues are always used when available. ' + KW('BURN CLOCKS') + ' controls whether the bot will <strong>also spend paid clocks</strong> to retry for a better placement. It is off by default so it never quietly consumes paid resources; turn it on when you want the bot to push harder for race wins.</p>' +
        '<h3>Loop</h3>' +
        '<p>' + KW('LOOP') + ' makes the bot automatically start a fresh career after one finishes, for unattended back-to-back runs. It is <strong>on by default</strong> (set to run until you stop it); set ' + KW('RUNS') + ' to <strong>1</strong> if you want a single career and a chance to review it before the next begins, or to any number for that many careers.</p>' +
        '<h3>Rescue a stuck career</h3>' +
        '<p>If a run desyncs from the game and gets stuck, ' + KW('RESCUE STUCK CAREER') + ' (in Diagnostics) attempts to recover it. The runner must be stopped first.</p>' +
        '<h3>Notifications</h3>' +
        '<p>Add a Discord webhook URL to receive notifications about run events such as career completion. Save it, then use Test to confirm it works. Leave it blank to keep notifications off.</p>' +
        '<div class="v6719-callout tip"><strong>Other settings panels</strong>' + KW('SCENARIO OVERRIDES') + ' adjusts scenario-specific behavior, and ' + KW('EVENT CHOICES') + ' lets you customize how individual story events are answered beyond the default stat-priority scoring. Most runs never need either.</div>'
    },
    {
      id: "ai-learning", group: "Intelligence", nav: "AI / Misc", eyebrow: "Learns over time",
      html:
        '<h2>AI / Misc</h2>' +
        '<p>The ' + KW('AI / MISC') + ' panel governs the data the bot records from your careers and the optional ways it can turn that data into better decisions. There are three layers here, from always-on and safe to fully optional and experimental. You can ignore all of it and the bot still runs well on its solver and training rules — this layer is an addition, not the foundation.</p>' +
        '<h3>1. Outcome risk (on by default)</h3>' +
        '<p>The bot keeps a local record of how each race has gone for you. The solver uses it to <strong>penalize races that historically went badly</strong>, steering away from likely losses. This is simple, safe, and on by default. It is statistical only — no model is involved — and it is independent of the predictive layers below.</p>' +
        '<h3>2. Shadow Mode &amp; Live Policy Assistance (LPA)</h3>' +
        '<p>As you run careers, the bot can train a small local model on the outcomes and let it <strong>predict</strong> good decisions. Before that model is ever allowed to affect a run, it goes through <strong>Shadow Mode</strong>: it makes predictions silently and they are scored against what actually happened. The accuracy of those silent predictions is its <strong>shadow precision</strong>.</p>' +
        '<p><strong>Live Policy Assistance</strong> is the switch that lets those learned hints <em>gently</em> adjust the Smart Race Solver\'s candidate scores. It is gated by shadow precision: until the model is reliable enough (the panel shows a recommendation and a readiness state), LPA stays off and changes nothing. Even when on, it only nudges scores among already-legal options — it never bypasses race availability, safety gates, or forced game states.</p>' +
        '<div class="v6719-callout key"><strong>How to use it</strong>Leave LPA <strong>off</strong> until the panel reports it is safe — realistically after many careers across several trainees. Watch the Shadow Mode readout to see precision climb. Flip LPA on only once the recommendation says it is ready; turn it back off if results get worse.</div>' +
        '<p><strong>Reading precision.</strong> A <em>warning</em> is a race the model wanted to penalize; it counts as <em>useful</em> if that race then finished below 1st, or a <em>false alarm</em> if it won anyway. <strong>Precision = useful / (useful + false alarms)</strong> — the share of warnings that were justified. Low precision means the model is flagging races you actually win.</p>' +
        '<p><strong>Tuning precision (advanced).</strong> Two auto-config knobs control how selective the warnings are. <code>warn_win_rate_ceiling</code> (default <code>0.50</code>) only lets a race generate a warning when its historical win rate is at or below the ceiling — lower it (e.g. <code>0.35</code>) to warn only on races that lose most of the time, which raises precision. <code>min_samples_for_model</code> (default <code>4</code>) sets how many recorded runs a race needs before it can warn at all, filtering noisy one-off losses. Both live in the AI auto-config; raising either trades fewer warnings for higher precision.</p>' +
        '<h3>3. Local LLM advisor (optional, advisory-only)</h3>' +
        '<p>You can connect a <strong>local large language model</strong> — running on your own machine — to read your career logs and comment on them. It is strictly an <strong>advisor</strong>: it analyzes logs and shadow-reviews decisions and writes up what it sees. It <strong>cannot click anything or control the runner</strong>; it has no path to drive the bot directly. Think of it as an analyst that reads the same logs you do and writes a second opinion.</p>' +
        '<h4>Setting it up</h4>' +
        '<ol class="v6719-steps">' +
        '<li><strong>Run a local model server.</strong> The easiest options are <strong>LM Studio</strong> or <strong>Ollama</strong>. Install one, download a chat model (a small 7–8B instruct model is plenty), and start its local server. Both expose an OpenAI-compatible API.</li>' +
        '<li><strong>Open ' + KW('AI / MISC') + ' → Local LLM</strong> and set <strong>Provider</strong> to LM Studio, Ollama, or Custom.</li>' +
        '<li><strong>Set the Base URL.</strong> LM Studio defaults to <code>http://localhost:1234/v1</code>; Ollama to <code>http://localhost:11434/v1</code>. For Custom, paste any OpenAI-compatible endpoint. An API key is only needed for endpoints that require one — local servers usually do not.</li>' +
        '<li><strong>Set the Model</strong> name to the model you loaded (as the server reports it).</li>' +
        '<li><strong>Pick a Mode</strong> (below), then <strong>Save</strong>. Use <strong>ANALYZE</strong> for a post-run write-up, or <strong>SHADOW REVIEW</strong> to have it second-guess recent turns.</li>' +
        '</ol>' +
        '<h4>Modes</h4>' +
        '<table class="v6719-help-table">' +
        '<tr><th>Mode</th><th>What it does</th></tr>' +
        '<tr><td>Off</td><td>The LLM is not contacted at all.</td></tr>' +
        '<tr><td>Offline Analysis</td><td>On request, it reads finished-career logs and writes a plain-language review. Nothing happens during a run.</td></tr>' +
        '<tr><td>Shadow Advisor</td><td>It reviews recent turns and records what it would have done, for you to compare. Still no effect on the run.</td></tr>' +
        '<tr><td>Recommend Only</td><td>Same as shadow, but its suggestions are surfaced more prominently as recommendations. It still never acts on its own.</td></tr>' +
        '</table>' +
        '<h4>How it could eventually influence decisions</h4>' +
        '<p>Today the LLM only produces text for you to read. The path by which AI ever nudges a live run is the <strong>Live Policy Assistance</strong> gate above — the small learned model, vetted by shadow precision — not the LLM. The LLM\'s value is interpretation: spotting patterns across logs, explaining why a run underperformed, and suggesting settings you then choose to apply. If a future version lets vetted advice feed the solver, it would go through that same precision-gated, score-nudging-only path, never direct control.</p>' +
        '<div class="v6719-callout tip"><strong>Recommendation</strong>If you do not run a local model, leave this <strong>Off</strong> — it changes nothing. If you do, <strong>Offline Analysis</strong> is the most useful setting: run a career, then hit ANALYZE for a readable post-mortem. Treat its output as a knowledgeable opinion to sanity-check, not as instructions.</div>' +
        '<div class="v6719-callout warn"><strong>Recommended posture</strong>Keep LPA and any LLM influence off until you have many careers across several trainees. The bot performs well on the solver and training rules alone; the learned layers are refinements on top.</div>'
    },
    {
      id: "items-skills", group: "Intelligence", nav: "Items & skills", eyebrow: "Automatic spend",
      html:
        '<h2>Items &amp; skills</h2>' +
        '<h3>Item use</h3>' +
        '<p>The item manager uses scenario items automatically — energy drinks, training megaphones, stat manuals, snacks, and the like — choosing what helps in the current situation. You will see the items it used listed in the Decision Reasoning for each turn.</p>' +
        '<h3>Skill buying</h3>' +
        '<p>The skill buyer spends skill points on recommended skills for your character, prioritizing the ones that matter for her running style and distances. It buys when it makes sense rather than hoarding points to the end.</p>' +
        '<div class="v6719-callout tip"><strong>Recovery skills matter</strong>For stamina-hungry runs, a gold recovery skill effectively lowers the stamina you need to clear races. If your character can learn one, it is often the most valuable purchase.</div>'
    },
    {
      id: "event-choices", group: "Intelligence", nav: "Event choices", eyebrow: "Story decisions",
      html:
        '<h2>Event choices</h2>' +
        '<p>During a career, story events pop up that ask you to pick an option. The ' + KW('EVENT CHOICES') + ' panel is where you control how the bot answers them. Each option in Umamusume gives different rewards — stats, skill hints, energy, mood — and the right pick depends on what you are building.</p>' +
        '<h3>How the bot decides (left on "Auto")</h3>' +
        '<p>By default every event is set to <strong>Auto</strong>, and the bot picks in this order: a few game-critical events have hardcoded correct answers; otherwise it <strong>scores the options</strong> using the known effects (from the gametora + master.mdb event database) against your <strong>Event Choice Prioritization</strong> stat order and picks the best; if it has no data for that event, it falls back to a safe default (the second option when there are several). So on Auto it is already making a reasonable, stat-aware choice.</p>' +
        '<h3>What the panel shows</h3>' +
        '<p>Each row lists the event, how often it has been seen, what the bot would auto-pick, and — where the database knows them — <strong>the effects of each choice</strong> (green for gains, red for losses). The dropdown lets you read those effects and choose. Events labelled <em>effect not in database</em> simply have no recorded outcome data yet; the gametora + master.mdb event database may simply not list it yet.</p>' +
        '<h3>Overriding a choice</h3>' +
        '<p>Pick a specific <strong>Choice</strong> from the dropdown to force it every time that event appears; pick <strong>Auto</strong> to hand the decision back to the bot. Overrides win over the automatic scoring, so this is how you guarantee, say, always taking the energy option or a particular skill hint. Overrides are saved immediately and persist across runs.</p>' +
        '<div class="v6719-callout tip"><strong>Is it affecting my runs?</strong>Left on Auto, Event Choices changes nothing about how the bot already behaves — it is just exposing and letting you override decisions the bot was making anyway. It will not break a run or get it stuck. Most runs never need an override; reach for it only when you want a specific event answered a specific way.</div>'
    },
    {
      id: "history-reasoning", group: "Intelligence", nav: "History & reasoning", eyebrow: "See the why",
      html:
        '<h2>Career history &amp; decision reasoning</h2>' +
        '<h3>Career history</h3>' +
        '<p>The ' + KW('CAREER HISTORY') + ' panel lets you browse completed runs — final stats, aptitudes, sparks, skills, and the full race list. Each run is a card; <strong>VIEW DETAILS</strong> opens a <strong>Race History</strong> breakdown of every race that career ran: grade, venue, surface and distance, the in-game date, your finishing place, fans earned, and — uniquely — the <strong>stats and energy you had at the moment of each race</strong>. That energy column is the fastest way to spot a run that raced itself into the ground at 0 energy. It is the record to share when asking why a run turned out a certain way.</p>' +
        '<h3>Decision reasoning</h3>' +
        '<p>The Decision Reasoning panel is the most useful tool for understanding and tuning the bot. For each turn it shows <strong>why</strong> the action was chosen: which stat priority applied, how far the stat was from its target, whether the scorer agreed, and which items were used. If the bot is doing something you did not expect, this is where you find out why.</p>' +
        '<div class="v6719-callout tip"><strong>Reading priority correctly</strong>In the default hint mode, the priority shown in Decision Reasoning is the one from your Training Settings — the order the bot actually used that turn.</div>' +
        '<p>The panel <strong>tail-follows</strong> the live run: while it is scrolled to the bottom, new turns keep it pinned there. Scroll up to read an earlier turn and it pauses so it will not yank you back; scroll to the bottom again to resume following. Clicking a card (here or in the Action Log) focuses that turn.</p>'
    },
    {
      id: "diagnostics", group: "Intelligence", nav: "Diagnostics", eyebrow: "Health check",
      html:
        '<h2>Diagnostics</h2>' +
        '<p>The ' + KW('DIAGNOSTICS') + ' panel confirms the bot is connected and reading the game correctly: connection status, the current turn, and basic health checks. Open it first whenever something seems stuck — it tells you whether the bot is actually attached to the game and seeing live state.</p>'
    },
    {
      id: "tips", group: "Strategy", nav: "Strategy & tips", eyebrow: "Play better",
      html:
        '<h2>Strategy &amp; tips</h2>' +
        '<p>A few gameplay realities that shape what the bot can achieve. These are levers outside the bot as much as inside it.</p>' +
        '<h3>Parent sparks are the real stat lever</h3>' +
        '<p>The two umamusume you inherit from grant starting-stat bonuses (blue sparks) that are completely separate from your support deck. A trainee with strong stat sparks begins far ahead and needs less training to reach high stats — which frees turns to race more. If you want both high stats and high fans, strong parent sparks are usually the missing ingredient.</p>' +
        '<h3>Race count versus stats is a real tradeoff</h3>' +
        '<p>Turns are finite. Every race is a turn not spent training. You cannot maximize both — decide whether a given run is chasing fans (race more, accept lower stats) or stats (race less). Raising race count will lower stats somewhat, by design.</p>' +
        '<h3>Set realistic race targets</h3>' +
        '<p>Depending on the trainee and your Max Streak, somewhere around 30 to 41 races is a typical, healthy range. Aim there rather than at an outlier number.</p>' +
        '<h3>Match the deck and sparks to the character</h3>' +
        '<p>Align your support deck and parent sparks with the character preferred distances and running style. The bot can only work with the aptitudes and stats the build provides.</p>'
    },
    {
      id: "faq", group: "Strategy", nav: "Troubleshooting", eyebrow: "Common questions",
      html:
        '<h2>Troubleshooting &amp; FAQ</h2>' +
        '<h3>My race count is too low</h3>' +
        '<p>Raise <strong>Max Streak</strong> in Smart Race Solver Settings. For a Mile/Medium trainee, 8 is a good target for around 41 races. Confirm your solver settings are saved in the panel.</p>' +
        '<h3>Stats fall short of their targets</h3>' +
        '<p>Expected when you race a lot — targets are guides, and there may not be enough training turns to reach all of them. Hitting every target while racing heavily is not possible from training alone; parent sparks make up the rest.</p>' +
        '<h3>Decision Reasoning shows a different priority than my settings</h3>' +
        '<p>In the default hint mode it shows the priority from your Training Settings, which is what the bot used. A character profile keeps its own separate priority that only applies in authoritative mode.</p>' +
        '<h3>Should I reset the AI learning data?</h3>' +
        '<p>Yes, if earlier runs were recorded under settings you have since corrected — stale outcome history can steer the solver away from races that are now winnable. Resetting archives the old data rather than deleting it.</p>' +
        '<h3>Do I have to log in after every update?</h3>' +
        '<p>No. Authentication is saved in the external userdata folder and reused across upgrades.</p>' +
        '<h3>My win rate is low / the bot raced many times in a row at 0 energy</h3>' +
        '<p>Check two things. First, leave <strong>Re-Plan Only on Race Events</strong> on (Smart Race Solver) so the schedule does not churn and overrun your Max Streak. Second, turn <strong>off</strong> Ignore Low Energy Racing Block and set an energy threshold around 30 — racing at 0 energy loses races. A careful build rests when low and wins more, even if it runs slightly fewer races.</p>' +
        '<h3>How do I change what the bot picks in a story event?</h3>' +
        '<p>Open Event Choices, find the event, and pick a Choice from its dropdown (the effects of each option are shown where known). Pick Auto to let the bot decide. See the Event choices topic.</p>' +
        '<h3>Can I connect my own local AI model?</h3>' +
        '<p>Yes — see AI / Misc → Local LLM advisor. Run LM Studio or Ollama, point the panel at its local URL, and use Offline Analysis for a post-run review. It only reads logs and comments; it cannot control the bot.</p>' +
        '<h3>Steam login says "rate limit exceeded" or won\'t accept my 2FA code</h3>' +
        '<p>That message comes from <strong>Steam</strong>, not the bot — Steam temporarily blocks sign-ins after several failed or rapid attempts. Wait about <strong>15-30 minutes</strong>, then try once with the correct password and a <strong>fresh</strong> Steam Guard code (codes refresh every 30 seconds). After a failed attempt the login button has a short cool-down so quick retries don\'t make the lockout worse.</p>' +
        '<h3>A career failed to start (error 2511, or a 500 / 501)</h3>' +
        '<p><strong>2511</strong> means the support deck had too many cards; Icarus now trims it automatically to a legal six (five of yours plus one borrowed friend). A <strong>500 / 501</strong> is usually a brief server hiccup or an invalid selection — if it mentions a guest parent, that rental likely expired or was used up for the day, so Refresh Guest Parents and reselect before trying again.</p>' +
        '<div class="v6719-callout tip"><strong>Still stuck?</strong>Open Diagnostics to confirm the bot is connected, then check Decision Reasoning to see what it is deciding and why. Those two panels explain most surprises.</div>'
    },
  ];

  function buildContent(host) {
    var inner = document.createElement("div");
    inner.className = "v6719-help-content-inner";

    var hero = document.createElement("div");
    hero.className = "v6719-help-hero";
    hero.innerHTML =
      "<h1>Icarus documentation</h1>" +
      "<p>A guide to every major part of the bot — what each panel does, how to use it, and how the pieces fit together. Use the menu on the left or the search box to jump to a topic.</p>";
    inner.appendChild(hero);

    SECTIONS.forEach(function (s) {
      var sec = document.createElement("section");
      sec.className = "v6719-help-section";
      sec.id = "v6719-doc-" + s.id;
      sec.setAttribute("data-doc-id", s.id);
      var search = (s.nav + " " + s.html).replace(/<[^>]+>/g, " ").toLowerCase();
      sec.setAttribute("data-search", search);
      sec.innerHTML =
        '<span class="v6719-help-eyebrow">' + s.eyebrow + "</span>" + s.html;
      inner.appendChild(sec);
    });

    var empty = document.createElement("div");
    empty.className = "v6719-help-empty";
    empty.id = "v6719-help-empty";
    empty.textContent = "No sections match your search.";
    inner.appendChild(empty);

    host.appendChild(inner);
  }

  function buildNav(host) {
    var lastGroup = null;
    SECTIONS.forEach(function (s) {
      if (s.group !== lastGroup) {
        var g = document.createElement("div");
        g.className = "v6719-help-nav-group";
        g.textContent = s.group;
        host.appendChild(g);
        lastGroup = s.group;
      }
      var a = document.createElement("a");
      a.className = "v6719-help-nav-link";
      a.textContent = s.nav;
      a.href = "#v6719-doc-" + s.id;
      a.setAttribute("data-target", "v6719-doc-" + s.id);
      host.appendChild(a);
    });
  }

  var initialized = false;
  function init() {
    if (initialized) return;
    var modal = document.getElementById("v6719-help-modal");
    var content = document.getElementById("v6719-help-content");
    var navList = document.getElementById("v6719-help-nav-list");
    if (!modal || !content || !navList) return;
    initialized = true;

    buildContent(content);
    buildNav(navList);

    var links = Array.prototype.slice.call(
      navList.querySelectorAll(".v6719-help-nav-link")
    );
    var sections = Array.prototype.slice.call(
      content.querySelectorAll(".v6719-help-section")
    );

    // Smooth-scroll nav clicks within the content pane (no URL hash jump).
    links.forEach(function (link) {
      link.addEventListener("click", function (ev) {
        ev.preventDefault();
        var target = document.getElementById(link.getAttribute("data-target"));
        if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });

    // Scroll-spy: highlight the section currently in view.
    function setActive(id) {
      links.forEach(function (l) {
        l.classList.toggle("is-active", l.getAttribute("data-target") === id);
      });
    }
    if ("IntersectionObserver" in window) {
      var spy = new IntersectionObserver(
        function (entries) {
          entries.forEach(function (e) {
            if (e.isIntersecting) setActive(e.target.id);
          });
        },
        { root: content, rootMargin: "0px 0px -70% 0px", threshold: 0 }
      );
      sections.forEach(function (sec) { spy.observe(sec); });
    }
    if (links[0]) links[0].classList.add("is-active");

    // Search: filter sections (and their nav links) by text.
    var searchInput = document.getElementById("v6719-help-search");
    var empty = document.getElementById("v6719-help-empty");
    if (searchInput) {
      searchInput.addEventListener("input", function () {
        var q = searchInput.value.trim().toLowerCase();
        var anyShown = false;
        sections.forEach(function (sec) {
          var hit = !q || (sec.getAttribute("data-search") || "").indexOf(q) !== -1;
          sec.classList.toggle("is-hidden", !hit);
          if (hit) anyShown = true;
          var link = links.filter(function (l) {
            return l.getAttribute("data-target") === sec.id;
          })[0];
          if (link) link.classList.toggle("is-hidden", !hit);
        });
        if (empty) empty.classList.toggle("is-shown", !anyShown);
      });
    }
  }

  function openModal() {
    init();
    var modal = document.getElementById("v6719-help-modal");
    if (modal) {
      modal.style.display = "flex";
      var content = document.getElementById("v6719-help-content");
      if (content) content.scrollTop = 0;
    }
  }
  function closeModal() {
    var modal = document.getElementById("v6719-help-modal");
    if (modal) modal.style.display = "none";
  }

  function wire() {
    var btn = document.getElementById("v6719-help-btn");
    var doneBtn = document.getElementById("v6719-help-done-btn");
    var modal = document.getElementById("v6719-help-modal");
    if (btn && !btn.dataset.v6719Bound) {
      btn.addEventListener("click", openModal);
      btn.dataset.v6719Bound = "1";
    }
    if (doneBtn && !doneBtn.dataset.v6719Bound) {
      doneBtn.addEventListener("click", closeModal);
      doneBtn.dataset.v6719Bound = "1";
    }
    if (modal && !modal.dataset.v6719Bound) {
      modal.addEventListener("click", function (ev) {
        if (ev.target === modal) closeModal();
      });
      modal.dataset.v6719Bound = "1";
    }
    if (!document.body.dataset.v6719EscBound) {
      document.addEventListener("keydown", function (ev) {
        if (ev.key === "Escape" && modal && modal.style.display === "flex") closeModal();
      });
      document.body.dataset.v6719EscBound = "1";
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wire);
  } else {
    wire();
  }
})();


// ===========================================================================
// v7.1 — Userdata folder setup popup.
//
// Shows on first dashboard load after Steam auth and whenever the userdata
// resolver flags a detection problem (pointer file references a folder that
// doesn't exist, or we've fallen back to the in-build directory).
//
// Independent of the help modal IIFE above so it can't accidentally break
// anything that was already working.
// ===========================================================================
(function () {
  var _info = null;
  var _wired = false;

  function $(id) { return document.getElementById(id); }

  function setText(id, value) {
    var el = $(id);
    if (el) el.textContent = value == null ? "" : String(value);
  }

  function sourceLabel(src) {
    switch (src) {
      case "env_icarus": return "$ICARUS_USERDATA_DIR (env var)";
      case "env_legacy_sweepycl": return "$SWEEPYCL_USERDATA_DIR (legacy env var)";
      case "env_legacy_sweepyclaude": return "$SWEEPYCLAUDE_USERDATA_DIR (legacy env var)";
      case "pointer_file": return "Cross-version pointer file";
      case "sibling_icarus": return "../Icarus_userdata (sibling folder)";
      case "sibling_legacy_sweepycl": return "../SweepyCL_userdata (legacy sibling folder)";
      case "sibling_legacy_sweepyclaude": return "../SweepyClaude_userdata (legacy sibling folder)";
      case "fallback_build_dir": return "In-build folder (not persistent across upgrades)";
      default: return src || "unknown";
    }
  }

  async function fetchInfo() {
    try {
      var res = await fetch("/api/userdata/info?t=" + Date.now());
      var data = await res.json();
      _info = data;
      return data;
    } catch (e) {
      console.warn("userdata info fetch failed:", e);
      return null;
    }
  }

  function renderInfo(info) {
    if (!info) return;
    setText("v71-userdata-current-path", info.current_path || "(none)");
    setText("v71-userdata-current-source", sourceLabel(info.current_source));
    setText("v71-userdata-pointer-path", info.pointer_file || "(none)");
    setText("v71-userdata-pointer-path-2", info.pointer_file || "");
    // Warning block
    var warnEl = $("v71-userdata-warning");
    if (warnEl) {
      var pieces = [];
      if (info.detection_warning) pieces.push(info.detection_warning);
      if (info.restart_required) pieces.push("Path changed in this session. Restart Icarus for the new location to take full effect.");
      if (info.is_fallback_build_dir) pieces.push("You're using the in-build folder. Settings will be lost on the next version unless you overwrite the same folder.");
      if (info.is_legacy_path) pieces.push("Currently resolving via a legacy Pre Icarus/Pre Icarus path. This still works; set an Icarus path here to migrate cleanly.");
      if (pieces.length) {
        warnEl.innerHTML = pieces.map(function (p) { return '<div class="v71-userdata-warning-line">⚠ ' + escapeHtmlSafe(p) + '</div>'; }).join("");
        warnEl.style.display = "";
      } else {
        warnEl.innerHTML = "";
        warnEl.style.display = "none";
      }
    }
    // Pre-fill input if pointer is set
    var input = $("v71-userdata-path-input");
    if (input && !input.dataset.v71UserTouched) {
      input.value = info.pointer_target || info.current_path || "";
    }
    // v7.1.1 — keep the Diagnostics fallback card in sync.
    renderDiagnosticsCard(info);
  }

  function escapeHtmlSafe(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function openModal() {
    var modal = $("v71-userdata-modal");
    if (modal) modal.style.display = "flex";
    fetchInfo().then(renderInfo);
  }

  function closeModal() {
    var modal = $("v71-userdata-modal");
    if (modal) modal.style.display = "none";
    // v7.4 — let the changelog popup know the userdata flow is resolved so it
    // can show after this modal (and never on top of it).
    try { document.dispatchEvent(new CustomEvent("sweepycl:userdata-closed")); } catch (e) {}
  }

  async function applyPath() {
    var input = $("v71-userdata-path-input");
    var migrateChk = $("v71-userdata-migrate-checkbox");
    var statusEl = $("v71-userdata-status-msg");
    if (!input) return;
    var path = (input.value || "").trim();
    if (!path) {
      if (statusEl) statusEl.textContent = "Enter a folder path first.";
      return;
    }
    var btn = $("v71-userdata-apply-btn");
    if (btn) btn.disabled = true;
    if (statusEl) statusEl.textContent = "Saving path...";
    try {
      var res = await fetch("/api/userdata/set-path", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          path: path,
          migrate_current: !!(migrateChk && migrateChk.checked),
        }),
      });
      var data = await res.json();
      if (!res.ok || !data.success) {
        if (statusEl) statusEl.textContent = (data && data.detail) || ("Failed: HTTP " + res.status);
        return;
      }
      _info = data;
      renderInfo(data);
      var msgParts = ["✔ Saved."];
      if (typeof data.migrated_files === "number" && data.migrated_files > 0) {
        msgParts.push("Copied " + data.migrated_files + " file(s) to the new folder.");
      }
      msgParts.push("Restart Icarus for the new path to take full effect.");
      if (statusEl) statusEl.textContent = msgParts.join(" ");
    } catch (e) {
      if (statusEl) statusEl.textContent = "Failed: " + (e && e.message ? e.message : e);
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  async function dismissIntro() {
    var suppress = false;
    var cb = $("v71-userdata-dontshow-checkbox");
    if (cb) suppress = !!cb.checked;
    try {
      await fetch("/api/userdata/intro-dismissed", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dont_show_again: true, suppress_permanently: suppress }),
      });
    } catch (e) { /* non-fatal */ }
    closeModal();
  }

  function useSuggested() {
    var input = $("v71-userdata-path-input");
    if (input && _info && _info.suggested_sibling) {
      input.value = _info.suggested_sibling;
      input.dataset.v71UserTouched = "1";
      input.focus();
    }
  }

  // v7.1.1 — Inject a fallback card into the Diagnostics modal so the
  // userdata setup is always reachable even if the top-bar USERDATA button
  // is hidden, obscured, or the user hasn't found it yet. The card shows
  // the current resolution state inline and offers a button to reopen the
  // full popup.
  function injectDiagnosticsCard() {
    var diagBody = document.getElementById("v516-diagnostics-body");
    if (!diagBody) return;
    if (document.getElementById("v71-userdata-diag-card")) return;  // already injected
    var card = document.createElement("div");
    card.id = "v71-userdata-diag-card";
    card.className = "v71-userdata-diag-card";
    card.innerHTML =
      '<div class="v71-userdata-diag-head">' +
        '<h3>Userdata Folder</h3>' +
        '<button id="v71-userdata-diag-open-btn" class="btn btn-sm v4-small-btn" type="button">OPEN USERDATA SETUP</button>' +
      '</div>' +
      '<div class="v71-userdata-diag-body">' +
        '<div class="v71-userdata-diag-row"><span>Current path</span><code id="v71-userdata-diag-path">(loading...)</code></div>' +
        '<div class="v71-userdata-diag-row"><span>Resolved via</span><code id="v71-userdata-diag-source">(loading...)</code></div>' +
        '<div class="v71-userdata-diag-row"><span>Pointer file</span><code id="v71-userdata-diag-pointer">(loading...)</code></div>' +
        '<div id="v71-userdata-diag-warning" class="v71-userdata-diag-warning" style="display: none;"></div>' +
        '<div class="v71-userdata-diag-hint">This is where your settings, presets, and Steam auth live. Use the button above to view or change the userdata folder.</div>' +
      '</div>';
    diagBody.appendChild(card);
    // Wire the reopen button
    var openBtn = document.getElementById("v71-userdata-diag-open-btn");
    if (openBtn) openBtn.addEventListener("click", openModal);
    // Populate now
    renderDiagnosticsCard(_info);
  }

  function renderDiagnosticsCard(info) {
    if (!info) return;
    setText("v71-userdata-diag-path", info.current_path || "(none)");
    setText("v71-userdata-diag-source", sourceLabel(info.current_source));
    setText("v71-userdata-diag-pointer", info.pointer_target || "(not set)");
    var warnEl = document.getElementById("v71-userdata-diag-warning");
    if (warnEl) {
      var msgs = [];
      if (info.detection_warning) msgs.push(info.detection_warning);
      if (info.is_fallback_build_dir) msgs.push("Falling back to the in-build folder. Settings won't survive a clean upgrade.");
      if (info.restart_required) msgs.push("Path changed this session. Restart Icarus for it to take full effect.");
      if (msgs.length) {
        warnEl.innerHTML = msgs.map(function (m) { return '<div>⚠ ' + escapeHtmlSafe(m) + '</div>'; }).join("");
        warnEl.style.display = "";
      } else {
        warnEl.innerHTML = "";
        warnEl.style.display = "none";
      }
    }
  }

  function bind() {
    if (_wired) return;
    var modal = $("v71-userdata-modal");
    if (!modal) return;  // markup not present (older index.html) — silently no-op
    _wired = true;

    var topBtn = $("v71-userdata-btn");
    if (topBtn) topBtn.addEventListener("click", openModal);

    var closeBtn = $("v71-userdata-close-btn");
    // Route the X through dismissIntro so the "Do not show again" checkbox is
    // honored when the user closes via the corner button too.
    if (closeBtn) closeBtn.addEventListener("click", dismissIntro);

    var dismissBtn = $("v71-userdata-dismiss-btn");
    if (dismissBtn) dismissBtn.addEventListener("click", dismissIntro);

    var applyBtn = $("v71-userdata-apply-btn");
    if (applyBtn) applyBtn.addEventListener("click", applyPath);

    var suggestBtn = $("v71-userdata-suggest-btn");
    if (suggestBtn) suggestBtn.addEventListener("click", useSuggested);

    var input = $("v71-userdata-path-input");
    if (input) {
      input.addEventListener("input", function () { input.dataset.v71UserTouched = "1"; });
    }

    // v7.1.1 — Click-outside-to-close and Escape-to-close are intentionally
    // removed. The popup contains an input field that the user pastes into,
    // and the previous behavior was closing the modal on stray backdrop
    // clicks (e.g. when the OS context menu dismissed and the click hit
    // the backdrop, or when the user clicked between input padding and
    // panel edge). Now the ONLY ways to close are the X button, the
    // dismiss button, or the open-from-Diagnostics fallback re-pressing
    // a button.

    // Diagnostics-fallback card needs to be injected once we know the
    // diagnostics body exists.
    injectDiagnosticsCard();
  }

  async function maybeAutoOpen() {
    var info = await fetchInfo();
    if (!info) {
      // No userdata info — don't block the changelog popup.
      try { document.dispatchEvent(new CustomEvent("sweepycl:userdata-closed")); } catch (e) {}
      return;
    }
    renderInfo(info);
    if (info.should_show_intro) {
      openModal();
    } else {
      // Userdata modal is skipped this load — signal so the changelog can show.
      try { document.dispatchEvent(new CustomEvent("sweepycl:userdata-closed")); } catch (e) {}
    }
  }

  function boot() {
    bind();
    // v7.1.2 — Do NOT auto-open the popup on DOMContentLoaded. The
    // dashboard.html serves the Steam auth form first; the popup would
    // cover the login UI. Wait for the post-auth 'sweepycl:dashboard-ready'
    // event dispatched at the end of renderDashboard(). Fires for both
    // manual login and cached-session auto-login.
    document.addEventListener('sweepycl:dashboard-ready', onDashboardReady);
    // Safety fallback: if the event already fired before this listener
    // attached (race condition on cached auto-login), check if the
    // dashboard view is already visible and proceed.
    setTimeout(function () {
      var loginView = document.getElementById('login-view');
      var dashView = document.getElementById('dashboard-view');
      var loginHidden = loginView && loginView.style.display === 'none';
      var dashVisible = dashView && (dashView.classList.contains('active') || dashView.style.display === 'flex' || dashView.style.display === 'block');
      if (loginHidden || dashVisible) {
        onDashboardReady();
      }
    }, 1500);
  }

  var _autoOpenFired = false;
  function onDashboardReady() {
    if (_autoOpenFired) return;
    _autoOpenFired = true;
    // Delay so the brand intro animation finishes first and the popup
    // doesn't cover an in-progress transition.
    setTimeout(maybeAutoOpen, 400);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();

// v7.4 — "What's New" changelog popup. Shows once per version, AFTER the
// userdata popup is closed/skipped (listens for sweepycl:userdata-closed).
(function () {
  var SEEN_KEY = "sweepy_changelog_seen_version";
  var shownThisSession = false;

  function $(id) { return document.getElementById(id); }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function inline(s) {
    return esc(s)
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/`([^`]+)`/g, "<code>$1</code>");
  }

  // Lightweight markdown → HTML for the changelog body (headings, bold, lists, tables).
  function renderMarkdown(md) {
    var lines = String(md || "").split(/\r?\n/);
    var out = [];
    var i = 0;
    while (i < lines.length) {
      var line = lines[i];
      var trimmed = line.trim();
      if (!trimmed) { i++; continue; }
      // table block
      if (trimmed.indexOf("|") === 0 || /^\|.*\|/.test(trimmed)) {
        var rows = [];
        while (i < lines.length && lines[i].trim().indexOf("|") >= 0 && /\|/.test(lines[i])) {
          rows.push(lines[i].trim());
          i++;
        }
        out.push(renderTable(rows));
        continue;
      }
      // bullet list
      if (/^[-*]\s+/.test(trimmed)) {
        out.push("<ul>");
        while (i < lines.length && /^[-*]\s+/.test(lines[i].trim())) {
          out.push("<li>" + inline(lines[i].trim().replace(/^[-*]\s+/, "")) + "</li>");
          i++;
        }
        out.push("</ul>");
        continue;
      }
      // numbered list
      if (/^\d+\.\s+/.test(trimmed)) {
        out.push("<ol>");
        while (i < lines.length && /^\d+\.\s+/.test(lines[i].trim())) {
          out.push("<li>" + inline(lines[i].trim().replace(/^\d+\.\s+/, "")) + "</li>");
          i++;
        }
        out.push("</ol>");
        continue;
      }
      // headings
      var h = trimmed.match(/^(#{2,6})\s+(.*)$/);
      if (h) {
        var level = Math.min(6, h[1].length + 1);
        out.push("<h" + level + ">" + inline(h[2]) + "</h" + level + ">");
        i++;
        continue;
      }
      out.push("<p>" + inline(trimmed) + "</p>");
      i++;
    }
    return out.join("");
  }

  function renderTable(rows) {
    var cells = rows
      .filter(function (r) { return !/^\|?[\s:-]+\|?$/.test(r.replace(/\|/g, "-")); })
      .map(function (r) {
        return r.replace(/^\||\|$/g, "").split("|").map(function (c) { return c.trim(); });
      });
    if (!cells.length) return "";
    var html = '<table class="changelog-table">';
    html += "<thead><tr>" + cells[0].map(function (c) { return "<th>" + inline(c) + "</th>"; }).join("") + "</tr></thead>";
    if (cells.length > 1) {
      html += "<tbody>";
      for (var r = 1; r < cells.length; r++) {
        html += "<tr>" + cells[r].map(function (c) { return "<td>" + inline(c) + "</td>"; }).join("") + "</tr>";
      }
      html += "</tbody>";
    }
    html += "</table>";
    return html;
  }

  function closeModal() {
    var modal = $("changelog-modal");
    if (modal) modal.style.display = "none";
  }

  // v2.1: show a persistent BETA badge (and red version pill) when the build's
  // changelog version is a beta, so testers always know they're on a beta build.
  function applyBetaBadge(version) {
    var isBeta = /beta/i.test(String(version || ""));
    var vEl = $("changelog-version");
    if (vEl) vEl.classList.toggle("is-beta", isBeta);
    var badge = document.getElementById("beta-build-badge");
    if (isBeta && !badge) {
      badge = document.createElement("div");
      badge.id = "beta-build-badge";
      badge.textContent = "BETA";
      badge.title = "Beta build — " + String(version || "") + ". See BETA_CHANGES.txt for what's new and how to test.";
      document.body.appendChild(badge);
    } else if (!isBeta && badge) {
      badge.remove();
    }
  }

  function openModal(data) {
    var modal = $("changelog-modal");
    if (!modal) return;
    var versionEl = $("changelog-version");
    var bodyEl = $("changelog-body");
    if (versionEl) versionEl.textContent = data.version || "";
    applyBetaBadge(data.version);
    if (bodyEl) bodyEl.innerHTML = renderMarkdown(data.markdown || "");
    modal.style.display = "flex";
    if (bodyEl) bodyEl.scrollTop = 0;
  }

  function markSeen(version) {
    try { localStorage.setItem(SEEN_KEY, version || "1"); } catch (e) {}
  }

  function wire(version) {
    var doneBtn = $("changelog-done-btn");
    function done() { markSeen(version); closeModal(); }
    if (doneBtn && !doneBtn.dataset.bound) {
      doneBtn.addEventListener("click", done);
      doneBtn.dataset.bound = "1";
    }
    // v7.6.2: the what's-new popup is dismissable ONLY via the close button.
    // Backdrop-click and Escape-to-close were intentionally removed so the
    // changelog can't be skipped accidentally.
  }

  async function maybeShow() {
    if (shownThisSession) return;
    shownThisSession = true;
    var data;
    try {
      var res = await fetch("/api/changelog");
      if (!res.ok) return;
      data = await res.json();
    } catch (e) { return; }
    if (!data || !data.success || !data.version) return;
    // Always show the what's-new popup on load (per-version gate disabled by
    // user request). `shownThisSession` still limits it to once per page load.
    wire(data.version);
    openModal(data);
  }

  document.addEventListener("sweepycl:userdata-closed", maybeShow);
})();



// NOVA — Advanced Local AI Agent & Desktop Automation Platform



// Production Workstation Application Bundle







(function() {



  'use strict';







  // State Management



  const state = {

    attachmentCache: {},

    activeAttachmentViewer: null,

    activeImageLightbox: null,



    conversations: [],



    activeConvId: null,



    messages: [],



    providers: [],



    models: [],



    agentProfiles: [],



    workspaces: [],



    activeWorkspace: null,



    systemPrompts: [],



    settings: {},



    taskPlan: null,



    pendingApprovals: [],



    systemStats: null,



    memoryFacts: [],



    isStreaming: false,



    streamingContent: '',



    streamingThought: '',



    sidebarOpen: true,



    rightPanelOpen: true,



    rightPanelTab: 'plan', // 'plan', 'workspace', 'health', 'memory'



    activeModal: null, // 'settings', 'provider', 'prompt'



    settingsTab: 'general',



    searchQuery: '',



    editingConvId: null,



    editingMessageId: null,



    editingMessageText: '',



    attachedFiles: [],



    showSearch: false,



    expandedToolDetails: {},



    expandedThoughts: {},

    expandedWorkedSections: {},

    viewingFilePath: null,

    viewingFileContent: null,

    viewingFileLoading: false,

    viewingFileError: null,

    viewingFileSize: null,

    viewingFileName: null,



    activeDropdown: null,

    activeTourStep: null,

    onboardingPreset: 'openai',



    slashMenuOpen: false,



    slashSelectedIndex: 0,



    activeSkill: 'research',



    renameModalConvId: null,



    renameModalValue: '',



    addMemoryModalOpen: false,

    addMemoryCategory: 'user_preference',

    addMemoryScope: 'global',

    memoryFilter: '',

    messageQueue: [],

    enableThinking: (localStorage.getItem('nova_enable_thinking') !== null) ? (localStorage.getItem('nova_enable_thinking') === 'true') : true,

    enableWebSearch: (localStorage.getItem('nova_enable_web_search') !== null) ? (localStorage.getItem('nova_enable_web_search') === 'true') : true,

    skills: [],

    mcpServers: [],

    mcpPresets: [],

    activeSubModal: null,

    lang: 'en',



  };







  // Slash Skills Catalog



  

    // Memory & Cookie Helpers for Last Selected AI Model

  function saveLastSelectedModel(modelName, providerId) {

    if (!modelName) return;

    try {

      localStorage.setItem('nova_last_model_id', modelName);

      if (providerId) localStorage.setItem('nova_last_provider_id', providerId);

      document.cookie = `nova_last_model_id=${encodeURIComponent(modelName)}; path=/; max-age=31536000; SameSite=Lax`;

      if (providerId) {

        document.cookie = `nova_last_provider_id=${encodeURIComponent(providerId)}; path=/; max-age=31536000; SameSite=Lax`;

      }

    } catch (e) {}

  }



  function getLastSelectedModel() {

    try {

      let mId = localStorage.getItem('nova_last_model_id');

      let pId = localStorage.getItem('nova_last_provider_id');

      if (!mId) {

        const m = document.cookie.match(/(?:^|;\s*)nova_last_model_id=([^;]+)/);

        if (m) mId = decodeURIComponent(m[1]);

      }

      if (!pId) {

        const p = document.cookie.match(/(?:^|;\s*)nova_last_provider_id=([^;]+)/);

        if (p) pId = decodeURIComponent(p[1]);

      }

      return { model_id: mId || null, provider_id: pId || null };

    } catch (e) {

      return { model_id: null, provider_id: null };

    }

  }



  function formatModelDisplayName(raw) {

    if (!raw) return '';

    let name = String(raw).replace(/\\/g, '/').replace(/\/+$/, '');

    if (name.includes('/')) {

      name = name.split('/').filter(Boolean).pop() || name;

    }

    name = name.replace(/\.(gguf|bin|safetensors|pt|pth|onnx)$/i, '');

    return name;

  }



  window.toggleThink = () => {

    state.enableThinking = !state.enableThinking;

    localStorage.setItem('nova_enable_thinking', state.enableThinking);

    render();

  };



  window.toggleWebSearch = () => {

    state.enableWebSearch = !state.enableWebSearch;

    localStorage.setItem('nova_enable_web_search', state.enableWebSearch);

    render();

  };



  // Antigravity Crisp SVG Icons for Skills

  function getSkillIconSvg(iconName) {

    if (!iconName) return icons.sparkles;

    if (typeof iconName === 'string' && iconName.trim().startsWith('<svg')) {

      return iconName;

    }

    const map = {

      'code': `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>`,

      'search': `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>`,

      'brain': `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z"/><path d="M12 5a3 3 0 1 1 5.997.125 4 4 0 0 1 2.526 5.77 4 4 0 0 1-.556 6.588A4 4 0 1 1 12 18Z"/></svg>`,

      'bug': `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m8 2 1.88 1.88"/><path d="M14.12 3.88 16 2"/><path d="M9 7.13v-1a3.003 3.003 0 1 1 6 0v1"/><path d="M12 20c-3.3 0-6-2.7-6-6v-3a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v3c0 3.3-2.7 6-6 6"/><path d="M12 20v-9"/><path d="M6.53 9C4.6 8.8 3 7.1 3 5"/><path d="M6 13H2"/><path d="M3 21c0-2.1 1.7-3.9 3.8-4"/><path d="M20.97 5c0 2.1-1.6 3.8-3.5 4"/><path d="M22 13h-4"/><path d="M17.2 17c2.1.1 3.8 1.9 3.8 4"/></svg>`,

      'terminal': `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"/><line x1="12" x2="20" y1="19" y2="19"/></svg>`,

      'sparkles': `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/></svg>`,

      'globe': `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" x2="22" y1="12" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>`,

      'rss': `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 11a9 9 0 0 1 9 9"/><path d="M4 4a16 16 0 0 1 16 16"/><circle cx="5" cy="19" r="1"/></svg>`,

      'shield': `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`,

      'toolbox': `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2h4a2 2 0 0 1 2 2v11z"/><path d="M10 2v4"/><path d="M14 2v4"/></svg>`,

      'cpu': `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="16" height="16" x="4" y="4" rx="2"/><rect width="6" height="6" x="9" y="9" rx="1"/><path d="M15 2v2"/><path d="M15 20v2"/><path d="M2 15h2"/><path d="M2 9h2"/><path d="M20 15h2"/><path d="M20 9h2"/><path d="M9 2v2"/><path d="M9 20v2"/></svg>`,

      'file': `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/></svg>`

    };

    return map[iconName] || icons[iconName] || icons.sparkles;

  }



  function getSkillColorClass(color) {

    switch (color) {

      case 'emerald': case 'green': return { bg: 'bg-emerald-500/15', text: 'text-emerald-400', border: 'border-emerald-500/20' };

      case 'amber': case 'yellow': return { bg: 'bg-amber-500/15', text: 'text-amber-400', border: 'border-amber-500/20' };

      case 'blue': case 'sky': return { bg: 'bg-blue-500/15', text: 'text-blue-400', border: 'border-blue-500/20' };

      case 'purple': case 'indigo': return { bg: 'bg-purple-500/15', text: 'text-purple-400', border: 'border-purple-500/20' };

      case 'rose': case 'red': return { bg: 'bg-rose-500/15', text: 'text-rose-400', border: 'border-rose-500/20' };

      case 'cyan': case 'teal': return { bg: 'bg-cyan-500/15', text: 'text-cyan-400', border: 'border-cyan-500/20' };

      case 'orange': return { bg: 'bg-orange-500/15', text: 'text-orange-400', border: 'border-orange-500/20' };

      default: return { bg: 'bg-emerald-500/15', text: 'text-emerald-400', border: 'border-emerald-500/20' };

    }

  }



    // English UI Translation Dictionary

  const i18n = {

    en: {

      new_session: "New Session",

      conversations: "Conversations",

      search_placeholder: "Search sessions...",

      pinned_sessions: "PINNED",

      recent_sessions: "RECENT",

      settings: "Control Center & Settings",

      active_workspace: "Active Workspace",

      ask_placeholder: "Ask anything, @ to mention, / for skills...",

      send: "Send",

      stop: "Stop",

      queue_badge: "Auto-send queue ({n} queued)",

      queue_desc: "Will be dispatched once current operation finishes",

      skills_header: "AGENT SKILLS (/ COMMANDS)",

      esc_to_close: "ESC TO CLOSE",

      tab_plan: "Task Plan",

      tab_files: "Files",

      tab_health: "Diagnostics",

      tab_memory: "Memory",

      no_active_plan: "No Active Task Plan",

      no_active_plan_desc: "When you give the agent complex goals, it generates and tracks multi-step plans here.",

      workspace_files: "Workspace Files",

      workstation_health: "Workstation Health",

      port: "PORT 46815",

      persistent_memory: "Persistent Memory Facts",

      add_fact: "+ Add Fact",

      rename_session: "Rename Session",

      save_title: "Save Title",

      cancel: "Cancel",

      delete_session: "Delete Session",

      export_markdown: "Export Markdown",

      copy_session_id: "Copy Session ID",

      session_options: "Session Options",

      settings_title: "NOVA Control Center & Customizations",

      settings_desc: "Manage agent profiles, skills, MCP servers, and local automation backends",

      tab_general: "1. General & System",

      tab_providers: "2. AI Providers & APIs",

      tab_skills: "3. Agent Skills & / Commands",

      tab_mcp: "4. MCP Servers & External Tools",

      tab_prompts: "5. System Directives",

      tab_terminal: "6. Terminal & PowerShell",

      tab_database: "7. SQLite Storage Engine",

      tab_security: "8. Security & Firewall",

      tab_logs: "9. Diagnostic Audit Logs",

      tab_about: "10. About NOVA Workstation",

      add_new_skill: "+ Add Custom Skill",

      add_mcp_server: "+ Add MCP Server",

      connect: "Connect",

      disconnect: "Disconnect",

      connected: "Connected",

      disconnected: "Disconnected",

      preset_install: "Install Preset",

      delete: "Delete",

      approval_required: "User Approval Required",

      approve: "Approve & Execute",

      reject: "Reject",

      auto_approve_session: "Always Allow in this Session",

      lang_name: "English"

    }

  };



  function t(key, params) {

    let val = (i18n.en && i18n.en[key]) || key;

    if (params) {

      for (const [k, v] of Object.entries(params)) {

        val = val.replace(new RegExp(`\{${k}\}`, 'g'), v);

      }

    }

    return val;

  }



  window.toggleLanguage = () => {

    state.lang = 'en';

    if (typeof localStorage !== 'undefined') {

      localStorage.setItem('nova_lang', 'en');

    }

    document.documentElement.dir = 'ltr';

    document.documentElement.lang = 'en';

    render();

  };



  const slashSkills = [



    {



      id: 'research',



      name: 'Deep Research',



      badge: 'PRO',



      color: 'emerald',



      icon: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/><path d="M11 8v6"/><path d="M8 11h6"/></svg>`,



      desc: 'Multi-step web exploration & comprehensive codebase synthesis',



      command: '/research'



    },



    {



      id: 'think',



      name: 'Deep Think',



      badge: 'REASONING',



      color: 'amber',



      icon: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a7 7 0 0 0-7 7c0 2.38 1.19 4.47 3 5.74V17a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2v-2.26c1.81-1.27 3-3.36 3-5.74a7 7 0 0 0-7-7Z"/><path d="M9 21h6"/></svg>`,



      desc: 'Extended chain-of-thought, system architecture & deep reflection',



      command: '/think'



    },



    {



      id: 'web',



      name: 'Web Search',



      badge: 'LIVE',



      color: 'blue',



      icon: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>`,



      desc: 'Live real-time search via DuckDuckGo & Google endpoints',



      command: '/web'



    },



    {



      id: 'terminal',



      name: 'Windows Diagnostics',



      badge: 'SYS',



      color: 'purple',



      icon: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 17 10 11 4 5"/><line x1="12" x2="20" y1="19" y2="19"/></svg>`,



      desc: 'PowerShell execution, memory telemetry & OS inspection',



      command: '/terminal'



    },



    {



      id: 'plan',



      name: 'Task Planner',



      badge: 'ROADMAP',



      color: 'teal',



      icon: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1" ry="1"/></svg>`,



      desc: 'Generate interactive step-by-step roadmap before performing actions',



      command: '/plan'



    },



    {



      id: 'turbo',



      name: 'Turbo Safe Ops',



      badge: 'FAST',



      color: 'emerald',



      icon: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>`,



      desc: 'Auto-approve safe read-only operations for zero latency',



      command: '/turbo'



    },



    {



      id: 'rss',



      name: 'RSS Feeds Explorer',



      badge: 'RSS',



      color: 'orange',



      icon: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 11a9 9 0 0 1 9 9"/><path d="M4 4a16 16 0 0 1 16 16"/><circle cx="5" cy="19" r="1"/></svg>`,



      desc: 'Browse curated country & topic RSS feed trees and fetch live news/articles',



      command: '/rss'



    }



  ];







  // Modern Toast Notification System (replaces raw browser alert)



  function showToast(message, type = 'info') {

    let container = document.getElementById('nova-toast-container');

    if (!container) {

      container = document.createElement('div');

      container.id = 'nova-toast-container';

      container.className = 'fixed bottom-6 right-6 z-50 flex flex-col gap-2 pointer-events-none select-none max-w-md';

      document.body.appendChild(container);

    }

    const toast = document.createElement('div');

    const isError = type === 'error';

    const isSuccess = type === 'success';



    const bgClass = isError ? 'bg-rose-950/95 border-rose-500/40 text-rose-100 shadow-rose-950/60' :

                    isSuccess ? 'bg-emerald-950/95 border-emerald-500/40 text-emerald-100 shadow-emerald-950/60' :

                    'bg-[#1a1a24]/95 border-white/15 text-zinc-100 shadow-black/70';



    const iconHtml = isError ? '<span class="text-rose-400 font-bold text-sm shrink-0">⚠️</span>' :

                     isSuccess ? '<span class="text-emerald-400 font-bold text-sm shrink-0">✓</span>' :

                     '<span class="text-indigo-400 font-bold text-sm shrink-0">ℹ</span>';



    toast.className = `flex items-center justify-between gap-3 px-4 py-3 rounded-xl border shadow-2xl backdrop-blur-xl text-xs font-medium transition-all duration-300 transform translate-y-2 opacity-0 pointer-events-auto ${bgClass}`;



    toast.innerHTML = `

      <div class="flex items-center gap-2.5 min-w-0">

        ${iconHtml}

        <span class="break-words leading-relaxed">${escapeHtml(message)}</span>

      </div>

      <button class="text-zinc-400 hover:text-white text-xs font-bold px-1.5 py-0.5 rounded transition shrink-0 cursor-pointer" onclick="this.parentElement.remove()">✕</button>

    `;



    container.appendChild(toast);

    requestAnimationFrame(() => {

      toast.classList.remove('translate-y-2', 'opacity-0');

      toast.classList.add('translate-y-0', 'opacity-100');

    });



    const displayDuration = isError ? 5000 : 3200;

    setTimeout(() => {

      toast.classList.add('opacity-0', 'translate-y-2');

      setTimeout(() => {

        try { toast.remove(); } catch (e) {}

      }, 300);

    }, displayDuration);

  }



  // Intercept window.alert so all native browser alerts become sleek in-app toasts

  window.alert = function(msg) {

    showToast(String(msg), 'error');

  };



  async function fetchProviders() {

    try {

      const [provs, mdls] = await Promise.all([

        apiCall('/providers').catch(() => []),

        apiCall('/models').catch(() => [])

      ]);

      state.providers = Array.isArray(provs) ? provs : [];

      state.models = Array.isArray(mdls) ? mdls : [];

      if (state.models.length === 0) {

        state.selectedDefaultModel = null;

        try { localStorage.removeItem('nova_last_model_id'); localStorage.removeItem('nova_last_provider_id'); } catch (e) {}

      } else if (state.selectedDefaultModel && !state.models.some(m => m.model_name === state.selectedDefaultModel)) {

        state.selectedDefaultModel = state.models[0].model_name;

      }

      return state.providers;

    } catch (e) {

      console.error('fetchProviders error:', e);

      return [];

    }

  }



  function showConfirmModal(title, message, onConfirm, confirmText, confirmClass) {

    state.confirmDialogConfig = {

      title: title || 'Confirm Action',

      message: message || 'Are you sure you want to proceed?',

      onConfirm: onConfirm,

      confirmText: confirmText || 'Delete',

      confirmClass: confirmClass || 'bg-rose-600 hover:bg-rose-500 text-white shadow-rose-950/40'

    };

    state.activeModal = 'confirm_dialog';

    render();

  }



  window.closeConfirmModal = () => {

    state.confirmDialogConfig = null;

    state.activeModal = null;

    render();

  };



  window.executeConfirmModalAction = async () => {

    const cfg = state.confirmDialogConfig;

    state.confirmDialogConfig = null;

    state.activeModal = null;

    render();

    if (cfg && typeof cfg.onConfirm === 'function') {

      await cfg.onConfirm();

    }

  };







  let wsConnection = null;



  let statsInterval = null;



  let reconnectTimer = null;



  let heartbeatTimer = null;







  // Icon Helpers



  const icons = {



    bot: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/></svg>`,



    terminal: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"/><line x1="12" x2="20" y1="19" y2="19"/></svg>`,



    shield: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/></svg>`,



    settings: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>`,



    cpu: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="16" height="16" x="4" y="4" rx="2"/><rect width="6" height="6" x="9" y="9" rx="1"/><path d="M15 2v2"/><path d="M15 20v2"/><path d="M2 15h2"/><path d="M2 9h2"/><path d="M20 15h2"/><path d="M20 9h2"/><path d="M9 2v2"/><path d="M9 20v2"/></svg>`,



    folder: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/></svg>`,



    file: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/></svg>`,



    check: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`,



    copy: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>`,



    edit: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/><path d="m15 5 4 4"/></svg>`,



    rotateCcw: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>`,



    send: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></svg>`,



    stop: `<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><rect width="16" height="16" x="4" y="4" rx="2"/></svg>`,



    paperclip: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>`,



    trash: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>`,



    pin: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" x2="12" y1="17" y2="22"/><path d="M5 17h14v-1.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V6h1a2 2 0 0 0 0-4H8a2 2 0 0 0 0 4h1v4.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24Z"/></svg>`,



    search: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>`,



    plus: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="M12 5v14"/></svg>`,



    x: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>`,



    chevronDown: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>`,



    refresh: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 21h5v-5"/></svg>`,



    alert: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" x2="12" y1="9" y2="13"/><line x1="12" x2="12.01" y1="17" y2="17"/></svg>`,



    sparkles: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/></svg>`,



    sparkles: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/></svg>`,



    brain: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.44-5.04Z"/><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.44-5.04Z"/></svg>`,



    antigravity: `<img src="/assets/logo.png" alt="NOVA" class="w-5 h-5 object-contain select-none pointer-events-none" />`,



    sidebarToggle: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M9 3v18"/></svg>`,



    arrowLeft: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m15 18-6-6 6-6"/></svg>`,



    arrowRight: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"/></svg>`,



    clock: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`,



    toolbox: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>`,



    gripVertical: `<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><circle cx="9" cy="5" r="1.5"/><circle cx="9" cy="12" r="1.5"/><circle cx="9" cy="19" r="1.5"/><circle cx="15" cy="5" r="1.5"/><circle cx="15" cy="12" r="1.5"/><circle cx="15" cy="19" r="1.5"/></svg>`,



    dotsVertical: `<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="12" cy="19" r="1.5"/></svg>`,



    splitWindow: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M12 3v18"/></svg>`,



    panelRight: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M15 3v18"/></svg>`,



    chevronRight: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"/></svg>`,



    chevronUp: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m18 15-6-6-6 6"/></svg>`,



    lightning: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>`,



    mic: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" x2="12" y1="19" y2="22"/></svg>`,



    arrowUp: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m5 12 7-7 7 7"/><path d="M12 19V5"/></svg>`



  };







  // Relative Time Formatter (e.g. now, 3m, 2h, 3d, 17d)



  function formatRelativeTime(dateStr) {



    if (!dateStr) return 'now';



    try {



      const date = new Date(dateStr);



      if (isNaN(date.getTime())) return 'now';



      const now = new Date();



      const diffMs = Math.max(0, now - date);



      const diffSec = Math.floor(diffMs / 1000);



      const diffMin = Math.floor(diffSec / 60);



      const diffHours = Math.floor(diffMin / 60);



      const diffDays = Math.floor(diffHours / 24);







      if (diffDays > 0) return `${diffDays}d`;



      if (diffHours > 0) return `${diffHours}h`;



      if (diffMin > 0) return `${diffMin}m`;



      return 'now';



    } catch (e) {



      return 'now';



    }



  }







  // Loading Screen Helpers



  function updateLoadingStatus(text, progress = null) {



    const el = document.getElementById('loading-status-text');



    if (el) el.textContent = text;



    const bar = document.getElementById('loading-progress-bar');



    if (bar && progress !== null) bar.style.width = progress + '%';



  }







  function hideLoadingScreen() {



    const loader = document.getElementById('app-loading-screen');



    if (loader) {



      loader.style.opacity = '0';



      loader.style.pointerEvents = 'none';



      setTimeout(() => {



        try { loader.remove(); } catch (e) {}



      }, 400);



    }



  }







  // Helper Functions



  function escapeHtml(str) {



    if (!str) return '';



    return str



      .replace(/&/g, '&amp;')



      .replace(/</g, '&lt;')



      .replace(/>/g, '&gt;')



      .replace(/"/g, '&quot;')



      .replace(/'/g, '&#039;');



  }



  function escapeAttr(str) {

    if (!str) return '';

    return String(str)

      .replace(/&/g, '&amp;')

      .replace(/"/g, '&quot;')

      .replace(/'/g, '&#39;')

      .replace(/</g, '&lt;')

      .replace(/>/g, '&gt;');

  }

  window.escapeAttr = escapeAttr;

  window.escapeHtml = escapeHtml;



function getActiveModel() {

    const curConv = (state.conversations || []).find(c => c.id === state.activeConvId);

    const savedModel = (typeof getLastSelectedModel === 'function') ? getLastSelectedModel() : {};

    const candidateModelName = curConv && curConv.model_id ? curConv.model_id : (state.selectedDefaultModel || savedModel.model_id || '');

    return (state.models || []).find(m => m.model_name === candidateModelName)

      || ((state.models && state.models.length > 0) ? state.models[0] : null);

  }

  window.getActiveModel = getActiveModel;



  function handleAttachedFileList(fileList) {

    if (!fileList || fileList.length === 0) return;

    const files = Array.from(fileList);

    const activeMdl = getActiveModel();

    const modelSupportsVision = activeMdl ? Boolean(activeMdl.supports_vision) : false;

    let rejectedImages = 0;



    const readPromises = files.map(file => {

      return new Promise((resolve) => {

        const ext = '.' + (file.name.split('.').pop() || '').toLowerCase();

        const isImage = (file.type && file.type.startsWith('image/')) || ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg'].includes(ext);



        if (isImage && !modelSupportsVision) {

          rejectedImages++;

          resolve(null);

          return;

        }



        const reader = new FileReader();

        reader.onload = () => {

          resolve({

            name: file.name || (isImage ? 'Pasted_Image_' + Date.now().toString().slice(-4) + '.png' : 'Pasted_File_' + Date.now().toString().slice(-4) + '.txt'),

            type: isImage ? 'image' : 'text',

            mime: file.type || (isImage ? 'image/png' : 'text/plain'),

            content: reader.result,

            size: file.size || (typeof reader.result === 'string' ? reader.result.length : 0),

            isSnippet: false

          });

        };

        reader.onerror = () => resolve(null);

        if (isImage) {

          reader.readAsDataURL(file);

        } else {

          reader.readAsText(file);

        }

      });

    });



    Promise.all(readPromises).then(results => {

      if (rejectedImages > 0) {

        const mName = activeMdl ? (formatModelDisplayName(activeMdl.display_name || activeMdl.model_name)) : 'Current model';

        showToast(`Model '${mName}' is a text-only model and does not support image input. Switch to a vision model (e.g. Qwen-VL, LLaVA, GPT-4o) to send images.`, 'warning');

      }

      const valid = results.filter(Boolean);

      if (valid.length > 0) {

        if (!state.attachedFiles) state.attachedFiles = [];

        state.attachedFiles.push(...valid);

        render();

        const inp = document.getElementById('composer-input');

        if (inp) inp.focus();

      }

    });

  }

  window.handleAttachedFileList = handleAttachedFileList;







  // Lightweight Token Colorizer for Syntax Highlighting

  function highlightCode(rawCode, lang) {

    const l = (lang || '').toLowerCase().trim();

    let code = escapeHtml(rawCode);

    

    if (['python', 'py'].includes(l)) {

      code = code.replace(/(#[^\n]*)/g, '<span class="text-zinc-500 italic">$1</span>');

      code = code.replace(/(&quot;[\s\S]*?&quot;|&#39;[\s\S]*?&#39;|"[^"\n]*"|'[^'\n]*')/g, '<span class="text-amber-300">$1</span>');

      code = code.replace(/\b(def|class|return|import|from|as|if|elif|else|for|while|try|except|finally|with|async|await|yield|lambda|None|True|False|pass|break|continue|in|is|not|and|or)\b/g, '<span class="text-purple-400 font-semibold">$1</span>');

      code = code.replace(/\b(print|len|range|int|str|float|list|dict|set|tuple|open|type|enumerate|zip|sum|min|max|abs)\b(?=\()/g, '<span class="text-blue-400">$1</span>');

      code = code.replace(/\b(\d+(\.\d+)?)\b/g, '<span class="text-cyan-400">$1</span>');

    } else if (['javascript', 'js', 'typescript', 'ts', 'jsx', 'tsx'].includes(l)) {

      code = code.replace(/(\/\/[^\n]*)/g, '<span class="text-zinc-500 italic">$1</span>');

      code = code.replace(/(&quot;[\s\S]*?&quot;|&#39;[\s\S]*?&#39;|`[\s\S]*?`|"[^"\n]*"|'[^'\n]*')/g, '<span class="text-amber-300">$1</span>');

      code = code.replace(/\b(const|let|var|function|return|if|else|for|while|try|catch|finally|async|await|import|export|from|class|extends|new|this|typeof|null|undefined|true|false)\b/g, '<span class="text-purple-400 font-semibold">$1</span>');

      code = code.replace(/\b(console|document|window|Math|Array|Object|Promise|JSON|setTimeout|fetch)\b/g, '<span class="text-blue-400">$1</span>');

      code = code.replace(/\b(\d+(\.\d+)?)\b/g, '<span class="text-cyan-400">$1</span>');

    } else if (['bash', 'sh', 'shell', 'powershell', 'ps1', 'cmd'].includes(l)) {

      code = code.replace(/(#[^\n]*)/g, '<span class="text-zinc-500 italic">$1</span>');

      code = code.replace(/(&quot;[\s\S]*?&quot;|&#39;[\s\S]*?&#39;|"[^"\n]*"|'[^'\n]*')/g, '<span class="text-amber-300">$1</span>');

      code = code.replace(/\b(curl|wget|git|npm|python|pip|docker|cd|ls|mkdir|rm|cp|mv|cat|grep|echo|exit|sudo|set|export|Get-ChildItem|Set-Location|Start-Process|Stop-Process)\b/g, '<span class="text-emerald-400 font-semibold">$1</span>');

    } else if (['json'].includes(l)) {

      code = code.replace(/(&quot;[^&]*&quot;)(\s*:)/g, '<span class="text-purple-300">$1</span>$2');

      code = code.replace(/(:)(\s*)(&quot;[^&]*&quot;)/g, '$1$2<span class="text-amber-300">$3</span>');

      code = code.replace(/\b(true|false|null)\b/g, '<span class="text-cyan-400 font-semibold">$1</span>');

      code = code.replace(/\b(\d+(\.\d+)?)\b/g, '<span class="text-cyan-400">$1</span>');

    } else if (['sql'].includes(l)) {

      code = code.replace(/(--[^\n]*)/g, '<span class="text-zinc-500 italic">$1</span>');

      code = code.replace(/\b(SELECT|FROM|WHERE|INSERT|INTO|VALUES|UPDATE|SET|DELETE|JOIN|LEFT|RIGHT|INNER|OUTER|ON|GROUP|BY|ORDER|ASC|DESC|LIMIT|OFFSET|CREATE|TABLE|DROP|ALTER|PRIMARY|KEY)\b/gi, '<span class="text-purple-400 font-bold">$1</span>');

    } else {

      code = code.replace(/(&quot;[^&]*&quot;|"[^"\n]*")/g, '<span class="text-emerald-400/90">$1</span>');

    }

    return code;

  }



  window.copyCodeBlock = (codeId, btn) => {

    const rawEl = document.getElementById(codeId + '_raw_code') || document.getElementById(codeId + '_raw') || document.getElementById(codeId);

    if (!rawEl) return;

    const text = rawEl.innerText || rawEl.textContent;

    navigator.clipboard.writeText(text).then(() => {

      const orig = btn.innerHTML;

      btn.innerHTML = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg> <span>Copied!</span>';

      btn.classList.add('text-emerald-400', 'border-emerald-500/40');

      setTimeout(() => {

        btn.innerHTML = orig;

        btn.classList.remove('text-emerald-400', 'border-emerald-500/40');

      }, 1800);

    }).catch(err => {

      showToast('Clipboard copy failed: ' + err, 'error');

    });

  };



  window.toggleCodeView = (codeId, view) => {

    const rawEl = document.getElementById(codeId + '_raw');

    const prevEl = document.getElementById(codeId + '_preview');

    const btnRaw = document.getElementById(codeId + '_btn_raw');

    const btnPrev = document.getElementById(codeId + '_btn_prev');

    if (!rawEl || !prevEl) return;

    if (view === 'preview') {

      rawEl.classList.add('hidden');

      prevEl.classList.remove('hidden');

      if (btnPrev) btnPrev.className = 'px-2.5 py-1 rounded-md bg-white/15 text-white font-semibold shadow-sm transition cursor-pointer';

      if (btnRaw) btnRaw.className = 'px-2.5 py-1 rounded-md text-zinc-400 hover:text-white transition cursor-pointer';

    } else {

      prevEl.classList.add('hidden');

      rawEl.classList.remove('hidden');

      if (btnRaw) btnRaw.className = 'px-2.5 py-1 rounded-md bg-white/15 text-white font-semibold shadow-sm transition cursor-pointer';

      if (btnPrev) btnPrev.className = 'px-2.5 py-1 rounded-md text-zinc-400 hover:text-white transition cursor-pointer';

    }

  };



  // High-Performance Antigravity Markdown & Table Engine

  function renderMarkdown(md, isNested) {

    if (!md) return '';



    const codeBlocks = [];

    const htmlBlocks = [];

    const inlineHtmlFragments = [];



    const sanitizeHtmlFragment = (raw) => {

      if (!raw) return '';

      return raw

        .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '')

        .replace(/\son[a-z]+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)/gi, '')

        .replace(/javascript\s*:/gi, 'blocked:');

    };



    // 1. Extract Code blocks

    let text = md;

    if (!isNested) {

      text = text.replace(/```([a-zA-Z0-9_-]*)\r?\n([\s\S]*?)```/g, (match, lang, code) => {

        const codeId = 'code_' + Math.random().toString(36).substr(2, 9);

        const cleanLang = (lang || 'code').trim().toLowerCase();

        const rawCode = code.trim();

        codeBlocks.push({ id: codeId, lang: cleanLang, code: rawCode });

        return '\n\n@@CODE_BLOCK_' + (codeBlocks.length - 1) + '@@\n\n';

      });

    }



    // 1b. Depth-aware container block extractor (protects nested divs/cards from breaking outer layout)

    const containerTags = ['div', 'section', 'article', 'figure', 'header', 'footer', 'aside', 'details', 'style', 'svg', 'table'];

    const tagPattern = new RegExp(`</?(${containerTags.join('|')})\\b[^>]*>`, 'gi');

    let depthProcessed = '';

    let lastIdx = 0;

    let match;

    let depth = 0;

    let blockStart = -1;

    let currentTag = '';



    while ((match = tagPattern.exec(text)) !== null) {

      const fullTag = match[0];

      const tagName = match[1].toLowerCase();

      const isClosing = fullTag.startsWith('</');

      const isSelfClosing = fullTag.endsWith('/>');



      if (depth === 0) {

        if (!isClosing && !isSelfClosing) {

          depth = 1;

          blockStart = match.index;

          currentTag = tagName;

          depthProcessed += text.slice(lastIdx, blockStart);

        } else if (isSelfClosing) {

          depthProcessed += text.slice(lastIdx, match.index);

          const idx = htmlBlocks.length;

          htmlBlocks.push(sanitizeHtmlFragment(fullTag));

          depthProcessed += '\n\n@@HTML_BLOCK_' + idx + '@@\n\n';

          lastIdx = tagPattern.lastIndex;

        } else if (isClosing) {

          // Orphan closing tag - strip it safely to protect app layout

          depthProcessed += text.slice(lastIdx, match.index);

          lastIdx = tagPattern.lastIndex;

        }

      } else {

        if (isClosing) {

          depth--;

          if (depth === 0) {

            const blockEnd = tagPattern.lastIndex;

            const blockContent = text.slice(blockStart, blockEnd);

            const idx = htmlBlocks.length;

            htmlBlocks.push(sanitizeHtmlFragment(blockContent));

            depthProcessed += '\n\n@@HTML_BLOCK_' + idx + '@@\n\n';

            lastIdx = blockEnd;

          }

        } else if (!isSelfClosing) {

          depth++;

        }

      }

    }



    if (depth > 0) {

      let blockContent = text.slice(blockStart);

      while (depth > 0) {

        blockContent += `</${currentTag}>`;

        depth--;

      }

      const idx = htmlBlocks.length;

      htmlBlocks.push(sanitizeHtmlFragment(blockContent));

      depthProcessed += '\n\n@@HTML_BLOCK_' + idx + '@@\n\n';

    } else {

      depthProcessed += text.slice(lastIdx);

    }

    text = depthProcessed;



    // 1c. Preserve inline HTML elements (img, span, a, br, small, badge tags) so markdown regexes never corrupt URLs/styles

    text = text.replace(

      /<\/?(?:img|span|a|br|hr|small|sub|sup|kbd|b|strong|i|em|u)\b[^>]*>/gi,

      (m) => {

        inlineHtmlFragments.push(sanitizeHtmlFragment(m));

        return '@@INLINE_HTML_' + (inlineHtmlFragments.length - 1) + '@@';

      }

    );



    // 2. Parse Markdown Tables

    const lines = text.split(/\r?\n/);

    const processedLines = [];

    let i = 0;



    const isTableDelim = (l) => /^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?$/.test((l || '').trim());

    const splitCells = (row) => {

      let raw = (row || '').trim();

      if (raw.startsWith('|')) raw = raw.slice(1);

      if (raw.endsWith('|')) raw = raw.slice(0, -1);

      return raw.split('|').map(c => c.trim());

    };



    const formatInline = (t) => {

      return escapeHtml(t)

        .replace(/\*\*(.*?)\*\*/g, '<strong class="font-semibold text-white">$1</strong>')

        .replace(/\*(.*?)\*/g, '<em class="italic text-zinc-300">$1</em>')

        .replace(/`([^`]+)`/g, '<code class="bg-[#181a24] text-emerald-400 px-1.5 py-0.5 rounded text-[11px] font-mono border border-white/5">$1</code>')

        .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-emerald-400 hover:text-emerald-300 underline underline-offset-2 transition">$1</a>');

    };



    while (i < lines.length) {

      const line = lines[i];

      if (line && line.includes('|') && i + 1 < lines.length && isTableDelim(lines[i + 1])) {

        const headerLine = lines[i];

        const delimLine = lines[i + 1];

        const headers = splitCells(headerLine);

        const delims = splitCells(delimLine);



        if (headers.length > 0 && headers.length === delims.length) {

          const alignments = delims.map(d => {

            const left = d.startsWith(':');

            const right = d.endsWith(':');

            if (left && right) return 'center';

            if (right) return 'right';

            return 'left';

          });



          const bodyRows = [];

          let j = i + 2;

          while (j < lines.length && lines[j].includes('|') && !isTableDelim(lines[j])) {

            const cells = splitCells(lines[j]);

            while (cells.length < headers.length) cells.push('');

            bodyRows.push(cells.slice(0, headers.length));

            j++;

          }



          const isPersianTable = /[\u0600-\u06FF]/.test(headerLine + bodyRows.map(r => r.join(' ')).join(' '));

          const defaultAlign = isPersianTable ? 'right' : 'left';



          let tableHtml = '<div class="my-4 overflow-x-auto rounded-2xl border border-white/10 bg-[#12131b] shadow-xl">\n';

          tableHtml += '  <table class="w-full text-xs border-collapse min-w-[340px]" dir="' + (isPersianTable ? 'rtl' : 'ltr') + '">\n';

          tableHtml += '    <thead>\n      <tr class="bg-white/[0.05] border-b border-white/10 text-zinc-200 font-semibold tracking-wide">\n';

          headers.forEach((h, idx) => {

            const align = alignments[idx] === 'center' ? 'center' : (alignments[idx] === 'right' ? 'right' : defaultAlign);

            tableHtml += '        <th class="py-3 px-4 text-' + align + ' font-semibold" style="text-align: ' + align + '">' + formatInline(h) + '</th>\n';

          });

          tableHtml += '      </tr>\n    </thead>\n';

          tableHtml += '    <tbody class="divide-y divide-white/5 text-zinc-300">\n';

          bodyRows.forEach(row => {

            tableHtml += '      <tr class="hover:bg-white/[0.025] transition">\n';

            row.forEach((cell, idx) => {

              const align = alignments[idx] === 'center' ? 'center' : (alignments[idx] === 'right' ? 'right' : defaultAlign);

              tableHtml += '        <td class="py-2.5 px-4 text-' + align + ' leading-relaxed" style="text-align: ' + align + '">' + formatInline(cell) + '</td>\n';

            });

            tableHtml += '      </tr>\n';

          });

          tableHtml += '    </tbody>\n  </table>\n</div>';



          processedLines.push(tableHtml);

          i = j;

          continue;

        }

      }



      processedLines.push(line);

      i++;

    }



    text = processedLines.join('\n');



    // 3. Headings

    text = text.replace(/^#### (.*$)/gim, '<h4 class="text-sm font-semibold text-zinc-200 mt-3 mb-1.5 flex items-center gap-2" dir="auto">$1</h4>');

    text = text.replace(/^### (.*$)/gim, '<h3 class="text-base font-semibold text-zinc-100 mt-4 mb-2 flex items-center gap-2" dir="auto">$1</h3>');

    text = text.replace(/^## (.*$)/gim, '<h2 class="text-lg font-bold text-white mt-5 mb-2.5 flex items-center gap-2" dir="auto">$1</h2>');

    text = text.replace(/^# (.*$)/gim, '<h1 class="text-xl font-bold text-white mt-6 mb-3 pb-2 border-b border-white/10 flex items-center gap-2" dir="auto">$1</h1>');



    // 4. Horizontal rules

    text = text.replace(/^\s*(?:---|---|\*\*\*|___)\s*$/gim, '<hr class="my-5 border-t border-white/10" />');



    // 5. Blockquotes

    text = text.replace(/^> (.*$)/gim, '<blockquote class="border-l-2 border-emerald-500 pl-3 my-2 text-zinc-400 italic bg-white/[0.02] py-1 rounded-r" dir="auto">$1</blockquote>');



    // 6. Lists & Checkboxes

    text = text.replace(/^\s*-\s*\[ \]\s*(.*$)/gim, '<div class="flex items-center gap-2 my-1 text-zinc-300 text-xs"><input type="checkbox" disabled class="rounded border-zinc-700 bg-zinc-800" /><span>$1</span></div>');

    text = text.replace(/^\s*-\s*\[x\]\s*(.*$)/gim, '<div class="flex items-center gap-2 my-1 text-zinc-300 text-xs"><input type="checkbox" checked disabled class="rounded border-emerald-500 text-emerald-500 bg-emerald-500/20" /><span>$1</span></div>');

    text = text.replace(/^\s*[-*+]\s+(.*$)/gim, '<li class="ml-4 list-disc text-zinc-300 my-1 leading-relaxed" dir="auto">$1</li>');

    text = text.replace(/^\s*(\d+)\.\s+(.*$)/gim, '<li class="ml-4 list-decimal text-zinc-300 my-1 leading-relaxed" dir="auto">$2</li>');



    // 7. Inline Formatting

    text = text.replace(/\*\*(.*?)\*\*/g, '<strong class="font-semibold text-white">$1</strong>');

    text = text.replace(/\*(.*?)\*/g, '<em class="italic text-zinc-300">$1</em>');

    text = text.replace(/`([^`]+)`/g, '<code class="bg-[#181a24] text-emerald-400 px-1.5 py-0.5 rounded text-[11px] font-mono border border-white/5">$1</code>');

    text = text.replace(/!\[([^\]]*)\]\(([^)\s]+)\)/g, '<img src="$2" alt="$1" class="my-2 rounded-xl max-w-full border border-white/10 shadow-lg" loading="lazy" />');

    text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-emerald-400 hover:text-emerald-300 underline underline-offset-2 transition">$1</a>');



    // 8. Line breaks in normal paragraphs

    text = text.split('\n').map(l => {

      const trimmed = l.trim();

      if (!trimmed) return '';

      if (trimmed.startsWith('<') && (trimmed.endsWith('>') || trimmed.includes('</'))) return l;

      return l + '<br/>';

    }).join('\n');



    // 9. Re-inject Code Blocks

    codeBlocks.forEach((cb, idx) => {

      const isPreviewable = ['markdown', 'md', 'html', 'svg', 'json'].includes(cb.lang);

      const initialMode = (cb.lang === 'markdown' || cb.lang === 'md') ? 'preview' : 'raw';

      const highlighted = highlightCode(cb.code, cb.lang);

      const escapedRaw = escapeHtml(cb.code);



      let previewHtml = '';

      if (cb.lang === 'markdown' || cb.lang === 'md') {

        previewHtml = renderMarkdown(cb.code, true);

      } else if (cb.lang === 'html' || cb.lang === 'svg') {

        previewHtml = cb.code;

      } else if (cb.lang === 'json') {

        try {

          previewHtml = '<pre class="text-xs font-mono text-cyan-300 leading-relaxed">' + escapeHtml(JSON.stringify(JSON.parse(cb.code), null, 2)) + '</pre>';

        } catch (e) {

          previewHtml = '<pre class="text-xs font-mono text-cyan-300 leading-relaxed">' + escapedRaw + '</pre>';

        }

      }



      const blockHtml = '<div class="my-4 rounded-2xl overflow-hidden border border-white/10 bg-[#0d0e15] shadow-2xl">\n' +

        '  <div class="flex items-center justify-between px-4 py-2.5 bg-[#141520] border-b border-white/10 text-xs text-zinc-400 font-mono">\n' +

        '    <div class="flex items-center gap-2">\n' +

        '      <span class="w-2 h-2 rounded-full bg-emerald-400 shadow-sm shadow-emerald-500/50"></span>\n' +

        '      <span class="font-semibold text-zinc-300 lowercase">' + escapeHtml(cb.lang || 'code') + '</span>\n' +

        '    </div>\n' +

        '    <div class="flex items-center gap-2">\n' +

        (isPreviewable ? ('      <div class="inline-flex items-center rounded-lg bg-black/40 p-0.5 border border-white/10 text-[11px] font-mono">\n' +

        '        <button id="' + cb.id + '_btn_prev" class="px-2.5 py-1 rounded-md ' + (initialMode === 'preview' ? 'bg-white/15 text-white font-semibold' : 'text-zinc-400 hover:text-white') + ' transition cursor-pointer" onclick="window.toggleCodeView(\'' + cb.id + '\', \'preview\')">Preview</button>\n' +

        '        <button id="' + cb.id + '_btn_raw" class="px-2.5 py-1 rounded-md ' + (initialMode === 'raw' ? 'bg-white/15 text-white font-semibold' : 'text-zinc-400 hover:text-white') + ' transition cursor-pointer" onclick="window.toggleCodeView(\'' + cb.id + '\', \'raw\')">Raw</button>\n' +

        '      </div>\n') : '') +

        '      <button class="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-zinc-300 hover:text-white border border-white/10 text-xs font-mono transition cursor-pointer" onclick="window.copyCodeBlock(\'' + cb.id + '\', this)" title="Copy Code">\n' +

        '        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>\n' +

        '        <span>Copy</span>\n' +

        '      </button>\n' +

        '    </div>\n' +

        '  </div>\n' +

        (isPreviewable ? ('  <div id="' + cb.id + '_preview" class="p-4 text-xs text-zinc-200 bg-[#0d0e15] ' + (initialMode === 'preview' ? '' : 'hidden') + ' select-text leading-relaxed border-t border-white/5">\n' +

        previewHtml + '\n  </div>\n') : '') +

        '  <pre id="' + cb.id + '_raw" class="p-4 text-xs font-mono overflow-x-auto text-emerald-300/90 leading-relaxed bg-[#0c0d14] ' + (initialMode === 'preview' ? 'hidden' : '') + ' select-text" dir="ltr" style="text-align: left;"><code id="' + cb.id + '_raw_code">' + highlighted + '</code></pre>\n' +

        '</div>';



      text = text.replace('@@CODE_BLOCK_' + idx + '@@', blockHtml);

    });



    // 10. Re-inject preserved HTML blocks & inline HTML fragments cleanly

    text = text.replace(/(?:<br\/>)?@@HTML_BLOCK_(\d+)@@(?:<br\/>)?/g, (_, idx) => htmlBlocks[Number(idx)] || '');

    text = text.replace(/@@INLINE_HTML_(\d+)@@/g, (_, idx) => inlineHtmlFragments[Number(idx)] || '');



    // 11. Balance and sanitize HTML tags to strictly protect NOVA application layout from stray/unclosed tags

    if (typeof DOMParser !== 'undefined') {

      try {

        const parser = new DOMParser();

        const doc = parser.parseFromString(text, 'text/html');

        doc.querySelectorAll('script, iframe, object, embed').forEach(el => el.remove());

        doc.querySelectorAll('*').forEach(el => {

          for (let aIdx = el.attributes.length - 1; aIdx >= 0; aIdx--) {

            const aName = el.attributes[aIdx].name.toLowerCase();

            const aVal = (el.attributes[aIdx].value || '').toLowerCase();

            if (aName.startsWith('on') || aVal.includes('javascript:') || aVal.includes('data:text/html')) {

              el.removeAttribute(el.attributes[aIdx].name);

            }

          }

        });

        return doc.body.innerHTML;

      } catch (e) {

        return text;

      }

    }



    return text;

  }





  // API Call Wrapper



  async function apiCall(endpoint, options = {}) {



    try {



      const res = await fetch('/api' + endpoint, {



        headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },



        ...options



      });



      if (!res.ok) {



        const err = await res.json().catch(() => ({ detail: res.statusText }));



        throw new Error(err.detail || 'API call failed');



      }



      return await res.json();



    } catch (err) {



      console.error('API Error:', err);



      throw err;



    }



  }







  // WebSocket / Real-Time Connection



  function setupWebSocket(convId) {



    if (wsConnection) {



      wsConnection.onclose = null;



      wsConnection.close();



      wsConnection = null;



    }



    clearTimeout(reconnectTimer);



    clearInterval(heartbeatTimer);







    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';



    const wsUrl = `${protocol}//${window.location.host}/api/ws/${convId}`;







    wsConnection = new WebSocket(wsUrl);







    wsConnection.onopen = () => {



      console.log('NOVA WebSocket connected for conversation:', convId);



    };







    wsConnection.onmessage = (e) => {



      try {



        const evt = JSON.parse(e.data);



        handleAgentEvent(evt);



      } catch (err) {



        console.error('WS parse error:', err);



      }



    };







    wsConnection.onclose = () => {



      console.log('NOVA WebSocket closed, scheduling auto-reconnect...');



      if (state.activeConvId === convId) {



        reconnectTimer = setTimeout(() => {



          setupWebSocket(convId);



        }, 2000);



      }



    };







    // Active heartbeat fallback: guarantees UI never hangs on Thinking and never prematurely stops streaming



    heartbeatTimer = setInterval(async () => {



      if (state.activeConvId === convId) {



        try {



          const data = await apiCall(`/conversations/${convId}`);



          if (data) {



            if (data.is_running === true) {



              if (!state.isStreaming) {



                state.isStreaming = true;



                render();



              }



            } else if (data.is_running === false && state.isStreaming) {



              state.isStreaming = false;



              state.streamingContent = '';



              state.streamingThought = '';



              processConversationData(data);



              const execs = await apiCall(`/executions/conversations/${convId}`);



              attachExecutionResults(execs);



              render();



              scrollToBottom();



              checkAndProcessMessageQueue();



            }



          }



        } catch (e) {}



      }



    }, 2500);



  }







  function handleAgentEvent(evt) {



    const { event_type, data } = evt;







    if (event_type === 'token') {



      state.isStreaming = true;



      state.streamingContent += data.delta || '';



      updateStreamingDOM();



    } else if (event_type === 'thought') {



      state.streamingThought += data.delta || '';



      updateStreamingDOM();



    } else if (event_type === 'status') {



      if (data.status === 'thinking') {



        state.isStreaming = true;



      } else if (data.status === 'reconnecting') {



        state.isStreaming = true;



        showToast(data.message || 'Network stream recovering...', 'info');



      }



    } else if (event_type === 'heartbeat') {



      state.isStreaming = true;



    } else if (event_type === 'tool_call_start') {



      state.messages.push({



        id: 'tc_' + Date.now(),



        role: 'system',



        created_at: new Date().toISOString(),



        content: `[TOOL_INVOKED] ${data.tool_name}`,



        toolData: data



      });



      render();



      scrollToBottom();



    } else if (event_type === 'tool_call_result') {



      // Find matching tool call message and attach result



      for (let i = state.messages.length - 1; i >= 0; i--) {



        if (state.messages[i].toolData && state.messages[i].toolData.tool_call_id === data.tool_call_id) {



          state.messages[i].toolResult = data.result;



          break;



        }



      }



      render();



      scrollToBottom();



    } else if (event_type === 'approval_required') {



      state.isStreaming = false;



      state.isAgentRunning = false;



      const aid = data && (data.approval_id || data.id);



      if (data && (!aid || !state.pendingApprovals.some(a => (a.approval_id || a.id) === aid))) {



        state.pendingApprovals.push(data);



      }



      render();



      scrollToBottom();



    } else if (event_type === 'plan_update') {



      if (data.plan) {



        state.taskPlan = data.plan;



        render();



      }



    } else if (event_type === 'conversation_renamed') {



      const c = state.conversations.find(x => x.id === evt.conversation_id);



      if (c && data && data.title) {



        c.title = data.title;



        render();



        showToast('Session renamed to: ' + data.title, 'success');



      }



    } else if (event_type === 'done') {



      state.isStreaming = false;



      state.streamingContent = '';



      state.streamingThought = '';



      refreshMessages();

      checkAndProcessMessageQueue();



    } else if (event_type === 'error') {



      state.isStreaming = false;



      state.messages.push({



        id: 'err_' + Date.now(),



        role: 'system',



        content: `[ERROR] ${data.message || 'Execution error'}`



      });



      render();



      scrollToBottom();



    }



  }







  function scrollToBottom(force = false) {



    const chatContainer = document.getElementById('chat-messages-container');



    if (chatContainer) {



      if (force) {



        chatContainer.scrollTop = chatContainer.scrollHeight;



      } else {



        const isScrolledUp = (chatContainer.scrollHeight - chatContainer.scrollTop - chatContainer.clientHeight > 80);



        if (!isScrolledUp) {



          chatContainer.scrollTop = chatContainer.scrollHeight;



        }



      }



    }



  }







  // Action Handlers



  async function init() {



    try {



      updateLoadingStatus('Connecting to local agent engine...', 30);



      const [convs, provs, mdls, profiles, wspaces, sets, stats, skillsData, mcpData, mcpPresetsData] = await Promise.all([



        apiCall('/conversations').catch(() => []),



        apiCall('/providers').catch(() => []),



        apiCall('/models').catch(() => []),



        apiCall('/agent-profiles').catch(() => []),



        apiCall('/workspaces').catch(() => []),



        apiCall('/settings').catch(() => ({})),



        apiCall('/tools').then(() => apiCall('/health')).catch(() => null),



        apiCall('/skills').catch(() => ({ skills: [] })),



        apiCall('/mcp/servers').catch(() => ({ servers: [] })),



        apiCall('/mcp/presets').catch(() => ({ presets: [] }))



      ]);



      state.skills = (skillsData && skillsData.skills) || [];



      state.mcpServers = (mcpData && mcpData.servers) || [];



      state.mcpPresets = (mcpPresetsData && mcpPresetsData.presets) || [];







      updateLoadingStatus('Configuring workspace & sessions...', 75);



      state.conversations = Array.isArray(convs) ? convs : [];

      const initialSavedModel = getLastSelectedModel();

      if (initialSavedModel.model_id) state.selectedDefaultModel = initialSavedModel.model_id;



      state.providers = Array.isArray(provs) ? provs : [];



      state.models = Array.isArray(mdls) ? mdls : [];



      state.agentProfiles = Array.isArray(profiles) ? profiles : [];



      state.workspaces = Array.isArray(wspaces) ? wspaces : [];



      state.settings = sets || {};



      state.systemStats = stats || null;







      if (state.workspaces.length > 0) {



        state.activeWorkspace = state.workspaces.find(w => w.is_active) || state.workspaces[0];



      }







      // Check URL route for /c/{convId}; keep root `/` on clean empty welcome view

      const urlMatch = window.location.pathname.match(/\/c\/([a-zA-Z0-9_-]+)/);

      const urlConvId = urlMatch ? urlMatch[1] : null;



      if (urlConvId && state.conversations.some(c => c.id === urlConvId)) {

        await selectConversation(urlConvId);

      } else {

        state.activeConvId = null;

        state.messages = [];

        state.taskPlan = null;

        state.pendingApprovals = [];

      }



      window.addEventListener('keydown', (e) => {

        if (e.key === 'Escape') {

          if (state.activeAttachmentViewer) {

            state.activeAttachmentViewer = null;

            render();

            return;

          }

          if (state.activeImageLightbox) {

            state.activeImageLightbox = null;

            render();

            return;

          }

        }

      });



      window.addEventListener('keydown', (e) => {

        if (e.key === 'Escape') {

          if (state.activeAttachmentViewer) {

            state.activeAttachmentViewer = null;

            render();

            return;

          }

          if (state.activeImageLightbox) {

            state.activeImageLightbox = null;

            render();

            return;

          }

        }

      });



      window.addEventListener('popstate', () => {

        const match = window.location.pathname.match(/\/c\/([a-zA-Z0-9_-]+)/);

        if (match && match[1]) {

          if (match[1] !== state.activeConvId) selectConversation(match[1]);

        } else {

          state.activeConvId = null;

          state.messages = [];

          state.taskPlan = null;

          state.pendingApprovals = [];

          render();

        }

      });







      // Start periodic health monitor



      statsInterval = setInterval(refreshSystemHealth, 15000);







    } catch (err) {



      console.error('Initialization error:', err);



    } finally {



      updateLoadingStatus('NOVA Workstation Ready', 100);



      try {



        const tourDone = localStorage.getItem('nova_tour_completed');

        const provDismissed = localStorage.getItem('nova_provider_setup_dismissed');



        if (!tourDone) {

          // On fresh launch, present the interactive feature tour first

          state.activeTourStep = 0;

        } else if (state.providers.length === 0 && !provDismissed) {

          // After tour is completed (or skipped), present provider onboarding if none configured

          state.activeModal = 'onboarding_provider';

        }



        render();



      } catch (renderErr) {



        console.error('Render error:', renderErr);



        const appEl = document.getElementById('app');



        if (appEl) {



          appEl.innerHTML = `



            <div class="flex-1 flex flex-col items-center justify-center p-8 text-center bg-[#0d0d0f] text-zinc-300">



              <div class="text-rose-400 text-lg font-semibold mb-2">Interface Render Error</div>



              <div class="text-xs font-mono bg-black/40 p-4 rounded-lg border border-white/10 max-w-xl text-left overflow-auto mb-4">${escapeHtml(renderErr.stack || renderErr.message)}</div>



              <button onclick="location.reload()" class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-medium transition">Reload Application</button>



            </div>



          `;



        }



      }



      setTimeout(hideLoadingScreen, 350);



    }



  }







  async function refreshSystemHealth() {



    try {



      const stats = await apiCall('/health');



      state.systemStats = stats;



      renderSystemStats();



    } catch (e) {}



  }







  async function createNewConversation() {

    try {

      const saved = getLastSelectedModel();

      let chosenModelId = null;

      let chosenProviderId = null;



      if (saved.model_id) {

        const found = state.models.find(m => m.model_name === saved.model_id);

        if (found) {

          chosenModelId = found.model_name;

          chosenProviderId = found.provider_id || saved.provider_id;

        }

      }



      if (!chosenModelId) {

        const defaultMdl = state.models.find(m => m.is_enabled) || state.models[0];

        const defaultProv = state.providers.find(p => p.is_enabled) || state.providers[0];

        chosenModelId = defaultMdl ? defaultMdl.model_name : null;

        chosenProviderId = defaultProv ? defaultProv.id : (defaultMdl ? defaultMdl.provider_id : null);

      }



      const defaultProf = state.agentProfiles[0];



      const newConv = await apiCall('/conversations', {

        method: 'POST',

        body: JSON.stringify({

          title: 'New Session',

          provider_id: chosenProviderId,

          model_id: chosenModelId,

          agent_profile_id: defaultProf ? defaultProf.id : null,

          workspace_path: state.activeWorkspace ? state.activeWorkspace.path : null,

          permission_mode: 'allow_safe'

        })

      });



      state.conversations.unshift(newConv);

      await selectConversation(newConv.id);

    } catch (err) {

      showToast('Failed to create session: ' + err.message, 'error');

    }

  }



  async function selectConversation(convId) {



    state.activeConvId = convId;



    state.pendingApprovals = [];



    state.editingMessageId = null;



    // Update browser URL to /c/{convId}

    try {

      const targetPath = '/c/' + convId;

      if (window.location.pathname !== targetPath) {

        window.history.pushState({ convId }, '', targetPath);

      }

    } catch (e) {

      console.warn('URL pushState error:', e);

    }



    setupWebSocket(convId);



    try {



      const data = await apiCall(`/conversations/${convId}`);



      if (data && data.is_running === true) {



        state.isStreaming = true;



      } else {



        state.isStreaming = false;



        state.streamingContent = '';



        state.streamingThought = '';



      }



      processConversationData(data);



    } catch (err) {



      console.error('Failed to load conversation:', err);



    }



    render();



    scrollToBottom();



  }







  function processConversationData(data) {



    if (data.conversation && data.conversation.id) {

      const idx = state.conversations.findIndex(c => c.id === data.conversation.id);

      if (idx !== -1) {

        state.conversations[idx] = { ...state.conversations[idx], ...data.conversation };

      }

    }



    const rawMsgs = (data.messages || []).slice();



    const toolCalls = data.tool_calls || [];



    const isRunning = Boolean(data.is_running);



    state.pendingApprovals = data.pending_approvals || [];



    if (isRunning) {



      state.isStreaming = true;



      if (rawMsgs.length > 0 && rawMsgs[rawMsgs.length - 1].role === 'assistant') {



        const activeAsst = rawMsgs[rawMsgs.length - 1];



        if (!state.streamingContent && activeAsst.content) {



          state.streamingContent = activeAsst.content;



        }



        if (!state.streamingThought && activeAsst.thoughts) {



          state.streamingThought = activeAsst.thoughts;



        }



        rawMsgs.pop();



      }



    } else if (!isRunning && state.isStreaming) {



      state.isStreaming = false;



      state.streamingContent = '';



      state.streamingThought = '';



    }







    const toolsByMsg = {};



    toolCalls.forEach(tc => {



      if (!toolsByMsg[tc.message_id]) toolsByMsg[tc.message_id] = [];



      toolsByMsg[tc.message_id].push(tc);



    });







    const timeline = [];



    rawMsgs.forEach(m => {



      if (m.role === 'system' && m.content && m.content.startsWith('[TOOL EXECUTION FEEDBACK]')) {



        return;



      }



      // Render tool calls BEFORE the assistant message so 'Worked for ...' accordion stays ABOVE the response

      if (m.role === 'assistant' && toolsByMsg[m.id]) {



        toolsByMsg[m.id].forEach(tc => {



          const hasResult = (tc.exit_code !== null && tc.exit_code !== undefined) || Boolean(tc.stdout) || Boolean(tc.stderr);

          timeline.push({



            id: 'tc_' + tc.id,



            role: 'system',



            created_at: tc.created_at,



            toolStatus: tc.status,



            content: `[TOOL_INVOKED] ${tc.tool_name}`,



            toolData: {



              tool_call_id: tc.id,



              tool_name: tc.tool_name,



              arguments: tc.arguments,



              risk_level: tc.risk_level



            },



            toolResult: hasResult ? {



              stdout: tc.stdout,



              stderr: tc.stderr,



              exit_code: tc.exit_code,



              duration_ms: tc.duration_ms



            } : null



          });



        });



      }



      timeline.push(m);



    });







    state.messages = timeline;



  }







  function attachExecutionResults(execs) {



    if (!execs || !execs.length) return;



    const execMap = {};



    execs.forEach(ex => { execMap[ex.id] = ex; });







    state.messages.forEach(msg => {



      if (msg.toolData && execMap[msg.toolData.tool_call_id]) {



        msg.toolResult = execMap[msg.toolData.tool_call_id];



      }



    });



  }







  async function refreshMessages() {



    if (!state.activeConvId) return;



    try {



      const data = await apiCall(`/conversations/${state.activeConvId}`);



      processConversationData(data);



      render();



      scrollToBottom();



    } catch (e) {}



  }







  async function stopGeneration() {



    if (!state.activeConvId) return;



    state.isStreaming = false;



    state.streamingContent = '';



    state.streamingThought = '';



    state.pendingApprovals = [];



    render();



    try {



      await apiCall(`/conversations/${state.activeConvId}/cancel`, { method: 'POST' });



    } catch (e) {}



    await refreshMessages();

    checkAndProcessMessageQueue();



  }







  async function retryTurn() {



    if (!state.activeConvId || state.isStreaming) return;



    state.isStreaming = true;



    state.streamingContent = '';



    state.streamingThought = '';



    render();



    scrollToBottom();



    try {



      await apiCall(`/conversations/${state.activeConvId}/retry`, { method: 'POST' });



    } catch (err) {



      state.isStreaming = false;



      showToast('Failed to retry: ' + err.message, 'error');



      render();



    }



  }







  async function sendMessage(text) {

    if (!text || !text.trim()) return;

    if (!state.activeConvId) {

      await createNewConversation();

      if (!state.activeConvId) return;

    }



    if (state.isStreaming) {

      if (!state.messageQueue) state.messageQueue = [];

      state.messageQueue.push({

        id: 'queue_' + Date.now(),

        convId: state.activeConvId,

        content: text.trim(),

        created_at: new Date().toISOString()

      });

      state.composerText = '';

      const composerInput = document.getElementById('composer-input');

      if (composerInput) { composerInput.value = ''; composerInput.style.height = '46px'; composerInput.style.overflowY = 'hidden'; }

      showToast('Message added to queue. Will auto-dispatch when current task completes.', 'info');

      render();

      return;

    }



    // Add optimistic user message

    state.messages.push({



      id: 'opt_' + Date.now(),



      role: 'user',



      content: text,



      created_at: new Date().toISOString()



    });



    state.isStreaming = true;



    state.streamingContent = '';



    state.streamingThought = '';



    render();



    scrollToBottom(true);







    try {



      await apiCall(`/conversations/${state.activeConvId}/messages`, {



        method: 'POST',



        body: JSON.stringify({

          content: text,

          enable_thinking: state.enableThinking !== undefined ? state.enableThinking : true,

          enable_search: state.enableWebSearch !== undefined ? state.enableWebSearch : true

        })



      });



    } catch (err) {



      state.isStreaming = false;



      state.messages.push({



        id: 'err_' + Date.now(),



        role: 'system',



        content: `Failed to dispatch prompt: ${err.message}`



      });



      render();



    }



  }







  

  function checkAndProcessMessageQueue() {

    if (state.isStreaming) return;

    if (state.messageQueue && state.messageQueue.length > 0) {

      const nextItem = state.messageQueue.shift();

      if (nextItem && nextItem.content) {

        render();

        showToast('Auto-dispatching queued message...', 'info');

        setTimeout(() => {

          sendMessage(nextItem.content);

        }, 400);

      }

    }

  }



  window.dequeueMessage = (idx) => {

    if (state.messageQueue && state.messageQueue[idx]) {

      state.messageQueue.splice(idx, 1);

      render();

      showToast('Message removed from queue.', 'info');

    }

  };



  async function handleApproval(approvalId, decision) {



    if (!approvalId) return;



    try {



      await apiCall(`/approvals/${approvalId}/decide`, {



        method: 'POST',



        body: JSON.stringify({ decision })



      });



      // Remove from pending (supports both live WS `approval_id` and DB `id`)



      state.pendingApprovals = (state.pendingApprovals || []).filter(a => (a.approval_id || a.id) !== approvalId);



      state.isAgentRunning = true;



      state.isStreaming = true;



      render();



      scrollToBottom();



    } catch (err) {



      showToast('Error recording approval: ' + err.message, 'error');



    }



  }







  async function deleteConversation(convId, e) {

    if (e) e.stopPropagation();

    showConfirmModal(

      'Delete Conversation',

      'Are you sure you want to delete this conversation? All associated messages and execution telemetry will be permanently removed.',

      async () => {

        try {

          await apiCall(`/conversations/${convId}`, { method: 'DELETE' });

          state.conversations = state.conversations.filter(c => c.id !== convId);

          if (state.activeConvId === convId) {

            state.activeConvId = null;

            state.messages = [];

            state.taskPlan = null;

            state.pendingApprovals = [];

            state.isStreaming = false;

            try { window.history.pushState({}, '', '/'); } catch (err) {}

            render();

          } else {

            render();

          }

          showToast('Conversation deleted.', 'info');

        } catch (err) {

          showToast('Failed to delete conversation: ' + err.message, 'error');

        }

      },

      'Delete Conversation',

      'bg-rose-600 hover:bg-rose-500 text-white'

    );

  }







  async function togglePin(convId, e) {



    if (e) e.stopPropagation();



    const conv = state.conversations.find(c => c.id === convId);



    if (!conv) return;



    const newPinned = conv.is_pinned ? 0 : 1;



    await apiCall(`/conversations/${convId}`, {



      method: 'PATCH',



      body: JSON.stringify({ is_pinned: newPinned })



    });



    conv.is_pinned = newPinned;



    state.conversations.sort((a, b) => (b.is_pinned - a.is_pinned));



    render();



  }







  // Render Component Tree



  function render() {

    const appEl = document.getElementById('app');

    if (!appEl) return;



    // Preserve composer text so typing is never interrupted

    const composerEl = document.getElementById('composer-input');

    if (composerEl) {

      state.composerText = composerEl.value;

    }



    // Preserve chat messages scroll position

    const chatContainer = document.getElementById('chat-messages-container');

    const prevScrollTop = chatContainer ? chatContainer.scrollTop : null;

    const isAtBottom = chatContainer ? (chatContainer.scrollHeight - chatContainer.scrollTop - chatContainer.clientHeight < 40) : true;



    // Preserve active focused element and selection range

    const activeEl = document.activeElement;

    const activeId = activeEl && activeEl.id ? activeEl.id : null;

    const selStart = (activeEl && activeEl.selectionStart !== undefined) ? activeEl.selectionStart : null;

    const selEnd = (activeEl && activeEl.selectionEnd !== undefined) ? activeEl.selectionEnd : null;



    appEl.innerHTML = `

      ${renderSidebar()}

      <div class="flex-1 flex flex-col h-full overflow-hidden bg-[#0d0d0f]">

        ${renderHeader()}

        <div class="flex-1 flex overflow-hidden">

          <div class="flex-1 flex flex-col h-full overflow-hidden relative">

            ${renderChatWorkspace()}

            ${renderComposer()}

          </div>

          ${state.rightPanelOpen ? renderRightPanel() : ''}

        </div>

      </div>

      ${renderModal()}

      ${renderDropdownMenu()}

      ${renderRenameModal()}

      ${renderAddMemoryModal()}

      ${renderTourOverlay()}

      ${renderAttachmentViewerModal()}

      ${renderImageLightboxModal()}

    `;



    bindEvents();



    // Restore chat scroll position seamlessly without jumping

    const newChatContainer = document.getElementById('chat-messages-container');

    if (newChatContainer && prevScrollTop !== null) {

      if (isAtBottom && state.isStreaming) {

        newChatContainer.scrollTop = newChatContainer.scrollHeight;

      } else {

        newChatContainer.scrollTop = prevScrollTop;

      }

    }



    // Restore element focus if appropriate (including composer-input)

    if (activeId) {

      const elToFocus = document.getElementById(activeId);

      if (elToFocus) {

        elToFocus.focus();

        if (selStart !== null && selEnd !== null && elToFocus.setSelectionRange) {

          try { elToFocus.setSelectionRange(selStart, selEnd); } catch (e) {}

        }

      }

    }

  }







    function renderSidebar() {



    if (!state.sidebarOpen) return '';



    const filteredConvs = state.conversations.filter(c =>



      (c?.title || "New Session").toLowerCase().includes((state.searchQuery || "").toLowerCase())



    );







    return `



      <div class="w-[260px] h-full bg-[#111115] border-r border-white/5 flex flex-col select-none text-zinc-300 shrink-0">



        <!-- Top Navigation Bar: Antigravity Logo, Sidebar Toggle, Back, Forward, Search -->



        <div class="px-3 pt-3 pb-2 flex items-center justify-between">



          <div class="flex items-center gap-1 text-zinc-400">



            <!-- Geometric Logo -->



            <button class="p-1 hover:text-white rounded hover:bg-white/5 transition text-zinc-200" title="NOVA Workstation">



              ${icons.antigravity}



            </button>



            <!-- Collapse sidebar toggle -->



            <button id="btn-collapse-sidebar" class="p-1 hover:text-white rounded hover:bg-white/5 transition text-zinc-400" title="Toggle Sidebar" onclick="window.toggleSidebar()">



              ${icons.sidebarToggle}



            </button>



            <!-- Back and Forward -->



            <button class="p-1 hover:text-white rounded hover:bg-white/5 transition text-zinc-500" title="Back">



              ${icons.arrowLeft}



            </button>



            <button class="p-1 hover:text-white rounded hover:bg-white/5 transition text-zinc-500" title="Forward">



              ${icons.arrowRight}



            </button>



          </div>







          <!-- Search toggle -->



          <button id="btn-search-toggle" class="p-1 hover:text-white rounded hover:bg-white/5 transition text-zinc-400" title="Search Conversations" onclick="window.toggleSearch()">



            ${icons.search}



          </button>



        </div>







        <!-- Optional Search Input -->



        ${state.showSearch ? `



          <div class="px-3 pb-2 animate-fade-in">



            <input



              id="sidebar-search-input"



              type="text"



              placeholder="Search history..."



              value="${escapeHtml(state.searchQuery)}"



              class="w-full px-2.5 py-1.5 bg-[#17171d] border border-white/10 rounded-lg text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-zinc-400"



            />



          </div>



        ` : ''}







        <!-- New Conversation Button -->



        <div class="px-3 pb-2.5">



          <button id="btn-new-chat" class="w-full py-2 px-3 rounded-lg bg-[#1a1a22] hover:bg-[#23232c] border border-white/5 text-zinc-200 hover:text-white text-xs font-medium flex items-center gap-2 transition shadow-sm cursor-pointer">



            ${icons.plus} <span>New Conversation</span>



          </button>



        </div>







        <!-- Automations & Customizations Navigation -->



        <div class="px-3 pb-2.5 space-y-0.5 border-b border-white/5 text-xs">



          <button class="w-full px-2 py-1.5 rounded-md hover:bg-white/5 flex items-center gap-2.5 text-zinc-400 hover:text-zinc-200 transition cursor-pointer" onclick="window.openSettingsTab('terminal')">



            <span class="text-zinc-400">${icons.clock}</span>



            <span>Automations</span>



          </button>



          <button class="w-full px-2 py-1.5 rounded-md hover:bg-white/5 flex items-center gap-2.5 text-zinc-400 hover:text-zinc-200 transition cursor-pointer" onclick="window.openSettingsTab('system_prompts')">



            <span class="text-zinc-400">${icons.toolbox}</span>



            <span>Customizations</span>



          </button>



        </div>







        <!-- Project & Conversation Groups -->



        <div class="flex-1 overflow-y-auto px-2 py-3 space-y-4">



          <!-- Projects Group -->



          <div>



            <div class="px-2 py-1 text-[11px] font-medium text-zinc-500 flex items-center justify-between">



              <span>Projects</span>



              <div class="flex items-center gap-1">



                <button class="p-0.5 hover:text-zinc-300 text-zinc-500" title="Workspace" onclick="window.openSettingsTab('workspace')">



                  ${icons.folder}



                </button>



              </div>



            </div>



            <div class="mt-0.5 px-2 py-1.5 text-xs text-zinc-400 flex items-center gap-2 rounded-lg hover:bg-white/5 cursor-pointer" onclick="window.openSettingsTab('workspace')">



              <span class="text-zinc-500">📁</span>



              <span class="truncate font-medium">${state.activeWorkspace ? state.activeWorkspace.name : 'NOVA Workspace'}</span>



            </div>



          </div>







          <!-- Conversations Group -->



          <div>



            <div class="px-2 py-1 text-[11px] font-medium text-zinc-500 flex items-center justify-between">



              <span>Conversations</span>



              <button class="p-0.5 hover:text-zinc-300 text-zinc-500 cursor-pointer" title="New" onclick="window.createNewConversation()">



                ${icons.plus}



              </button>



            </div>



            <div class="space-y-0.5 mt-1">



              ${filteredConvs.length > 0 ? filteredConvs.map(c => renderConvItem(c)).join('') : `



                <div class="text-xs text-zinc-600 px-2 py-3 text-center">No conversations found</div>



              `}



            </div>



          </div>



        </div>







        <!-- Pinned Settings Button at Bottom -->



        <div class="p-2 border-t border-white/5 bg-[#0e0e12]">



          <button id="btn-toggle-settings" class="w-full px-2.5 py-1.5 rounded-lg hover:bg-white/5 flex items-center gap-2 text-xs text-zinc-400 hover:text-zinc-200 transition cursor-pointer">



            ${icons.settings}



            <span class="font-medium">Settings</span>



          </button>



        </div>



      </div>



    `;



  }







  function renderConvItem(conv) {



    const isActive = conv.id === state.activeConvId;



    const timeLabel = formatRelativeTime(conv.updated_at || conv.created_at);







    if (isActive) {



      return `



        <div



          class="group flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs cursor-pointer bg-[#22222a] text-zinc-100 font-medium border border-white/5 transition"



          onclick="window.selectConv('${conv.id}')" oncontextmenu="window.openConvContextMenu('${conv.id}', event)"



        >



          <span class="truncate flex-1 pr-2" dir="auto">${escapeHtml(conv.title)}</span>



          <div class="flex items-center gap-1.5 text-zinc-400">



            <button class="p-0.5 text-zinc-400 hover:text-white" title="Options" onclick="window.openConvMenu('${conv.id}', event)">



              ${icons.gripVertical}



            </button>



          </div>



        </div>



      `;



    }







    return `



      <div



        class="group flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs cursor-pointer text-zinc-400 hover:text-zinc-200 hover:bg-[#1a1a20] transition"



        onclick="window.selectConv('${conv.id}')" oncontextmenu="window.openConvContextMenu('${conv.id}', event)"



      >



        <span class="truncate flex-1 pr-2" dir="auto">${escapeHtml(conv.title)}</span>



        <div class="flex items-center gap-1 text-[11px] text-zinc-500 font-mono shrink-0">



          <span class="group-hover:hidden">${timeLabel}</span>



          <div class="hidden group-hover:flex items-center gap-1">



            <button class="p-0.5 text-zinc-400 hover:text-zinc-100" onclick="window.togglePin('${conv.id}', event)" title="Pin">



              ${icons.pin}



            </button>



            <button class="p-0.5 text-zinc-400 hover:text-rose-400" onclick="window.deleteConv('${conv.id}', event)" title="Delete">



              ${icons.trash}



            </button>



          </div>



        </div>



      </div>



    `;



  }







  function renderHeader() {



    const curConv = state.conversations.find(c => c.id === state.activeConvId);



    const title = curConv ? curConv.title : 'NOVA AI Workstation';







    return `



      <div class="h-12 border-b border-white/5 bg-[#0d0d0f] px-5 flex items-center justify-between select-none shrink-0">



        <div class="flex items-center gap-2.5 min-w-0">



          ${!state.sidebarOpen ? `



            <button id="btn-expand-sidebar" type="button" class="p-1.5 hover:text-white rounded-lg hover:bg-white/10 transition text-zinc-300 cursor-pointer border border-white/10 bg-[#15161e]" title="Show Sidebar" onclick="window.toggleSidebar()">



              ${icons.sidebarToggle}



            </button>



            <button type="button" class="p-1.5 hover:text-white rounded-lg hover:bg-white/10 transition text-zinc-300 cursor-pointer" title="New Session" onclick="window.createNewConversation()">



              ${icons.plus}



            </button>



          ` : ''}



          <h1 class="text-sm font-medium text-zinc-200 truncate tracking-tight" dir="auto">



            ${escapeHtml(title)}



          </h1>



        </div>







        <!-- Top Right Action Icons: More menu, Split view, Panel right -->



        <div class="flex items-center gap-1 text-zinc-400">



          ${curConv ? `



            <button class="p-1.5 hover:text-white rounded hover:bg-white/5 transition text-zinc-400 cursor-pointer" title="Options" onclick="window.openConvMenu('${state.activeConvId}', event)">



              ${icons.dotsVertical}



            </button>



          ` : ''}



          <button class="p-1.5 hover:text-white rounded hover:bg-white/5 transition text-zinc-400 cursor-pointer" title="Split view" onclick="window.openSettingsTab('terminal')">



            ${icons.splitWindow}



          </button>



          <button id="btn-toggle-activity-panel" class="p-1.5 hover:text-white rounded hover:bg-white/5 transition cursor-pointer ${state.rightPanelOpen ? 'text-zinc-100 bg-white/10' : 'text-zinc-400'}" title="Toggle Side Panel">



            ${icons.panelRight}



          </button>



        </div>



      </div>



    `;



  }







  

  function renderMessageSequence(messages) {

    if (!messages || messages.length === 0) return '';

    const output = [];

    let i = 0;

    while (i < messages.length) {

      const msg = messages[i];

      if (msg.role === 'system' && msg.toolData) {

        const toolGroup = [];

        const startIndex = i;

        while (i < messages.length && messages[i].role === 'system' && messages[i].toolData) {

          toolGroup.push(messages[i]);

          i++;

        }

        const groupId = (toolGroup[0].toolData && toolGroup[0].toolData.tool_call_id) || toolGroup[0].id || ('group_' + startIndex);

        let totalMs = 0;

        toolGroup.forEach(m => {

          totalMs += (m.toolResult && m.toolResult.duration_ms) || 25;

        });

        let wallMs = 0;

        if (toolGroup.length > 0 && toolGroup[0].created_at) {

          const startTs = new Date(toolGroup[0].created_at).getTime();

          const lastItem = (i < messages.length && messages[i].role === 'assistant' && messages[i].created_at) ? messages[i] : toolGroup[toolGroup.length - 1];

          const endTs = lastItem && lastItem.created_at ? new Date(lastItem.created_at).getTime() : startTs;

          if (!isNaN(startTs) && !isNaN(endTs) && endTs > startTs) {

            wallMs = endTs - startTs;

          }

        }

        const totalSec = Math.max(1, Math.round(Math.max(totalMs, wallMs) / 1000));

        const durationText = totalSec >= 60 ? `${Math.round(totalSec / 60)}m` : `${totalSec}s`;

        

        const isLatest = (i === messages.length) && (state.isStreaming || state.isAgentRunning);

        const isExpanded = state.expandedWorkedSections[groupId] !== undefined ? !!state.expandedWorkedSections[groupId] : isLatest;

        

        output.push(`

          <div class="text-xs text-zinc-400 pl-1 py-1">

            <button

              class="flex items-center gap-1.5 text-zinc-400 hover:text-zinc-200 transition font-medium cursor-pointer py-1 select-none"

              onclick="window.toggleWorkedGroup('${groupId}')"

            >

              <span>Worked for ${durationText}</span>

              <span class="text-zinc-500">${isExpanded ? icons.chevronDown : icons.chevronRight}</span>

            </button>

            ${isExpanded ? `

              <div class="pl-1 pt-1 pb-1 space-y-1">

                ${toolGroup.map(m => renderAntigravityStep(m)).join('')}

              </div>

            ` : ''}

          </div>

        `);

      } else {

        output.push(renderMessageItem(msg));

        i++;

      }

    }

    return output.join('');

  }



  function renderApprovalCard(app) {



    if (!app) return '';



    const aid = app.approval_id || app.id || '';



    const risk = String(app.risk_level || 'MODERATE').toUpperCase();



    const isHighRisk = risk === 'HIGH' || risk === 'CRITICAL';



    const borderCls = isHighRisk ? 'border-rose-500/40 bg-rose-950/20' : 'border-amber-500/40 bg-amber-950/20';



    const badgeCls = isHighRisk



      ? 'bg-rose-500/20 text-rose-300 border-rose-500/30'



      : 'bg-amber-500/20 text-amber-300 border-amber-500/30';



    const titleText = app.tool_name || app.shell || 'System Operation';



    const cmdText = app.command || app.message || '';



    const cwdText = app.cwd || '';



    return `



      <div class="rounded-2xl border ${borderCls} p-4 shadow-xl space-y-3 animate-fade-in">



        <div class="flex items-center justify-between gap-3 flex-wrap">



          <div class="flex items-center gap-2 text-amber-300 font-medium text-xs">



            ${icons.alert}



            <span>Permission Required — ${escapeHtml(titleText)}</span>



          </div>



          <span class="text-[10px] font-mono px-2 py-0.5 rounded-full border ${badgeCls}">${escapeHtml(risk)} RISK</span>



        </div>



        ${app.message && app.command ? `<p class="text-xs text-zinc-300 leading-relaxed">${escapeHtml(app.message)}</p>` : ''}



        ${cmdText ? `



          <pre class="bg-[#0a0a0f] border border-white/10 rounded-xl p-3 font-mono text-[11px] text-zinc-200 overflow-x-auto whitespace-pre-wrap break-all select-text max-h-48">${escapeHtml(cmdText)}</pre>



        ` : ''}



        ${cwdText ? `<div class="text-[11px] text-zinc-400 font-mono truncate">Working Directory: ${escapeHtml(cwdText)}</div>` : ''}



        <div class="flex items-center gap-2 pt-1 flex-wrap">



          <button



            type="button"



            onclick="window.decideApp('${escapeHtml(aid)}', 'approved_once')"



            class="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium transition cursor-pointer"



          >Allow Once</button>



          <button



            type="button"



            onclick="window.decideApp('${escapeHtml(aid)}', 'approved_session')"



            class="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-zinc-100 text-xs font-medium transition cursor-pointer"



          >Allow for Session</button>



          <button



            type="button"



            onclick="window.decideApp('${escapeHtml(aid)}', 'denied')"



            class="px-3 py-1.5 rounded-lg bg-rose-600/20 hover:bg-rose-600/35 border border-rose-500/30 text-rose-300 text-xs font-medium transition cursor-pointer"



          >Deny</button>



        </div>



      </div>



    `;



  }







  function renderChatWorkspace() {



    const approvals = Array.isArray(state.pendingApprovals) ? state.pendingApprovals : [];



    return `



      <div id="chat-messages-container" class="flex-1 overflow-y-auto px-4 sm:px-6 py-6 space-y-6">



        <div class="max-w-4xl mx-auto w-full space-y-6">



          ${state.messages.length === 0 && !state.isStreaming ? renderEmptyState() : ''}







          ${renderMessageSequence(state.messages)}







          <!-- Live Streaming Turn -->



          ${state.isStreaming ? renderStreamingTurn() : ''}







          <!-- Pending Approval Cards -->



          ${approvals.map(app => renderApprovalCard(app)).join('')}



        </div>



      </div>



    `;



  }







  function renderEmptyState() {



    return `



      <div class="flex flex-col items-center justify-center min-h-[60vh] text-center max-w-xl mx-auto px-4 select-none animate-fade-in">



        <div class="w-16 h-16 rounded-2xl bg-[#13131a] border border-violet-500/25 flex items-center justify-center text-zinc-100 mb-4 shadow-[0_0_24px_rgba(139,92,246,0.2)] p-2">



          <img src="/assets/logo.png" alt="NOVA" class="w-12 h-12 object-contain select-none pointer-events-none drop-shadow-[0_0_12px_rgba(56,189,248,0.35)]" />



        </div>



        <h2 class="text-xl font-semibold text-zinc-100 mb-2 tracking-tight">NOVA AI Workstation</h2>



        <p class="text-xs text-zinc-400 mb-8 leading-relaxed max-w-md">



          Autonomous local agent connected to native OS shell (PowerShell / Bash / Zsh), diagnostics, and live web & RSS search.



        </p>







        <div class="grid grid-cols-2 gap-2.5 w-full text-xs">



          <button



            class="p-3 rounded-xl bg-[#141419] hover:bg-[#1a1a22] border border-white/5 hover:border-white/15 text-left text-zinc-300 transition flex flex-col gap-1 cursor-pointer"



            onclick="window.quickPrompt('Search the web for the latest artificial intelligence advancements and summarize them.')"



          >



            <div class="font-medium text-zinc-200 flex items-center gap-1.5">



              <span>🌐</span> <span>Live Web Search</span>



            </div>



            <span class="text-[11px] text-zinc-500">Query DuckDuckGo for live internet data</span>



          </button>







          <button



            class="p-3 rounded-xl bg-[#141419] hover:bg-[#1a1a22] border border-white/5 hover:border-white/15 text-left text-zinc-300 transition flex flex-col gap-1 cursor-pointer"



            onclick="window.quickPrompt('Inspect my system CPU, RAM usage, and active processes.')"



          >



            <div class="font-medium text-zinc-200 flex items-center gap-1.5">



              <span>💻</span> <span>System Diagnostics</span>



            </div>



            <span class="text-[11px] text-zinc-500">Inspect RAM, CPU and active processes</span>



          </button>







          <button



            class="p-3 rounded-xl bg-[#141419] hover:bg-[#1a1a22] border border-white/5 hover:border-white/15 text-left text-zinc-300 transition flex flex-col gap-1 cursor-pointer"



            onclick="window.quickPrompt('Analyze and inspect the files in my active workspace directory.')"



          >



            <div class="font-medium text-zinc-200 flex items-center gap-1.5">



              <span>📂</span> <span>Workspace Files</span>



            </div>



            <span class="text-[11px] text-zinc-500">Analyze local project architecture</span>



          </button>







          <button



            class="p-3 rounded-xl bg-[#141419] hover:bg-[#1a1a22] border border-white/5 hover:border-white/15 text-left text-zinc-300 transition flex flex-col gap-1 cursor-pointer"



            onclick="window.quickPrompt('Show my operating system architecture, OS version, and exact current time.')"



          >



            <div class="font-medium text-zinc-200 flex items-center gap-1.5">



              <span>🕒</span> <span>Windows OS Metadata</span>



            </div>



            <span class="text-[11px] text-zinc-500">Query OS environment and uptime</span>



          </button>



        </div>



      </div>



    `;



  }







  function parseMessageAttachments(rawContent, msgId) {

    if (!rawContent) return { cleanText: "", attachments: [] };

    if (!state.attachmentCache) state.attachmentCache = {};

    const attachments = [];

    let textWork = rawContent;



    // 1. Match modern <attachment type="..." name="..." mime="..." size="...">body</attachment>

    const modernRegex = /<attachment\s+([^>]*?)>([\s\S]*?)<\/attachment>/gi;

    let match;

    let idx = 0;

    while ((match = modernRegex.exec(rawContent)) !== null) {

      const attrStr = match[1];

      const body = match[2];

      const typeMatch = attrStr.match(/type="([^"]+)"/i);

      const nameMatch = attrStr.match(/name="([^"]+)"/i);

      const mimeMatch = attrStr.match(/mime="([^"]+)"/i);

      const sizeMatch = attrStr.match(/size="([^"]+)"/i);



      const type = typeMatch ? typeMatch[1].toLowerCase() : "text";

      const name = nameMatch ? nameMatch[1] : (type === "image" ? "Image.png" : "Attachment.txt");

      const mime = mimeMatch ? mimeMatch[1] : (type === "image" ? "image/png" : "text/plain");

      const size = sizeMatch ? parseInt(sizeMatch[1], 10) : body.length;

      const attId = `${msgId || "msg"}_att_${idx++}`;



      const attObj = { id: attId, type, name, mime, size, content: body };

      state.attachmentCache[attId] = attObj;

      attachments.push(attObj);

    }



    if (attachments.length > 0) {

      textWork = rawContent.replace(modernRegex, "").trim();

    } else {

      // 2. Backward compatibility: match legacy [Attached File: filename]\n```ext\nbody\n```

      const legacyRegex = /\[Attached File:\s*([^\]]+)\]\s*```([a-zA-Z0-9_-]*)\r?\n([\s\S]*?)\r?\n```\s*/gi;

      let legMatch;

      let legIdx = 0;

      while ((legMatch = legacyRegex.exec(rawContent)) !== null) {

        const name = legMatch[1].trim();

        const body = legMatch[3];

        const attId = `${msgId || "msg"}_leg_${legIdx++}`;

        const attObj = { id: attId, type: "text", name, mime: "text/plain", size: body.length, content: body };

        state.attachmentCache[attId] = attObj;

        attachments.push(attObj);

      }

      if (attachments.length > 0) {

        textWork = rawContent.replace(legacyRegex, "").trim();

      }

    }



    return { cleanText: textWork, attachments };

  }



  function renderMessageItem(msg) {



    if (msg.role === 'user') {



      const isEditing = state.editingMessageId === msg.id;







      if (isEditing) {



        return `



          <div class="w-full flex justify-end animate-fade-in">



            <div class="w-full bg-[#212127] border border-white/15 rounded-2xl p-4 shadow-lg">



              <textarea



                id="msg-edit-textarea-${msg.id}"



                rows="3"



                class="w-full bg-[#16161b] text-zinc-100 text-sm p-3 rounded-xl border border-white/10 focus:outline-none focus:border-emerald-500 resize-none font-sans leading-relaxed"



                dir="auto"



              >${escapeHtml(state.editingMessageText || msg.content)}</textarea>



              <div class="flex items-center justify-end gap-2 mt-3">



                <button class="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs text-zinc-300 cursor-pointer" onclick="window.cancelEditMessage()">



                  Cancel



                </button>



                <button class="px-3.5 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-xs text-white font-medium cursor-pointer" onclick="window.saveEditedMessage('${msg.id}', true)">



                  Save & Resend



                </button>



              </div>



            </div>



          </div>



        `;



      }







      const { cleanText, attachments } = parseMessageAttachments(msg.content, msg.id);



      let attachmentsHtml = '';

      if (attachments && attachments.length > 0) {

        attachmentsHtml = `

          <div class="flex flex-wrap gap-2 ${cleanText ? 'mt-2.5 pt-2 border-t border-white/5' : ''}">

            ${attachments.map(att => {

              if (att.type === 'image') {

                return `

                  <div class="group/attimg relative rounded-xl overflow-hidden border border-white/15 bg-black/40 hover:border-emerald-500/50 transition cursor-pointer shadow-md max-w-[260px]" onclick="window.openImageLightbox('${att.id}')" title="Click to view full image">

                    <img src="${escapeAttr(att.content)}" class="max-h-40 max-w-full object-cover rounded-lg block" alt="${escapeAttr(att.name)}" />

                    <div class="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/90 via-black/60 to-transparent p-2 flex items-center justify-between text-[11px] text-zinc-200">

                      <span class="truncate max-w-[170px] font-medium flex items-center gap-1.5">

                        <svg class="w-3.5 h-3.5 text-emerald-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>

                        <span>${escapeHtml(att.name)}</span>

                      </span>

                      <span class="text-[10px] text-zinc-400 font-mono shrink-0">${formatBytes(att.size)}</span>

                    </div>

                  </div>

                `;

              } else {

                const isPaste = att.type === 'paste';

                const iconSvg = isPaste

                  ? `<svg class="w-3.5 h-3.5 text-amber-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/></svg>`

                  : `<svg class="w-3.5 h-3.5 text-blue-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>`;

                return `

                  <div class="inline-flex items-center gap-2.5 px-3 py-2 rounded-xl bg-[#16161d] hover:bg-[#1f2029] border border-white/10 hover:border-white/20 text-xs text-zinc-200 cursor-pointer transition shadow-sm group/attchip select-none" onclick="window.openAttachmentViewer('${att.id}')" title="Click to view file contents">

                    ${iconSvg}

                    <div class="flex flex-col min-w-0">

                      <span class="font-medium text-zinc-200 truncate max-w-[190px] group-hover/attchip:text-white">${escapeHtml(att.name)}</span>

                      <span class="text-[10px] text-zinc-500 font-mono">${formatBytes(att.size)}</span>

                    </div>

                    <span class="ml-1 px-2 py-0.5 rounded-md bg-white/5 group-hover/attchip:bg-emerald-500/15 text-[11px] font-sans text-zinc-400 group-hover/attchip:text-emerald-400 transition font-medium flex items-center gap-1">

                      <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>

                      View

                    </span>

                  </div>

                `;

              }

            }).join('')}

          </div>

        `;

      }



      return `

        <div class="w-full flex justify-end animate-fade-in">

          <div class="max-w-[85%] w-fit min-w-[70px] bg-[#212127] border border-white/5 rounded-2xl p-3.5 sm:p-4 text-sm text-zinc-100 leading-relaxed shadow-sm group relative" dir="auto">

            ${cleanText ? `<div class="whitespace-pre-wrap select-text pr-8">${escapeHtml(cleanText)}</div>` : ''}

            ${attachmentsHtml}

            <!-- Floating action buttons on hover -->

            <div class="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition flex items-center gap-1 bg-[#17171c] border border-white/10 rounded-lg p-1 text-zinc-400 shadow-md">

              <button class="p-1 hover:text-white cursor-pointer" onclick="window.copyMsgContent('${msg.id}')" title="Copy">${icons.copy}</button>

              <button class="p-1 hover:text-white cursor-pointer" onclick="window.startEditMessage('${msg.id}')" title="Edit">${icons.edit}</button>

            </div>

          </div>

        </div>

      `;



    }







    if (msg.role === 'system' && msg.toolData) {



      // Timeline Step item



      return renderAntigravityStep(msg);



    }







    if (msg.role === 'assistant') {



      const extractedInlineThoughts = [];

      const cleanAssistantContent = (msg.content || '')

        .replace(/<think>([\s\S]*?)<\/think>/gi, (_, inner) => {

          if (inner && inner.trim()) extractedInlineThoughts.push(inner.trim());

          return '';

        })

        .replace(/<think>[\s\S]*$/gi, '')

        .replace(/<(?:session_title|title)>[\s\S]*?<\/(?:session_title|title)>/gi, '')

        .trim();



      const combinedThoughts = ((msg.thoughts || '').trim() + (extractedInlineThoughts.length ? '\n' + extractedInlineThoughts.join('\n') : '')).trim();

      const hasContent = cleanAssistantContent.length > 0;

      const hasThoughts = combinedThoughts.length > 0;



      if (!hasContent && !hasThoughts && !(msg.tool_calls && msg.tool_calls.length > 0)) {

        return '';

      }



      return `



        <div class="w-full space-y-3 animate-fade-in">



          ${hasThoughts ? `



            <div class="text-xs text-zinc-400 pl-1">



              <button



                class="flex items-center gap-1.5 text-zinc-400 hover:text-zinc-200 transition font-medium cursor-pointer py-1"



                onclick="window.toggleThought('${msg.id}')"



              >



                <span>Thought for ${msg.tokens ? Math.max(5, Math.min(45, Math.floor(msg.tokens / 8))) : 15}s</span>



                <span class="text-zinc-500">${state.expandedThoughts[msg.id] ? icons.chevronDown : icons.chevronRight}</span>



              </button>



              ${state.expandedThoughts[msg.id] ? `



                <div class="mt-1 text-xs font-mono text-zinc-400 bg-[#121216] border border-white/5 rounded-xl p-3 whitespace-pre-wrap max-h-48 overflow-y-auto">



                  ${escapeHtml(combinedThoughts)}



                </div>



              ` : ''}



            </div>



          ` : ''}







          ${(hasContent || (!state.isAgentRunning && msg.tool_calls && msg.tool_calls.length > 0)) ? `



            <div class="text-sm text-zinc-200 leading-relaxed space-y-3 pt-1 select-text" dir="auto">



              ${renderMarkdown(cleanAssistantContent || 'All requested operations have been completed successfully.')}



            </div>



            <div class="flex items-center gap-2 pt-1 text-zinc-500 text-xs">



              <button class="p-1 hover:text-zinc-300 transition cursor-pointer" onclick="window.copyMsgContent('${msg.id}')" title="Copy">${icons.copy}</button>



              <button class="p-1 hover:text-zinc-300 transition cursor-pointer" onclick="window.retryTurn()" title="Regenerate">${icons.refresh}</button>



            </div>



          ` : ''}



        </div>



      `;



    }







    return '';



  }







  function formatTerminalOutput(toolResult) {

    if (!toolResult) return '';

    let raw = toolResult.stdout || toolResult.result || '';

    if (typeof raw === 'string' && (raw.startsWith('{') || raw.startsWith('['))) {

      try {

        const parsed = JSON.parse(raw);

        if (parsed && parsed.directory && Array.isArray(parsed.items)) {

          let out = '    Directory: ' + parsed.directory + '\n\n';

          out += 'Mode                 LastWriteTime         Length Name\n';

          out += '----                 -------------         ------ ----\n';

          for (const item of parsed.items) {

            const mode = item.is_dir ? 'd-----' : '-a----';

            const len = item.is_dir ? '' : String(item.size_bytes || 0).padStart(14, ' ');

            const name = item.name || '';

            const dt = item.modified ? new Date(item.modified * 1000) : new Date();

            const dateStr = dt.toLocaleDateString() + '   ' + dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

            out += mode + '         ' + dateStr.padEnd(20, ' ') + ' ' + len.padEnd(14, ' ') + ' ' + name + '\n';

          }

          return out;

        } else if (parsed && parsed.stdout) {

          return parsed.stdout;

        }

      } catch (e) {}

    }

    return typeof raw === 'object' ? JSON.stringify(raw, null, 2) : String(raw);

  }



  function renderAntigravityStep(msg) {

    const { toolData, toolResult } = msg;

    const tcName = (toolData && toolData.tool_name) || 'execute';

    const isCompleted = toolResult && toolResult.exit_code === 0;

    const isError = toolResult && toolResult.exit_code !== null && toolResult.exit_code !== undefined && toolResult.exit_code !== 0;

    const isWaitingApproval = msg.toolStatus === 'waiting_approval';

    const isRejected = msg.toolStatus === 'rejected';

    const isRunning = !toolResult && msg.toolStatus !== 'cancelled' && !isWaitingApproval && !isRejected && state.isStreaming;

    const stepId = (toolData && toolData.tool_call_id) || msg.id;

    const isExpanded = state.expandedToolDetails && state.expandedToolDetails[stepId];

    const args = (toolData && toolData.arguments) || {};



    let stepLabel = '';

    let badgeClass = 'text-zinc-300';

    let cmdLine = '';



    // Determine clean label and command line for terminal prompt

    if (args.toolSummary || args.summary) {

      stepLabel = `Ran ${escapeHtml(args.toolSummary || args.summary)}`;

    } else if (tcName.includes('cmd') || tcName.includes('command') || tcName.includes('powershell')) {

      const rawCmd = args.CommandLine || args.command || '';

      const cmdShort = rawCmd.length > 50 ? rawCmd.slice(0, 47) + '...' : rawCmd;

      stepLabel = `Ran ${escapeHtml(cmdShort || 'command')}`;

      if (isError) badgeClass = 'text-rose-400';

    } else if (tcName === 'list_directory') {

      const p = args.path || '.';

      const dirName = p.replace(/\\/g, '/').split('/').filter(Boolean).pop() || p;

      stepLabel = `Ran list ${escapeHtml(dirName)}`;

    } else if (tcName === 'read_file') {

      const p = (args.path || '').replace(/\\/g, '/');

      const f = p.split('/').pop() || 'file';

      stepLabel = `Analyzed <span class="hover:underline text-cyan-400 cursor-pointer font-medium" data-file-path="${escapeHtml(p)}" onclick="event.stopPropagation(); window.openFileDrawer(this.getAttribute('data-file-path'))">📄 ${escapeHtml(f)}</span>`;

      badgeClass = 'text-cyan-400';

    } else if (tcName === 'write_file' || tcName === 'create_file' || tcName === 'edit_file') {

      const p = (args.path || '').replace(/\\/g, '/');

      const f = p.split('/').pop() || 'file';

      stepLabel = `Edited <span class="hover:underline text-emerald-400 cursor-pointer font-medium" data-file-path="${escapeHtml(p)}" onclick="event.stopPropagation(); window.openFileDrawer(this.getAttribute('data-file-path'))">📄 ${escapeHtml(f)}</span>`;

      badgeClass = 'text-emerald-400';

    } else if (tcName === 'run_python' && args.script_path) {

      const p = (args.script_path || '').replace(/\\/g, '/');

      const f = p.split('/').pop() || p;

      stepLabel = `Ran python <span class="hover:underline text-emerald-400 cursor-pointer font-medium" data-file-path="${escapeHtml(p)}" onclick="event.stopPropagation(); window.openFileDrawer(this.getAttribute('data-file-path'))">📄 ${escapeHtml(f)}</span>`;

    } else if (tcName === 'web_search') {

      stepLabel = `Ran web_search "${escapeHtml(args.query || '')}"`;

    } else if (tcName === 'list_rss_categories') {

      stepLabel = `Browsed RSS Directory Tree${args.filter ? ` ("${escapeHtml(args.filter)}")` : ''}`;

      badgeClass = 'text-orange-400';

    } else if (tcName === 'get_rss_category_feeds') {

      stepLabel = `Explored RSS Category: ${escapeHtml(args.category || '')}`;

      badgeClass = 'text-orange-400';

    } else if (tcName === 'fetch_rss_feed') {

      const targetLabel = args.category || (args.url ? args.url.replace(/^https?:\/\//, '').slice(0, 38) : 'feed');

      stepLabel = `Fetched RSS: ${escapeHtml(targetLabel)}${args.query ? ` ("${escapeHtml(args.query)}")` : ''}`;

      badgeClass = 'text-orange-400';

    } else {

      stepLabel = `Ran ${escapeHtml(tcName)}`;

    }



    // Determine terminal command line

    if (args.CommandLine) {

      cmdLine = args.CommandLine;

    } else if (args.command) {

      cmdLine = args.command;

    } else if (tcName === 'list_directory') {

      cmdLine = `Get-ChildItem -Path "${args.path || '.'}"`;

    } else if (tcName === 'read_file') {

      cmdLine = `Get-Content -Path "${args.path || ''}"`;

    } else if (tcName === 'write_file' || tcName === 'create_file') {

      cmdLine = `Set-Content -Path "${args.path || ''}"`;

    } else if (tcName === 'edit_file') {

      cmdLine = `Edit-File -Path "${args.path || ''}"`;

    } else if (tcName === 'inspect_project') {

      cmdLine = `inspect_project -Path "${args.path || '.'}"`;

    } else if (tcName === 'web_search') {

      cmdLine = `search "${args.query || ''}"`;

    } else {

      const argPairs = Object.entries(args)

        .map(([k, v]) => `-${k} ${typeof v === 'object' ? JSON.stringify(v) : v}`)

        .join(' ');

      cmdLine = `${tcName} ${argPairs}`.trim();

    }



    const formattedOutput = formatTerminalOutput(toolResult);



    return `

      <div class="pl-1 text-xs space-y-1">

        <button

          class="flex items-center gap-2 text-left hover:text-white transition font-sans cursor-pointer group py-0.5 ${badgeClass}"

          onclick="window.toggleToolDetail('${stepId}')"

        >

          <span class="text-zinc-500">${isExpanded ? icons.chevronDown : icons.chevronRight}</span>

          <span class="truncate font-medium">${stepLabel}</span>

          ${isRunning ? '<span class="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse ml-1"></span>' : ''}

          ${isWaitingApproval ? '<span class="text-amber-400 text-[10px] font-mono ml-1">(awaiting permission)</span>' : ''}

          ${isRejected ? '<span class="text-rose-400 text-[10px] font-mono ml-1">(denied)</span>' : ''}

          ${isCompleted ? `<span class="text-zinc-500 text-[10px] ml-1">(${toolResult.duration_ms || 25}ms)</span>` : ''}

        </button>



        ${isExpanded ? `

          <div class="mt-2 ml-4 bg-[#0a0a0f] border border-white/10 rounded-xl p-3.5 font-mono text-xs text-zinc-300 shadow-2xl">

            <div class="flex items-start gap-2.5 text-zinc-100 font-mono text-xs leading-relaxed">

              <span class="text-emerald-400 font-bold select-none text-sm leading-none pt-0.5">$</span>

              <span class="text-zinc-100 font-semibold select-text break-all">${escapeHtml(cmdLine)}</span>

            </div>

            ${formattedOutput ? `

              <div class="mt-3 pt-3 border-t border-white/5 font-mono text-[11px] text-zinc-300 leading-relaxed overflow-x-auto whitespace-pre-wrap select-text max-h-96">

                ${escapeHtml(formattedOutput)}

              </div>

            ` : ''}

            ${toolResult && toolResult.stderr ? `

              <div class="mt-2 text-rose-400 font-mono text-[11px] whitespace-pre-wrap select-text">

                ${escapeHtml(toolResult.stderr)}

              </div>

            ` : ''}

            ${isRunning ? `

              <div class="mt-2 text-amber-400/80 font-mono text-[11px] italic">

                Executing command...

              </div>

            ` : ''}

          </div>

        ` : ''}

      </div>

    `;

  }



  function renderStreamingTurn() {



    return `



      <div id="streaming-turn-container" class="w-full space-y-3 animate-fade-in">



        ${renderStreamingTurnInner()}



      </div>



    `;



  }



  function renderStreamingTurnInner() {



    return `



        <!-- Antigravity Active Timeline Header -->



        <div class="pl-1 space-y-2">



          ${state.streamingThought ? `



            <div class="text-xs text-zinc-400">



              <div class="flex items-center gap-1.5 font-medium py-1">



                <span>Thinking</span>



                <span class="text-zinc-500">${icons.chevronDown}</span>



              </div>



              <div class="mt-1 text-xs font-mono text-zinc-400 bg-[#121216] border border-white/5 rounded-xl p-3 whitespace-pre-wrap max-h-40 overflow-y-auto">



                ${escapeHtml(state.streamingThought)}



              </div>



            </div>



          ` : ''}







          <!-- Working indicator -->



          <div class="flex items-center gap-2 text-xs text-zinc-400 font-medium py-1">



            <span class="w-2 h-2 rounded-full bg-emerald-400 pulse-orb"></span>



            <span>Working</span>



          </div>



        </div>







        ${(() => {

          const cleanStream = (state.streamingContent || '')

            .replace(/<think>[\s\S]*?<\/think>/gi, '')

            .replace(/<think>[\s\S]*$/gi, '')

            .trim();

          return cleanStream ? `

            <div class="text-sm text-zinc-200 leading-relaxed space-y-3 pt-1 select-text" dir="auto">

              ${renderMarkdown(cleanStream)}

              <span class="inline-block w-1.5 h-4 bg-emerald-400 ml-1 animate-pulse"></span>

            </div>

          ` : '';

        })()}



    `;



  }



  function updateStreamingDOM() {



    const streamContainer = document.getElementById('streaming-turn-container');



    const chatContainer = document.getElementById('chat-messages-container');







    if (!streamContainer) {



      render();



      if (chatContainer) {



        chatContainer.scrollTop = chatContainer.scrollHeight;



      }



      return;



    }







    streamContainer.innerHTML = renderStreamingTurnInner();







    if (chatContainer) {



      const isScrolledUp = (chatContainer.scrollHeight - chatContainer.scrollTop - chatContainer.clientHeight > 80);



      if (!isScrolledUp) {



        chatContainer.scrollTop = chatContainer.scrollHeight;



      }



    }



  }







  function renderComposer() {



    const hasAttachments = state.attachedFiles && state.attachedFiles.length > 0;



    const curConv = state.conversations.find(c => c.id === state.activeConvId);



    const savedModel = getLastSelectedModel();

    const candidateModelName = curConv && curConv.model_id ? curConv.model_id : (state.selectedDefaultModel || savedModel.model_id || '');

    const foundMdl = (state.models || []).find(m => m.model_name === candidateModelName)

      || ((state.models && state.models.length > 0) ? state.models[0] : null);

    const activeModelName = foundMdl ? foundMdl.model_name : '';

    const activeModelSupportsVision = foundMdl ? Boolean(foundMdl.supports_vision) : false;

    const activeModelDisplay = foundMdl

      ? formatModelDisplayName(foundMdl.display_name || foundMdl.model_name)

      : 'No Model';







    const permMode = curConv ? (curConv.permission_mode || 'allow_safe') : 'allow_safe';



    const permModeLabel = {



      allow_safe: 'Turbo',



      ask_every_time: 'Ask Every Time',



      manual: 'Manual Strict'



    }[permMode] || 'Turbo';







    return `



      <div class="max-w-4xl mx-auto w-full px-4 sm:px-6 pb-6 pt-2 select-none">



        <div class="relative bg-[#18181d] border border-white/10 rounded-2xl p-3 shadow-2xl focus-within:border-zinc-500/50 transition-all flex flex-col gap-2">



          <!-- Skills Slash Command Popup Menu -->



          ${state.slashMenuOpen ? `

            <div id="skills-slash-menu" class="absolute bottom-full mb-3 left-0 w-84 bg-[#14141a]/95 border border-white/10 rounded-2xl shadow-2xl p-2.5 backdrop-blur-2xl z-50 max-h-76 overflow-y-auto">

              <div class="flex items-center justify-between px-2.5 py-1.5 border-b border-white/5 text-[10px] font-mono text-zinc-400 mb-1.5">

                <span class="flex items-center gap-1.5 font-semibold text-zinc-200">

                  <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>

                  ${t('skills_header')}

                </span>

                <span>${t('esc_to_close')}</span>

              </div>

              <div class="space-y-1">

                ${((state.skills && state.skills.length > 0) ? state.skills : slashSkills).map((sk, sIdx) => {

                  const sIcon = getSkillIconSvg(sk.icon);

                  const sColor = getSkillColorClass(sk.color);

                  const sDesc = sk.description || sk.desc || '';

                  return `

                    <div

                      class="group flex items-center gap-3 px-3 py-2 rounded-xl cursor-pointer transition ${state.slashSelectedIndex === sIdx ? 'bg-white/10 text-white shadow-sm border border-white/10' : 'text-zinc-300 hover:bg-white/5 hover:text-white'}"

                      onclick="window.selectSlashSkill('${sk.id}')"

                    >

                      <div class="w-8 h-8 rounded-xl ${sColor.bg} ${sColor.text} flex items-center justify-center shrink-0 border ${sColor.border} shadow-inner">

                        ${sIcon}

                      </div>

                      <div class="flex-1 min-w-0">

                        <div class="flex items-center justify-between">

                          <span class="font-semibold text-xs text-zinc-100 tracking-tight">${escapeHtml(sk.name)}</span>

                          <span class="text-[10px] font-mono px-2 py-0.5 rounded-full bg-white/5 text-zinc-400 border border-white/10">${escapeHtml(sk.command)}</span>

                        </div>

                        <div class="text-[11px] text-zinc-400 truncate mt-0.5">${escapeHtml(sDesc)}</div>

                      </div>

                    </div>

                  `;

                }).join('')}

              </div>

            </div>

          ` : ''}



          <!-- Attached files / snippets -->



          ${hasAttachments ? `

            <div class="flex flex-wrap gap-2 pb-2 border-b border-white/5">

              ${state.attachedFiles.map((file, idx) => `

                <div class="flex items-center gap-2 px-2.5 py-1.5 rounded-xl bg-[#22222a] border border-white/10 text-xs text-zinc-200 shadow-sm">

                  ${file.type === 'image' ? `

                    <img src="${file.content}" class="w-6 h-6 object-cover rounded-md border border-white/10 shrink-0" alt="thumb" />

                  ` : (file.isSnippet || file.type === 'paste') ? `

                    <svg class="w-4 h-4 text-amber-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/></svg>

                  ` : `

                    <svg class="w-4 h-4 text-blue-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>

                  `}

                  <span class="font-medium truncate max-w-[180px]">${escapeHtml(file.name)}</span>

                  <span class="text-[10px] text-zinc-400 font-mono">(${formatBytes(file.size)})</span>

                  ${(file.isSnippet || file.type === 'paste') ? `

                    <button class="text-[10px] text-emerald-400 hover:text-emerald-300 ml-1 underline cursor-pointer" onclick="window.convertSnippetToText(${idx})">Edit as text</button>

                  ` : ''}

                  <button class="text-zinc-500 hover:text-rose-400 ml-1 cursor-pointer font-bold px-1 text-sm" onclick="window.removeAttachment(${idx})" title="Remove attachment">&times;</button>

                </div>

              `).join('')}

            </div>

          ` : ''}







          <!-- Message Queue Badge -->

          ${state.messageQueue && state.messageQueue.length > 0 ? `

            <div class="flex flex-col gap-1.5 p-2.5 rounded-xl bg-indigo-950/40 border border-indigo-500/30 text-xs text-indigo-200 shadow-lg">

              <div class="flex items-center justify-between">

                <span class="flex items-center gap-1.5 font-semibold text-indigo-300">

                  <span class="w-2 h-2 rounded-full bg-indigo-400 animate-pulse"></span>

                  ${t('queue_badge', { n: state.messageQueue.length })}

                </span>

                <span class="text-[10px] text-zinc-400 font-mono">Dispatches automatically when current task finishes</span>

              </div>

              <div class="space-y-1 mt-1 max-h-24 overflow-y-auto">

                ${state.messageQueue.map((qm, qIdx) => `

                  <div class="flex items-center justify-between px-2.5 py-1.5 rounded-lg bg-black/40 border border-white/5 text-[11px]">

                    <span class="truncate max-w-[85%] text-zinc-200 font-medium">${qIdx + 1}. ${escapeHtml(qm.content)}</span>

                    <button class="text-rose-400 hover:text-rose-300 ml-2 cursor-pointer font-bold px-1.5 py-0.5 rounded hover:bg-white/5" onclick="window.dequeueMessage(${qIdx})" title="Remove from queue">✕</button>

                  </div>

                `).join('')}

              </div>

            </div>

          ` : ''}



          <!-- Textarea -->



          <textarea



            id="composer-input" rows="2" placeholder="Ask anything, @ to mention, / for actions" class="w-full bg-transparent text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none resize-none font-sans min-h-[46px] max-h-[268px] py-1.5 leading-relaxed overflow-y-hidden transition-all duration-75"



          >${escapeHtml(state.composerText || '')}</textarea>







          <!-- Bottom Toolbar Row -->



          <div class="flex items-center justify-between pt-1.5 border-t border-white/5">



            <!-- Left Controls: Plus (Attach), Model Pill Dropdown, Web Search Indicator -->



            <div class="flex items-center gap-2">



              <label class="w-7 h-7 rounded-full bg-[#23232b] hover:bg-[#2c2c36] text-zinc-300 hover:text-white flex items-center justify-center cursor-pointer transition" title="${activeModelSupportsVision ? 'Attach file or image' : 'Attach code/text file (Selected model is text-only)'}">



                ${icons.plus}



                <input type="file" id="file-upload-input" class="hidden" accept="${activeModelSupportsVision ? '.txt,.py,.js,.jsx,.ts,.tsx,.json,.md,.csv,.html,.css,.yaml,.yml,.ini,.env,.sh,.bat,.ps1,.sql,.c,.cpp,.h,.rs,.go,.xml,.png,.jpg,.jpeg,.gif,.webp,image/*' : '.txt,.py,.js,.jsx,.ts,.tsx,.json,.md,.csv,.html,.css,.yaml,.yml,.ini,.env,.sh,.bat,.ps1,.sql,.c,.cpp,.h,.rs,.go,.xml'}" />



              </label>







              <!-- Model Pill -->



              <div class="relative inline-flex items-center">



                <button id="btn-model-pill" class="bg-[#23232b] hover:bg-[#2c2c36] border border-white/5 px-2.5 py-1 rounded-full text-xs text-zinc-200 flex items-center gap-1.5 cursor-pointer shadow-sm transition max-w-[200px] sm:max-w-[260px]">



                  <span class="text-emerald-400 shrink-0">${icons.sparkles}</span>



                  <span class="font-medium truncate">${escapeHtml(activeModelDisplay)}</span>



                  <span class="text-zinc-500 shrink-0">${icons.chevronUp}</span>



                </button>



                <select id="header-model-select" class="absolute inset-0 opacity-0 cursor-pointer w-full h-full">



                  ${(!state.models || state.models.length === 0) ? `



                    <option value="" selected disabled>No models configured</option>



                  ` : (() => {



                    const provs = state.providers || [];



                    const seenIds = new Set();



                    let html = '';



                    for (const p of provs) {



                      const pModels = (state.models || []).filter(m => m.provider_id === p.id);



                      if (pModels.length > 0) {



                        html += `<optgroup label="${escapeHtml(p.name)}">`;



                        for (const m of pModels) {



                          seenIds.add(m.id);



                          const vTag = m.supports_vision ? ' 👁️ [Vision]' : '';

                          html += `<option value="${escapeHtml(m.model_name)}" ${m.model_name === activeModelName ? 'selected' : ''}>${escapeHtml(formatModelDisplayName(m.display_name || m.model_name))}${vTag}</option>`;



                        }



                        html += `</optgroup>`;



                      }



                    }



                    const leftovers = (state.models || []).filter(m => !seenIds.has(m.id));



                    for (const m of leftovers) {



                      const vTag2 = m.supports_vision ? ' 👁️ [Vision]' : '';

                      html += `<option value="${escapeHtml(m.model_name)}" ${m.model_name === activeModelName ? 'selected' : ''}>${escapeHtml(formatModelDisplayName(m.display_name || m.model_name))}${vTag2}</option>`;



                    }



                    return html;



                  })()}



                </select>



              </div>



              <!-- Think Toggle Button -->

              <button

                type="button"

                id="btn-toggle-think"

                onclick="window.toggleThink()"

                class="px-2.5 py-1 rounded-full text-xs flex items-center gap-1.5 cursor-pointer transition border ${state.enableThinking ? 'bg-indigo-500/15 border-indigo-500/30 text-indigo-300 shadow-sm' : 'bg-[#23232b] border-white/5 text-zinc-500 hover:text-zinc-300'}"

                title="${state.enableThinking ? 'Reasoning/Thinking is ON (Click to disable)' : 'Reasoning/Thinking is OFF (Click to enable)'}"

              >

                <span class="w-1.5 h-1.5 rounded-full ${state.enableThinking ? 'bg-indigo-400 animate-pulse' : 'bg-zinc-600'}"></span>

                <span class="font-medium">Think</span>

              </button>



              <!-- Search Toggle Button -->

              <button

                type="button"

                id="btn-toggle-search"

                onclick="window.toggleWebSearch()"

                class="px-2.5 py-1 rounded-full text-xs flex items-center gap-1.5 cursor-pointer transition border ${state.enableWebSearch ? 'bg-cyan-500/15 border-cyan-500/30 text-cyan-300 shadow-sm' : 'bg-[#23232b] border-white/5 text-zinc-500 hover:text-zinc-300'}"

                title="${state.enableWebSearch ? 'Live Web Search is ON (Click to disable)' : 'Live Web Search is OFF (Click to enable)'}"

              >

                <span class="w-1.5 h-1.5 rounded-full ${state.enableWebSearch ? 'bg-cyan-400' : 'bg-zinc-600'}"></span>

                <span class="font-medium">Search</span>

              </button>

              <!-- Vision Computer Control Badge -->
              ${activeModelSupportsVision ? `
                <span class="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 select-none cursor-default font-medium" title="Vision Model Active: Desktop Mouse & Keyboard GUI Automation is enabled">
                  <span>🖱️</span>
                  <span>GUI Agent</span>
                </span>
              ` : ''}



            </div>







            <!-- Right Controls: Permission Pill (Turbo), Mic, Send/Stop -->



            <div class="flex items-center gap-2">



              <!-- Permission Mode Pill -->



              <div class="relative inline-flex items-center">



                <button class="bg-[#23232b] hover:bg-[#2c2c36] border border-white/5 px-2.5 py-1 rounded-full text-xs text-zinc-300 flex items-center gap-1.5 cursor-pointer shadow-sm transition">



                  <span class="text-amber-400">${icons.lightning}</span>



                  <span>${permModeLabel}</span>



                  <span class="text-zinc-500">${icons.chevronUp}</span>



                </button>



                <select id="header-perm-mode" class="absolute inset-0 opacity-0 cursor-pointer w-full h-full">



                  <option value="allow_safe" ${permMode === 'allow_safe' ? 'selected' : ''}>Turbo (Safe Ops)</option>



                  <option value="ask_every_time" ${permMode === 'ask_every_time' ? 'selected' : ''}>Ask Every Time</option>



                  <option value="manual" ${permMode === 'manual' ? 'selected' : ''}>Manual Strict</option>



                </select>



              </div>







              <!-- Mic Button -->



              <button class="w-7 h-7 rounded-full hover:bg-white/5 text-zinc-400 hover:text-zinc-200 flex items-center justify-center transition cursor-pointer" title="Voice Input" onclick="window.voicePromptPlaceholder()">



                ${icons.mic}



              </button>







                            <!-- Send / Stop / Queue Buttons -->

              ${state.isStreaming ? `

                <button id="btn-stop-gen" class="w-7 h-7 rounded-md bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 flex items-center justify-center border border-rose-500/30 transition cursor-pointer" title="Stop generation">

                  <div class="w-2.5 h-2.5 bg-rose-400 rounded-sm"></div>

                </button>

                <button id="btn-send-msg" class="w-7 h-7 rounded-full bg-indigo-500/30 hover:bg-indigo-500/50 text-indigo-200 border border-indigo-500/40 flex items-center justify-center font-bold transition shadow-sm cursor-pointer" title="Queue message for auto-send (Enter)">

                  ${icons.arrowUp}

                </button>

              ` : `

                <button id="btn-send-msg" class="w-7 h-7 rounded-full bg-zinc-100 hover:bg-white text-zinc-900 flex items-center justify-center font-bold transition shadow-sm cursor-pointer" title="Send message (Enter)">

                  ${icons.arrowUp}

                </button>

              `}

            </div>

          </div>

        </div>

      </div>



      `;



    }







      

  // Right Diagnostic & Workspace Panel

  function renderRightPanel() {

    return `

      <div class="w-80 h-full bg-[#12141c] border-l border-[#232736] flex flex-col select-none">

        <!-- Panel Tabs -->

        <div class="flex items-center border-b border-[#232736] bg-[#0d0f17] text-xs font-medium">

          <button

            class="flex-1 py-2.5 text-center border-b-2 ${state.rightPanelTab === 'plan' ? 'border-emerald-400 text-emerald-400 bg-[#161924]' : 'border-transparent text-slate-400 hover:text-slate-200'} cursor-pointer"

            onclick="window.switchTab('plan')"

          >

            ${t('tab_plan')}

          </button>

          <button

            class="flex-1 py-2.5 text-center border-b-2 ${state.rightPanelTab === 'workspace' ? 'border-emerald-400 text-emerald-400 bg-[#161924]' : 'border-transparent text-slate-400 hover:text-slate-200'} cursor-pointer"

            onclick="window.switchTab('workspace')"

          >

            ${t('tab_files')}

          </button>

          <button

            class="flex-1 py-2.5 text-center border-b-2 ${state.rightPanelTab === 'health' ? 'border-emerald-400 text-emerald-400 bg-[#161924]' : 'border-transparent text-slate-400 hover:text-slate-200'} cursor-pointer"

            onclick="window.switchTab('health')"

          >

            ${t('tab_health')}

          </button>

          <button

            class="flex-1 py-2.5 text-center border-b-2 ${state.rightPanelTab === 'memory' ? 'border-emerald-400 text-emerald-400 bg-[#161924]' : 'border-transparent text-slate-400 hover:text-slate-200'} cursor-pointer"

            onclick="window.switchTab('memory')"

          >

            ${t('tab_memory')}

          </button>

        </div>



        <!-- Panel Body -->

        <div class="flex-1 overflow-y-auto p-3 text-xs text-slate-300">

          ${renderRightPanelContent()}

        </div>

      </div>

    `;

  }



  function renderRightPanelContent() {

    if (state.rightPanelTab === 'file_viewer') {

      const p = state.viewingFilePath || '';

      const fn = state.viewingFileName || p.replace(/\\/g, '/').split('/').pop() || 'file';

      const sizeStr = state.viewingFileSize != null ? `${(state.viewingFileSize / 1024).toFixed(1)} KB` : '';

      return `

        <div class="space-y-3 h-full flex flex-col">

          <div class="flex items-center justify-between pb-2 border-b border-[#232736]">

            <div class="flex items-center gap-2 min-w-0">

              <span class="text-emerald-400">📄</span>

              <div class="truncate">

                <div class="font-bold text-slate-100 text-xs truncate" title="${escapeHtml(p)}">${escapeHtml(fn)}</div>

                <div class="text-[10px] font-mono text-slate-500 truncate" title="${escapeHtml(p)}">${escapeHtml(p)}</div>

              </div>

            </div>

            <div class="flex items-center gap-2 shrink-0">

              ${sizeStr ? `<span class="text-[10px] font-mono bg-white/5 px-1.5 py-0.5 rounded text-slate-400">${sizeStr}</span>` : ''}

              <button class="p-1 hover:bg-white/10 text-slate-400 hover:text-white rounded transition cursor-pointer" onclick="window.closeFileDrawer()" title="Close Viewer">

                ${icons.x}

              </button>

            </div>

          </div>

          <div class="flex-1 overflow-auto bg-[#0a0a0f] border border-white/5 rounded-xl p-3 font-mono text-xs text-zinc-300">

            ${state.viewingFileLoading ? `

              <div class="flex items-center justify-center py-12 text-slate-500 gap-2">

                <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>

                <span>Loading file contents...</span>

              </div>

            ` : state.viewingFileError ? `

              <div class="text-rose-400 p-2 text-xs font-sans">

                ${escapeHtml(state.viewingFileError)}

              </div>

            ` : `

              <pre class="leading-relaxed whitespace-pre-wrap select-text font-mono text-[11px] text-zinc-200"><code>${escapeHtml(state.viewingFileContent || '')}</code></pre>

            `}

          </div>

        </div>

      `;

    }

    if (state.rightPanelTab === 'plan') {

      if (!state.taskPlan) {

        return `

          <div class="text-center py-10 text-slate-500">

            <div class="mb-2 flex justify-center text-slate-600">${icons.brain}</div>

            <div class="font-medium text-slate-400 mb-1">${t('no_active_plan')}</div>

            <p class="text-[11px] leading-relaxed">${t('no_active_plan_desc')}</p>

          </div>

        `;

      }

      return `

        <div class="space-y-3">

          <div class="font-semibold text-slate-100 text-sm pb-1 border-b border-[#232736]">

            ${escapeHtml(state.taskPlan.task_goal)}

          </div>

          <div class="space-y-2">

            ${state.taskPlan.steps.map((s, idx) => `

              <div class="flex items-start gap-2.5 p-2 rounded-lg bg-[#090a0f] border border-[#232736]">

                <span class="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-mono shrink-0 ${

                  s.status === 'completed' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40' :

                  s.status === 'in_progress' ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40 animate-pulse' :

                  'bg-slate-800 text-slate-400'

                }">

                  ${s.status === 'completed' ? '✓' : idx + 1}

                </span>

                <div class="flex-1">

                  <div class="font-medium text-slate-200">${escapeHtml(s.title)}</div>

                  ${s.description ? `<div class="text-[11px] text-slate-400 mt-0.5">${escapeHtml(s.description)}</div>` : ''}

                </div>

              </div>

            `).join('')}

          </div>

        </div>

      `;

    }



    if (state.rightPanelTab === 'workspace') {

      return `

        <div class="space-y-3">

          <div class="flex items-center justify-between pb-1 border-b border-[#232736]">

            <span class="font-semibold text-slate-100 text-xs">Workspace Files</span>

            <button class="text-slate-400 hover:text-emerald-400 cursor-pointer" onclick="window.refreshFiles()" title="Refresh">

              ${icons.refresh}

            </button>

          </div>

          <div class="text-[11px] font-mono text-emerald-400 truncate">

            ${state.activeWorkspace ? state.activeWorkspace.path : 'Default Workspace'}

          </div>

          <div id="file-tree-container" class="space-y-1">

            <div class="text-slate-500 text-center py-6">Loading files...</div>

          </div>

        </div>

      `;

    }



    if (state.rightPanelTab === 'health') {

      return `

        <div class="space-y-4">

          <div class="font-semibold text-slate-100 text-xs pb-1 border-b border-[#232736] flex items-center justify-between">

            <span>Workstation Health</span>

            <span class="text-emerald-400 font-mono text-[11px]">PORT 46815</span>

          </div>



          <div class="space-y-3 font-mono text-[11px]">

            <div class="bg-[#090a0f] p-2.5 rounded-lg border border-[#232736] space-y-1">

              <div class="text-slate-400 font-sans">Operating System</div>

              <div class="text-slate-200 font-bold">${state.systemStats ? state.systemStats.os : 'Windows'}</div>

            </div>



            <div class="bg-[#090a0f] p-2.5 rounded-lg border border-[#232736] space-y-1">

              <div class="text-slate-400 font-sans">Permission Security</div>

              <div class="text-emerald-400 font-bold">Safe Local Execution</div>

            </div>



            <div class="bg-[#090a0f] p-2.5 rounded-lg border border-[#232736] space-y-1">

              <div class="text-slate-400 font-sans">Database Status</div>

              <div class="text-slate-200">SQLite3 (WAL Mode + FTS5)</div>

            </div>

          </div>

        </div>

      `;

    }



    if (state.rightPanelTab === 'memory') {

      const allFacts = state.memoryFacts || [];

      const q = (state.memoryFilter || '').trim().toLowerCase();

      const filteredFacts = q

        ? allFacts.filter(f => (f.content || '').toLowerCase().includes(q) || (f.category || '').toLowerCase().includes(q))

        : allFacts;

      const catStyles = {

        environment: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',

        user_preference: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',

        instruction: 'bg-amber-500/15 text-amber-300 border-amber-500/30',

        project_detail: 'bg-violet-500/15 text-violet-300 border-violet-500/30'

      };

      return `

        <div class="space-y-3">

          <div class="flex items-center justify-between pb-2.5 border-b border-white/10">

            <div class="flex items-center gap-2">

              <span class="w-6 h-6 rounded-lg bg-emerald-500/15 border border-emerald-500/25 flex items-center justify-center text-emerald-400">

                ${icons.brain}

              </span>

              <div>

                <div class="font-semibold text-zinc-100 text-xs leading-tight">Persistent Memory</div>

                <div class="text-[10px] text-zinc-500 font-mono">${allFacts.length} saved rule${allFacts.length === 1 ? '' : 's'}</div>

              </div>

            </div>

            <button

              type="button"

              onclick="window.openAddMemoryModal()"

              class="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-gradient-to-r from-emerald-600/90 to-teal-600/90 hover:from-emerald-500 hover:to-teal-500 text-white text-[11px] font-medium shadow-md shadow-emerald-950/50 border border-emerald-400/25 transition cursor-pointer"

            >

              <span>+ Add Fact</span>

            </button>

          </div>

          ${allFacts.length > 2 ? `

            <div class="relative">

              <input

                id="memory-filter-input"

                type="text"

                value="${escapeHtml(state.memoryFilter || '')}"

                oninput="window.setMemoryFilter(this.value)"

                placeholder="Filter memories..."

                class="w-full bg-[#090a0f] border border-white/10 rounded-lg px-2.5 py-1.5 text-[11px] text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-emerald-500/50 transition"

              />

            </div>

          ` : ''}

          <div id="memory-facts-list" class="space-y-2.5">

            ${filteredFacts.length > 0 ? filteredFacts.map(f => {

              const cat = (f.category || 'user_preference').toLowerCase();

              const catCls = catStyles[cat] || 'bg-zinc-500/15 text-zinc-300 border-zinc-500/30';

              const isGlobal = !f.conversation_id;

              return `

                <div class="group p-3 rounded-xl bg-[#0b0c12] hover:bg-[#11131d] border border-white/10 hover:border-emerald-500/25 transition space-y-2 shadow-sm">

                  <div class="flex items-center justify-between gap-2">

                    <div class="flex items-center gap-1.5 flex-wrap">

                      <span class="text-[10px] font-mono px-2 py-0.5 rounded-full border ${catCls}">${escapeHtml(cat.replace(/_/g, ' ').toUpperCase())}</span>

                      <span class="text-[9px] font-mono px-1.5 py-0.5 rounded-full border ${isGlobal ? 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30' : 'bg-zinc-800 text-zinc-400 border-white/10'}">${isGlobal ? 'GLOBAL' : 'SESSION'}</span>

                    </div>

                    <button

                      type="button"

                      title="Delete fact"

                      class="opacity-70 group-hover:opacity-100 text-zinc-500 hover:text-rose-400 p-1 rounded-md hover:bg-rose-500/10 transition cursor-pointer"

                      onclick="window.delMemory('${f.id}')"

                    >${icons.x}</button>

                  </div>

                  <div class="text-zinc-300 text-xs leading-relaxed break-words select-text">${escapeHtml(f.content)}</div>

                </div>

              `;

            }).join('') : `

              <div class="text-center py-8 px-3 rounded-xl border border-dashed border-white/10 bg-white/[0.02] space-y-2">

                <div class="w-9 h-9 mx-auto rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">${icons.brain}</div>

                <div class="text-zinc-300 text-xs font-medium">${q ? 'No matching facts found' : 'No persistent memories yet'}</div>

                <div class="text-zinc-500 text-[11px] leading-relaxed">${q ? 'Try a different keyword.' : 'Save preferences, formatting rules, or project facts so NOVA remembers them automatically.'}</div>

              </div>

            `}

          </div>

        </div>

      `;

    }



    return '';

  }



  // Graphical Context Dropdown Menu

  function renderDropdownMenu() {

    if (!state.activeDropdown || state.activeDropdown.type !== 'conv') return '';

    const convId = state.activeDropdown.convId;

    const c = state.conversations.find(x => x.id === convId);

    const isPinned = c && c.is_pinned;



    return `

      <div

        id="context-menu-container"

        class="fixed z-50 bg-[#16161c] border border-white/10 rounded-xl shadow-2xl p-1.5 w-52 backdrop-blur-md select-none"

        style="top: ${state.activeDropdown.y}px; left: ${state.activeDropdown.x}px;"

        onclick="event.stopPropagation()"

      >

        <div class="text-[10px] font-mono text-zinc-500 px-2 py-1 uppercase tracking-wider flex items-center justify-between">

          <span>Session Options</span>

          <button onclick="window.closeDropdownMenu()" class="text-zinc-500 hover:text-white cursor-pointer">${icons.x}</button>

        </div>

        <button

          onclick="window.startRenameConversation('${convId}')"

          class="w-full flex items-center gap-2.5 px-2.5 py-1.5 text-xs text-zinc-300 hover:text-white hover:bg-white/10 rounded-lg transition text-left cursor-pointer"

        >

          <span class="text-zinc-400">${icons.edit}</span>

          <span>Rename Session</span>

        </button>

        <button

          onclick="window.togglePin('${convId}')"

          class="w-full flex items-center gap-2.5 px-2.5 py-1.5 text-xs text-zinc-300 hover:text-white hover:bg-white/10 rounded-lg transition text-left cursor-pointer"

        >

          <span class="text-zinc-400">${icons.pin}</span>

          <span>${isPinned ? 'Unpin from Top' : 'Pin to Top'}</span>

        </button>

        <button

          onclick="window.exportConversationMarkdown('${convId}')"

          class="w-full flex items-center gap-2.5 px-2.5 py-1.5 text-xs text-zinc-300 hover:text-white hover:bg-white/10 rounded-lg transition text-left cursor-pointer"

        >

          <span class="text-zinc-400">${icons.file}</span>

          <span>Export Markdown</span>

        </button>

        <button

          onclick="window.copyConversationId('${convId}')"

          class="w-full flex items-center gap-2.5 px-2.5 py-1.5 text-xs text-zinc-300 hover:text-white hover:bg-white/10 rounded-lg transition text-left cursor-pointer"

        >

          <span class="text-zinc-400">${icons.copy}</span>

          <span>Copy Session ID</span>

        </button>

        <div class="h-px bg-white/5 my-1"></div>

        <button

          onclick="window.deleteConv('${convId}')"

          class="w-full flex items-center gap-2.5 px-2.5 py-1.5 text-xs text-rose-400 hover:text-rose-300 hover:bg-rose-500/10 rounded-lg transition text-left cursor-pointer"

        >

          <span>${icons.trash}</span>

          <span>Delete Session</span>

        </button>

      </div>

    `;

  }



  // Graphical Rename Modal

  function renderRenameModal() {

    if (!state.renameModalConvId) return '';

    return `

      <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm select-none" onclick="window.closeRenameModal(event)">

        <div class="bg-[#18181d] border border-white/10 rounded-2xl w-full max-w-md p-5 shadow-2xl flex flex-col gap-4" onclick="event.stopPropagation()">

          <div class="flex items-center justify-between pb-3 border-b border-white/5">

            <div class="flex items-center gap-2.5">

              <div class="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center border border-emerald-500/20">

                ${icons.edit}

              </div>

              <h3 class="text-sm font-semibold text-white">Rename Session</h3>

            </div>

            <button id="btn-rename-close" onclick="window.closeRenameModal()" class="text-zinc-400 hover:text-white p-1 rounded-lg hover:bg-white/5 cursor-pointer">

              ${icons.x}

            </button>

          </div>

          <div class="flex flex-col gap-1.5">

            <label class="text-xs text-zinc-400 font-medium">Session Title</label>

            <input

              id="rename-modal-input"

              type="text"

              value="${escapeHtml(state.renameModalValue)}"

              class="w-full bg-[#111115] border border-white/10 rounded-xl px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-emerald-500 transition"

              placeholder="Enter new conversation name..."

              onkeydown="if (event.key === 'Enter') window.submitRenameModal()"

            />

          </div>

          <div class="flex items-center justify-end gap-2 pt-2">

            <button id="btn-rename-cancel" onclick="window.closeRenameModal()" class="px-4 py-2 text-xs font-medium text-zinc-400 hover:text-white hover:bg-white/5 rounded-xl transition cursor-pointer">

              Cancel

            </button>

            <button id="btn-rename-save" onclick="window.submitRenameModal()" class="px-4 py-2 text-xs font-medium bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl shadow-lg transition cursor-pointer">

              Save Title

            </button>

          </div>

        </div>

      </div>

    `;

  }



  // Graphical Add Memory Modal

  function renderAddMemoryModal() {

    if (!state.addMemoryModalOpen) return '';

    const categories = [

      { id: 'user_preference', label: 'User Preference', desc: 'Language, tone, workflow style', cls: 'border-emerald-500/50 bg-emerald-500/15 text-emerald-300' },

      { id: 'environment', label: 'Environment / UI', desc: 'Rendering, OS, runtime rules', cls: 'border-cyan-500/50 bg-cyan-500/15 text-cyan-300' },

      { id: 'instruction', label: 'Instruction', desc: 'Permanent behavioral directive', cls: 'border-amber-500/50 bg-amber-500/15 text-amber-300' },

      { id: 'project_detail', label: 'Project Detail', desc: 'Stack, repo, architecture notes', cls: 'border-violet-500/50 bg-violet-500/15 text-violet-300' }

    ];

    const selCat = state.addMemoryCategory || 'user_preference';

    const selScope = state.addMemoryScope || 'global';



    return `

      <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 select-none animate-fade-in" onclick="window.closeAddMemoryModal(event)">

        <div class="bg-[#14151c] border border-white/15 rounded-2xl w-full max-w-lg shadow-[0_24px_80px_rgba(0,0,0,0.75)] overflow-hidden flex flex-col" onclick="event.stopPropagation()">

          <!-- Gradient Accent Header -->

          <div class="px-5 py-4 bg-gradient-to-r from-[#171923] via-[#151821] to-[#13191d] border-b border-white/10 flex items-center justify-between">

            <div class="flex items-center gap-3">

              <div class="w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-500/20 to-cyan-500/20 text-emerald-300 flex items-center justify-center border border-emerald-400/30 shadow-inner">

                ${icons.brain}

              </div>

              <div>

                <h3 class="text-sm font-semibold text-white tracking-tight">Add Persistent Memory Fact</h3>

                <p class="text-[11px] text-zinc-400">Injected automatically into NOVA's context memory</p>

              </div>

            </div>

            <button type="button" onclick="window.closeAddMemoryModal()" class="text-zinc-400 hover:text-white p-1.5 rounded-lg hover:bg-white/10 transition cursor-pointer">

              ${icons.x}

            </button>

          </div>



          <div class="p-5 space-y-4">

            <!-- Category Picker -->

            <div class="space-y-2">

              <label class="text-[11px] font-semibold uppercase tracking-wider text-zinc-400">Category</label>

              <div class="grid grid-cols-2 gap-2">

                ${categories.map(c => {

                  const active = selCat === c.id;

                  return `

                    <button

                      type="button"

                      onclick="window.setAddMemoryCategory('${c.id}')"

                      class="p-2.5 rounded-xl border text-left transition cursor-pointer ${active ? c.cls + ' shadow-sm' : 'border-white/10 bg-[#0d0e14] hover:bg-[#171923] text-zinc-300'}"

                    >

                      <div class="text-xs font-semibold">${c.label}</div>

                      <div class="text-[10px] opacity-75 mt-0.5">${c.desc}</div>

                    </button>

                  `;

                }).join('')}

              </div>

            </div>



            <!-- Scope Toggle -->

            <div class="space-y-1.5">

              <label class="text-[11px] font-semibold uppercase tracking-wider text-zinc-400">Memory Scope</label>

              <div class="grid grid-cols-2 gap-2 p-1 rounded-xl bg-[#0b0c11] border border-white/10">

                <button

                  type="button"

                  onclick="window.setAddMemoryScope('global')"

                  class="py-1.5 px-3 rounded-lg text-xs font-medium transition cursor-pointer ${selScope === 'global' ? 'bg-indigo-600/30 text-indigo-200 border border-indigo-400/40 shadow-sm' : 'text-zinc-400 hover:text-zinc-200'}"

                >Global (All Chats)</button>

                <button

                  type="button"

                  onclick="window.setAddMemoryScope('session')"

                  class="py-1.5 px-3 rounded-lg text-xs font-medium transition cursor-pointer ${selScope === 'session' ? 'bg-emerald-600/30 text-emerald-200 border border-emerald-400/40 shadow-sm' : 'text-zinc-400 hover:text-zinc-200'}"

                >Current Session Only</button>

              </div>

            </div>



            <!-- Fact Input -->

            <div class="space-y-1.5">

              <label class="text-[11px] font-semibold uppercase tracking-wider text-zinc-400">Memory Content</label>

              <textarea

                id="add-memory-input"

                rows="4"

                class="w-full bg-[#0b0c11] border border-white/15 rounded-xl px-3.5 py-2.5 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-emerald-500/70 transition resize-none leading-relaxed"

                placeholder="e.g. When showing images in chat, use styled HTML <img> tags and rich flexbox layouts..."

                onkeydown="if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); window.submitAddMemoryModal(); }"

              ></textarea>

              <div class="flex items-center justify-between text-[10px] text-zinc-500">

                <span>Press Enter to save, Shift+Enter for new line</span>

              </div>

            </div>

          </div>



          <!-- Footer Actions -->

          <div class="px-5 py-3.5 bg-[#0f1016] border-t border-white/10 flex items-center justify-end gap-2.5">

            <button type="button" onclick="window.closeAddMemoryModal()" class="px-4 py-2 text-xs font-medium text-zinc-400 hover:text-white hover:bg-white/5 rounded-xl transition cursor-pointer">

              Cancel

            </button>

            <button type="button" onclick="window.submitAddMemoryModal()" class="px-4 py-2 text-xs font-semibold bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 text-white rounded-xl shadow-lg shadow-emerald-950/50 transition cursor-pointer">

              Save to Memory

            </button>

          </div>

        </div>

      </div>

    `;

  }



  function renderModal() {

    if (state.activeSubModal === 'add_skill') return renderAddSkillModal();

    if (state.activeSubModal === 'add_mcp') return renderAddMCPModal();

    if (state.activeModal === 'confirm_dialog') return renderConfirmModal();

    if (state.activeModal === 'onboarding_provider') return renderOnboardingProviderModal();

    if (state.activeModal === 'provider') return renderProviderModal();

    if (state.activeModal === 'settings') return renderSettingsModal();

    return '';

  }



  function renderConfirmModal() {

    const config = state.confirmDialogConfig || {

      title: 'Confirm Action',

      message: 'Are you sure you want to proceed?',

      confirmText: 'Confirm',

      confirmClass: 'bg-rose-600 hover:bg-rose-500 text-white'

    };



    return `

      <div class="modal-overlay" onclick="window.closeConfirmModal()">

        <div class="modal-content max-w-md bg-[#16161c] border border-white/10 rounded-2xl shadow-2xl p-0 overflow-hidden" onclick="event.stopPropagation()">

          <div class="px-5 py-4 border-b border-white/10 flex items-center justify-between bg-[#1a1a22]">

            <div class="flex items-center gap-2.5">

              <span class="w-2.5 h-2.5 rounded-full bg-rose-400 animate-pulse"></span>

              <span class="font-bold text-sm text-white">${escapeHtml(config.title)}</span>

            </div>

            <button class="text-zinc-400 hover:text-white p-1 rounded cursor-pointer" onclick="window.closeConfirmModal()">${icons.x}</button>

          </div>

          <div class="p-5 space-y-4 text-xs">

            <p class="text-zinc-300 leading-relaxed text-sm">

              ${escapeHtml(config.message)}

            </p>

            <div class="pt-2 flex justify-end gap-2 border-t border-white/5">

              <button class="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-zinc-300 font-medium transition cursor-pointer" onclick="window.closeConfirmModal()">

                Cancel

              </button>

              <button id="btn-confirm-action" class="px-4 py-2 rounded-xl font-bold transition cursor-pointer shadow-lg ${config.confirmClass || 'bg-rose-600 hover:bg-rose-500 text-white'}" onclick="window.executeConfirmModalAction()">

                ${escapeHtml(config.confirmText || 'Confirm')}

              </button>

            </div>

          </div>

        </div>

      </div>

    `;

  }



  function renderSettingsModal() {

    const tabs = [

      { id: 'general', label: '1. General & System', icon: icons.settings },

      { id: 'providers', label: '2. AI Providers & APIs', icon: icons.cpu, badge: state.providers ? state.providers.length : 0 },

      { id: 'skills', label: '3. Agent Skills & / Commands', icon: icons.sparkles, badge: state.skills ? state.skills.length : 0, highlight: true },

      { id: 'mcp', label: '4. MCP Servers & External Tools', icon: icons.toolbox, badge: (state.mcpServers || []).filter(s => s.status === 'connected').length + ' Online', highlight: true },

      { id: 'prompts', label: '5. System Directives', icon: icons.file },

      { id: 'terminal', label: '6. Terminal & PowerShell', icon: icons.terminal },

      { id: 'database', label: '7. SQLite Storage Engine', icon: icons.folder },

      { id: 'security', label: '8. Security & Firewall', icon: icons.shield },

      { id: 'logs', label: '9. Diagnostic Audit Logs', icon: icons.clock },

      { id: 'about', label: '10. About NOVA Workstation', icon: icons.antigravity }

    ];



    return `

      <div class="modal-overlay" onclick="window.closeModal(event)">

        <div class="modal-content max-w-5xl h-[85vh] flex flex-col p-0 overflow-hidden bg-[#121217] border border-white/10 rounded-2xl shadow-2xl" onclick="event.stopPropagation()">

          

          <!-- Header -->

          <div class="px-6 py-4 border-b border-white/10 flex items-center justify-between bg-[#16161c]">

            <div class="flex items-center gap-3">

              <div class="w-8 h-8 rounded-xl bg-emerald-500/15 text-emerald-400 flex items-center justify-center border border-emerald-500/20">

                ${icons.settings}

              </div>

              <div>

                <h2 class="text-sm font-bold text-white tracking-tight flex items-center gap-2">

                  NOVA Control Center & Customizations

                  <span class="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-mono border border-emerald-500/20">v1.0.0</span>

                </h2>

                <p class="text-[11px] text-zinc-400 mt-0.5">Manage agent profiles, skills, MCP servers, and local automation backends</p>

              </div>

            </div>

            <button class="w-8 h-8 rounded-lg text-zinc-400 hover:text-white hover:bg-white/5 flex items-center justify-center transition cursor-pointer" onclick="window.closeModal()">

              ${icons.x}

            </button>

          </div>



          <!-- Body with Sidebar and Content -->

          <div class="flex-1 flex overflow-hidden">

            <!-- Tabs Sidebar -->

            <div class="w-64 border-r border-white/10 bg-[#14141a] p-3 space-y-1 overflow-y-auto">

              ${tabs.map(t => `

                <button

                  class="w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-xs font-medium transition cursor-pointer ${state.settingsTab === t.id ? 'bg-white/10 text-white shadow-sm border border-white/10' : 'text-zinc-400 hover:bg-white/5 hover:text-zinc-200'}"

                  onclick="window.openSettingsTab('${t.id}')"

                >

                  <div class="flex items-center gap-2.5 min-w-0">

                    <span class="${t.highlight ? 'text-emerald-400' : 'text-zinc-400'} shrink-0">${t.icon}</span>

                    <span class="truncate">${t.label}</span>

                  </div>

                  ${t.badge !== undefined ? `

                    <span class="text-[10px] font-mono px-1.5 py-0.5 rounded ${t.highlight ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/20' : 'bg-white/5 text-zinc-400'}">${t.badge}</span>

                  ` : ''}

                </button>

              `).join('')}

            </div>



            <!-- Tab Content Viewport -->

            <div class="flex-1 p-6 overflow-y-auto bg-[#0f0f13]">

              ${renderSettingsTab(state.settingsTab || 'general')}

            </div>

          </div>



        </div>

      </div>

    `;

  }



  function renderSettingsTab(tab) {

    if (tab === 'skills') {

      const skillsList = state.skills && state.skills.length > 0 ? state.skills : slashSkills;

      return `

        <div class="space-y-5">

          <div class="flex items-center justify-between pb-3 border-b border-white/10">

            <div>

              <h3 class="text-sm font-bold text-white flex items-center gap-2">

                <span class="text-emerald-400">${icons.sparkles}</span>

                Agent Skills & Slash Commands

              </h3>

              <p class="text-xs text-zinc-400 mt-1">

                Extend NOVA with specialized skills and custom slash triggers (e.g. /research, /code, /audit).

              </p>

            </div>

            <div class="flex items-center gap-2">

              <button class="px-3 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-zinc-300 border border-white/10 text-xs font-semibold flex items-center gap-1.5 transition cursor-pointer" onclick="window.rescanSkillsFolder()" title="Scan physical skills/ folder on disk for new/modified SKILL.md files">

                ${icons.refresh}

                <span>Rescan skills/ Folder</span>

              </button>

              <button class="px-3 py-1.5 rounded-xl bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/30 text-xs font-semibold flex items-center gap-1.5 transition cursor-pointer" onclick="window.openAddSkillModal()">

                ${icons.plus}

                <span>+ Add Skill / File</span>

              </button>

            </div>

          </div>



          <!-- Skills Catalog Grid -->

          <div class="grid grid-cols-1 md:grid-cols-2 gap-3">

            ${skillsList.map(sk => {

              const sIcon = getSkillIconSvg(sk.icon);

              const sColor = getSkillColorClass(sk.color);

              const sDesc = sk.description || sk.desc || '';

              return `

              <div class="p-4 rounded-xl bg-[#16161c] border border-white/10 hover:border-zinc-500/40 transition flex flex-col justify-between gap-3 shadow-md">

                <div>

                  <div class="flex items-center justify-between">

                    <div class="flex items-center gap-2.5">

                      <div class="w-8 h-8 rounded-xl ${sColor.bg} ${sColor.text} flex items-center justify-center shrink-0 border ${sColor.border} shadow-inner">

                        ${sIcon}

                      </div>

                      <div>

                        <span class="font-bold text-xs text-zinc-100">${escapeHtml(sk.name)}</span>

                        <div class="text-[10px] font-mono text-emerald-400 font-semibold">${escapeHtml(sk.command)}</div>

                      </div>

                    </div>

                    <span class="text-[9px] font-mono px-2 py-0.5 rounded-full ${sk.is_builtin ? 'bg-zinc-800 text-zinc-400 border border-white/5' : 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/20'}">

                      ${sk.is_builtin ? 'BUILTIN' : 'CUSTOM'}

                    </span>

                  </div>

                  <p class="text-[11px] text-zinc-400 mt-2.5 leading-relaxed">

                    ${escapeHtml(sDesc)}

                  </p>

                </div>

                <div class="pt-2 border-t border-white/5 flex items-center justify-between text-xs">

                  <div class="flex items-center gap-2">

                    <span class="text-[10px] text-zinc-500 font-mono">Trigger: ${escapeHtml(sk.command)}</span>

                    <span class="text-[9px] font-mono px-2 py-0.5 rounded bg-white/5 text-zinc-400 border border-white/5 flex items-center gap-1" title="Physical file on disk">

                      📁 ${escapeHtml(sk.file_path || ('skills/' + (sk.command || '').replace('/', '') + '/SKILL.md'))}

                    </span>

                  </div>

                  ${!sk.is_builtin ? `

                    <button class="text-rose-400 hover:text-rose-300 text-xs font-semibold px-2 py-1 rounded hover:bg-rose-500/10 transition cursor-pointer" onclick="window.deleteSkill('${sk.id}')">

                      Delete

                    </button>

                  ` : ''}

                </div>

              </div>

            `;

            }).join('')}

          </div>

        </div>

      `;

    }



    if (tab === 'mcp') {

      const servers = state.mcpServers || [];

      const presets = state.mcpPresets || [];

      return `

        <div class="space-y-6">

          <div class="flex items-center justify-between pb-3 border-b border-white/10">

            <div>

              <h3 class="text-sm font-bold text-white flex items-center gap-2">

                <span class="text-emerald-400">${icons.toolbox}</span>

                Model Context Protocol (MCP) Servers

              </h3>

              <p class="text-xs text-zinc-400 mt-1">

                Standard external tool server integration for AI agents (Filesystem, SQLite, Git, API Tools).

              </p>

            </div>

            <button class="px-3 py-1.5 rounded-xl bg-indigo-500/20 hover:bg-indigo-500/30 text-indigo-300 border border-indigo-500/30 text-xs font-semibold flex items-center gap-1.5 transition cursor-pointer" onclick="window.openAddMCPModal()">

              ${icons.plus}

              + Add MCP Server

            </button>

          </div>



          ${presets && presets.length > 0 ? `

            <!-- Presets Grid -->

            <div>

              <h4 class="text-xs font-semibold text-zinc-300 mb-2.5 flex items-center gap-2">

                <span>🚀 1-Click Popular MCP Presets</span>

              </h4>

              <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2.5">

                ${presets.map(p => `

                  <div class="p-3 rounded-xl bg-[#16161c] border border-white/10 flex flex-col justify-between gap-2">

                    <div>

                      <div class="font-bold text-xs text-zinc-200">${escapeHtml(p.name)}</div>

                      <div class="text-[10px] font-mono text-zinc-400 mt-0.5 truncate">${escapeHtml(p.url || p.command || '')} ${escapeHtml((p.args || []).join(' '))}</div>

                      <p class="text-[11px] text-zinc-400 mt-1.5 line-clamp-2">${escapeHtml(p.description)}</p>

                    </div>

                    <button class="w-full mt-1 px-2.5 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-zinc-200 border border-white/10 text-xs font-medium transition cursor-pointer flex items-center justify-center gap-1" onclick="window.installMCPPreset('${p.id}')">

                      ${icons.plus} Add Server

                    </button>

                  </div>

                `).join('')}

              </div>

            </div>

          ` : ''}



          <!-- Configured MCP Servers List -->

          <div>

            <h4 class="text-xs font-semibold text-zinc-300 mb-2.5 flex items-center justify-between">

              <span>Configured MCP Servers (${servers.length})</span>

              <span class="text-[10px] text-zinc-400 font-mono">Live connection status</span>

            </h4>

            

            ${servers.length === 0 ? `

              <div class="p-6 rounded-xl bg-[#16161c] border border-dashed border-white/10 text-center text-xs text-zinc-400">

                No MCP servers configured yet. You can add one using the 1-click presets above or connect a custom server.

              </div>

            ` : `

              <div class="space-y-2.5">

                ${servers.map(s => {

                  const isOnline = s.status === 'connected';

                  return `

                    <div class="p-3.5 rounded-xl bg-[#16161c] border border-white/10 flex items-center justify-between gap-4">

                      <div class="min-w-0 flex-1">

                        <div class="flex items-center gap-2">

                          <span class="w-2.5 h-2.5 rounded-full ${isOnline ? 'bg-emerald-400 animate-pulse' : s.status === 'error' ? 'bg-rose-400' : 'bg-zinc-500'}"></span>

                          <span class="font-bold text-xs text-zinc-100">${escapeHtml(s.name)}</span>

                          <span class="text-[10px] font-mono px-2 py-0.5 rounded bg-white/5 text-zinc-400 uppercase">${s.transport_type}</span>

                          ${s.tools_count ? `

                            <span class="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">${s.tools_count} AI Tools</span>

                          ` : ''}

                        </div>

                        <div class="text-[11px] font-mono text-zinc-400 mt-1 truncate">

                          ${escapeHtml(s.url || s.command || '')} ${escapeHtml((s.args || []).join(' '))}

                        </div>

                        ${s.last_error ? `

                          <div class="text-[11px] text-rose-400 mt-1 font-mono">Error: ${escapeHtml(s.last_error)}</div>

                        ` : ''}

                      </div>



                      <div class="flex items-center gap-2 shrink-0">

                        ${isOnline ? `

                          <button class="px-2.5 py-1 rounded-lg bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 border border-amber-500/30 text-xs transition cursor-pointer" onclick="window.disconnectMCPServer('${s.id}')">

                            Disconnect

                          </button>

                        ` : `

                          ${state.connectingMcpServerId === s.id ? `

                            <button disabled class="px-2.5 py-1 rounded-lg bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-xs cursor-wait font-semibold flex items-center gap-1.5 opacity-90">

                              <svg class="animate-spin h-3 w-3 text-indigo-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path></svg>

                              <span>Connecting...</span>

                            </button>

                          ` : `

                            <button class="px-2.5 py-1 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/30 text-xs transition cursor-pointer font-semibold" onclick="window.connectMCPServer('${s.id}')">

                              Connect Server

                            </button>

                          `}

                        `}

                        <button class="text-rose-400 hover:text-rose-300 p-1.5 rounded hover:bg-rose-500/10 transition cursor-pointer" onclick="window.deleteMCPServer('${s.id}')" title="Delete Server">

                          ${icons.trash}

                        </button>

                      </div>

                    </div>

                  `;

                }).join('')}

              </div>

            `}

          </div>

        </div>

      `;

    }



    if (tab === 'general') {

      return `

        <div class="space-y-4 max-w-xl text-xs">

          <div class="pb-2 border-b border-white/10">

            <h3 class="text-sm font-bold text-white">General & Environment Configuration</h3>

          </div>

          <div>

            <label class="block text-zinc-400 mb-1 font-semibold">Active Project Workspace</label>

            <input type="text" value="${escapeHtml(state.activeWorkspace ? state.activeWorkspace.path : 'C:\\Users\\Asus\\.gemini\\antigravity\\scratch\\nova')}" class="w-full bg-[#16161c] border border-white/10 rounded-xl px-3 py-2 font-mono text-emerald-400 text-xs" readonly />

          </div>

          <div class="p-3.5 bg-[#16161c] rounded-xl border border-white/10 flex items-center justify-between shadow-sm">

            <div>

              <div class="font-bold text-zinc-100 flex items-center gap-2">

                <span class="text-emerald-400">${icons.sparkles}</span>

                Interactive Product Tour

              </div>

              <p class="text-zinc-400 text-[11px] mt-0.5">Explore NOVA's core features, agent workflows, and controls with a step-by-step walkthrough.</p>

            </div>

            <button class="px-3.5 py-1.5 rounded-xl bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/30 text-xs font-semibold transition cursor-pointer" onclick="window.startTour(); window.closeModal();">

              Take Tour

            </button>

          </div>

          <div class="p-3 bg-[#16161c] rounded-xl border border-white/10 space-y-1">

            <div class="font-bold text-zinc-200">Local Architecture Verification</div>

            <p class="text-zinc-400 text-[11px] leading-relaxed">NOVA runs 100% locally on localhost:46815. All conversations, memory vectors, tool telemetry, and session logs remain securely stored in your local SQLite database.</p>

          </div>

        </div>

      `;

    }



    if (tab === 'providers') {

      const provs = state.providers || [];

      return `

        <div class="space-y-4">

          <div class="flex items-center justify-between pb-2 border-b border-white/10">

            <div>

              <h3 class="text-sm font-bold text-white">AI Model Providers & APIs</h3>

              <p class="text-[11px] text-zinc-400 mt-0.5">Models in chat follow your provider order below (oldest to newest)</p>

            </div>

            <div class="flex items-center gap-2">

              <button class="px-3 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-zinc-300 border border-white/10 text-xs font-semibold flex items-center gap-1.5 transition cursor-pointer" onclick="window.syncAllProviders(this)" title="Sync models from all configured providers at once">

                ${icons.refresh}

                <span>Sync All Models</span>

              </button>

              <button class="btn btn-primary text-xs cursor-pointer" onclick="window.openProviderModal()">+ Add Provider</button>

            </div>

          </div>

          ${provs.length === 0 ? `

            <div class="p-6 rounded-xl border border-dashed border-white/10 bg-[#13141a] text-center space-y-2">

              <div class="text-xs font-semibold text-zinc-200">No AI providers configured</div>

              <div class="text-[11px] text-zinc-500">Add Ollama, LM Studio, or an OpenAI-compatible API provider to enable models.</div>

            </div>

          ` : ''}

          <div class="space-y-3">

            ${provs.map((p, idx) => {

              const provModels = (state.models || []).filter(m => m.provider_id === p.id);

              return `

                <div class="p-4 bg-[#16161c] rounded-xl border border-white/10 space-y-3">

                  <div class="flex items-start justify-between gap-3 flex-wrap">

                    <div class="min-w-0">

                      <div class="flex items-center gap-2 flex-wrap">

                        <span class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/5 text-zinc-400 border border-white/10">#${idx + 1}</span>

                        <span class="font-bold text-xs text-white">${escapeHtml(p.name)}</span>

                        ${p.provider_type ? `<span class="text-[10px] font-mono px-2 py-0.5 rounded-full bg-indigo-500/15 text-indigo-300 border border-indigo-500/25">${escapeHtml(p.provider_type.toUpperCase())}</span>` : ''}

                      </div>

                      <div class="text-[11px] font-mono text-zinc-400 mt-1 break-all">${escapeHtml(p.base_url)}</div>

                    </div>

                    <div class="flex items-center gap-2 shrink-0">

                      <button class="px-2.5 py-1 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 border border-emerald-500/30 text-xs font-semibold transition cursor-pointer" onclick="window.syncProv('${p.id}', this)">

                        Sync Models

                      </button>

                      <button class="text-rose-400 hover:text-rose-300 text-xs font-semibold px-2 py-1 rounded hover:bg-rose-500/10 transition cursor-pointer" onclick="window.deleteProvider('${p.id}', this)">

                        Delete

                      </button>

                    </div>

                  </div>

                  <div class="pt-2.5 border-t border-white/5 space-y-2">

                    <div class="flex items-center justify-between text-[11px]">

                      <span class="font-semibold text-zinc-300">Models (${provModels.length})</span>

                      ${provModels.length === 0 ? '<span class="text-zinc-500 text-[10px]">Click Sync Models to discover</span>' : ''}

                    </div>

                    ${provModels.length > 0 ? `

                      <div class="flex flex-wrap gap-1.5">

                        ${provModels.map(m => `

                          <div class="inline-flex items-center gap-2 px-2.5 py-1 rounded-lg bg-[#0d0e14] border border-white/10 text-[11px] text-zinc-200" title="${escapeHtml(m.model_name)}">

                            <span class="w-1.5 h-1.5 rounded-full ${m.supports_vision ? 'bg-emerald-400' : 'bg-zinc-500'} shrink-0"></span>

                            <span class="font-medium">${escapeHtml(formatModelDisplayName(m.display_name || m.model_name))}</span>

                            ${m.supports_vision ? `<span class="px-1.5 py-0.5 rounded text-[10px] font-mono bg-emerald-500/15 text-emerald-300 border border-emerald-500/25 flex items-center gap-1 select-none" title="Multimodal Vision Supported">👁️ Vision</span>` : ''}

                            <button

                              type="button"

                              title="Remove model"

                              class="text-zinc-500 hover:text-rose-400 ml-0.5 cursor-pointer"

                              onclick="window.deleteProviderModel('${escapeHtml(m.id)}')"

                            >×</button>

                          </div>

                        `).join('')}

                      </div>

                    ` : ''}

                  </div>

                </div>

              `;

            }).join('')}

          </div>

        </div>

      `;

    }



    if (tab === 'terminal') {

      return `

        <div class="space-y-4">

          <div class="flex items-center justify-between pb-2 border-b border-white/10">

            <h3 class="text-sm font-bold text-white">Terminal & Execution Subsystem</h3>

            <span class="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">POWERSHELL / BASH / ZSH</span>

          </div>

          <div class="space-y-3 max-w-xl text-xs">

            <div class="p-3 bg-[#16161c] rounded-xl border border-white/10 space-y-1">

              <label class="block text-zinc-400 font-semibold">Primary Shell Engine</label>

              <div class="font-mono text-emerald-400 font-bold">Adaptive Native OS Shell (PowerShell / CMD / Bash / Zsh)</div>

              <p class="text-[11px] text-zinc-500">Automatically adapts shell execution to Windows, macOS, or Linux cleanly.</p>

            </div>

          </div>

        </div>

      `;

    }



    if (tab === 'database') {

      return `

        <div class="space-y-4 max-w-xl text-xs">

          <div class="pb-2 border-b border-white/10">

            <h3 class="text-sm font-bold text-white">SQLite Database & Storage Engine</h3>

          </div>

          <div class="p-3 bg-[#16161c] rounded-xl border border-white/10 space-y-2">

            <div class="flex justify-between text-zinc-400">

              <span>Database File:</span>

              <span class="text-zinc-200 font-mono">data/nova.db</span>

            </div>

            <div class="flex justify-between text-zinc-400">

              <span>Mode:</span>

              <span class="text-emerald-400 font-mono">SQLite3 WAL Mode</span>

            </div>

          </div>

        </div>

      `;

    }



    if (tab === 'security') {

      return `

        <div class="space-y-4 max-w-xl text-xs">

          <div class="pb-2 border-b border-white/10">

            <h3 class="text-sm font-bold text-white">Security & Permission Safeguards</h3>

          </div>

          <div class="p-3 bg-[#16161c] rounded-xl border border-white/10 space-y-1">

            <div class="font-bold text-emerald-400">Interactive Approval Gate</div>

            <p class="text-zinc-400 text-[11px] leading-relaxed">Destructive operations strictly require user confirmation before execution.</p>

          </div>

        </div>

      `;

    }



    if (tab === 'logs') {

      return `

        <div class="space-y-4">

          <div class="flex items-center justify-between pb-2 border-b border-white/10">

            <h3 class="text-sm font-bold text-white">Audit & Diagnostic Logs</h3>

            <button class="px-2.5 py-1 rounded bg-white/10 text-white text-xs hover:bg-white/20 transition cursor-pointer" onclick="window.fetchLogs()">Refresh</button>

          </div>

          <div id="logs-viewer" class="p-3 rounded-xl bg-black/40 border border-white/10 text-zinc-300 font-mono text-[11px] max-h-80 overflow-y-auto">

            Click Refresh to fetch live system logs...

          </div>

        </div>

      `;

    }



    if (tab === 'about') {

      return `

        <div class="space-y-4 max-w-lg text-xs text-zinc-300 leading-relaxed">

          <div class="flex items-center gap-3 pb-3 border-b border-white/10">

            <div class="w-10 h-10 rounded-xl bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400 font-bold text-lg">N</div>

            <div>

              <div class="text-sm font-bold text-white">NOVA AI Workstation</div>

              <div class="text-emerald-400 font-mono text-[11px] font-semibold">Version 1.0.0 (Public Release)</div>

            </div>

          </div>

          <p class="text-zinc-300 leading-relaxed">

            Production-grade autonomous AI Agent workstation for Windows. Direct integration with native PowerShell, desktop automation, local filesystem, external MCP tool servers, and extensible multi-step reasoning.

          </p>

          <div class="pt-3 border-t border-white/10 space-y-2">

            <div class="text-[11px] text-zinc-400 font-medium">Official Open-Source Repository:</div>

            <a href="https://github.com/GoatSecurity/nova-ai" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-2 px-3 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-emerald-400 hover:text-emerald-300 border border-white/10 transition cursor-pointer font-mono text-xs">

              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/></svg>

              <span>github.com/GoatSecurity/nova-ai</span>

            </a>

          </div>

        </div>

      `;

    }



    return '';

  }



  function renderAddSkillModal() {

    return `

      <div class="modal-overlay" onclick="window.closeSubModal()">

        <div class="modal-content max-w-lg bg-[#16161c] border border-white/10 rounded-2xl shadow-2xl p-0 overflow-hidden" onclick="event.stopPropagation()">

          <div class="px-6 py-4 border-b border-white/10 flex items-center justify-between bg-[#1a1a22]">

            <span class="font-bold text-sm text-white flex items-center gap-2">

              <span class="text-emerald-400">${icons.sparkles}</span>

              Add New Skill / SKILL.md File

            </span>

            <button class="text-zinc-400 hover:text-white p-1 rounded cursor-pointer" onclick="window.closeSubModal()">${icons.x}</button>

          </div>

          

          <div class="p-6 space-y-3.5 text-xs">

            <div>

              <label class="block text-zinc-300 mb-1 font-medium">Skill Name</label>

              <input id="skill-name" type="text" placeholder="e.g. Code Security Auditor" class="w-full bg-[#111116] border border-white/10 rounded-xl px-3 py-2 text-zinc-100 focus:outline-none focus:border-emerald-500" />

            </div>



            <div class="grid grid-cols-2 gap-3">

              <div>

                <label class="block text-zinc-300 mb-1 font-medium">Slash Command (Trigger)</label>

                <input id="skill-cmd" type="text" placeholder="/audit" class="w-full bg-[#111116] border border-white/10 rounded-xl px-3 py-2 font-mono text-emerald-400 focus:outline-none focus:border-emerald-500" />

              </div>

              <div>

                <label class="block text-zinc-300 mb-1 font-medium">Theme Color</label>

                <select id="skill-color" class="w-full bg-[#111116] border border-white/10 rounded-xl px-3 py-2 text-zinc-100 focus:outline-none focus:border-emerald-500">

                  <option value="indigo">Indigo</option>

                  <option value="emerald">Emerald</option>

                  <option value="amber">Amber</option>

                  <option value="purple">Purple</option>

                  <option value="rose">Rose</option>

                  <option value="blue">Blue</option>

                  <option value="cyan">Cyan</option>

                </select>

              </div>

            </div>



            <div>

              <label class="block text-zinc-300 mb-1 font-medium">Short Description</label>

              <input id="skill-desc" type="text" placeholder="e.g. Audit codebase for security vulnerabilities, flaws, and CVEs" class="w-full bg-[#111116] border border-white/10 rounded-xl px-3 py-2 text-zinc-100 focus:outline-none focus:border-emerald-500" />

            </div>



            <div>

              <label class="block text-zinc-300 mb-1 font-medium">System Prompt / Instructions</label>

              <textarea id="skill-prompt" rows="4" placeholder="You are an expert security code auditor. When this skill is active, meticulously inspect source files, check for injection flaws, review authentication, and provide patch recommendations..." class="w-full bg-[#111116] border border-white/10 rounded-xl px-3 py-2 text-zinc-100 focus:outline-none focus:border-emerald-500 leading-relaxed font-mono text-[11px] resize-none"></textarea>

            </div>



            <div class="pt-3 flex justify-end gap-2 border-t border-white/5">

              <button class="px-3.5 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-zinc-300 text-xs transition cursor-pointer" onclick="window.closeSubModal()">Cancel</button>

              <button class="px-4 py-1.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-bold text-xs transition cursor-pointer shadow-md" onclick="window.saveNewSkill()">Save & Activate Skill</button>

            </div>

          </div>

        </div>

      </div>

    `;

  }



  function renderAddMCPModal() {

    state.mcpModalType = state.mcpModalType || 'remote';

    return `

      <div class="modal-overlay" onclick="window.closeSubModal()">

        <div class="modal-content max-w-lg bg-[#16161c] border border-white/10 rounded-2xl shadow-2xl p-0 overflow-hidden" onclick="event.stopPropagation()">

          <div class="px-6 py-4 border-b border-white/10 flex items-center justify-between bg-[#1a1a22]">

            <span class="font-bold text-sm text-white flex items-center gap-2">

              <span class="text-indigo-400">${icons.toolbox}</span>

              Add MCP Server

            </span>

            <button class="text-zinc-400 hover:text-white p-1 rounded cursor-pointer" onclick="window.closeSubModal()">${icons.x}</button>

          </div>

          

          <div class="p-6 space-y-4 text-xs">

            <!-- Mode Switch: Remote HTTP vs Local Process -->

            <div class="grid grid-cols-2 gap-2 p-1 rounded-xl bg-black/30 border border-white/5">

              <button id="btn-mcp-tab-remote" type="button" class="py-2 px-3 rounded-lg font-semibold text-xs transition cursor-pointer flex items-center justify-center gap-2 ${state.mcpModalType === 'remote' ? 'bg-indigo-600 text-white shadow' : 'text-zinc-400 hover:text-white'}" onclick="window.switchMCPModalType('remote')">

                <span>🌐 Remote (HTTP / URL)</span>

              </button>

              <button id="btn-mcp-tab-local" type="button" class="py-2 px-3 rounded-lg font-semibold text-xs transition cursor-pointer flex items-center justify-center gap-2 ${state.mcpModalType === 'local' ? 'bg-indigo-600 text-white shadow' : 'text-zinc-400 hover:text-white'}" onclick="window.switchMCPModalType('local')">

                <span>💻 Local Process (stdio)</span>

              </button>

            </div>



            ${state.mcpModalType === 'remote' ? `

              <!-- Remote HTTP / URL Fields -->

              <div>

                <label class="block text-zinc-300 font-medium mb-1">Server Endpoint URL or JSON Config</label>

                <textarea id="mcp-remote-url" rows="3" placeholder="https://mcp.example.com/sse or paste Claude / Cursor JSON config:&#10;{&#10;  &quot;mcpServers&quot;: { &quot;my-tool&quot;: { &quot;url&quot;: &quot;https://...&quot; } }&#10;}" class="w-full bg-[#111116] border border-white/10 rounded-xl px-3 py-2 font-mono text-zinc-100 focus:outline-none focus:border-indigo-500 text-[11px] resize-none leading-relaxed"></textarea>

              </div>



              <div>

                <label class="block text-zinc-300 mb-1 font-medium">Server Name (Optional)</label>

                <input id="mcp-name" type="text" placeholder="e.g. Remote AI Tool" class="w-full bg-[#111116] border border-white/10 rounded-xl px-3 py-2 text-zinc-100 focus:outline-none focus:border-indigo-500" />

              </div>



              <div>

                <label class="block text-zinc-300 mb-1 font-medium">Optional Headers / Auth (JSON)</label>

                <input id="mcp-remote-env" type="text" placeholder='{"Authorization": "Bearer ..."}' class="w-full bg-[#111116] border border-white/10 rounded-xl px-3 py-2 text-zinc-100 focus:outline-none focus:border-indigo-500 font-mono text-[11px]" />

              </div>



              <div class="p-3 rounded-xl bg-indigo-950/20 border border-indigo-500/20 text-[11px] text-zinc-400">

                Direct stateless JSON-RPC over HTTP. Automatically discovers tools and registers them with the agent.

              </div>

            ` : `

              <!-- Local stdio Process Fields -->

              <div>

                <label class="block text-zinc-300 mb-1 font-medium">Server Name</label>

                <input id="mcp-name" type="text" placeholder="e.g. Local Filesystem or Git Explorer" class="w-full bg-[#111116] border border-white/10 rounded-xl px-3 py-2 text-zinc-100 focus:outline-none focus:border-indigo-500" />

              </div>



              <div class="grid grid-cols-3 gap-2">

                <div class="col-span-1">

                  <label class="block text-zinc-300 mb-1 font-medium">Command</label>

                  <input id="mcp-local-cmd" type="text" placeholder="npx / uvx / python" class="w-full bg-[#111116] border border-white/10 rounded-xl px-3 py-2 font-mono text-indigo-300 focus:outline-none focus:border-indigo-500" />

                </div>

                <div class="col-span-2">

                  <label class="block text-zinc-300 mb-1 font-medium">Arguments (space-separated)</label>

                  <input id="mcp-local-args" type="text" placeholder="-y @modelcontextprotocol/server-filesystem C:\\Projects" class="w-full bg-[#111116] border border-white/10 rounded-xl px-3 py-2 font-mono text-zinc-100 focus:outline-none focus:border-indigo-500" />

                </div>

              </div>



              <div>

                <label class="block text-zinc-300 mb-1 font-medium">Environment Variables (JSON)</label>

                <textarea id="mcp-local-env" rows="2" placeholder='{"GITHUB_TOKEN": "..."}' class="w-full bg-[#111116] border border-white/10 rounded-xl px-3 py-2 text-zinc-100 focus:outline-none focus:border-indigo-500 font-mono text-[11px] resize-none"></textarea>

              </div>



              <div class="p-3 rounded-xl bg-emerald-950/20 border border-emerald-500/20 text-[11px] text-zinc-400">

                Executes a local background process via stdin/stdout with live tool discovery.

              </div>

            `}



            ${state.mcpConnecting ? `

              <div class="p-3 rounded-xl bg-indigo-500/10 border border-indigo-500/25 text-indigo-300 text-xs flex items-center gap-3 animate-pulse">

                <svg class="animate-spin h-4 w-4 text-indigo-400 shrink-0" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">

                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>

                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>

                </svg>

                <div>

                  <div class="font-bold text-white text-xs">Connecting to MCP Server...</div>

                  <div class="text-[11px] text-indigo-300/80 mt-0.5">Contacting endpoint, performing handshake and querying tools/list. Please wait...</div>

                </div>

              </div>

            ` : ''}



            <div class="pt-3 flex justify-end gap-2 border-t border-white/5">

              <button class="px-3.5 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-zinc-300 text-xs transition cursor-pointer" onclick="window.closeSubModal()" ${state.mcpConnecting ? 'disabled' : ''}>Cancel</button>

              ${state.mcpConnecting ? `

                <button disabled class="px-4 py-1.5 rounded-xl bg-indigo-600/60 text-white font-bold text-xs cursor-wait shadow-md flex items-center gap-2 opacity-90">

                  <svg class="animate-spin h-3.5 w-3.5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">

                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>

                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>

                  </svg>

                  <span>Connecting & Discovering Tools...</span>

                </button>

              ` : `

                <button class="px-4 py-1.5 rounded-xl bg-indigo-500 hover:bg-indigo-400 text-white font-bold text-xs transition cursor-pointer shadow-md flex items-center gap-1.5" onclick="window.saveNewMCPServer()">

                  <span>Connect Server</span>

                </button>

              `}

            </div>

          </div>

        </div>

      </div>

    `;

  }



  function renderProviderModal() {

    return `

      <div class="modal-overlay" onclick="window.closeModal(event)">

        <div class="modal-content max-w-md bg-[#16161c] border border-white/10 rounded-2xl shadow-2xl p-0 overflow-hidden" onclick="event.stopPropagation()">

          <div class="px-5 py-3.5 border-b border-white/10 flex items-center justify-between bg-[#1a1a22]">

            <span class="font-bold text-sm text-white">Add AI Provider</span>

            <button class="text-zinc-400 hover:text-white p-1 rounded cursor-pointer" onclick="window.closeModal()">${icons.x}</button>

          </div>

          <div class="p-5 space-y-3 text-xs">

            <div>

              <label class="block text-zinc-400 mb-1 font-medium">Provider Name</label>

              <input id="prov-name" type="text" placeholder="e.g. Local vLLM / OpenAI / DeepSeek" class="w-full bg-[#111116] border border-white/10 rounded-xl px-3 py-2 text-zinc-100 focus:outline-none focus:border-emerald-500" />

            </div>



            <div>

              <label class="block text-zinc-400 mb-1 font-medium">Base URL</label>

              <input id="prov-url" type="text" placeholder="https://api.openai.com/v1" class="w-full bg-[#111116] border border-white/10 rounded-xl px-3 py-2 font-mono text-zinc-100 focus:outline-none focus:border-emerald-500" />

            </div>

            <div>

              <label class="block text-zinc-400 mb-1 font-medium">API Key (Optional for local models)</label>

              <input id="prov-key" type="password" placeholder="sk-..." class="w-full bg-[#111116] border border-white/10 rounded-xl px-3 py-2 font-mono text-zinc-100 focus:outline-none focus:border-emerald-500" />

            </div>

            <div class="pt-2 flex justify-end gap-2 border-t border-white/5">

              <button class="px-3 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-zinc-300 text-xs transition cursor-pointer" onclick="window.closeModal()">Cancel</button>

              <button id="btn-save-new-provider" class="px-4 py-1.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-bold text-xs transition cursor-pointer flex items-center gap-1.5" onclick="window.saveNewProvider()">Save Provider</button>

            </div>

          </div>

        </div>

      </div>

    `;

  }







  // Onboarding AI Provider Presets



  function detectProviderType(url, name, key) {

    const u = (url || '').toLowerCase();

    const n = (name || '').toLowerCase();

    if (u.includes('anthropic.com') || n.includes('claude') || n.includes('anthropic')) return 'anthropic';

    if (u.includes('generativelanguage.googleapis.com') || n.includes('gemini') || n.includes('google')) return 'gemini';

    if (u.includes('/v1') || u.includes('/models') || u.includes('/chat/completions')) return 'openai_compatible';

    if (u.includes(':11434') || n.includes('ollama')) return 'ollama';

    if (u.includes(':1234') || n.includes('lm studio') || n.includes('lmstudio')) return 'lm_studio';

    if (u.includes('groq.com') || n.includes('groq')) return 'groq';

    if (u.includes('deepseek.com') || n.includes('deepseek')) return 'deepseek';

    return 'openai_compatible';

  }



  const ONBOARDING_PRESETS = {

    openai: {

      name: 'OpenAI',

      type: 'openai_compatible',

      url: 'https://api.openai.com/v1',

      model: 'gpt-4o-mini',

      keyPlaceholder: 'sk-proj-...',

      keyRequired: true

    },

    anthropic: {

      name: 'Anthropic Claude',

      type: 'anthropic',

      url: 'https://api.anthropic.com/v1',

      model: 'claude-3-5-sonnet-20241022',

      keyPlaceholder: 'sk-ant-...',

      keyRequired: true

    },

    gemini: {

      name: 'Google Gemini',

      type: 'openai_compatible',

      url: 'https://generativelanguage.googleapis.com/v1beta/openai/',

      model: 'gemini-1.5-flash',

      keyPlaceholder: 'AIzaSy...',

      keyRequired: true

    },

    groq: {

      name: 'Groq Cloud',

      type: 'openai_compatible',

      url: 'https://api.groq.com/openai/v1',

      model: 'llama-3.3-70b-versatile',

      keyPlaceholder: 'gsk_...',

      keyRequired: true

    },

    deepseek: {

      name: 'DeepSeek',

      type: 'openai_compatible',

      url: 'https://api.deepseek.com/v1',

      model: 'deepseek-chat',

      keyPlaceholder: 'sk-...',

      keyRequired: true

    },

    ollama: {

      name: 'Ollama (Local)',

      type: 'ollama',

      url: 'http://127.0.0.1:11434',

      model: 'llama3:latest',

      keyPlaceholder: 'Not required for local models',

      keyRequired: false

    },

    lm_studio: {

      name: 'LM Studio (Local)',

      type: 'lm_studio',

      url: 'http://127.0.0.1:1234/v1',

      model: 'local-model',

      keyPlaceholder: 'Not required for local models',

      keyRequired: false

    }

  };



  function renderOnboardingProviderModal() {

    const curPresetKey = state.onboardingPreset || 'openai';

    const curPreset = ONBOARDING_PRESETS[curPresetKey] || ONBOARDING_PRESETS.openai;



    return `

      <div class="modal-overlay">

        <div class="modal-content max-w-xl bg-[#16161c] border border-white/10 rounded-2xl shadow-2xl p-0 overflow-hidden" onclick="event.stopPropagation()">

          <div class="px-6 py-4 border-b border-white/10 flex items-center justify-between bg-[#191a24]">

            <div class="flex items-center gap-3">

              <div class="w-9 h-9 rounded-xl bg-emerald-500/15 text-emerald-400 flex items-center justify-center border border-emerald-500/20 shadow-inner">

                ${icons.cpu}

              </div>

              <div>

                <h2 class="text-sm font-bold text-white tracking-tight flex items-center gap-2">

                  Welcome to NOVA Workstation

                  <span class="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-mono border border-emerald-500/20">Initial Setup</span>

                </h2>

                <p class="text-[11px] text-zinc-400 mt-0.5">Configure an AI provider to power NOVA's reasoning, or skip to configure later</p>

              </div>

            </div>

            <button id="btn-onboard-close" class="text-zinc-400 hover:text-white p-1 rounded cursor-pointer" onclick="window.skipOnboardingProvider()">${icons.x}</button>

          </div>



          <div class="p-6 space-y-4 text-xs">

            <div>

              <label class="block text-zinc-300 font-semibold mb-2">Select Provider Preset</label>

              <div class="grid grid-cols-3 sm:grid-cols-4 gap-2">

                ${Object.entries(ONBOARDING_PRESETS).map(([k, p]) => `

                  <button type="button" data-preset="${k}" class="btn-onboard-preset py-2 px-2.5 rounded-xl border text-left transition cursor-pointer flex flex-col justify-between gap-1 ${curPresetKey === k ? 'bg-emerald-500/15 border-emerald-500/50 text-white shadow-sm' : 'bg-black/30 border-white/5 text-zinc-400 hover:text-zinc-200 hover:border-white/10'}" onclick="window.setOnboardPreset(\'${k}\')">

                    <span class="font-bold text-[11px] truncate">${escapeHtml(p.name)}</span>

                    <span class="text-[9px] font-mono text-zinc-500 truncate">${p.keyRequired ? 'API Key' : 'Local'}</span>

                  </button>

                `).join('')}

              </div>

            </div>



            <div>

              <div class="flex items-center justify-between mb-1">

                <label class="block text-zinc-300 font-medium">Provider Display Name</label>

                <span class="text-[10px] text-emerald-400 font-mono flex items-center gap-1">

                  <span>⚡</span> Models auto-discovered on save

                </span>

              </div>

              <input id="onboard-name" type="text" value="${escapeHtml(curPreset.name)}" class="w-full bg-[#111116] border border-white/10 rounded-xl px-3 py-2 text-zinc-100 focus:outline-none focus:border-emerald-500 text-xs font-medium" />

            </div>



            <div>

              <label class="block text-zinc-300 mb-1 font-medium">API Base URL</label>

              <input id="onboard-url" type="text" value="${escapeHtml(curPreset.url)}" class="w-full bg-[#111116] border border-white/10 rounded-xl px-3 py-2 font-mono text-xs text-zinc-300 focus:outline-none focus:border-emerald-500" />

            </div>



            <div>

              <label class="block text-zinc-300 mb-1 font-medium flex items-center justify-between">

                <span>API Key ${curPreset.keyRequired ? '<span class="text-emerald-400">*</span>' : '<span class="text-zinc-500 font-normal">(Optional for local)</span>'}</span>

              </label>

              <input id="onboard-key" type="password" placeholder="${escapeHtml(curPreset.keyPlaceholder)}" class="w-full bg-[#111116] border border-white/10 rounded-xl px-3 py-2 font-mono text-xs text-zinc-100 focus:outline-none focus:border-emerald-500" />

            </div>



            <div class="p-3 rounded-xl bg-white/[0.02] border border-white/5 text-[11px] text-zinc-400 flex items-start gap-2">

              <span class="text-emerald-400 shrink-0 mt-0.5">${icons.info || 'ℹ️'}</span>

              <span>You can always manage, switch, or add more providers later from <strong>Settings &gt; AI Providers</strong>.</span>

            </div>



            <div class="pt-3 flex items-center justify-between border-t border-white/5">

              <button id="btn-onboard-skip" class="px-4 py-2 rounded-xl text-zinc-400 hover:text-white hover:bg-white/5 text-xs font-semibold transition cursor-pointer" onclick="window.skipOnboardingProvider()">

                Skip for Now

              </button>

              <button id="btn-onboard-save" class="px-5 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-bold text-xs transition cursor-pointer shadow-lg shadow-emerald-500/20 flex items-center gap-1.5" onclick="window.saveOnboardingProvider()">

                <span>Save & Continue</span>

                <span>→</span>

              </button>

            </div>

          </div>

        </div>

      </div>

    `;

  }



  // Interactive Product Walkthrough Tour

  const TOUR_STEPS = [

    {

      title: "Welcome to NOVA AI Workstation",

      badge: "Getting Started",

      text: "NOVA is an autonomous agentic AI workstation running natively on your PC. It automates system workflows, analyzes and patches codebases, researches the web, and executes PowerShell commands.",

      highlightId: null,

      nextLabel: "Start Tour →"

    },

    {

      title: "Conversations & Workspace History",

      badge: "Step 1 of 5",

      text: "All your project conversations and tasks are organized here in the sidebar. Right-click any conversation to rename, pin to the top, export to Markdown, or inspect session details.",

      highlightId: "sidebar-container",

      nextLabel: "Next Feature →"

    },

    {

      title: "Dynamic Model & Provider Hub",

      badge: "Step 2 of 5",

      text: "Switch between cloud models (OpenAI, Claude, Gemini, DeepSeek) and local offline models (Ollama, LM Studio) instantly on the fly without restarting the application.",

      highlightId: "header-model-select",

      nextLabel: "Next Feature →"

    },

    {

      title: "Agent Input & Specialized Skills",

      badge: "Step 3 of 5",

      text: "Type any prompt in natural language, drag-and-drop file attachments, or type / to activate specialized skills such as /research (Deep Web Research), /code (Architect), or /terminal.",

      highlightId: "chat-input",

      nextLabel: "Next Feature →"

    },

    {

      title: "Live Activity & MCP Tool Telemetry",

      badge: "Step 4 of 5",

      text: "Click the activity button to open the right-hand drawer. Monitor real-time CPU/RAM meters, review running background tasks, inspect MCP external tools, and view live audit logs.",

      highlightId: "btn-toggle-activity-panel",

      nextLabel: "Next Feature →"

    },

    {

      title: "Control Center & MCP Customizations",

      badge: "Step 5 of 5",

      text: "Fine-tune system prompts, connect custom remote or local stdio MCP servers, configure safety permission modes, and customize agent personas to fit your workflow.",

      highlightId: "btn-toggle-settings",

      nextLabel: "Finish Tour ✓"

    }

  ];





  function renderAttachmentViewerModal() {

    if (!state.activeAttachmentViewer) return '';

    const att = state.activeAttachmentViewer;

    const lines = (att.content || '').split('\n');

    const lineCount = lines.length;



    return `

      <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 sm:p-6 select-none animate-fade-in" onclick="window.closeAttachmentViewer(event)">

        <div class="bg-[#14141a] border border-white/15 rounded-2xl w-full max-w-3xl max-h-[85vh] shadow-[0_24px_80px_rgba(0,0,0,0.85)] flex flex-col overflow-hidden" onclick="event.stopPropagation()">

          <!-- Header -->

          <div class="px-5 py-3.5 bg-[#181820] border-b border-white/10 flex items-center justify-between">

            <div class="flex items-center gap-3 min-w-0">

              <div class="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center border border-emerald-500/20 text-base">

                ${att.type === 'paste'

                  ? `<svg class="w-4 h-4 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/></svg>`

                  : `<svg class="w-4 h-4 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>`}

              </div>

              <div class="min-w-0">

                <h3 class="font-semibold text-sm text-zinc-100 truncate">${escapeHtml(att.name)}</h3>

                <p class="text-[11px] text-zinc-400 font-mono">${formatBytes(att.size)} &bull; ${lineCount} ${lineCount === 1 ? 'line' : 'lines'}</p>

              </div>

            </div>

            <div class="flex items-center gap-2">

              <button id="btn-copy-attachment-content" class="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-xs text-zinc-300 hover:text-white flex items-center gap-1.5 border border-white/10 transition cursor-pointer" onclick="window.copyAttachmentContent()">

                ${icons.copy}

                <span>Copy</span>

              </button>

              <button class="w-8 h-8 rounded-lg hover:bg-white/10 text-zinc-400 hover:text-white flex items-center justify-center transition cursor-pointer text-base font-bold" onclick="window.closeAttachmentViewer()">&times;</button>

            </div>

          </div>



          <!-- Code Viewer Body -->

          <div class="flex-1 p-4 overflow-y-auto bg-[#0d0d12] text-xs font-mono text-zinc-200 select-text leading-relaxed">

            <pre class="whitespace-pre font-mono m-0"><code>${escapeHtml(att.content)}</code></pre>

          </div>



          <!-- Footer -->

          <div class="px-5 py-2.5 bg-[#181820] border-t border-white/10 flex items-center justify-between text-xs text-zinc-400">

            <span>UTF-8 Plain Text / Code</span>

            <button class="px-4 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs text-zinc-200 cursor-pointer font-medium" onclick="window.closeAttachmentViewer()">Close</button>

          </div>

        </div>

      </div>

    `;

  }



  function renderImageLightboxModal() {

    if (!state.activeImageLightbox) return '';

    const img = state.activeImageLightbox;



    return `

      <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/90 backdrop-blur-md p-4 sm:p-6 select-none animate-fade-in" onclick="window.closeImageLightbox(event)">

        <div class="relative max-w-5xl max-h-[92vh] flex flex-col items-center justify-center" onclick="event.stopPropagation()">

          <!-- Top Toolbar -->

          <div class="w-full flex items-center justify-between pb-3 text-xs text-zinc-300">

            <div class="flex items-center gap-2">

              <svg class="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>

              <span class="font-medium truncate max-w-xs text-white">${escapeHtml(img.name)}</span>

              <span class="text-zinc-500 font-mono">(${formatBytes(img.size)})</span>

            </div>

            <div class="flex items-center gap-2">

              <a href="${escapeAttr(img.content)}" download="${escapeAttr(img.name)}" class="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-white text-xs flex items-center gap-1.5 transition">

                <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>

                Download

              </a>

              <button class="w-8 h-8 rounded-lg bg-white/10 hover:bg-white/20 text-white flex items-center justify-center transition cursor-pointer text-base font-bold" onclick="window.closeImageLightbox()">&times;</button>

            </div>

          </div>



          <!-- Image Body -->

          <div class="relative overflow-hidden rounded-2xl border border-white/15 bg-black/60 shadow-2xl flex items-center justify-center p-2">

            <img src="${escapeAttr(img.content)}" class="max-h-[80vh] max-w-[88vw] object-contain rounded-xl select-none" alt="${escapeAttr(img.name)}" />

          </div>

        </div>

      </div>

    `;

  }



  function renderTourOverlay() {

    if (state.activeTourStep === null || state.activeTourStep === undefined) return '';

    const stepIdx = Math.max(0, Math.min(state.activeTourStep, TOUR_STEPS.length - 1));

    const step = TOUR_STEPS[stepIdx];

    const isFirst = stepIdx === 0;

    const isLast = stepIdx === TOUR_STEPS.length - 1;



    return `

      <div class="fixed inset-0 z-50 pointer-events-auto bg-black/60 backdrop-blur-[2px] flex items-center justify-center p-4 select-none animate-fade-in" onclick="event.stopPropagation()">

        <div class="max-w-md w-full bg-[#16161c] border border-white/15 rounded-2xl shadow-2xl p-6 space-y-4 animate-scale-in">

          <div class="flex items-center justify-between">

            <span class="text-[10px] font-mono px-2.5 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/25 font-semibold">

              ${step.badge}

            </span>

            <button id="btn-tour-close" class="text-zinc-500 hover:text-white p-1 rounded transition cursor-pointer" onclick="window.skipTour()" title="Skip Tour">

              ${icons.x}

            </button>

          </div>



          <div class="space-y-2">

            <h3 class="text-base font-bold text-white tracking-tight flex items-center gap-2">

              <span class="text-emerald-400">${icons.sparkles}</span>

              ${step.title}

            </h3>

            <p class="text-xs text-zinc-300 leading-relaxed">

              ${step.text}

            </p>

          </div>



          <!-- Progress dots -->

          <div class="flex items-center justify-center gap-1.5 pt-2">

            ${TOUR_STEPS.map((_, idx) => `

              <span class="h-1.5 rounded-full transition-all duration-300 ${idx === stepIdx ? 'w-6 bg-emerald-400' : 'w-1.5 bg-white/20'}"></span>

            `).join('')}

          </div>



          <div class="pt-3 border-t border-white/10 flex items-center justify-between">

            <button id="btn-tour-skip" class="text-xs font-semibold text-zinc-400 hover:text-white px-2 py-1.5 rounded-lg transition cursor-pointer" onclick="window.skipTour()">

              Skip Tour

            </button>

            <div class="flex items-center gap-2">

              ${!isFirst ? `

                <button id="btn-tour-prev" class="px-3.5 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-zinc-300 text-xs font-semibold transition cursor-pointer" onclick="window.prevTourStep()">

                  Back

                </button>

              ` : ''}

              <button id="btn-tour-next" class="px-4 py-1.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-bold text-xs transition cursor-pointer shadow-lg shadow-emerald-500/20" onclick="window.nextTourStep()">

                ${step.nextLabel}

              </button>

            </div>

          </div>

        </div>

      </div>

    `;

  }



  function bindEvents() {



    const newChatBtn = document.getElementById('btn-new-chat');



    if (newChatBtn) newChatBtn.onclick = createNewConversation;



    // Fallback dual-layer bindings for Onboarding Modal

    const btnOnboardClose = document.getElementById('btn-onboard-close');

    if (btnOnboardClose) btnOnboardClose.onclick = (e) => { e.preventDefault(); e.stopPropagation(); window.skipOnboardingProvider(); };

    const btnOnboardSkip = document.getElementById('btn-onboard-skip');

    if (btnOnboardSkip) btnOnboardSkip.onclick = (e) => { e.preventDefault(); e.stopPropagation(); window.skipOnboardingProvider(); };

    const btnOnboardSave = document.getElementById('btn-onboard-save');

    if (btnOnboardSave) btnOnboardSave.onclick = (e) => { e.preventDefault(); e.stopPropagation(); window.saveOnboardingProvider(); };



    document.querySelectorAll('.btn-onboard-preset').forEach(btn => {

      btn.onclick = (e) => {

        e.preventDefault();

        e.stopPropagation();

        const k = btn.getAttribute('data-preset');

        if (k) window.setOnboardPreset(k);

      };

    });



    // Fallback dual-layer bindings for Interactive Tour

    const btnTourClose = document.getElementById('btn-tour-close');

    if (btnTourClose) btnTourClose.onclick = (e) => { e.preventDefault(); e.stopPropagation(); window.skipTour(); };

    const btnTourSkip = document.getElementById('btn-tour-skip');

    if (btnTourSkip) btnTourSkip.onclick = (e) => { e.preventDefault(); e.stopPropagation(); window.skipTour(); };

    const btnTourPrev = document.getElementById('btn-tour-prev');

    if (btnTourPrev) btnTourPrev.onclick = (e) => { e.preventDefault(); e.stopPropagation(); window.prevTourStep(); };

    const btnTourNext = document.getElementById('btn-tour-next');

    if (btnTourNext) btnTourNext.onclick = (e) => { e.preventDefault(); e.stopPropagation(); window.nextTourStep(); };



    // Fallback dual-layer bindings for Rename Modal

    const btnRenameClose = document.getElementById('btn-rename-close');

    if (btnRenameClose) btnRenameClose.onclick = (e) => { e.preventDefault(); e.stopPropagation(); window.closeRenameModal(); };

    const btnRenameCancel = document.getElementById('btn-rename-cancel');

    if (btnRenameCancel) btnRenameCancel.onclick = (e) => { e.preventDefault(); e.stopPropagation(); window.closeRenameModal(); };

    const btnRenameSave = document.getElementById('btn-rename-save');

    if (btnRenameSave) btnRenameSave.onclick = (e) => { e.preventDefault(); e.stopPropagation(); window.submitRenameModal(); };



    const btnMcpRemote = document.getElementById('btn-mcp-tab-remote');

    if (btnMcpRemote) btnMcpRemote.onclick = (e) => { if (e) { e.preventDefault(); e.stopPropagation(); } window.switchMCPModalType('remote'); };

    const btnMcpLocal = document.getElementById('btn-mcp-tab-local');

    if (btnMcpLocal) btnMcpLocal.onclick = (e) => { if (e) { e.preventDefault(); e.stopPropagation(); } window.switchMCPModalType('local'); };







    const toggleSettingsBtn = document.getElementById('btn-toggle-settings');



    if (toggleSettingsBtn) toggleSettingsBtn.onclick = () => {



      state.activeModal = 'settings';



      render();



      if (state.settingsTab === 'logs') window.fetchLogs();



    };







    const togglePanelBtn = document.getElementById('btn-toggle-activity-panel');



    if (togglePanelBtn) togglePanelBtn.onclick = () => {



      state.rightPanelOpen = !state.rightPanelOpen;



      render();



    };







    const searchInput = document.getElementById('sidebar-search-input');



    if (searchInput) {



      searchInput.oninput = (e) => {



        state.searchQuery = e.target.value;



        render();



        // Restore focus



        const inp = document.getElementById('sidebar-search-input');



        if (inp) inp.focus();



      };



    }







        const modelSelect = document.getElementById('header-model-select');



    if (modelSelect) {



      modelSelect.onchange = async (e) => {



        const selectedModel = e.target.value;

        if (!selectedModel) return;



        const foundMdl = state.models.find(m => m.model_name === selectedModel);

        const newSupportsVision = foundMdl ? Boolean(foundMdl.supports_vision) : false;



        // Guard: Prevent switching to a text-only model while editing a message that contains images

        if (state.editingMessageId) {

          const editMsg = state.messages.find(m => m.id === state.editingMessageId);

          if (editMsg) {

            const { attachments } = parseMessageAttachments(editMsg.content, editMsg.id);

            const hasImages = (attachments || []).some(a => a.type === 'image');

            if (hasImages && !newSupportsVision) {

              showToast('Cannot switch to a text-only model while editing a message containing images. Please select a vision model.', 'warning');

              const prevModel = state.selectedDefaultModel || '';

              modelSelect.value = prevModel;

              return;

            }

          }

        }



        // Guard: If switching to a text-only model and composer currently has attached images, purge images safely

        if (!newSupportsVision && state.attachedFiles && state.attachedFiles.length > 0) {

          const hadImages = state.attachedFiles.some(f => f.type === 'image' || (f.mime && f.mime.startsWith('image/')));

          if (hadImages) {

            state.attachedFiles = state.attachedFiles.filter(f => f.type !== 'image' && (!f.mime || !f.mime.startsWith('image/')));

            showToast('Switched to text-only model. Image attachments were removed.', 'warning');

          }

        }



        const patchPayload = { model_id: selectedModel };



        if (foundMdl && foundMdl.provider_id) {



          patchPayload.provider_id = foundMdl.provider_id;



        }



        state.selectedDefaultModel = selectedModel;

        saveLastSelectedModel(selectedModel, patchPayload.provider_id);



        if (state.activeConvId) {



          const c = state.conversations.find(conv => conv.id === state.activeConvId);



          if (c) {



            c.model_id = selectedModel;



            if (patchPayload.provider_id) c.provider_id = patchPayload.provider_id;



          }



          render();



          const modelNameDisp = foundMdl ? (foundMdl.display_name || foundMdl.model_name) : selectedModel;



          showToast('Model switched to ' + modelNameDisp, 'info');



          apiCall(`/conversations/${state.activeConvId}`, {



            method: 'PATCH',



            body: JSON.stringify(patchPayload)



          }).catch(console.error);



        } else {



          render();



        }



      };



    }







    const permModeSelect = document.getElementById('header-perm-mode');



    if (permModeSelect) {



      permModeSelect.onchange = async (e) => {



        if (!state.activeConvId) return;



        await apiCall(`/conversations/${state.activeConvId}`, {



          method: 'PATCH',



          body: JSON.stringify({ permission_mode: e.target.value })



        });



        const c = state.conversations.find(conv => conv.id === state.activeConvId);



        if (c) c.permission_mode = e.target.value;



      };



    }







    const composerInput = document.getElementById('composer-input');



    const sendBtn = document.getElementById('btn-send-msg');



    const stopBtn = document.getElementById('btn-stop-gen');







        if (composerInput) {

      const autoResizeComposer = (el) => {

        if (!el) return;

        el.style.height = 'auto';

        const minH = 46;

        const maxH = 268; // 10 to 12 lines (~22px line height * 12)

        const scrollH = el.scrollHeight;

        if (scrollH <= minH) {

          el.style.height = minH + 'px';

          el.style.overflowY = 'hidden';

        } else if (scrollH >= maxH) {

          el.style.height = maxH + 'px';

          el.style.overflowY = 'auto';

        } else {

          el.style.height = scrollH + 'px';

          el.style.overflowY = 'hidden';

        }

      };



      autoResizeComposer(composerInput);

    composerInput.onpaste = (e) => {

        const cb = e.clipboardData || window.clipboardData;

        if (!cb) return;



        // 1. Check if files were pasted directly (e.g. copied from Windows Explorer or desktop)

        const files = Array.from(cb.files || []);

        if (files.length > 0) {

          e.preventDefault();

          handleAttachedFileList(files);

          return;

        }



        // 2. Check clipboard items for any files (e.g. screenshot images from clipboard buffer)

        const items = Array.from(cb.items || []);

        const fileItems = items.filter(it => it.kind === 'file').map(it => it.getAsFile()).filter(Boolean);

        if (fileItems.length > 0) {

          e.preventDefault();

          handleAttachedFileList(fileItems);

          return;

        }



        // 3. Check for large pasted text snippet (> 800 chars or > 15 lines)

        const text = cb.getData('text');

        if (text && (text.length > 800 || text.split('\n').length > 15)) {

          e.preventDefault();

          if (!state.attachedFiles) state.attachedFiles = [];

          state.attachedFiles.push({

            name: `Pasted_Text_${Date.now().toString().slice(-4)}.txt`,

            type: 'paste',

            mime: 'text/plain',

            content: text,

            size: new Blob([text]).size,

            isSnippet: true

          });

          render();

          const inp = document.getElementById('composer-input');

          if (inp) inp.focus();

          return;

        }

      };



      // Global window paste and drag-drop handlers for copied files

      if (!window.__novaPasteHandlerBound) {

        window.__novaPasteHandlerBound = true;

        window.addEventListener('paste', (e) => {

          const activeEl = document.activeElement;

          if (activeEl && activeEl.id === 'composer-input') return;

          const isOtherInput = activeEl && (activeEl.tagName === 'INPUT' || activeEl.tagName === 'TEXTAREA');

          const cb = e.clipboardData || window.clipboardData;

          if (!cb) return;

          const files = Array.from(cb.files || []);

          const items = Array.from(cb.items || []);

          const fileItems = items.filter(it => it.kind === 'file').map(it => it.getAsFile()).filter(Boolean);

          const allFiles = files.length > 0 ? files : fileItems;

          if (allFiles.length > 0) {

            if (!isOtherInput) {

              e.preventDefault();

              handleAttachedFileList(allFiles);

            }

          }

        });



        window.addEventListener('dragover', (e) => {

          if (e.dataTransfer && e.dataTransfer.types && Array.from(e.dataTransfer.types).includes('Files')) {

            e.preventDefault();

          }

        });

        window.addEventListener('drop', (e) => {

          if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {

            e.preventDefault();

            handleAttachedFileList(e.dataTransfer.files);

          }

        });

      }



      composerInput.onkeydown = (e) => {



        if (state.slashMenuOpen) {



          if (e.key === 'ArrowDown') {



            e.preventDefault();



            const currentSkillsList = (state.skills && state.skills.length > 0) ? state.skills : slashSkills;

            state.slashSelectedIndex = (state.slashSelectedIndex + 1) % currentSkillsList.length;



            render();



            return;



          }



          if (e.key === 'ArrowUp') {



            e.preventDefault();



            const currentSkillsList = (state.skills && state.skills.length > 0) ? state.skills : slashSkills;

            state.slashSelectedIndex = (state.slashSelectedIndex - 1 + currentSkillsList.length) % currentSkillsList.length;



            render();



            return;



          }



          if (e.key === 'Enter' || e.key === 'Tab') {



            e.preventDefault();



            const currentSkillsList = (state.skills && state.skills.length > 0) ? state.skills : slashSkills;

            const chosen = currentSkillsList[state.slashSelectedIndex];



            if (chosen) window.selectSlashSkill(chosen.id);



            return;



          }



          if (e.key === 'Escape') {



            e.preventDefault();



            state.slashMenuOpen = false;



            render();



            return;



          }



        }



        if (e.key === 'Enter' && !e.shiftKey) {



          e.preventDefault();



          submitComposer();



        }



      };







      composerInput.oninput = (e) => {



        const val = e.target.value;



        state.composerText = val;

        autoResizeComposer(e.target);



        if (val.startsWith('/') && !val.includes(' ') && !state.slashMenuOpen) {



          state.slashMenuOpen = true;



          render();



          const inp = document.getElementById('composer-input');



          if (inp) {



            inp.value = val;



            inp.focus();



            inp.selectionStart = inp.selectionEnd = val.length;



          }



        } else if (state.slashMenuOpen && (val.includes(' ') || !val.includes('/'))) {



          state.slashMenuOpen = false;



          render();



          const inp = document.getElementById('composer-input');



          if (inp) {



            inp.value = val;



            inp.focus();



            inp.selectionStart = inp.selectionEnd = val.length;



          }



        }



      };



    }







    if (sendBtn) {



      sendBtn.onclick = () => {



        submitComposer();



      };



    }







    if (stopBtn) {



      stopBtn.onclick = () => {



        stopGeneration();



      };



    }







    const fileInput = document.getElementById('file-upload-input');

    if (fileInput) {

      fileInput.onchange = (e) => {

        if (e.target.files && e.target.files.length > 0) {

          handleAttachedFileList(e.target.files);

          fileInput.value = '';

        }

      };

    }



    // Add drag-and-drop listener to composer

    const composerBox = composerInput ? composerInput.closest('.relative') : null;

    if (composerBox) {

      composerBox.ondragover = (e) => {

        e.preventDefault();

        composerBox.classList.add('ring-2', 'ring-emerald-500/50');

      };

      composerBox.ondragleave = (e) => {

        composerBox.classList.remove('ring-2', 'ring-emerald-500/50');

      };

      composerBox.ondrop = (e) => {

        e.preventDefault();

        composerBox.classList.remove('ring-2', 'ring-emerald-500/50');

        const files = Array.from(e.dataTransfer.files || []);

        if (files.length === 0) return;

        handleAttachedFileList(files);

      };

    }



  }







  // Global Window Bindings for Inline Clicks



  



  function submitComposer() {

    try {

      const composerInput = document.getElementById('composer-input');

      const userText = composerInput ? composerInput.value.trim() : '';



      if (!userText && (!state.attachedFiles || state.attachedFiles.length === 0)) {

        return;

      }



      const activeMdl = getActiveModel();

      const modelSupportsVision = activeMdl ? Boolean(activeMdl.supports_vision) : false;

      const hasImage = (state.attachedFiles || []).some(f => f.type === 'image' || (f.mime && f.mime.startsWith('image/')));

      if (hasImage && !modelSupportsVision) {

        const mName = activeMdl ? (formatModelDisplayName(activeMdl.display_name || activeMdl.model_name)) : 'Selected model';

        showToast(`Cannot send image: model '${mName}' is a text-only model. Remove image or switch to a vision model.`, 'error');

        return;

      }



      let fullPrompt = '';

      if (state.attachedFiles && state.attachedFiles.length > 0) {

        const fileTags = state.attachedFiles.map(f => {

          const mime = f.mime || (f.type === 'image' ? 'image/png' : 'text/plain');

          const type = f.type || (f.isSnippet ? 'paste' : 'text');

          return `<attachment type="${type}" name="${escapeAttr(f.name)}" mime="${mime}" size="${f.size}">${f.content}</attachment>`;

        }).join('\n\n');



        if (userText) {

          fullPrompt = fileTags + '\n\n' + userText;

        } else {

          fullPrompt = fileTags;

        }

      } else {

        fullPrompt = userText;

      }



      state.attachedFiles = [];

      state.composerText = '';

      if (composerInput) {

        composerInput.value = '';

        composerInput.style.height = '46px';

        composerInput.style.overflowY = 'hidden';

      }

      sendMessage(fullPrompt);

    } catch (err) {

      console.error('Error submitting composer:', err);

    }

  }







  function formatBytes(bytes) {



    if (!bytes || bytes === 0) return '0 B';



    const k = 1024;



    const sizes = ['B', 'KB', 'MB'];



    const i = Math.floor(Math.log(bytes) / Math.log(k));



    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];



  }







  window.convertSnippetToText = (idx) => {



    if (!state.attachedFiles[idx]) return;



    const snippet = state.attachedFiles[idx];



    state.attachedFiles.splice(idx, 1);



    render();



    const inp = document.getElementById('composer-input');



    if (inp) {



      inp.value = snippet.content + (inp.value ? '\n' + inp.value : '');



      inp.focus();



    }



  };







  window.removeAttachment = (idx) => {



    state.attachedFiles.splice(idx, 1);



    render();



    const inp = document.getElementById('composer-input');



    if (inp) inp.focus();



  };



  window.openAttachmentViewer = (attId) => {

    const att = state.attachmentCache && state.attachmentCache[attId];

    if (!att) return;

    state.activeAttachmentViewer = att;

    render();

  };



  window.closeAttachmentViewer = () => {

    state.activeAttachmentViewer = null;

    render();

  };



  window.copyAttachmentContent = () => {

    if (!state.activeAttachmentViewer) return;

    navigator.clipboard.writeText(state.activeAttachmentViewer.content || '');

    const btn = document.getElementById('btn-copy-attachment-content');

    if (btn) {

      btn.innerHTML = `${icons.check} <span>Copied!</span>`;

      btn.classList.add('text-emerald-400');

      setTimeout(() => {

        if (btn) {

          btn.innerHTML = `${icons.copy} <span>Copy</span>`;

          btn.classList.remove('text-emerald-400');

        }

      }, 2000);

    }

    showToast('Attachment content copied', 'info');

  };



  window.openImageLightbox = (attId) => {

    const att = state.attachmentCache && state.attachmentCache[attId];

    if (!att) return;

    state.activeImageLightbox = att;

    render();

  };



  window.closeImageLightbox = () => {

    state.activeImageLightbox = null;

    render();

  };







  window.syncAllProviders = async () => {



    for (const p of state.providers) {



      try {



        await apiCall('/providers/' + p.id + '/sync-models', { method: 'POST' });



      } catch (e) {}



    }



    const mdls = await apiCall('/models');



    state.models = mdls;



    render();



    showToast('Model catalogs synchronized!', 'success');



  };







  



  window.toggleSearch = () => {



    state.showSearch = !state.showSearch;



    render();



    if (state.showSearch) {



      const inp = document.getElementById('sidebar-search-input');



      if (inp) inp.focus();



    }



  };







  window.toggleSidebar = () => {



    state.sidebarOpen = !state.sidebarOpen;



    render();



  };







  window.toggleToolDetail = (stepId) => {

    const chatContainer = document.getElementById('chat-messages-container');

    const prevScrollTop = chatContainer ? chatContainer.scrollTop : null;

    state.expandedToolDetails[stepId] = !state.expandedToolDetails[stepId];

    render();

    const newChat = document.getElementById('chat-messages-container');

    if (newChat && prevScrollTop !== null) {

      newChat.scrollTop = prevScrollTop;

    }

  };







  window.toggleThought = (msgId) => {

    const chatContainer = document.getElementById('chat-messages-container');

    const prevScrollTop = chatContainer ? chatContainer.scrollTop : null;

    state.expandedThoughts[msgId] = !state.expandedThoughts[msgId];

    render();

    const newChat = document.getElementById('chat-messages-container');

    if (newChat && prevScrollTop !== null) {

      newChat.scrollTop = prevScrollTop;

    }

  };







  window.copyMsgContent = (msgId) => {



    const msg = state.messages.find(m => m.id === msgId);



    if (msg && msg.content) {



      const { cleanText, attachments } = parseMessageAttachments(msg.content, msg.id);

      let toCopy = cleanText;

      if (!toCopy && attachments.length > 0) {

        toCopy = attachments.map(a => `[${a.name}]\n${a.content}`).join('\n\n');

      }



      navigator.clipboard.writeText(toCopy || msg.content).then(() => showToast('Copied to clipboard!', 'info'));



    }



  };



  window.copyToClipboard = (text) => {



    navigator.clipboard.writeText(text).then(() => showToast('Copied to clipboard!', 'info'));



  };







  window.quickPrompt = (text) => {



    sendMessage(text);



  };







  window.openAutomations = () => {



    state.activeModal = 'settings';



    state.settingsTab = 'terminal';



    render();



  };







  window.openSettingsTab = (tab) => {



    state.activeModal = 'settings';



    state.settingsTab = tab;



    render();



  };







    window.openConvContextMenu = (convId, e) => {

    if (e) {

      e.stopPropagation();

      e.preventDefault();

    }

    const clientX = e && typeof e.clientX === 'number' ? e.clientX : 180;

    const clientY = e && typeof e.clientY === 'number' ? e.clientY : 100;

    state.activeDropdown = {

      type: 'conv',

      convId: convId,

      x: Math.max(16, Math.min(clientX, window.innerWidth - 240)),

      y: Math.max(16, Math.min(clientY, window.innerHeight - 280))

    };

    render();

  };



  window.openConvMenu = (convId, e) => {



    if (e) {



      e.stopPropagation();



      e.preventDefault();



    }



    const rect = e && e.currentTarget ? e.currentTarget.getBoundingClientRect() : { right: window.innerWidth - 220, bottom: 100 };



    state.activeDropdown = {



      type: 'conv',



      convId: convId,



      x: Math.max(16, Math.min(rect.right - 180, window.innerWidth - 220)),



      y: (rect.bottom || 100) + 6



    };



    render();



  };







  window.toggleSlashMenu = (e) => {



    if (e) e.stopPropagation();



    state.slashMenuOpen = !state.slashMenuOpen;



    render();



    if (state.slashMenuOpen) {



      const inp = document.getElementById('composer-input');



      if (inp) inp.focus();



    }



  };







  window.selectSlashSkill = (skillId) => {

    const currentSkillsList = (state.skills && state.skills.length > 0) ? state.skills : slashSkills;

    const skillObj = currentSkillsList.find(s => s.id === skillId || s.command === skillId || s.command === '/' + skillId);

    state.activeSkill = skillObj ? skillObj.id : skillId;

    state.slashMenuOpen = false;

    const cmd = skillObj ? skillObj.command : ('/' + skillId);

    state.composerText = cmd + ' ';

    const inp = document.getElementById('composer-input');

    if (inp) {

      inp.value = cmd + ' ';

      inp.style.height = 'auto';

      inp.style.height = Math.min(Math.max(inp.scrollHeight, 46), 268) + 'px';

      inp.focus();

    }

    render();

  };







  window.submitRenameModal = async () => {



    const inp = document.getElementById('rename-modal-input');



    const newTitle = inp ? inp.value.trim() : '';



    const convId = state.renameModalConvId;



    if (newTitle && convId) {



      const c = state.conversations.find(x => x.id === convId);



      if (c) c.title = newTitle;



      await apiCall('/conversations/' + convId, {



        method: 'PATCH',



        body: JSON.stringify({ title: newTitle })



      }).catch(console.error);



      showToast('Session renamed successfully', 'success');



    }



    state.renameModalConvId = null;



    render();



  };







  window.exportConversationMarkdown = (convId) => {



    state.activeDropdown = null;



    const c = state.conversations.find(x => x.id === convId);



    const title = c ? c.title : 'Conversation';



    let md = `# ${title}\n\n*Exported from NOVA AI Workstation*\n\n---\n\n`;



    state.messages.forEach(m => {



      md += `### ${m.role === 'user' ? 'User' : 'NOVA Assistant'}\n\n${m.content || ''}\n\n---\n\n`;



    });



    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });



    const url = URL.createObjectURL(blob);



    const a = document.createElement('a');



    a.href = url;



    a.download = `${title.replace(/[/\\:*?"<>|]/g, '_')}.md`;



    a.click();



    URL.revokeObjectURL(url);



    showToast('Markdown exported successfully', 'success');



    render();



  };







  window.copyConversationId = (convId) => {



    state.activeDropdown = null;



    navigator.clipboard.writeText(convId).then(() => {



      showToast('Session ID copied to clipboard', 'info');



    }).catch(() => {});



    render();



  };







  window.addMemoryFactPrompt = () => {



    state.addMemoryModalOpen = true;



    render();



    setTimeout(() => {



      const inp = document.getElementById('add-memory-input');



      if (inp) inp.focus();



    }, 50);



  };







  window.closeAddMemoryModal = (e) => {



    if (e) e.stopPropagation();



    state.addMemoryModalOpen = false;



    render();



  };







  window.setAddMemoryCategory = (cat) => {

    const inp = document.getElementById('add-memory-input');

    const draft = inp ? inp.value : '';

    state.addMemoryCategory = cat;

    render();

    setTimeout(() => {

      const el = document.getElementById('add-memory-input');

      if (el && draft && !el.value) el.value = draft;

    }, 0);

  };



  window.setAddMemoryScope = (scope) => {

    const inp = document.getElementById('add-memory-input');

    const draft = inp ? inp.value : '';

    state.addMemoryScope = scope;

    render();

    setTimeout(() => {

      const el = document.getElementById('add-memory-input');

      if (el && draft && !el.value) el.value = draft;

    }, 0);

  };



  window.setMemoryFilter = (val) => {

    state.memoryFilter = val || '';

    render();

  };



  window.submitAddMemoryModal = async () => {

    const inp = document.getElementById('add-memory-input');

    const fact = inp ? inp.value.trim() : '';

    if (!fact) {

      showToast('Please enter a fact or instruction to save.', 'warning');

      return;

    }

    try {

      await apiCall('/memory/facts', {

        method: 'POST',

        body: JSON.stringify({

          content: fact,

          category: state.addMemoryCategory || 'user_preference',

          conversation_id: (state.addMemoryScope === 'session' && state.activeConvId) ? state.activeConvId : null

        })

      });

      showToast('Fact saved to persistent memory', 'success');

      state.addMemoryModalOpen = false;

      await window.fetchMemory();

    } catch (err) {

      showToast('Failed to save memory fact: ' + (err.message || err), 'error');

    }

  };







  window.voicePromptPlaceholder = () => {



    showToast('Voice recognition microphone ready. Speak your prompt or type in the box.', 'info');



  };







  window.createNewConversation = createNewConversation;

  window.toggleWorkedGroup = (groupId) => {

    const current = state.expandedWorkedSections[groupId];

    state.expandedWorkedSections[groupId] = current !== undefined ? !current : true;

    render();

  };

  window.openFileDrawer = async (filePath) => {

    if (!filePath) return;

    const cleanPath = String(filePath).replace(/\\/g, '/').trim();

    state.rightPanelOpen = true;

    state.rightPanelTab = 'file_viewer';

    state.viewingFilePath = cleanPath;

    state.viewingFileContent = null;

    state.viewingFileLoading = true;

    state.viewingFileError = null;

    state.viewingFileSize = null;

    state.viewingFileName = cleanPath.split('/').pop() || 'file';

    render();



    try {

      const res = await apiCall(`/workspaces/file-content?path=${encodeURIComponent(cleanPath)}`);

      state.viewingFileContent = res.content || '';

      state.viewingFileSize = res.size;

      state.viewingFileName = res.filename;

      state.viewingFilePath = res.path;

    } catch (err) {

      state.viewingFileError = err.message || 'Failed to read file.';

    } finally {

      state.viewingFileLoading = false;

      render();

    }

  };

  window.closeFileDrawer = () => {

    state.rightPanelTab = 'plan';

    render();

  };

  window.state = state;

  window.render = render;

  window.selectConversation = selectConversation;

  window.selectConv = selectConversation;



  window.deleteConv = deleteConversation;



  window.togglePin = togglePin;



  window.decideApp = handleApproval;

  window.handleApproval = handleApproval;



  window.stopGeneration = stopGeneration;



  window.retryTurn = retryTurn;







  window.startEditMessage = (msgId) => {



    const msg = state.messages.find(m => m.id === msgId);



    if (!msg) return;



    const { cleanText, attachments } = parseMessageAttachments(msg.content, msg.id);

    const hasImages = (attachments || []).some(a => a.type === 'image');

    const activeMdl = getActiveModel();

    const modelSupportsVision = activeMdl ? Boolean(activeMdl.supports_vision) : false;



    if (hasImages && !modelSupportsVision) {

      const mName = activeMdl ? formatModelDisplayName(activeMdl.display_name || activeMdl.model_name) : 'current';

      showToast(`This message contains images. You cannot edit or resend it with text-only model '${mName}'. Please switch to a vision model first.`, 'warning');

      return;

    }



    state.editingMessageId = msgId;



    state.editingMessageText = cleanText || '';



    render();



    const textarea = document.getElementById(`msg-edit-textarea-${msgId}`);



    if (textarea) {



      textarea.focus();



      textarea.selectionStart = textarea.selectionEnd = textarea.value.length;



      textarea.onkeydown = (e) => {



        if (e.key === 'Enter' && !e.shiftKey) {



          e.preventDefault();



          window.saveEditedMessage(msgId, true);



        } else if (e.key === 'Escape') {



          window.cancelEditMessage();



        }



      };



    }



  };







  window.cancelEditMessage = () => {



    state.editingMessageId = null;



    state.editingMessageText = '';



    render();



  };







  window.saveEditedMessage = async (msgId, resend) => {



    const textarea = document.getElementById(`msg-edit-textarea-${msgId}`);



    let newContent = textarea ? textarea.value.trim() : (state.editingMessageText || '').trim();



    if (!newContent && !state.activeConvId) return;



    const oldMsg = state.messages.find(m => m.id === msgId);

    if (oldMsg) {

      const { attachments } = parseMessageAttachments(oldMsg.content, oldMsg.id);

      if (attachments && attachments.length > 0) {

        const fileTags = attachments.map(f => {

          return `<attachment type="${f.type}" name="${escapeAttr(f.name)}" mime="${f.mime}" size="${f.size}">${f.content}</attachment>`;

        }).join('\n\n');

        newContent = fileTags + (newContent ? '\n\n' + newContent : '');

      }

    }







    state.editingMessageId = null;



    state.editingMessageText = '';







    if (resend) {

      const targetOldMsg = state.messages.find(m => m.id === msgId);

      if (targetOldMsg) {

        const { attachments: oldAtts } = parseMessageAttachments(targetOldMsg.content, targetOldMsg.id);

        const hasImages = (oldAtts || []).some(a => a.type === 'image');

        const activeMdl = getActiveModel();

        const modelSupportsVision = activeMdl ? Boolean(activeMdl.supports_vision) : false;

        if (hasImages && !modelSupportsVision) {

          showToast('Cannot resend message with images to a text-only model. Please switch to a vision model first.', 'error');

          return;

        }

      }



      state.isStreaming = true;



      state.streamingContent = '';



      state.streamingThought = '';



    }



    render();







    try {



      await apiCall(`/conversations/${state.activeConvId}/messages/${msgId}`, {



        method: 'PATCH',



        body: JSON.stringify({

          content: newContent,

          resend: !!resend,

          enable_thinking: state.enableThinking !== undefined ? state.enableThinking : true,

          enable_search: state.enableWebSearch !== undefined ? state.enableWebSearch : true

        })



      });



      await refreshMessages();



    } catch (err) {



      showToast('Failed to update message: ' + err.message, 'error');



      state.isStreaming = false;



      render();



    }



  };







  window.copyText = (text, btnEl) => {



    navigator.clipboard.writeText(text);



    if (btnEl) {



      const orig = btnEl.innerHTML;



      btnEl.innerHTML = `${icons.check} <span>Copied!</span>`;



      setTimeout(() => { btnEl.innerHTML = orig; }, 1800);



    }



  };



  window.closeModal = (e) => {



    state.activeModal = null;



    render();



  };



  // Modal and Navigation Window Methods

  window.closeDropdownMenu = () => {

    state.activeDropdown = null;

    render();

  };



  window.startRenameConversation = (convId) => {

    state.activeDropdown = null;

    state.renameModalConvId = convId;

    const c = state.conversations.find(x => x.id === convId);

    state.renameModalValue = c ? (c.title || '') : '';

    render();

    setTimeout(() => {

      const inp = document.getElementById('rename-modal-input');

      if (inp) {

        inp.focus();

        inp.select();

      }

    }, 50);

  };



  window.closeRenameModal = (e) => {

    if (e && e.target && e.currentTarget && e.target !== e.currentTarget && e.target.closest && e.target.closest('#rename-modal-content')) return;

    state.renameModalConvId = null;

    render();

  };



  window.openProviderModal = () => {

    state.activeModal = 'provider';

    render();

  };



  window.deleteProvider = async (id, btnEl) => {

    showConfirmModal(

      'Delete AI Provider',

      'Are you sure you want to delete this AI provider and all its configured models? This action cannot be undone.',

      async () => {

        try {

          if (btnEl) {

            btnEl.disabled = true;

            btnEl.textContent = 'Deleting...';

          }

          await apiCall(`/providers/${id}`, { method: 'DELETE' });

          await fetchProviders();

          render();

          showToast('Provider deleted successfully.', 'info');

        } catch (e) {

          showToast('Failed to delete provider: ' + (e.message || e), 'error');

        }

      },

      'Delete Provider',

      'bg-rose-600 hover:bg-rose-500 text-white'

    );

  };



  window.openAddMemoryModal = () => {

    if (typeof window.addMemoryFactPrompt === 'function') {

      window.addMemoryFactPrompt();

    } else {

      state.addMemoryModalOpen = true;

      render();

    }

  };



  async function fetchSkills() {

    try {

      const skillsData = await apiCall('/skills').catch(() => ({ skills: [] }));

      state.skills = (skillsData && skillsData.skills) || (Array.isArray(skillsData) ? skillsData : []);

    } catch (e) {

      state.skills = state.skills || [];

    }

  }



  window.rescanSkillsFolder = async () => {

    try {

      const res = await apiCall('/skills/scan', { method: 'POST' });

      if (res && Array.isArray(res.skills)) {

        state.skills = res.skills;

      } else {

        await fetchSkills();

      }

      render();

      showToast((res && res.message) || `Scanned skills folder: ${state.skills.length} skills loaded`, 'success');

    } catch (e) {

      showToast('Failed to scan skills folder: ' + (e.message || e), 'error');

    }

  };



  window.setOnboardPreset = (key) => {

    state.onboardingPreset = key;

    render();

  };



  window.skipOnboardingProvider = () => {

    localStorage.setItem('nova_provider_setup_dismissed', 'true');

    localStorage.setItem('nova_onboarding_dismissed', 'true');

    state.activeModal = null;

    const tourDone = localStorage.getItem('nova_tour_completed');

    if (!tourDone) {

      state.activeTourStep = 0;

    }

    render();

  };



  window.saveOnboardingProvider = async () => {

    const curPresetKey = state.onboardingPreset || 'openai';

    const curPreset = ONBOARDING_PRESETS[curPresetKey] || ONBOARDING_PRESETS.openai;

    const nameEl = document.getElementById('onboard-name');

    const urlEl = document.getElementById('onboard-url');

    const keyEl = document.getElementById('onboard-key');



    const name = nameEl ? nameEl.value.trim() : (curPreset.name || 'AI Provider');

    const url = urlEl ? urlEl.value.trim() : (curPreset.url || '');

    const key = keyEl ? keyEl.value.trim() : '';



    const saveBtn = document.getElementById('btn-onboard-save');



    if (!name || !url) {

      showToast('Provider name and API base URL are required', 'error');

      return;

    }



    if (curPreset.keyRequired && !key) {

      showToast(`API Key is required for ${name}. If you wish to proceed without configuring an API key now, click "Skip for Now".`, 'error');

      return;

    }



    try {

      if (saveBtn) {

        saveBtn.disabled = true;

        saveBtn.innerHTML = `

          <svg class="animate-spin h-3.5 w-3.5 text-zinc-950 inline mr-1" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">

            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>

            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>

          </svg>

          Connecting & Discovering Models...

        `;

      }



      const created = await apiCall('/providers', {

        method: 'POST',

        body: JSON.stringify({

          name,

          provider_type: detectProviderType(url, name, key),

          base_url: url,

          api_key: key || null

        })

      });



      // Autonomously discover models from provider

      let syncResult = null;

      if (created && created.id) {

        try {

          syncResult = await apiCall(`/providers/${created.id}/sync-models`, { method: 'POST' });

        } catch (_) {

          if (curPreset && curPreset.model) {

            try {

              await apiCall(`/providers/${created.id}/models`, {

                method: 'POST',

                body: JSON.stringify({

                  id: curPreset.model,

                  name: curPreset.model,

                  context_length: 128000

                })

              });

            } catch (__) {}

          }

        }

      }



      localStorage.setItem('nova_provider_setup_dismissed', 'true');

      localStorage.setItem('nova_onboarding_dismissed', 'true');

      state.activeModal = null;



      await fetchProviders();



      if (state.models.length > 0) {

        state.selectedModelId = state.models[0].model_name;

        state.selectedDefaultModel = state.models[0].model_name;

        document.cookie = `nova_last_model_id=${encodeURIComponent(state.models[0].model_name)}; path=/; max-age=31536000; SameSite=Lax`;

      }



      const tourDone = localStorage.getItem('nova_tour_completed');

      if (!tourDone) {

        state.activeTourStep = 0;

      }

      render();



      if (syncResult && syncResult.status === 'success' && syncResult.count > 0) {

        showToast(`Connected ${name}! Discovered ${syncResult.count} models.`, 'success');

      } else if (syncResult && syncResult.message) {

        showToast(syncResult.message, 'info');

      } else {

        showToast('AI Provider connected successfully!', 'success');

      }

    } catch (e) {

      showToast('Failed to save provider: ' + (e.message || e), 'error');

    } finally {

      if (saveBtn) {

        saveBtn.disabled = false;

        saveBtn.innerHTML = `<span>Save & Continue</span><span>→</span>`;

      }

    }

  };



  window.startTour = () => {

    state.activeModal = null;

    state.activeTourStep = 0;

    render();

  };



  window.nextTourStep = () => {

    if (state.activeTourStep === null || state.activeTourStep === undefined) return;

    if (state.activeTourStep < TOUR_STEPS.length - 1) {

      state.activeTourStep++;

    } else {

      state.activeTourStep = null;

      localStorage.setItem('nova_tour_completed', 'true');

      const provDismissed = localStorage.getItem('nova_provider_setup_dismissed');

      if (state.providers.length === 0 && !provDismissed) {

        state.activeModal = 'onboarding_provider';

      } else {

        showToast('Tour completed! You are ready to build.', 'success');

      }

    }

    render();

  };



  window.prevTourStep = () => {

    if (state.activeTourStep === null || state.activeTourStep === undefined) return;

    if (state.activeTourStep > 0) {

      state.activeTourStep--;

    }

    render();

  };



  window.skipTour = () => {

    state.activeTourStep = null;

    localStorage.setItem('nova_tour_completed', 'true');

    const provDismissed = localStorage.getItem('nova_provider_setup_dismissed');

    if (state.providers.length === 0 && !provDismissed) {

      state.activeModal = 'onboarding_provider';

    }

    render();

  };





  window.switchTab = (tab) => {



    state.rightPanelTab = tab;



    render();



    if (tab === 'workspace') window.refreshFiles();



    if (tab === 'memory') window.fetchMemory();



  };



  window.switchSettingsTab = (tab) => {



    state.settingsTab = tab;



    render();



    if (tab === 'logs') window.fetchLogs();



  };



  window.sendPredefined = (prompt) => {



    sendMessage(prompt);



  };



  window.openAddProvider = () => {



    state.activeModal = 'provider';



    render();



  };



  window.testProv = async (id) => {



    try {



      const res = await apiCall(`/providers/${id}/test`, { method: 'POST' });



      showToast(res.message, 'error');



    } catch (e) {



      showToast('Test failed: ' + e.message, 'error');



    }



  };



  window.deleteProviderModel = async (modelId) => {

    if (!modelId) return;

    try {

      await apiCall(`/models/${encodeURIComponent(modelId)}`, { method: 'DELETE' });

      await fetchProviders();

      render();

      showToast('Model removed.', 'info');

    } catch (e) {

      showToast('Failed to remove model: ' + (e.message || e), 'error');

    }

  };



  window.syncAllProviders = async (btnEl) => {

    try {

      if (btnEl) {

        btnEl.disabled = true;

        btnEl.innerHTML = `<span class="inline-block animate-spin mr-1">↻</span> Syncing all...`;

      }

      showToast('Syncing all providers...', 'info');

      const res = await apiCall('/providers/sync-all', { method: 'POST' });

      await fetchProviders();

      render();

      showToast(res.message || 'All providers synced successfully.', 'success');

    } catch (err) {

      showToast('Failed to sync all providers: ' + (err.message || err), 'error');

    } finally {

      if (btnEl) {

        btnEl.disabled = false;

        btnEl.innerHTML = `${icons.refresh} <span>Sync All Models</span>`;

      }

    }

  };



  window.syncProv = async (id, btnEl) => {

    try {

      if (btnEl) {

        btnEl.disabled = true;

        btnEl.innerHTML = `<span class="inline-block animate-spin mr-1">↻</span> Syncing...`;

      }

      showToast('Connecting & discovering models...', 'info');

      const res = await apiCall(`/providers/${id}/sync-models`, { method: 'POST' });

      await fetchProviders();

      render();

      if (res && res.status === 'success' && res.count > 0) {

        showToast(res.message || `Discovered ${res.count} models!`, 'success');

      } else {

        showToast(res.message || 'Model sync completed.', 'info');

      }

    } catch (e) {

      showToast('Model sync failed: ' + (e.message || e), 'error');

    } finally {

      if (btnEl) {

        btnEl.disabled = false;

        btnEl.textContent = 'Sync Models';

      }

    }

  };



  window.saveNewProvider = async () => {

    const nameEl = document.getElementById('prov-name');

    const typeEl = document.getElementById('prov-type');

    const urlEl = document.getElementById('prov-url');

    const keyEl = document.getElementById('prov-key');

    const saveBtn = document.getElementById('btn-save-new-provider');



    const name = nameEl ? nameEl.value.trim() : '';

    const url = urlEl ? urlEl.value.trim() : '';

    const key = keyEl ? keyEl.value.trim() : '';

    const type = detectProviderType(url, name, key);



    if (!name || !url) {

      showToast('Provider Name and API Base URL are required.', 'error');

      return;

    }



    try {

      if (saveBtn) {

        saveBtn.disabled = true;

        saveBtn.innerHTML = `

          <svg class="animate-spin h-3.5 w-3.5 text-zinc-950 inline mr-1" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">

            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>

            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>

          </svg>

          Connecting & Syncing...

        `;

      }



      const created = await apiCall('/providers', {

        method: 'POST',

        body: JSON.stringify({

          name,

          provider_type: type,

          base_url: url,

          api_key: key || null

        })

      });



      let syncResult = null;

      if (created && created.id) {

        try {

          syncResult = await apiCall(`/providers/${created.id}/sync-models`, { method: 'POST' });

        } catch (syncErr) {

          console.warn('Sync models error:', syncErr);

        }

      }



      state.activeModal = null;

      await fetchProviders();



      if (state.models.length > 0 && !state.selectedDefaultModel) {

        state.selectedDefaultModel = state.models[0].model_name;

        document.cookie = `nova_last_model_id=${encodeURIComponent(state.models[0].model_name)}; path=/; max-age=31536000; SameSite=Lax`;

      }



      render();



      if (syncResult && syncResult.status === 'success' && syncResult.count > 0) {

        showToast(`Connected ${name}! Discovered ${syncResult.count} models.`, 'success');

      } else if (syncResult && syncResult.message) {

        showToast(syncResult.message, 'info');

      } else {

        showToast(`Provider '${name}' added successfully.`, 'success');

      }

    } catch (e) {

      showToast('Failed to add provider: ' + (e.message || e), 'error');

    } finally {

      if (saveBtn) {

        saveBtn.disabled = false;

        saveBtn.textContent = 'Save Provider';

      }

    }

  };



  window.vacuumDb = async () => {



    try {



      await apiCall('/database/vacuum', { method: 'POST' });



      showToast('Database optimized!', 'success');



    } catch (e) {



      showToast(e.message, 'error');



    }



  };



  window.fetchLogs = async () => {



    try {



      const logs = await apiCall('/logs/app?lines=100');



      const el = document.getElementById('logs-viewer');



      if (el) el.innerText = (logs.lines || []).join('\n') || 'No logs recorded.';



    } catch (e) {}



  };



  window.fetchMemory = async () => {



    try {



      const facts = await apiCall('/memory/facts');



      state.memoryFacts = facts || [];



      render();



    } catch (e) {}



  };



  window.delMemory = async (id) => {



    await apiCall(`/memory/facts/${id}`, { method: 'DELETE' });



    window.fetchMemory();



  };



  // (Native browser prompt removed; window.openAddMemoryModal / addMemoryFactPrompt opens graphical modal)



  window.refreshFiles = async () => {



    const el = document.getElementById('file-tree-container');



    if (!el) return;



    try {



      // Use list_directory tool via backend



      const res = await apiCall('/tools');



      // Read directory



      const listData = await fetch('/api/workspaces').then(r => r.json());



      el.innerHTML = `



        <div class="space-y-1">



          <div class="flex items-center gap-1.5 py-1 text-slate-300 font-medium">



            ${icons.folder} <span>backend/</span>



          </div>



          <div class="flex items-center gap-1.5 py-1 text-slate-300 font-medium">



            ${icons.folder} <span>frontend/</span>



          </div>



          <div class="flex items-center gap-1.5 py-1 text-slate-300 font-medium">



            ${icons.folder} <span>data/</span>



          </div>



          <div class="flex items-center gap-1.5 py-1 text-slate-400 font-mono text-[11px] pl-4">



            ${icons.file} <span>nova.db</span>



          </div>



          <div class="flex items-center gap-1.5 py-1 text-slate-400 font-mono text-[11px] pl-4">



            ${icons.file} <span>start.bat</span>



          </div>



          <div class="flex items-center gap-1.5 py-1 text-slate-400 font-mono text-[11px] pl-4">



            ${icons.file} <span>requirements.txt</span>



          </div>



        </div>



      `;



    } catch (e) {



      el.innerHTML = '<div class="text-rose-400">Failed to inspect workspace.</div>';



    }



  };







  // Global Outside Click Listener



  document.addEventListener('click', (e) => {



    let shouldRender = false;



    if (state.activeDropdown && !e.target.closest('#context-menu-container') && !e.target.closest('[title="Options"]')) {



      state.activeDropdown = null;



      shouldRender = true;



    }



    if (state.slashMenuOpen && !e.target.closest('#skills-slash-menu') && e.target.id !== 'composer-input' && !e.target.closest('#btn-toggle-skills')) {



      state.slashMenuOpen = false;



      shouldRender = true;



    }



    if (shouldRender) render();



  });







  // Launch Application



  document.addEventListener('DOMContentLoaded', init);



  if (document.readyState === 'complete' || document.readyState === 'interactive') {



    init();



  }





  // Skills & MCP Global Window Bindings

  window.openAddSkillModal = () => {

    state.activeSubModal = 'add_skill';

    render();

  };



  window.openAddMCPModal = () => {

    state.activeSubModal = 'add_mcp';

    render();

  };



  window.closeSubModal = () => {

    state.activeSubModal = null;

    render();

  };



  window.switchMCPModalType = (type) => {

    state.mcpModalType = type;

    render();

  };



  window.saveNewSkill = async () => {

    const nameEl = document.getElementById('skill-name');

    const cmdEl = document.getElementById('skill-cmd');

    const descEl = document.getElementById('skill-desc');

    const promptEl = document.getElementById('skill-prompt');

    const colorEl = document.getElementById('skill-color');



    if (!nameEl || !cmdEl || !descEl || !promptEl) return;

    const name = nameEl.value.trim();

    const command = cmdEl.value.trim();

    const desc = descEl.value.trim();

    const prompt = promptEl.value.trim();

    const color = colorEl ? colorEl.value : 'indigo';



    if (!name || !command || !desc || !prompt) {

      showToast('Please fill in all skill fields.', 'error');

      return;

    }



    try {

      showToast('Registering new skill...', 'info');

      const res = await apiCall('/skills', {

        method: 'POST',

        body: JSON.stringify({

          name: name,

          command: command,

          description: desc,

          system_prompt: prompt,

          icon: 'sparkles',

          color: color

        })

      });

      state.activeSubModal = null;

      const skillsData = await apiCall('/skills').catch(() => ({ skills: [] }));

      state.skills = (skillsData && skillsData.skills) || [];

      showToast('Skill ' + command + ' added and activated successfully!', 'success');

      render();

    } catch (e) {

      showToast('Error saving skill: ' + e.message, 'error');

    }

  };



  window.deleteSkill = async (skillId) => {

    showConfirmModal(

      'Delete Skill',

      'Are you sure you want to delete this custom skill? Its trigger command and configuration file will be removed.',

      async () => {

        try {

          await apiCall(`/skills/${skillId}`, { method: 'DELETE' });

          const skillsData = await apiCall('/skills').catch(() => ({ skills: [] }));

          state.skills = (skillsData && skillsData.skills) || [];

          showToast('Skill deleted successfully.', 'info');

          render();

        } catch (e) {

          showToast('Error deleting skill: ' + e.message, 'error');

        }

      },

      'Delete Skill',

      'bg-rose-600 hover:bg-rose-500 text-white'

    );

  };



  window.saveNewMCPServer = async () => {

    const isRemote = (state.mcpModalType || 'remote') === 'remote';

    const nameEl = document.getElementById('mcp-name');

    let name = nameEl ? nameEl.value.trim() : '';



    let payload = { is_enabled: 1 };



    if (isRemote) {

      const urlEl = document.getElementById('mcp-remote-url');

      const envEl = document.getElementById('mcp-remote-env');

      const rawInput = urlEl ? urlEl.value.trim() : '';

      if (!rawInput && !name) {

        showToast('Please specify an MCP endpoint URL or JSON configuration.', 'error');

        return;

      }

      let env = {};

      if (envEl && envEl.value.trim()) {

        try { env = JSON.parse(envEl.value.trim()); } catch (e) { showToast('Invalid JSON format for headers.', 'error'); return; }

      }

      payload = {

        name: name || rawInput,

        url: rawInput.startsWith('http') ? rawInput : undefined,

        config_json: rawInput.includes('{') ? rawInput : undefined,

        transport_type: 'http',

        env: env,

        is_enabled: 1

      };

    } else {

      const cmdEl = document.getElementById('mcp-local-cmd');

      const argsEl = document.getElementById('mcp-local-args');

      const envEl = document.getElementById('mcp-local-env');

      const cmd = cmdEl ? cmdEl.value.trim() : '';

      const argsStr = argsEl ? argsEl.value.trim() : '';

      const args = argsStr ? argsStr.split(/\s+/) : [];

      if (!cmd) {

        showToast('Please specify the executable command (e.g. npx, uvx, python).', 'error');

        return;

      }

      let env = {};

      if (envEl && envEl.value.trim()) {

        try { env = JSON.parse(envEl.value.trim()); } catch (e) { showToast('Invalid JSON format for environment variables.', 'error'); return; }

      }

      payload = {

        name: name || cmd,

        transport_type: 'stdio',

        command: cmd,

        args: args,

        env: env,

        is_enabled: 1

      };

    }



    state.mcpConnecting = true;

    render();



    try {

      showToast('Connecting to MCP server and discovering tools...', 'info');

      const res = await apiCall('/mcp/servers', {

        method: 'POST',

        body: JSON.stringify(payload)

      });

      state.activeSubModal = null;

      const mcpData = await apiCall('/mcp/servers').catch(() => ({ servers: [] }));

      state.mcpServers = (mcpData && mcpData.servers) || [];

      const srv = res && res.server;

      const count = (srv && srv.tools_count) || 0;

      showToast('MCP server connected! ' + count + ' AI tools discovered.', 'success');

      render();

    } catch (e) {

      showToast('Error connecting to MCP server: ' + e.message, 'error');

    } finally {

      state.mcpConnecting = false;

      render();

    }

  };



  window.installMCPPreset = async (presetId) => {

    const preset = (state.mcpPresets || []).find(p => p.id === presetId);

    if (!preset) return;

    try {

      showToast('Installing and connecting ' + preset.name + '...', 'info');

      await apiCall('/mcp/servers', {

        method: 'POST',

        body: JSON.stringify({

          name: preset.name,

          transport_type: preset.transport_type || 'http',

          url: preset.url || '',

          command: preset.command || '',

          args: preset.args || [],

          env: {},

          is_enabled: 1

        })

      });

      const mcpData = await apiCall('/mcp/servers').catch(() => ({ servers: [] }));

      state.mcpServers = (mcpData && mcpData.servers) || [];

      showToast(preset.name + ' installed and connected successfully!', 'success');

      render();

    } catch (e) {

      showToast('Error installing preset: ' + e.message, 'error');

    }

  };



  window.connectMCPServer = async (serverId) => {

    state.connectingMcpServerId = serverId;

    render();

    try {

      showToast('Connecting to MCP server and discovering tools...', 'info');

      await apiCall(`/mcp/servers/${serverId}/connect`, { method: 'POST' });

      const mcpData = await apiCall('/mcp/servers').catch(() => ({ servers: [] }));

      state.mcpServers = (mcpData && mcpData.servers) || [];

      showToast('MCP server connected and tools enabled!', 'success');

      render();

    } catch (e) {

      showToast('Connection error: ' + e.message, 'error');

    } finally {

      state.connectingMcpServerId = null;

      render();

    }

  };



  window.disconnectMCPServer = async (serverId) => {

    try {

      await apiCall(`/mcp/servers/${serverId}/disconnect`, { method: 'POST' });

      const mcpData = await apiCall('/mcp/servers').catch(() => ({ servers: [] }));

      state.mcpServers = (mcpData && mcpData.servers) || [];

      showToast('MCP server disconnected.', 'info');

      render();

    } catch (e) {

      showToast('Error: ' + e.message, 'error');

    }

  };



  window.deleteMCPServer = async (serverId) => {

    showConfirmModal(

      'Delete MCP Server',

      'Are you sure you want to disconnect and delete this MCP server? Its registered tools will no longer be available to the agent.',

      async () => {

        try {

          await apiCall(`/mcp/servers/${serverId}`, { method: 'DELETE' });

          const mcpData = await apiCall('/mcp/servers').catch(() => ({ servers: [] }));

          state.mcpServers = (mcpData && mcpData.servers) || [];

          showToast('MCP server removed.', 'info');

          render();

        } catch (e) {

          showToast('Error deleting MCP server: ' + e.message, 'error');

        }

      },

      'Delete Server',

      'bg-rose-600 hover:bg-rose-500 text-white'

    );

  };

})();


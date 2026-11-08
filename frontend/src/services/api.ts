import {
  Conversation,
  Message,
  ToolCall,
  ExecutionApproval,
  Provider,
  ProviderModel,
  AgentProfile,
  SystemPrompt,
  Workspace,
  MemoryFact,
  SystemHealthStats
} from '../types';

const API_BASE = '/api';

export const api = {
  // Health
  async getHealth() {
    const res = await fetch(`${API_BASE}/health`);
    return res.json();
  },

  // Conversations
  async listConversations(includeArchived = false): Promise<Conversation[]> {
    const res = await fetch(`${API_BASE}/conversations?include_archived=${includeArchived}`);
    return res.json();
  },

  async createConversation(data: Partial<Conversation>): Promise<Conversation> {
    const res = await fetch(`${API_BASE}/conversations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return res.json();
  },

  async getConversation(id: string): Promise<{ conversation: Conversation; messages: Message[] }> {
    const res = await fetch(`${API_BASE}/conversations/${id}`);
    return res.json();
  },

  async updateConversation(id: string, updates: Partial<Conversation>): Promise<Conversation> {
    const res = await fetch(`${API_BASE}/conversations/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates)
    });
    return res.json();
  },

  async deleteConversation(id: string): Promise<{ status: string }> {
    const res = await fetch(`${API_BASE}/conversations/${id}`, { method: 'DELETE' });
    return res.json();
  },

  async sendMessage(convId: string, content: string, preApprovedId?: string) {
    const res = await fetch(`${API_BASE}/conversations/${convId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, pre_approved_id: preApprovedId })
    });
    return res.json();
  },

  // Providers & Models
  async listProviders(): Promise<Provider[]> {
    const res = await fetch(`${API_BASE}/providers`);
    return res.json();
  },

  async createProvider(data: any): Promise<Provider> {
    const res = await fetch(`${API_BASE}/providers`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return res.json();
  },

  async updateProvider(id: string, data: any): Promise<Provider> {
    const res = await fetch(`${API_BASE}/providers/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return res.json();
  },

  async deleteProvider(id: string) {
    const res = await fetch(`${API_BASE}/providers/${id}`, { method: 'DELETE' });
    return res.json();
  },

  async testProvider(id: string) {
    const res = await fetch(`${API_BASE}/providers/${id}/test`, { method: 'POST' });
    return res.json();
  },

  async syncProviderModels(id: string) {
    const res = await fetch(`${API_BASE}/providers/${id}/sync-models`, { method: 'POST' });
    return res.json();
  },

  async addManualModel(provId: string, modelData: any) {
    const res = await fetch(`${API_BASE}/providers/${provId}/models`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(modelData)
    });
    return res.json();
  },

  async listAllModels(): Promise<ProviderModel[]> {
    const res = await fetch(`${API_BASE}/models`);
    return res.json();
  },

  // Profiles & Prompts
  async listAgentProfiles(): Promise<AgentProfile[]> {
    const res = await fetch(`${API_BASE}/agent-profiles`);
    return res.json();
  },

  async createAgentProfile(data: any): Promise<AgentProfile> {
    const res = await fetch(`${API_BASE}/agent-profiles`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return res.json();
  },

  async listSystemPrompts(): Promise<SystemPrompt[]> {
    const res = await fetch(`${API_BASE}/system-prompts`);
    return res.json();
  },

  async createSystemPrompt(data: any): Promise<SystemPrompt> {
    const res = await fetch(`${API_BASE}/system-prompts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return res.json();
  },

  // Tools & Executions
  async listTools() {
    const res = await fetch(`${API_BASE}/tools`);
    return res.json();
  },

  async listExecutions(convId: string): Promise<ToolCall[]> {
    const res = await fetch(`${API_BASE}/executions/conversations/${convId}`);
    return res.json();
  },

  async cancelExecution(executionId: string) {
    const res = await fetch(`${API_BASE}/executions/${executionId}/cancel`, { method: 'POST' });
    return res.json();
  },

  // Approvals
  async getApproval(id: string): Promise<ExecutionApproval> {
    const res = await fetch(`${API_BASE}/approvals/${id}`);
    return res.json();
  },

  async decideApproval(id: string, decision: 'approved_once' | 'approved_session' | 'denied') {
    const res = await fetch(`${API_BASE}/approvals/${id}/decide`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision, actor: 'user' })
    });
    return res.json();
  },

  // Workspaces
  async listWorkspaces(): Promise<Workspace[]> {
    const res = await fetch(`${API_BASE}/workspaces`);
    return res.json();
  },

  async createWorkspace(name: string, path: string, description = ''): Promise<Workspace> {
    const res = await fetch(`${API_BASE}/workspaces`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, path, description })
    });
    return res.json();
  },

  async activateWorkspace(id: string): Promise<Workspace> {
    const res = await fetch(`${API_BASE}/workspaces/${id}/activate`, { method: 'POST' });
    return res.json();
  },

  // Memory & Search
  async listMemoryFacts(category?: string): Promise<MemoryFact[]> {
    const url = category ? `${API_BASE}/memory/facts?category=${category}` : `${API_BASE}/memory/facts`;
    const res = await fetch(url);
    return res.json();
  },

  async createMemoryFact(content: string, category = 'project_detail'): Promise<MemoryFact> {
    const res = await fetch(`${API_BASE}/memory/facts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, category })
    });
    return res.json();
  },

  async deleteMemoryFact(id: string) {
    const res = await fetch(`${API_BASE}/memory/facts/${id}`, { method: 'DELETE' });
    return res.json();
  },

  async searchMemoryAndHistory(query: string) {
    const res = await fetch(`${API_BASE}/memory/search?query=${encodeURIComponent(query)}`);
    return res.json();
  },

  // Attachments
  async uploadAttachment(filename: string, contentBase64: string, conversationId: string) {
    const res = await fetch(`${API_BASE}/attachments`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename, content_base64: contentBase64, conversation_id: conversationId })
    });
    return res.json();
  },

  // Settings
  async getSettings() {
    const res = await fetch(`${API_BASE}/settings`);
    return res.json();
  },

  async updateSettingsSection(sectionKey: string, values: Record<string, any>) {
    const res = await fetch(`${API_BASE}/settings/${sectionKey}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ values })
    });
    return res.json();
  },

  // Database
  async getDatabaseStatus() {
    const res = await fetch(`${API_BASE}/database/status`);
    return res.json();
  },

  async vacuumDatabase() {
    const res = await fetch(`${API_BASE}/database/vacuum`, { method: 'POST' });
    return res.json();
  },

  // Diagnostics
  async getAppLogs(lines = 100) {
    const res = await fetch(`${API_BASE}/logs/app?lines=${lines}`);
    return res.json();
  },

  async getAuditLogs(lines = 100) {
    const res = await fetch(`${API_BASE}/logs/audit?lines=${lines}`);
    return res.json();
  }
};

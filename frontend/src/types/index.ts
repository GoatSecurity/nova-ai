export interface Conversation {
  id: string;
  title: string;
  provider_id: string | null;
  model_id: string | null;
  agent_profile_id: string | null;
  system_prompt_id: string | null;
  workspace_path: string | null;
  permission_mode: 'ask_every_time' | 'allow_safe' | 'session_approval' | 'manual';
  is_pinned: number;
  is_archived: number;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  thoughts?: string;
  tokens: number;
  created_at: string;
}

export interface ToolCall {
  id: string;
  message_id: string;
  conversation_id: string;
  tool_name: string;
  arguments_json: string;
  arguments?: Record<string, any>;
  risk_level: 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL';
  status: 'pending' | 'waiting_approval' | 'approved' | 'rejected' | 'running' | 'completed' | 'failed' | 'cancelled';
  created_at: string;
  stdout?: string;
  stderr?: string;
  exit_code?: number;
  duration_ms?: number;
  is_error?: number;
  output?: Record<string, any>;
}

export interface ExecutionApproval {
  id: string;
  conversation_id: string;
  tool_call_id: string;
  command_hash: string;
  command: string;
  shell: string;
  cwd: string;
  risk_level: 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL';
  status: 'pending' | 'approved_once' | 'approved_session' | 'denied' | 'expired';
  decided_by?: string;
  created_at: string;
  decided_at?: string;
}

export interface Provider {
  id: string;
  name: string;
  provider_type: 'openai_compatible' | 'ollama' | 'anthropic' | 'gemini' | 'lm_studio';
  base_url: string;
  api_key_masked?: string;
  auth_type: string;
  custom_headers: Record<string, string>;
  models_endpoint: string;
  chat_endpoint: string;
  is_enabled: number;
  created_at: string;
}

export interface ProviderModel {
  id: string;
  provider_id: string;
  model_name: string;
  display_name: string;
  context_length: number;
  supports_tools: number;
  supports_vision: number;
  is_local: number;
  is_enabled: number;
  provider_name?: string;
  provider_type?: string;
}

export interface AgentProfile {
  id: string;
  name: string;
  description: string;
  system_instructions: string;
  preferred_tools: string[];
  default_risk_mode: string;
  is_builtin: number;
}

export interface SystemPrompt {
  id: string;
  name: string;
  content: string;
  is_global: number;
  is_active: number;
}

export interface PlanStep {
  id: string;
  title: string;
  description?: string;
  status: 'pending' | 'in_progress' | 'waiting_approval' | 'completed' | 'failed' | 'skipped';
  result_summary?: string;
}

export interface TaskPlan {
  conversation_id: string;
  task_goal: string;
  steps: PlanStep[];
}

export interface Workspace {
  id: string;
  name: string;
  path: string;
  description: string;
  is_active: number;
}

export interface MemoryFact {
  id: string;
  conversation_id?: string;
  category: 'user_preference' | 'project_detail' | 'environment' | 'instruction';
  content: string;
  confidence: number;
  created_at: string;
}

export interface SystemHealthStats {
  os: string;
  release: string;
  cpu_count_logical: number;
  total_ram_gb: number;
  available_ram_gb: number;
  ram?: {
    percent_used: number;
    used_gb: number;
    total_gb: number;
  };
  disks?: Array<{
    device: string;
    mountpoint: string;
    percent_used: number;
    free_gb: number;
    total_gb: number;
  }>;
}

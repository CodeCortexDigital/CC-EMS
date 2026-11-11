// The school's AI settings: which AI features are on, what they cost this month, and the AI use notice.
import api from './api';

export interface AiFeature { key: string; label: string; description: string; enabled: boolean }
export interface AiUsage {
  since: string; requests: number; input_tokens: number; output_tokens: number; monthly_token_cap: number;
  by_feature: Array<{ feature: string; label: string; requests: number; tokens: number }>;
}
export interface ApprovalCandidate { id: string; name: string; email: string; role: string }
export interface ApprovalRule { required: 1 | 2; approvers: string[]; candidates: ApprovalCandidate[] }
export interface AiSettings {
  ai_enabled: boolean;
  approval: ApprovalRule;
  provider: { configured: boolean; name: string; note: string };
  contact_details_shared: boolean;
  features: AiFeature[];
  usage: AiUsage;
  notice: { version: number; text: string; accepted: boolean; accepted_at: string | null; accepted_by: string | null };
}

const aiSettings = {
  async get(): Promise<AiSettings> { return (await api.get('/ai/settings/')).data; },
  async setFeatures(features: Record<string, boolean>): Promise<AiSettings> { return (await api.put('/ai/settings/', { features })).data; },
  async setAiEnabled(ai_enabled: boolean): Promise<AiSettings> { return (await api.put('/ai/settings/', { ai_enabled })).data; },
  async setApproval(required: 1 | 2, approvers: string[]): Promise<AiSettings> { return (await api.put('/ai/settings/', { approval: { required, approvers } })).data; },
  async acceptNotice(): Promise<AiSettings> { return (await api.post('/ai/settings/accept-notice/')).data; },
};

export default aiSettings;

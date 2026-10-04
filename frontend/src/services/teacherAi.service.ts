// Teacher assistant drafts: a message to a family and a rubric. Both are drafts to read and edit; nothing is sent or saved here.
import api from './api';

export type MessageKind = 'behavior_concern' | 'positive_note' | 'missed_assignments' | 'attendance_concern' | 'custom';
export type Tone = 'warm' | 'formal' | 'brief';
export const MESSAGE_KIND_LABEL: Record<MessageKind, string> = {
  behavior_concern: 'A behavior concern', positive_note: 'A positive note', missed_assignments: 'Missing assignments',
  attendance_concern: 'An attendance concern', custom: 'Something else',
};
export const TONE_LABEL: Record<Tone, string> = { warm: 'Warm', formal: 'Formal', brief: 'Brief' };

export interface MessageDraft { subject: string; body: string; source: 'ai' | 'template'; warnings: string[] }
export interface RubricLevel { label: string; description: string }
export interface RubricCriterion { name: string; levels: RubricLevel[] }
export type Rubric = RubricCriterion[];
export const DEFAULT_LEVELS = ['Exceeds', 'Meets', 'Approaching', 'Beginning'];

const teacherAi = {
  async parentMessage(body: { student: string; template: MessageKind; details: string; tone: Tone }): Promise<MessageDraft> {
    return (await api.post('/ai/parent-message/', body)).data;
  },
  async rubric(body: { title: string; instructions?: string; subject?: string; grade?: string; standards?: string[]; levels?: string[] }):
    Promise<{ criteria: Rubric; source: 'ai' | 'template' }> {
    return (await api.post('/ai/rubric/', body)).data;
  },
};

export default teacherAi;

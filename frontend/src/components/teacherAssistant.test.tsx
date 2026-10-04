// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock('@/services/api', () => ({
  extractListData: (d: unknown) => d,
  default: { get: vi.fn(), post: vi.fn() },
}));

import api from '@/services/api';
import DraftWithAi from '@/components/messages/DraftWithAi';
import RubricEditor, { RubricTable } from '@/components/gradebook/RubricEditor';
import type { Rubric } from '@/services/teacherAi.service';

const get = api.get as unknown as ReturnType<typeof vi.fn>;
const post = api.post as unknown as ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks(); cleanup();
  get.mockResolvedValue({ data: [{ id: 's1', student_id: 'STU1', name: 'Kid Four', class_name: 'Grade 4' }] });
});

async function pickStudent() {
  fireEvent.click(screen.getByRole('button', { name: /Draft with AI/ }));
  fireEvent.change(screen.getByLabelText('Which student is this about?'), { target: { value: 'kid' } });
  fireEvent.click(await screen.findByRole('option', { name: /Kid Four/ }));
}

describe('Draft a message to a family', () => {
  it('needs a student and some notes, then fills the subject and message for the teacher to edit', async () => {
    post.mockResolvedValue({ data: { subject: 'Catching up', body: 'Dear family, ...', source: 'ai', warnings: [] } });
    const onDraft = vi.fn();
    render(<DraftWithAi onDraft={onDraft} />);
    await pickStudent();
    const go = screen.getByRole('button', { name: 'Draft the message' }) as HTMLButtonElement;
    expect(go.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('Message type'), { target: { value: 'positive_note' } });
    fireEvent.change(screen.getByLabelText('Tone'), { target: { value: 'brief' } });
    fireEvent.change(screen.getByLabelText('Your notes'), { target: { value: 'Helped a new classmate' } });
    fireEvent.click(go);
    await waitFor(() => expect(post).toHaveBeenCalledWith('/ai/parent-message/', { student: 's1', template: 'positive_note', details: 'Helped a new classmate', tone: 'brief' }));
    expect(onDraft).toHaveBeenCalledWith({ subject: 'Catching up', body: 'Dear family, ...' });
    expect(await screen.findByText(/Drafted by AI/)).toBeTruthy();
  });

  it('says so when it is a plain template, and passes on warnings about sensitive notes', async () => {
    post.mockResolvedValue({ data: { subject: 's', body: 'b', source: 'template', warnings: ['Keep these for the office or nurse.'] } });
    render(<DraftWithAi onDraft={() => undefined} />);
    await pickStudent();
    fireEvent.change(screen.getByLabelText('Your notes'), { target: { value: 'He takes medication' } });
    fireEvent.click(screen.getByRole('button', { name: 'Draft the message' }));
    expect(await screen.findByText(/standard template/)).toBeTruthy();
    expect(screen.getByRole('alert').textContent).toMatch(/office or nurse/);
  });
});

describe('Rubric editor', () => {
  const draft: Rubric = [{ name: 'Accuracy', levels: [{ label: 'Exceeds', description: 'No errors' }, { label: 'Meets', description: 'Few errors' }] }];
  const ctx = { title: 'Fractions project', instructions: '', subject: 'Math', grade: 'Grade 4' };

  it('drafts a rubric from the assignment and hands it back to be edited', async () => {
    post.mockResolvedValue({ data: { criteria: draft, source: 'ai' } });
    const onChange = vi.fn();
    render(<RubricEditor value={[]} onChange={onChange} context={ctx} />);
    fireEvent.click(screen.getByRole('button', { name: /Draft with AI/ }));
    await waitFor(() => expect(onChange).toHaveBeenCalledWith(draft));
    expect(post).toHaveBeenCalledWith('/ai/rubric/', expect.objectContaining({ title: 'Fractions project', subject: 'Math', grade: 'Grade 4' }));
    expect(await screen.findByText(/Drafted by AI/)).toBeTruthy();
  });

  it('will not draft without a title', () => {
    render(<RubricEditor value={[]} onChange={() => undefined} context={{ ...ctx, title: '' }} />);
    fireEvent.click(screen.getByRole('button', { name: /Draft with AI/ }));
    expect(post).not.toHaveBeenCalled();
  });

  it('lets the teacher edit what a level looks like, add a criterion and remove one', () => {
    const onChange = vi.fn();
    render(<RubricEditor value={draft} onChange={onChange} context={ctx} />);
    fireEvent.change(screen.getByLabelText('Criterion 1, Meets'), { target: { value: 'Mostly right' } });
    expect(onChange).toHaveBeenLastCalledWith([{ name: 'Accuracy', levels: [{ label: 'Exceeds', description: 'No errors' }, { label: 'Meets', description: 'Mostly right' }] }]);
    fireEvent.click(screen.getByRole('button', { name: /Add a criterion/ }));
    expect(onChange).toHaveBeenLastCalledWith([...draft, { name: '', levels: [{ label: 'Exceeds', description: '' }, { label: 'Meets', description: '' }] }]);
    fireEvent.click(screen.getByLabelText('Remove criterion 1'));
    expect(onChange).toHaveBeenLastCalledWith([]);
  });

  it('asks before replacing a rubric that already exists', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    render(<RubricEditor value={draft} onChange={() => undefined} context={ctx} />);
    fireEvent.click(screen.getByRole('button', { name: /Draft with AI/ }));
    expect(confirm).toHaveBeenCalled();
    expect(post).not.toHaveBeenCalled();
    confirm.mockRestore();
  });

  it('shows a rubric as a table for grading', () => {
    render(<RubricTable rubric={draft} />);
    expect(screen.getByText('Accuracy')).toBeTruthy();
    expect(screen.getByText('No errors')).toBeTruthy();
    expect(screen.getByRole('columnheader', { name: 'Meets' })).toBeTruthy();
  });
});

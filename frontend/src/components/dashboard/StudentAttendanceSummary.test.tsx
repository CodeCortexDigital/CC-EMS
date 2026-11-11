import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import StudentAttendanceSummary from './StudentAttendanceSummary';

describe('StudentAttendanceSummary', () => {
  it('shows excused students so present, late, absent and excused add up to the total', () => {
    render(<StudentAttendanceSummary total={214} present={204} late={0} absent={4} loading={false} />);
    expect(screen.getByText('Excused')).toBeInTheDocument();
    expect(screen.getByText('6')).toBeInTheDocument();
  });

  it('has no excused column when everyone is accounted for', () => {
    render(<StudentAttendanceSummary total={100} present={90} late={4} absent={6} loading={false} />);
    expect(screen.queryByText('Excused')).not.toBeInTheDocument();
  });
});

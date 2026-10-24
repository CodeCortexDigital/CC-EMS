// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import OverflowTabs, { fitCount } from './OverflowTabs';

const items = ['One', 'Two', 'Three', 'Four', 'Five', 'Six'].map((label) => ({ id: label.toLowerCase(), label }));

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

/** jsdom has no layout: say every tab is 100px wide and the row is `row` px wide. */
function layout(row: number) {
  vi.spyOn(HTMLElement.prototype, 'offsetWidth', 'get').mockReturnValue(100);
  vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(row);
}

describe('fitCount', () => {
  it('shows everything when it fits, or when the width is not known yet', () => {
    expect(fitCount([100, 100, 100], 400)).toBe(3);
    expect(fitCount([100, 100, 100], 0)).toBe(3);
  });
  it('leaves room for the More button when some do not fit, and never shows fewer than one', () => {
    expect(fitCount([100, 100, 100, 100, 100, 100], 400)).toBe(3);   // 92 for More + 3 x 100 = 392
    expect(fitCount([300, 300], 200)).toBe(1);
  });
});

describe('OverflowTabs', () => {
  it('shows all tabs when there is room, with no More button', () => {
    layout(1000);
    render(<OverflowTabs items={items} activeId="one" onSelect={() => undefined} />);
    expect(screen.queryByRole('button', { name: /More/ })).toBeNull();
    expect(screen.getAllByRole('button').filter((b) => b.getAttribute('aria-hidden') !== 'true')).toHaveLength(6);
  });

  it('puts what does not fit under More, and the menu opens the page', () => {
    layout(400);
    const onSelect = vi.fn();
    render(<OverflowTabs items={items} activeId="one" onSelect={onSelect} />);
    expect(screen.getByRole('button', { name: /One/ })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Six' })).toBeNull();
    const more = screen.getByRole('button', { name: /More/ });
    expect(more.textContent).toContain('3');
    fireEvent.click(more);
    fireEvent.click(within(screen.getByRole('menu')).getByRole('menuitem', { name: 'Five' }));
    expect(onSelect).toHaveBeenCalledWith('five');
    expect(screen.queryByRole('menu')).toBeNull();
  });

  it('keeps the current page visible in the row even when it would not fit', () => {
    layout(400);
    render(<OverflowTabs items={items} activeId="six" onSelect={() => undefined} />);
    const six = screen.getByRole('button', { name: 'Six' });
    expect(six.getAttribute('aria-current')).toBe('page');
    expect(within(screen.getByRole('button', { name: /More/ })).queryByText('Six')).toBeNull();
  });

  it('closes the menu with Escape', () => {
    layout(400);
    render(<OverflowTabs items={items} activeId="one" onSelect={() => undefined} />);
    fireEvent.click(screen.getByRole('button', { name: /More/ }));
    expect(screen.getByRole('menu')).toBeTruthy();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('menu')).toBeNull();
  });

  it('works as in-page tabs too (role=tab, selected state)', () => {
    layout(1000);
    render(<OverflowTabs role="tab" items={items} activeId="two" onSelect={() => undefined} />);
    expect(screen.getByRole('tab', { name: 'Two' }).getAttribute('aria-selected')).toBe('true');
    expect(screen.getByRole('tab', { name: 'One' }).getAttribute('aria-selected')).toBe('false');
  });
});

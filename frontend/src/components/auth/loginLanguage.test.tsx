// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import LoginFrame from './LoginFrame';
import { useLocaleStore } from '@/store/localeStore';

afterEach(() => { cleanup(); useLocaleStore.setState({ userLanguage: null }); });

describe('Sign-in page language choice', () => {
  it('offers the language menu and remembers the chosen language', () => {
    render(<MemoryRouter><LoginFrame console="Admin"><p>form</p></LoginFrame></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: /Language/i }));
    fireEvent.click(screen.getByRole('radio', { name: /日本語/ }));
    expect(useLocaleStore.getState().userLanguage).toBe('ja');
  });
});

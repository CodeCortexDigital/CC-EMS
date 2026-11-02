// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { applyPageText } from './pageText';

const tick = () => new Promise((r) => setTimeout(r, 0));

afterEach(async () => { await applyPageText('en'); document.body.innerHTML = ''; });

describe('text written into pages', () => {
  it('swaps known wording for the chosen language, keeping spaces, and leaves the rest alone', async () => {
    document.body.innerHTML = '<h1> Interventions </h1><p>Some unknown text</p><input placeholder="Search a student or title"><code>Interventions</code><div translate="no">Interventions</div>';
    await applyPageText('es');
    expect(document.querySelector('h1')!.textContent).toBe(' Intervenciones ');
    expect(document.querySelector('p')!.textContent).toBe('Some unknown text');
    expect(document.querySelector('input')!.getAttribute('placeholder')).toBe('Buscar un estudiante o título');
    expect(document.querySelector('code')!.textContent).toBe('Interventions');
    expect(document.querySelector('[translate=no]')!.textContent).toBe('Interventions');
  });

  it('translates text that appears later, and text the page changes afterwards', async () => {
    document.body.innerHTML = '<div id="root"></div>';
    await applyPageText('es');
    const root = document.getElementById('root')!;
    root.innerHTML = '<b>New intervention</b>';
    await tick();
    expect(root.textContent).toBe('Nueva intervención');
    root.firstChild!.firstChild!.nodeValue = 'Reviews due';                  // the page (React) writes new English
    await tick();
    expect(root.textContent).toBe('Revisiones pendientes');
  });

  it('puts the English back when English is chosen again', async () => {
    document.body.innerHTML = '<h1>Interventions</h1><input placeholder="Search a student or title">';
    await applyPageText('es');
    expect(document.querySelector('h1')!.textContent).toBe('Intervenciones');
    await applyPageText('en');
    expect(document.querySelector('h1')!.textContent).toBe('Interventions');
    expect(document.querySelector('input')!.getAttribute('placeholder')).toBe('Search a student or title');
  });
});

describe('phrase lists', () => {
  const files = import.meta.glob('./phrases/*.json', { eager: true }) as Record<string, { default: Record<string, string> }>;
  const holes = (s: string) => (s.match(/\{[^}]*\}|%[sd]/g) ?? []).sort().join('|');

  it('exist for Spanish, Portuguese, French, German and Arabic, with real coverage', () => {
    for (const code of ['es', 'pt', 'fr', 'de', 'ar']) {
      const list = files[`./phrases/${code}.json`]?.default;
      expect(list, code).toBeTruthy();
      expect(Object.keys(list).length, code).toBeGreaterThan(4000);
    }
  });

  it('never have an empty translation or lose a {placeholder}', () => {
    for (const [file, mod] of Object.entries(files)) {
      for (const [en, out] of Object.entries(mod.default)) {
        expect(out.trim(), `${file}: ${en}`).not.toBe('');
        expect(holes(out), `${file}: ${en}`).toBe(holes(en));
      }
    }
  });
});

describe('regional wording', () => {
  it('applies the school\'s wording to text written into pages, before translating', async () => {
    const { setRegionWording } = await import('./pageText');
    setRegionWording((t) => t.replace(/Date Sheet/g, 'Exam Schedule'));
    document.body.innerHTML = '<h1>Date Sheet</h1><p>Interventions</p>';
    await applyPageText('en');
    expect(document.querySelector('h1')!.textContent).toBe('Exam Schedule');
    await applyPageText('es');
    expect(document.querySelector('p')!.textContent).toBe('Intervenciones');
    expect(document.querySelector('h1')!.textContent).toBe('Calendario de exámenes');   // regional wording first, then Spanish
    setRegionWording(null);
    await applyPageText('en');
    expect(document.querySelector('h1')!.textContent).toBe('Date Sheet');
  });
});

// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';

vi.mock('./api', () => ({ default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() } }));

import { urlBase64ToUint8Array } from './push.service';

describe('urlBase64ToUint8Array', () => {
  it('turns the server key into the bytes the browser needs', () => {
    expect(Array.from(urlBase64ToUint8Array('AQID'))).toEqual([1, 2, 3]);
    expect(Array.from(urlBase64ToUint8Array('-_8'))).toEqual([251, 255]);          // url-safe characters, no padding
    expect(urlBase64ToUint8Array('')).toHaveLength(0);
  });
});

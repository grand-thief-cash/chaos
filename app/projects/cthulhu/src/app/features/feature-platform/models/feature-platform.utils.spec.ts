import { HttpErrorResponse } from '@angular/common/http';
import { computeValidationError, featurePlatformError, featureStatusTone } from './feature-platform.utils';

describe('Feature Platform utilities', () => {
  it('keeps unknown visually distinct from missing', () => {
    expect(featureStatusTone('unknown')).toBe('unknown');
    expect(featureStatusTone('missing')).toBe('danger');
    expect(featureStatusTone('dirty')).toBe('warning');
  });

  it('preserves structured 409/422 backend error codes', () => {
    const conflict = featurePlatformError(new HttpErrorResponse({
      status: 409,
      error: { code: 'RUN_STATE_CONFLICT', message: 'run changed state' },
    }));
    expect(conflict).toEqual(jasmine.objectContaining({ code: 'RUN_STATE_CONFLICT', message: 'run changed state', status: 409 }));

    const validation = featurePlatformError(new HttpErrorResponse({
      status: 422,
      error: { detail: { code: 'SOURCE_UNAVAILABLE', error: 'profile is unavailable' } },
    }));
    expect(validation.code).toBe('SOURCE_UNAVAILABLE');
    expect(validation.message).toBe('profile is unavailable');
  });

  it('fails compute validation closed for missing subjects, duplicates and invalid cutoff', () => {
    expect(computeValidationError('platform.security.constant_one', 1, [], '2026-07-18T10:00', '2026-07-18T09:00')).toContain('security');
    expect(computeValidationError('platform.security.constant_one', 1, [1, 1], '2026-07-18T10:00', '2026-07-18T09:00')).toContain('unique');
    expect(computeValidationError('platform.security.constant_one', 1, [1], '2026-07-18T10:00', '2026-07-18T11:00')).toContain('cutoff');
    expect(computeValidationError('platform.security.constant_one', 1, [1], '2026-07-18T10:00', '2026-07-18T09:00')).toBeNull();
  });
});

import { FEATURE_PLATFORM_ROUTES } from './feature-platform.routes';

describe('Feature Platform routes', () => {
  it('keeps every Phase 4 view refreshable from a stable URL', () => {
    const paths = FEATURE_PLATFORM_ROUTES.map((route) => route.path);
    expect(paths).toContain('registry');
    expect(paths).toContain('definitions/:featureCode');
    expect(paths).toContain('lineage/:featureCode');
    expect(paths).toContain('runs');
    expect(paths).toContain('runs/:runId');
    expect(paths).toContain('values');
    expect(paths).toContain('compute');
  });
});

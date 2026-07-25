import { FEATURE_PLATFORM_ROUTES } from './feature-platform.routes';

describe('Feature Platform routes', () => {
  it('keeps every Feature Platform view refreshable from a stable URL', () => {
    const paths = FEATURE_PLATFORM_ROUTES.map((route) => route.path);
    expect(paths).toContain('manifests');
    expect(paths).toContain('registry');
    expect(paths).toContain('definitions/:featureCode');
    expect(paths).toContain('lineage');
    expect(paths).toContain('lineage/:featureCode');
    expect(paths).toContain('preview');
    expect(paths).toContain('runs');
    expect(paths).toContain('backfills');
    expect(paths).toContain('runs/:runId');
    expect(paths).toContain('values');
    expect(paths).toContain('purges');
    expect(paths).toContain('compute');
  });
});

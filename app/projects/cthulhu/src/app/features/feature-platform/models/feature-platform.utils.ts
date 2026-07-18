import { HttpErrorResponse } from '@angular/common/http';
import { FeatureAvailability, FeaturePlatformErrorView } from './feature-platform.models';

export type FeatureStatusTone = 'success' | 'warning' | 'danger' | 'processing' | 'neutral' | 'unknown';

export function featureStatusTone(status: string | null | undefined): FeatureStatusTone {
  switch ((status || 'unknown').toLowerCase()) {
    case 'ready':
    case 'valid':
    case 'published':
    case 'loadable':
    case 'available':
    case 'succeeded':
    case 'active':
      return 'success';
    case 'running':
    case 'planning':
    case 'validating':
    case 'queued':
      return 'processing';
    case 'partial':
    case 'draft':
    case 'deprecated':
    case 'dirty':
    case 'stale':
    case 'not_ready':
      return 'warning';
    case 'failed':
    case 'missing':
    case 'invalid':
    case 'unloadable':
    case 'unsupported':
    case 'disabled':
    case 'aborted':
    case 'cancelled':
      return 'danger';
    case 'unknown':
      return 'unknown';
    default:
      return 'neutral';
  }
}

export function featurePlatformError(error: unknown): FeaturePlatformErrorView {
  if (error instanceof HttpErrorResponse) {
    const body = error.error?.detail ?? error.error ?? {};
    const code = String(body.code ?? body.error_code ?? `HTTP_${error.status || 0}`);
    const message = String(body.message ?? body.error ?? error.message ?? 'Feature Platform request failed');
    return { code, message, status: error.status };
  }
  if (error && typeof error === 'object') {
    const body = error as Record<string, unknown>;
    return {
      code: String(body['code'] ?? 'CLIENT_ERROR'),
      message: String(body['message'] ?? 'Feature Platform request failed'),
    };
  }
  return { code: 'CLIENT_ERROR', message: String(error || 'Feature Platform request failed') };
}

export function unknownAvailability(featureCode: string, sourceProfile: string, reason: string): FeatureAvailability {
  return {
    feature_code: featureCode,
    source_profile: sourceProfile,
    status: 'unavailable',
    definition_status: 'unknown',
    version_status: 'unknown',
    dependency_status: 'unknown',
    data_status: 'unknown',
    implementation_status: 'unknown',
    materialization_status: 'unknown',
    execution_readiness: 'unknown',
    reasons: [reason],
    data_fields: [],
  };
}

export function isDirtyRevision(revision: string | null | undefined): boolean {
  return !!revision && revision.toLowerCase().includes('dirty');
}

export function computeValidationError(
  featureCode: string,
  version: number | null,
  securityIds: number[],
  asOf: string,
  cutoff: string,
): string | null {
  if (!featureCode || !version || version <= 0) return 'Choose a published Feature version.';
  if (!securityIds.length) return 'Add at least one security.';
  if (securityIds.some((id) => !Number.isInteger(id) || id <= 0)) return 'Security IDs must be positive integers.';
  if (new Set(securityIds).size !== securityIds.length) return 'Security IDs must be unique.';
  if (!asOf || !cutoff) return 'As-of and data cutoff times are required.';
  if (new Date(cutoff).getTime() > new Date(asOf).getTime()) return 'Data cutoff must not be later than as-of time.';
  return null;
}

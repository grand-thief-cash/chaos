from __future__ import annotations

from collections import Counter

from atlas.models import CrosswalkMapping, CrosswalkValidation, MappingRelation, TaxonomyNode


class CrosswalkValidator:
    """Programmatic safety checks after model mapping and after every repair attempt."""

    def validate(
        self,
        source_nodes: list[TaxonomyNode],
        target_nodes: list[TaxonomyNode],
        mappings: list[CrosswalkMapping],
    ) -> CrosswalkValidation:
        source_codes = {item.code for item in source_nodes}
        target_codes = {item.code for item in target_nodes}
        errors: list[str] = []
        warnings: list[str] = []
        counts = Counter(item.source_code for item in mappings)
        for code in source_codes:
            if counts[code] == 0:
                errors.append(f"SOURCE_UNCOVERED:{code}")
            elif counts[code] > 1:
                errors.append(f"SOURCE_DUPLICATED:{code}")
        mapped_sources: set[str] = set()
        source_scheme = source_nodes[0].scheme if source_nodes else ""
        target_scheme = target_nodes[0].scheme if target_nodes else ""
        for item in mappings:
            if item.source_scheme != source_scheme:
                errors.append(
                    f"SOURCE_SCHEME_MISMATCH:{item.source_code}"
                )
            if item.target_scheme != target_scheme:
                errors.append(
                    f"TARGET_SCHEME_MISMATCH:{item.source_code}"
                )
            if item.source_code not in source_codes:
                errors.append(f"UNKNOWN_SOURCE:{item.source_code}")
                continue
            mapped_sources.add(item.source_code)
            if item.relation == MappingRelation.NO_CANONICAL_MAPPING:
                if item.target_code is not None:
                    errors.append(f"NO_MAPPING_HAS_TARGET:{item.source_code}")
                if not item.exception_reason:
                    errors.append(f"NO_MAPPING_WITHOUT_REASON:{item.source_code}")
            elif not item.target_code or item.target_code not in target_codes:
                errors.append(f"UNKNOWN_TARGET:{item.source_code}:{item.target_code}")
            if item.confidence < 0.7:
                warnings.append(f"LOW_CONFIDENCE:{item.source_code}")
        coverage = len(mapped_sources) / len(source_codes) if source_codes else 1.0
        return CrosswalkValidation(
            valid=not errors,
            source_count=len(source_codes),
            mapped_source_count=len(mapped_sources),
            coverage_ratio=coverage,
            errors=sorted(set(errors)),
            warnings=sorted(set(warnings)),
        )

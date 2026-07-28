from atlas.knowledge_production.industry_crosswalk import CrosswalkValidator
from atlas.models import CrosswalkMapping, MappingRelation, TaxonomyNode


def test_crosswalk_requires_every_source_and_valid_target():
    sources = [
        TaxonomyNode(scheme="EastMoney", code="A", name="锂电池", level=1),
        TaxonomyNode(scheme="EastMoney", code="B", name="机器人", level=1),
    ]
    targets = [TaxonomyNode(scheme="SW2021", code="S1", name="电池", level=1)]
    mappings = [
        CrosswalkMapping(
            source_scheme="EastMoney",
            source_code="A",
            target_scheme="SW2021",
            target_code="S1",
            relation=MappingRelation.NARROWER,
            confidence=0.9,
            rationale="锂电池属于电池",
        )
    ]
    invalid = CrosswalkValidator().validate(sources, targets, mappings)
    assert not invalid.valid
    assert "SOURCE_UNCOVERED:B" in invalid.errors
    mappings.append(
        CrosswalkMapping(
            source_scheme="EastMoney",
            source_code="B",
            target_scheme="SW2021",
            target_code=None,
            relation=MappingRelation.NO_CANONICAL_MAPPING,
            confidence=0.8,
            rationale="无可比分类",
            exception_reason="target scheme has no matching concept",
        )
    )
    assert CrosswalkValidator().validate(sources, targets, mappings).valid

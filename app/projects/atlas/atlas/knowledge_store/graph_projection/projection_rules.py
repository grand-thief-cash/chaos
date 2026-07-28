from atlas.models import Polarity, RelationClaim


_PROJECTABLE_ASSERTIONS = {"OBSERVED_FACT", "COMPANY_DISCLOSURE"}


def is_projectable(claim: RelationClaim) -> bool:
    return (
        claim.status == "ACCEPTED"
        and claim.polarity == Polarity.AFFIRMED
        and claim.assertion_type.value in _PROJECTABLE_ASSERTIONS
        and bool(claim.canonical_predicate)
    )

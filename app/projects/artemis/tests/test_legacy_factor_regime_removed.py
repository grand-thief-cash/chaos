"""Phase 0 contract: the experimental Factor/Regime HTTP APIs stay removed."""

from artemis.api.http_gateway.routes import app


def test_legacy_factor_and_regime_routes_are_not_registered():
    paths = {route.path for route in app.routes}

    assert not any(path == "/factors" or path.startswith("/factors/") for path in paths)
    assert not any(path == "/regime" or path.startswith("/regime/") for path in paths)

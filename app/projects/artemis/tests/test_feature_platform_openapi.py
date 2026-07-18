from artemis.api.http_gateway.routes import app


FEATURE_PATHS = {
    "/features/compute",
    "/features/executions/{run_id}",
    "/features/maintenance/reconcile-stale",
    "/features/manifests/validate",
    "/features/registry/sync",
}


def test_feature_platform_openapi_contract():
    schema = app.openapi()

    assert schema["info"]["title"] == "Artemis Gateway"
    assert schema["info"]["version"] == "0.47.0"
    assert FEATURE_PATHS <= set(schema["paths"])

    compute = schema["paths"]["/features/compute"]["post"]
    request_schema = compute["requestBody"]["content"]["application/json"]["schema"]
    assert request_schema["$ref"].endswith("/FeatureComputeRequest")
    assert {"200", "202", "409", "422"} <= set(compute["responses"])

    model = schema["components"]["schemas"]["FeatureComputeRequest"]
    assert {"features", "security_ids", "as_of_time", "data_cutoff_time", "market"} <= set(model["required"])
    assert model["properties"]["security_ids"]["maxItems"] == 20000

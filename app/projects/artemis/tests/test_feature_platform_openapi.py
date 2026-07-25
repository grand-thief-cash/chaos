from artemis.api.http_gateway.routes import app


FEATURE_PATHS = {
    "/features/compute",
    "/features/executions/{run_id}",
    "/features/maintenance/reconcile-stale",
    "/features/manifests/catalog",
    "/features/manifests/validate",
    "/features/registry/sync",
    "/features/registry/sync:preview",
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

    catalog = schema["paths"]["/features/manifests/catalog"]["get"]
    assert catalog["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/ManifestCatalogResponse"
    )

    sync = schema["paths"]["/features/registry/sync"]["post"]
    sync_request = sync["requestBody"]["content"]["application/json"]["schema"]
    assert sync_request["$ref"].endswith("/RegistrySyncRequest")

    preview = schema["paths"]["/features/registry/sync:preview"]["post"]
    preview_response = preview["responses"]["200"]["content"]["application/json"]["schema"]
    assert preview_response["$ref"].endswith("/RegistrySyncPreviewResponse")

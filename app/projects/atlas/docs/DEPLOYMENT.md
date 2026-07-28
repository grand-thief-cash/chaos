# Atlas deployment

Atlas follows the same dependency-cached base-image and lightweight
application-image layout as Artemis.

## Automated deployment

From the repository root:

```bash
export CHAOS_DEPLOY_PASSWORD='...'
python deploy/scripts/deploy_atlas.py
```

Optional variables:

```text
CHAOS_DEPLOY_HOST       Remote Docker host; default 192.168.31.72.
CHAOS_DEPLOY_USER       Remote SSH user; default machine.
ATLAS_UPLOAD_CONFIG     Set to 1 to upload local production configuration.
OLLAMA_API_KEY          Passed to the Atlas container.
PDF_MODEL_API_KEY       Passed to the PDF extraction endpoint adapter.
DEEPSEEK_API_KEY        Reserved for a paid provider configuration.
```

The script reads the image version from `app/projects/atlas/CHANGELOG`, hashes
`requirements.txt` for the base-image tag, uploads only the Atlas package and
Docker inputs, builds both images when needed, starts the versioned Compose
service, and waits for the container health check.

The first deployment initializes the remote configuration. Later deployments
do not overwrite it unless `ATLAS_UPLOAD_CONFIG=1`; this protects semantic YAML
versions reviewed and published inside the persistent configuration volume.

## Build the base image

Run from `app/projects/atlas` so `requirements.txt` is the Docker build context:

```bash
docker build \
  -f ../../../deploy/docker/dockerfile/Dockerfile-atlas-base \
  -t atlas-base:latest \
  .
```

## Build the service image

Run from `app/projects/atlas` so the `atlas/` package is the Docker build context:

```bash
docker build \
  -f ../../../deploy/docker/dockerfile/Dockerfile-atlas \
  --build-arg BASE_TAG=latest \
  -t atlas:v1.0.0 \
  .
```

## Runtime configuration

Place the production configuration and published semantic YAML files under:

```text
/home/machine/data_volume/atlas/config/
├── config.yaml
├── report_prompt_mapping.yaml
└── semantic/
    └── atlas-semantic-vNNNN.yaml
```

The production configuration must point to externally managed phoenixA, MinIO,
the PDF-capable extraction endpoint, and the Ollama agent endpoint. Atlas does
not receive PostgreSQL or Neo4j credentials.

Ollama's OpenAI-compatible endpoint is used for structured text agents
(discovery aggregation, entity coreference/reranking, crosswalk, query, and
company review). It is not treated as a direct-PDF endpoint. Whole-PDF
extraction uses the separately configured `openai_compatible_pdf` endpoint.

Published semantic YAML is immutable. Creating a YAML file does not
automatically activate it: update `engine.knowledge_engine.semantic_config_path`
in the deployed `config.yaml`, then restart Atlas.

Start the service:

```bash
docker compose \
  -f deploy/docker/docker-compose/atlas.yaml \
  up -d
```

from dataclasses import dataclass, field
from pathlib import Path

from atlas.application.extraction_orchestrator import ExtractionOrchestrator
from atlas.application.crosswalk_orchestrator import CrosswalkOrchestrator
from atlas.application.crosswalk_service import CrosswalkSchemeService
from atlas.application.free_extraction_runner import FreeExtractionRunner
from atlas.application.knowledge_production_orchestrator import (
    KnowledgeProductionOrchestrator,
)
from atlas.application.semantic_discovery_service import SemanticDiscoveryService
from atlas.application.report_consumer import ReportConsumer
from atlas.core.clients import (
    CronjobCallbackClient,
    MinIOPDFReader,
    OllamaChatClient,
    OpenAICompatibleTextPDFClient,
    OpenAICompatiblePDFClient,
    OpenRouterTextPDFClient,
    PhoenixAClient,
    ZhipuTextPDFClient,
    build_structured_chat_client,
)
from atlas.core.llm import FailoverLLMClient, KeyPool
from atlas.core.sample_task_registry import SampleTaskRegistry
from atlas.intelligence import (
    CompanyReviewAgent,
    PhoenixAQueryToolbox,
    QueryOrchestrator,
    StructuredQueryModelAdapter,
)
from atlas.knowledge_production.extractor import (
    FreeExtractionExtractor,
    FreeExtractionPromptBuilder,
    PromptBuilder,
    WholePDFExtractor,
)
from atlas.knowledge_production.entity_resolver import (
    EntityResolutionService,
    StructuredEntityCandidateReranker,
    StructuredEntityClusterer,
)
from atlas.knowledge_production.entity_resolver.phoenixa_candidates import (
    PhoenixAEntityCandidateSource,
)
from atlas.knowledge_production.industry_crosswalk import StructuredCrosswalkModelAdapter
from atlas.knowledge_production.ontology_discovery import (
    FreeDiscoverySummariser,
    FreeFieldReviewSummariser,
    SemanticRegistry,
)
from atlas.knowledge_production.pdf_preprocessor import (
    HTTPLayoutParserSidecar,
    PikePDFUnlocker,
    RapidOCRLayoutParser,
)
from atlas.models import Config, LLMModelCfg, ModelProvider


@dataclass(slots=True)
class AtlasRuntime:
    config: Config
    phoenixa: PhoenixAClient
    semantic_registry: SemanticRegistry
    extraction_orchestrator: ExtractionOrchestrator
    knowledge_production_orchestrator: KnowledgeProductionOrchestrator
    report_consumer: ReportConsumer
    sample_task_registry: SampleTaskRegistry = field(default_factory=SampleTaskRegistry)
    cronjob_callback: CronjobCallbackClient | None = None
    discovery_orchestrator: object | None = None
    crosswalk_service: object | None = None
    query_orchestrator: object | None = None
    company_review_agent: object | None = None
    layout_parser_sidecar: object | None = None
    sampling_llm_harnesses: dict[str, object] = field(default_factory=dict)


def _build_key_pool(
    model_name: str,
    model_cfg: LLMModelCfg,
    cache: dict[str, KeyPool],
    total_concurrency: int,
) -> KeyPool:
    """One KeyPool per model name so roles sharing a model share one pool."""
    pool = cache.get(model_name)
    if pool is None:
        pool = KeyPool(model_cfg.api_keys, total_concurrency=total_concurrency)
        cache[model_name] = pool
    return pool


def _build_model_client(
    model_name: str,
    model_cfg: LLMModelCfg,
    key_pools: dict[str, KeyPool],
    total_concurrency: int,
):
    pool = _build_key_pool(model_name, model_cfg, key_pools, total_concurrency)
    if model_cfg.provider == ModelProvider.ZHIPU_TEXT:
        return ZhipuTextPDFClient(model_cfg, pool)
    if model_cfg.provider == ModelProvider.OLLAMA:
        return OllamaChatClient(model_cfg, pool)
    if model_cfg.capabilities.pdf_direct and not model_cfg.capabilities.text_extraction:
        return OpenAICompatiblePDFClient(model_cfg, pool)
    if model_cfg.provider in {
        ModelProvider.NVIDIA_NIM,
        ModelProvider.OPENAI_COMPATIBLE,
    }:
        return OpenAICompatibleTextPDFClient(model_cfg, pool)
    return OpenRouterTextPDFClient(model_cfg, pool)


def _build_stage_harness(
    stage: str,
    config: Config,
    key_pools: dict[str, KeyPool],
    client_cache: dict[str, object],
):
    harness_cfg = config.llm.harness_for_stage(stage)
    if harness_cfg is None:
        return None
    clients: list[tuple[str, object]] = []
    for model_name in harness_cfg.models:
        client = client_cache.get(model_name)
        if client is None:
            client = _build_model_client(
                model_name,
                config.llm.models[model_name],
                key_pools,
                config.engine.knowledge_engine.llm_concurrency,
            )
            client_cache[model_name] = client
        clients.append((model_name, client))
    return FailoverLLMClient(clients, harness_cfg)


def build_runtime(config: Config) -> AtlasRuntime:
    http = config.http_client
    knowledge = config.engine.knowledge_engine
    phoenixa = PhoenixAClient(
        config.dept_services.phoenixA.base_url,
        research_report_source=knowledge.research_report_source,
        timeout_seconds=http.timeout_seconds,
        verify_ssl=http.verify_ssl,
        headers=http.headers,
    )
    catalog_service = config.dept_services.sampling_catalog_phoenixA
    sampling_catalog = (
        PhoenixAClient(
            catalog_service.base_url,
            research_report_source=knowledge.research_report_source,
            timeout_seconds=http.timeout_seconds,
            verify_ssl=http.verify_ssl,
            headers=http.headers,
        )
        if catalog_service is not None
        else phoenixa
    )
    endpoint_cfg, source_bucket = config.minio.resolve_bucket(config.minio.source_bucket)
    minio = MinIOPDFReader(
        endpoint_cfg.endpoint,
        endpoint_cfg.access_key,
        endpoint_cfg.secret_key,
        source_bucket,
        secure=endpoint_cfg.secure,
    )
    sampling_endpoint_cfg, sampling_source_bucket = config.minio.resolve_sampling_bucket()
    sampling_minio = MinIOPDFReader(
        sampling_endpoint_cfg.endpoint,
        sampling_endpoint_cfg.access_key,
        sampling_endpoint_cfg.secret_key,
        sampling_source_bucket,
        secure=sampling_endpoint_cfg.secure,
    )

    key_pools: dict[str, KeyPool] = {}
    model_clients: dict[str, object] = {}
    extraction_name, extraction_model = config.llm.model_for_role("extraction")
    llm = _build_model_client(
        extraction_name, extraction_model, key_pools, knowledge.llm_concurrency
    )
    model_clients[extraction_name] = llm
    extractor = WholePDFExtractor(
        llm,
        prompt_builder=PromptBuilder(knowledge.prompt_mapping_path),
        maximum_total_attempts=knowledge.maximum_total_attempts,
    )
    orchestrator = ExtractionOrchestrator(
        reader=minio,
        store=phoenixa,
        extractor=extractor,
        unlocker=PikePDFUnlocker(),
        pipeline_version=knowledge.pipeline_version,
    )
    agent_name, agent_model = config.llm.model_for_role("agent")
    agent_pool = _build_key_pool(
        agent_name, agent_model, key_pools, knowledge.llm_concurrency
    )
    agent_client = build_structured_chat_client(agent_model, agent_pool)
    query_orchestrator = QueryOrchestrator(
        StructuredQueryModelAdapter(agent_client),
        PhoenixAQueryToolbox(phoenixa),
    )
    semantic_registry = SemanticRegistry(knowledge.semantic_config_path)
    crosswalk_service = CrosswalkSchemeService(
        config.taxonomy,
        phoenixa,
        phoenixa,
        CrosswalkOrchestrator(StructuredCrosswalkModelAdapter(agent_client)),
        semantic_registry,
        semantic_directory=Path(knowledge.semantic_config_path).parent,
    )
    cronjob_callback = CronjobCallbackClient(config.dept_services.cronjob.base_url)
    layout_sidecar = None
    if knowledge.sampling_layout_sidecar_url:
        layout_sidecar = HTTPLayoutParserSidecar(knowledge.sampling_layout_sidecar_url)
    elif knowledge.sampling_local_ocr_enabled:
        layout_sidecar = RapidOCRLayoutParser(
            dpi=knowledge.sampling_local_ocr_dpi,
            maximum_pages=knowledge.sampling_local_ocr_maximum_pages,
        )
    sampling_extraction_harness = _build_stage_harness(
        "sampling_extraction", config, key_pools, model_clients
    )
    sampling_review_harness = _build_stage_harness(
        "sampling_review", config, key_pools, model_clients
    )
    sampling_llm = sampling_extraction_harness or llm
    reviewer_llm = sampling_review_harness or sampling_llm
    free_extractor = FreeExtractionExtractor(
        sampling_llm,
        prompt_builder=FreeExtractionPromptBuilder(knowledge.prompt_mapping_path),
        # Free-extraction has no strict validator; give it its own retry budget
        # (at least 2) so a single flaky OpenRouter response doesn't fail a doc.
        maximum_total_attempts=max(2, knowledge.maximum_total_attempts),
        # Each provider applies its own configured default. A harness must not
        # force the primary model's thinking mode onto fallback providers.
        thinking_mode=None if sampling_extraction_harness else extraction_model.thinking_mode,
        chunk_output_tokens=knowledge.sampling_chunk_output_tokens,
        merge_output_tokens=knowledge.sampling_merge_output_tokens,
        maximum_chunks=knowledge.sampling_maximum_chunks,
        prompt_reserve_tokens=knowledge.sampling_prompt_reserve_tokens,
        layout_sidecar=layout_sidecar,
    )
    free_runner = FreeExtractionRunner(
        # Sampling may read a larger production corpus through a dedicated
        # read-only identity while all results remain in the development
        # PhoenixA database. No MinIO writer is constructed for this path.
        reader=sampling_minio,
        store=phoenixa,
        extractor=free_extractor,
        unlocker=PikePDFUnlocker(),
        pipeline_version=knowledge.pipeline_version,
    )
    # Predicate/concept induction is a separate, expensive pass. Field
    # discovery and support counting do not depend on it, so keep it opt-in for
    # resource-constrained sampling runs.
    free_summariser = FreeDiscoverySummariser(
        agent_client if knowledge.sampling_enable_semantic_summarizer else None
    )
    free_field_reviewer = FreeFieldReviewSummariser(
        reviewer_llm if callable(getattr(reviewer_llm, "complete_text", None)) else None,
        batch_size=knowledge.sampling_field_review_batch_size,
        output_tokens=knowledge.sampling_field_review_output_tokens,
    )
    discovery_service = SemanticDiscoveryService(
        phoenixa,
        orchestrator,
        semantic_registry,
        semantic_directory=Path(knowledge.semantic_config_path).parent,
        sample_catalog=sampling_catalog,
        agent_client=agent_client,
        cronjob_callback=cronjob_callback,
        free_runner=free_runner,
        free_summariser=free_summariser,
        free_field_reviewer=free_field_reviewer,
        document_concurrency=knowledge.llm_concurrency,
        minimum_success_ratio=knowledge.sampling_minimum_success_ratio,
    )
    knowledge_production = KnowledgeProductionOrchestrator(
        orchestrator,
        EntityResolutionService(
            PhoenixAEntityCandidateSource(phoenixa),
            StructuredEntityCandidateReranker(agent_client),
        ),
        phoenixa,
        StructuredEntityClusterer(agent_client),
    )
    report_consumer = ReportConsumer(
        phoenixa, knowledge_production, semantic_registry
    )
    return AtlasRuntime(
        config=config,
        phoenixa=phoenixa,
        semantic_registry=semantic_registry,
        extraction_orchestrator=orchestrator,
        knowledge_production_orchestrator=knowledge_production,
        report_consumer=report_consumer,
        sample_task_registry=SampleTaskRegistry(),
        cronjob_callback=cronjob_callback,
        crosswalk_service=crosswalk_service,
        query_orchestrator=query_orchestrator,
        company_review_agent=CompanyReviewAgent(query_orchestrator),
        layout_parser_sidecar=layout_sidecar,
        sampling_llm_harnesses={
            name: harness
            for name, harness in {
                "sampling_extraction": sampling_extraction_harness,
                "sampling_review": sampling_review_harness,
            }.items()
            if harness is not None
        },
        discovery_orchestrator=discovery_service,
    )

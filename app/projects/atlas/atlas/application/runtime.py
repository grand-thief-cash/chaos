from dataclasses import dataclass
from pathlib import Path

from atlas.application.extraction_orchestrator import ExtractionOrchestrator
from atlas.application.crosswalk_orchestrator import CrosswalkOrchestrator
from atlas.application.crosswalk_service import CrosswalkSchemeService
from atlas.application.knowledge_production_orchestrator import (
    KnowledgeProductionOrchestrator,
)
from atlas.application.semantic_discovery_service import SemanticDiscoveryService
from atlas.application.report_consumer import ReportConsumer
from atlas.core.clients import (
    MinIOPDFReader,
    OpenAICompatiblePDFClient,
    PhoenixAClient,
    build_structured_chat_client,
)
from atlas.intelligence import (
    CompanyReviewAgent,
    PhoenixAQueryToolbox,
    QueryOrchestrator,
    StructuredQueryModelAdapter,
)
from atlas.knowledge_production.extractor import PromptBuilder, WholePDFExtractor
from atlas.knowledge_production.entity_resolver import (
    EntityResolutionService,
    StructuredEntityCandidateReranker,
    StructuredEntityClusterer,
)
from atlas.knowledge_production.entity_resolver.phoenixa_candidates import (
    PhoenixAEntityCandidateSource,
)
from atlas.knowledge_production.industry_crosswalk import StructuredCrosswalkModelAdapter
from atlas.knowledge_production.ontology_discovery import SemanticRegistry
from atlas.knowledge_production.pdf_preprocessor import PikePDFUnlocker
from atlas.models import Config


@dataclass(slots=True)
class AtlasRuntime:
    config: Config
    phoenixa: PhoenixAClient
    semantic_registry: SemanticRegistry
    extraction_orchestrator: ExtractionOrchestrator
    knowledge_production_orchestrator: KnowledgeProductionOrchestrator
    report_consumer: ReportConsumer
    discovery_orchestrator: object | None = None
    crosswalk_service: object | None = None
    query_orchestrator: object | None = None
    company_review_agent: object | None = None


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
    minio = MinIOPDFReader(
        config.minio.endpoint,
        config.minio.access_key,
        config.minio.secret_key,
        config.minio.bucket,
        secure=config.minio.secure,
    )
    extraction_model = config.llm.extraction
    llm = OpenAICompatiblePDFClient(
        extraction_model.base_url,
        extraction_model.model,
        api_key=extraction_model.resolved_api_key,
        timeout_seconds=extraction_model.timeout_seconds,
        temperature=extraction_model.temperature,
        maximum_output_tokens=extraction_model.maximum_output_tokens,
    )
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
    agent_client = build_structured_chat_client(config.llm.agent)
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
    discovery_service = SemanticDiscoveryService(
        phoenixa,
        orchestrator,
        semantic_registry,
        semantic_directory=Path(knowledge.semantic_config_path).parent,
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
        crosswalk_service=crosswalk_service,
        query_orchestrator=query_orchestrator,
        company_review_agent=CompanyReviewAgent(query_orchestrator),
        discovery_orchestrator=discovery_service,
    )

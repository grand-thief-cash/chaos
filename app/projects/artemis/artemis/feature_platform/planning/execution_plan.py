from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Callable, Iterable

from artemis.feature_platform.domain.errors import FeaturePlatformError
from artemis.feature_platform.domain.models import FeatureReference, RegistryFeatureVersion
from artemis.feature_platform.planning.cycle_detector import detect_cycle
from artemis.feature_platform.planning.graph import DependencyGraph


@dataclass(frozen=True)
class PlanNode:
    registry_version: RegistryFeatureVersion
    feature_dependency_ids: tuple[int, ...]
    data_field_dependencies: tuple[dict, ...]

    @property
    def id(self) -> int:
        return self.registry_version.id

    @property
    def identity(self) -> str:
        return f"{self.registry_version.feature_code}@{self.registry_version.version_number}"


@dataclass(frozen=True)
class ExecutionPlan:
    root_version_ids: tuple[int, ...]
    ordered_nodes: tuple[PlanNode, ...]
    plan_checksum: str
    unsupported_nodes: tuple[str, ...] = ()

    @property
    def feature_version_ids(self) -> list[int]:
        return [node.id for node in self.ordered_nodes]

    @property
    def nodes_by_id(self) -> dict[int, PlanNode]:
        return {node.id: node for node in self.ordered_nodes}

    @property
    def data_field_dependencies(self) -> list[dict]:
        result: list[dict] = []
        for node in self.ordered_nodes:
            result.extend(node.data_field_dependencies)
        return result

    def ensure_executable(self) -> None:
        if self.unsupported_nodes:
            raise FeaturePlatformError(
                "UNSUPPORTED_IMPLEMENTATION",
                "execution plan contains unsupported nodes: " + ", ".join(self.unsupported_nodes),
                status_code=422,
            )

    def summary(self) -> dict:
        return {
            "root_feature_version_ids": list(self.root_version_ids),
            "ordered_nodes": [node.identity for node in self.ordered_nodes],
            "feature_version_ids": self.feature_version_ids,
            "data_field_dependency_count": len(self.data_field_dependencies),
            "plan_checksum": self.plan_checksum,
            "unsupported_nodes": list(self.unsupported_nodes),
        }


class DependencyPlanner:
    def __init__(self, resolver: Callable[[str, int], RegistryFeatureVersion]) -> None:
        self.resolver = resolver

    def build(self, roots: Iterable[FeatureReference]) -> ExecutionPlan:
        root_refs = list(roots)
        if not root_refs:
            raise FeaturePlatformError(
                "FEATURE_REFERENCE_REQUIRED",
                "at least one root feature is required",
                status_code=400,
            )

        graph = DependencyGraph()
        versions: dict[int, RegistryFeatureVersion] = {}
        references: dict[tuple[str, int], int] = {}
        data_dependencies: dict[int, list[dict]] = {}
        unsupported: set[str] = set()

        def resolve(code: str, number: int) -> RegistryFeatureVersion:
            key = (code, number)
            if key in references:
                return versions[references[key]]
            version = self.resolver(code, number)
            if version.status != "published":
                raise FeaturePlatformError(
                    "FEATURE_VERSION_NOT_PUBLISHED",
                    f"feature version {code}@{number} is {version.status or 'unknown'}",
                    status_code=422,
                )
            existing = versions.get(version.id)
            if existing and (
                existing.feature_code != code or existing.version_number != number
            ):
                raise FeaturePlatformError(
                    "REGISTRY_IDENTITY_CONFLICT",
                    f"feature version id {version.id} resolves to multiple identities",
                    status_code=409,
                )
            versions[version.id] = version
            references[key] = version.id
            graph.add_node(version.id)

            implementation = version.implementation
            if (
                implementation.get("kind") != "python"
                or implementation.get("status") != "active"
                or implementation.get("is_canonical") is not True
            ):
                unsupported.add(f"{code}@{number}")

            node_fields: list[dict] = []
            for dependency in version.dependencies:
                kind = dependency.get("dependency_kind")
                snapshot = version.dependency_snapshot(dependency)
                if kind == "feature":
                    upstream_code = str(snapshot.get("feature_code", ""))
                    upstream_number = int(snapshot.get("feature_version", 0) or 0)
                    if not upstream_code or upstream_number <= 0:
                        raise FeaturePlatformError(
                            "DEPENDENCY_REFERENCE_INVALID",
                            f"registry dependency for {code}@{number} lacks an exact feature reference",
                            status_code=422,
                        )
                    upstream = resolve(upstream_code, upstream_number)
                    frozen_id = dependency.get("depends_on_feature_version_id")
                    if frozen_id is None or int(frozen_id) != upstream.id:
                        raise FeaturePlatformError(
                            "DEPENDENCY_IDENTITY_CONFLICT",
                            (
                                f"registry dependency {code}@{number} -> "
                                f"{upstream_code}@{upstream_number} does not match its frozen version id"
                            ),
                            status_code=409,
                        )
                    graph.add_dependency(version.id, upstream.id)
                elif kind == "data_field":
                    required = ("source", "dataset", "data_type", "raw_field", "contract_version")
                    if any(not snapshot.get(field) for field in required):
                        raise FeaturePlatformError(
                            "DATA_FIELD_DEPENDENCY_INVALID",
                            f"registry data field dependency for {code}@{number} is incomplete",
                            status_code=422,
                        )
                    if dependency.get("data_field_dictionary_id") is None:
                        raise FeaturePlatformError(
                            "DATA_FIELD_NOT_FOUND",
                            f"registry data field dependency for {code}@{number} is unresolved",
                            status_code=422,
                        )
                    node_fields.append(snapshot)
                else:
                    raise FeaturePlatformError(
                        "DEPENDENCY_KIND_INVALID",
                        f"registry dependency for {code}@{number} has invalid kind {kind!r}",
                        status_code=422,
                    )
            data_dependencies[version.id] = node_fields
            return version

        roots_resolved = [resolve(reference.code, reference.version) for reference in root_refs]
        cycle = detect_cycle(graph.edges)
        if cycle:
            labels = [
                f"{versions[node].feature_code}@{versions[node].version_number}"
                for node in cycle
            ]
            raise FeaturePlatformError(
                "DEPENDENCY_CYCLE",
                "feature dependency cycle detected: " + " -> ".join(labels),
                status_code=422,
            )

        ordered_ids: list[int] = []
        visited: set[int] = set()

        def order(node_id: int) -> None:
            if node_id in visited:
                return
            for upstream_id in sorted(graph.edges.get(node_id, set())):
                order(upstream_id)
            visited.add(node_id)
            ordered_ids.append(node_id)

        for root in sorted(roots_resolved, key=lambda item: item.id):
            order(root.id)

        nodes = tuple(
            PlanNode(
                registry_version=versions[node_id],
                feature_dependency_ids=tuple(sorted(graph.edges.get(node_id, set()))),
                data_field_dependencies=tuple(data_dependencies.get(node_id, [])),
            )
            for node_id in ordered_ids
        )
        checksum_payload = {
            "root_feature_version_ids": sorted(root.id for root in roots_resolved),
            "nodes": [
                {
                    "feature_version_id": node.id,
                    "feature_dependencies": list(node.feature_dependency_ids),
                    "data_field_dependencies": sorted(
                        node.data_field_dependencies,
                        key=lambda item: (
                            item["source"],
                            item["dataset"],
                            item["data_type"],
                            item["raw_field"],
                            item["contract_version"],
                        ),
                    ),
                }
                for node in nodes
            ],
        }
        canonical = json.dumps(
            checksum_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        checksum = hashlib.sha256(canonical).hexdigest()
        return ExecutionPlan(
            root_version_ids=tuple(sorted(root.id for root in roots_resolved)),
            ordered_nodes=nodes,
            plan_checksum=checksum,
            unsupported_nodes=tuple(sorted(unsupported)),
        )

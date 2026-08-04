export interface Delta {
  columnsAdded: { name: string; dtype: string }[];
  columnsRemoved: { name: string; dtype: string }[];
  rowCountBefore: number;
  rowCountAfter: number;
  summary: string;
}

export interface ArtifactRefJson {
  artifactId: string;
  artifactName: string;
  granularity: string;
  detail: string | null;
}

export interface TagJson {
  name: string;
  color: string;
}

export interface AnnotationJson {
  annotationId: string;
  title: string;
  note: string;
  tags: TagJson[];
  artifacts: ArtifactRefJson[];
  author: { agent_id: string; agent_type: string; display_name: string };
  timestamp: string;
}

export interface OperationJson {
  operationId: string;
  name: string;
  operationType: string;
  commandName: string;
  category: string;
}

export interface ProvenanceNodeJson {
  stateId: string;
  parentStateId: string | null;
  branchId: string;
  operation: OperationJson;
  params: Record<string, unknown>;
  delta: Delta;
  annotations: AnnotationJson[];
}

export interface ProvenanceTreeJson {
  rootId: string;
  branches: Record<string, string>;
  nodes: Record<string, ProvenanceNodeJson>;
}

export const CATEGORY_COLOR: Record<string, string> = {
  CLEANING: "#0EA5E9",
  FEATURE_ENGINEERING: "#10B981",
  ANALYSIS: "#F59E0B",
  COMPARISON: "#F43F5E",
  DATA_LOADING: "#8B5CF6",
  AGGREGATION: "#8B5CF6",
};

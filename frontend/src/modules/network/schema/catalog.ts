import raw from '@catalog/components.json';
import type { NodeType, PortKind } from '@/modules/network/model/document';

/**
 * The component catalog (resources/catalog/components.json): one source for node types,
 * fields, ports and rules. The editor takes initial node data and ports from it; the backend
 * its port check; the architect its knowledge. Backend tests keep it in step with the code.
 */
export type CatalogField = {
  key: string;
  type: string;
  description: string;
  /** Value a new node starts with. */
  initial?: unknown;
  /** Value the backend uses while the field is unset. */
  default?: unknown;
  min?: number;
  max?: number;
  values?: string[];
  required?: boolean;
  advanced?: boolean;
  /** Tool node fields: the kinds they belong to. */
  kinds?: string[];
};

export type CatalogPort = {
  id: string;
  kind: PortKind;
  direction: 'in' | 'out';
  required?: boolean;
};

export type CatalogNodeType = {
  type: NodeType;
  label: string;
  purpose: string;
  use: string;
  fields: CatalogField[];
  ports: CatalogPort[];
  /** Outputs that depend on the graph (orchestrator channels, router branches). */
  dynamicOut?: string;
  rules: string[];
  tips: string[];
};

export type ComponentCatalog = {
  catalogVersion: number;
  nodeTypes: CatalogNodeType[];
  toolKinds: { kind: string; label: string; purpose: string; risk?: string }[];
  errors: Record<string, string>;
};

export const COMPONENTS = raw as unknown as ComponentCatalog;

const BY_TYPE = new Map(COMPONENTS.nodeTypes.map((spec) => [spec.type, spec]));

export function nodeSpec(type: NodeType): CatalogNodeType {
  const spec = BY_TYPE.get(type);
  if (!spec) throw new Error(`component catalog has no node type ${type}`);
  return spec;
}

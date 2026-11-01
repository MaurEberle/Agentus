export type ModelKind = 'embedding' | 'image' | 'moe' | 'normal';

export type InstalledModel = {
  name: string;
  sizeBytes?: number;
  digest?: string;
  modifiedAt?: string;
  family?: string;
  parameterSize?: string;
  quantization?: string;
  format?: string;
  architecture?: string;
  contextLength?: number;
  embeddingLength?: number;
  blockCount?: number;
  expertCount?: number;
  capabilities: string[];
  kind: ModelKind | string;
  vision: boolean;
  tools: boolean;
  thinking: boolean;
  hasTemplate: boolean;
  license?: string;
  licenseClipped?: boolean;
  hfUrl?: string;
  loaded: boolean;
  vramBytes?: number;
  tags: string[];
};

export type HubHit = {
  id: string;
  pipeline?: string;
  downloads: number;
  likes: number;
  url: string;
  tools: boolean;
  thinking: boolean;
  vision: boolean;
  moe: boolean;
};

export type QuantFile = {
  quant: string;
  filename: string;
  sizeBytes?: number;
  tag: string;
  installed: boolean;
};

export type HubFiles = {
  id: string;
  url: string;
  author?: string;
  pipeline?: string;
  downloads: number;
  likes: number;
  updatedAt?: string;
  repoBytes?: number;
  architecture?: string;
  parameters?: string;
  contextLength?: number;
  license?: string;
  licenseUrl?: string;
  baseModel?: string;
  baseUrl?: string;
  languages: string[];
  hasTemplate: boolean;
  tools: boolean;
  thinking: boolean;
  vision: boolean;
  moe: boolean;
  installable: boolean;
  reason?: string;
  quants: QuantFile[];
  messageKey?: string;
};

export type DownloadStatus = 'queued' | 'running' | 'paused' | 'stopped' | 'done' | 'error';

export type DownloadJob = {
  id: string;
  model: string;
  label: string;
  publisher?: string;
  sizeBytes?: number;
  status: DownloadStatus;
  errorKey?: string;
  completed?: number;
  total?: number;
  rateBps?: number;
};

export type DownloadList = {
  paused: boolean;
  items: DownloadJob[];
};

export type PullEvent = {
  status: string;
  completed?: number;
  total?: number;
  messageKey?: string;
};

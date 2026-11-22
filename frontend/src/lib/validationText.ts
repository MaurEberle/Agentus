/**
 * Backend graph validation keys (`graph.*`) mapped to the editor's texts under
 * `network.validation.*`. Keys not listed here (`graph.mcp.*`, `graph.router.*`) have
 * their own translation and are used as they are.
 */
export const GRAPH_ERROR_TEXT: Record<string, string> = {
  'graph.knowledge.path': 'network.validation.knowledgePath',
  'graph.knowledge.helpCorpus': 'network.validation.knowledgeHelpCorpus',
  'graph.knowledge.dataDir': 'network.validation.knowledgeDataDir',
  'graph.fileAccess.root': 'network.validation.fileAccessRoot',
  'graph.terminal.root': 'network.validation.terminalRoot',
  'graph.zip.root': 'network.validation.zipRoot',
  'graph.fileAccess.rootMissing': 'network.validation.fileAccessRootMissing',
  'graph.terminal.rootMissing': 'network.validation.terminalRootMissing',
  'graph.zip.rootMissing': 'network.validation.zipRootMissing',
  'graph.terminal.programs': 'network.validation.terminalPrograms',
  'graph.tool.maxCalls': 'network.validation.toolMaxCalls',
  'graph.llm.temperature': 'network.validation.llmTemperature',
  'graph.llm.maxTokens': 'network.validation.llmMaxTokens',
  'graph.llm.maxTokensContext': 'network.validation.llmMaxTokensContext',
  'graph.knowledge.topK': 'network.validation.knowledgeTopK',
  'graph.knowledge.score': 'network.validation.knowledgeScore',
  'graph.http.credentialUrl': 'network.validation.httpCredentialUrl',
  'graph.cycle': 'network.validation.cycle',
  'graph.agent.noLlm': 'network.validation.agentLlm',
  'graph.agent.noMessage': 'network.validation.agentMessage',
  'graph.llm.credential': 'network.validation.modelRequired',
  'graph.end.missing': 'network.validation.endRequired',
  'graph.chatInput.duplicate': 'network.validation.tooManyChatInputs',
  'graph.orchestrator.duplicate': 'network.validation.orchestratorDuplicate',
  'graph.orchestrator.noChat': 'network.validation.orchestratorChat',
  'graph.orchestrator.fanout': 'network.validation.orchestratorFanout',
  'graph.orchestrator.noEnd': 'network.validation.orchestratorEnd',
  'graph.orchestrator.noLlm': 'network.validation.orchestratorLlm',
  'graph.orchestrator.looseAgent': 'network.validation.orchestratorLooseAgent',
  'graph.orchestrator.noAgents': 'network.validation.orchestratorAgents',
  'graph.chain.noEnd': 'network.validation.chainEnd',
  'graph.agent.mode': 'network.validation.agentMode',
  'graph.agent.channel': 'network.validation.agentChannel',
  'graph.edge.invalid': 'network.validation.edgeType',
};

/** The i18n key that explains a backend validation error. */
export function validationTextKey(messageKey: string): string {
  return GRAPH_ERROR_TEXT[messageKey] ?? messageKey;
}

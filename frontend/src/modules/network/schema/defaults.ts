import type { GraphNode, NodeType } from '@/modules/network/model/document';
import { newId, snapPosition } from '@/modules/network/model/document';

export function defaultData(type: NodeType): Record<string, unknown> {
  switch (type) {
    case 'chat_input':
      return { displayName: '', placeholder: '', startMessage: '', requireInput: false };
    case 'llm':
      return { displayName: '', provider: 'ollama', model: 'llama3.2:1b' };
    case 'agent':
      return { displayName: '', systemPrompt: '' };
    case 'tool':
      return { displayName: '', kind: 'datetime' };
    case 'knowledge':
      return { displayName: '', sourcePath: '', topK: 5 };
    case 'router':
      return {
        displayName: '',
        branches: [{ id: newId('br'), name: 'A', condition: '' }],
      };
    case 'end':
      return { displayName: '' };
  }
}

export function createNode(type: NodeType, position: { x: number; y: number }, snap: boolean): GraphNode {
  return {
    id: newId(type),
    type,
    position: snapPosition(position, snap),
    data: defaultData(type),
  };
}

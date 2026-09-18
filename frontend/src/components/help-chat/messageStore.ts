import type { HelpMessage } from '@/components/help-chat/model';

export const helpMessageCache: HelpMessage[] = [];

export function clearHelpMessageCache() {
  helpMessageCache.splice(0, helpMessageCache.length);
}

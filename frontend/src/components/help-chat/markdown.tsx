import type { ReactNode } from 'react';

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
}

export function LightMarkdown({ text }: { text: string }) {
  const escaped = escapeHtml(text);
  const withCode = escaped.replace(/`([^`]+)`/g, '<code>$1</code>');
  const withBold = withCode.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  const lines = withBold.split('\n');
  const nodes: ReactNode[] = [];
  lines.forEach((line, index) => {
    nodes.push(
      <span key={`l-${index}`} dangerouslySetInnerHTML={{ __html: line || ' ' }} />,
    );
    if (index < lines.length - 1) nodes.push(<br key={`b-${index}`} />);
  });
  return <p className="whitespace-pre-wrap break-words text-sm leading-6">{nodes}</p>;
}

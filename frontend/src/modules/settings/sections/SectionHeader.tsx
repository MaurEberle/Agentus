export function SectionHeader({ title, description }: { title: string; description: string }) {
  return (
    <header className="mb-6 space-y-1">
      <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
      <p className="text-sm text-muted-foreground">{description}</p>
    </header>
  );
}

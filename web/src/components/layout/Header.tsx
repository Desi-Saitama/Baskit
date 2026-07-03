interface HeaderProps {
  title: string;
  subtitle: string;
  actions?: React.ReactNode;
}

export default function Header({ title, subtitle, actions }: HeaderProps) {
  return (
    <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between animate-fade-in">
      <div>
        <p className="font-mono text-xs uppercase tracking-[0.28em] text-orange-700">
          private self-hosted tracker
        </p>
        <h1 className="mt-2 text-3xl font-extrabold text-stone-900 md:text-5xl font-heading">
          {title}
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-stone-500 md:text-base">
          {subtitle}
        </p>
      </div>
      {actions && <div className="flex gap-2">{actions}</div>}
    </div>
  );
}

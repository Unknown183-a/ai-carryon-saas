export default function ComingSoon({
  title,
  reason,
}: {
  title: string;
  reason: string;
}) {
  return (
    <div className="max-w-3xl">
      <h1 className="font-display text-2xl font-semibold text-paper">{title}</h1>
      <div className="panel mt-6 border-dashed px-6 py-10 text-center">
        <p className="text-sm text-paper">Not wired up yet.</p>
        <p className="mx-auto mt-1.5 max-w-md text-sm text-slate">{reason}</p>
      </div>
    </div>
  );
}

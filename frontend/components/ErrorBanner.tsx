import { TriangleAlert } from "lucide-react";

export default function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="flex items-start gap-2.5 border border-contradict/30 bg-contradict-soft text-contradict rounded-lg px-4 py-3 text-sm">
      <TriangleAlert size={16} className="shrink-0 mt-0.5" />
      <p>{message}</p>
    </div>
  );
}

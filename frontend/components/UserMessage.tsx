export default function UserMessage({ content }: { content: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[80%] bg-ink text-paper-raised rounded-lg rounded-tr-sm px-4 py-2.5 text-[15px] leading-relaxed whitespace-pre-wrap">
        {content}
      </div>
    </div>
  );
}

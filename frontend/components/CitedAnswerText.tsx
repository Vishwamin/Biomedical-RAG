const CITATION_REGEX = /\[(\d+)\]/g;

export default function CitedAnswerText({
  text,
  validCitationNumbers,
  onCitationClick,
}: {
  text: string;
  validCitationNumbers: Set<number>;
  onCitationClick: (n: number) => void;
}) {
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;

  CITATION_REGEX.lastIndex = 0;
  while ((match = CITATION_REGEX.exec(text)) !== null) {
    const n = parseInt(match[1], 10);
    if (match.index > lastIndex) {
      parts.push(<span key={key++}>{text.slice(lastIndex, match.index)}</span>);
    }
    if (validCitationNumbers.has(n)) {
      parts.push(
        <button
          key={key++}
          onClick={() => onCitationClick(n)}
          className="font-data text-accent bg-accent-soft hover:bg-accent hover:text-paper-raised transition-colors rounded px-1 mx-0.5 text-[0.85em] align-middle"
        >
          [{n}]
        </button>
      );
    } else {
      parts.push(<span key={key++}>{match[0]}</span>);
    }
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) {
    parts.push(<span key={key++}>{text.slice(lastIndex)}</span>);
  }

  return <p className="text-[15px] leading-relaxed text-ink">{parts}</p>;
}

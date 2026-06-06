import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";

const components: Components = {
  table: ({ children }) => (
    <div className="my-4 overflow-x-auto rounded-2xl border border-[#ded8cc] bg-white shadow-sm">
      <table className="min-w-full border-collapse text-sm leading-6">
        {children}
      </table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="bg-[#ebe5da] text-left text-zinc-900">{children}</thead>
  ),
  th: ({ children }) => (
    <th className="whitespace-nowrap border-b border-[#ded8cc] px-4 py-3 font-bold">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="min-w-[11rem] border-b border-[#eee8dd] px-4 py-3 align-top text-zinc-700 last:border-b-0">
      {children}
    </td>
  ),
  p: ({ children }) => <p className="my-2 leading-7">{children}</p>,
  ul: ({ children }) => <ul className="my-3 list-disc space-y-1 pl-6">{children}</ul>,
  ol: ({ children }) => <ol className="my-3 list-decimal space-y-1 pl-6">{children}</ol>,
  li: ({ children }) => <li className="pl-1 leading-7">{children}</li>,
  strong: ({ children }) => <strong className="font-extrabold text-zinc-950">{children}</strong>,
};

export function MarkdownMessage({ content, compact = false }: { content: string; compact?: boolean }) {
  return (
    <div className={compact ? "text-sm text-zinc-700" : "text-base text-zinc-700"}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
}

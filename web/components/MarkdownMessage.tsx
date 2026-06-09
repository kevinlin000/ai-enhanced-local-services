import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";

const components: Components = {
  h1: ({ children }) => (
    <h1 className="mb-3 mt-4 text-3xl font-semibold leading-tight tracking-normal text-zinc-950">
      {children}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 className="mb-3 mt-5 text-2xl font-semibold leading-tight tracking-normal text-zinc-950">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="mb-2 mt-4 text-lg font-semibold leading-snug text-zinc-950">
      {children}
    </h3>
  ),
  table: ({ children }) => (
    <div className="my-4 overflow-x-auto rounded-3xl border border-[#ded8cc] bg-[#fffdfa] shadow-sm">
      <table className="min-w-full border-collapse text-sm leading-6">
        {children}
      </table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="bg-[#ebe5da] text-left text-zinc-950">{children}</thead>
  ),
  th: ({ children }) => (
    <th className="whitespace-nowrap border-b border-[#ded8cc] px-4 py-3 font-semibold">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="min-w-[11rem] border-b border-[#eee8dd] px-4 py-3 align-top text-zinc-700 last:border-b-0">
      {children}
    </td>
  ),
  p: ({ children }) => <p className="my-2 max-w-3xl leading-8">{children}</p>,
  ul: ({ children }) => <ul className="my-3 max-w-3xl list-disc space-y-1 pl-6">{children}</ul>,
  ol: ({ children }) => <ol className="my-3 max-w-3xl list-decimal space-y-1 pl-6">{children}</ol>,
  li: ({ children }) => <li className="pl-1 leading-8">{children}</li>,
  strong: ({ children }) => <strong className="font-semibold text-zinc-950">{children}</strong>,
  blockquote: ({ children }) => (
    <blockquote className="my-4 max-w-3xl rounded-3xl border border-[#e3dac8] bg-[#f3ecdd] px-5 py-4 text-zinc-700">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="my-5 border-[#ded8cc]" />,
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

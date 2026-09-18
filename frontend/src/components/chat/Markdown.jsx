import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import CodeBlock from "./CodeBlock";
import rehypeRaw from "rehype-raw";

const components = {
  pre: CodeBlock,

  a: ({ href, children, ...props }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      {...props}
    >
      {children}
    </a>
  ),

  table: ({ children, ...props }) => (
    <div className="my-4 w-full overflow-x-auto">
      <table {...props}>{children}</table>
    </div>
  ),
};

export default function Markdown({ content }) {
  return (
    <div className="markdown-body w-full min-w-0">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw, rehypeHighlight]}
        components={components}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
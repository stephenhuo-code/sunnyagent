import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { fixFileUrl, isValidFileUrl } from "../utils/url";

interface SafeMarkdownProps {
  children: string;
  /** Maximum content length to render (optional) */
  maxLength?: number;
}

/**
 * Safe link component that fixes URL prefixes and handles invalid URLs gracefully
 */
const SafeLink = ({
  href,
  children,
}: React.AnchorHTMLAttributes<HTMLAnchorElement> & { children?: React.ReactNode }) => {
  const fixedHref = fixFileUrl(href || "");

  // Check if it's a valid URL or mailto link
  if (!isValidFileUrl(fixedHref) && !fixedHref.startsWith("mailto:")) {
    // Invalid link - render as plain text with strikethrough style
    return <span className="invalid-link">{children}</span>;
  }

  const isFileDownload = fixedHref.startsWith("/api/files/");

  return (
    <a
      href={fixedHref}
      target={isFileDownload ? "_blank" : undefined}
      rel={isFileDownload ? "noopener noreferrer" : undefined}
    >
      {children}
    </a>
  );
};

/**
 * Safe image component with error handling
 */
const SafeImage = ({ src, alt }: { src?: string; alt?: string }) => (
  <img
    src={src}
    alt={alt || ""}
    style={{
      maxWidth: "100%",
      maxHeight: "400px",
      borderRadius: "8px",
      marginTop: "8px",
      display: "block",
    }}
    onError={(e) => {
      e.currentTarget.style.display = "none";
    }}
  />
);

/**
 * SafeMarkdown - A wrapper around react-markdown that handles:
 * - Fixing sandbox: URL prefixes
 * - Graceful handling of invalid links
 * - Image error handling
 */
export default function SafeMarkdown({ children, maxLength }: SafeMarkdownProps) {
  const content = maxLength ? children.slice(0, maxLength) : children;

  return (
    <Markdown
      remarkPlugins={[remarkGfm]}
      components={{
        a: SafeLink,
        img: SafeImage,
      }}
    >
      {content}
    </Markdown>
  );
}

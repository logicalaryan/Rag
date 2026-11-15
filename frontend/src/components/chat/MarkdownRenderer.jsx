import React from 'react';

/**
 * Lightweight, zero-dependency Markdown renderer for React.
 * Handles headings, bold, italic, inline code, code blocks, lists, links, and paragraphs.
 */
export function MarkdownRenderer({ content }) {
  if (!content) return null;

  // Split into code blocks vs non-code blocks
  const parts = content.split(/(```[\s\S]*?```)/g);

  return (
    <div className="markdown-content">
      {parts.map((part, index) => {
        if (!part) return null;

        // Code block
        if (part.startsWith('```') && part.endsWith('```')) {
          const lines = part.slice(3, -3).trim().split('\n');
          const language = lines[0].match(/^[a-zA-Z0-9_-]+$/) ? lines.shift() : '';
          const code = lines.join('\n');
          return (
            <div key={index} className="md-code-block">
              {language && <div className="md-code-lang">{language}</div>}
              <pre>
                <code>{code}</code>
              </pre>
            </div>
          );
        }

        // Standard text lines
        const lines = part.split('\n');
        const elements = [];
        let listItems = [];
        let inList = false;

        const flushList = (keyPrefix) => {
          if (listItems.length > 0) {
            elements.push(
              <ul key={`${keyPrefix}-list`} className="md-list">
                {listItems.map((item, idx) => (
                  <li key={idx}>{renderInline(item)}</li>
                ))}
              </ul>
            );
            listItems = [];
            inList = false;
          }
        };

        lines.forEach((line, lineIdx) => {
          const trimmed = line.trim();

          // Bullet lists: * or -
          const listMatch = line.match(/^\s*[-*]\s+(.*)$/);
          if (listMatch) {
            inList = true;
            listItems.push(listMatch[1]);
            return;
          }

          flushList(`flush-${lineIdx}`);

          // Empty line
          if (!trimmed) {
            return;
          }

          // Headers
          if (trimmed.startsWith('### ')) {
            elements.push(<h4 key={lineIdx} className="md-h4">{renderInline(trimmed.slice(4))}</h4>);
          } else if (trimmed.startsWith('## ')) {
            elements.push(<h3 key={lineIdx} className="md-h3">{renderInline(trimmed.slice(3))}</h3>);
          } else if (trimmed.startsWith('# ')) {
            elements.push(<h2 key={lineIdx} className="md-h2">{renderInline(trimmed.slice(2))}</h2>);
          } else {
            elements.push(<p key={lineIdx} className="md-p">{renderInline(line)}</p>);
          }
        });

        flushList(`final-${index}`);
        return <React.Fragment key={index}>{elements}</React.Fragment>;
      })}
    </div>
  );
}

/**
 * Parses inline elements: math ($math$), bold (**text**), italic (*text*), inline code (`code`), links ([text](url)).
 */
function renderInline(text) {
  if (!text) return '';

  // Tokenize regex: inline code, math ($...$), links, bold, italic
  const tokenRegex = /(`[^`]+`|\$[^$]+\$|\[[^\]]+\]\([^)]+\)|\*\*[^*]+\*\*|\*[^*]+\*)/g;
  const parts = text.split(tokenRegex);

  return parts.map((part, i) => {
    if (!part) return null;

    // Inline code
    if (part.startsWith('`') && part.endsWith('`') && part.length >= 2) {
      return (
        <code key={i} className="md-inline-code">
          {part.slice(1, -1)}
        </code>
      );
    }

    // Inline LaTeX math: $3 \times 3 = 9$ -> clean readable math
    if (part.startsWith('$') && part.endsWith('$') && part.length >= 2) {
      const cleanMath = part
        .slice(1, -1)
        .replace(/\\times/g, '×')
        .replace(/\\cdot/g, '·')
        .replace(/\\div/g, '÷')
        .replace(/\\pm/g, '±')
        .replace(/\\leq/g, '≤')
        .replace(/\\geq/g, '≥')
        .replace(/\\neq/g, '≠')
        .replace(/\\approx/g, '≈');
      return (
        <span key={i} className="md-math">
          {cleanMath}
        </span>
      );
    }

    // Link: [label](url)
    const linkMatch = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
    if (linkMatch) {
      return (
        <a key={i} href={linkMatch[2]} target="_blank" rel="noopener noreferrer" className="md-link">
          {linkMatch[1]}
        </a>
      );
    }

    // Bold: **text**
    if (part.startsWith('**') && part.endsWith('**') && part.length >= 4) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }

    // Italic: *text*
    if (part.startsWith('*') && part.endsWith('*') && part.length >= 2) {
      return <em key={i}>{part.slice(1, -1)}</em>;
    }

    return part;
  });
}

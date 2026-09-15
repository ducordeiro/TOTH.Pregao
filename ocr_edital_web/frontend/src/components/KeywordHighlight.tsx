import { Fragment, useMemo } from "react";
import { createKeywordHighlighter } from "../keywordHighlight";

export function KeywordHighlight({ text, terms }: { text: string; terms: readonly string[] }) {
  const highlight = useMemo(() => createKeywordHighlighter(terms), [terms]);
  return highlight(text).map((part, index) => part.highlighted
    ? <span className="search-keyword-hit" key={index}>{part.text}</span>
    : <Fragment key={index}>{part.text}</Fragment>);
}

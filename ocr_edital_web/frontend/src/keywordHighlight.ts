export interface HighlightPart {
  text: string;
  highlighted: boolean;
}

function fold(value: string) {
  return value.normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase();
}

// Keep the same singular/plural alternatives as etl/search_filters.py.
function variants(word: string) {
  const values = new Set([word]);
  if (word.length > 3) {
    for (const [ending, replacement] of [
      ["oes", "ao"], ["ais", "al"], ["eis", "el"], ["is", "il"], ["es", ""], ["s", ""],
    ]) {
      if (word.endsWith(ending)) values.add(word.slice(0, -ending.length) + replacement);
    }
    values.add(word + "s");
    if (/[rzn]$/.test(word)) values.add(word + "es");
    for (const [ending, replacement] of [["al", "ais"], ["el", "eis"], ["ao", "oes"]]) {
      if (word.endsWith(ending)) values.add(word.slice(0, -ending.length) + replacement);
    }
  }
  return values;
}

export function createKeywordHighlighter(terms: readonly string[]) {
  const phrases = terms.flatMap((term) => term.split(";"))
    .map((term) => (fold(term).match(/[a-z0-9]+/g) || []).map(variants))
    .filter((phrase) => phrase.length);

  return (text: string): HighlightPart[] => {
    if (!text || !phrases.length) return [{ text, highlighted: false }];
    const tokens = Array.from(text.matchAll(/[\p{L}\p{M}\p{N}]+/gu), (match) => ({
      value: fold(match[0]), start: match.index, end: match.index + match[0].length,
    }));
    const hits = new Set<number>();
    for (const phrase of phrases) {
      tokens.forEach((token, start) => {
        if (!phrase[0].has(token.value)) return;
        const matched = [start];
        let position = start;
        for (const alternatives of phrase.slice(1)) {
          let next = position + 1;
          while (next < tokens.length && next <= position + 3 && !alternatives.has(tokens[next].value)) next++;
          if (next >= tokens.length || next > position + 3) return;
          matched.push(next);
          position = next;
        }
        matched.forEach((index) => hits.add(index));
      });
    }
    const parts: HighlightPart[] = [];
    let cursor = 0;
    tokens.forEach((token, index) => {
      if (!hits.has(index)) return;
      if (cursor < token.start) parts.push({ text: text.slice(cursor, token.start), highlighted: false });
      parts.push({ text: text.slice(token.start, token.end), highlighted: true });
      cursor = token.end;
    });
    if (cursor < text.length) parts.push({ text: text.slice(cursor), highlighted: false });
    return parts;
  };
}

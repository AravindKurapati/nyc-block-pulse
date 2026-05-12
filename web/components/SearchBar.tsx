"use client";

import { useEffect, useRef, useState } from "react";

import { searchAddresses } from "@/lib/api";
import type { SearchResult } from "@/lib/types";

type SearchBarProps = {
  onSelect: (result: SearchResult) => void;
};

export default function SearchBar({ onSelect }: SearchBarProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const skipNextSearchRef = useRef(false);

  useEffect(() => {
    const trimmed = query.trim();
    abortRef.current?.abort();

    if (skipNextSearchRef.current) {
      skipNextSearchRef.current = false;
      setResults([]);
      setError(null);
      setIsLoading(false);
      return;
    }

    if (trimmed.length < 2) {
      setResults([]);
      setError(null);
      setIsLoading(false);
      return;
    }

    const controller = new AbortController();
    abortRef.current = controller;
    const timeout = window.setTimeout(() => {
      setIsLoading(true);
      setError(null);
      searchAddresses(trimmed, controller.signal)
        .then((items) => setResults(items.slice(0, 5)))
        .catch((err: unknown) => {
          if (err instanceof DOMException && err.name === "AbortError") {
            return;
          }
          setError(err instanceof Error ? err.message : "Search failed.");
          setResults([]);
        })
        .finally(() => {
          if (!controller.signal.aborted) {
            setIsLoading(false);
          }
        });
    }, 250);

    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [query]);

  const showMenu =
    query.trim().length >= 2 && (results.length > 0 || isLoading || error);

  return (
    <div className="relative w-full max-w-xl">
      <label className="sr-only" htmlFor="address-search">
        Search address or intersection
      </label>
      <input
        id="address-search"
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Search address or intersection"
        autoComplete="off"
        onBlur={() => {
          window.setTimeout(() => {
            setResults([]);
            setError(null);
          }, 100);
        }}
        className="h-10 w-full rounded border border-neutral-300 bg-white px-3 text-sm text-neutral-950 outline-none transition placeholder:text-neutral-400 focus:border-neutral-950 focus:ring-2 focus:ring-neutral-950/10"
      />
      {showMenu ? (
        <div className="absolute left-0 right-0 top-12 z-30 overflow-hidden rounded border border-neutral-200 bg-white shadow-lg">
          {isLoading ? (
            <div className="px-3 py-2 text-sm text-neutral-500">Searching...</div>
          ) : null}
          {error ? (
            <div className="px-3 py-2 text-sm text-red-700">{error}</div>
          ) : null}
          {results.map((result) => (
            <button
              key={`${result.display}-${result.lat}-${result.lon}`}
              type="button"
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => {
                skipNextSearchRef.current = true;
                setQuery(result.display);
                setResults([]);
                onSelect(result);
              }}
              className="flex w-full items-center justify-between gap-3 border-b border-neutral-100 px-3 py-2 text-left text-sm last:border-b-0 hover:bg-neutral-50"
            >
              <span className="truncate font-medium text-neutral-900">
                {result.display}
              </span>
              {result.borough ? (
                <span className="shrink-0 text-xs text-neutral-500">
                  {result.borough}
                </span>
              ) : null}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

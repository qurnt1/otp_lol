import { useCallback, useEffect, useRef, useState } from "react";

import type { PageId } from "../types/api";
import { pageFromHash } from "./routes";

type NavigationGuard = (nextPage: PageId, currentPage: PageId) => boolean;

export function useHashRoute(guard?: NavigationGuard): readonly [PageId, (page: PageId) => void] {
  const initialPage = pageFromHash() ?? "dashboard";
  const [activePage, setActivePage] = useState<PageId>(initialPage);
  const currentPage = useRef(initialPage);
  const guardRef = useRef(guard);
  guardRef.current = guard;

  useEffect(() => {
    if (!pageFromHash()) window.history.replaceState(null, "", "#dashboard");
    const onHashChange = () => {
      const nextPage = pageFromHash();
      if (!nextPage) return;
      if (guardRef.current && !guardRef.current(nextPage, currentPage.current)) {
        window.history.replaceState(null, "", `#${currentPage.current}`);
        return;
      }
      currentPage.current = nextPage;
      setActivePage(nextPage);
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const navigate = useCallback((page: PageId) => {
    if (window.location.hash === `#${page}`) return;
    window.location.hash = `#${page}`;
  }, []);

  return [activePage, navigate];
}

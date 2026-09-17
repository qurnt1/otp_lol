import { useCallback, useEffect, useRef, useState } from "react";

import type { AppRoute } from "../types/api";
import { parseHashRoute, routeToHash } from "./routes";

type NavigationGuard = (nextRoute: AppRoute, currentRoute: AppRoute) => boolean;

export function useHashRoute(guard?: NavigationGuard): readonly [AppRoute, (route: AppRoute) => void, (route: AppRoute) => void] {
  const initialRoute = useRef<AppRoute>(parseHashRoute() ?? { page: "dashboard" }).current;
  const [activeRoute, setActiveRoute] = useState<AppRoute>(initialRoute);
  const currentRoute = useRef(initialRoute);
  const guardRef = useRef(guard);
  guardRef.current = guard;

  useEffect(() => {
    if (!parseHashRoute()) window.history.replaceState(null, "", routeToHash(initialRoute));
    const onHashChange = () => {
      const nextRoute = parseHashRoute();
      if (!nextRoute) {
        window.history.replaceState(null, "", routeToHash(currentRoute.current));
        return;
      }
      if (guardRef.current && !guardRef.current(nextRoute, currentRoute.current)) {
        window.history.replaceState(null, "", routeToHash(currentRoute.current));
        return;
      }
      currentRoute.current = nextRoute;
      setActiveRoute(nextRoute);
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, [initialRoute]);

  const navigate = useCallback((route: AppRoute, replace = false) => {
    const hash = routeToHash(route);
    if (replace) {
      window.history.replaceState(null, "", hash);
      currentRoute.current = route;
      setActiveRoute(route);
      return;
    }
    if (window.location.hash === hash) return;
    window.location.hash = hash;
  }, []);

  const replaceRoute = useCallback((route: AppRoute) => navigate(route, true), [navigate]);

  return [activeRoute, navigate, replaceRoute];
}

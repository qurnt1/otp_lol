import { useState, type ImgHTMLAttributes, type ReactNode } from "react";
import { cn } from "../../lib/cn";

interface AssetImageProps extends ImgHTMLAttributes<HTMLImageElement> {
  fallback?: ReactNode;
}

export function AssetImage({ fallback, className, onError, ...props }: AssetImageProps) {
  const [failedSource, setFailedSource] = useState<string | null>(null);
  const source = typeof props.src === "string" ? props.src : "";
  if (!source || failedSource === source) return <span className={cn("asset-fallback", className)} aria-hidden="true">{fallback}</span>;
  return <img {...props} className={className} onError={(event) => { setFailedSource(source); onError?.(event); }} />;
}

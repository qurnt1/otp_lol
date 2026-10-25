import { LoaderCircle, WifiOff } from "lucide-react";

import { Button } from "../../components/ui/button";
import { fr } from "../../content/fr";

type NetworkWarningProps = {
  state: "checking" | "offline";
  onRetry?: () => void;
};

export function NetworkWarning({ state, onRetry }: NetworkWarningProps) {
  const checking = state === "checking";
  return <section className="network-warning" aria-live="polite" role="status">
      <img className="network-warning-image" src="/assets/app/garen.webp" alt={fr.network.imageAlt} width="48" height="48" />
      <div className="network-warning-icon" aria-hidden="true">
        {checking ? <LoaderCircle className="is-spinning" size={22} /> : <WifiOff size={22} />}
      </div>
      <div className="network-warning-copy">
        <strong>{checking ? fr.network.checking : fr.network.warningTitle}</strong>
        <span>{checking ? fr.network.checkingMessage : fr.network.warningMessage}</span>
      </div>
      {!checking && <Button variant="primary" type="button" onClick={onRetry}>{fr.network.retry}</Button>}
    </section>;
}

import { LoaderCircle, WifiOff } from "lucide-react";

import { Button } from "../../components/ui/button";
import { fr } from "../../content/fr";

type NetworkGateProps = {
  state: "checking" | "offline";
  onRetry?: () => void;
};

export function NetworkGate({ state, onRetry }: NetworkGateProps) {
  const checking = state === "checking";
  return <main className="network-gate" aria-live="polite">
    <section className="network-gate-card" role="status">
      <img className="network-gate-image" src="/assets/app/garen.webp" alt={fr.network.imageAlt} width="112" height="112" />
      <div className="network-gate-icon" aria-hidden="true">
        {checking ? <LoaderCircle className="is-spinning" size={22} /> : <WifiOff size={22} />}
      </div>
      <h1>{checking ? fr.network.checking : fr.network.offlineTitle}</h1>
      <p>{checking ? fr.network.checkingMessage : fr.network.offlineMessage}</p>
      {!checking && <Button variant="primary" type="button" onClick={onRetry}>{fr.network.retry}</Button>}
    </section>
  </main>;
}

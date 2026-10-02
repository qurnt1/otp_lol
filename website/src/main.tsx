import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./site/App";
import "./styles.css";
import faviconUrl from "../../frontend/public/assets/app/garen.ico";

document.getElementById("site-favicon")?.setAttribute("href", faviconUrl);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

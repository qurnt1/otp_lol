import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "/otp_lol/",
  plugins: [react()],
});

import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/sora/600.css";
import "@fontsource/sora/700.css";
import "./styles/index.css";

import { MotionConfig } from "framer-motion";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { Background, ToastProvider } from "./components";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {/* reducedMotion="user" disables Framer transforms when the OS asks for less motion */}
    <MotionConfig reducedMotion="user">
      <BrowserRouter>
        <ToastProvider>
          <Background />
          <App />
        </ToastProvider>
      </BrowserRouter>
    </MotionConfig>
  </StrictMode>,
);

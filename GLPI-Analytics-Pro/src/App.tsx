import { BrowserRouter } from "react-router-dom";
import { Router } from "./routes/Router";
import { SettingsProvider } from "./contexts/SettingsContext";

export function App() {
  return (
    <BrowserRouter>
      <SettingsProvider>
        <Router />
      </SettingsProvider>
    </BrowserRouter>
  );
}

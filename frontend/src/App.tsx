import { Route, Routes } from "react-router-dom";
import { Home } from "./pages/Home";
import { NotFound } from "./pages/NotFound";
import { Styleguide } from "./pages/Styleguide";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/styleguide" element={<Styleguide />} />
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}

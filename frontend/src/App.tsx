import { Routes, Route } from "react-router-dom";
import HomePage from "./pages/HomePage";
import NarrativePage from "./pages/NarrativePage";
import PredictionPage from "./pages/PredictionPage";
import NotFoundPage from "./pages/NotFoundPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/match/:matchId" element={<NarrativePage />} />
      <Route path="/predictions" element={<PredictionPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}

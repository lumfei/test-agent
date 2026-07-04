import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppLayout } from './components/layout/AppLayout';
import { OnlineRunTestPage } from './pages/OnlineRunTestPage';
import { OfflineReportPage } from './pages/OfflineReportPage';
import { OnlineHistoryPage } from './pages/OnlineHistoryPage';
import { OfflineDetailPage } from './pages/OfflineDetailPage';
import { OnlineLoadResultPage } from './pages/OnlineLoadResultPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<Navigate to="/run" replace />} />
          <Route path="run" element={<OnlineRunTestPage />} />
          <Route path="history" element={<OnlineHistoryPage />} />
          <Route path="load" element={<OnlineLoadResultPage />} />
          <Route path="load/:runId" element={<OnlineLoadResultPage />} />
          <Route path="offline/report" element={<OfflineReportPage />} />
          <Route path="offline/detail" element={<OfflineDetailPage />} />
          <Route path="*" element={<Navigate to="/run" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;

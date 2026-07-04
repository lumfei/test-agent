import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { TabBar } from './TabBar';
import { Footer } from './Footer';

export function AppLayout() {

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <Sidebar />

      {/* Main Area */}
      <div className="flex-1 flex flex-col min-w-0">
        <TabBar />

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>

        <Footer />
      </div>
    </div>
  );
}

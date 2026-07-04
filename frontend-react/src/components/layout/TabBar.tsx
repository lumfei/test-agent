import { useNavigate, useLocation } from 'react-router-dom';
import { useAppStore } from '../../stores/useAppStore';
import { ONLINE_TABS, OFFLINE_TABS } from '../../utils/constants';

export function TabBar() {
  const mode = useAppStore((s) => s.mode);
  const navigate = useNavigate();
  const location = useLocation();

  const tabs = mode === 'online' ? ONLINE_TABS : OFFLINE_TABS;

  // Match current tab based on path
  const activeTab = tabs.find((t) => location.pathname === t.path)?.id || tabs[0]?.id;

  const handleTabClick = (tab: (typeof tabs)[0]) => {
    useAppStore.getState().setActiveTab(tab.id);
    navigate(tab.path);
  };

  return (
    <div className="border-b border-gray-200 bg-white">
      <nav className="flex gap-0 px-2">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => handleTabClick(tab)}
            className={`px-5 py-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.id
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </nav>
    </div>
  );
}

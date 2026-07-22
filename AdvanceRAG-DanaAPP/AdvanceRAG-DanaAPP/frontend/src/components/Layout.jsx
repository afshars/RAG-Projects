import { Outlet, NavLink } from 'react-router-dom';
import { Sparkles, MessageSquare, Upload, Settings as SettingsIcon, ClipboardList } from 'lucide-react';

const navItems = [
  { to: '/', label: 'گفت‌وگو', icon: MessageSquare, end: true },
  { to: '/knowledge', label: 'منابع', icon: Upload },
  { to: '/settings', label: 'تنظیمات', icon: SettingsIcon },
  { to: '/evaluation', label: 'ارزیابی', icon: ClipboardList },
];

export default function Layout() {
  return (
    <div className="flex flex-row h-screen overflow-hidden bg-background">
      <aside className="w-16 md:w-56 bg-sidebar border-l border-sidebar-border flex flex-col flex-shrink-0">
        <div className="p-3 md:p-4 flex items-center gap-2.5 border-b border-sidebar-border">
          <div className="w-9 h-9 rounded-xl bg-primary flex items-center justify-center flex-shrink-0 shadow-md shadow-primary/20">
            <Sparkles className="w-5 h-5 text-primary-foreground" />
          </div>
          <div className="hidden md:block">
            <h1 className="text-base font-bold text-foreground leading-tight">دانا</h1>
            <p className="text-[11px] text-muted-foreground leading-tight">سیستم پیشرفته RAG</p>
          </div>
        </div>

        <nav className="flex-1 p-2 md:p-3 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors justify-center md:justify-start ${
                  isActive
                    ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                    : 'text-sidebar-foreground hover:bg-sidebar-accent/50'
                }`
              }
            >
              <item.icon className="w-5 h-5 flex-shrink-0" />
              <span className="hidden md:inline">{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>

      <main className="flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
}

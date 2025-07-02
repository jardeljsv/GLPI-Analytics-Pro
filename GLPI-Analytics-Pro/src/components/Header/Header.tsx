/* Icons */
import { BellSimple, List, Question, UserCircle } from "phosphor-react";

import { NavItem } from "./NavItem/NavItem";
import { useSettings } from "@/contexts/SettingsContext";

export const Header = ({ toggleSidebar }: { toggleSidebar: () => void }) => {
  const { settings } = useSettings();

  return (
    <div className="bg-gray-50 flex p-8 h-16 justify-between  items-center text-slate-900 border-b-4 border-[var(--primary-color)]">
      <button
        type="button"
        className="flex items-center gap-2"
        onClick={toggleSidebar}
      >
        <NavItem icon={List} route="#" />
      </button>

      {settings.logo_url ? (
        <img src={settings.logo_url} className="w-24 h-18" alt="glpi" />
      ) : (
        <span className="text-2xl font-bold primary-text">GLPI Analytics</span>
      )}

      <nav className="flex gap-2">
        <NavItem icon={BellSimple} route="/main/notification" />
        <NavItem icon={Question} route="/main/help" />
        <NavItem icon={UserCircle} route="/main/system" />
      </nav>
    </div>
  );
};

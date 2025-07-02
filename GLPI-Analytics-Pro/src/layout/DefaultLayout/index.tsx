import { useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import { Header } from "../../components/Header/Header";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import { useSettings } from "@/contexts/SettingsContext";

export const DefaultLayout = () => {
  const [show, setShow] = useState(true);
  const sidebarStorageKey = "sidebar";
  const { settings } = useSettings();

  useEffect(() => {
    const savedStatusSidebar = localStorage.getItem(sidebarStorageKey);

    if (savedStatusSidebar !== null) {
      setShow(JSON.parse(savedStatusSidebar));
    }
  }, []);

  useEffect(() => {
    document.documentElement.style.setProperty('--primary-color', settings.primary_color);
    document.documentElement.style.setProperty('--secondary-color', settings.secondary_color);
  }, [settings.primary_color, settings.secondary_color]);

  function toggleSidebar() {
    const newValueShow = !show;

    setShow(newValueShow);
    localStorage.setItem(sidebarStorageKey, JSON.stringify(newValueShow));
  }

  return (
    <div className="grid h-screen grid-rows-[auto_1fr] grid-cols-[auto_1fr]">
      <div className="col-span-full">
        <Header toggleSidebar={() => toggleSidebar()} />
      </div>

      <Sidebar disabled={show} />

      <div className="flex flex-1 overflow-y-auto p-4">
        <Outlet />
      </div>
    </div>
  );
};

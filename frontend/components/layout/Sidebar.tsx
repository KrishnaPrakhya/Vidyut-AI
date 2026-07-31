"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function Sidebar() {
  const pathname = usePathname();

  const navItems = [
    { label: "Dashboard", href: "/dashboard", icon: "📊" },
    { label: "Simulation", href: "/simulation", icon: "⚡" },
    { label: "AI Models", href: "/models", icon: "🧠" },
    { label: "Reports", href: "/reports", icon: "📄" },
    { label: "About", href: "/about", icon: "ℹ️" },
    { label: "Settings", href: "/settings", icon: "⚙️" },
  ];

  return (
    <aside className="sidebar-nav">
      <div className="sidebar-header">
        <span className="kicker">COMMAND NAVIGATION</span>
      </div>

      <nav className="sidebar-menu">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`sidebar-link ${isActive ? "active" : ""}`}
            >
              <span className="sidebar-icon">{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}

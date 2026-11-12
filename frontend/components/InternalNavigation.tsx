"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAuth } from "../context/AuthContext";

type NavigationItem = { href: string; label: string };

export function InternalNavigation({ items = [] }: { items?: NavigationItem[] }) {
  const router = useRouter();
  const { signOut } = useAuth();

  function handleLogout() {
    signOut();
    router.replace("/login");
  }

  return <nav className="campaign-navigation internal-navigation" aria-label="Навигация приложения">
    <div className="internal-navigation-left">
      <Link className="internal-navigation-brand" href="/campaigns">MORDHEIM</Link>
      <Link aria-label="Раздел кампаний" className="text-button" href="/campaigns">Кампании</Link>
      {items.map((item) => <Link className="text-button" href={item.href} key={item.href}>{item.label}</Link>)}
    </div>
    <div className="internal-navigation-right">
      <Link className="text-button" href="/profile">Личный кабинет</Link>
      <button className="text-button" type="button" onClick={handleLogout}>Выйти</button>
    </div>
  </nav>;
}

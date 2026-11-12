"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "../../context/AuthContext";
import { ApiError, clearNotifications, getNotifications, markAllNotificationsRead, markNotificationRead, Notification } from "../../lib/api";

export function NotificationBell() {
  const { accessToken } = useAuth();
  const router = useRouter();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");

  const refresh = useCallback(() => {
    if (accessToken) getNotifications(accessToken).then(setNotifications).catch((error) => { if (!(error instanceof ApiError && error.status === 401)) return; });
  }, [accessToken]);

  useEffect(() => {
    refresh();
    const interval = window.setInterval(refresh, 30000);
    window.addEventListener("focus", refresh);
    return () => { window.clearInterval(interval); window.removeEventListener("focus", refresh); };
  }, [refresh]);

  async function read(id: string) {
    if (!accessToken) return;
    await markNotificationRead(accessToken, id);
    setNotifications((items) => items.map((item) => item.id === id ? { ...item, is_read: true } : item));
  }

  async function readAll() {
    if (!accessToken) return;
    await markAllNotificationsRead(accessToken);
    setNotifications((items) => items.map((item) => ({ ...item, is_read: true })));
  }

  async function clear() {
    if (!accessToken || !window.confirm("Очистить все уведомления?")) return;
    await clearNotifications(accessToken);
    setNotifications([]);
  }

  function targetFor(item: Notification): string | null {
    if (item.notification_type === "invitation") return "/profile#invitations";
    if (item.notification_type === "join_request" && item.campaign_id) return `/campaigns/${item.campaign_id}#join-requests`;
    if (["join_request_approved", "invitation_accepted", "master_transferred", "member_left"].includes(item.notification_type) && item.campaign_id) return `/campaigns/${item.campaign_id}#members`;
    if (item.notification_type === "member_excluded") return null;
    if (["join_request_rejected", "invitation_declined", "invitation_revoked"].includes(item.notification_type)) return "/profile#notifications";
    return item.campaign_id ? `/campaigns/${item.campaign_id}` : null;
  }

  async function openNotification(item: Notification) {
    if (!accessToken) return;
    try {
      if (!item.is_read) {
        await markNotificationRead(accessToken, item.id);
        setNotifications((items) => items.map((current) => current.id === item.id ? { ...current, is_read: true } : current));
      }
    } catch { /* Do not block safe navigation if marking read temporarily fails. */ }
    const target = targetFor(item);
    if (target) { setOpen(false); router.push(target); }
    else setMessage("Это уведомление сохранено в истории. Доступ к кампании больше недоступен.");
  }

  const unread = notifications.some((item) => !item.is_read);
  return <div className="notification-bell" id="notifications"><button type="button" className={unread ? "bell-button bell-unread" : "bell-button"} title="Уведомления" aria-label="Уведомления" onClick={() => setOpen((value) => !value)}><svg className="bell-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4" /></svg>{unread && <span className="notification-dot" />}</button>{message && <p className="form-message form-error" role="alert">{message}</p>}{open && <div className="notification-panel"><div className="notification-header"><strong>Уведомления</strong><button type="button" onClick={readAll}>Прочитать все</button></div>{notifications.length === 0 ? <p className="auth-intro">Новых уведомлений нет.</p> : notifications.map((item) => <button type="button" className={item.is_read ? "notification-item" : "notification-item notification-new"} key={item.id} onClick={() => openNotification(item)}><strong>{item.title}</strong><span>{item.message}</span></button>)}<button type="button" className="notification-clear" onClick={clear}>Очистить уведомления</button></div>}</div>;
}

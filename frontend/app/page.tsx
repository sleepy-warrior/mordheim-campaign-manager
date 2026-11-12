import Link from "next/link";

export default function Home() {
  return (
    <main className="auth-page">
      <section className="auth-card">
        <div className="eyebrow">MORDHEIM CAMPAIGN MANAGER</div>
        <h1>Врата города проклятых</h1>
        <p className="auth-intro">
          Управляйте кампанией, пока руины ещё хранят тайны. Войдите или создайте
          учётную запись, чтобы начать.
        </p>
        <p>
          <Link href="/login">Войти</Link> · <Link href="/register">Регистрация</Link>
        </p>
      </section>
    </main>
  );
}

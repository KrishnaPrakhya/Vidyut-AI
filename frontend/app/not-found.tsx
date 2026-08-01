import Link from "next/link";

export default function NotFound() {
  return <main className="system-page">
    <div className="system-page-mark">V</div>
    <p className="system-page-code">Route status / 404</p>
    <h1>That console view is not on this grid.</h1>
    <p>The address may be incomplete, or the workspace has moved. Return to Vidyut to continue operating from a known state.</p>
    <Link href="/">Return to Vidyut <span>→</span></Link>
  </main>;
}
